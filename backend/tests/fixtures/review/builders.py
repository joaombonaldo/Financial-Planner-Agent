"""Helpers para popular o banco com transações já categorizadas, prontas pra revisão."""

import sqlite3
from datetime import date

from financial_planner.db import repository
from financial_planner.state import Bank, Transaction, TransactionType


def seed_categorized_transaction(
    conn: sqlite3.Connection,
    dedup_hash: str,
    description_raw: str,
    category: str,
    confidence: str,
    subcategory: str | None = None,
    amount: float = 100.0,
    account: Bank = Bank.INTER,
    tx_type: TransactionType = TransactionType.EXPENSE,
    transaction_date: date = date(2026, 8, 20),
) -> Transaction:
    transaction = Transaction(
        dedup_hash=dedup_hash,
        date=transaction_date,
        description_raw=description_raw,
        account=account,
        type=tx_type,
        amount=amount,
        month_ref=f"{transaction_date.year:04d}-{transaction_date.month:02d}",
    )
    repository.insert_transaction(conn, transaction)
    repository.update_transaction_category(conn, dedup_hash, category, subcategory, confidence)
    return transaction
