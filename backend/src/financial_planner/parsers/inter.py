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

        dedup_hash = compute_dedup_hash(
            transaction_date, description, amount, Bank.INTER.value
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
