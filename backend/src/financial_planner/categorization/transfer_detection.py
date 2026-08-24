"""Detects candidates for transfers between the user's own accounts (contracts/transfer-detection.md).

PIX/TED/DOC pattern in the description + a mirrored amount (same absolute value,
opposite type) in another account within a ±2-day window. Both conditions are
mandatory. Never excludes the transaction from the total nor confirms it — only flags
it (FR-008).
"""

import re

from financial_planner.state import Transaction

_TRANSFER_PATTERN = re.compile(r"pix|ted|doc", re.IGNORECASE)
_WINDOW_DAYS = 2


def is_transfer_candidate(transaction: Transaction, other_transactions: list[Transaction]) -> bool:
    if not _TRANSFER_PATTERN.search(transaction.description_raw):
        return False

    for other in other_transactions:
        if other.dedup_hash == transaction.dedup_hash:
            continue
        if other.account == transaction.account:
            continue
        if other.type == transaction.type:
            continue
        if other.amount != transaction.amount:
            continue
        if abs((other.date - transaction.date).days) > _WINDOW_DAYS:
            continue
        return True

    return False
