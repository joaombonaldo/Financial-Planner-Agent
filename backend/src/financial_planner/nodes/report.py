"""Node generate_report: assembles the month's final report from earlier nodes' output.

Read-only, no LLM. Only touches transactions via db/repository.py (Principle II).
The graph's last node — see specs/007-generate-report.

Feature 012 (reimbursement netting) — see specs/012-reimbursement-netting:
the user splits some expenses with a third party (e.g. 50/50 with their brother);
the inbound repayment is categorized as `Receita / Reembolso`. Such a repayment is
NOT income — it is netted against the expense categories it offsets. The feature's
additions here are deliberately localized and marked with `# --- reimbursement`
comments: another agent (feature C) will later restructure this file into
debit+credit streams, and these blocks should fold into that work with minimal
churn. The shared report dataclasses live in state.py (which feature 012 must not
touch), so the model is extended via thin subclasses below.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from financial_planner.categorization.taxonomy import (
    TRANSFER_CATEGORY,
    Taxonomy,
    load_taxonomy,
)
from financial_planner.db import repository
from financial_planner.state import CategoryBreakdownEntry, MonthlyReport, TransactionType

# --- reimbursement: a `Receita / Reembolso` inflow is a shared-expense repayment,
# not earnings. Sum it separately and net it against expenses.
INCOME_CATEGORY = "Receita"
REIMBURSEMENT_SUBCATEGORY = "Reembolso"

# Attribution is best-effort text matching (see compute_reimbursements); only tokens
# at least this long are used as category keywords, to avoid noise matches.
_MIN_KEYWORD_LEN = 4


@dataclass
class ReportCategoryBreakdownEntry(CategoryBreakdownEntry):
    """CategoryBreakdownEntry + feature 012 netting fields.

    `total` stays equal to the NET figure so the existing CLI printer keeps working
    unchanged; `gross` and `reimbursed` are new siblings for callers that want the
    detail. For income/non-netted categories: gross == net == total, reimbursed == 0.
    """

    gross: float = 0.0
    reimbursed: float = 0.0
    net: float = 0.0


@dataclass
class ReimbursementReport(MonthlyReport):
    """MonthlyReport + feature 012 aggregate reimbursement fields.

    `total_expense` and `net_balance` on this object are already NET of
    `total_reimbursements`. `unattributed_reimbursements` is the part that reduced
    the overall expense total but no single category.
    """

    total_reimbursements: float = 0.0
    unattributed_reimbursements: float = 0.0


@dataclass
class ReimbursementSummary:
    """Result of attributing the month's Reembolso inflows to expense categories."""

    total: float
    by_category: dict[str, float]
    unattributed: float


def _attribution_keywords(
    expense_categories: Iterable[str], taxonomy: Taxonomy
) -> dict[str, str]:
    """Map a lowercased keyword -> the single top-level expense category that owns it.

    Keywords are each expense category name plus its subcategory names, plus the
    slash/space-separated tokens of those names (>= _MIN_KEYWORD_LEN chars).
    Keywords that resolve to more than one category (e.g. "restaurante" appearing
    under both Alimentação and Lazer) are dropped as ambiguous.
    """
    owners: dict[str, set[str]] = {}
    for category in expense_categories:
        tokens = {category.lower()}
        for sub in taxonomy.subcategories_for(category):
            tokens.add(sub.lower())
            for part in sub.replace("/", " ").split():
                tokens.add(part.lower())
        for token in tokens:
            if len(token) >= _MIN_KEYWORD_LEN:
                owners.setdefault(token, set()).add(category)
    return {kw: next(iter(cats)) for kw, cats in owners.items() if len(cats) == 1}


