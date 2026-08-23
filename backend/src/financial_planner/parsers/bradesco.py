"""Adapter de parsing para exports do Bradesco.

Formato (BRD 6.1/6.3): UTF-8 com BOM, separador ';', colunas
Data;Histórico;Docto.;Crédito (R$);Débito (R$);Saldo (R$). Metadado na linha 1,
possível bloco duplicado "Últimos Lancamentos" no meio do arquivo e rodapé "Total" —
todos filtrados por `filter_transaction_lines` (nenhum começa com uma data).
"""

from pathlib import Path

from financial_planner.state import Bank, Transaction, TransactionType

from .base import filter_transaction_lines
from .dedup import compute_dedup_hash
from .normalize import month_ref, parse_brl_amount, parse_brl_date


def parse(path: str) -> list[Transaction]:
    # utf-8-sig lida com o BOM do Bradesco e também funciona normalmente sem BOM.
    text = Path(path).read_text(encoding="utf-8-sig")
    tx_lines = filter_transaction_lines(text.splitlines())

    transactions: list[Transaction] = []
    for line in tx_lines:
        date_str, historico, _docto, credito, debito, _saldo = line.split(";")[:6]

        transaction_date = parse_brl_date(date_str)
        description = historico.strip()

        if credito.strip():
            amount = parse_brl_amount(credito)
            tx_type = TransactionType.INCOME
        else:
            amount = parse_brl_amount(debito)
            tx_type = TransactionType.EXPENSE

        dedup_hash = compute_dedup_hash(
            transaction_date, description, amount, Bank.BRADESCO.value
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
