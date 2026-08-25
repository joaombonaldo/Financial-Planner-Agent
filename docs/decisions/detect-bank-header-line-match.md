# Decision: match the exact header line instead of whole-file substring search

**Branch**: `010-detect-bank-header-match`
**Date**: 2026-08-25
**Status**: Implemented
**Related**: [specs/001-ingest-extratos](../../specs/001-ingest-extratos/spec.md) (FR-001, FR-009, SC-005), [dedup-hash-discriminator.md](dedup-hash-discriminator.md) (previous fix in this same area — unrelated code path, noted only because both were found in the same review pass)

## Problem

`detect_bank` (`backend/src/financial_planner/parsers/detect.py`) originally decided
the source bank by searching for column-name substrings anywhere in the raw file
text:

```python
text = Path(path).read_text(encoding="utf-8-sig")

if "Crédito (R$)" in text and "Débito (R$)" in text:
    return Bank.BRADESCO

if "Descrição" in text and "Histórico" in text and "Valor" in text:
    return Bank.INTER
```

This has no structural guarantee — it's lexical coincidence over the *whole file*,
not "the header row actually declares these columns." Two consequences:

1. **A file that isn't a real Bradesco/Inter export can still be misdetected as
   one**, if its free-text fields (a memo, a merchant description, a note column)
   happen to contain the checked substrings. Concretely: a transaction description
   like `"Nota interna: ajuste de Crédito (R$) e Débito (R$) pendente de
   auditoria"` in an otherwise unsupported file format would have matched the
   Bradesco branch even with no Bradesco-shaped header anywhere in the file.
2. **This is worse than a parsing error, because it doesn't fail loudly.** If the
   file is misdetected, `nodes/ingest.py` runs the *wrong bank's parser* over it.
   `filter_transaction_lines` still only picks up lines matching the
   `DD/MM/YYYY;...` pattern, so it wouldn't crash — it would just silently produce
   transactions from whatever incidentally-date-shaped lines exist, using the wrong
   column semantics (e.g. treating some other field as Crédito/Débito). No
   `UnrecognizedBankError` is raised, so FR-009's safety net ("never fail silently")
   never engages. This directly threatens SC-005 ("flagged... never processed as if
   it were correct").
3. **Order dependency compounds it.** Bradesco is checked first unconditionally, so
   an ambiguous file that happened to satisfy both branches would always resolve to
   Bradesco with no signal that the detection was ambiguous.

The spec's own Assumptions section anticipates that bank export formats will change
over time ("future layout changes by the banks may require adjusting the
corresponding adapter") — which is exactly the scenario where this class of bug
would surface: a changed Bradesco header stops matching, but the file's other
content coincidentally satisfies the Inter substring check, so the system reports a
successful Inter import of a broken Bradesco file instead of rejecting it.

## Why this wasn't caught by the existing test suite

`test_detect_bank` only exercised the two banks' real, well-formed headers.
`test_detect_unknown_bank` used a completely unrelated CSV shape (`Date,Description,
Amount`) that shares no substrings with either bank's column names, so it could
never have exposed a false-positive collision — it only tested the "obviously
nothing matches" case, not the "something incidentally matches" case.

## Options considered

1. **Do nothing** — accept the risk. Rejected: this is the very first thing that
   runs on any input file (FR-001), and a wrong outcome here poisons everything
   downstream with no warning, exactly the failure mode FR-009 exists to prevent.
2. **Tighten the substring checks** (e.g. require all of a bank's column names,
   or require them in a specific relative order within the text). Rejected: still
   fundamentally a "does this text appear somewhere" check; free-text bank
   descriptions are effectively unconstrained, so no set of substring conditions
   fully closes the gap, only shrinks it.
3. **Match the exact header line** — implemented. See below.

## Implementation

`detect_bank` now splits the file into lines and looks for a line whose *stripped
content equals* one of two known header strings, verbatim:

```python
_BRADESCO_HEADER = "Data;Histórico;Docto.;Crédito (R$);Débito (R$);Saldo (R$)"
_INTER_HEADER = "Data Lançamento;Histórico;Descrição;Valor;Saldo"

for line in text.splitlines():
    stripped = line.strip()
    if stripped == _BRADESCO_HEADER:
        return Bank.BRADESCO
    if stripped == _INTER_HEADER:
        return Bank.INTER
```

A file's free-text fields can no longer trigger a match — only the actual header
row (Bradesco's own duplicated "Últimos Lancamentos" header included, since it's a
literal repeat of the same header line) can. If the header line doesn't match
either bank exactly — including a bank changing its export format — the function
now reliably falls through to `UnrecognizedBankError`, which is the correct,
loud-failure behavior FR-009 calls for.

This is intentionally strict (exact match, not `startswith`/`in`): per the spec's
own assumption, a layout change is expected to require adjusting the adapter
explicitly, not being silently absorbed by a looser match. A strict match turns a
future header change into a clear, actionable `UnrecognizedBankError` instead of a
silent misdetection.

## Consequences / things to watch

- **Any future header change to either bank's export requires updating
  `_BRADESCO_HEADER`/`_INTER_HEADER` in lockstep** with the corresponding parser
  adapter (`bradesco.py`/`inter.py`), since both now encode the same column
  layout assumption independently. If they drift apart, detection could accept a
  header that the parser then can't handle correctly (e.g. a column reordered but
  still same names) — this file doesn't validate column *order* semantics used by
  the parsers, only that the header line matches verbatim, which happens to cover
  order too since it's a full-string match today. Worth remembering if either
  header constant is ever loosened to a set-based/order-independent check.
- No longer needs the whole file held in memory just to search for two literal
  strings — the fix has this as a side benefit but it wasn't the goal.

## Test coverage added

`backend/tests/test_parsers.py`:
- `test_detect_rejects_free_text_that_merely_contains_bradesco_column_names`
- `test_detect_rejects_free_text_that_merely_contains_inter_column_names`

New fixtures, each containing every substring the old implementation checked for,
embedded in a free-text field with no real bank header present — proving these
would have been misdetected under the old logic and are correctly rejected now:
- `backend/tests/fixtures/detect/false_positive_bradesco_substrings.csv`
- `backend/tests/fixtures/detect/false_positive_inter_substrings.csv`

Existing coverage (`test_detect_bank`, `test_detect_unknown_bank`, and the full
suite) still passes unmodified.
