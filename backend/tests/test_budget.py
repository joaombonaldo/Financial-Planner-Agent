from datetime import date

import pytest
from langgraph.types import Command

from financial_planner.db import repository
from financial_planner.graph import build_graph
from financial_planner.nodes.budget import check_budget
from financial_planner.state import Bank, BudgetNotConfiguredError, BudgetStatus, Transaction, TransactionType
from tests.fixtures.review.builders import seed_categorized_transaction

MONTH_REF = "2026-08"


def _write_budget(tmp_path, goals: dict) -> str:
    import yaml

    path = tmp_path / "budget.local.yaml"
    path.write_text(yaml.dump(goals), encoding="utf-8")
    return str(path)


def _comparison(results, category):
    return next(r for r in results if r.category == category)


# --- User Story 1: actual spend vs. goal -------------------------------------------------


def test_budget_within_budget(tmp_path):
    db_path = str(tmp_path / "test.db")
    budget_path = _write_budget(tmp_path, {"Alimentação": 500.0})

    conn = repository.connect(db_path)
    seed_categorized_transaction(conn, "hash-1", "Mercado A", category="Alimentação", confidence="high", amount=100.0)
    seed_categorized_transaction(conn, "hash-2", "Mercado B", category="Alimentação", confidence="high", amount=150.0)
    conn.close()

    results = check_budget(MONTH_REF, db_path, budget_path)
    comparison = _comparison(results, "Alimentação")

    assert comparison.actual_spend == 250.0
    assert comparison.difference == 250.0
    assert comparison.status == BudgetStatus.WITHIN_BUDGET


def test_budget_over_budget(tmp_path):
    db_path = str(tmp_path / "test.db")
    budget_path = _write_budget(tmp_path, {"Alimentação": 200.0})

    conn = repository.connect(db_path)
    seed_categorized_transaction(conn, "hash-3", "Mercado A", category="Alimentação", confidence="high", amount=300.0)
    conn.close()

    results = check_budget(MONTH_REF, db_path, budget_path)
    comparison = _comparison(results, "Alimentação")

    assert comparison.actual_spend == 300.0
    assert comparison.difference == -100.0
    assert comparison.status == BudgetStatus.OVER_BUDGET


def test_budget_exact_equal_is_within(tmp_path):
    db_path = str(tmp_path / "test.db")
    budget_path = _write_budget(tmp_path, {"Transporte": 100.0})

    conn = repository.connect(db_path)
    seed_categorized_transaction(conn, "hash-4", "Uber", category="Transporte", confidence="high", amount=100.0)
    conn.close()

    results = check_budget(MONTH_REF, db_path, budget_path)
    comparison = _comparison(results, "Transporte")

    assert comparison.actual_spend == 100.0
    assert comparison.difference == 0.0
    assert comparison.status == BudgetStatus.WITHIN_BUDGET


def test_budget_zero_transactions_category(tmp_path):
    db_path = str(tmp_path / "test.db")
    budget_path = _write_budget(tmp_path, {"Educação": 300.0})
    repository.connect(db_path).close()

    results = check_budget(MONTH_REF, db_path, budget_path)
    comparison = _comparison(results, "Educação")

    assert comparison.actual_spend == 0.0
    assert comparison.status == BudgetStatus.WITHIN_BUDGET


def test_budget_missing_config_raises_error(tmp_path):
    db_path = str(tmp_path / "test.db")
    repository.connect(db_path).close()
    missing_path = str(tmp_path / "does-not-exist.yaml")

    with pytest.raises(BudgetNotConfiguredError):
        check_budget(MONTH_REF, db_path, missing_path)


# --- User Story 2: transfers and income excluded ------------------------------------------


def test_budget_excludes_transfers(tmp_path):
    db_path = str(tmp_path / "test.db")
    budget_path = _write_budget(tmp_path, {"Transferência interna": 100.0})

    conn = repository.connect(db_path)
    seed_categorized_transaction(
        conn, "hash-5", "PIX ENVIADO", category="Transferência interna", confidence="high", amount=500.0
    )
    conn.close()

    results = check_budget(MONTH_REF, db_path, budget_path)
    comparison = _comparison(results, "Transferência interna")

    assert comparison.actual_spend == 0.0


def test_budget_excludes_income(tmp_path):
    from financial_planner.state import TransactionType

    db_path = str(tmp_path / "test.db")
    budget_path = _write_budget(tmp_path, {"Receita": 1000.0})

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

    results = check_budget(MONTH_REF, db_path, budget_path)
    comparison = _comparison(results, "Receita")

    assert comparison.actual_spend == 0.0


# --- Full-chain smoke test (no LLM involved) -----------------------------------------------


def test_full_chain_produces_budget_report(tmp_path):
    """Driving the real graph end to end (no LLM, via a pre-populated merchant memory)
    produces a budget_report that correctly excludes a confirmed transfer."""
    db_path = str(tmp_path / "test.db")
    budget_path = _write_budget(tmp_path, {"Transporte": 50.0, "Transferência interna": 999.0})

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
            "budget_path": budget_path,
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
