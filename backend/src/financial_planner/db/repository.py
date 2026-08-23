"""Único ponto de acesso ao SQLite para transações (Princípio II da constituição).

Nodes nunca importam sqlite3 diretamente — sempre via este módulo.
"""

import sqlite3
from pathlib import Path

from financial_planner.state import Transaction

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


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
