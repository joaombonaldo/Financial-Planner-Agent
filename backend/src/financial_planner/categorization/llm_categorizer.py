"""Categorização via LLM para merchants sem match em memória (contracts/llm-categorizer.md).

Único módulo desta feature que efetivamente invoca llm/client.py. Nunca retorna
confidence="high" (reservado a matches de merchant memory) e sempre retorna uma
categoria válida da taxonomia — aplica o fallback "Outros"/"low" internamente quando a
resposta do LLM não corresponde a nenhuma categoria conhecida.
"""

from typing import Literal, Protocol

from financial_planner.categorization.taxonomy import FALLBACK_CATEGORY, Taxonomy
from financial_planner.llm.client import get_chat_model

_PROMPT_TEMPLATE = (
    "Categorize a transação abaixo em uma categoria e subcategoria da taxonomia disponível.\n"
    "Descrição: {description}\n"
    "Categorias disponíveis: {categories}\n"
    'Responda apenas no formato "categoria|subcategoria" (subcategoria vazia se não houver).'
)


class ChatModel(Protocol):
    def invoke(self, prompt: str): ...


def categorize_via_llm(
    description_raw: str, taxonomy: Taxonomy, chat_model: ChatModel | None = None
) -> tuple[str, str | None, Literal["medium", "low"]]:
    model = chat_model or get_chat_model()
    prompt = _PROMPT_TEMPLATE.format(
        description=description_raw, categories=", ".join(taxonomy.category_names())
    )
    response = model.invoke(prompt)
    raw = response.content.strip()

    if "|" in raw:
        category, _, subcategory_raw = raw.partition("|")
        category = category.strip()
        subcategory = subcategory_raw.strip() or None
    else:
        category, subcategory = raw, None

    if not taxonomy.is_valid(category, subcategory):
        return FALLBACK_CATEGORY, None, "low"

    return category, subcategory, "medium"
