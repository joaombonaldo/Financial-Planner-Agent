"""Checagem de saldo como sanidade do parser (FR-008/FR-009).

Compara, em ordem cronológica (mais antigo -> mais recente), saldo_anterior +/- valor_da
transação contra o saldo declarado na linha. Divergência gera aviso — não aborta a
importação das transações já reconhecidas corretamente (ver research.md).

Achados de exports reais (não previstos na spec original, corrigidos após validação
manual — ver quickstart.md):
- O saldo pode ser negativo (cheque especial) — normalizar sempre como valor absoluto
  perderia o sinal, então o saldo é parseado preservando o sinal.
- A ordem cronológica das linhas no arquivo varia por banco (Bradesco: mais antigo
  primeiro; Inter: mais recente primeiro) — as linhas são reordenadas para ordem
  ascendente por data antes da checagem sequencial, independente da ordem de origem.
"""

from pathlib import Path

from financial_planner.state import Bank, BalanceReconciliation

from .base import filter_transaction_lines
from .normalize import parse_brl_amount, parse_brl_date

_TOLERANCE = 0.01


def _parse_signed_balance(raw: str) -> float:
    raw = raw.strip()
    magnitude = parse_brl_amount(raw)
    return -magnitude if raw.startswith("-") else magnitude


def _signed_amount_and_balance(line: str, bank: Bank) -> tuple[float, float]:
    fields = line.split(";")
    if bank is Bank.BRADESCO:
        _, _, _docto, credito, debito, saldo_str = fields[:6]
        if credito.strip():
            signed_amount = parse_brl_amount(credito)
        elif debito.strip():
            signed_amount = -parse_brl_amount(debito)
        else:
            # Linha administrativa sem movimentação real (ver bradesco.py).
            signed_amount = 0.0
    else:
        _, _, _descricao, valor_str, saldo_str = fields[:5]
        raw_valor = valor_str.strip()
        signed_amount = -parse_brl_amount(raw_valor) if raw_valor.startswith("-") else parse_brl_amount(raw_valor)

    return signed_amount, _parse_signed_balance(saldo_str)


def _chronological_order(lines: list[str]) -> list[str]:
    """Garante ordem ascendente por data, independente da ordem de origem do arquivo."""
    first_date = parse_brl_date(lines[0].split(";", 1)[0])
    last_date = parse_brl_date(lines[-1].split(";", 1)[0])
    return list(reversed(lines)) if first_date > last_date else lines


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
    unique_lines = _chronological_order(unique_lines)

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
