from datetime import date

from financial_planner.db import repository
from financial_planner.nodes.budget import check_budget
from financial_planner.nodes.insights import generate_insights
from financial_planner.state import TransactionType
from tests.fixtures.categorization.llm_double import FakeChatModel, RaisingChatModel
from tests.fixtures.review.builders import seed_categorized_transaction

MONTH_REF = "2026-08"
PREVIOUS_MONTH_REF = "2026-07"


# --- User Story 1: grounded summary for a single month ----------------------------------


def test_insights_summary_grounded_in_real_data(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    seed_categorized_transaction(
        conn, "hash-1", "Mercado A", category="Alimentação", confidence="high", amount=250.0
    )
    conn.close()

    fake_llm = FakeChatModel("Você gastou principalmente com Alimentação este mês.")
    result = generate_insights(MONTH_REF, db_path, chat_model=fake_llm)

    assert result.summary == "Você gastou principalmente com Alimentação este mês."
    assert result.error is None
    assert "Alimentação" in fake_llm.calls[0]
    assert "250.00" in fake_llm.calls[0]


def test_insights_includes_budget_report_in_context(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    seed_categorized_transaction(
        conn, "hash-2", "Uber", category="Transporte", confidence="high", amount=400.0
    )
    conn.close()

    budget_report = [
        {"category": "Transporte", "goal": 300.0, "actual_spend": 400.0, "difference": -100.0, "status": "over_budget"}
    ]
    fake_llm = FakeChatModel("Transporte estourou o orçamento.")
    generate_insights(MONTH_REF, db_path, budget_report=budget_report, chat_model=fake_llm)

    prompt = fake_llm.calls[0]
    assert "Transporte" in prompt
    assert "ACIMA do orçamento" in prompt


# --- Feature 012: shared-expense reimbursement netting in the prompt context ------------


def test_insights_context_includes_reimbursement_netting(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    seed_categorized_transaction(
        conn, "rb-1", "SUPERMERCADO XPTO", category="Alimentação", subcategory="Mercado",
        confidence="high", amount=800.0,
    )
    seed_categorized_transaction(
        conn, "rb-2", "PIX RECEBIDO IRMAO - divisao mercado", category="Receita",
        subcategory="Reembolso", confidence="high", amount=400.0,
        tx_type=TransactionType.INCOME,
    )
    conn.close()

    fake_llm = FakeChatModel("mercado saiu por metade.")
    result = generate_insights(MONTH_REF, db_path, chat_model=fake_llm)

    assert result.summary == "mercado saiu por metade."
    prompt = fake_llm.calls[0]
    assert "Alimentação: R$ 800.00 bruto, R$ 400.00 reembolsado, R$ 400.00 líquido" in prompt


def test_insights_unattributed_reimbursement_in_context(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    seed_categorized_transaction(
        conn, "ru-1", "SUPERMERCADO XPTO", category="Alimentação", subcategory="Mercado",
        confidence="high", amount=800.0,
    )
    seed_categorized_transaction(
        conn, "ru-2", "PIX RECEBIDO", category="Receita", subcategory="Reembolso",
        confidence="high", amount=400.0, tx_type=TransactionType.INCOME,
    )
    conn.close()

    fake_llm = FakeChatModel("resumo.")
    generate_insights(MONTH_REF, db_path, chat_model=fake_llm)

    prompt = fake_llm.calls[0]
    assert "não atribuídos a uma categoria" in prompt
    assert "R$ 400.00" in prompt


def test_insights_no_reimbursement_section_when_none(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    seed_categorized_transaction(
        conn, "rn-1", "Mercado A", category="Alimentação", subcategory="Mercado",
        confidence="high", amount=100.0,
    )
    conn.close()

    fake_llm = FakeChatModel("resumo.")
    generate_insights(MONTH_REF, db_path, chat_model=fake_llm)

    assert "Reembolsos de despesas compartilhadas" not in fake_llm.calls[0]


# --- User Story 2: comparison with the previous month -----------------------------------


def test_insights_includes_previous_month_comparison(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    seed_categorized_transaction(
        conn,
        "hash-3",
        "Mercado A",
        category="Alimentação",
        confidence="high",
        amount=100.0,
        transaction_date=date(2026, 8, 10),
    )
    seed_categorized_transaction(
        conn,
        "hash-4",
        "Mercado A",
        category="Alimentação",
        confidence="high",
        amount=50.0,
        transaction_date=date(2026, 7, 10),
    )
    conn.close()

    fake_llm = FakeChatModel("Você gastou mais com Alimentação do que no mês passado.")
    generate_insights(MONTH_REF, db_path, chat_model=fake_llm)

    prompt = fake_llm.calls[0]
    assert PREVIOUS_MONTH_REF in prompt
    assert "50.00" in prompt


def test_insights_first_month_no_comparison(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    seed_categorized_transaction(
        conn, "hash-5", "Mercado A", category="Alimentação", confidence="high", amount=100.0
    )
    conn.close()

    fake_llm = FakeChatModel("Resumo do primeiro mês.")
    result = generate_insights(MONTH_REF, db_path, chat_model=fake_llm)

    assert result.summary == "Resumo do primeiro mês."
    assert PREVIOUS_MONTH_REF not in fake_llm.calls[0]


# --- User Story 3: LLM failure never blocks processing -----------------------------------


def test_insights_llm_failure_returns_error_not_raise(tmp_path):
    db_path = str(tmp_path / "test.db")
    repository.connect(db_path).close()

    raising_llm = RaisingChatModel(ConnectionError("Ollama unreachable"))
    result = generate_insights(MONTH_REF, db_path, chat_model=raising_llm)

    assert result.summary is None
    assert "Ollama unreachable" in result.error


def test_insights_blank_response_treated_as_failure(tmp_path):
    db_path = str(tmp_path / "test.db")
    repository.connect(db_path).close()

    fake_llm = FakeChatModel("   ")
    result = generate_insights(MONTH_REF, db_path, chat_model=fake_llm)

    assert result.summary is None
    assert result.error is not None


# --- Smoke test: budget_check's output correctly feeds generate_insights ----------------


def _write_budget(tmp_path, goals: dict) -> str:
    import yaml

    path = tmp_path / "budget.local.yaml"
    path.write_text(yaml.dump(goals), encoding="utf-8")
    return str(path)


def test_budget_report_feeds_insights_context(tmp_path):
    """The exact dict shape graph.py builds from check_budget()'s output must be
    usable by generate_insights() unmodified — this is the real connection point
    between the two nodes, tested without any LangGraph machinery involved."""
    db_path = str(tmp_path / "test.db")
    budget_path = _write_budget(tmp_path, {"Transporte": 100.0})

    conn = repository.connect(db_path)
    seed_categorized_transaction(
        conn, "hash-6", "Uber", category="Transporte", confidence="high", amount=250.0
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

    fake_llm = FakeChatModel("Transporte estourou.")
    result = generate_insights(MONTH_REF, db_path, budget_report=budget_report, chat_model=fake_llm)

    assert result.summary == "Transporte estourou."
    prompt = fake_llm.calls[0]
    assert "250.00" in prompt
    assert "ACIMA do orçamento" in prompt
