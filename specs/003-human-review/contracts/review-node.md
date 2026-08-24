# Contract: The `human_review` Node

## `nodes/review.py`

**Input**: `GraphState` (see data-model.md) — uses `month_ref` and `db_path`.

**Behavior**:
1. Queries the month's pending items (`confidence != 'high'`) directly from the database via `db/repository.py`.
2. If there are none, returns without calling `interrupt()` (FR-008 — never interrupts for nothing).
3. For each pending item, in query order:
   a. Calls `interrupt(payload)` with the item's data.
   b. Validates the received response (`Command(resume=...)`) against the taxonomy and against the item's type
      (transfer or not).
   c. If invalid, calls `interrupt()` again for the **same** item, with `error` filled in the payload — doesn't
      move to the next item until getting a valid response.
   d. If valid, persists the decision immediately via `db/repository.py` (`confidence = "high"`) and moves on to
      the next pending item.

**Guarantees the contract requires**:
- Never persists a category outside the taxonomy (FR-009/SC-005).
- Never leaves a transfer candidate without an explicit decision (FR-004/SC-004).
- Resuming after a process interruption never re-presents an already-decided item (FR-007) — guaranteed by the
  combination of always querying the database fresh + checkpointer replay (see research.md).
- Doesn't write to `merchant_memory` — out of scope (FR-010).

## `graph.py`

**Responsibility**: build and compile the `StateGraph` (`detect_and_parse` → `categorize` → `human_review`) with
`SqliteSaver` as the checkpointer, using the same database file as `db/repository.py`. Exposes a
`build_graph(db_path) -> CompiledGraph` function — whoever calls it (the CLI or a test) is responsible for
invoking/resuming via `thread_id = month_ref`.

## `interface/cli.py`

**Responsibility**: drive the interruption loop — invokes the graph, when it receives an `interrupt()` formats
the payload for the terminal, reads a line from `stdin`, and resumes the graph with that response, repeating
until the graph finishes. Knows nothing about taxonomy or business rules — it just displays what the node sends
and returns text (see research.md).
