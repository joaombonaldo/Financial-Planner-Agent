# Research: Human Review of Transactions

## Pending review = `confidence != 'high'`, no special condition for transfers

- **Decision**: an item is pending review if, and only if, `confidence != 'high'`. There's no separate OR
  condition for transfer candidates.
- **Rationale**: per feature 002, `category = "Transferência interna"` is only ever assigned with
  `confidence = medium` — never `high`. So every transfer candidate is already covered by the
  `confidence != 'high'` condition; an extra condition would be redundant. Simplifies FR-001 and the
  `list_pending_review` query.
- **Alternatives considered**: `WHERE confidence != 'high' OR category = 'Transferência interna'` — rejected as
  logically redundant given the invariant established in feature 002.

## Multiple interruptions in a single node

- **Decision**: `nodes/review.py` queries the month's pending items on every run/resume, and iterates over them
  calling `interrupt(payload)` once per item, inside a `for` loop. The user's response (`Command(resume=...)`) is
  validated and persisted immediately before moving to the next item in the loop.
- **Rationale**: it's LangGraph's own recommended pattern for HITL with multiple sequential questions in a single
  node run — on resume, the node re-executes from the start, and each already-answered `interrupt()` returns the
  resume value recorded in the checkpoint, without re-asking. Since the pending list is queried from the database
  on every run (not captured once in memory), items already decided in a previous resume simply no longer appear
  in the list — FR-007 ("don't ask again") falls out for free from the combination of the checkpointer + always
  querying the database fresh.
- **Alternatives considered**: one node per pending item, with a conditional edge deciding whether to loop back to
  the same node or move on — rejected as adding graph complexity (Principle I) with no real gain over the loop
  inside a single node.

## Category validation inside the node, not in the CLI

- **Decision**: validating a manually provided category/subcategory (FR-009) happens inside `nodes/review.py`,
  using the same `Taxonomy` from feature 002. If the response is invalid, the node calls `interrupt()` again for
  the **same** item, now with an error message in the payload, without moving to the next item.
- **Rationale**: keeps the CLI generic — it only displays the payload the node sends and returns a line of text,
  with no knowledge of categorization rules. This preserves Principle II (business rules stay out of the
  interface layer) and lets validation be tested with no terminal at all.
- **Alternatives considered**: validating in the CLI before sending the resume — rejected because it would
  duplicate taxonomy logic across two layers, and the CLI would end up knowing a business rule that isn't its
  responsibility.

## User response format

- **Decision**: the same text format used by `llm_categorizer` (feature 002): `"category|subcategory"` (blank
  subcategory if none), plus two special keywords: `aceitar` ("accept" — keeps the suggestion as-is) and
  `confirmar` ("confirm" — only for transfer candidates, keeps "Transferência interna").
- **Rationale**: reuses a format and parser already validated in the previous feature, instead of inventing a new
  response protocol — Principle I.
- **Alternatives considered**: an item-by-item interactive prompt (e.g. a TUI library with menus) — rejected as
  over-engineering for a flow-validation CLI (BRD section 3: "Focus on validating the agent flow before investing
  in UI").

## Checkpointer

- **Decision**: `langgraph-checkpoint-sqlite` (`SqliteSaver`), pointing at the same `.db` file used by
  `db/repository.py`. The graph's `thread_id` is `month_ref` (e.g. `"2026-08"`), as already defined in the BRD.
- **Rationale**: it's the piece that makes FR-006/FR-007/SC-002 possible — without a persistent checkpointer, any
  interruption would lose the session's progress. The BRD already plans a future swap to
  `langgraph-checkpoint-postgres` "same interface", so using the SQLite variant now doesn't compromise
  Principle IV.
- **Alternatives considered**: an in-memory checkpointer (`MemorySaver`) — rejected because it doesn't survive a
  real process interruption, directly violating SC-002.

## Testing strategy

- **Decision**: tests call the compiled graph via `.invoke()`/`.stream()` with a test `thread_id`, capture the
  first `interrupt()`'s payload, respond with `Command(resume=...)`, and repeat until the graph finishes — all of
  it inside the test process, with no subprocess nor real terminal.
- **Rationale**: keeps the suite deterministic and fast, aligned with the constitution.
- **Alternatives considered**: testing `interface/cli.py` end-to-end by simulating stdin — kept as a light
  additional test (smoke test), not as the main way to test the node's decision logic.
