"""Node budget: compares actual spend per category against configured goals, and
owns reading/writing the goals themselves (feature: budget UI, 2026-09-14).

Only touches db/repository.py — goals live in the `budget_goals` table now, not
`config/budget.local.yaml` (BRD §5.5 always anticipated this: "the same function
starts reading from [a real store], without changing the rest of the system" — every
caller of `check_budget` is unchanged by this, only where the goals come from moved).
"""

from financial_planner.budget.spending import compute_category_spend
from financial_planner.db import repository
from financial_planner.db.repository import DEFAULT_BUDGET_SCOPE
from financial_planner.state import BudgetStatus, CategoryComparison


def check_budget(month_ref: str, db_path: str) -> list[CategoryComparison]:
    conn = repository.connect(db_path)
    try:
        goals = repository.get_effective_budget(conn, month_ref)
        # Feature 014 decision: budget stays debit-only. Card spend is budgeted via
        # a single `Cartão de crédito` goal (the bill amount), not per-category —
        # counting credit purchases here too would double-count them against both
        # their own category's goal and the card goal. See docs/decisions/
        # credit-card-stream.md and specs/013-credit-card-stream's follow-up §5.
        transactions = repository.list_transactions_by_month(conn, month_ref)
    finally:
        conn.close()

    spend_by_category = compute_category_spend(transactions)

    comparisons = []
    for category, goal in goals.items():
        actual_spend = spend_by_category.get(category, 0.0)
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


def get_default_goals(db_path: str) -> dict[str, float]:
    """The global default goal set."""
    conn = repository.connect(db_path)
    try:
        return repository.list_budget_goals(conn, DEFAULT_BUDGET_SCOPE)
    finally:
        conn.close()


def set_default_goals(goals: dict[str, float], db_path: str) -> dict[str, float]:
    """Full replace of the global default goal set."""
    conn = repository.connect(db_path)
    try:
        repository.replace_budget_goals(conn, DEFAULT_BUDGET_SCOPE, goals)
        return repository.list_budget_goals(conn, DEFAULT_BUDGET_SCOPE)
    finally:
        conn.close()


def get_month_goals(month_ref: str, db_path: str) -> tuple[dict[str, float], dict[str, float]]:
    """`(overrides, effective)` for one month: `overrides` is that month's own rows
    only (empty if it has none yet — everything currently falls back to default),
    `effective` is the merged view `check_budget` actually uses."""
    conn = repository.connect(db_path)
    try:
        overrides = repository.list_budget_goals(conn, month_ref)
        effective = repository.get_effective_budget(conn, month_ref)
        return overrides, effective
    finally:
        conn.close()


def set_month_goals(
    month_ref: str, goals: dict[str, float], db_path: str
) -> tuple[dict[str, float], dict[str, float]]:
    """Full replace of `month_ref`'s overrides (not the merged view — a category
    left out of `goals` reverts to the default, it does not zero out)."""
    conn = repository.connect(db_path)
    try:
        repository.replace_budget_goals(conn, month_ref, goals)
        overrides = repository.list_budget_goals(conn, month_ref)
        effective = repository.get_effective_budget(conn, month_ref)
        return overrides, effective
    finally:
        conn.close()
