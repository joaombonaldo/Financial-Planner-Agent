"""Checagem de saldo como sanidade do parser (FR-008/FR-009).

Compara, em ordem cronológica no arquivo, saldo_anterior +/- valor_da_transação contra
o saldo declarado na linha. Divergência gera aviso — não aborta a importação das
transações já reconhecidas corretamente (ver research.md).
"""

from pathlib import Path

from financial_planner.state import Bank, BalanceReconciliation

from .base import filter_transaction_lines
from .normalize import parse_brl_amount

_TOLERANCE = 0.01


def _signed_amount_and_balance(line: str, bank: Bank) -> tuple[float, float]:
    fields = line.split(";")
    if bank is Bank.BRADESCO:
        _, _, _docto, credito, debito, saldo_str = fields[:6]
        signed_amount = parse_brl_amount(credito) if credito.strip() else -parse_brl_amount(debito)
    else:
        _, _, _descricao, valor_str, saldo_str = fields[:5]
        raw_valor = valor_str.strip()
        signed_amount = -parse_brl_amount(raw_valor) if raw_valor.startswith("-") else parse_brl_amount(raw_valor)

    saldo = parse_brl_amount(saldo_str)
    return signed_amount, saldo


def check_balance_reconciliation(
    path: str, bank: Bank
) -> tuple[BalanceReconciliation, list[str]]:
    text = Path(path).read_text(encoding="utf-8-sig")
    tx_lines = filter_transaction_lines(text.splitlines())

    if not tx_lines:
        return BalanceReconciliation.NOT_AVAILABLE, []

    # Seções duplicadas (ex.: "Últimos Lancamentos" do Bradesco) podem repetir a mesma
    # linha de transação literalmente — não é um novo lançamento no saldo, então a
    # checagem sequencial deve andar sobre ocorrências únicas, preservando a ordem.
    unique_lines = list(dict.fromkeys(tx_lines))

    warnings: list[str] = []
    previous_balance: float | None = None

    for line in unique_lines:
        signed_amount, saldo = _signed_amount_and_balance(line, bank)

        if previous_balance is not None:
            expected = previous_balance + signed_amount
            if abs(expected - saldo) > _TOLERANCE:
                warnings.append(
                    f"Saldo não reconcilia na linha '{line}': esperado {expected:.2f}, "
                    f"encontrado {saldo:.2f}"
                )

        previous_balance = saldo

    if warnings:
        return BalanceReconciliation.MISMATCH, warnings
    return BalanceReconciliation.OK, warnings
