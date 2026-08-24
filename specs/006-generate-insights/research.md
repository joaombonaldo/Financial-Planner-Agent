# Research: Generate Insights

No `NEEDS CLARIFICATION` remained in the Technical Context — the design follows spec.md's Assumptions directly.

## Extracting the spend calculation into `budget/spending.py`

- **Decision**: pull the per-category sum currently inline in `nodes/budget.py::check_budget` into
  `budget/spending.py::compute_category_spend(transactions) -> dict[str, float]`, generalized to return spend for
  every category present (not just goal categories) — `check_budget` then looks up `spend_by_category.get(category,
  0.0)` per configured goal, functionally identical to before.
- **Rationale**: `generate_insights` needs the same calculation for two different months, and duplicating it would
  violate spec.md's own Assumptions ("reuses the same category-spend calculation logic already built for
  budget_check").
- **Alternatives considered**: having `generate_insights` call `check_budget()` twice (once per month) and derive
  spend from its output — rejected, since `check_budget` is scoped to configured-goal categories only
  (`FR-006` of feature 005), while insights need totals across every category that had any spend, goal or not, for
  a complete comparison.

## Previous month = immediately preceding calendar month

- **Decision**: `_previous_month_ref("2026-08")` → `"2026-07"`; `_previous_month_ref("2026-01")` → `"2025-12"`,
  via plain integer arithmetic on the `"YYYY-MM"` string, no date library needed.
- **Rationale**: matches spec.md's Assumptions directly; the pipeline's monthly cadence (BRD section 4) never
  implies any other lookback window.
- **Alternatives considered**: a configurable N-month lookback — rejected as unneeded complexity (Principle I)
  for a v1 that only needs "did anything change since last month."

## Never raising on LLM failure

- **Decision**: `generate_insights` wraps the LLM call in a broad `except Exception`, returning an `InsightsResult`
  with `summary=None` and `error=<reason>` instead of propagating. An empty/blank response after `.strip()` is
  treated the same as a failure.
- **Rationale**: FR-006 is explicit and BRD marks this node "optional" — the one place in this codebase where a
  broad exception handler is the *correct* design, not a code smell, because the contract is "never block the
  rest of the run," not "handle known failure modes."
- **Alternatives considered**: catching only specific exception types (connection errors, timeouts) — rejected,
  since FR-006 says "fails for any reason," and a narrower catch would let an unanticipated LLM client bug still
  crash the whole month's processing, which is exactly what this feature exists to prevent.

## Reusing the LLM test double, adding a failure variant

- **Decision**: reuse `tests/fixtures/categorization/llm_double.py::FakeChatModel` as-is for the success-path
  tests (same `invoke(prompt) -> response.content` shape `llm_categorizer.py` already relies on). Add a second
  small double, `RaisingChatModel`, to the same file, whose `invoke()` raises a given exception — used for
  FR-006's failure tests.
- **Rationale**: no new test infrastructure needed for the success path (Principle I); the failure path needs
  exactly one new, minimal double.
- **Alternatives considered**: a dedicated `tests/fixtures/insights/` module — rejected as unnecessary duplication
  when the existing double already fits.

## Where the result goes

- **Decision**: `graph.py`'s node wrapper adds `insights_summary: str | None` and `insights_error: str | None` to
  `GraphState`, mirroring the `budget_report` field's pattern (plain, checkpointer-safe types, not a dataclass).
- **Rationale**: consistent with how feature 005 already handles a computed, non-persisted result flowing to
  whatever consumes it next (the not-yet-built `generate_report`).
- **Alternatives considered**: nesting both under one `insights_result: dict` field — rejected as a marginal
  preference; two flat optional fields are just as simple and mirror `budget_report`'s existing flat-field
  pattern closely enough not to introduce a new shape.
