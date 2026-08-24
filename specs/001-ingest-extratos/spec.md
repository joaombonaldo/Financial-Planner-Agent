# Feature Specification: Bank Statement Ingestion

**Feature Branch**: `001-ingest-extratos`

**Created**: 2026-08-23

**Status**: Draft

**Input**: User description: "Ingestion of bank statements (CSV) from Bradesco and Inter, normalizing transactions into a single schema, automatically detecting the source bank, and avoiding duplication on reimport. Corresponds to the `detect_and_parse` node of the graph described in the BRD."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Import a statement from a supported bank (Priority: P1)

As a user, I want to point the system at a CSV statement file exported from Bradesco or Inter and get that month's transactions in a single normalized format, so they're ready for categorization without me having to manually clean up or reformat the file.

**Why this priority**: Without this there's no project — it's the graph's first node, and everything else (categorization, review, budget, insights) depends on normalized, trustworthy transactions.

**Independent Test**: Can be tested in isolation by providing a real (or fixture) statement file from each bank and verifying the output is a list of transactions in the normalized schema, without depending on any other graph node.

**Acceptance Scenarios**:

1. **Given** a Bradesco statement file (UTF-8 with BOM, separate `Crédito (R$)`/`Débito (R$)` columns, metadata on line 1, a duplicated "Últimos Lancamentos" block, and a "Total" footer line), **When** the system processes the file, **Then** only the real transaction lines are converted, in the correct count, and the source bank is identified as Bradesco without manual intervention.
2. **Given** an Inter statement file (UTF-8 without BOM, single signed `Valor` column, 4 metadata lines + a blank line before the header, `Descrição` blank on some rows), **When** the system processes the file, **Then** all transaction lines are converted correctly, using `Histórico` as the description when `Descrição` is blank.
3. **Given** an amount in Brazilian number format (e.g. `1.645,20`) and a date in `DD/MM/YYYY` format, **When** the transaction is normalized, **Then** the numeric amount and the date end up in a single canonical format, identical for both banks.

---

### User Story 2 - Reimport a statement without duplicating transactions (Priority: P2)

As a user, I want to be able to reimport the same file (or a new export that overlaps already-processed days) without transactions showing up duplicated, so I can safely reprocess a month whenever I need to fix something.

**Why this priority**: Bradesco exposes two blocks with potential overlap in the same file, and future re-exports may include already-imported days — without this, reports and budget become silently incorrect.

**Independent Test**: Can be tested by importing the same file twice (or two files with overlapping transactions) and verifying the number of stored transactions doesn't increase on the second import.

**Acceptance Scenarios**:

