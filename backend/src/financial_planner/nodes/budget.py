"""Node budget_check: compares actual spend per category against configured goals.

Only touches transactions via db/repository.py and goals via budget/config.py — never
opens the budget file or sqlite3 directly (Principle II).
"""

from financial_planner.budget.config import get_budget
from financial_planner.categorization.taxonomy import TRANSFER_CATEGORY
from financial_planner.db import repository
from financial_planner.state import BudgetStatus, CategoryComparison, TransactionType


def check_budget(
    month_ref: str, db_path: str, budget_path: str | None = None
) -> list[CategoryComparison]:
    goals = get_budget(budget_path)

    conn = repository.connect(db_path)
    try:
        transactions = repository.list_transactions_by_month(conn, month_ref)
    finally:
        conn.close()

    spend_by_category: dict[str, float] = {category: 0.0 for category in goals}
    for transaction in transactions:
        if transaction.confidence != "high":
            continue
        if transaction.type != TransactionType.EXPENSE:
            continue
        if transaction.category == TRANSFER_CATEGORY:
            continue
        if transaction.category not in spend_by_category:
            continue
        spend_by_category[transaction.category] += transaction.amount

    comparisons = []
    for category, goal in goals.items():
        actual_spend = spend_by_category[category]
        difference = goal - actual_spend
        status = BudgetStatus.OVER_BUDGET if actual_spend > goal else BudgetStatus.WITHIN_BUDGET
        comparisons.append(
            CategoryComparison(
                category=category,
                goal=goal,
                actual_spend=actual_spend,
                difference=difference,
                status=status,
            )
        )

    return comparisons
