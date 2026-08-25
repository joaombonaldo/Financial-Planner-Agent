# Feature Specification: Required Subcategory Selection

**Feature Branch**: `008-required-subcategory`

**Created**: 2026-08-25

**Status**: Draft

**Input**: User description: "Adicionar seleção obrigatória de subcategoria durante a categorização automática
(LLM) e melhorar a experiência de revisão manual (human_review) para subcategorizar gastos durante a execução do
programa. O mecanismo de categoria+subcategoria já existe tecnicamente, mas na prática o LLM frequentemente deixa
a subcategoria vazia mesmo quando a categoria escolhida tem subcategorias válidas na taxonomia, porque o prompt
atual permite isso livremente e a validação sempre aceita subcategoria vazia independente da categoria ter opções
ou não. Também melhorar a UX do human_review, listando as subcategorias válidas da categoria sugerida."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - LLM chooses a subcategory whenever one exists (Priority: P1)

As a user, I want automatic categorization to always fill in a subcategory when the chosen category has
subcategories in the taxonomy (e.g. "Moradia" → "Aluguel/Financiamento"), so I don't end up with a pile of
transactions that only have a broad category and no further detail, forcing me to type the full
"categoria|subcategoria" correction by hand for cases the system could already have gotten right.

**Why this priority**: This is the actual gap the user felt while using the app — the category/subcategory
mechanism already exists end-to-end, but nothing today pushes automatic categorization to actually use it, so in
practice most transactions came back subcategory-less even when a fitting subcategory existed.

**Independent Test**: Can be tested by feeding categorize() a transaction description for a category that has
subcategories in the taxonomy, and verifying the persisted transaction has a non-empty subcategory. Can also be
tested for a category with no subcategories in the taxonomy (e.g. "Outros"), verifying subcategory stays empty as
before.

**Acceptance Scenarios**:

1. **Given** a transaction description with no merchant-memory match, **When** the LLM categorizes it into a
   category that has subcategories in the taxonomy, **Then** the persisted transaction has both category and a
   non-empty subcategory from that category's list.
2. **Given** the same setup, **When** the LLM categorizes it into a category that has no subcategories in the
   taxonomy (e.g. "Outros", "Transferência interna", "Cartão de crédito/Parcelamentos"), **Then** the persisted
   transaction has that category and an empty subcategory, exactly as before this feature.
3. **Given** the LLM returns a category with subcategories but leaves the subcategory empty anyway (ignoring the
   instruction), **When** categorize() processes the response, **Then** the transaction still ends up with
   `confidence` medium/low (as it already does today for any LLM-sourced categorization) so it's caught by human
   review, instead of being silently accepted or discarded into the "Outros" fallback.

---

### User Story 2 - See valid subcategories while reviewing (Priority: P2)

As a user, while reviewing a pending transaction, I want to see the list of valid subcategories for the suggested
category, so I can confirm or correct the subcategory by typing the exact expected name, without having to
memorize or guess the taxonomy from `config/categories.yaml`.

**Why this priority**: Reduces friction and invalid-input round-trips during review (FR-009 of feature 003 already
rejects unknown categories/subcategories and re-asks) — it's a usability improvement on top of an already-working
mechanism, not a functional gap, hence lower priority than User Story 1.

**Independent Test**: Can be tested by triggering a pending review item whose suggested category has subcategories
in the taxonomy, and verifying the presented prompt lists exactly that category's subcategories.

**Acceptance Scenarios**:

1. **Given** a pending review item suggesting a category that has subcategories in the taxonomy, **When** the item
   is presented to the user, **Then** the list of valid subcategories for that category is shown alongside the
   suggestion.
2. **Given** a pending review item suggesting a category with no subcategories in the taxonomy, **When** the item
   is presented, **Then** no subcategory list is shown (nothing to choose from).

---

### Edge Cases

- LLM picks a category that has subcategories but responds with a subcategory name outside that category's list:
  treated the same as today's out-of-taxonomy response — falls back to "Outros"/`low` (existing behavior, no
  change to that safety net).
