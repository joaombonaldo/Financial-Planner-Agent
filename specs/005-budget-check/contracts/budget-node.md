# Contract: Node `budget_check`

## `budget/config.py`

**`get_budget(path=None) -> dict[str, float]`**

- Reads `config/budget.local.yaml` by default (or `path`, when given — used by tests).
- Raises `BudgetNotConfiguredError` when the file doesn't exist.
- Returns `{}` (not an error) when the file exists but defines no categories.
- The only function in the codebase allowed to read this file — `nodes/budget.py` never opens it directly
  (Principle II).

## `nodes/budget.py`

**`check_budget(month_ref, db_path, budget_path=None) -> list[CategoryComparison]`**

**Behavior**:
1. Calls `get_budget(budget_path)` — lets `BudgetNotConfiguredError` propagate unhandled (FR-008: an explicit
   failure, not a silently empty report).
2. Reads the month's transactions via `db/repository.py`.
3. For each configured category, sums `amount` across transactions matching `type == 'expense'`,
   `category == <that category>`, `category != TRANSFER_CATEGORY`, `confidence == 'high'`.
4. Builds one `CategoryComparison` per configured category (even if actual spend is zero — FR-004's "no
   transactions this month" acceptance scenario).

**Guarantees the contract requires**:
- Never includes a category without a configured goal (FR-006).
- Never counts a transfer or an income transaction toward any total (FR-002/FR-003).
- Never mutates `transactions` (FR-009).
- `status = 'over_budget'` only when `actual_spend` is strictly greater than `goal` (FR-005).

## `graph.py`

**Change**: `update_memory` → `END` becomes `update_memory` → `budget_check` → `END`. The node wrapper converts
`check_budget()`'s dataclass list into plain dicts for the `budget_report` field of `GraphState` (see
research.md — checkpointer-safe state shape).
