"""Transaction deduplication hash (Principle VII of the constitution).

Computed over already-normalized values (not over the CSV's raw text), so the same
transaction produces the same hash even with minor textual variation between exports.
"""

import hashlib
from datetime import date


def compute_dedup_hash(
    transaction_date: date, description_raw: str, amount: float, account: str
) -> str:
    payload = f"{transaction_date.isoformat()}|{description_raw.strip()}|{amount:.2f}|{account}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
