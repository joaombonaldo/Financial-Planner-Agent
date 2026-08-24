"""Node categorize: orchestrates transfer detection + merchant memory + LLM.

Evaluation order (see research.md): transfer -> memory -> LLM. Doesn't access sqlite3
nor init_chat_model directly — delegates to db/repository.py and categorization/*.py
(Principle II).
"""

from financial_planner.categorization import merchant_memory
from financial_planner.categorization.llm_categorizer import ChatModel, categorize_via_llm
from financial_planner.categorization.taxonomy import TRANSFER_CATEGORY, load_taxonomy
from financial_planner.categorization.transfer_detection import is_transfer_candidate
from financial_planner.db import repository


def categorize(month_ref: str, db_path: str, chat_model: ChatModel | None = None) -> None:
    conn = repository.connect(db_path)
    try:
        taxonomy = load_taxonomy()
        transactions = repository.list_transactions_by_month(conn, month_ref)

        for transaction in transactions:
            if is_transfer_candidate(transaction, transactions):
                repository.update_transaction_category(
                    conn, transaction.dedup_hash, TRANSFER_CATEGORY, None, "medium"
                )
                continue

            match = merchant_memory.lookup(conn, transaction.description_raw)
            if match is not None:
                category, subcategory = match
                repository.update_transaction_category(
                    conn, transaction.dedup_hash, category, subcategory, "high"
                )
                continue

            category, subcategory, confidence = categorize_via_llm(
                transaction.description_raw, taxonomy, chat_model
            )
            repository.update_transaction_category(
                conn, transaction.dedup_hash, category, subcategory, confidence
            )
    finally:
        conn.close()
