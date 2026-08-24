"""Detecção de candidatos a transferência entre contas próprias (contracts/transfer-detection.md).

Padrão PIX/TED/DOC na descrição + valor espelhado (mesmo valor absoluto, type oposto)
em outra conta dentro de uma janela de ±2 dias. As duas condições são obrigatórias.
Nunca exclui a transação do total nem confirma — apenas sinaliza (FR-008).
"""

import re

from financial_planner.state import Transaction

_TRANSFER_PATTERN = re.compile(r"pix|ted|doc", re.IGNORECASE)
_WINDOW_DAYS = 2


def is_transfer_candidate(transaction: Transaction, other_transactions: list[Transaction]) -> bool:
    if not _TRANSFER_PATTERN.search(transaction.description_raw):
        return False

    for other in other_transactions:
        if other.dedup_hash == transaction.dedup_hash:
            continue
        if other.account == transaction.account:
            continue
        if other.type == transaction.type:
            continue
        if other.amount != transaction.amount:
            continue
        if abs((other.date - transaction.date).days) > _WINDOW_DAYS:
            continue
        return True

    return False
