"""Single point of SQLite access for transactions and merchant memory (Principle II).

Nodes never import sqlite3 directly — always via this module.
"""

import sqlite3
from datetime import date as date_cls
from datetime import datetime
from pathlib import Path

from financial_planner.categorization.taxonomy import CREDIT_CARD_CATEGORY
from financial_planner.state import Bank, Instrument, Transaction, TransactionType

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"

_TRANSACTION_COLUMNS = (
    "dedup_hash, date, description_raw, account, type, amount, month_ref, "
    "category, subcategory, confidence, installment_id, instrument, fatura_ref, "
    "deleted_at"
)


def _row_to_transaction(row: tuple) -> Transaction:
    (
        dedup_hash,
        date_str,
        description_raw,
        account,
        tx_type,
        amount,
        month_ref,
        category,
        subcategory,
        confidence,
        installment_id,
        instrument,
        fatura_ref,
        deleted_at,
    ) = row
    return Transaction(
        dedup_hash=dedup_hash,
        date=date_cls.fromisoformat(date_str),
        description_raw=description_raw,
        account=Bank(account),
        type=TransactionType(tx_type),
        amount=amount,
        month_ref=month_ref,
        category=category,
        subcategory=subcategory,
        confidence=confidence,
        installment_id=installment_id,
        instrument=Instrument(instrument or Instrument.DEBIT.value),
        fatura_ref=fatura_ref,
        deleted_at=deleted_at,
    )


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.executescript(_SCHEMA_PATH.read_text())
    return conn


def transaction_exists(conn: sqlite3.Connection, dedup_hash: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM transactions WHERE dedup_hash = ?", (dedup_hash,)
    ).fetchone()
    return row is not None


def get_transaction(conn: sqlite3.Connection, dedup_hash: str) -> Transaction | None:
    """A single transaction by its dedup_hash, regardless of deleted_at — callers
    that need to look one up (e.g. a manual edit, which only receives a
    dedup_hash from the client) need to see it whether active or already
    soft-deleted. Returns None if no such transaction exists at all."""
    row = conn.execute(
        f"SELECT {_TRANSACTION_COLUMNS} FROM transactions WHERE dedup_hash = ?",
        (dedup_hash,),
    ).fetchone()
    return _row_to_transaction(row) if row else None


