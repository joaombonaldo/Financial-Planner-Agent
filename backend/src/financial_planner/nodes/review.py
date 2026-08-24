"""Node human_review: revisão humana via interrupt(), um item por vez.

Cada invocação deste node trata no máximo um item pendente. Repetir para os próximos
itens é responsabilidade da aresta condicional em graph.py (self-loop), não de um laço
interno chamando interrupt() para itens diferentes.

Por quê: a lista de pendências (list_pending_review) muda a cada item persistido, e o
replay de interrupt() do LangGraph casa respostas por ordem de chamada dentro da mesma
execução do node, não pelo conteúdo perguntado. Se a lista fosse reconsultada dentro de
um laço que chama interrupt() várias vezes no mesmo node, um replay entre itens
diferentes poderia aplicar a resposta de um item ao item errado. Tratando um item por
invocação, o único laço interno que existe é o de "resposta inválida, perguntar nesse
mesmo item de novo" — que nunca muda a lista de pendências entre suas chamadas (nenhum
persist acontece até a resposta ser válida), então não sofre desse problema.
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
