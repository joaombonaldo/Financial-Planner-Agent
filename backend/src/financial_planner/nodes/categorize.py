"""Node categorize: orchestrates transfer detection + merchant memory + LLM.

Evaluation order (see research.md): transfer -> memory -> LLM. Doesn't access sqlite3
nor init_chat_model directly — delegates to db/repository.py and categorization/*.py
(Principle II).

Feature 014: credit-card purchases (instrument=credit, feature 013) are categorized
too — any category can occur on either instrument (see BRD §5.3.1) — but never run
through transfer detection: an internal transfer is a movement between the user's
own debit/PIX accounts, which a card purchase can never be.

Idempotency (found 2026-09-12 running a real month): `run_month()` always calls
`graph.invoke()` with a fresh input, even to resume a thread that already has
pending human_review items — LangGraph re-executes every node from
`detect_and_parse` on each such call, not just the ones after the last confirmed
checkpoint. `detect_and_parse` is already idempotent via dedup_hash, but this node
was not: it re-ran transfer detection + memory/LLM categorization on every
transaction in the month on every single invocation, silently repeating a full
LLM pass (and potentially producing a different suggestion each time, since the
LLM isn't deterministic) for transactions that already have a category from an
earlier run — including ones already confirmed by a human. Skipping any
transaction that already has a category fixes both: restarting after an
interrupted run is near-instant, and a confirmed category never gets silently
reconsidered by a later categorize() pass.
"""

from financial_planner.categorization import merchant_memory
from financial_planner.categorization.llm_categorizer import ChatModel, categorize_via_llm
from financial_planner.categorization.taxonomy import TRANSFER_CATEGORY, Taxonomy, load_taxonomy
from financial_planner.categorization.transfer_detection import is_transfer_candidate
from financial_planner.db import repository
from financial_planner.state import Transaction


def _categorize_one(
    conn, transaction: Transaction, taxonomy: Taxonomy, chat_model: ChatModel | None
) -> None:
    match = merchant_memory.lookup(conn, transaction.description_raw)
    if match is not None:
        category, subcategory = match
        repository.update_transaction_category(
            conn, transaction.dedup_hash, category, subcategory, "high"
        )
        return

    category, subcategory, confidence = categorize_via_llm(
        transaction.description_raw, taxonomy, chat_model
    )
    repository.update_transaction_category(
        conn, transaction.dedup_hash, category, subcategory, confidence
    )


def categorize(month_ref: str, db_path: str, chat_model: ChatModel | None = None) -> None:
    conn = repository.connect(db_path)
    try:
        taxonomy = load_taxonomy()
        debit_transactions = repository.list_transactions_by_month(conn, month_ref)
        credit_transactions = repository.list_credit_transactions_by_month(conn, month_ref)

        for transaction in debit_transactions:
            if transaction.category is not None:
                continue
            if is_transfer_candidate(transaction, debit_transactions):
                repository.update_transaction_category(
                    conn, transaction.dedup_hash, TRANSFER_CATEGORY, None, "medium"
                )
                continue
            _categorize_one(conn, transaction, taxonomy, chat_model)

        for transaction in credit_transactions:
            if transaction.category is not None:
                continue
            _categorize_one(conn, transaction, taxonomy, chat_model)
    finally:
        conn.close()
