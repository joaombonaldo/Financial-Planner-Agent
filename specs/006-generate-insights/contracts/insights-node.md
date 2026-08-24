# Contract: Node `generate_insights`

## `budget/spending.py`

**`compute_category_spend(transactions: list[Transaction]) -> dict[str, float]`**

Pure function, no I/O. Sums `amount` per `category` across the given transactions, applying the shared filter
(`type == 'expense'`, `category != TRANSFER_CATEGORY`, `confidence == 'high'`). Categories with zero matching
transactions simply don't appear in the returned dict.

## `nodes/insights.py`

**`generate_insights(month_ref, db_path, budget_report=None, chat_model=None) -> InsightsResult`**

**Behavior**:
1. Reads transactions for `month_ref` and for the immediately preceding month via `db/repository.py`.
2. Computes spend-per-category for both months via `budget/spending.py`.
3. Builds a prompt including: current month's spend, `budget_report` (when given), and the previous month's
   spend (only when that month has any data at all — otherwise the comparison is omitted entirely, per FR-005).
4. Calls the LLM (`chat_model` or `llm/client.py`'s real client) inside a broad `try/except` (see research.md —
   this is the one deliberately broad exception handler in the codebase).
5. On success with non-blank content: returns `InsightsResult(summary=text, error=None)`.
6. On any failure, or a blank response: returns `InsightsResult(summary=None, error=<reason>)`.

**Guarantees the contract requires**:
- Never raises (FR-006) — every failure path returns a populated `error`, never propagates.
- Never fabricates a comparison when no prior-month data exists (FR-005).
- Never mutates `transactions`, budget goals, or `merchant_memory` (FR-007).
- The prompt is always in Portuguese, and so is any response the LLM is asked to produce (FR-008) — this node
  doesn't attempt to translate; it simply never asks for anything but Portuguese.

## `graph.py`

**Change**: `budget_check` → `END` becomes `budget_check` → `generate_insights` → `END`. The node wrapper reads
`state.get("budget_report")` (already computed by the prior node) and passes it straight through — no
recomputation.
