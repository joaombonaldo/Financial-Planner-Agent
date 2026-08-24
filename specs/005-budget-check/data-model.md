# Data Model: Budget Check

## Budget goal (config, not a database table)

Read from `config/budget.local.yaml` (Phase 1) via `get_budget()`.

| Field | Type | Description |
|---|---|---|
| category | string (map key) | must match a category name used by the categorization taxonomy, but this feature doesn't validate that (see spec.md Edge Cases) |
| goal | decimal (map value) | the monthly spending limit for that category |

## Category spend summary (`CategoryComparison`, in `state.py`)

This feature's computed output — not persisted.

| Field | Type | Description |
|---|---|---|
| `category` | string | the category being compared |
| `goal` | decimal | the configured monthly goal |
| `actual_spend` | decimal | sum of expense transactions in that category this month, excluding transfers and non-`high`-confidence rows |
| `difference` | decimal | `goal - actual_spend` — positive means headroom remaining, negative means the amount over |
| `status` | enum: `within_budget` \| `over_budget` | `over_budget` only when `actual_spend > goal` (exact equality is `within_budget`, per FR-005) |

## Transaction (read-only input, no changes)

Reads `type`, `category`, `amount`, `confidence`, `month_ref` from `transactions`. Selection rule for a given
category's `actual_spend`: `month_ref = ? AND type = 'expense' AND category = ? AND category != 'Internal
Transfer' AND confidence = 'high'`.
