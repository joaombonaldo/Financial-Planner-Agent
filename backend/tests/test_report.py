from datetime import date

from financial_planner.categorization.taxonomy import CREDIT_CARD_CATEGORY
from financial_planner.db import repository
from financial_planner.nodes.budget import check_budget
from financial_planner.nodes.insights import generate_insights
from financial_planner.nodes.report import generate_report
from financial_planner.state import Instrument, TransactionType
from tests.fixtures.categorization.llm_double import FakeChatModel
from tests.fixtures.review.builders import seed_categorized_transaction

MONTH_REF = "2026-08"


# --- User Story 1: complete financial picture --------------------------------------------


def test_report_totals_match_manual_arithmetic(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    seed_categorized_transaction(
        conn, "hash-1", "Salário", category="Receita", confidence="high", amount=5000.0, tx_type=TransactionType.INCOME
    )
    seed_categorized_transaction(
        conn, "hash-2", "Mercado A", category="Alimentação", confidence="high", amount=300.0
    )
    seed_categorized_transaction(
        conn, "hash-3", "Uber", category="Transporte", confidence="high", amount=150.0
    )
    conn.close()

    report = generate_report(MONTH_REF, db_path)

    assert report.total_income == 5000.0
    assert report.total_expense == 450.0
    assert report.net_balance == 4550.0


def test_report_breakdown_includes_non_goal_categories(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    seed_categorized_transaction(
        conn, "hash-4", "Loja X", category="Vestuário", confidence="high", amount=80.0
    )
    conn.close()

    report = generate_report(MONTH_REF, db_path)

    entry = next(e for e in report.category_breakdown if e.category == "Vestuário")
    assert entry.total == 80.0
    assert entry.type == TransactionType.EXPENSE


def test_report_zero_transactions_all_zero(tmp_path):
    db_path = str(tmp_path / "test.db")
    repository.connect(db_path).close()

    report = generate_report(MONTH_REF, db_path)

    assert report.total_income == 0.0
    assert report.total_expense == 0.0
    assert report.net_balance == 0.0
    assert report.category_breakdown == []
    assert report.transaction_count == 0


# --- User Story 2: transfers kept separate -------------------------------------------------


def test_report_excludes_transfers_from_totals(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    seed_categorized_transaction(
        conn, "hash-5", "PIX ENVIADO", category="Transferência interna", confidence="high", amount=1000.0
    )
    seed_categorized_transaction(
        conn, "hash-6", "Mercado A", category="Alimentação", confidence="high", amount=100.0
    )
    conn.close()

    report = generate_report(MONTH_REF, db_path)

    assert report.transfer_total == 1000.0
    assert report.total_income == 0.0
    assert report.total_expense == 100.0
    assert all(e.category != "Transferência interna" for e in report.category_breakdown)


# --- Feature 012: shared-expense reimbursement netting -----------------------------------


def test_reimbursement_excluded_from_income_and_nets_the_category(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    seed_categorized_transaction(
        conn, "r-1", "Salário", category="Receita", subcategory="Salário",
        confidence="high", amount=5000.0, tx_type=TransactionType.INCOME,
    )
    seed_categorized_transaction(
        conn, "r-2", "SUPERMERCADO XPTO", category="Alimentação", subcategory="Mercado",
        confidence="high", amount=800.0,
    )
    seed_categorized_transaction(
        conn, "r-3", "PIX RECEBIDO IRMAO - divisao mercado", category="Receita",
        subcategory="Reembolso", confidence="high", amount=400.0,
        tx_type=TransactionType.INCOME,
    )
    conn.close()

    report = generate_report(MONTH_REF, db_path)

    # Reembolso is NOT income.
    assert report.total_income == 5000.0
    assert report.total_reimbursements == 400.0
    # Expense and net balance are net of the reimbursement.
    assert report.total_expense == 400.0
    assert report.net_balance == 4600.0

    entry = next(e for e in report.category_breakdown if e.category == "Alimentação")
    assert entry.gross == 800.0
    assert entry.reimbursed == 400.0
    assert entry.net == 400.0
    assert entry.total == 400.0  # `total` holds the net figure for existing consumers
    assert report.unattributed_reimbursements == 0.0


def test_unattributed_reimbursement_reduces_total_only(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    seed_categorized_transaction(
        conn, "u-1", "SUPERMERCADO XPTO", category="Alimentação", subcategory="Mercado",
        confidence="high", amount=800.0,
    )
    seed_categorized_transaction(
        conn, "u-2", "PIX RECEBIDO", category="Receita", subcategory="Reembolso",
        confidence="high", amount=400.0, tx_type=TransactionType.INCOME,
    )
    conn.close()

    report = generate_report(MONTH_REF, db_path)

    assert report.total_reimbursements == 400.0
    assert report.unattributed_reimbursements == 400.0
    assert report.total_expense == 400.0  # 800 gross - 400 unattributed
    assert report.net_balance == -400.0

    entry = next(e for e in report.category_breakdown if e.category == "Alimentação")
    assert entry.gross == 800.0
    assert entry.reimbursed == 0.0
    assert entry.total == 800.0  # category line untouched


def test_report_without_reimbursements_leaves_fields_zero(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    seed_categorized_transaction(
        conn, "n-1", "Mercado A", category="Alimentação", subcategory="Mercado",
        confidence="high", amount=100.0,
    )
    conn.close()

    report = generate_report(MONTH_REF, db_path)

    assert report.total_reimbursements == 0.0
    assert report.unattributed_reimbursements == 0.0
    assert report.total_expense == 100.0
    entry = next(e for e in report.category_breakdown if e.category == "Alimentação")
    assert entry.gross == entry.net == entry.total == 100.0
    assert entry.reimbursed == 0.0


# --- User Story 3: budget and insights carried through unmodified --------------------------


def test_report_carries_budget_and_insights_through_unmodified(tmp_path):
    db_path = str(tmp_path / "test.db")
    repository.connect(db_path).close()

    budget_report = [
        {"category": "Transporte", "goal": 300.0, "actual_spend": 400.0, "difference": -100.0, "status": "over_budget"}
    ]

    report = generate_report(
        MONTH_REF,
        db_path,
        budget_report=budget_report,
        insights_summary="Resumo do mês.",
        insights_error=None,
    )

    assert report.budget_report == budget_report
    assert report.insights_summary == "Resumo do mês."
    assert report.insights_error is None


# --- Smoke test: budget_check -> generate_insights -> generate_report, chained -----------


def _seed_budget(db_path: str, goals: dict) -> None:
    conn = repository.connect(db_path)
    repository.replace_budget_goals(conn, repository.DEFAULT_BUDGET_SCOPE, goals)
    conn.close()


def test_full_chain_produces_complete_report(tmp_path):
    """Feeding each node's real output into the next (no LangGraph machinery, no real
    LLM — same reasoning as feature 006's smoke test, since generate_insights always
    needs the LLM and GraphState has no injection point for it) confirms the three
    final nodes' outputs are shape-compatible end to end."""
    db_path = str(tmp_path / "test.db")
    _seed_budget(db_path, {"Transporte": 100.0})

    conn = repository.connect(db_path)
    seed_categorized_transaction(
        conn, "hash-7", "Uber", category="Transporte", confidence="high", amount=250.0
    )
    seed_categorized_transaction(
        conn,
        "hash-8",
        "Salário",
        category="Receita",
        confidence="high",
        amount=3000.0,
        tx_type=TransactionType.INCOME,
    )
    conn.close()

    comparisons = check_budget(MONTH_REF, db_path)
    budget_report = [
        {
            "category": c.category,
            "goal": c.goal,
            "actual_spend": c.actual_spend,
            "difference": c.difference,
            "status": c.status.value,
        }
        for c in comparisons
    ]

    insights_result = generate_insights(
        MONTH_REF, db_path, budget_report=budget_report, chat_model=FakeChatModel("Transporte estourou.")
    )

    report = generate_report(
        MONTH_REF,
        db_path,
        budget_report=budget_report,
        insights_summary=insights_result.summary,
        insights_error=insights_result.error,
    )

    assert report.total_income == 3000.0
    assert report.total_expense == 250.0
    assert report.net_balance == 2750.0
    assert report.budget_report == budget_report
    assert report.insights_summary == "Transporte estourou."
    assert report.insights_error is None
    assert report.transaction_count == 2


# --- Feature 014: dual-stream report (credit-card purchases) -----------------------------


def test_credit_purchases_excluded_from_headline_totals(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    seed_categorized_transaction(
        conn, "hash-debit", "Mercado A", category="Alimentação", confidence="high", amount=300.0
    )
    seed_categorized_transaction(
        conn,
        "hash-credit",
        "Restaurante Y",
        category="Lazer",
        subcategory="Restaurante/Bar",
        confidence="high",
        amount=200.0,
        instrument=Instrument.CREDIT,
    )
    conn.close()

    report = generate_report(MONTH_REF, db_path)

    # Only the debit purchase counts toward the headline total / breakdown.
    assert report.total_expense == 300.0
    assert not any(e.category == "Lazer" for e in report.category_breakdown)


def test_credit_category_breakdown_reports_this_months_card_purchases(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    seed_categorized_transaction(
        conn,
        "hash-credit-1",
        "Restaurante Y",
        category="Lazer",
        subcategory="Restaurante/Bar",
        confidence="high",
        amount=200.0,
        instrument=Instrument.CREDIT,
    )
    seed_categorized_transaction(
        conn,
        "hash-credit-2",
        "Perfumaria Z",
        category="Compras",
        subcategory="Perfumes/Cosméticos",
        confidence="high",
        amount=90.0,
        instrument=Instrument.CREDIT,
    )
    conn.close()

    report = generate_report(MONTH_REF, db_path)

    assert report.credit_total == 290.0
    breakdown = {e.category: e.total for e in report.credit_category_breakdown}
    assert breakdown == {"Lazer": 200.0, "Compras": 90.0}


def test_credit_breakdown_skips_unreviewed_purchases(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    seed_categorized_transaction(
        conn,
        "hash-pending",
        "Loja qualquer",
        category="Compras",
        confidence="medium",
        amount=50.0,
        instrument=Instrument.CREDIT,
    )
    conn.close()

    report = generate_report(MONTH_REF, db_path)

    assert report.credit_category_breakdown == []
    assert report.credit_total == 0.0


def test_fatura_reconciliation_matches_purchases_to_payment_line(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    # Two card purchases in July, belonging to the fatura due/paid in August.
    seed_categorized_transaction(
        conn,
        "hash-purchase-1",
        "Restaurante Y",
        category="Lazer",
        confidence="high",
        amount=120.0,
        instrument=Instrument.CREDIT,
        fatura_ref="2026-08",
        transaction_date=date(2026, 7, 15),
    )
    seed_categorized_transaction(
        conn,
        "hash-purchase-2",
        "Perfumaria Z",
        category="Compras",
        confidence="high",
        amount=80.0,
        instrument=Instrument.CREDIT,
        fatura_ref="2026-08",
        transaction_date=date(2026, 7, 20),
    )
    conn.close()

    # The debit payment line lands in August; confirming it as the card-bill
    # category auto-links fatura_ref (see db/repository.py).
    conn = repository.connect(db_path)
    seed_categorized_transaction(
        conn,
        "hash-payment",
        "Pagamento Fatura",
        category=CREDIT_CARD_CATEGORY,
        confidence="high",
        amount=200.0,
    )
    conn.close()

    report = generate_report(MONTH_REF, db_path)

    assert len(report.fatura_reconciliations) == 1
    reconciliation = report.fatura_reconciliations[0]
    assert reconciliation.fatura_ref == MONTH_REF
    assert reconciliation.debit_payment == 200.0
    assert reconciliation.credit_purchases_total == 200.0
    assert reconciliation.delta == 0.0


def test_fatura_reconciliation_flags_a_delta(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    seed_categorized_transaction(
        conn,
        "hash-purchase",
        "Restaurante Y",
        category="Lazer",
        confidence="high",
        amount=120.0,
        instrument=Instrument.CREDIT,
        fatura_ref="2026-08",
        transaction_date=date(2026, 7, 15),
    )
    conn.close()

    conn = repository.connect(db_path)
    # Bill is 5.90 higher than the itemized purchases — a plausible fatura fee.
    seed_categorized_transaction(
        conn,
        "hash-payment",
        "Pagamento Fatura",
        category=CREDIT_CARD_CATEGORY,
        confidence="high",
        amount=125.90,
    )
    conn.close()

    report = generate_report(MONTH_REF, db_path)

    reconciliation = report.fatura_reconciliations[0]
    assert round(reconciliation.delta, 2) == 5.90


def test_no_fatura_line_means_no_reconciliation(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    seed_categorized_transaction(
        conn, "hash-debit", "Mercado A", category="Alimentação", confidence="high", amount=300.0
    )
    conn.close()

    report = generate_report(MONTH_REF, db_path)

    assert report.fatura_reconciliations == []
