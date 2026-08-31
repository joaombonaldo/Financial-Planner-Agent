# Feature Specification: Credit-card fatura ingestion (separate stream)

**Feature Branch**: `013-credit-card-stream`

**Created**: 2026-08-30

**Status**: Implemented up to the report boundary — parsers, detection, schema,
persistence and tests are done. The debit+credit dual-stream **report** integration
is a documented follow-up (see the last section).

**Input**: User description: "Ingest the monthly credit-card fatura (PDF) from
Bradesco and Inter as a stream separate from the debit/PIX extracts: itemized,
categorized normally, dated by purchase date, grouped by purchase month, and NOT
added to the month's headline expense total. The fatura payment shows up on the
debit side as one `Cartão de crédito` line in the month it's paid, carrying a
`fatura_ref`. Sum of a month's credit purchases reconciles against that payment
line, ± fatura interest / annuity / IOF."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Itemize what I put on the card this month (Priority: P1)

As a user, I want to point the system at my monthly fatura PDF and get every card
purchase as an individual, normally-categorized transaction dated by when I made the
purchase, so I can see *what* I spent on the card — by category and by month —
without that amount inflating the month's headline expense total (which already
counts the fatura payment on the debit side).

**Why this priority**: It's the whole feature. Without it, card spend is a single
opaque debit line and the category breakdown is blind to roughly half of real
discretionary spending.

**Independent Test**: Feed a fatura PDF (or the anonymized text fixture) from each
bank and verify the output is a list of transactions in the normalized schema, each
with `instrument = credit`, a `fatura_ref`, `month_ref` = purchase month, and
(where present) an installment marker — without depending on any other graph node.

**Acceptance Scenarios**:

1. **Given** a Bradesco fatura PDF (text layer, `DD/MM` purchase dates with no year,
   a rates/limits table printed beside the transaction list, `NN/MM` installment
   tokens, a trailing-`-` payment line), **When** the system processes it, **Then**
   only the real `Lançamentos` rows become transactions, each tagged
   `instrument = credit`, dated by purchase date with the year inferred from the due
   date, grouped under their purchase month.
