"""Node update_memory: persists confirmed categorizations into merchant memory.

Only touches merchant_memory via db/repository.py — never transactions. Runs after
human_review has fully resolved a month (see graph.py), so every transaction it reads
is either confirmed by a human or already high-confidence from a prior memory match.
"""

from financial_planner.categorization.merchant_memory import normalize_merchant_key
from financial_planner.categorization.taxonomy import TRANSFER_CATEGORY
from financial_planner.db import repository


def update_memory(month_ref: str, db_path: str) -> None:
    conn = repository.connect(db_path)
    try:
        transactions = repository.list_transactions_by_month(conn, month_ref)

        for transaction in transactions:
            if transaction.confidence != "high":
                continue
            if transaction.category == TRANSFER_CATEGORY:
                continue

            merchant_key = normalize_merchant_key(transaction.description_raw)
            repository.upsert_merchant_category(
                conn, merchant_key, transaction.category, transaction.subcategory
            )
    finally:
        conn.close()
