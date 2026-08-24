"""Node human_review: human review via interrupt(), one item at a time.

Each invocation of this node handles at most one pending item. Repeating for the next
items is the responsibility of the conditional edge in graph.py (self-loop), not of an
internal loop calling interrupt() for different items.

Why: the pending list (list_pending_review) changes with every item persisted, and
LangGraph's interrupt() replay matches responses by call order within the same node
run, not by the content asked. If the list were re-queried inside a loop that calls
interrupt() multiple times in the same node, a replay across different items could
apply one item's answer to the wrong item. By handling one item per invocation, the
only internal loop that exists is "invalid response, ask about the same item again" —
which never changes the pending list between its calls (no persist happens until the
response is valid), so it doesn't suffer from that problem.

Response keywords ("aceitar", "confirmar") and error messages shown to the user stay
in Portuguese, same as the CLI — the app's actual runtime language.
"""

from langgraph.types import interrupt

from financial_planner.categorization.taxonomy import TRANSFER_CATEGORY, Taxonomy, load_taxonomy
from financial_planner.db import repository
from financial_planner.state import Transaction


def _build_payload(transaction: Transaction, error: str | None = None) -> dict:
    payload = {
        "transaction": {
            "date": transaction.date.isoformat(),
            "description_raw": transaction.description_raw,
            "amount": transaction.amount,
            "account": transaction.account.value,
            "category": transaction.category,
            "subcategory": transaction.subcategory,
            "confidence": transaction.confidence,
        },
        "is_transfer_candidate": transaction.category == TRANSFER_CATEGORY,
    }
    if error:
        payload["error"] = error
    return payload


def _parse_answer(
    answer: str, transaction: Transaction, is_transfer: bool, taxonomy: Taxonomy
) -> tuple[str, str | None] | None:
    answer = (answer or "").strip()
    lowered = answer.lower()

    if not is_transfer and lowered == "aceitar":
        return transaction.category, transaction.subcategory
    if is_transfer and lowered == "confirmar":
        return TRANSFER_CATEGORY, None

    if "|" in answer:
        category, _, subcategory_raw = answer.partition("|")
        category = category.strip()
        subcategory = subcategory_raw.strip() or None
    else:
        category, subcategory = answer, None

    if not category or not taxonomy.is_valid(category, subcategory):
        return None

    return category, subcategory


def review(month_ref: str, db_path: str) -> None:
    conn = repository.connect(db_path)
    try:
        pending = repository.list_pending_review(conn, month_ref)
        if not pending:
            return

        transaction = pending[0]
        is_transfer = transaction.category == TRANSFER_CATEGORY
        taxonomy = load_taxonomy()

        payload = _build_payload(transaction)
        while True:
            answer = interrupt(payload)
            result = _parse_answer(answer, transaction, is_transfer, taxonomy)

            if result is None:
                payload = _build_payload(transaction, error=f"Resposta inválida: {answer!r}")
                continue

            category, subcategory = result
            repository.update_transaction_category(
                conn, transaction.dedup_hash, category, subcategory, "high"
            )
            return
    finally:
        conn.close()
