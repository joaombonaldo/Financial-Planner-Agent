# Feature Specification: Generate Insights

**Feature Branch**: `006-generate-insights`

**Created**: 2026-08-24

**Status**: Draft

**Input**: User description: "Generate insights (the `generate_insights` node of the graph): produces a
natural-language summary, in Portuguese, of where the user's money went this month, grounded in the month's
actual category spend and the budget comparison already computed by budget_check, including a comparison against
the previous month's spending when available. Uses an LLM through the existing swappable abstraction. Marked
'optional' in the BRD, meaning a failure here must never block the rest of the month's processing. Consumes the
output of features 001-005."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Get a plain-language summary of where the money went (Priority: P1)

As a user, I want a short, natural-language summary of my spending for the month, grounded in my real
transactions and budget comparison, so I can understand my financial situation without manually reading every
categorized transaction.

**Why this priority**: It's the entire point of this feature — without a grounded summary, the user is left to
manually piece together the story from raw category totals, which is exactly what this node exists to avoid.

**Independent Test**: Can be tested by seeding a month's categorized transactions and budget comparison, running
insight generation with a mocked LLM, and verifying the summary text is produced and the LLM was given the real
category spend and budget data as context (not invented data).

**Acceptance Scenarios**:

1. **Given** a fully processed month with categorized transactions and a budget comparison, **When** insight
   generation runs, **Then** a natural-language summary in Portuguese is produced, and the context given to the
   LLM includes that month's actual per-category spend and the budget comparison.
2. **Given** a category that's over budget this month, **When** insight generation runs, **Then** the LLM's
   context includes that specific over-budget fact, so the summary is able to reference it.

---

### User Story 2 - See how spending changed versus last month (Priority: P2)

As a user, I want the summary to reflect how my spending this month compares to last month, so I notice new or
growing spending patterns as they emerge, not just a snapshot with no history.

**Why this priority**: A single month's numbers alone tell you what happened, not whether it's normal or a new
trend — the comparison is what turns raw totals into something actionable.

**Independent Test**: Can be tested by seeding two consecutive months of categorized transactions with a
noticeable difference in one category, running insight generation for the second month, and verifying the
previous month's per-category totals were included in the LLM's context.

**Acceptance Scenarios**:

1. **Given** categorized transactions exist for both the current month and the immediately preceding month,
   **When** insight generation runs for the current month, **Then** the LLM's context includes a category-by-
   category comparison between the two months.
2. **Given** no data exists for the immediately preceding month (e.g. this is the first month ever processed),
   **When** insight generation runs, **Then** a summary is still produced for the current month alone, without
   referencing a comparison that doesn't exist.

---

### User Story 3 - Never let an LLM failure block the month's processing (Priority: P2)

As a user, I want the rest of my month's processing to complete even if generating insights fails (e.g. Ollama
isn't running), so a transient LLM problem never costs me my budget results or categorized data.

**Why this priority**: The BRD explicitly marks this node "optional" — insights are commentary on top of data
that's already fully valid and useful on its own; losing the whole run over commentary would be a
disproportionate failure mode.

**Independent Test**: Can be tested by forcing the LLM call to raise an error and verifying the overall process
still completes, with a clear, recorded reason for the missing summary — not a silent, empty result
indistinguishable from "nothing to say."

**Acceptance Scenarios**:

1. **Given** the LLM call fails (e.g. connection error), **When** insight generation runs, **Then** the failure
   is recorded with a clear reason, and processing continues rather than crashing.
2. **Given** the LLM returns an empty or malformed response, **When** insight generation runs, **Then** this is
   treated the same as a failure (recorded, not silently accepted as a valid summary).

### Edge Cases

- First month ever processed (no prior-month data at all): summary is generated for the current month alone, per
  User Story 2's second acceptance scenario.
- A category present in the prior month's totals but absent this month (or vice versa): the comparison must
  handle this without crashing — a category with no data in one of the two months is treated as zero for that
  month.
- The LLM is unreachable, times out, or returns garbage: treated as a recorded failure, never a crash and never a
  silently-accepted bad summary (User Story 3).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST generate a natural-language summary of the processed month's spending, using an
  LLM.
- **FR-002**: The summary MUST be grounded in the month's real categorized transaction data — never data invented
  or assumed by the LLM.
- **FR-003**: The context given to the LLM MUST include actual spend per category for the current month and the
  budget comparison already computed by `budget_check`.
- **FR-004**: When categorized data exists for the immediately preceding month, the context given to the LLM MUST
  include a category-by-category comparison between the current and prior month.
- **FR-005**: When no prior-month data exists, the system MUST still generate a summary for the current month
  alone, without fabricating or claiming a comparison that doesn't exist.
- **FR-006**: If insight generation fails for any reason (LLM unavailable, error, empty/malformed response), the
  system MUST NOT fail the overall month's processing — it MUST record a clear, explicit failure reason and allow
  processing to continue.
- **FR-007**: This feature MUST NOT modify any transaction, budget goal, or merchant memory entry — it's a
  read-only, generative step.
- **FR-008**: The generated summary MUST be written in Portuguese, since it's user-facing application content.
- **FR-009**: The LLM MUST be accessed only through the existing swappable abstraction — this feature MUST NOT
  make a direct provider call of its own.

### Key Entities *(include if feature involves data)*

- **Month spend summary** (computed, not persisted): per-category actual spend for one month, reused as the
  building block for both the current month's context and the prior-month comparison.
- **Insights result**: either the generated summary text, or a recorded failure reason when generation didn't
  succeed. Not persisted — it's this feature's output, meant to feed the not-yet-built report node.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every fully processed month produces a natural-language summary in Portuguese, grounded in that
  month's real category spend and budget comparison.
- **SC-002**: When prior-month data exists, generation is given that comparison as context; when it doesn't,
  generation still succeeds without a fabricated comparison.
- **SC-003**: An LLM failure during insight generation never crashes or blocks the overall month's processing.
- **SC-004**: No transaction, budget goal, or merchant memory entry is ever modified by this feature.

## Assumptions

- "Previous month" means the calendar month immediately before the one being processed (e.g. `2026-07` for
  `2026-08`), not an arbitrary lookback window — matches the monthly cadence already established by the rest of
  the pipeline.
- This feature reuses the same category-spend calculation logic already built for `budget_check` (actual expense
  per category, transfers and income excluded, `confidence = high` only) rather than introducing a second way of
  computing the same numbers.
- The generated summary is free-form text, not a structured object with individual claims the system can
  independently verify — the LLM is trusted to describe the numbers it's given accurately, the same trust model
  already accepted for categorization in feature 002.
- No mechanism exists yet to store past months' generated summaries for later reference — like the budget
  comparison, this is computed fresh each run and handed to whichever node consumes it next.
