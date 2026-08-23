"""Node detect_and_parse: orquestra detecção de banco, parsing e persistência.

Não acessa pandas/sqlite3 diretamente — delega para parsers/ e db/repository.py
(Princípio II da constituição).
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
    """Detecta o banco, importa as transações e reporta o resultado.

    Levanta UnrecognizedBankError (via detect_bank) se o arquivo não corresponder a
    nenhum banco suportado — nunca gera transações parciais nesse caso (FR-009).
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
