"""Helpers para montar transações sintéticas e popular o banco de teste."""

import sqlite3
from datetime import date

from financial_planner.db import repository
from financial_planner.state import Bank, Transaction, TransactionType


def make_transaction(
    dedup_hash: str,
    description_raw: str,
    amount: float = 100.0,
    account: Bank = Bank.INTER,
    tx_type: TransactionType = TransactionType.EXPENSE,
    transaction_date: date = date(2026, 8, 20),
) -> Transaction:
    return Transaction(
        dedup_hash=dedup_hash,
        date=transaction_date,
        description_raw=description_raw,
        account=account,
        type=tx_type,
        amount=amount,
        month_ref=f"{transaction_date.year:04d}-{transaction_date.month:02d}",
    )


def seed_transaction(conn: sqlite3.Connection, transaction: Transaction) -> None:
    repository.insert_transaction(conn, transaction)


def seed_merchant_memory(
    conn: sqlite3.Connection, merchant_key: str, category: str, subcategory: str | None
) -> None:
    conn.execute(
        "INSERT INTO merchant_memory (merchant_key, category, subcategory) VALUES (?, ?, ?)",
        (merchant_key, category, subcategory),
    )
    conn.commit()
