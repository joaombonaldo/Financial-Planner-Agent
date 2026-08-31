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
    "Taxonomia disponível (categoria: subcategorias):\n{taxonomy}\n"
    "Se a categoria escolhida tiver subcategorias listadas, você DEVE escolher uma delas — não deixe a "
    "subcategoria vazia nesse caso. Subcategoria vazia só é aceitável para categorias sem nenhuma "
    "subcategoria listada.\n"
    "Orientações específicas:\n"
    '- Compras/aplicações de investimento como "CDB", "Aplicação", "Cdb Pos Di", "RDB", "Tesouro" → '
    "Investimento.\n"
    '- Pagamento de fatura de cartão de crédito saindo da conta corrente como "Pagamento efetuado", '
    '"Pagamento Fatura", "PAGAMENTO DE FATURA" → Cartão de crédito/Parcelamentos.\n'
    'Responda apenas no formato "categoria|subcategoria" (subcategoria vazia apenas se a categoria não '
    "tiver nenhuma)."
)


def _describe_taxonomy(taxonomy: Taxonomy) -> str:
    lines = []
    for category in taxonomy.category_names():
        subcategories = taxonomy.subcategories_for(category)
        suffix = ", ".join(subcategories) if subcategories else "(sem subcategorias)"
        lines.append(f"- {category}: {suffix}")
    return "\n".join(lines)


class ChatModel(Protocol):
    def invoke(self, prompt: str): ...


def categorize_via_llm(
    description_raw: str, taxonomy: Taxonomy, chat_model: ChatModel | None = None
) -> tuple[str, str | None, Literal["medium", "low"]]:
    model = chat_model or get_chat_model()
    prompt = _PROMPT_TEMPLATE.format(description=description_raw, taxonomy=_describe_taxonomy(taxonomy))
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
