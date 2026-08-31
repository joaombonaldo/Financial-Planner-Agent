"""Shared helpers for the credit-card fatura adapters (feature 013).

Both ``credit_card_bradesco`` and ``credit_card_inter`` follow the CSV adapters'
contract (see parsers/base.py) with two additions:

- every returned Transaction carries ``instrument = Instrument.CREDIT`` and a
  ``fatura_ref`` (the YYYY-MM of the fatura's due date — the month it is paid, which
  is the month its settling line lands in the debit extract);
- ``month_ref`` is still the month of the *purchase date*, so a purchase made in
  May that shows up on an August-due fatura is grouped under ``2026-05``.

The fatura total is informational: it does NOT feed the month's headline expense
total. Reconciliation (sum of a fatura's purchases vs. the debit payment line) is a
report-node concern — see docs/decisions/credit-card-stream.md.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from financial_planner.parsers.dedup import compute_dedup_hash
from financial_planner.parsers.normalize import parse_brl_amount
from financial_planner.state import Bank, Instrument, Transaction, TransactionType

# Portuguese three-letter month abbreviations as they appear in Inter's fatura.
PT_MONTHS = {
    "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
    "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12,
}

# A BRL money token, optionally trailed by '-' (Bradesco marks credits that way).
BRL_AMOUNT = r"\d{1,3}(?:\.\d{3})*,\d{2}-?"
_BRL_AMOUNT_RE = re.compile(BRL_AMOUNT)

# Words in a fatura line that mean "this is a payment/credit, not a purchase".
_CREDIT_MARKERS = re.compile(
    r"PAGTO|PAGAMENTO|ESTORNO|CRÉDITO|CREDITO|DEVOLU|REEMBOLSO", re.IGNORECASE
)


@dataclass(frozen=True)
class FaturaMetadata:
    """Fatura-level fields, parsed once per file."""

    bank: Bank
    due_date: date
    fatura_ref: str
    total: float | None = None
    closing_date: date | None = None
    previous_balance: float | None = None


def fatura_ref_for(due: date) -> str:
    """A fatura is identified by the month it is due / paid."""
    return f"{due.year:04d}-{due.month:02d}"


def infer_year(purchase_month: int, due: date) -> int:
    """Bradesco prints purchase dates as DD/MM with no year. A purchase can only be
    in the due-date's year or the one before it (faturas span at most ~12 months of
    installment history)."""
    return due.year if purchase_month <= due.month else due.year - 1


def parse_amount_and_type(token: str) -> tuple[float, TransactionType]:
    credit = token.rstrip().endswith("-")
    amount = parse_brl_amount(token.rstrip("-"))
    return amount, (TransactionType.INCOME if credit else TransactionType.EXPENSE)


def strip_installment_bradesco(description: str) -> tuple[str, int | None, int | None]:
    """Bradesco embeds the installment as a bare ``NN/MM`` token in the description
    (e.g. ``HOTEL VILA MICHEL 03/06``)."""
    match = re.search(r"\b(\d{1,2})/(\d{1,2})\b", description)
    if not match:
        return description.strip(), None, None
    index, count = int(match.group(1)), int(match.group(2))
    if index == 0 or count == 0 or index > count:
        return description.strip(), None, None
    cleaned = (description[: match.start()] + description[match.end():]).strip()
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned, index, count


def strip_installment_inter(description: str) -> tuple[str, int | None, int | None]:
    """Inter spells it out: ``AMAZON BR (Parcela 06 de 07)``."""
    match = re.search(r"\(Parcela\s+(\d{1,2})\s+de\s+(\d{1,2})\)", description, re.IGNORECASE)
    if not match:
        return description.strip(), None, None
    index, count = int(match.group(1)), int(match.group(2))
    cleaned = (description[: match.start()] + description[match.end():]).strip()
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned, index, count


def is_payment(description: str, tx_type: TransactionType) -> bool:
    return tx_type is TransactionType.INCOME or bool(_CREDIT_MARKERS.search(description))


class CreditTransactionBuilder:
    """Builds credit-stream Transactions with a collision-safe dedup hash.

    Credit rows have no ``Docto.`` number. The discriminator mirrors the reasoning in
    docs/decisions/dedup-hash-discriminator.md: a stable per-file occurrence index
    over ``(date, description, amount, installment_index)``, plus the masked card
    tail and the ``credit:`` prefix so a credit row can never collide with a debit
    row that happens to share date+description+amount+account.
    """

    def __init__(self, meta: FaturaMetadata) -> None:
        self._meta = meta
        self._seen: dict[tuple, int] = {}

    def build(
        self,
        *,
        purchase_date: date,
        description: str,
        amount: float,
        tx_type: TransactionType,
        card_tail: str,
        installment_index: int | None,
        installment_count: int | None,
    ) -> Transaction:
        key = (purchase_date, description, round(amount, 2), installment_index)
        occurrence = self._seen.get(key, 0)
        self._seen[key] = occurrence + 1

        discriminator = (
            f"credit:{card_tail}:{installment_index or 0}/{installment_count or 0}"
            f":{occurrence}"
        )
        dedup_hash = compute_dedup_hash(
            purchase_date, description, amount, self._meta.bank.value, discriminator
        )
        return Transaction(
            dedup_hash=dedup_hash,
            date=purchase_date,
            description_raw=description,
            account=self._meta.bank,
            type=tx_type,
            amount=amount,
            month_ref=f"{purchase_date.year:04d}-{purchase_date.month:02d}",
            instrument=Instrument.CREDIT,
            fatura_ref=self._meta.fatura_ref,
            installment_index=installment_index,
            installment_count=installment_count,
        )


def last_brl_amount(text: str) -> re.Match | None:
    """The rightmost BRL token on a line — for foreign-currency rows that print the
    origin-currency value and the BRL value on the same line, the BRL one is last."""
    matches = list(_BRL_AMOUNT_RE.finditer(text))
    return matches[-1] if matches else None
