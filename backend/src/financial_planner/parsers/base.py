"""Shared contract for per-bank parser adapters.

See specs/001-ingest-extratos/contracts/parser-adapter.md. Each bank adapter
(bradesco.py, inter.py) exposes a `parse(path: str) -> list[Transaction]` function with
these guarantees:

- Metadata lines, repeated headers, and footers never become a Transaction.
- description_raw is never empty (fallback applied internally by the adapter).
- amount is always positive; direction lives entirely in `type`.
- date and amount are already normalized to the canonical format.
- The order of returned transactions preserves the source file's order.

No formal Protocol/ABC (Principle I — pragmatic simplicity): the guarantee is by
signature convention, not by a type contract.
"""

import re

# Only lines starting with a DD/MM/YYYY date followed by ';' are transaction
# candidates — this robustly handles metadata, duplicated headers, and footers
# without needing to map the file's exact line-by-line structure (see research.md).
TRANSACTION_LINE_PATTERN = re.compile(r"^\d{2}/\d{2}/\d{4};")


def is_transaction_line(line: str) -> bool:
    return bool(TRANSACTION_LINE_PATTERN.match(line))


def filter_transaction_lines(raw_lines: list[str]) -> list[str]:
    """Return only the transaction-candidate lines, in the file's original order."""
    return [line for line in raw_lines if is_transaction_line(line)]
