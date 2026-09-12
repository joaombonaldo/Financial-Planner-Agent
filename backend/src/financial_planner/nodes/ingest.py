"""Node detect_and_parse: orchestrates bank/instrument detection, parsing, persistence.

Doesn't access pandas/sqlite3 directly — delegates to parsers/ and db/repository.py
(Principle II of the constitution).

Two streams share this path (see docs/decisions/credit-card-stream.md):
- CSV debit/PIX extracts -> ``instrument='debit'``, balance reconciliation runs.
- Credit-card fatura PDFs -> ``instrument='credit'``, no running-balance column to
  reconcile; each row already carries its ``fatura_ref``. Dedup uses the credit
  discriminator built in ``parsers.credit_card_common`` (no ``Docto.`` on a fatura).
"""

from financial_planner.db import repository
from financial_planner.parsers import (
    bradesco,
    credit_card_bradesco,
    credit_card_inter,
    inter,
)
from financial_planner.parsers.detect import detect_bank, detect_instrument
from financial_planner.parsers.reconcile import check_balance_reconciliation
from financial_planner.state import Bank, ImportResult, Instrument

_PARSERS = {
    (Bank.BRADESCO, Instrument.DEBIT): bradesco.parse,
    (Bank.INTER, Instrument.DEBIT): inter.parse,
    (Bank.BRADESCO, Instrument.CREDIT): credit_card_bradesco.parse,
    (Bank.INTER, Instrument.CREDIT): credit_card_inter.parse,
}


def detect_and_parse(path: str, db_path: str) -> ImportResult:
    """Detects the bank and instrument, imports the transactions, reports the result.

    Raises UnrecognizedBankError (via detect_bank) if the file doesn't match any
    supported bank — never generates partial transactions in that case (FR-009).
    """
    bank = detect_bank(path)
    instrument = detect_instrument(path)
    transactions = _PARSERS[(bank, instrument)](path)

    result = ImportResult(bank=bank, source_file=path, instrument=instrument)

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

    if instrument is Instrument.DEBIT:
        reconciliation, warnings = check_balance_reconciliation(path, bank)
        result.balance_reconciliation = reconciliation
        result.warnings.extend(warnings)

    return result
