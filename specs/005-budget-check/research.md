# Research: Budget Check

No `NEEDS CLARIFICATION` remained in the Technical Context — the design follows the BRD's own stated plan for
budget goals (section 5.5) plus the transfer-exclusion rule already established in section 5.2.

## `get_budget()` as its own small module

- **Decision**: `budget/config.py` exposes `get_budget(path=None) -> dict[str, float]`, reading
  `config/budget.local.yaml` by default. Raises a dedicated `BudgetNotConfiguredError` (in `state.py`, alongside
  `UnrecognizedBankError`) when the file doesn't exist.
- **Rationale**: BRD 5.5 explicitly describes this as a swappable function — "the same function starts reading
  from Supabase [in Phase 2], without changing the rest of the system." Isolating it mirrors `llm/client.py`'s
  role for the LLM (Principle III's swappability pattern, generalized to any external dependency, not just the
  LLM).
- **Alternatives considered**: reading the YAML file directly inside `nodes/budget.py` — rejected, since it would
  violate Principle II (the node would touch a file/config source directly instead of through a dedicated
  module) and make the Phase 2 Supabase swap require editing the node itself.

## Missing configuration vs. empty configuration

- **Decision**: a missing `budget.local.yaml` raises `BudgetNotConfiguredError`; a present-but-empty file (valid
  YAML, zero categories) returns an empty dict — no error.
- **Rationale**: FR-008/SC-004 — these are semantically different states ("you haven't set this up yet" vs. "you
  deliberately want zero goals") and must be distinguishable, not silently collapsed into the same "empty result."
- **Alternatives considered**: treating a missing file as an empty budget (auto-defaulting to zero goals) —
  rejected, since it would let a first-time setup mistake pass completely unnoticed (no goals ever get compared,
  no signal to the user that anything's wrong).

## Spend calculation: plain Python, not SQL aggregation

- **Decision**: `nodes/budget.py` reads the month's transactions via the existing
  `list_transactions_by_month`, then sums in Python: `type == 'expense' and category != TRANSFER_CATEGORY and
  confidence == 'high'`, grouped by `category`.
- **Rationale**: matches the volume already handled the same way by `transfer_detection.py` (feature 002) — a
  `GROUP BY SUM` query would work too, but adds a second way of reading the same table for no real benefit at
  this scale (Principle I).
- **Alternatives considered**: a SQL aggregate query (`SELECT category, SUM(amount) ... GROUP BY category`) —
  rejected as unneeded complexity for dozens of rows; worth revisiting only if/when transaction volume per month
  grows by orders of magnitude.

## Where the comparison result goes

- **Decision**: `nodes/budget.py`'s node wrapper in `graph.py` returns `{"budget_report": [...]}` as a plain list
  of dicts (not dataclass instances) in the state update, adding a `budget_report` field to `GraphState`. The
  underlying `check_budget()` function itself returns a list of `CategoryComparison` dataclass instances for a
  clean Python API when called/tested directly.
- **Rationale**: `GraphState` is checkpointed by LangGraph; keeping the state-update shape to plain
  dicts/lists/primitives avoids any question about whether a custom dataclass round-trips cleanly through the
  checkpointer's serializer. The dataclass/dict split mirrors the same separation already used elsewhere (e.g.
  `ImportResult` as a rich return value from `detect_and_parse`, versus the empty `{}` its graph wrapper returns).
- **Alternatives considered**: persisting the comparison to a new database table — rejected per spec.md's
  Assumptions; this is computed, ephemeral data meant for the next node in the same run, not a historical record
  (no current feature needs to look up a past month's budget comparison later).

## Testing strategy

- **Decision**: tests seed transactions directly (same pattern as features 002-004's isolated node tests) and
  write a temporary `budget.local.yaml`-equivalent file via `tmp_path`, passing its path explicitly to
  `get_budget()`/`check_budget()` rather than relying on the real gitignored file.
- **Rationale**: no LLM, no human interaction, no reason to involve the graph or a real file in the repo — a
  plain function-level test is the simplest thing that could work (Principle I).
- **Alternatives considered**: pointing tests at the real `config/budget.local.yaml` path — rejected, since that
  file is gitignored and personal (may not exist, or may hold the user's real goals, in any given environment).
