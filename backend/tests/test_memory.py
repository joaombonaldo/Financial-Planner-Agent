from datetime import date

from financial_planner.db import repository
from financial_planner.graph import build_graph
from financial_planner.nodes.memory import update_memory
from financial_planner.state import Bank, Transaction, TransactionType
from tests.fixtures.review.builders import seed_categorized_transaction

MONTH_REF = "2026-08"


def _memory_entry(db_path: str, merchant_key: str) -> tuple | None:
    conn = repository.connect(db_path)
    row = conn.execute(
        "SELECT category, subcategory FROM merchant_memory WHERE merchant_key = ?",
        (merchant_key,),
    ).fetchone()
    conn.close()
    return row


# --- User Story 1: remember confirmed categorizations -----------------------------------


def test_memory_remembers_confirmed_categorization(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    seed_categorized_transaction(
        conn, "hash-1", "Uber Uber *trip", category="Transporte", subcategory="Uber/99", confidence="high"
    )
    conn.close()

    update_memory(MONTH_REF, db_path)

    assert _memory_entry(db_path, "uber uber *trip") == ("Transporte", "Uber/99")


def test_memory_overwrites_stale_mapping_with_newest(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    seed_categorized_transaction(
        conn, "hash-2", "Loja XYZ", category="Outros", confidence="high"
    )
    conn.close()
    update_memory(MONTH_REF, db_path)
    assert _memory_entry(db_path, "loja xyz") == ("Outros", None)

    conn = repository.connect(db_path)
    seed_categorized_transaction(
        conn,
        "hash-3",
        "Loja XYZ",
        category="Vestuário",
        subcategory="Roupas",
        confidence="high",
        transaction_date=date(2026, 8, 21),
    )
    conn.close()
    update_memory(MONTH_REF, db_path)

    assert _memory_entry(db_path, "loja xyz") == ("Vestuário", "Roupas")


def test_memory_empty_month_is_noop(tmp_path):
    db_path = str(tmp_path / "test.db")
    repository.connect(db_path).close()

    update_memory(MONTH_REF, db_path)

    conn = repository.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM merchant_memory").fetchone()[0]
    conn.close()
    assert count == 0


# --- User Story 2: never remember a transfer ---------------------------------------------


def test_memory_never_writes_transfer_category(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    seed_categorized_transaction(
        conn, "hash-4", "PIX ENVIADO", category="Transferência interna", confidence="high"
    )
    conn.close()

    update_memory(MONTH_REF, db_path)

    assert _memory_entry(db_path, "pix enviado") is None


# --- Full-chain smoke test (no LLM involved) ---------------------------------------------


def test_full_chain_remembers_merchant_across_months(tmp_path):
    """A merchant confirmed one month auto-categorizes with high confidence the next,
    entirely through merchant memory — no LLM call anywhere in this test."""
    db_path = str(tmp_path / "test.db")

    conn = repository.connect(db_path)
    repository.upsert_merchant_category(conn, "uber uber *trip", "Transporte", "Uber/99")
    # A fresh, uncategorized transaction — as if it just came out of ingest.
    repository.insert_transaction(
        conn,
        Transaction(
            dedup_hash="hash-next-month",
            date=date(2026, 9, 5),
            description_raw="Uber Uber *trip",
            account=Bank.INTER,
            type=TransactionType.EXPENSE,
            amount=30.0,
            month_ref="2026-09",
        ),
    )
    conn.close()

    graph = build_graph(db_path)
    result = graph.invoke(
        {"source_files": [], "month_ref": "2026-09", "db_path": db_path},
        config={"configurable": {"thread_id": "2026-09"}},
    )

    assert not result.get("__interrupt__")

    conn = repository.connect(db_path)
    row = conn.execute(
        "SELECT category, subcategory, confidence FROM transactions WHERE dedup_hash = ?",
        ("hash-next-month",),
    ).fetchone()
    conn.close()

    assert row == ("Transporte", "Uber/99", "high")
