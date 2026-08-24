"""LLM-based categorization for merchants with no memory match (contracts/llm-categorizer.md).

The only module in this feature that actually invokes llm/client.py. Never returns
confidence="high" (reserved for merchant-memory matches) and always returns a valid
taxonomy category — applies the "Outros"/"low" fallback internally when the LLM's
response doesn't match any known category.

The prompt template stays in Portuguese on purpose: it must keep working with the
Portuguese taxonomy and with real (Portuguese) transaction descriptions.
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