1. **Given** a file already successfully imported, **When** the same file is imported again, **Then** no new transaction is created.
2. **Given** two transactions with the same date, description, amount, and account, coming from different sections of the same file (e.g. main statement + Bradesco's "Últimos Lancamentos"), **When** the file is processed, **Then** only one transaction is kept.

---

### User Story 3 - Be warned when a file couldn't be processed correctly (Priority: P3)

As a user, I want to know when the parser failed to correctly interpret a statement (unexpected format, unrecognized lines, a balance that doesn't add up), so I don't make financial decisions based on incomplete data without realizing it.

**Why this priority**: It's the safety net for the whole project — wrong data with no warning is worse than no data, but it doesn't block the happy path (P1/P2) from working first.

**Independent Test**: Can be tested by providing a deliberately corrupted/incomplete file and a valid file whose declared balance doesn't match the sum of recognized transactions, verifying both cases produce an explicit warning instead of a silent failure.

**Acceptance Scenarios**:

1. **Given** a file whose layout doesn't match any supported bank, **When** the system tries to process it, **Then** the user gets an explicit error indicating the bank wasn't recognized, without generating partial transactions.
2. **Given** a valid file from a supported bank, **When** the sum of recognized transactions doesn't reconcile with the file's balance column, **Then** the system flags the inconsistency to the user instead of silently proceeding.

### Edge Cases

- Metadata lines at the start of the file (branch/account header on Bradesco; title/account/period/balance on Inter) must not become transactions.
- A repeated column header mid-file (Bradesco's "Últimos Lancamentos" block) must not become a transaction nor break parsing of subsequent lines.
- The "Total" footer line (Bradesco) must not become a transaction.
- Blank lines anywhere in the file must be ignored without interrupting processing.
- A blank `Descrição` on Inter must fall back to `Histórico`, never resulting in a transaction with no description.
- Bradesco's `Histórico` never includes the counterparty's name — this is a source-data limitation, not a parsing error, and must be accepted as such (enriching the description isn't this feature's responsibility).
- A file from an unsupported bank (neither Bradesco nor Inter) must be explicitly rejected.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST automatically detect which bank (Bradesco or Inter) produced a statement file, without requiring manual selection from the user.
- **FR-002**: The system MUST correctly extract transactions from Bradesco exports, including the case of two separate amount columns (credit/debit), the duplicated "Últimos Lancamentos" section, and the "Total" footer.
- **FR-003**: The system MUST correctly extract transactions from Inter exports, including the single signed amount column case and the description fallback (blank `Descrição` → use `Histórico`).
- **FR-004**: The system MUST normalize amounts in Brazilian number format and dates in `DD/MM/YYYY` format into a single canonical format, regardless of source bank.
- **FR-005**: The system MUST identify as a transaction only the lines that represent real movements, ignoring metadata, blank lines, repeated headers, and totaling lines, regardless of where those lines sit in the file.
- **FR-006**: The system MUST compute a deduplication hash per transaction (date + description + amount + account) and not create a new transaction when that hash already exists.
- **FR-007**: The system MUST classify each normalized transaction as `income` or `expense` based on the sign/source column. Classifying as `transfer` (between the user's own accounts) is out of scope for this feature.
- **FR-008**: The system MUST use the statement's running balance column (when present) as a sanity check, comparing the declared balance against the accumulated sum of recognized transactions.
- **FR-009**: The system MUST explicitly report when a file can't be identified as a supported bank, or when the balance check (FR-008) indicates an inconsistency — never fail silently nor generate partial transactions without a warning.
- **FR-010**: The system MUST leave normalized transactions ready for consumption by the categorization step, without filling in category, subcategory, or confidence (a later feature's responsibility).

### Key Entities *(include if feature involves data)*

- **Normalized transaction**: represents a single entry identified in a statement. Attributes relevant to this feature: deduplication hash, date, description (as it came from the bank), source account/bank, type (`income`/`expense`), amount (always positive), reference month. Category, subcategory, confidence, and installment linkage are filled in by later features and are out of scope here.
- **Statement file**: the CSV manually exported by the user from one of the two supported banks' online banking. Each file covers a period (typically a month) and one account.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can import the full monthly statement from either supported bank without needing to manually edit or clean the file beforehand.
- **SC-002**: 100% of real transaction lines present in a sample statement are recognized and converted — no real transaction is lost, and no metadata/header/footer line becomes a fake transaction.
- **SC-003**: Reimporting the same file, or a file whose period overlaps one already imported, results in zero duplicate transactions.
- **SC-004**: The sum of a month's imported transactions reconciles with the balance declared in the source statement, within a negligible rounding difference.
- **SC-005**: A file from an unsupported bank, or with a balance that doesn't reconcile, is flagged to the user in 100% of cases, never processed as if it were correct.

## Assumptions

- Only Bradesco and Inter are supported in this feature; support for other banks is left for a future iteration.
- Statement files are provided manually by the user (exported from online banking); automatic bank integration is out of scope for the project as a whole.
- The file format follows what was observed in the real exports collected between 24/07 and 22/08/2026; future layout changes by the banks may require adjusting the corresponding adapter.
- Assigning category, subcategory, and confidence isn't part of this feature — it's the categorization step's responsibility, which consumes this feature's output.
- Identifying/confirming transfers between the user's own accounts isn't part of this feature — it's the responsibility of categorization combined with human review.
- Each imported file corresponds to a single account/bank; files mixing accounts from different banks aren't a supported case.
