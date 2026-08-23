"""Hash de deduplicação de transações (Princípio VII da constituição).

Calculado sobre valores já normalizados (não sobre o texto cru do CSV), para que a
mesma transação gere o mesmo hash mesmo com pequenas variações textuais entre exports.
"""

import hashlib
from datetime import date


def compute_dedup_hash(
    transaction_date: date, description_raw: str, amount: float, account: str
) -> str:
    payload = f"{transaction_date.isoformat()}|{description_raw.strip()}|{amount:.2f}|{account}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
