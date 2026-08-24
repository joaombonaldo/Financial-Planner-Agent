"""Shared category-spend calculation, used by both budget_check and generate_insights.

Pure function, no I/O — takes an already-fetched transaction list, returns totals per
category. Categories with zero matching transactions simply don't appear in the result.
"""

from financial_planner.categorization.taxonomy import TRANSFER_CATEGORY
from financial_planner.state import Transaction, TransactionType


def compute_category_spend(transactions: list[Transaction]) -> dict[str, float]:
    spend: dict[str, float] = {}
    for transaction in transactions:
        if transaction.confidence != "high":
            continue
        if transaction.type != TransactionType.EXPENSE:
            continue
        if transaction.category is None or transaction.category == TRANSFER_CATEGORY:
            continue
        spend[transaction.category] = spend.get(transaction.category, 0.0) + transaction.amount
    return spend
