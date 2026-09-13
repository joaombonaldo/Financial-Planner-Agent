"""Node transactions: manual, human-initiated edits to a single transaction.

This is the domain-logic entry point for the FastAPI interface layer's manual-edit
endpoints — interface/api.py calls into this module rather than db/repository.py
directly, the same way interface/cli.py never imports db/repository.py itself (see
specs/015-fastapi-core-api "Architecture").
"""

from financial_planner.db import repository
from financial_planner.nodes.memory import update_memory
from financial_planner.state import Transaction, TransactionNotFoundError


def recategorize(dedup_hash: str, category: str, subcategory: str | None, db_path: str) -> Transaction:
    """Behaves exactly like answering a real human_review item: sets
    confidence='high' and re-runs update_memory for the transaction's month.
    update_memory is idempotent — it re-scans the whole month but only upserts
    confidence='high' non-transfer rows, so calling it for a single correction is
    cheap and correct."""
    conn = repository.connect(db_path)
    try:
        transaction = repository.get_transaction(conn, dedup_hash)
        if transaction is None:
            raise TransactionNotFoundError(dedup_hash)

        repository.update_transaction_category(conn, dedup_hash, category, subcategory, "high")
        month_ref = transaction.month_ref
    finally:
        conn.close()

    update_memory(month_ref, db_path)

    conn = repository.connect(db_path)
    try:
        return repository.get_transaction(conn, dedup_hash)
    finally:
        conn.close()


def soft_delete(dedup_hash: str, db_path: str) -> Transaction:
    """"Not mine" — excludes the transaction everywhere. Deliberately does NOT
    touch merchant_memory (BRD decision: a "not mine" transaction is usually a
    one-off, not a recurring pattern worth learning)."""
    conn = repository.connect(db_path)
    try:
        transaction = repository.get_transaction(conn, dedup_hash)
        if transaction is None:
            raise TransactionNotFoundError(dedup_hash)

        repository.soft_delete_transaction(conn, dedup_hash)
        return repository.get_transaction(conn, dedup_hash)
    finally:
        conn.close()


def restore(dedup_hash: str, db_path: str) -> Transaction:
    """Undo soft_delete."""
    conn = repository.connect(db_path)
    try:
        transaction = repository.get_transaction(conn, dedup_hash)
        if transaction is None:
            raise TransactionNotFoundError(dedup_hash)

        repository.restore_transaction(conn, dedup_hash)
        return repository.get_transaction(conn, dedup_hash)
    finally:
        conn.close()
