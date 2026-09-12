"""Feature 015: soft-delete behavior in db/repository.py.

No node owns this yet (that's nodes/transactions.py, built separately) — these
tests exercise the repository contract directly, the same way it'll be used.
"""

from financial_planner.db import repository
from tests.fixtures.categorization.builders import make_transaction, seed_transaction

MONTH_REF = "2026-08"


def test_soft_deleted_transaction_excluded_from_month_listing(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    seed_transaction(conn, make_transaction("hash-1", "Mercado A", amount=50.0))

    repository.soft_delete_transaction(conn, "hash-1")

    assert repository.list_transactions_by_month(conn, MONTH_REF) == []
    assert (
        len(repository.list_transactions_by_month(conn, MONTH_REF, include_deleted=True)) == 1
    )
    conn.close()


def test_soft_deleted_transaction_excluded_from_pending_review(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    seed_transaction(conn, make_transaction("hash-1", "Mercado A", amount=50.0))

    repository.soft_delete_transaction(conn, "hash-1")

    assert repository.list_pending_review(conn, MONTH_REF) == []
    conn.close()


def test_restore_brings_a_soft_deleted_transaction_back(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    seed_transaction(conn, make_transaction("hash-1", "Mercado A", amount=50.0))
    repository.soft_delete_transaction(conn, "hash-1")

    repository.restore_transaction(conn, "hash-1")

    result = repository.list_transactions_by_month(conn, MONTH_REF)
    assert len(result) == 1
    assert result[0].deleted_at is None
    conn.close()


def test_soft_delete_sets_deleted_at_timestamp(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    seed_transaction(conn, make_transaction("hash-1", "Mercado A", amount=50.0))

    repository.soft_delete_transaction(conn, "hash-1")

    row = repository.list_transactions_by_month(conn, MONTH_REF, include_deleted=True)[0]
    assert row.deleted_at is not None
    conn.close()


def test_soft_delete_does_not_break_reimport_dedup(tmp_path):
    """The whole point of soft-delete over a real DELETE: transaction_exists must
    still see a soft-deleted row, so re-ingesting the same statement file never
    resurrects it."""
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    seed_transaction(conn, make_transaction("hash-1", "Mercado A", amount=50.0))
    repository.soft_delete_transaction(conn, "hash-1")

    assert repository.transaction_exists(conn, "hash-1") is True
    conn.close()
