"""Balance check as a parser sanity net (FR-008/FR-009).

Compares, in chronological order (oldest -> newest), previous_balance +/- the
transaction amount against the balance declared on the line. A discrepancy produces a
warning — it doesn't abort importing the transactions already recognized correctly
(see research.md).

Findings from real exports (not anticipated by the original spec, fixed after manual
validation — see quickstart.md):
- The balance can be negative (overdraft) — always normalizing to an absolute value
  would lose the sign, so the balance is parsed while preserving the sign.
- The chronological order of lines in the file varies by bank (Bradesco: oldest
  first; Inter: most recent first) — lines are reordered to ascending date order
  before the sequential check, regardless of the source order.

Warning messages stay in Portuguese: they surface to the end user (the app's actual
runtime language), same as the CLI and the taxonomy.
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
        _, _, _doc_number, credit, debit, balance_str = fields[:6]
        if credit.strip():
            signed_amount = parse_brl_amount(credit)
        elif debit.strip():
            signed_amount = -parse_brl_amount(debit)
        else:
            # Administrative line with no real movement (see bradesco.py).
            signed_amount = 0.0
    else:
        _, _, _description, amount_str, balance_str = fields[:5]
        raw_amount = amount_str.strip()
        signed_amount = -parse_brl_amount(raw_amount) if raw_amount.startswith("-") else parse_brl_amount(raw_amount)

    return signed_amount, _parse_signed_balance(balance_str)


def _chronological_order(lines: list[str]) -> list[str]:
    """Ensures ascending date order, regardless of the file's source order."""
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

    # Duplicated sections (e.g. Bradesco's "Últimos Lancamentos") can literally repeat
    # the same transaction line — it's not a new balance entry, so the sequential
    # check must walk over unique occurrences, preserving order.
    unique_lines = list(dict.fromkeys(tx_lines))
    unique_lines = _chronological_order(unique_lines)

    warnings: list[str] = []
    previous_balance: float | None = None

    for line in unique_lines:
        signed_amount, balance = _signed_amount_and_balance(line, bank)

        if previous_balance is not None:
            expected = previous_balance + signed_amount
            if abs(expected - balance) > _TOLERANCE:
                warnings.append(
                    f"Saldo não reconcilia na linha '{line}': esperado {expected:.2f}, "
                    f"encontrado {balance:.2f}"
                )

        previous_balance = balance

    if warnings:
        return BalanceReconciliation.MISMATCH, warnings
    return BalanceReconciliation.OK, warnings
