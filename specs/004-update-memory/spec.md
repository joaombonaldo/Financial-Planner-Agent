# Feature Specification: Merchant Memory Update

**Feature Branch**: `004-update-memory`

**Created**: 2026-08-23

**Status**: Draft

**Input**: User description: "Merchant memory update (the `update_memory` node of the graph): persists confirmed
categorizations into the merchant → category mapping so future months auto-categorize known merchants without
LLM calls or human review. Consumes the output of human review (003); does not use an LLM. Closes the loop that
feature 002 explicitly deferred ('writing new confirmations is a future feature's responsibility')."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Remember confirmed categorizations for next month (Priority: P1)

As a user, I want every category I confirm (directly or through review) this month to be remembered, so that next
month the same merchant is categorized automatically with high confidence, without me reviewing it again.

**Why this priority**: It's the entire point of this feature and the reason merchant memory exists at all — without
it, every month would require re-deciding every merchant from scratch, no matter how many times it was already
confirmed.

**Independent Test**: Can be tested by processing a month where a transaction ends up with a confirmed category,
then verifying that a transaction from the same merchant in a later month is automatically categorized with
`confidence = high`, without calling the LLM.

**Acceptance Scenarios**:

1. **Given** a transaction that ends this month's processing with `confidence = high` and a real category (not
   "Internal Transfer"), **When** the merchant memory update runs, **Then** the merchant → category mapping is
   persisted, ready to be reused by future categorization runs.
2. **Given** a merchant already has a mapping in memory, and this month a transaction from that same merchant is
   confirmed with a **different** category than what's stored, **When** the update runs, **Then** the stored
   mapping is overwritten with the newest confirmed category.
3. **Given** a month with no transactions at all, **When** the update runs, **Then** nothing is written and no
   error occurs.

---

### User Story 2 - Never remember a transfer as a merchant category (Priority: P1)

As a user, I want confirmed "Internal Transfer" transactions to never be written into merchant memory, so that a
generic description (like "PIX SENT") never gets permanently associated with "Internal Transfer" and wrongly
auto-categorizes a future non-transfer transaction that happens to share that same generic text.

**Why this priority**: Transfer detection is structural (pattern + mirrored amount across accounts), not a
per-merchant fact — memorizing it as one would silently break the transfer-review safeguard built in feature 002
for exactly the generic descriptions (like Bradesco's "PIX SENT"/"PIX RECEIVED") that most need it.

**Independent Test**: Can be tested by confirming a transaction as "Internal Transfer" and verifying that no
merchant memory entry is created or updated for it.

**Acceptance Scenarios**:

1. **Given** a transaction confirmed with `category = "Internal Transfer"`, **When** the merchant memory update
   runs, **Then** no entry is written to merchant memory for that transaction's merchant — existing entries for
   that same merchant (if any, from a prior non-transfer confirmation) are left untouched.

### Edge Cases

- Two transactions from the same merchant, confirmed with different categories in the same month (e.g. the user
  manually assigns different subcategories to two purchases from the same store): the later one processed wins;
  this is an accepted ambiguity, not an error condition.
- A transaction somehow still has `confidence` other than `high` when this node runs (shouldn't happen after
  human review, per feature 003): it MUST be skipped, not written to memory under a partial/unconfirmed state.
- Running the update twice for the same month: MUST NOT create duplicate entries nor fail — the second run is a
  no-op if nothing changed since the first.
- A merchant memory entry already exists and this month's confirmation matches it exactly: the update is a
  harmless no-op rewrite (same value written again).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST persist a merchant → category/subcategory mapping into merchant memory for every
  transaction in the processed month with `confidence = high` and `category` different from "Internal Transfer".
- **FR-002**: When a merchant already has a mapping in memory, the system MUST overwrite it with the newest
  confirmed category/subcategory — the latest confirmation always wins.
- **FR-003**: Transactions with `category = "Internal Transfer"` MUST NOT be written to merchant memory under any
  circumstance, regardless of their confidence level.
- **FR-004**: This feature MUST NOT modify any transaction's `category`, `subcategory`, or `confidence` — it only
  reads already-decided transactions and writes to merchant memory.
- **FR-005**: Running this feature more than once for the same month MUST be idempotent — no duplicate entries, no
  error, no change beyond what the current state of the month's transactions already implies.
- **FR-006**: The system MUST skip any transaction whose `confidence` is not `high` — never write a partial or
  unconfirmed category to merchant memory.

### Key Entities *(include if feature involves data)*

- **Merchant memory** (from feature 002, previously read-only for this project): now also written by this
  feature. A mapping from a normalized merchant key to a confirmed category/subcategory.
- **Transaction** (from features 001-003): read-only input to this feature — its `category`, `subcategory`, and
  `confidence` are the source of truth for what gets written to merchant memory.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A merchant confirmed in one month is automatically categorized with `confidence = high` — no LLM
  call, no human review — the next time a transaction from that same merchant is processed.
- **SC-002**: No merchant memory entry ever has "Internal Transfer" as its stored category.
- **SC-003**: Running the merchant memory update twice on the same month never creates duplicate entries nor
  raises an error.
- **SC-004**: No transaction's `category`, `subcategory`, or `confidence` is altered by this feature.

## Assumptions

- There's no separate "confirmed by a human" marker on a transaction — `confidence = high` means the same thing
  whether it came from a merchant-memory match (feature 002) or from an explicit human decision (feature 003).
  This feature treats every `confidence = high`, non-transfer transaction in the processed month as worth
  remembering, including ones that were already `high` via a prior memory match — rewriting an already-correct
  mapping is a harmless no-op, and this avoids introducing a new field just to track provenance.
- The merchant key definition matches feature 002: normalized (trimmed, lowercased) `description_raw`.
- There's no mechanism yet to prune or manually correct a stale/wrong merchant memory entry outside of
  reconfirming that merchant with a new category in a later month — deliberately out of scope; a dedicated
  "forget this merchant" capability can be a future feature if it turns out to be needed in practice.
