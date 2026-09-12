"""Node generate_report: assembles the month's final report from earlier nodes' output.

Read-only, no LLM. Only touches transactions via db/repository.py (Principle II).
The graph's last node — see specs/007-generate-report.

Feature 012 (reimbursement netting) — see specs/012-reimbursement-netting:
the user splits some expenses with a third party (e.g. 50/50 with their brother);
the inbound repayment is categorized as `Receita / Reembolso`. Such a repayment is
NOT income — it is netted against the expense categories it offsets. The feature's
additions here are marked with `# --- reimbursement` comments.

Feature 014 (dual-stream report — see specs/013-credit-card-stream's "Follow-up:
report integration" and docs/decisions/credit-card-stream.md): credit-card
purchases are read separately (`instrument=credit`) and reported in their own
`credit_category_breakdown`/`credit_total`, dated by purchase month. They are
NEVER folded into `total_income`/`total_expense`/`category_breakdown` — those stay
debit-only, same default `list_transactions_by_month` always had. What hits the
debit total is the `Cartão de crédito` payment line; `fatura_reconciliations`
cross-checks that line's amount against the sum of the fatura's actual purchases
(see db/repository.py:update_transaction_category for how the two sides link via
`fatura_ref`). Marked with `# --- credit stream` comments.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field

from financial_planner.categorization.taxonomy import (
    CREDIT_CARD_CATEGORY,
    TRANSFER_CATEGORY,
    Taxonomy,
    load_taxonomy,
)
from financial_planner.db import repository
from financial_planner.state import (
    CategoryBreakdownEntry,
    MonthlyReport,
    Transaction,
    TransactionType,
)

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
class FaturaReconciliation:
    """Cross-check between a fatura's itemized credit purchases and the debit
    payment line that settles it, joined on `fatura_ref` (see module docstring).

    `delta` is expected to be fee-shaped (fatura interest / annuity / IOF) — a large
    or negative delta suggests a missing/duplicated purchase or a mismatched fatura.
    """

    fatura_ref: str
    debit_payment: float
    credit_purchases_total: float
    delta: float


@dataclass
class DualStreamReport(ReimbursementReport):
    """ReimbursementReport + feature 014 credit-card stream fields.

    `credit_category_breakdown`/`credit_total` are informational — purchases made
    this month (by purchase date), NOT included in total_expense/category_breakdown.
    """

    credit_category_breakdown: list[CategoryBreakdownEntry] = field(default_factory=list)
    credit_total: float = 0.0
    fatura_reconciliations: list[FaturaReconciliation] = field(default_factory=list)


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


def _compute_credit_stream(
    conn, month_ref: str
) -> tuple[list[CategoryBreakdownEntry], float]:
    """Feature 014: this month's confirmed card purchases, by category (informational,
    grouped by purchase month — never folded into the debit headline totals)."""
    credit_transactions = repository.list_credit_transactions_by_month(conn, month_ref)

    credit_totals: dict[tuple[str, TransactionType], float] = {}
    credit_total = 0.0
    for transaction in credit_transactions:
        if transaction.confidence != "high" or transaction.category is None:
            continue
        key = (transaction.category, transaction.type)
        credit_totals[key] = credit_totals.get(key, 0.0) + transaction.amount
        if transaction.type == TransactionType.EXPENSE:
            credit_total += transaction.amount

    credit_category_breakdown = [
        CategoryBreakdownEntry(category=category, type=tx_type, total=amount)
        for (category, tx_type), amount in credit_totals.items()
    ]

    return credit_category_breakdown, credit_total


def _compute_fatura_reconciliations(
    conn, debit_transactions: Iterable[Transaction]
) -> list[FaturaReconciliation]:
    """For every confirmed `Cartão de crédito` debit line this month, sum the actual
    purchases in the fatura it settles (via fatura_ref) and compare."""
    reconciliations = []
    for transaction in debit_transactions:
        if transaction.category != CREDIT_CARD_CATEGORY or not transaction.fatura_ref:
            continue
        fatura_purchases = repository.list_credit_transactions_by_fatura_ref(
            conn, transaction.fatura_ref
        )
        purchases_total = sum(
            t.amount if t.type == TransactionType.EXPENSE else -t.amount
            for t in fatura_purchases
        )
        reconciliations.append(
            FaturaReconciliation(
                fatura_ref=transaction.fatura_ref,
                debit_payment=transaction.amount,
                credit_purchases_total=purchases_total,
                delta=transaction.amount - purchases_total,
            )
        )
    return reconciliations


def generate_report(
    month_ref: str,
    db_path: str,
    budget_report: list[dict] | None = None,
    insights_summary: str | None = None,
    insights_error: str | None = None,
) -> DualStreamReport:
    conn = repository.connect(db_path)
    try:
        transactions = repository.list_transactions_by_month(conn, month_ref)
        # --- credit stream
        credit_category_breakdown, credit_total = _compute_credit_stream(conn, month_ref)
        fatura_reconciliations = _compute_fatura_reconciliations(conn, transactions)
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

    return DualStreamReport(
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
        credit_category_breakdown=credit_category_breakdown,
        credit_total=credit_total,
        fatura_reconciliations=fatura_reconciliations,
    )
