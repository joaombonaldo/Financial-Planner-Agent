"""Normalizes amount (Brazilian format) and date into the canonical format.

See research.md — "Amount and date normalization": explicit format, never automatic
inference (dates like 01/02/2026 are ambiguous without a fixed format).
"""

from datetime import date, datetime


def parse_brl_amount(raw: str) -> float:
    """Converts '1.645,20' -> 1645.20. Always returns a positive value."""
    cleaned = raw.strip().replace(".", "").replace(",", ".")
    return abs(float(cleaned))


def parse_brl_date(raw: str) -> date:
    """Converts 'DD/MM/YYYY' -> date, with an explicit format (never inferred)."""
    return datetime.strptime(raw.strip(), "%d/%m/%Y").date()


def month_ref(d: date) -> str:
    """E.g.: date(2026, 8, 23) -> '2026-08'."""
    return f"{d.year:04d}-{d.month:02d}"
