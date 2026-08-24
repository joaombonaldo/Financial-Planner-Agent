"""Automatic detection of the source bank from the header's column structure.

See research.md — "Automatic source-bank detection": the two formats are structurally
distinct enough (column names) to not need an ambiguous heuristic.
"""

from pathlib import Path

from financial_planner.state import Bank, UnrecognizedBankError


def detect_bank(path: str) -> Bank:
    text = Path(path).read_text(encoding="utf-8-sig")

    if "Crédito (R$)" in text and "Débito (R$)" in text:
        return Bank.BRADESCO

    if "Descrição" in text and "Histórico" in text and "Valor" in text:
        return Bank.INTER

    raise UnrecognizedBankError(
        f"File doesn't match any supported bank (Bradesco, Inter): {path}"
    )
