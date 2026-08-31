# Decision: credit-card fatura ingestion as a separate stream

**Branch**: `013-credit-card-stream`
**Date**: 2026-08-30
**Status**: Implemented (parsers / detection / schema / persistence / tests). Report
integration is a documented follow-up — see spec §"Follow-up: report integration".
**Related**: [specs/013-credit-card-stream](../../specs/013-credit-card-stream/spec.md),
[dedup-hash-discriminator.md](dedup-hash-discriminator.md),
[detect-bank-header-line-match.md](detect-bank-header-line-match.md),
[installments-deferred-to-phase-3.md](installments-deferred-to-phase-3.md)

## Model

Credit-card purchases are a **separate stream** from the debit/PIX extracts:

- They are itemized from the monthly fatura PDF, categorized normally (any category —
  `Lazer`, `Compras`, `Alimentação`, …; **category and instrument are independent
  axes**), dated by **purchase date**, and grouped by the month of purchase
  (`month_ref`).
- They are **NOT added to that month's headline expense total.** A May purchase that
  lands on an August-due fatura is informational — "what I put on the card".
- The **fatura payment** appears in the debit/PIX extract as one line in the month it
  is paid, categorized `Cartão de crédito` (whatever that category is called in
  `config/categories.yaml` after the taxonomy reorg — it was
  `Cartão de crédito/Parcelamentos` in Appendix A). That line is what hits the debit
  total, and it carries a `fatura_ref` pointing at the fatura it settles.
- Sum of a fatura's credit purchases should reconcile against the corresponding
  fatura payment line, ± fatura-level interest / annuity / IOF.

### `fatura_ref`

`fatura_ref` is the **`YYYY-MM` of the fatura's due date** — i.e. the month the
fatura is paid, which is the month its settling line shows up in the debit extract.
For both sample faturas the due date is in September, so `fatura_ref = "2026-09"`
even though the user's filenames say `2026-08` (their closing-month convention).
Rule lives in `parsers/credit_card_common.fatura_ref_for(due_date)`.

`month_ref` on a credit row stays the **purchase month**, unchanged from the debit
semantics.

## PDF parsing

`pdfplumber` (added to `backend/pyproject.toml`) extracts the text layer; then the
same philosophy as the CSV adapters applies — a per-line transaction regex, only
matching lines become transactions. `parsers/pdf_text.py` centralizes extraction and
handles two real-world quirks:

- **Leading NUL padding.** `extracts/fatura-inter-2026-08.pdf` is a valid PDF
  preceded by ~430 KB of `0x00` bytes (a download/save artifact); pdfminer rejects it
  outright ("No /Root object"). We strip everything before the `%PDF` marker before
  handing the bytes to pdfplumber.
- **Password-protected PDFs.** Neither sample is encrypted. If a bank ships one, the
  password is read from an env var — per-bank `CREDIT_CARD_PDF_PASSWORD_BRADESCO` /
  `CREDIT_CARD_PDF_PASSWORD_INTER` first, then shared `CREDIT_CARD_PDF_PASSWORD`.
  Never a CLI arg, never logged.

### What each sample PDF looks like

