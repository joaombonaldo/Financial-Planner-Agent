# Feature Specification: Dual-stream report, credit-row categorization, fatura reconciliation

**Feature Branch**: `011-taxonomy-reimbursement-credit-card` (continued — no new branch cut)

**Created**: 2026-09-12

**Status**: Implemented

**Input**: The follow-up left open by specs/013-credit-card-stream §"Follow-up:
report integration": credit-card purchases (feature 013) were ingested and stored
(`instrument='credit'`) but never categorized, never shown in any report, and never
reconciled against the debit-side fatura payment. This feature closes that gap.

## Problem

After feature 013, credit-card purchases parsed from a fatura PDF sat in the
database uncategorized and invisible: `categorize`/`human_review`/`update_memory`
all read the debit-only default (`list_transactions_by_month(..., instrument=
Instrument.DEBIT)`), so a credit row's `category` stayed `NULL` forever, and no
report surfaced it. Feature 013 had no payoff without this feature.

## Decisions

One open question from specs/013 needed a call before implementing, made by the
user on 2026-09-12: **`budget_check` stays debit-only.** A category's goal covers
debit spend only; card spend is budgeted via one `Cartão de crédito` goal (the bill
amount). Counting credit purchases by purchase month against a category's goal too
was rejected — it would double-count the same money against both that category's
goal and the `Cartão de crédito` goal.

## What changed

1. **`categorize` processes both streams.** Transfer detection still runs on the
   debit stream only (a card purchase can never be an internal transfer between the
   user's own accounts). Merchant-memory lookup and LLM categorization now run on
   credit transactions too — any category can occur on either instrument (BRD
   §5.3.1). Refactored the shared memory/LLM logic into `_categorize_one()` to avoid
   duplicating it between the two loops.

2. **`update_memory` reads both streams** (`instrument=None`) — a confirmed
   card-purchase merchant is remembered in `merchant_memory` exactly like a debit
   one. `human_review`/`list_pending_review` needed no change — they were already
   instrument-agnostic; only `categorize` populating a category for credit rows was
   missing.

3. **`fatura_ref` auto-link.** `db/repository.py:update_transaction_category` now
   sets `fatura_ref = month_ref` on a transaction whenever it's confirmed with
   category `Cartão de crédito` (`categorization.taxonomy.CREDIT_CARD_CATEGORY`,
   new constant) **and** `instrument = 'debit'`. This is the only place the debit
   side writes `fatura_ref`; a credit row's `fatura_ref` (set at parse time by
   feature 013) is never touched here. Since a fatura's credit purchases already
   carry `fatura_ref = YYYY-MM` of their fatura's due date, and the debit payment
   line lands in the debit extract in that same due month, the two sides end up
   with equal `fatura_ref` values — the join key for reconciliation.

4. **Dual-stream report** (`nodes/report.py`). `generate_report` now also returns
   (via a new `DualStreamReport(ReimbursementReport)`):
   - `credit_category_breakdown` / `credit_total` — this month's **confirmed**
     card purchases (`confidence='high'`), grouped by category, by **purchase
     month**. Informational only — never folded into `total_income`,
     `total_expense`, `net_balance`, or the debit `category_breakdown`.
   - `fatura_reconciliations` (`FaturaReconciliation` per entry) — for every
     confirmed `Cartão de crédito` debit line this month, the sum of the fatura's
     actual purchases (`repository.list_credit_transactions_by_fatura_ref`) vs. the
     line's own amount, and the delta. Purchases are summed regardless of review
     status (a reconciliation check on real money, not a categorization check);
     income-type credit rows (refunds/payments) net *against* the purchase total,
     matching how a card issuer computes the amount due.
   - Reimbursement netting (feature 012) is unaffected — reimbursements are a
     debit/PIX-only concept, unrelated to the credit stream.

5. **`generate_insights`** gets the same credit breakdown as extra prompt context,
   explicitly labeled "not part of the totals above" so the LLM doesn't add it into
   the month's total spend.

6. **`graph.py`/`interface/cli.py`** propagate and print the new fields: a "Compras
   no cartão de crédito" section with a total, and one reconciliation line per
   fatura (`OK` when the delta is ~0, otherwise the delta amount).

7. **`nodes/review.py`** now includes `instrument` in the interrupt payload; the CLI
   tags a prompt `[cartão de crédito]` when reviewing a credit-stream item, so the
   reviewer knows which stream they're looking at.

## Out of scope / unchanged

- `budget_check` — debit-only, per the decision above; no code change was actually
  needed (already the default), only a clarifying comment.
- Installments (BRD §5.3, deferred to Phase 3 — unrelated to this feature).
- Any UI — CLI-only, same as the rest of Phase 1.

## Test coverage added

`backend/tests/test_categorize.py`: credit rows categorized via memory and via LLM;
a credit row is never treated as a transfer candidate; confirming a debit row as
`Cartão de crédito` sets `fatura_ref`; a credit row's parse-time `fatura_ref` is
never overwritten by that same rule.

`backend/tests/test_memory.py`: a confirmed credit-card merchant is written to
`merchant_memory`.

`backend/tests/test_report.py`: credit purchases excluded from headline totals;
`credit_category_breakdown`/`credit_total` computed correctly and skip
not-yet-reviewed rows; fatura reconciliation matches an exact case and flags a fee
delta; no `Cartão de crédito` line this month means no reconciliation entries.

Full suite: 98 → 110 passed, no regressions, debit-only default behavior for
`budget_check`/`generate_report`'s headline totals unchanged.
