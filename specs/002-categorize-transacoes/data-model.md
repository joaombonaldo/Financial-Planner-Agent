# Data Model: Transaction Categorization

## Transaction (fields filled in by this feature)

Extends the schema already created by feature 001 (`transactions`). This feature fills in the fields that
ingestion left `NULL`:

| Field | Type | Source / rule |
|---|---|---|
| `category` | string | "Transferência interna" (candidate), a category mapped from memory, a category suggested by the LLM, or "Outros" (fallback) |
| `subcategory` | string, nullable | same, when applicable (transfer and "Outros" may have no subcategory) |
| `confidence` | enum: `high`\|`medium`\|`low` | `high` only via merchant memory; the LLM and transfer candidates never produce `high` |

Fields already filled in by feature 001 (`dedup_hash`, `date`, `description_raw`, `account`, `type`, `amount`,
`month_ref`) are only read, never changed by this feature. `installment_id` remains out of scope.

## Merchant Memory

New table, read-only in this feature (writing is a future feature's responsibility, `update_memory`).

| Field | Type | Description |
|---|---|---|
| `merchant_key` | string, PK | normalized (trim + lowercase) text of `description_raw` |
| `category` | string | category confirmed in a previous run |
| `subcategory` | string, nullable | confirmed subcategory, when applicable |

**Validation**: if `merchant_key` doesn't exist in the table, the transaction moves on to transfer detection / the
LLM (not an error — it's the expected case for a new merchant, see User Story 2).

## Taxonomy

Not a table — it's configuration loaded from `config/categories.yaml` (BRD Appendix A).

| Field | Type | Description |
|---|---|---|
| `category` | string | category name (e.g. "Alimentação") |
| `subcategories` | list[string] | valid subcategories for that category |

Two special entries are always present: `"Outros"` (fallback, no subcategory required) and `"Transferência
interna"` (used only by transfer detection, never suggested by the LLM).

**Validation**: any category/subcategory outside this list, coming from the LLM, is replaced with `"Outros"` /
`confidence = low` (see research.md).

## Transfer Candidate (a concept, not its own table)

The result of the pattern + mirrored-amount check (FR-007), expressed as the combination:
`category = "Transferência interna"`, `confidence = medium` (never `high` — always pending human confirmation,
never `low`, because it's a direct structural match, not a guess). There's no separate "TransferCandidate"
entity — the flag lives entirely in the transaction's own fields. Confirming (or rejecting) the suggestion is
left to a future feature (`human_review`).
