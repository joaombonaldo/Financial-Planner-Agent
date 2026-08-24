# Feature Specification: Transaction Categorization

**Feature Branch**: `002-categorize-transacoes`

**Created**: 2026-08-23

**Status**: Draft

**Input**: User description: "Automatic transaction categorization (the graph's `categorize` node): uses memory of
already-confirmed merchants to categorize with high confidence without an LLM; calls the LLM only for new or
ambiguous cases, returning categorical confidence (high/medium/low); flags candidates for transfers between the
user's own accounts without automatically excluding them from the total. Consumes the output of the ingestion
feature (001) and prepares the result for human review (a future feature)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Automatically categorize already-known merchants (Priority: P1)

As a user, I want transactions from merchants I've already categorized in previous months to be categorized
automatically with high confidence, without calling the LLM or requiring my review, so I don't repeat the same
manual work every month.

**Why this priority**: It's what makes the monthly process sustainable — without it, every transaction would
require human review or an LLM call, every month, forever.

**Independent Test**: Can be tested by providing a transaction whose merchant already has a confirmed mapping in
memory and verifying it gets the correct category with `confidence = high`, with no LLM call.

**Acceptance Scenarios**:

1. **Given** a transaction whose description matches a merchant already confirmed in memory (e.g. "Uber" →
   Transporte/Uber-99), **When** the transaction is categorized, **Then** it gets the mapped category and
   subcategory, with `confidence = high`, with no LLM call.
