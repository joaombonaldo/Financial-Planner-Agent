"""Transaction deduplication hash (Principle VII of the constitution).

Computed over already-normalized values (not over the CSV's raw text), so the same
transaction produces the same hash even with minor textual variation between exports.

`date + description + amount + account` alone is not a safe key: two genuinely
distinct transactions can legitimately share all four (e.g. two identical-amount
purchases at the same merchant on the same day). Without a fifth distinguishing
value, the second one collides with the first and is silently dropped as a
"duplicate" on insert (see docs/decisions/dedup-hash-discriminator.md) — a direct
violation of specs/001-ingest-extratos spec.md SC-002 ("no real transaction is
lost"). `discriminator` carries that fifth value; each bank adapter decides what to
pass (see bradesco.py / inter.py), since what's available differs by source.
"""

import hashlib
from datetime import date


def compute_dedup_hash(
    transaction_date: date,
    description_raw: str,
    amount: float,
    account: str,
    discriminator: str = "",
) -> str:
    payload = (
        f"{transaction_date.isoformat()}|{description_raw.strip()}|{amount:.2f}|"
        f"{account}|{discriminator}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
