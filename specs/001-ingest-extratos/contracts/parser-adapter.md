# Contract: Per-Bank Parser Adapter

Internal interface that each bank adapter (`parsers/bradesco.py`, `parsers/inter.py`) must implement. Consumed by
`parsers/detect.py` (adapter selection) and by `nodes/ingest.py` (orchestration) — never directly by other nodes,
per Principle II of the constitution.

## Bank detection

**Input**: raw content (or path) of the statement file.

**Output**: bank identifier (`bradesco` | `inter`) or an explicit "not recognized" signal.

**Rule**: based on the header's column structure (see research.md — "Automatic source-bank detection"). Never
throws a silent exception; an unrecognized file is an explicit result, not a parsing failure treated as an empty
success.

## Per-adapter parsing

**Input**: raw content (or path) of the statement file, already identified as belonging to a specific bank.

**Output**: list of `Normalized transaction` (field subset defined in `data-model.md`) + the information needed to
build the `ImportResult` (balance values read, in file order, for the sanity check).

**Guarantees the contract requires from any adapter**:
- Metadata lines, repeated headers, and footers never appear in the returned transaction list.
- `description_raw` is never empty (applies the `Histórico` fallback when the primary description column is
  blank).
- `amount` is always positive; direction (income/expense) lives entirely in the `type` field.
- `date` and `amount` are already normalized to the canonical format (ISO date, decimal) — the caller never
  receives the bank's raw format.
- The order of returned transactions preserves the source file's order (needed for the sequential balance check).

## Usage by the `detect_and_parse` node

The node (`nodes/ingest.py`) only orchestrates: it calls bank detection, selects the matching adapter, calls
parsing, and delegates the `dedup_hash` check + persistence to `db/repository.py`. The node never reads the file
nor formats CSV directly — that's the boundary Principle II of the constitution protects.
