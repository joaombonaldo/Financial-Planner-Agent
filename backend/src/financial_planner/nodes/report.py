"""Node generate_report: assembles the month's final report from earlier nodes' output.

Read-only, no LLM. Only touches transactions via db/repository.py (Principle II).
The graph's last node — see specs/007-generate-report.
"""

from financial_planner.categorization.taxonomy import TRANSFER_CATEGORY
from financial_planner.db import repository
from financial_planner.state import CategoryBreakdownEntry, MonthlyReport, TransactionType


def generate_report(
    month_ref: str,
    db_path: str,
    budget_report: list[dict] | None = None,
    insights_summary: str | None = None,
    insights_error: str | None = None,
) -> MonthlyReport:
    conn = repository.connect(db_path)
    try:
        transactions = repository.list_transactions_by_month(conn, month_ref)
    finally:
        conn.close()

    total_income = 0.0
    total_expense = 0.0
    transfer_total = 0.0
    breakdown_totals: dict[tuple[str, TransactionType], float] = {}
    transaction_count = 0

    for transaction in transactions:
        if transaction.confidence != "high":
            continue

        transaction_count += 1

        if transaction.category == TRANSFER_CATEGORY:
            transfer_total += transaction.amount
            continue

        if transaction.type == TransactionType.INCOME:
            total_income += transaction.amount
        elif transaction.type == TransactionType.EXPENSE:
            total_expense += transaction.amount

        if transaction.category is not None:
            key = (transaction.category, transaction.type)
            breakdown_totals[key] = breakdown_totals.get(key, 0.0) + transaction.amount

    category_breakdown = [
        CategoryBreakdownEntry(category=category, type=tx_type, total=total)
        for (category, tx_type), total in breakdown_totals.items()
    ]

    return MonthlyReport(
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
    )
