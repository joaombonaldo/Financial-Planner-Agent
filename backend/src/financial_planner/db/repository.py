"""Single point of SQLite access for transactions and merchant memory (Principle II).

Nodes never import sqlite3 directly — always via this module.
"""

import sqlite3
from datetime import date as date_cls
from pathlib import Path

from financial_planner.state import Bank, Transaction, TransactionType

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"

_TRANSACTION_COLUMNS = (
    "dedup_hash, date, description_raw, account, type, amount, month_ref, "
    "category, subcategory, confidence, installment_id"
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


def insert_transaction(conn: sqlite3.Connection, transaction: Transaction) -> None:
    conn.execute(
        """
        INSERT INTO transactions
            (dedup_hash, date, description_raw, account, type, amount, month_ref)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            transaction.dedup_hash,
            transaction.date.isoformat(),
            transaction.description_raw,
            transaction.account.value,
            transaction.type.value,
            transaction.amount,
            transaction.month_ref,
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
    conn.commit()


def list_transactions_by_month(conn: sqlite3.Connection, month_ref: str) -> list[Transaction]:
    rows = conn.execute(
        f"SELECT {_TRANSACTION_COLUMNS} FROM transactions WHERE month_ref = ? ORDER BY date",
        (month_ref,),
    ).fetchall()
    return [_row_to_transaction(row) for row in rows]


def list_pending_review(conn: sqlite3.Connection, month_ref: str) -> list[Transaction]:
    """Transactions not yet decided by a human nor by confirmed memory.

    confidence != 'high' already covers transfer candidates: the categorization
    feature never assigns confidence='high' to "Transferência interna" (only
    human_review can). See research.md.
    """
    rows = conn.execute(
        f"SELECT {_TRANSACTION_COLUMNS} FROM transactions "
        "WHERE month_ref = ? AND confidence != 'high' ORDER BY date",
        (month_ref,),
    ).fetchall()
    return [_row_to_transaction(row) for row in rows]
