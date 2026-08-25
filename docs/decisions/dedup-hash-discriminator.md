# Decision: add a per-bank discriminator to the dedup hash

**Branch**: `009-dedup-occurrence-index`
**Date**: 2026-08-25
**Status**: Implemented
**Related**: [specs/001-ingest-extratos](../../specs/001-ingest-extratos/spec.md) (FR-006, SC-002, SC-003)

## Problem

`compute_dedup_hash` (`backend/src/financial_planner/parsers/dedup.py`) originally
keyed the dedup hash on `date + description + amount + account` only:

```python
payload = f"{transaction_date.isoformat()}|{description_raw.strip()}|{amount:.2f}|{account}"
```

Those four fields are not a safe uniqueness key. Two genuinely distinct real
transactions can share all four — e.g. two identical-amount purchases at the same
merchant on the same day (two ¥15 bakery purchases, two identical Pix transfers to
the same person). Since `nodes/ingest.py` treats any hash already present in the DB
as a duplicate to skip (`repository.transaction_exists`), the second transaction
would be silently dropped on import, not merely on reimport.

This directly undermines **SC-002** ("100% of real transaction lines... recognized
and converted — no real transaction is lost") while superficially looking like
**SC-003** (reimport safety) was working correctly — the failure is invisible unless
someone manually reconciles transaction counts against the source file.

## Why this wasn't caught by the existing test suite

`test_dedup_within_same_file` (`backend/tests/test_parsers.py`) only exercises
Bradesco's "Últimos Lancamentos" block, which is a **literal duplicate of the same
line** (same Docto., same everything) — collapsing it to one transaction is
correct, intended behavior (FR-006). No fixture exercised the case of two
**distinct** transactions that happen to collide on the four normalized fields, so
the collision was never observed even though the risk was present from the initial
`001-ingest-extratos` implementation.

## Options considered

1. **Do nothing** — accept the risk. Rejected: this is P1 foundation code
   everything downstream (categorization, review, budget, insights, reports)
   depends on. A silently dropped transaction corrupts every later stage with no
   error surfaced anywhere (violates the intent of FR-009's "never fail silently").
2. **Global occurrence counter across all lines in a parse**, regardless of bank.
   Rejected: doesn't distinguish "true file duplicate" (Bradesco's repeated block —
   should collapse) from "distinct real transaction" (should not collapse) using
   the same signal, so it would either break the existing collapse behavior or fail
   to fix the collision, depending on which one comes first in file order.
3. **Per-bank discriminator, chosen per source's actual data** — implemented. See
   below.

## Implementation

`compute_dedup_hash` gained an optional fifth `discriminator: str = ""` parameter,
folded into the hash payload. Each adapter supplies whatever data actually
distinguishes real transactions in its source format:

- **Bradesco** (`parsers/bradesco.py`): uses the `Docto.` column, which was already
  being parsed and then discarded. It's a per-line document/reference number
  present on every real transaction. Two distinct transactions get different
  Docto. values → different hashes. The "Últimos Lancamentos" block repeats the
  *entire* line verbatim, Docto. included, so it still collapses to the same hash
  — no regression to the existing collapse behavior.
- **Inter** (`parsers/inter.py`): has no per-line reference number in the export
  format at all (`Data Lançamento;Histórico;Descrição;Valor;Saldo`). Instead, the
  parser counts occurrences of the same `(date, description, amount)` key as it
  walks the file in order and uses that occurrence index as the discriminator. This
  is deterministic across reimports of the same file (same source order → same
  occurrence sequence → same hashes → reimport dedup, FR-006, still works) while
  giving two real same-day/same-description/same-amount transactions distinct
  hashes.

## Consequences / things to watch

- **Order-dependence for Inter.** The occurrence-index discriminator relies on
  `filter_transaction_lines` producing the same relative order for the same file on
  every parse. If a future change reorders or dedupes lines before this point (e.g.
  sorting by date), the occurrence sequence — and therefore reimport dedup for
  transactions sharing a key — could break silently. If that ever changes, revisit
  this discriminator.
- **Inter still has a theoretical residual gap**: if a *reimported* file's row order
  for same-key transactions differs from the original (e.g. the bank re-exports
  with a different internal tie-break for same-day transactions), the occurrence
  index could realign incorrectly and either wrongly re-dedupe or wrongly
  duplicate. No evidence this happens in practice; flagging for awareness only.
- **Bradesco depends on Docto. always being populated.** All real-transaction and
  administrative lines observed so far have a Docto. value (including `0` for
  "COD. LANC. 0" administrative lines). If a future Bradesco export ever omits it,
  the discriminator degrades to `""` for those lines only, which is equivalent to
  the old behavior (collision risk reappears for that subset).
- Existing dedup hash values change for all Bradesco/Inter transactions (the hash
  payload shape changed). No persisted hash values are referenced anywhere outside
  equality checks in code/tests, so this has no migration impact — but if a
  production DB already has rows keyed on the old hash format, reimporting the same
  file post-upgrade will treat every transaction as new (one-time re-import, not
  ongoing duplication) rather than matching the old hashes. Acceptable for this
  project's current stage (no production data yet), but worth a heads-up before any
  real deployment.

## Test coverage added

`backend/tests/test_parsers.py`:
- `test_bradesco_distinct_transactions_same_fields_get_different_hashes`
- `test_bradesco_same_day_same_amount_both_survive_import`
- `test_inter_distinct_transactions_same_fields_get_different_hashes`
- `test_inter_same_day_same_amount_reimport_is_still_idempotent`

New fixtures:
- `backend/tests/fixtures/bradesco/same_day_same_amount.csv`
- `backend/tests/fixtures/inter/same_day_same_amount.csv`

Existing regression coverage (`test_dedup_within_same_file`,
`test_reimport_skips_duplicates`, `test_parse_bradesco`, `test_parse_inter`, full
suite) still passes unmodified — the change is additive to the hash payload, not a
behavior change for the cases those tests cover.
