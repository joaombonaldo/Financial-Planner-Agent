# Data Model: Generate Report

## Category breakdown entry (`CategoryBreakdownEntry`, in `state.py`)

| Field | Type | Description |
|---|---|---|
| `category` | string | the category |
| `type` | string (`"income"` \| `"expense"`) | which side of the ledger this total belongs to |
| `total` | float | sum of confirmed (`confidence = high`) transactions for that category and type, excluding transfers |

## Monthly report (`MonthlyReport`, in `state.py`)

This feature's assembled output — not persisted.

| Field | Type | Description |
|---|---|---|
| `month_ref` | string | the processed month |
| `total_income` | float | sum of `type = income`, `confidence = high` transactions |
| `total_expense` | float | sum of `type = expense`, `confidence = high`, non-transfer transactions |
| `net_balance` | float | `total_income - total_expense` |
| `transfer_total` | float | sum of confirmed "Internal Transfer" transactions, kept separate |
| `category_breakdown` | list[`CategoryBreakdownEntry`] | every category with any confirmed activity this month |
| `transaction_count` | int | count of `confidence = high` transactions the totals above are based on |
| `budget_report` | list[dict] | the budget comparison from `budget_check`, carried through unmodified |
| `insights_summary` | string, nullable | the summary from `generate_insights`, carried through unmodified |
| `insights_error` | string, nullable | the recorded failure reason from `generate_insights`, when generation didn't succeed |

## Transaction (read-only input, no changes)

Reads `type`, `category`, `amount`, `confidence` from `transactions` for the processed `month_ref`. Selection
rule: `confidence = 'high'`; transfers (`category = 'Internal Transfer'`) are separated into `transfer_total`
rather than excluded outright, since FR-005 requires them to still be visible, just not counted as income/expense.
