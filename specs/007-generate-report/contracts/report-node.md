# Contract: Node `generate_report`

## `nodes/report.py`

**`generate_report(month_ref, db_path, budget_report=None, insights_summary=None, insights_error=None) ->
MonthlyReport`**

**Behavior**:
1. Reads the month's transactions via `db/repository.py`.
2. For each transaction with `confidence == 'high'`:
   - if `category == TRANSFER_CATEGORY`: add to `transfer_total`, exclude from everything else.
   - elif `type == income`: add to `total_income` and to the `(category, 'income')` breakdown entry.
   - elif `type == expense`: add to `total_expense` and to the `(category, 'expense')` breakdown entry.
3. Computes `net_balance = total_income - total_expense`.
4. Copies `budget_report`, `insights_summary`, `insights_error` into the result unmodified.

**Guarantees the contract requires**:
- Never includes a transfer in `total_income`, `total_expense`, `net_balance`, or `category_breakdown` (FR-005).
- Includes every category with any confirmed activity, income or expense, goal or no goal (FR-004).
- `transaction_count` reflects exactly the transactions that contributed to the totals (see research.md).
- Never mutates `transactions`, budget goals, or `merchant_memory` (FR-008).
- Never calls an LLM (FR-009) and never recomputes `budget_report`/insights — only assembles what it's given.

## `graph.py`

**Change**: `generate_insights` → `END` becomes `generate_insights` → `generate_report` → `END`. The node wrapper
passes `state.get("budget_report")`, `state.get("insights_summary")`, `state.get("insights_error")` straight
through, and converts the returned `MonthlyReport` into a plain dict for the `report` field of `GraphState`.
