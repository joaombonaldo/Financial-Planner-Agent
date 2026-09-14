from datetime import date

from langgraph.types import Command

from financial_planner.db import repository
from financial_planner.graph import build_graph
from financial_planner.nodes.budget import check_budget
from financial_planner.state import Bank, BudgetStatus, Transaction, TransactionType
from tests.fixtures.review.builders import seed_categorized_transaction

MONTH_REF = "2026-08"


def _seed_budget(db_path: str, goals: dict, month_ref: str | None = None) -> None:
    """Seed the default scope (month_ref=None) or one month's overrides."""
    conn = repository.connect(db_path)
    repository.replace_budget_goals(
        conn, month_ref or repository.DEFAULT_BUDGET_SCOPE, goals
    )
    conn.close()


def _comparison(results, category):
    return next(r for r in results if r.category == category)


# --- User Story 1: actual spend vs. goal -------------------------------------------------


def test_budget_within_budget(tmp_path):
    db_path = str(tmp_path / "test.db")
    _seed_budget(db_path, {"Alimentação": 500.0})

    conn = repository.connect(db_path)
    seed_categorized_transaction(conn, "hash-1", "Mercado A", category="Alimentação", confidence="high", amount=100.0)
    seed_categorized_transaction(conn, "hash-2", "Mercado B", category="Alimentação", confidence="high", amount=150.0)
    conn.close()

    results = check_budget(MONTH_REF, db_path)
    comparison = _comparison(results, "Alimentação")

    assert comparison.actual_spend == 250.0
    assert comparison.difference == 250.0
    assert comparison.status == BudgetStatus.WITHIN_BUDGET


def test_budget_over_budget(tmp_path):
    db_path = str(tmp_path / "test.db")
    _seed_budget(db_path, {"Alimentação": 200.0})

    conn = repository.connect(db_path)
    seed_categorized_transaction(conn, "hash-3", "Mercado A", category="Alimentação", confidence="high", amount=300.0)
    conn.close()

    results = check_budget(MONTH_REF, db_path)
    comparison = _comparison(results, "Alimentação")

    assert comparison.actual_spend == 300.0
    assert comparison.difference == -100.0
    assert comparison.status == BudgetStatus.OVER_BUDGET


def test_budget_exact_equal_is_within(tmp_path):
    db_path = str(tmp_path / "test.db")
    _seed_budget(db_path, {"Transporte": 100.0})

    conn = repository.connect(db_path)
    seed_categorized_transaction(conn, "hash-4", "Uber", category="Transporte", confidence="high", amount=100.0)
    conn.close()

    results = check_budget(MONTH_REF, db_path)
    comparison = _comparison(results, "Transporte")

    assert comparison.actual_spend == 100.0
    assert comparison.difference == 0.0
    assert comparison.status == BudgetStatus.WITHIN_BUDGET


def test_budget_zero_transactions_category(tmp_path):
    db_path = str(tmp_path / "test.db")
    _seed_budget(db_path, {"Educação": 300.0})
    repository.connect(db_path).close()

    results = check_budget(MONTH_REF, db_path)
    comparison = _comparison(results, "Educação")

    assert comparison.actual_spend == 0.0
    assert comparison.status == BudgetStatus.WITHIN_BUDGET


def test_budget_with_no_goals_configured_is_empty_not_an_error(tmp_path):
    db_path = str(tmp_path / "test.db")
    repository.connect(db_path).close()

    results = check_budget(MONTH_REF, db_path)

    assert results == []


# --- User Story 1b: month-level overrides -------------------------------------------------


def test_budget_month_override_takes_precedence_over_default(tmp_path):
    db_path = str(tmp_path / "test.db")
    _seed_budget(db_path, {"Lazer": 300.0})
    _seed_budget(db_path, {"Lazer": 800.0}, month_ref=MONTH_REF)

    conn = repository.connect(db_path)
    seed_categorized_transaction(conn, "hash-lazer", "Viagem", category="Lazer", confidence="high", amount=500.0)
    conn.close()

    results = check_budget(MONTH_REF, db_path)
    comparison = _comparison(results, "Lazer")

    assert comparison.goal == 800.0
    assert comparison.status == BudgetStatus.WITHIN_BUDGET