2. **Given** an Inter fatura PDF (text layer, possibly NUL-padded, `DD de mon. YYYY`
   dates, `(Parcela NN de MM)` markers, per-card sections, a "Próxima fatura" block
   of next month's installments, un-dated foreign-currency detail lines), **When**
   the system processes it, **Then** all `Despesas da fatura` rows become
   transactions, and the subtotals, the FX detail lines and the "Próxima fatura"
   installments do not.
3. **Given** a fatura whose purchases sum to the fatura total, **When** it is parsed,
   **Then** the sum of the `expense` rows equals the parsed fatura total (payment /
   credit rows classified `income` and excluded).

---

### User Story 2 - Reconcile card purchases against the fatura payment (Priority: P2)

As a user, I want the total of a fatura's itemized purchases to line up with the
single `Cartão de crédito` payment line that hits my debit extract when the fatura is
paid, so I can trust that nothing was dropped or double-counted between the two
streams.

**Why this priority**: It's the safety net that makes the separate-stream model
trustworthy; it builds on Story 1 but isn't needed to get value from itemization.

**Independent Test**: Seed a fatura's credit rows and a debit `Cartão de crédito`
line sharing a `fatura_ref`, and verify `sum(credit purchases for that fatura_ref)`
equals the debit line amount within the fatura's interest / annuity / IOF.

**Acceptance Scenarios**:

1. **Given** every credit purchase for `fatura_ref = 2026-09` and the debit payment
   line tagged `fatura_ref = 2026-09`, **When** they are compared, **Then** the
   difference is explained entirely by fatura-level interest / annuity / IOF (zero on
   a paid-in-full fatura with no foreign purchases).

---

### User Story 3 - Reimport a fatura without duplicating (Priority: P2)

As a user, I want to reprocess the same fatura (or a corrected re-export) without the
purchases showing up twice.

**Independent Test**: Ingest the same fatura PDF twice; the stored transaction count
does not increase on the second run.

**Acceptance Scenarios**:

1. **Given** a fatura already imported, **When** the same file is imported again,
   **Then** zero new transactions are created.
2. **Given** two genuine purchases on the same day at the same merchant for the same
   amount, **When** the fatura is processed, **Then** both are kept (distinct dedup
   hashes).

### Edge Cases

- `.pdf` extension routes to the fatura path; the CSV exact-header-line detection is
  untouched. A PDF that matches neither bank's issuer string is rejected with
  `UnrecognizedBankError` (no partial transactions).
- A fatura PDF preceded by NUL padding is still parsed (leading bytes before `%PDF`
  are stripped).
- A password-protected fatura reads its password from `CREDIT_CARD_PDF_PASSWORD` (or
  per-bank `…_BRADESCO` / `…_INTER`); never a CLI arg, never logged.
- Payment / credit rows on the fatura (`PAGTO`, `ESTORNO`, trailing `-`, leading `+`)
  are classified `income` and excluded from the "what I put on the card" sum.
- Only the *next* fatura's closing date is printed on either document; the current
  one's is stored as `None` where absent.
- Foreign-currency detail (origin amount, quote) is not retained; a per-transaction
  `IOF …` line, when the bank emits one, is kept as its own transaction.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST accept a Bradesco or Inter credit-card fatura PDF as an
  input file and extract its text layer with `pdfplumber`.
- **FR-002**: The system MUST identify transaction rows by a per-line regex (date at
  line start), same philosophy as the CSV adapters — metadata, headers, subtotals,
  foreign-currency detail lines and next-fatura installments MUST NOT become
  transactions.
- **FR-003**: The system MUST parse each row's purchase date, description, amount
  (Brazilian number format) and installment marker when present
  (`NN/MM` for Bradesco, `(Parcela NN de MM)` for Inter), and MUST infer the year for
  Bradesco's `DD/MM` dates from the fatura due date.
- **FR-004**: The system MUST extract fatura-level metadata: total, due date,
  previous balance, closing date (when printed), and a `fatura_ref` = `YYYY-MM` of
  the due date.
- **FR-005**: Every credit-card row MUST be persisted with `instrument = 'credit'`,
  `month_ref` = purchase month, and `fatura_ref` set.
- **FR-006**: The system MUST detect the source bank of a fatura PDF by a stable
  verbatim issuer string and route to the matching adapter; a non-matching PDF MUST
  raise `UnrecognizedBankError` without generating partial transactions.
- **FR-007**: The system MUST compute a credit-specific dedup discriminator
  (`credit:` prefix + card tail + installment index/count + per-file occurrence
  index) so that (a) a credit row never collides with a debit row sharing
  date+description+amount+account, (b) reimporting a fatura creates no duplicates,
  (c) two genuine same-day/same-merchant/same-amount purchases stay distinct.
- **FR-008**: Reading a month's transactions for the existing debit-oriented nodes
  (`report`, `budget`, `insights`, `categorize`) MUST return debit rows only by
  default — credit purchases MUST NOT leak into the headline debit totals.
- **FR-009**: The system MUST expose queries for "credit transactions by purchase
  month" and "credit transactions by `fatura_ref`".
- **FR-010**: A password-protected fatura MUST take its password from an env var, not
  a CLI argument.

### Key Entities *(include if feature involves data)*

- **Credit-card purchase**: a normalized transaction with `instrument = 'credit'`,
  `date` = purchase date, `month_ref` = purchase month, `fatura_ref` = `YYYY-MM` of
  the fatura's due date, optional `installment_index` / `installment_count`. Same
  category/subcategory/confidence mechanism as any other transaction (populated
  later).
- **Fatura metadata**: bank, due date, `fatura_ref`, total, closing date (nullable),
  previous balance. Parsed once per file; not persisted as a row.
- **Fatura payment line** (debit stream, populated by the report follow-up): the one
  `Cartão de crédito` debit transaction in the month the fatura is paid, tagged with
  the settled fatura's `fatura_ref`.

## Success Criteria *(mandatory)*

- **SC-001**: Every real `Lançamentos` / `Despesas da fatura` row in a sample fatura
  is recognized; no metadata/subtotal/FX-detail/next-fatura line becomes a
  transaction. (Bradesco sample: 5 rows; Inter sample: 28 rows.)
- **SC-002**: `sum(expense rows)` equals the parsed fatura total within the fatura's
  interest / annuity / IOF. (Both samples: exact.)
- **SC-003**: Reimporting a fatura yields zero duplicate transactions; two genuine
  same-key purchases both survive.
- **SC-004**: Existing debit-side reports, budgets and insights are byte-for-byte
  unchanged by the presence of credit rows in the database.
- **SC-005**: A PDF that is not a supported fatura is rejected, never parsed as one.

## Assumptions

- Only Bradesco and Inter faturas are supported, matching the real PDFs collected on
  2026-08-30.
- Fatura PDFs are provided manually by the user (downloaded from the bank app).
- `fatura_ref` follows the **due date's** month (the month the fatura is paid), not
  the user's closing-month filename convention.
- The full installments feature (linking `Parcela k/n` rows across faturas) stays
  deferred — the markers are parsed and carried, not modeled as installment plans.
- Categorization of credit rows and their appearance in the report are the follow-up
  below; this feature stops at persistence.

---

## Follow-up: report integration (the human will do this)

`nodes/report.py` and `nodes/insights.py` are being rewritten in parallel (feature
B). This feature deliberately does **not** touch them. When the report is wired for
the dual stream it must:

1. **Keep the credit stream separate.** Read credit purchases via
   `repository.list_credit_transactions_by_month(conn, month_ref)` (or
   `list_transactions_by_month(conn, month_ref, instrument=None)` and split on
   `instrument`). Present them as their own section — "Card purchases this month, by
   category" — with their own subtotal.
2. **Exclude credit purchases from the headline totals.** `total_income`,
   `total_expense`, `net_balance` and the main `category_breakdown` stay
   debit-only (that's the current default of `list_transactions_by_month`). The card
   spend must never be double-counted alongside the `Cartão de crédito` debit
   payment line.
3. **Link `fatura_ref` on the debit payment line.** When a debit transaction is
   confirmed as category `Cartão de crédito` (whatever that category ends up named
   after the taxonomy reorg), set its `fatura_ref` to the `YYYY-MM` of that debit
   line's own month (the fatura is paid in the month its line lands). This is the
   only place the debit side writes `fatura_ref`. A `repository` helper
   (`set_fatura_ref(dedup_hash, fatura_ref)` or an extension of
   `update_transaction_category`) needs adding.
4. **Reconciliation view.** For each `fatura_ref` present in the month, show
   `sum(list_credit_transactions_by_fatura_ref(conn, fatura_ref))` vs. the debit
   `Cartão de crédito` line amount for that `fatura_ref`, and the delta (expected to
   be fatura interest / annuity / IOF). Flag a delta that isn't plausibly
   fee-shaped.
5. **Open question — `budget_check`.** Decide whether `budget_check` should count
   credit purchases by **purchase month** against category goals (so a category's
   goal covers card + debit spend in that category), or continue to see only the
   debit stream (card spend implicitly budgeted via a single `Cartão de crédito`
   goal). The model in this spec (credit excluded from the headline total) argues for
   the latter as the default; counting by purchase month is the more useful view but
   needs a deliberate call on double-counting against the `Cartão de crédito` goal.
6. **Categorization.** Credit rows currently land uncategorized and are invisible to
   `categorize` / `human_review` (which read the debit-only default). Wiring them in
   means passing `instrument=None` (or a credit pass) in `nodes/categorize.py` and
   `repository.list_pending_review`, and confirming the review loop and
   `merchant_memory` behave for credit rows.
