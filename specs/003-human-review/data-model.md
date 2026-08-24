# Data Model: Human Review of Transactions

## Transaction (fields changed by this feature)

No new column on `transactions`. This feature only updates `category`, `subcategory`, and `confidence` — the same
fields feature 002 already fills in — via a human decision instead of memory/LLM.

| Field | Rule in this feature |
|---|---|
| `category`/`subcategory` | Kept (accept) or replaced by the user's validated input (correct) |
| `confidence` | Always becomes `"high"` once the decision is made — never stays `medium`/`low` after being reviewed |

## Pending review item (a concept, not a table)

A query, not an entity: `SELECT ... FROM transactions WHERE month_ref = ? AND confidence != 'high' ORDER BY date`.
See research.md — why this single condition already covers transfer candidates.

## GraphState

The minimal state that flows between the `StateGraph`'s nodes. Deliberately small: the nodes already fetch and
persist transactions directly in the database (the pattern established in features 001/002), so the graph state
doesn't carry the transaction list — only what the nodes need to know what to process.

| Field | Type | Description |
|---|---|---|
| `source_files` | list[str] | paths of the statements to import (input to `detect_and_parse`) |
| `month_ref` | str | month being processed (e.g. `"2026-08"`) — also used as the checkpointer's `thread_id` |
| `db_path` | str | path of the SQLite database shared by all nodes |

## Interruption payload (the `interrupt()` format)

Not a persisted entity — it's the data structure exchanged between `nodes/review.py` and whoever is driving the
graph (the CLI, or a test).

| Field | Description |
|---|---|
| `transaction` | date, description, amount, account, suggested category/subcategory/confidence |
| `is_transfer_candidate` | `bool` — changes the expected valid responses (`confirmar`/category vs. `aceitar`/category) |
| `error` | optional — present when the node is re-asking about the same item after an invalid response |

## User response (`Command(resume=...)`)

Free text, in the same format used by feature 002's `llm_categorizer`:

| Input | Effect |
|---|---|
| `"aceitar"` | keeps the suggested category/subcategory (only for items that aren't transfer candidates) |
| `"confirmar"` | keeps `"Transferência interna"` (only for transfer candidates) |
| `"category\|subcategory"` | replaces the suggestion with the provided category/subcategory (subcategory optional) |
| anything else, or a category outside the taxonomy | invalid — the node interrupts again for the same item with `error` filled in |
