"""Detecção automática do banco de origem a partir da estrutura de colunas do header.

Ver research.md — "Detecção automática do banco de origem": os dois formatos são
estruturalmente distintos o suficiente (nomes de coluna) para não precisar de
heurística ambígua.
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
        f"Arquivo não corresponde a nenhum banco suportado (Bradesco, Inter): {path}"
    )
