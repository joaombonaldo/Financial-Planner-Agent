"""Node detect_and_parse: orchestrates bank detection, parsing, and persistence.

Doesn't access pandas/sqlite3 directly — delegates to parsers/ and db/repository.py
(Principle II of the constitution).
"""

from financial_planner.db import repository
from financial_planner.parsers import bradesco, inter
from financial_planner.parsers.detect import detect_bank
from financial_planner.parsers.reconcile import check_balance_reconciliation
from financial_planner.state import Bank, ImportResult

_PARSERS = {
    Bank.BRADESCO: bradesco.parse,
    Bank.INTER: inter.parse,
}


def detect_and_parse(path: str, db_path: str) -> ImportResult:
    """Detects the bank, imports the transactions, and reports the result.

    Raises UnrecognizedBankError (via detect_bank) if the file doesn't match any
    supported bank — never generates partial transactions in that case (FR-009).
    """
    bank = detect_bank(path)
    transactions = _PARSERS[bank](path)

    result = ImportResult(bank=bank, source_file=path)

    conn = repository.connect(db_path)
    try:
        for transaction in transactions:
            if repository.transaction_exists(conn, transaction.dedup_hash):
                result.transactions_skipped_duplicate += 1
                continue
            repository.insert_transaction(conn, transaction)
            result.transactions_imported += 1
    finally:
        conn.close()

    reconciliation, warnings = check_balance_reconciliation(path, bank)
    result.balance_reconciliation = reconciliation
    result.warnings.extend(warnings)

    return result
