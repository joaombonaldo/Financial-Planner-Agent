# Decision: defer credit-card installment tracking to Phase 3

**Branch**: `main` (no feature branch — scope decision, not an implementation)
**Date**: 2026-08-30
**Status**: Accepted
**Related**: [docs/brd-financial-planner-agent.md](../brd-financial-planner-agent.md) §5.3, §6.2, §10

## Problem

The BRD describes installment (`parcelamento`) tracking in several places:

- §1 overview: "Tracks credit card installments, transfers between the user's own
  accounts, income and expenses".
- §5.3: each installment shows in its category's monthly spend, plus a dedicated
  `installments` table (total amount, number of installments, paid/remaining)
  queryable as a separate view.
- §6.2: a full `installments` table schema (id, description, total_amount,
  num_installments, installment_amount, first_charge_date, account).

None of this is built. The current state is a single nullable `installment_id`
column on the transaction row:

- `backend/src/financial_planner/db/schema.sql`: `installment_id INTEGER  -- future feature: installments`
- `backend/src/financial_planner/state.py`: `installment_id: int | None = None`
- `backend/src/financial_planner/db/repository.py`: the column is read/written but
  never populated with a real value.

There is no `installments` table, no installment-detection logic, no dedicated
view, and no graph node that touches installments. The BRD's §10 roadmap does not
explicitly assign installments to a phase, leaving its Phase-1 status open.

## Decision

**Installment tracking is out of scope for Phase 1 and is deferred to Phase 3**,
alongside the other "beyond financial planning" tracking work (investment
tracking is already Phase 3 per §10).

The Phase 1 MVP is considered complete without it: all seven graph nodes are
implemented and wired, the four §10 acceptance criteria were validated against two
real months (see `specs/007-generate-report/tasks.md`), and installments are not
required to satisfy any of those criteria.

## Rationale

1. **Not on the MVP acceptance path.** §10's criteria are: process a real month
   from both banks without error; review/correction works via CLI; the final
   report matches a manually verified statement sum; insights reflect the month.
   An individual installment charge already flows through the pipeline as an
   ordinary transaction in its category's spend — which is exactly what §5.3's
   first bullet asks for. Only the *aggregate view* (the `installments` table and
   its paid/remaining rollup) is missing, and nothing in the acceptance criteria
   depends on that view.

2. **It is a feature, not a fix.** Doing it properly means: a new `installments`
   table + migration, detection logic (parsing "PARC 03/12"-style markers out of
   `Histórico`/`Descrição`, grouping charges into a plan, inferring
   `num_installments` / `installment_amount` / `first_charge_date`), a repository
   view, and a way to surface it (CLI output now, dashboard in Phase 2). That is a
   full spec-kit feature cycle (spec → plan → tasks → implement), comparable in
   size to `002-categorize-transacoes`, not a cleanup task.

3. **Bank-format uncertainty.** Per BRD §6.3, the real exports were only confirmed
   for one month. Bradesco's `Histórico` "never includes the counterparty's name"
   and Inter splits type/description across two columns with `Descrição` sometimes
   blank. Whether installment markers appear reliably, and in what exact form, is
   not yet established from real data. Building detection now risks encoding
   assumptions that a second month of real exports would invalidate — the same
   lesson already recorded in the dedup and bank-detection decision records.

4. **Phase 3 already owns adjacent work.** Investment tracking is Phase 3. The
   `installments` view is naturally part of the same "richer financial picture"
   milestone and benefits from being designed together with it and with the
   Phase 2 dashboard that would display it.

## Scope kept in Phase 1

- The `installment_id` nullable column stays on the transaction schema as-is. It
  is a harmless forward-compatible stub (always `NULL` today) and removing it
  would be churn for no benefit.
- Individual installment charges continue to be categorized and counted in their
  category's monthly spend like any other transaction. No behavior change.

## What Phase 3 picks up

- Create the `installments` table per BRD §6.2.
- Installment-plan detection: recognize installment markers in the raw
  description, group related monthly charges, populate `installment_id` on the
  member transactions, and derive the plan-level fields.
- A repository view exposing per-plan paid / remaining status.
- Surface the view (CLI and/or the Phase 2 dashboard).
- Revisit against at least a second month of real exports from both banks before
  finalizing the detection heuristics.

## Consequences / things to watch

- The BRD's §1 overview still lists installment tracking as a headline capability.
  Readers should treat §10 + this record as the authority on phasing: it is a
  planned capability, not a Phase 1 one.
- Until Phase 3, there is no way to answer "how many installments are left on
  purchase X" from the system — that stays a manual check against the card
  statement. Acceptable for the single-user monthly cadence.
- If a future need forces installments earlier (e.g. they turn out to dominate
  monthly spend and distort budget checks), reopen this decision — the schema
  stub means the transaction table needs no migration to start populating it.
