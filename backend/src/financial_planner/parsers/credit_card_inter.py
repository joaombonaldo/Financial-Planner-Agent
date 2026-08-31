"""Parsing adapter for the Inter credit-card fatura (PDF, feature 013).

Text layer: present (Chromium print -> pdfcpu). One sample file is a valid PDF
preceded by ~430 KB of NUL padding — handled transparently in
``parsers.pdf_text``. Not password-protected in the samples.

Row format under ``Despesas da fatura`` / ``CARTÃO 5361****XXXX``:
``DD de <mon>. YYYY  <description>  -  [+ ]R$ <amount>`` — full purchase date (no
year inference needed); the lone ``-`` is the empty "Beneficiário" column; a ``+``
before ``R$`` marks a payment/credit; installments are spelled out as
``(Parcela NN de MM)`` inside the description. Foreign-currency rows are followed by
un-dated ``Valor e símbolo da moeda de origem: ...`` detail lines (ignored — they
don't match the row regex). The "Próxima fatura" section lists next month's
installments without a date prefix, so they're ignored too.

Fatura metadata: the running page header ``5361****XXXX DD/MM/YYYY R$ <total>`` gives
the due date and total; ``Data de corte: DD/MM/YYYY`` and ``Valor antecipado R$ <n>``
give the (next) closing date and the carried-in balance.
"""

from __future__ import annotations

import re

from financial_planner.parsers.credit_card_common import (
    PT_MONTHS,
    CreditTransactionBuilder,
    FaturaMetadata,
    fatura_ref_for,
    is_payment,
    strip_installment_inter,
)
from financial_planner.parsers.normalize import parse_brl_amount, parse_brl_date
from financial_planner.parsers.pdf_text import extract_text
from financial_planner.state import Bank, Transaction, TransactionType

_ISSUER_MARKER = "BANCO INTER S/A"

_MONTHS_ALT = "|".join(PT_MONTHS)
_ROW_RE = re.compile(
    rf"^(?P<day>\d{{2}})\s+de\s+(?P<mon>{_MONTHS_ALT})\.?\s+(?P<year>\d{{4}})\s+"
    rf"(?P<rest>.+?)\s+R\$\s*(?P<amt>\d{{1,3}}(?:\.\d{{3}})*,\d{{2}})\s*$"
)
_CARD_RE = re.compile(r"CART[ÃA]O\s+\S*?(\d{4})\s*$")

_HEADER_TOTAL_RE = re.compile(
    r"\d{4}\*+\d{4}\s+(\d{2}/\d{2}/\d{4})\s+R\$\s*([\d.]+,\d{2})"
)
_FATURA_ATUAL_RE = re.compile(r"Fatura atual\s+R\$\s*([\d.]+,\d{2})")
_CORTE_RE = re.compile(r"Data de corte:\s*(\d{2}/\d{2}/\d{4})")
_ANTECIPADO_RE = re.compile(r"Valor antecipado\s+R\$\s*([\d.]+,\d{2})")


def is_inter_fatura(text: str) -> bool:
    return _ISSUER_MARKER in text


def parse_metadata(text: str) -> FaturaMetadata:
    header = _HEADER_TOTAL_RE.search(text)
    if not header:
        raise ValueError("Inter fatura: could not locate due date / total header")
    due = parse_brl_date(header.group(1))
    total = parse_brl_amount(header.group(2))

    fatura_atual = _FATURA_ATUAL_RE.search(text)
    if fatura_atual:
        total = parse_brl_amount(fatura_atual.group(1))

    corte = _CORTE_RE.search(text)
    antecipado = _ANTECIPADO_RE.search(text)
    return FaturaMetadata(
        bank=Bank.INTER,
        due_date=due,
        fatura_ref=fatura_ref_for(due),
        total=total,
        # "Data de corte" on the document is the *next* fatura's cut-off date.
        closing_date=parse_brl_date(corte.group(1)) if corte else None,
        previous_balance=parse_brl_amount(antecipado.group(1)) if antecipado else None,
    )


def parse_statement_text(text: str) -> list[Transaction]:
    meta = parse_metadata(text)
    builder = CreditTransactionBuilder(meta)

    transactions: list[Transaction] = []
    card_tail = "0000"
    for raw in text.splitlines():
        line = raw.strip()
        card = _CARD_RE.search(line)
        if card:
            card_tail = card.group(1)
            continue

        row = _ROW_RE.match(line)
        if not row:
            continue

        rest = row.group("rest")
        has_plus = bool(re.search(r"\+\s*$", rest))
        description = re.sub(r"[\s\-+]+$", "", rest).strip()
        description, inst_idx, inst_count = strip_installment_inter(description)
        if not description:
            description = "LANÇAMENTO SEM DESCRIÇÃO"

        amount = parse_brl_amount(row.group("amt"))
        tx_type = (
            TransactionType.INCOME
            if has_plus or is_payment(description, TransactionType.EXPENSE)
            else TransactionType.EXPENSE
        )

        month = PT_MONTHS[row.group("mon")]
        purchase_date = parse_brl_date(
            f"{row.group('day')}/{month:02d}/{row.group('year')}"
        )

        transactions.append(
            builder.build(
                purchase_date=purchase_date,
                description=description,
                amount=amount,
                tx_type=tx_type,
                card_tail=card_tail,
                installment_index=inst_idx,
                installment_count=inst_count,
            )
        )
    return transactions


def parse(path: str) -> list[Transaction]:
    return parse_statement_text(extract_text(path, bank_hint="inter"))


__all__ = [
    "parse",
    "parse_statement_text",
    "parse_metadata",
    "is_inter_fatura",
]
