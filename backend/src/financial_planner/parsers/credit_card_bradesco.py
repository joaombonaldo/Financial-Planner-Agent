"""Parsing adapter for the Bradesco credit-card fatura (PDF, feature 013).

Text layer: present (iText producer), not scanned, not password-protected in the
samples collected. Two pages: page 1 is the summary (totals, due date, previous
balance), page 2 the itemized ``Lançamentos``.

Row format on page 2: ``DD/MM  <description>  [<city>]  [<US$ value>]  <R$ value>[-]``
— purchase date has no year; a trailing ``-`` on the amount marks a payment/credit;
installments are a bare ``NN/MM`` token inside the description (``HOTEL ... 03/06``);
foreign-currency rows print the origin value and the BRL value on the same line, BRL
last. The rates/limits table is printed to the right of the transaction list at the
same vertical positions, so we rebuild page text from left-of-x words only
(``parsers.pdf_text.extract_left_column_pages``).

Fatura metadata on page 1: ``R$ <total> <DD/MM/YYYY due>`` under "Total da fatura /
Vencimento", ``Previsão de fechamento da próxima fatura:<DD/MM/YYYY>``, and
``Saldo anterior......... R$ <n>``.
"""

from __future__ import annotations

import re

from financial_planner.parsers.credit_card_common import (
    CreditTransactionBuilder,
    FaturaMetadata,
    fatura_ref_for,
    infer_year,
    last_brl_amount,
    parse_amount_and_type,
    strip_installment_bradesco,
)
from financial_planner.parsers.normalize import parse_brl_amount, parse_brl_date
from financial_planner.parsers.pdf_text import extract_left_column_pages, extract_text
from financial_planner.state import Bank, Transaction

# A verbatim slice of Bradesco's fatura boilerplate ("Baixe o app Bradesco Cartões
# ou acesse o site" / "no App Bradesco Cartões,"). ASCII-only so it survives any
# font-encoding quirk in the PDF's text layer.
_ISSUER_MARKER = "Bradesco Cart"

_ROW_RE = re.compile(r"^(?P<day>\d{2})/(?P<month>\d{2})\s+(?P<rest>\S.*)$")
_CARD_RE = re.compile(r"Cart[aã]o\s+[\dX* ]*?(\d{4})\s*$")
_TRAILING_FX_RE = re.compile(r"\s*\d[\d.]*,\d{2}\S*\s*$")

_TOTAL_DUE_RE = re.compile(r"R\$\s*([\d.]+,\d{2})\s+(\d{2}/\d{2}/\d{4})")
_CLOSING_RE = re.compile(r"fechamento da próxima fatura:\s*(\d{2}/\d{2}/\d{4})")
_PREV_BALANCE_RE = re.compile(r"Saldo anterior[.\s]*R\$\s*([\d.]+,\d{2})")

_X_MAX = 360.0


def is_bradesco_fatura(text: str) -> bool:
    return _ISSUER_MARKER in text


def parse_metadata(text: str) -> FaturaMetadata:
    total_due = _TOTAL_DUE_RE.search(text)
    if not total_due:
        raise ValueError("Bradesco fatura: could not locate total / due date")
    total = parse_brl_amount(total_due.group(1))
    due = parse_brl_date(total_due.group(2))

    closing = _CLOSING_RE.search(text)
    prev = _PREV_BALANCE_RE.search(text)
    return FaturaMetadata(
        bank=Bank.BRADESCO,
        due_date=due,
        fatura_ref=fatura_ref_for(due),
        total=total,
        # The only date Bradesco labels "fechamento" is the *next* fatura's — kept
        # as-is; the current fatura's closing is not printed on the document.
        closing_date=parse_brl_date(closing.group(1)) if closing else None,
        previous_balance=parse_brl_amount(prev.group(1)) if prev else None,
    )


def parse_statement_text(full_text: str, row_pages: list[str]) -> list[Transaction]:
    meta = parse_metadata(full_text)
    builder = CreditTransactionBuilder(meta)

    transactions: list[Transaction] = []
    card_tail = "0000"
    for page in row_pages:
        for line in page.splitlines():
            line = line.strip()
            card = _CARD_RE.search(line)
            if card:
                card_tail = card.group(1)
                continue

            row = _ROW_RE.match(line)
            if not row:
                continue
            amount_match = last_brl_amount(row.group("rest"))
            if not amount_match:
                continue

            amount, tx_type = parse_amount_and_type(amount_match.group(0))
            description = row.group("rest")[: amount_match.start()].strip()
            description = _TRAILING_FX_RE.sub("", description).strip()
            description, inst_idx, inst_count = strip_installment_bradesco(description)
            if not description:
                description = "LANÇAMENTO SEM DESCRIÇÃO"

            month = int(row.group("month"))
            purchase_date = parse_brl_date(
                f"{row.group('day')}/{row.group('month')}/{infer_year(month, meta.due_date)}"
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
    full_text = extract_text(path, bank_hint="bradesco")
    row_pages = extract_left_column_pages(path, x_max=_X_MAX, bank_hint="bradesco")
    return parse_statement_text(full_text, row_pages)


# Convenience for text-fixture tests: treat the fixture as both the metadata source
# and (line-filtered) the row source.
def parse_text_fixture(text: str) -> list[Transaction]:
    return parse_statement_text(text, [text])


__all__ = [
    "parse",
    "parse_statement_text",
    "parse_text_fixture",
    "parse_metadata",
    "is_bradesco_fatura",
]
