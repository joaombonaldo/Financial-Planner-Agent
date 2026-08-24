# Feature Specification: Human Review of Transactions

**Feature Branch**: `003-human-review`

**Created**: 2026-08-23

**Status**: Draft

**Input**: User description: "Human review (the graph's `human_review` node): interrupts processing whenever
there are medium/low confidence transactions or transfer candidates between the user's own accounts, presents
each one for the user to confirm or correct, and persists the decision immediately — without losing progress if
the session is interrupted midway. Consumes the output of the categorization feature (002); doesn't use an LLM.
Includes assembling the graph (a LangGraph `StateGraph` with `interrupt()`) that wires
`detect_and_parse` → `categorize` → `human_review`, since this is the first node whose reason to exist depends on
running inside a compiled graph."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Review and correct medium/low confidence transactions (Priority: P1)

As a user, I want to see every transaction the system categorized with medium or low confidence, with the
suggestion already filled in, and be able to accept that suggestion or correct it, to make sure my financial data
is right before any report gets generated.

**Why this priority**: It's this node's reason to exist — without it, low-confidence transactions would stay
permanently wrong, and the project's core promise (mandatory human review for sensitive decisions) wouldn't be
fulfilled.

**Independent Test**: Can be tested by providing a month with medium/low confidence transactions and simulating
user responses (accept / correct), verifying each transaction ends up with the right category and
`confidence = high`.

**Acceptance Scenarios**:

1. **Given** a transaction with `confidence = medium` and a suggested category, **When** the user accepts the
   suggestion, **Then** the transaction keeps the suggested category/subcategory and gets `confidence = high`.
2. **Given** a transaction with `confidence = low`, **When** the user provides a category different from the
   suggestion, **Then** the transaction gets the category/subcategory the user provided, with `confidence = high`.
3. **Given** a month where every transaction already has `confidence = high` (nothing pending), **When**
   processing reaches this node, **Then** the graph proceeds automatically, without interrupting for review.

---

### User Story 2 - Confirm or reject transfer candidates (Priority: P1)

As a user, I want to confirm or reject each transaction flagged as a candidate for a transfer between my own
accounts, to control exactly which movements are treated as internal transfers and which are real
expense/income.

**Why this priority**: A transfer suggestion can never turn into an automatic decision (BRD 5.2) — without this
user story, transfer candidates would stay permanently stuck in "suggested" state, never confirmed.

**Independent Test**: Can be tested by providing a transaction with `category = "Transferência interna"`
(suggested by categorization) and simulating both confirmation and rejection, verifying the outcome in each case.

**Acceptance Scenarios**:

1. **Given** a transaction suggested as "Transferência interna", **When** the user confirms, **Then** it keeps
   that category and gets `confidence = high`.
2. **Given** a transaction suggested as "Transferência interna", **When** the user rejects it and provides the
   real category, **Then** it gets the provided category (never staying as "Transferência interna" unconfirmed
   nor ending up with no category), with `confidence = high`.

---

### User Story 3 - Resume an interrupted review without losing progress (Priority: P2)

As a user, I want to be able to interrupt a review session midway (closing the terminal, for instance) and resume
later, without losing decisions I already made nor repeating reviews already done.

**Why this priority**: Reviewing a whole month can have dozens of items — without this guarantee, an accidental
interruption would force redoing everything, which in practice would discourage using the review feature at all.

**Independent Test**: Can be tested by reviewing part of the pending items, simulating an interruption, and
resuming processing — verifying that already-decided items aren't presented again and keep the decision made.

**Acceptance Scenarios**:

1. **Given** a review session with 3 pending items, **When** the user decides the first item and the session is
   interrupted before the second, **Then** the first item keeps the decision made (persisted immediately) upon
   resuming.
2. **Given** a session resumed after an interruption, **When** processing continues, **Then** only the items
   still pending are presented to the user — no already-decided item is asked about again.

### Edge Cases

