"""Node generate_insights: LLM-generated Portuguese summary of the month's spending.

Only touches transactions via db/repository.py and the LLM via llm/client.py —
never sqlite3 or a provider SDK directly (Principle II). Deliberately never raises:
this node is marked "optional" in the BRD, so any failure (LLM unreachable, timeout,
blank response) is recorded and returned, never allowed to block the rest of the
month's processing (FR-006).
"""

from typing import Protocol

from financial_planner.budget.spending import compute_category_spend
from financial_planner.db import repository
from financial_planner.llm.client import get_chat_model
from financial_planner.nodes.report import (
    INCOME_CATEGORY,
    REIMBURSEMENT_SUBCATEGORY,
    compute_reimbursements,
)
from financial_planner.state import InsightsResult

_PROMPT_TEMPLATE = """Você é um assistente financeiro pessoal. Escreva um resumo curto, em português, sobre a
situação financeira do usuário no mês {month_ref}, com base exclusivamente nos dados abaixo. Não invente números
nem categorias que não estejam listados.

Gasto por categoria em {month_ref}:
{current_spend}

Comparação com a meta de orçamento:
{budget_report}
{reimbursement_section}{previous_month_section}
Escreva de forma direta, destacando para onde o dinheiro foi e qualquer categoria estourada."""

_PREVIOUS_MONTH_TEMPLATE = """
Gasto por categoria no mês anterior ({previous_month_ref}), para comparação:
{previous_spend}
"""

# Feature 012: shared-expense reimbursements. A `Receita / Reembolso` inflow is NOT
# income — it abates the expense category it offsets. Feed the gross/reimbursed/net
# split into the prompt so the summary can report the real (net) cost per category.
_REIMBURSEMENT_TEMPLATE = """
Reembolsos de despesas compartilhadas em {month_ref} (o reembolso NÃO é receita — ele abate a despesa):
{reimbursement_lines}
"""


class ChatModel(Protocol):
    def invoke(self, prompt: str): ...


def _previous_month_ref(month_ref: str) -> str:
    year, month = (int(part) for part in month_ref.split("-"))
    if month == 1:
        return f"{year - 1:04d}-12"
    return f"{year:04d}-{month - 1:02d}"


def _format_spend(spend: dict[str, float]) -> str:
    if not spend:
        return "(nenhum gasto registrado)"
    return "\n".join(f"- {category}: R$ {amount:.2f}" for category, amount in spend.items())


def _format_reimbursements(summary, gross_by_category: dict[str, float]) -> str:
    lines = []
    for category, reimbursed in sorted(summary.by_category.items()):
        gross = gross_by_category.get(category, 0.0)
        lines.append(
            f"- {category}: R$ {gross:.2f} bruto, R$ {reimbursed:.2f} reembolsado, "
            f"R$ {gross - reimbursed:.2f} líquido"
        )
    if summary.unattributed:
        lines.append(
            f"- Reembolsos não atribuídos a uma categoria específica: "
            f"R$ {summary.unattributed:.2f} (abatidos do total de despesas)"
        )
    return "\n".join(lines)


def _format_budget_report(budget_report: list[dict] | None) -> str:
    if not budget_report:
        return "(nenhuma meta configurada)"
    lines = []
    for entry in budget_report:
        marker = "dentro do orçamento" if entry["status"] == "within_budget" else "ACIMA do orçamento"
        lines.append(
            f"- {entry['category']}: R$ {entry['actual_spend']:.2f} de R$ {entry['goal']:.2f} ({marker})"
        )
    return "\n".join(lines)


def generate_insights(
    month_ref: str,
    db_path: str,
    budget_report: list[dict] | None = None,
    chat_model: ChatModel | None = None,
) -> InsightsResult:
    conn = repository.connect(db_path)
    try:
        current_transactions = repository.list_transactions_by_month(conn, month_ref)
        previous_transactions = repository.list_transactions_by_month(
            conn, _previous_month_ref(month_ref)
        )
    finally:
        conn.close()

    current_spend = compute_category_spend(current_transactions)
    previous_spend = compute_category_spend(previous_transactions) if previous_transactions else {}

    # Feature 012: net the month's Reembolso inflows against expense categories.
    # `current_spend` is already gross expense per category (Reembolso is type
    # income, so compute_category_spend never counted it).
    reimbursement_inflows = [
        (t.description_raw, t.amount)
        for t in current_transactions
        if t.confidence == "high"
        and t.category == INCOME_CATEGORY
        and t.subcategory == REIMBURSEMENT_SUBCATEGORY
    ]
    reimbursements = compute_reimbursements(reimbursement_inflows, current_spend)
    reimbursement_section = ""
    if reimbursements.total:
        reimbursement_section = _REIMBURSEMENT_TEMPLATE.format(
            month_ref=month_ref,
            reimbursement_lines=_format_reimbursements(reimbursements, current_spend),
        )

    previous_month_section = ""
    if previous_spend:
        previous_month_section = _PREVIOUS_MONTH_TEMPLATE.format(
            previous_month_ref=_previous_month_ref(month_ref),
            previous_spend=_format_spend(previous_spend),
        )

    prompt = _PROMPT_TEMPLATE.format(
        month_ref=month_ref,
        current_spend=_format_spend(current_spend),
        budget_report=_format_budget_report(budget_report),
        reimbursement_section=reimbursement_section,
        previous_month_section=previous_month_section,
    )

    model = chat_model or get_chat_model()
    try:
        response = model.invoke(prompt)
        summary = (response.content or "").strip()
    except Exception as exc:  # noqa: BLE001 — deliberate: this node must never raise, see FR-006
        return InsightsResult(summary=None, error=str(exc))

    if not summary:
        return InsightsResult(summary=None, error="Resposta vazia do LLM")

    return InsightsResult(summary=summary, error=None)