2. **Given** a month with no merchant confirmed in memory yet (the system's first run), **When** transactions are
   categorized, **Then** no transaction gets `confidence = high` just for being in memory — all go through the
   LLM categorization flow (User Story 2).

---

### User Story 2 - Categorize new or ambiguous transactions via LLM (Priority: P1)

As a user, I want transactions from merchants I've never seen before to be automatically categorized by an LLM,
using the defined category taxonomy, with an explicit confidence level, so I know which ones deserve my attention
during review.

**Why this priority**: Together with User Story 1, it's what delivers this feature's core value — without it,
every new transaction would end up with no category at all.

**Independent Test**: Can be tested by providing a transaction whose merchant isn't in memory and verifying the
LLM is called and returns a valid category from the taxonomy with a categorical confidence level.

**Acceptance Scenarios**:

1. **Given** a transaction whose merchant isn't in memory, **When** it's categorized, **Then** the LLM is called
   and returns a category/subcategory belonging to the configured taxonomy, with `confidence` equal to `medium` or
   `low` (never `high` — high confidence only comes from an already-known merchant, see User Story 1).
2. **Given** an LLM response that doesn't match any category in the configured taxonomy, **When** the result is
   processed, **Then** the transaction gets the fallback category "Outros" with `confidence = low`, instead of
   being left without a category or breaking processing.
3. **Given** a transaction with a generic description insufficient for reliable categorization (e.g. a Bradesco
   `Histórico` that never names the merchant), **When** it's categorized, **Then** it gets `confidence = medium`
   or `low`, never `high`.

---

### User Story 3 - Flag candidates for transfers between the user's own accounts (Priority: P2)

As a user, I want transactions that look like transfers between my own accounts (Bradesco ↔ Inter) to be flagged
as candidates, without being automatically excluded from the expense/income total, so I can confirm before any
exclusion happens.

**Why this priority**: It avoids both the error of counting an internal transfer as a real expense and the bigger
error of excluding something from the total that wasn't actually a transfer — that's why the final decision is
left to human review, not to this feature.

**Independent Test**: Can be tested by providing two mirrored transactions (same amount, different accounts,
dates within a ±2-day window, a transfer pattern in the description) and verifying both get flagged as candidates
for "Transferência interna", staying in the total until later confirmation.

**Acceptance Scenarios**:

1. **Given** two transactions with a mirrored amount (one outgoing in one account, one incoming in another
   account of the same user) within up to a 2-day window, and with a transfer pattern in the description
   (PIX/TED/DOC), **When** categorization runs, **Then** both are suggested with category "Transferência interna",
   but stay counted in the total until confirmed by human review (out of scope for this feature).
2. **Given** a transaction with a transfer pattern in the description but no matching mirrored amount in another
   account within the ±2-day window, **When** categorization runs, **Then** it isn't flagged as a transfer
   candidate — it follows the normal categorization flow (User Story 1 or 2).

### Edge Cases

- Empty merchant memory (first use of the system): all transactions go through the LLM flow (User Story 2), none
  gets `high` for lack of history.
- A transaction description with no merchant name (e.g. Bradesco's generic "PIX ENVIADO"/"PIX RECEBIDO"): doesn't
  block categorization, but limits the chance of a memory match and tends to result in lower confidence.
- An LLM response outside the known taxonomy: falls into "Outros" with `confidence = low`, never breaks
  processing.
- Two mirrored-amount transactions that coincide by chance (not actually a transfer): still get flagged as
  candidates — the final decision to accept or reject the suggestion belongs to human review, not to this
  feature.
- A credit-card installment transaction: gets the purchase's normal category (e.g. "Vestuário"); the installment
  logic itself (the `installments` table) is a future feature's responsibility, not this one's.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: For each transaction, the system MUST check whether the merchant (derived from the description)
  already has a confirmed mapping in memory before considering any other categorization source.
- **FR-002**: When the merchant is already confirmed in memory, the system MUST assign the mapped category and
  subcategory with `confidence = high`, without calling the LLM.
- **FR-003**: When the merchant isn't confirmed in memory, the system MUST call the LLM to suggest a category and
  subcategory from the configured taxonomy.
- **FR-004**: The system MUST keep the category/subcategory taxonomy as extensible configuration (not hardcoded),
  including the "Outros" and "Transferência interna" categories described in the BRD's Appendix A.
- **FR-005**: When the LLM's response doesn't match any category in the configured taxonomy, the system MUST
  assign the fallback category "Outros" with `confidence = low`, instead of failing or leaving the transaction
  without a category.
- **FR-006**: `confidence = high` MUST only occur via an already-confirmed merchant in memory (FR-002); every
  LLM-driven categorization MUST result in `confidence` equal to `medium` or `low`.
- **FR-007**: The system MUST identify transactions that are candidates for transfers between the user's own
  accounts: a transfer pattern in the description (PIX/TED/DOC) combined with a mirrored amount in another of the
  user's accounts within a window of up to 2 days.
- **FR-008**: Transfer-candidate transactions MUST be suggested with category "Transferência interna", but MUST
  NOT be excluded from the expense/income total nor automatically confirmed by this feature — final confirmation
  is human review's responsibility (out of scope for this feature).
- **FR-009**: Categorization confidence MUST always be represented categorically (`high`/`medium`/`low`), never
  as a numeric value.
- **FR-010**: The system MUST persist the category, subcategory, and confidence assigned to each transaction,
  ready for consumption by the human review step.
- **FR-011**: This feature MUST NOT write new confirmations into merchant memory — that's a future feature's
  responsibility (`update_memory`), triggered after human review.

### Key Entities *(include if feature involves data)*

- **Merchant mapping**: an association between a merchant (derived from the transaction description) and a
  category/subcategory already confirmed in previous runs. This feature only reads this mapping; writing new
  confirmations is a future feature's responsibility.
- **Category taxonomy**: configurable list of categories and subcategories (BRD Appendix A), including the
  fallbacks "Outros" (low confidence) and "Transferência interna" (transfer candidates).
- **Transaction (extended)**: the normalized transaction produced by the ingestion feature (001), now with
  `category`, `subcategory`, and `confidence` filled in by this feature.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Transactions from merchants already confirmed in previous months are categorized automatically
  with high confidence, requiring no user action nor LLM call.
- **SC-002**: 100% of processed transactions end up with a valid taxonomy category — no transaction is left
  without a category, even in cases of an unexpected LLM response.
- **SC-003**: 100% of transfer-candidate transactions are flagged for confirmation, and none is excluded from the
  expense/income total by this feature.
- **SC-004**: 100% of categorized transactions have a confidence value among `high`/`medium`/`low` — no numeric
  or missing value.
- **SC-005**: No transaction gets `confidence = high` without having come from an already-confirmed merchant in
  memory.

## Assumptions

- A transaction's merchant is derived from the normalized text of `description_raw`; more sophisticated entity
  resolution (fuzzy matching between name variations of the same merchant) isn't needed in this first version —
  it can be refined later, based on real usage.
- Bradesco transactions with a generic description (e.g. "PIX ENVIADO"/"PIX RECEBIDO", with no counterparty name)
  will rarely have a direct merchant-memory match — they tend to go through the LLM flow with lower confidence, as
  already identified in the BRD (section 6.3).
- Transfer detection (FR-007) only considers transactions already imported into the system for the user's known
  accounts (Bradesco and Inter) within the same monthly processing batch — it doesn't search beyond the ±2-day
  window nor in accounts other than the ones already registered.
- The LLM used is local (Ollama + Qwen2.5, per the BRD's stack), but this spec is provider-agnostic — the concrete
  choice and how to swap it are left to the technical plan.
- Credit-card installments get the purchase's normal category from this feature; the specific installment logic
  (the `installments` table, tracking paid/remaining installments) is a future feature's responsibility.
