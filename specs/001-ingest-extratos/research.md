# Research: Bank Statement Ingestion

No `NEEDS CLARIFICATION` marker was left in the Technical Context — the BRD (`docs/brd-financial-planner-agent.md`,
section 6.3) already validates both banks' format from real exports. This document records the technical decisions
needed to implement the business decisions already made.

## Transaction line detection

- **Decision**: test every line of the file against a date regex at the start of the line
  (`^\d{2}/\d{2}/\d{4};`); only matching lines become a transaction candidate.
- **Rationale**: validated against a real Bradesco file (54 total lines → 42 valid transaction lines), robustly
  handles leading metadata, a header duplicated mid-file ("Últimos Lancamentos"), and a "Total" footer without
  needing to map the exact line-by-line structure.
- **Alternatives considered**: a fixed `skiprows` per bank — rejected as fragile to metadata-size variation and
  unable to handle Bradesco's mid-file duplicated header.

## Automatic source-bank detection

- **Decision**: inspect the header's column structure before applying the specific parser — the presence of
  separate `Crédito (R$)` and `Débito (R$)` columns plus `Docto.` identifies Bradesco; the presence of a single
  signed `Valor` column plus Inter-style metadata lines (title/account/period/balance) identifies Inter.
- **Rationale**: the two formats are structurally distinct enough (column count and names) to not need an
  ambiguous heuristic; if neither pattern is recognized, the file is rejected (FR-001, FR-009).
- **Alternatives considered**: detection by file name/extension — rejected because the user exports the files
  manually and there's no guaranteed naming convention.

## Amount and date normalization

- **Decision**: an amount in Brazilian format (`1.645,20`) is normalized by removing the thousands separator
  (`.`) and swapping `,` for `.` before converting to a number; a `DD/MM/YYYY` date is parsed with an explicit
  format (equivalent to `strptime("%d/%m/%Y")`), never automatic format inference.
- **Rationale**: automatic date-format inference (e.g. `dateutil` without an explicit format) is ambiguous for
  dates like `01/02/2026` (could be read as month/day); an explicit format eliminates this whole class of error.
- **Alternatives considered**: using the system `locale` for pt-BR parsing — rejected because it depends on the
  runtime environment's configuration, breaking the Pragmatic Simplicity principle with no real need.

## Deduplication hash

- **Decision**: a deterministic hash (e.g. SHA-256) over the normalized concatenation of
  `date + description_raw + amount + account`, computed after amount/date normalization (not over the raw CSV
  text).
- **Rationale**: computing it over already-normalized values guarantees the same transaction produces the same
  hash even if the raw textual appearance varies slightly between exports (e.g. an extra space); satisfies FR-006
  and Principle VII of the constitution.
- **Alternatives considered**: using Bradesco's `Docto.` as a native identifier — rejected because Inter has no
  equivalent (BRD 6.3), so it can't serve as the single strategy for both banks.

## Balance check as a sanity net

- **Decision**: compare, in chronological order within the file, a row's declared balance against
  `previous balance ± current transaction amount`; discrepancies (beyond a rounding tolerance, e.g. R$ 0.01)
  produce a warning reported to the user (FR-009), but don't abort importing the transactions already recognized
  correctly.
- **Rationale**: it's a data-quality check, not a business rule that blocks the flow — the goal is visibility
  (the principle of never failing silently), not automatically blocking the whole file over one suspicious line.
- **Alternatives considered**: aborting the entire import on any balance discrepancy — rejected as disproportionate;
  a single line-reading error shouldn't discard an entire month of correct transactions.

## Testing strategy

- **Decision**: small fixtures (2-3 lines) per bank covering the happy path and the edge cases documented in the
  spec (BOM, duplicated header, blank `Descrição`, blank line, "Total" footer); deterministic tests, no network
  or LLM.
- **Rationale**: aligned with the constitution's "Testing Standards" section; parsers are pure enough to not need
  mocks.
- **Alternatives considered**: using the full real files as test fixtures — rejected because real data never
  enters the repository (constitution, "Sensitive Data Protection" section).
