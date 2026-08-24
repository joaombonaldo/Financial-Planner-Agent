from financial_planner.db import repository
from financial_planner.nodes.budget import check_budget
from financial_planner.nodes.insights import generate_insights
from financial_planner.nodes.report import generate_report
from financial_planner.state import TransactionType
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


def _write_budget(tmp_path, goals: dict) -> str:
    import yaml

    path = tmp_path / "budget.local.yaml"
    path.write_text(yaml.dump(goals), encoding="utf-8")
    return str(path)


def test_full_chain_produces_complete_report(tmp_path):
    """Feeding each node's real output into the next (no LangGraph machinery, no real
    LLM — same reasoning as feature 006's smoke test, since generate_insights always
    needs the LLM and GraphState has no injection point for it) confirms the three
    final nodes' outputs are shape-compatible end to end."""
    db_path = str(tmp_path / "test.db")
    budget_path = _write_budget(tmp_path, {"Transporte": 100.0})

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

    comparisons = check_budget(MONTH_REF, db_path, budget_path)
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
