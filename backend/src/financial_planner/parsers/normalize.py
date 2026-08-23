"""Normalização de valor (formato brasileiro) e data para o formato canônico.

Ver research.md — "Normalização de valor e data": formato explícito, nunca inferência
automática (datas como 01/02/2026 são ambíguas sem formato fixo).
"""

from datetime import date, datetime


def parse_brl_amount(raw: str) -> float:
    """Converte '1.645,20' -> 1645.20. Sempre retorna valor positivo."""
    cleaned = raw.strip().replace(".", "").replace(",", ".")
    return abs(float(cleaned))


def parse_brl_date(raw: str) -> date:
    """Converte 'DD/MM/AAAA' -> date, com formato explícito (nunca inferido)."""
    return datetime.strptime(raw.strip(), "%d/%m/%Y").date()


def month_ref(d: date) -> str:
    """Ex.: date(2026, 8, 23) -> '2026-08'."""
    return f"{d.year:04d}-{d.month:02d}"
