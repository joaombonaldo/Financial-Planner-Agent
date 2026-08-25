"""Parsing adapter for Bradesco exports.

Format (BRD 6.1/6.3): UTF-8 with BOM, ';' separator, columns
Data;Histórico;Docto.;Crédito (R$);Débito (R$);Saldo (R$). Metadata on line 1, a
possible duplicated "Últimos Lancamentos" block mid-file, and a "Total" footer — all
filtered out by `filter_transaction_lines` (none of them start with a date).
"""

from pathlib import Path

from financial_planner.state import Bank, Transaction, TransactionType

from .base import filter_transaction_lines
from .dedup import compute_dedup_hash
from .normalize import month_ref, parse_brl_amount, parse_brl_date


def parse(path: str) -> list[Transaction]:
    # utf-8-sig handles Bradesco's BOM and also works fine without one.
    text = Path(path).read_text(encoding="utf-8-sig")
    tx_lines = filter_transaction_lines(text.splitlines())

    transactions: list[Transaction] = []
    for line in tx_lines:
        date_str, description_raw, doc_number, credit, debit, _balance = line.split(";")[:6]

        transaction_date = parse_brl_date(date_str)
        description = description_raw.strip()

        if credit.strip():
            amount = parse_brl_amount(credit)
            tx_type = TransactionType.INCOME
        elif debit.strip():
            amount = parse_brl_amount(debit)
            tx_type = TransactionType.EXPENSE
        else:
            # Administrative line with no real movement (e.g. "COD. LANC. 0" with
            # both columns blank/whitespace) — observed in real exports. Balance
            # doesn't change; a zero amount doesn't affect totals either way.
            amount = 0.0
            tx_type = TransactionType.EXPENSE

        # Docto. distinguishes two real transactions that otherwise share date,
        # description and amount. The duplicated "Últimos Lancamentos" block repeats
        # the same Docto. value along with everything else, so it still collapses to
        # the same hash — see dedup.py's docstring.
        dedup_hash = compute_dedup_hash(
            transaction_date, description, amount, Bank.BRADESCO.value, doc_number.strip()
        )

        transactions.append(
            Transaction(
                dedup_hash=dedup_hash,
                date=transaction_date,
                description_raw=description,
                account=Bank.BRADESCO,
                type=tx_type,
                amount=amount,
                month_ref=month_ref(transaction_date),
            )
        )

    return transactions