def compute_reimbursements(
    reimbursements: list[tuple[str, float]],
    gross_expense_by_category: dict[str, float],
    taxonomy: Taxonomy | None = None,
) -> ReimbursementSummary:
    """Attribute each Reembolso inflow to a shared expense category by its description.

    KNOWN SIMPLIFICATION (feature 012): there is no counterparty field on
    Transaction and some banks emit generic PIX descriptions, so attribution is
    purely best-effort substring matching of the inflow's description against
    taxonomy-derived category keywords. An inflow whose description matches zero
    categories, more than one category, or a category with no gross spend this
    month falls into `unattributed` — it still reduces the overall expense total,
    just not a specific category line. Transaction-to-transaction matching is a
    documented follow-up (out of scope here).

    `reimbursements` is a list of (description_raw, amount) for the month's
    confirmed `Receita / Reembolso` inflows.
    """
    total = sum(amount for _, amount in reimbursements)
    if not reimbursements:
        return ReimbursementSummary(total=0.0, by_category={}, unattributed=0.0)

    taxonomy = taxonomy or load_taxonomy()
    keywords = _attribution_keywords(gross_expense_by_category.keys(), taxonomy)

    by_category: dict[str, float] = {}
    unattributed = 0.0
    for description, amount in reimbursements:
        text = (description or "").lower()
        matched = {cat for kw, cat in keywords.items() if kw in text}
        if len(matched) == 1:
            category = next(iter(matched))
            by_category[category] = by_category.get(category, 0.0) + amount
        else:
            unattributed += amount

    return ReimbursementSummary(
        total=total, by_category=by_category, unattributed=unattributed
    )


def generate_report(
    month_ref: str,
    db_path: str,
    budget_report: list[dict] | None = None,
    insights_summary: str | None = None,
    insights_error: str | None = None,
) -> ReimbursementReport:
    conn = repository.connect(db_path)
    try:
        transactions = repository.list_transactions_by_month(conn, month_ref)
    finally:
        conn.close()

    total_income = 0.0
    gross_expense = 0.0
    transfer_total = 0.0
    breakdown_totals: dict[tuple[str, TransactionType], float] = {}
    # --- reimbursement: collected here, netted after the loop.
    reimbursement_inflows: list[tuple[str, float]] = []
    transaction_count = 0

    for transaction in transactions:
        if transaction.confidence != "high":
            continue

        transaction_count += 1

        if transaction.category == TRANSFER_CATEGORY:
            transfer_total += transaction.amount
            continue

        # --- reimbursement: a Reembolso inflow is neither income nor a normal
        # category line — it is netted against expenses below.
        if (
            transaction.category == INCOME_CATEGORY
            and transaction.subcategory == REIMBURSEMENT_SUBCATEGORY
        ):
            reimbursement_inflows.append(
                (transaction.description_raw, transaction.amount)
            )
            continue

        if transaction.type == TransactionType.INCOME:
            total_income += transaction.amount
        elif transaction.type == TransactionType.EXPENSE:
            gross_expense += transaction.amount

        if transaction.category is not None:
            key = (transaction.category, transaction.type)
            breakdown_totals[key] = breakdown_totals.get(key, 0.0) + transaction.amount

    # --- reimbursement: attribute inflows to expense categories, then net.
    gross_expense_by_category = {
        category: amount
        for (category, tx_type), amount in breakdown_totals.items()
        if tx_type == TransactionType.EXPENSE
    }
    reimbursements = compute_reimbursements(
        reimbursement_inflows, gross_expense_by_category
    )

    category_breakdown = []
    for (category, tx_type), gross in breakdown_totals.items():
        reimbursed = (
            reimbursements.by_category.get(category, 0.0)
            if tx_type == TransactionType.EXPENSE
            else 0.0
        )
        net = gross - reimbursed
        category_breakdown.append(
            ReportCategoryBreakdownEntry(
                category=category,
                type=tx_type,
                total=net,  # NET, so the existing CLI/graph projection shows the netted figure
                gross=gross,
                reimbursed=reimbursed,
                net=net,
            )
        )

    total_expense = gross_expense - reimbursements.total

    return ReimbursementReport(
        month_ref=month_ref,
        total_income=total_income,
        total_expense=total_expense,
        net_balance=total_income - total_expense,
        transfer_total=transfer_total,
        category_breakdown=category_breakdown,
        transaction_count=transaction_count,
        budget_report=budget_report or [],
        insights_summary=insights_summary,
        insights_error=insights_error,
        total_reimbursements=reimbursements.total,
        unattributed_reimbursements=reimbursements.unattributed,
    )
