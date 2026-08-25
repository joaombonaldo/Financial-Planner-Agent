"""Automatic detection of the source bank from the header's column structure.

See research.md — "Automatic source-bank detection": the two formats are structurally
distinct enough (column names) to not need an ambiguous heuristic.

Matches the exact header line, not a substring search over the whole file — see
docs/decisions/detect-bank-header-line-match.md for why the earlier substring
approach was a correctness risk, not just a style nit.
"""

from pathlib import Path

from financial_planner.state import Bank, UnrecognizedBankError

_BRADESCO_HEADER = "Data;Histórico;Docto.;Crédito (R$);Débito (R$);Saldo (R$)"
_INTER_HEADER = "Data Lançamento;Histórico;Descrição;Valor;Saldo"


def detect_bank(path: str) -> Bank:
    text = Path(path).read_text(encoding="utf-8-sig")

    for line in text.splitlines():
        stripped = line.strip()
        if stripped == _BRADESCO_HEADER:
            return Bank.BRADESCO
        if stripped == _INTER_HEADER:
            return Bank.INTER

    raise UnrecognizedBankError(
        f"File doesn't match any supported bank (Bradesco, Inter): {path}"
    )
