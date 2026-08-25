"""Parsing adapter for Inter exports.

Format (BRD 6.1/6.3): UTF-8 without BOM, ';' separator, columns
Data Lançamento;Histórico;Descrição;Valor;Saldo. Valor is signed (negative = debit).
`Descrição` can come blank — in that case, fall back to `Histórico`.
"""

from pathlib import Path

from financial_planner.state import Bank, Transaction, TransactionType

from .base import filter_transaction_lines
from .dedup import compute_dedup_hash
from .normalize import month_ref, parse_brl_amount, parse_brl_date


def parse(path: str) -> list[Transaction]:
    text = Path(path).read_text(encoding="utf-8-sig")
    tx_lines = filter_transaction_lines(text.splitlines())

    # Inter's export has no per-line document/reference number (unlike Bradesco's
    # Docto.), so two real transactions sharing date+description+amount can't be told
    # apart from their fields alone. Counting occurrences of the same key, in file
    # order, gives each one a distinct-but-deterministic discriminator: reparsing the
    # same file reproduces the same sequence of counts, so reimport dedup (FR-006)
    # still works, while two distinct transactions within one file no longer collide.
    occurrence_counts: dict[tuple, int] = {}

    transactions: list[Transaction] = []
    for line in tx_lines:
        date_str, generic_description, merchant_description, amount_str, _balance = line.split(";")[:5]

        transaction_date = parse_brl_date(date_str)
        description = merchant_description.strip() or generic_description.strip()

        raw_amount = amount_str.strip()
        amount = parse_brl_amount(raw_amount)
        tx_type = (
            TransactionType.EXPENSE if raw_amount.startswith("-") else TransactionType.INCOME
        )

        key = (transaction_date, description, amount)
        occurrence = occurrence_counts.get(key, 0)
        occurrence_counts[key] = occurrence + 1

        dedup_hash = compute_dedup_hash(
            transaction_date, description, amount, Bank.INTER.value, str(occurrence)
        )

        transactions.append(
            Transaction(
                dedup_hash=dedup_hash,
                date=transaction_date,
                description_raw=description,
                account=Bank.INTER,
                type=tx_type,
                amount=amount,
                month_ref=month_ref(transaction_date),
            )
        )

    return transactions
