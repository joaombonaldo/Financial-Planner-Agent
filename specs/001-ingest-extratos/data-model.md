# Data Model: Bank Statement Ingestion

Scope: only the fields and entities this feature (`detect_and_parse`) produces or consumes. Fields filled in by
later features (categorization, human review, installments) are marked as `deferred` and aren't this feature's
responsibility.

## Normalized transaction

Corresponds to the subset of the `transactions` schema (BRD 6.1) that this feature fills in.

| Field | Type | Source / rule | Required in this feature? |
|---|---|---|---|
| `dedup_hash` | string | deterministic hash over normalized `date + description_raw + amount + account` (see research.md) | Yes |
| `date` | date (ISO) | normalized from `DD/MM/YYYY` | Yes |
| `description_raw` | string | Bradesco: `Histórico` column. Inter: `Descrição`, falling back to `Histórico` when `Descrição` is blank | Yes |
| `account` | string | identifier for the source account/bank (Bradesco or Inter), determined by automatic detection | Yes |
| `type` | enum: `income` \| `expense` | derived from the sign/source column (Bradesco: which of `Crédito`/`Débito` is populated; Inter: sign of `Valor`) | Yes |
| `amount` | decimal, always positive | normalized from Brazilian number format (`1.645,20` → `1645.20`) | Yes |
| `month_ref` | string (e.g. `"2026-08"`) | derived from `date` | Yes |
| `category` | string, nullable | — | No — `deferred` to the categorization feature |
| `subcategory` | string, nullable | — | No — `deferred` |
| `confidence` | enum: `high`\|`medium`\|`low`, nullable | — | No — `deferred` |
| `installment_id` | FK, nullable | — | No — `deferred` (installments feature) |

**Validation**:
- A `dedup_hash` that already exists in the database → the transaction is silently dropped from the insert (not
  an error; the expected behavior per FR-006), but it's still counted in the import report (see `ImportResult`).
- A file line that doesn't match the transaction-line pattern (see research.md) never becomes a `Transaction` — it's
  ignored before reaching this model.

## Import result (`ImportResult`)

Not persisted — it's the return value of the ingestion process for a single run, used to report to the user
(FR-009) and for consumption by the graph's next node.

| Field | Type | Description |
|---|---|---|
| `bank` | enum: `bradesco` \| `inter` | bank detected for the file |
| `source_file` | string | path of the processed file |
| `transactions_imported` | int | number of new transactions inserted |
| `transactions_skipped_duplicate` | int | number of recognized transactions that already existed (dedup) |
| `balance_reconciliation` | enum: `ok` \| `mismatch` \| `not_available` | balance check result (research.md); `not_available` when the file has no usable balance column |
| `warnings` | list[string] | explanatory messages for any discrepancy (e.g. a balance line that doesn't reconcile) |

**Error state (doesn't produce an `ImportResult`)**: if the bank isn't recognized (FR-001), the process returns an
explicit error before producing any transaction — it's not an `ImportResult` with zero transactions, it's a
distinctly reported failure.

## Statement file (input, not persisted)

Represents the CSV provided by the user. Not a stored domain entity — it exists only as input to this feature's
process.

| Field | Description |
|---|---|
| `path` | local path of the manually exported CSV |
| `bank` (detected) | Bradesco or Inter — the result of automatic detection, not provided by the user |
