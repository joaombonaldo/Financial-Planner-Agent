from datetime import date

from financial_planner.db import repository
from financial_planner.nodes.categorize import categorize
from financial_planner.state import Bank, TransactionType
from tests.fixtures.categorization.builders import make_transaction, seed_merchant_memory, seed_transaction
from tests.fixtures.categorization.llm_double import FakeChatModel

MONTH_REF = "2026-08"


def _category_row(db_path: str, dedup_hash: str) -> tuple:
    conn = repository.connect(db_path)
    row = conn.execute(
        "SELECT category, subcategory, confidence FROM transactions WHERE dedup_hash = ?",
        (dedup_hash,),
    ).fetchone()
    conn.close()
    return row


# --- User Story 1: categorize already-known merchants -----------------------------------


def test_categorize_known_merchant(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)

    transaction = make_transaction("hash-1", "Uber Uber *trip", amount=25.0)
    seed_transaction(conn, transaction)
    seed_merchant_memory(conn, "uber uber *trip", "Transporte", "Uber/99")
    conn.close()

    categorize(MONTH_REF, db_path)

    assert _category_row(db_path, "hash-1") == ("Transporte", "Uber/99", "high")


def test_empty_merchant_memory_never_high(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    seed_transaction(conn, make_transaction("hash-2", "Loja Desconhecida"))
    conn.close()

    fake_llm = FakeChatModel("Alimentação|Mercado")
    categorize(MONTH_REF, db_path, chat_model=fake_llm)

    assert _category_row(db_path, "hash-2")[2] != "high"


# --- User Story 2: categorize via LLM, with fallback -------------------------------------


def test_categorize_new_merchant_via_llm(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    seed_transaction(conn, make_transaction("hash-3", "Supermercado XYZ"))
    conn.close()

    fake_llm = FakeChatModel("Alimentação|Mercado")
    categorize(MONTH_REF, db_path, chat_model=fake_llm)

    category, subcategory, confidence = _category_row(db_path, "hash-3")
    assert category == "Alimentação"
    assert subcategory == "Mercado"
    assert confidence in ("medium", "low")
    assert confidence != "high"
    assert len(fake_llm.calls) == 1


def test_llm_response_outside_taxonomy_falls_back(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    seed_transaction(conn, make_transaction("hash-4", "Estabelecimento Estranho"))
    conn.close()

    fake_llm = FakeChatModel("Categoria Inventada Pelo LLM|Subcategoria Qualquer")
    categorize(MONTH_REF, db_path, chat_model=fake_llm)

    assert _category_row(db_path, "hash-4") == ("Outros", None, "low")


def test_llm_prompt_lists_subcategories_and_requires_them_when_available(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    seed_transaction(conn, make_transaction("hash-prompt", "Aluguel Imobiliaria"))
    conn.close()

    fake_llm = FakeChatModel("Moradia|Aluguel/Financiamento")
    categorize(MONTH_REF, db_path, chat_model=fake_llm)

    prompt = fake_llm.calls[0]
    assert "Moradia: Aluguel/Financiamento, Condomínio" in prompt
    assert "Outros: (sem subcategorias)" in prompt
    assert "DEVE escolher uma delas" in prompt


def test_llm_empty_subcategory_for_category_with_options_is_not_invalid(tmp_path):
    """FR-004 (spec 008): a category with subcategories, but an empty subcategory answer from the
    LLM, must NOT fall back to Outros/low — it should keep the chosen category (with empty
    subcategory) so it still reaches human_review, same as any other LLM-sourced categorization.
    """
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    seed_transaction(conn, make_transaction("hash-5", "Aluguel Imobiliaria"))
    conn.close()

    fake_llm = FakeChatModel("Moradia|")
    categorize(MONTH_REF, db_path, chat_model=fake_llm)

    category, subcategory, confidence = _category_row(db_path, "hash-5")
    assert category == "Moradia"
    assert subcategory is None
    assert confidence in ("medium", "low")


# --- User Story 3: flag transfer candidates -----------------------------------------------


def test_transfer_pair_detected(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)

    seed_transaction(
        conn,
        make_transaction(
            "hash-out",
            "PIX ENVIADO",
            amount=500.0,
            account=Bank.INTER,
            tx_type=TransactionType.EXPENSE,
            transaction_date=date(2026, 8, 10),
        ),
    )
    seed_transaction(
        conn,
        make_transaction(
            "hash-in",
            "PIX RECEBIDO",
            amount=500.0,
            account=Bank.BRADESCO,
            tx_type=TransactionType.INCOME,
            transaction_date=date(2026, 8, 11),
        ),
    )
    conn.close()

    fake_llm = FakeChatModel("Outros|")
    categorize(MONTH_REF, db_path, chat_model=fake_llm)

    assert _category_row(db_path, "hash-out") == ("Transferência interna", None, "medium")
    assert _category_row(db_path, "hash-in") == ("Transferência interna", None, "medium")
    # Neither was removed from the total — both stay in the transactions table.
    conn = repository.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    conn.close()
    assert count == 2
    assert fake_llm.calls == []


def test_transfer_pattern_without_mirror_falls_through(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    seed_transaction(
        conn,
        make_transaction(
            "hash-lonely-pix",
            "PIX ENVIADO",
            amount=500.0,
            account=Bank.INTER,
            tx_type=TransactionType.EXPENSE,
            transaction_date=date(2026, 8, 10),
        ),
    )
    conn.close()

    fake_llm = FakeChatModel("Outros|")
    categorize(MONTH_REF, db_path, chat_model=fake_llm)

    category, _subcategory, confidence = _category_row(db_path, "hash-lonely-pix")
    assert category != "Transferência interna"
    assert confidence != "high"