- LLM picks a category that has subcategories but leaves the subcategory field empty despite the instruction: the
  transaction still keeps the chosen category with an empty subcategory and medium/low confidence, going through
  human review as usual — it is not treated as an invalid response and does not fall back to "Outros" (see User
  Story 1, Acceptance Scenario 3).
- Merchant-memory matches (`confidence = high`) are explicitly out of scope for this feature — they continue to
  skip human review with whatever category/subcategory they carry, unchanged.
- A category's subcategory list is edited in `config/categories.yaml` after some transactions were already
  categorized: no retroactive effect — this feature only changes behavior for transactions categorized from this
  point forward.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: When the LLM categorizer selects a category that has one or more subcategories defined in the
  taxonomy, the system MUST instruct the LLM to also select one of that category's subcategories.
- **FR-002**: When the LLM categorizer selects a category that has no subcategories defined in the taxonomy, the
  system MUST continue allowing an empty subcategory, unchanged from current behavior.
- **FR-003**: The system MUST continue validating the LLM's chosen subcategory against the selected category's
  list in the taxonomy; a subcategory outside that list MUST still fall back to the existing "Outros"/`low`
  behavior (feature 002), unchanged.
- **FR-004**: An LLM response that selects a category with available subcategories but leaves the subcategory
  empty MUST NOT be treated as an invalid/out-of-taxonomy response — it MUST keep the chosen category (with an
  empty subcategory) at medium/low confidence, same as any other LLM-sourced categorization, so it reaches human
  review instead of being discarded into "Outros".
- **FR-005**: This feature MUST NOT change how merchant-memory matches (`confidence = high`) are handled — they
  continue to bypass human review unchanged.
- **FR-006**: When presenting a pending review item, the system MUST show the list of valid subcategories for the
  item's suggested category, when that category has any defined in the taxonomy.
- **FR-007**: When the suggested category has no subcategories in the taxonomy, the system MUST NOT show a
  subcategory list for it.
- **FR-008**: This feature MUST NOT change the accepted input format for a manual review correction
  (`"aceitar"`/`"confirmar"` or `"categoria|subcategoria"`, per feature 003) — only what's shown to the user
  before answering.

### Key Entities *(include if feature involves data)*

- No new entities. This feature only changes how the existing `Transaction.category`/`subcategory` fields
  (feature 002) get populated by the LLM categorizer, and what's displayed (not stored) during human review
  (feature 003).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For transactions categorized by the LLM into a category that has subcategories in the taxonomy, the
  large majority end up with a non-empty subcategory on first pass (measured qualitatively by the user during
  normal monthly use — no numeric target, since this depends on the underlying LLM's behavior, which is
  explicitly out of this feature's control).
- **SC-002**: Transactions categorized into a category with no subcategories in the taxonomy are unaffected —
  their subcategory stays empty, exactly as before this feature.
- **SC-003**: No previously-passing categorization test (feature 002) or review test (feature 003) regresses:
  merchant-memory matches, transfer detection, and the "Outros"/`low` fallback for out-of-taxonomy responses keep
  behaving exactly as before.
- **SC-004**: During review, whenever the suggested category has subcategories, the user can see all of them
  without leaving the terminal prompt or consulting `config/categories.yaml` separately.

## Assumptions

- The LLM cannot be forced at the API level to always emit a subcategory — this feature can only strengthen the
  prompt's instruction, not guarantee compliance. That's why FR-004 exists: an empty subcategory from the LLM,
  even when one was expected, is not an error — it degrades to today's already-existing safety net (human
  review), not to data loss or a hard failure.
- "Has subcategories in the taxonomy" means the category's list in `config/categories.yaml` is non-empty (e.g.
  "Moradia") as opposed to an empty list (e.g. "Outros", "Transferência interna", "Cartão de
  crédito/Parcelamentos", per Appendix A of the BRD).
- This feature only touches the LLM-categorization path and the human-review presentation layer — it doesn't
  change `config/categories.yaml`'s content, the taxonomy schema, the database schema, or the merchant-memory
  path.
- Reviewing/subcategorizing transactions that already reached `confidence = high` via merchant memory, or
  reviewing transactions from already-processed past months, are out of scope for this feature (explicitly
  deferred by the user) — a possible future feature.