| | Bradesco fatura | Inter fatura |
|---|---|---|
| Text layer | yes (iText producer), 2 pages | yes (Chromium print → pdfcpu), 8 pages |
| Password | none | none |
| Corruption | none | ~436 KB of leading NUL bytes |
| Row date | `DD/MM` — **no year** (inferred from due date) | `DD de <mon>. YYYY` — full date |
| Row layout | `DD/MM  desc  [city]  [US$]  R$[-]`; rates/limits table printed to the **right** at the same y — filtered by x-coordinate (`extract_left_column_pages`) | `DD de mon. YYYY  desc  -  [+ ]R$ value`; the lone `-` is the empty "Beneficiário" column, `+` marks a credit |
| Installments | bare `NN/MM` token inside the description (`HOTEL ... 03/06`) | `(Parcela NN de MM)` spelled out in the description |
| Payment / credit line | trailing `-` on the amount (`638,06-`) and/or `PAGTO`/`ESTORNO`/… keyword | leading `+` before `R$` and/or keyword |
| Foreign currency | US$ + R$ on one line, BRL last; take the rightmost BRL token | separate un-dated `Valor e símbolo da moeda de origem: …` detail lines → ignored (don't match the row regex) |
| Per-cardholder sections | `... Cartão 4066 XXXX XXXX 8989` headers + `Total para<name>` subtotals | `CARTÃO 5361****1034` headers + `Total CARTÃO …` subtotals |
| Next-fatura installments | n/a in sample | listed under "Próxima fatura" **without a date prefix** → ignored |
| Total | "Total da fatura em real" / "(=)Total" — `R$ 700,05` | "Fatura atual" / header line — `R$ 3.122,62` |
| Due date | "Total da fatura / Vencimento … R$ 700,05 04/09/2026" | header line `5361****7199 02/09/2026 R$ 3.122,62`; "Data de Vencimento 02/09/2026" |
| Closing date | only the **next** fatura's is printed ("Previsão de fechamento da próxima fatura:23/09/2026") | only the **next** fatura's cut is printed ("Data de corte: 25/09/2026") |
| Previous balance | "Saldo anterior… R$ 638,06" | "Valor antecipado R$ 0,00" |

Reconciliation on the real files: sum of expense rows == fatura total exactly
(Bradesco 700,05; Inter 3.122,62), with the payment/credit rows classified `income`
and excluded from that sum.

## Detection

`parsers/detect.py` branches on file extension first: `.pdf` → credit-card fatura
path, anything else → the existing exact-header-line CSV path (unchanged). A fatura
has no single header line, so the bank is decided by a **distinctive verbatim issuer
string** that only appears in that bank's fatura boilerplate — `"Bradesco Cart"`
(from "app Bradesco Cartões"), `"BANCO INTER S/A"`. This is the same spirit as
`detect-bank-header-line-match.md` (a fixed marker, not a loose "a column name
appears somewhere" search); the deviation is that it's a boilerplate phrase rather
than a header row, because a fatura doesn't have one. Unmatched PDF →
`UnrecognizedBankError`, same loud-failure contract as the CSV path.

`detect_instrument(path)` → `Instrument.CREDIT` for `.pdf`, `Instrument.DEBIT`
otherwise. `nodes/ingest.py` routes on the `(Bank, Instrument)` pair.

## Dedup

A fatura has no `Docto.` number. Credit rows get a discriminator built in
`parsers/credit_card_common.CreditTransactionBuilder`, mirroring
`dedup-hash-discriminator.md`:

```
credit:<card_tail>:<installment_index>/<installment_count>:<occurrence_index>
```

- `credit:` prefix — a credit row can never collide with a debit row that shares
  `date+description+amount+account` (the fatura payment line vs. an identical-looking
  purchase). `parsers/dedup.py` is **unchanged** — no change to debit hashes.
- `card_tail` — masked last 4 of the card the row sits under (additional cardholders).
- installment index/count — two installments of the same purchase on one fatura are
  distinct rows.
- `occurrence_index` — a stable per-file count over
  `(date, description, amount, installment_index)`, exactly like the Inter debit
  adapter, so re-ingesting the same fatura is idempotent (FR-006) while two genuine
  same-day / same-merchant / same-amount purchases stay distinct (verified on the
  real Inter file: two `SABOR DE LUNA` on 2026-08-23, R$ 107,80 and R$ 29,00).

## Schema + model

`db/schema.sql` — two new columns on `transactions` (source of truth for a **fresh**
DB, created by `repository.connect`'s `CREATE TABLE IF NOT EXISTS`):

```sql
instrument TEXT NOT NULL DEFAULT 'debit',  -- 'debit' | 'credit'
fatura_ref TEXT                            -- YYYY-MM of the fatura (credit rows now; debit payment line later)
```

plus `idx_transactions_instrument_month` and `idx_transactions_fatura_ref`.

`state.py` — `Instrument` enum; `Transaction` gains `instrument` (default
`Instrument.DEBIT`), `fatura_ref`, and `installment_index` / `installment_count`
(parsed and carried on the object for reconciliation + dedup, **not** persisted as
columns — the full installments feature stays deferred per
`installments-deferred-to-phase-3.md`).

`db/repository.py`:
- `insert_transaction` / `_row_to_transaction` / `_TRANSACTION_COLUMNS` carry the two
  new columns.
- `list_transactions_by_month(conn, month_ref, instrument=Instrument.DEBIT)` — the
  **default is debit-only**, so `report` / `budget` / `insights` / `categorize` see
  exactly what they saw before this feature; credit purchases don't leak into the
  headline debit totals. `instrument=None` returns every stream.
- new: `list_credit_transactions_by_month(conn, month_ref)` and
  `list_credit_transactions_by_fatura_ref(conn, fatura_ref)`.

### Migration for the existing `data/financial-planner.db`

`CREATE TABLE IF NOT EXISTS` does **not** add columns to an existing table, so run
this once (the user runs it — a classifier blocks DB writes from the agent):

```sql
ALTER TABLE transactions ADD COLUMN instrument TEXT NOT NULL DEFAULT 'debit';
ALTER TABLE transactions ADD COLUMN fatura_ref TEXT;

-- ADD COLUMN ... DEFAULT already backfills every existing row to 'debit';
-- this is just an explicit belt-and-braces no-op:
UPDATE transactions SET instrument = 'debit' WHERE instrument IS NULL;

CREATE INDEX IF NOT EXISTS idx_transactions_instrument_month ON transactions (instrument, month_ref);
CREATE INDEX IF NOT EXISTS idx_transactions_fatura_ref ON transactions (fatura_ref);
```

No existing dedup hash changes (the discriminator is additive and credit-only), so
re-importing the CSV extracts after the migration is a no-op.

## Consequences / things to watch

- **Bradesco year inference.** `DD/MM` → year is `due.year` if `month <= due.month`
  else `due.year - 1`. Breaks for an installment older than ~12 months before the
  due date (none in the sample; faturas don't show history that deep).
- **Closing date is the *next* fatura's** on both documents — stored as-is in
  `FaturaMetadata.closing_date` with a code comment. The current fatura's closing
  date is simply not printed. Not needed for reconciliation.
- **Bradesco left-column x cutoff** (`x_max=360`) is tuned to the sample's layout. A
  layout change moves it; the transaction regex still anchors on `^DD/MM `, so the
  failure mode is "row dropped", not "garbage row".
- **FX metadata is dropped** (origin currency, quote, per-transaction IOF is kept
  only as its own `IOF …` line). Acceptable for categorization + reconciliation;
  revisit if per-transaction FX detail is ever needed.
- **Categorization of credit rows** is not wired yet — `list_transactions_by_month`
  defaults to debit-only, so `categorize` / `human_review` don't see credit rows.
  They land uncategorized. Wiring them in is part of the report follow-up.
