# Research: Generate Report

No `NEEDS CLARIFICATION` remained in the Technical Context — the design follows spec.md's Assumptions directly.

## A new breakdown function, not a reuse of `compute_category_spend`

- **Decision**: `nodes/report.py` computes its own category breakdown, keyed by `(category, type)`, covering
  both `income` and `expense` transactions. It does not reuse `budget/spending.py::compute_category_spend`.
- **Rationale**: `compute_category_spend` is deliberately expense-only (that's exactly what `budget_check` and
  `generate_insights` need — goals and spend commentary are both about spending). The report needs the complete
  picture (BRD 5.4 — "the system tracks complete movement, not just spend"), including income categories like
  "Receita". Generalizing `compute_category_spend` to also handle income would change its meaning for its two
  existing callers for no benefit to them.
- **Alternatives considered**: adding a `type` filter parameter to `compute_category_spend` and calling it twice
  (once per type) from `nodes/report.py` — considered, but keyed differently: it returns `dict[str, float]`
  (category only), while the report needs to keep income and expense separate even when they'd otherwise share a
  category name — a `(category, type)` key from the start is simpler than merging two same-shaped dicts with a
  potential key collision.

## Transaction count reflects what's actually totaled

- **Decision**: `transaction_count` in the assembled report counts exactly the transactions that contributed to
  `total_income`/`total_expense`/`transfer_total` (i.e. `confidence == 'high'`) — not every row in the database
  for that `month_ref` regardless of confidence.
- **Rationale**: FR-010's purpose is letting the user sanity-check the totals against the source data; a count
  that included excluded rows (there shouldn't be any this late in the graph, but the safety filter exists
  anyway) would make that cross-check misleading.
- **Alternatives considered**: counting every row for the month unconditionally — rejected as inconsistent with
  what the count is actually meant to verify.

## Assembling, not recomputing, the budget and insights sections

- **Decision**: `generate_report(month_ref, db_path, budget_report=None, insights_summary=None,
  insights_error=None)` takes the already-computed budget comparison and insights result as parameters and
  copies them into `MonthlyReport` unmodified — it never calls `check_budget()` or `generate_insights()` itself.
- **Rationale**: matches FR-006/FR-007/SC-004 directly, and the same "don't recompute what a prior node already
  computed" pattern `generate_insights` itself already established for `budget_report` (feature 006).
- **Alternatives considered**: none seriously — recomputing would risk the assembled report disagreeing with
  what the user already saw from the earlier steps in the same run.

## Testing strategy

- **Decision**: tests seed transactions directly (same pattern as every prior feature's isolated node tests) and
  call `generate_report()` with manually constructed `budget_report`/`insights_summary` values, asserting the
  assembled `MonthlyReport` matches manual arithmetic and carries the given values through unchanged.
- **Rationale**: no LLM, no human interaction, no reason to involve the graph for the core logic — a plain
  function-level test is the simplest thing that could work (Principle I). A full-chain smoke test is still
  worthwhile in Polish, mirroring every prior feature's pattern, to prove the real wiring end to end.
- **Alternatives considered**: none — this is the same testing approach used throughout the project for
  non-LLM, non-interactive nodes.
