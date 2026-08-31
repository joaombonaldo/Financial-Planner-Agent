"""Automatic detection of the source bank and payment instrument from a file.

CSV extracts (features 001+) are debit/PIX statements; their bank is decided by an
*exact* header-line match — see docs/decisions/detect-bank-header-line-match.md for
why a whole-file substring search was a correctness risk.

PDF files (feature 013) are credit-card faturas. A fatura has no single header line
to match, so the bank is decided by a distinctive multi-word issuer string that only
appears in that bank's own fatura boilerplate ("app Bradesco Cartões",
"BANCO INTER S/A") — still a fixed, verbatim marker, not a loose "column name
appears somewhere" heuristic. See docs/decisions/credit-card-stream.md.
"""

from pathlib import Path

from financial_planner.parsers import credit_card_bradesco, credit_card_inter
from financial_planner.parsers.pdf_text import extract_text
from financial_planner.state import Bank, Instrument, UnrecognizedBankError

_BRADESCO_HEADER = "Data;Histórico;Docto.;Crédito (R$);Débito (R$);Saldo (R$)"
_INTER_HEADER = "Data Lançamento;Histórico;Descrição;Valor;Saldo"


def _is_pdf(path: str) -> bool:
    return path.lower().endswith(".pdf")


def detect_instrument(path: str) -> Instrument:
    """PDF => credit-card fatura stream; anything else => debit/PIX stream."""
    return Instrument.CREDIT if _is_pdf(path) else Instrument.DEBIT


def _detect_fatura_bank(path: str) -> Bank:
    text = extract_text(path)
    if credit_card_bradesco.is_bradesco_fatura(text):
        return Bank.BRADESCO
    if credit_card_inter.is_inter_fatura(text):
        return Bank.INTER
    raise UnrecognizedBankError(
        f"PDF doesn't match any supported credit-card fatura (Bradesco, Inter): {path}"
    )


def _detect_csv_bank(path: str) -> Bank:
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


def detect_bank(path: str) -> Bank:
    return _detect_fatura_bank(path) if _is_pdf(path) else _detect_csv_bank(path)