def test_budget_falls_back_to_default_for_a_category_the_month_does_not_override(tmp_path):
    db_path = str(tmp_path / "test.db")
    _seed_budget(db_path, {"Lazer": 300.0, "Transporte": 100.0})
    _seed_budget(db_path, {"Lazer": 800.0}, month_ref=MONTH_REF)  # Transporte untouched

    results = check_budget(MONTH_REF, db_path)

    assert _comparison(results, "Lazer").goal == 800.0
    assert _comparison(results, "Transporte").goal == 100.0


def test_budget_override_for_a_different_month_does_not_leak(tmp_path):
    db_path = str(tmp_path / "test.db")
    _seed_budget(db_path, {"Lazer": 300.0})
    _seed_budget(db_path, {"Lazer": 800.0}, month_ref="2026-07")

    results = check_budget(MONTH_REF, db_path)

    assert _comparison(results, "Lazer").goal == 300.0


# --- User Story 2: transfers and income excluded ------------------------------------------


def test_budget_excludes_transfers(tmp_path):
    db_path = str(tmp_path / "test.db")
    _seed_budget(db_path, {"Transferência interna": 100.0})

    conn = repository.connect(db_path)
    seed_categorized_transaction(
        conn, "hash-5", "PIX ENVIADO", category="Transferência interna", confidence="high", amount=500.0
    )
    conn.close()

    results = check_budget(MONTH_REF, db_path)
    comparison = _comparison(results, "Transferência interna")

    assert comparison.actual_spend == 0.0


def test_budget_excludes_income(tmp_path):
    db_path = str(tmp_path / "test.db")
    _seed_budget(db_path, {"Receita": 1000.0})

    conn = repository.connect(db_path)
    seed_categorized_transaction(
        conn,
        "hash-6",
        "Salário",
        category="Receita",
        confidence="high",
        amount=5000.0,
        tx_type=TransactionType.INCOME,
    )
    conn.close()

    results = check_budget(MONTH_REF, db_path)
    comparison = _comparison(results, "Receita")

    assert comparison.actual_spend == 0.0


# --- Full-chain smoke test (no LLM involved) -----------------------------------------------


def test_full_chain_produces_budget_report(tmp_path):
    """Driving the real graph end to end (no LLM, via a pre-populated merchant memory)
    produces a budget_report that correctly excludes a confirmed transfer."""
    db_path = str(tmp_path / "test.db")
    _seed_budget(db_path, {"Transporte": 50.0, "Transferência interna": 999.0})

    conn = repository.connect(db_path)
    repository.upsert_merchant_category(conn, "uber uber *trip", "Transporte", "Uber/99")
    repository.insert_transaction(
        conn,
        Transaction(
            dedup_hash="hash-smoke-expense",
            date=date(2026, 9, 5),
            description_raw="Uber Uber *trip",
            account=Bank.INTER,
            type=TransactionType.EXPENSE,
            amount=80.0,
            month_ref="2026-09",
        ),
    )
    seed_categorized_transaction(
        conn,
        "hash-smoke-transfer",
        "PIX ENVIADO",
        category="Transferência interna",
        confidence="medium",
        account=Bank.INTER,
        transaction_date=date(2026, 9, 5),
    )
    conn.close()

    graph = build_graph(db_path)
    result = graph.invoke(
        {
            "source_files": [],
            "month_ref": "2026-09",
            "db_path": db_path,
        },
        config={"configurable": {"thread_id": "2026-09"}},
    )

    while result.get("__interrupt__"):
        payload = result["__interrupt__"][0].value
        answer = "confirmar" if payload["is_transfer_candidate"] else "aceitar"
        result = graph.invoke(
            Command(resume=answer), config={"configurable": {"thread_id": "2026-09"}}
        )

    report = {entry["category"]: entry for entry in result["budget_report"]}

    assert report["Transporte"]["actual_spend"] == 80.0
    assert report["Transporte"]["status"] == "over_budget"
    assert report["Transferência interna"]["actual_spend"] == 0.0