def insert_transaction(conn: sqlite3.Connection, transaction: Transaction) -> None:
    conn.execute(
        """
        INSERT INTO transactions
            (dedup_hash, date, description_raw, account, type, amount, month_ref,
             instrument, fatura_ref)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            transaction.dedup_hash,
            transaction.date.isoformat(),
            transaction.description_raw,
            transaction.account.value,
            transaction.type.value,
            transaction.amount,
            transaction.month_ref,
            transaction.instrument.value,
            transaction.fatura_ref,
        ),
    )
    conn.commit()


def get_merchant_category(
    conn: sqlite3.Connection, merchant_key: str
) -> tuple[str, str | None] | None:
    row = conn.execute(
        "SELECT category, subcategory FROM merchant_memory WHERE merchant_key = ?",
        (merchant_key,),
    ).fetchone()
    return (row[0], row[1]) if row else None


def update_transaction_category(
    conn: sqlite3.Connection,
    dedup_hash: str,
    category: str,
    subcategory: str | None,
    confidence: str,
) -> None:
    conn.execute(
        """
        UPDATE transactions
        SET category = ?, subcategory = ?, confidence = ?
        WHERE dedup_hash = ?
        """,
        (category, subcategory, confidence, dedup_hash),
    )
    # Feature 014: confirming a debit transaction as the credit-card-bill category
    # links it to its fatura — fatura_ref becomes the month this payment line itself
    # lands in, which is the same value the fatura's credit-card purchases already
    # carry (see parsers/credit_card_common.py), so the two sides join on fatura_ref.
    # Credit-stream rows never hit this branch (their fatura_ref is set at parse
    # time and must not be overwritten here).
    if category == CREDIT_CARD_CATEGORY:
        conn.execute(
            "UPDATE transactions SET fatura_ref = month_ref "
            "WHERE dedup_hash = ? AND instrument = ?",
            (dedup_hash, Instrument.DEBIT.value),
        )
    conn.commit()


def list_transactions_by_month(
    conn: sqlite3.Connection,
    month_ref: str,
    instrument: Instrument | None = Instrument.DEBIT,
    include_deleted: bool = False,
) -> list[Transaction]:
    """Transactions for a month.

    Defaults to the debit/PIX stream only (``instrument=Instrument.DEBIT``) so the
    existing report / budget / insights / categorize nodes keep seeing exactly what
    they saw before feature 013 — credit-card fatura purchases are a separate stream
    (see docs/decisions/credit-card-stream.md) and must not leak into the headline
    debit totals. Pass ``instrument=None`` to get every stream, or
    ``Instrument.CREDIT`` for the credit stream.

    Feature 015: soft-deleted rows (``deleted_at`` set) are excluded by default —
    "not mine" transactions must be invisible to categorize/review/memory/budget/
    insights/report, the same way credit rows are invisible to the debit-only
    default. Pass ``include_deleted=True`` only for a UI that needs to show/restore
    them (see specs/015-fastapi-core-api).
    """
    clauses = ["month_ref = ?"]
    params: list = [month_ref]
    if instrument is not None:
        clauses.append("instrument = ?")
        params.append(instrument.value)
    if not include_deleted:
        clauses.append("deleted_at IS NULL")
    rows = conn.execute(
        f"SELECT {_TRANSACTION_COLUMNS} FROM transactions "
        f"WHERE {' AND '.join(clauses)} ORDER BY date",
        params,
    ).fetchall()
    return [_row_to_transaction(row) for row in rows]


def list_credit_transactions_by_month(
    conn: sqlite3.Connection, month_ref: str, include_deleted: bool = False
) -> list[Transaction]:
    """Credit-card purchases grouped by the month they were *made* (purchase date)."""
    return list_transactions_by_month(
        conn, month_ref, instrument=Instrument.CREDIT, include_deleted=include_deleted
    )


def list_credit_transactions_by_fatura_ref(
    conn: sqlite3.Connection, fatura_ref: str
) -> list[Transaction]:
    """Every credit-card purchase that belongs to a given fatura (YYYY-MM of its due
    date). Used to reconcile the fatura total against the debit payment line.
    Deleted rows are excluded — a soft-deleted purchase shouldn't count toward
    reconciliation."""
    rows = conn.execute(
        f"SELECT {_TRANSACTION_COLUMNS} FROM transactions "
        "WHERE fatura_ref = ? AND instrument = ? AND deleted_at IS NULL ORDER BY date",
        (fatura_ref, Instrument.CREDIT.value),
    ).fetchall()
    return [_row_to_transaction(row) for row in rows]


def upsert_merchant_category(
    conn: sqlite3.Connection,
    merchant_key: str,
    category: str,
    subcategory: str | None,
) -> None:
    """Insert or overwrite a merchant's confirmed category mapping.

    Idempotent by construction (ON CONFLICT), not by any application-level dedup
    logic — see specs/004-update-memory/research.md.
    """
    conn.execute(
        """
        INSERT INTO merchant_memory (merchant_key, category, subcategory)
        VALUES (?, ?, ?)
        ON CONFLICT(merchant_key) DO UPDATE SET
            category = excluded.category,
            subcategory = excluded.subcategory
        """,
        (merchant_key, category, subcategory),
    )
    conn.commit()


def list_month_refs(conn: sqlite3.Connection) -> list[str]:
    """Every distinct month_ref with at least one non-deleted transaction, newest
    first. Backs the month-history list (nodes/queries.py)."""
    rows = conn.execute(
        "SELECT DISTINCT month_ref FROM transactions "
        "WHERE deleted_at IS NULL ORDER BY month_ref DESC"
    ).fetchall()
    return [row[0] for row in rows]


def list_pending_review(conn: sqlite3.Connection, month_ref: str) -> list[Transaction]:
    """Transactions not yet decided by a human nor by confirmed memory.

    confidence != 'high' already covers transfer candidates: the categorization
    feature never assigns confidence='high' to "Transferência interna" (only
    human_review can). See research.md.

    Feature 015: a soft-deleted transaction is never pending review — it's been
    decided to not exist.
    """
    rows = conn.execute(
        f"SELECT {_TRANSACTION_COLUMNS} FROM transactions "
        "WHERE month_ref = ? AND confidence != 'high' AND deleted_at IS NULL "
        "ORDER BY date",
        (month_ref,),
    ).fetchall()
    return [_row_to_transaction(row) for row in rows]


def soft_delete_transaction(conn: sqlite3.Connection, dedup_hash: str) -> None:
    """Mark a transaction excluded everywhere ("not mine") without removing the
    row — re-ingest idempotency (transaction_exists/dedup_hash) depends on the
    row still being present, so a real DELETE would let the same statement file
    silently resurrect it on a future re-upload. See specs/015-fastapi-core-api.
    """
    conn.execute(
        "UPDATE transactions SET deleted_at = ? WHERE dedup_hash = ?",
        (datetime.now().isoformat(timespec="seconds"), dedup_hash),
    )
    conn.commit()


def restore_transaction(conn: sqlite3.Connection, dedup_hash: str) -> None:
    """Undo soft_delete_transaction."""
    conn.execute(
        "UPDATE transactions SET deleted_at = NULL WHERE dedup_hash = ?",
        (dedup_hash,),
    )
    conn.commit()
