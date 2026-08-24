# Data Model: Generate Insights

## Month spend summary (computed, shared with `budget_check`)

`budget/spending.py::compute_category_spend(transactions) -> dict[str, float]` — a plain mapping, category name
to total expense, built from the same filter rule used everywhere else in the pipeline: `type == 'expense'`,
`category != 'Internal Transfer'`, `confidence == 'high'`. Not a dataclass — a dict is the whole entity.

## Insights result (`InsightsResult`, in `state.py`)

This feature's computed output — not persisted.

| Field | Type | Description |
|---|---|---|
| `summary` | string, nullable | the generated Portuguese summary text, or `None` if generation failed |
| `error` | string, nullable | a clear reason when `summary` is `None`; always `None` when `summary` is set |

Exactly one of `summary`/`error` is set at a time — never both `None`, never both populated.

## Transaction (read-only input, no changes)

Reads the same fields `budget_check` already reads (`type`, `category`, `amount`, `confidence`), for two
`month_ref` values: the one being processed, and the immediately preceding one (when it exists).