- No transaction pending review for the month: the node must not interrupt the graph (User Story 1, scenario 3).
- The user provides a category or subcategory outside the configured taxonomy during a correction: the system
  MUST reject the input and ask again, never silently accepting an invalid category.
- Two transactions form a mirrored transfer pair (one suggestion in each account): each is reviewed
  independently — confirming or rejecting one doesn't automatically decide the other.
- Session interrupted with no decision made yet: upon resuming, every originally pending item stays pending, with
  no duplication or loss.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST interrupt processing of the month whenever there's at least one transaction with
  `confidence` other than `high`, or with `category = "Transferência interna"` not yet confirmed.
- **FR-002**: For each pending item, the system MUST present the user with date, description, amount, account,
  and the suggested category/subcategory/confidence before asking for a decision.
- **FR-003**: For items that aren't transfer candidates, the user MUST be able to accept the suggestion or provide
  a different category/subcategory, within the configured taxonomy.
- **FR-004**: For transfer candidates, the user MUST be able to confirm (keeps "Transferência interna") or reject
  and provide the real category — never left undecided.
- **FR-005**: Every transaction decided by the user (accepted or corrected) MUST end up with `confidence = high`,
  reflecting that a human decision is the highest possible confidence source in the system.
- **FR-006**: Each decision MUST be persisted immediately after being made, not only at the end of the whole
  session — an interruption can't cost already-made decisions.
- **FR-007**: When resuming an interrupted session, the system MUST present only the items still pending —
  already-decided items MUST NOT be presented again.
- **FR-008**: When there's no item pending review for the month, the system MUST proceed with processing
  automatically, without interrupting.
- **FR-009**: The system MUST validate any manually provided category/subcategory against the configured
  taxonomy, rejecting and re-asking for invalid entries.
- **FR-010**: This feature MUST NOT write new confirmations into merchant memory — that remains a future
  feature's responsibility (`update_memory`), which consumes this feature's decisions.

### Key Entities *(include if feature involves data)*

- **Pending review item**: not its own entity — it's any transaction (from feature 002) with `confidence` other
  than `high`, or with `category = "Transferência interna"` not yet confirmed by the user.
- **Human decision**: the update of a transaction's `category`/`subcategory`/`confidence`, applied directly onto
  the existing record — there's no separate "decisions" table; the transaction itself is the source of truth for
  whether it was reviewed, since `confidence = high` only happens via confirmed memory (feature 002) or a human
  decision (this feature).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of medium/low confidence transactions, or transfer candidates, in a processed month end review
  with `confidence = high`.
- **SC-002**: Interrupting a review session midway and resuming it later doesn't lose any decision already made.
- **SC-003**: A month where every transaction is already `confidence = high` is processed with no interruption
  for review.
- **SC-004**: No transfer candidate stays with `category = "Transferência interna"` without the user's explicit
  confirmation by the end of the month's review.
- **SC-005**: No category or subcategory outside the configured taxonomy is accepted during a manual correction.

## Assumptions

- A human decision (accept or correct) always results in `confidence = high` — there's no separate fourth
  "human-reviewed" confidence level; the value `high` already communicates "doesn't need further review", whether
  its origin is merchant memory (feature 002) or a human decision (this feature).
- Each transaction is reviewed individually, even when part of a mirrored transfer pair — this version has no
  "review the pair at once" interaction (could be a future refinement).
- The user interaction interface at this stage is the CLI (per the BRD's Phase 1 stack); this feature includes
  only the minimum interaction needed to review a month, not a full CLI with every product command.
- Assembling the graph (`StateGraph`, `interrupt()`, a checkpointer with `thread_id` per month) is treated as a
  technical detail of this feature (goes into the implementation plan), not as a separate feature — it's the
  first time a graph actually needs to exist, since the previous nodes ran as independent functions.
- Persisting a decision "immediately" (FR-006) means writing to the database for each decided item, not waiting
  for the whole review session to end — aligned with using the LangGraph checkpointer to resume exactly where it
  left off.
