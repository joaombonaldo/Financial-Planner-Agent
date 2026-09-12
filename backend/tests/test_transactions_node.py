import pytest

from financial_planner.db import repository
from financial_planner.nodes import transactions
from financial_planner.state import Instrument, TransactionNotFoundError
from tests.fixtures.categorization.builders import make_transaction, seed_transaction
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


def _memory_count(db_path: str) -> int:
    conn = repository.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM merchant_memory").fetchone()[0]
    conn.close()
    return count


# --- recategorize -------------------------------------------------------------------------


def test_recategorize_sets_high_confidence_and_new_category(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    seed_categorized_transaction(
        conn, "hash-1", "Loja XYZ", category="Outros", confidence="low"
    )
    conn.close()

    result = transactions.recategorize("hash-1", "Vestuário", "Roupas", db_path)

    assert result.category == "Vestuário"
    assert result.subcategory == "Roupas"
    assert result.confidence == "high"


def test_recategorize_updates_merchant_memory(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    seed_categorized_transaction(
        conn, "hash-2", "Uber Uber *trip", category="Outros", confidence="low"
    )
    conn.close()

    transactions.recategorize("hash-2", "Transporte", "Uber/99", db_path)

    assert _memory_entry(db_path, "uber uber *trip") == ("Transporte", "Uber/99")


def test_recategorize_on_already_deleted_transaction_still_works(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    seed_categorized_transaction(
        conn, "hash-3", "Loja ABC", category="Outros", confidence="low"
    )
    conn.close()

    deleted = transactions.soft_delete("hash-3", db_path)
    assert deleted.deleted_at is not None

    result = transactions.recategorize("hash-3", "Vestuário", None, db_path)

    assert result.category == "Vestuário"
    assert result.confidence == "high"
    assert result.deleted_at is not None


def test_recategorize_raises_for_unknown_hash(tmp_path):
    db_path = str(tmp_path / "test.db")
    repository.connect(db_path).close()

    with pytest.raises(TransactionNotFoundError):
        transactions.recategorize("missing-hash", "Outros", None, db_path)


# --- soft_delete ---------------------------------------------------------------------------


def test_soft_delete_excludes_from_month_listing(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    txn = make_transaction("hash-4", "Loja DEF")
    seed_transaction(conn, txn)
    conn.close()

    transactions.soft_delete("hash-4", db_path)

    conn = repository.connect(db_path)
    active = repository.list_transactions_by_month(conn, MONTH_REF, instrument=Instrument.DEBIT)
    conn.close()
    assert all(t.dedup_hash != "hash-4" for t in active)


def test_soft_delete_does_not_touch_merchant_memory(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    txn = make_transaction("hash-5", "Loja GHI")
    seed_transaction(conn, txn)
    conn.close()

    transactions.soft_delete("hash-5", db_path)

    assert _memory_count(db_path) == 0


def test_soft_delete_raises_for_unknown_hash(tmp_path):
    db_path = str(tmp_path / "test.db")
    repository.connect(db_path).close()

    with pytest.raises(TransactionNotFoundError):
        transactions.soft_delete("missing-hash", db_path)


# --- restore ---------------------------------------------------------------------------------


def test_restore_brings_transaction_back(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    txn = make_transaction("hash-6", "Loja JKL")
    seed_transaction(conn, txn)
    conn.close()

    transactions.soft_delete("hash-6", db_path)
    restored = transactions.restore("hash-6", db_path)

    assert restored.deleted_at is None

    conn = repository.connect(db_path)
    active = repository.list_transactions_by_month(conn, MONTH_REF, instrument=Instrument.DEBIT)
    conn.close()
    assert any(t.dedup_hash == "hash-6" for t in active)


def test_restore_raises_for_unknown_hash(tmp_path):
    db_path = str(tmp_path / "test.db")
    repository.connect(db_path).close()

    with pytest.raises(TransactionNotFoundError):
        transactions.restore("missing-hash", db_path)
