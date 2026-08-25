import pytest

from financial_planner.nodes.ingest import detect_and_parse
from financial_planner.parsers import bradesco, inter
from financial_planner.parsers.detect import detect_bank
from financial_planner.parsers.reconcile import check_balance_reconciliation
from financial_planner.state import Bank, BalanceReconciliation, TransactionType, UnrecognizedBankError

BRADESCO_HAPPY_PATH = "tests/fixtures/bradesco/happy_path.csv"
BRADESCO_WRONG_BALANCE = "tests/fixtures/bradesco/wrong_balance.csv"
BRADESCO_ADMIN_LINE = "tests/fixtures/bradesco/admin_line_and_negative_balance.csv"
BRADESCO_SAME_DAY_SAME_AMOUNT = "tests/fixtures/bradesco/same_day_same_amount.csv"
INTER_HAPPY_PATH = "tests/fixtures/inter/happy_path.csv"
INTER_DESCENDING_ORDER = "tests/fixtures/inter/descending_order.csv"
INTER_SAME_DAY_SAME_AMOUNT = "tests/fixtures/inter/same_day_same_amount.csv"
UNRECOGNIZED_BANK = "tests/fixtures/unrecognized_bank.csv"


# --- User Story 1: import a statement from a supported bank ---------------------------


def test_parse_bradesco():
    transactions = bradesco.parse(BRADESCO_HAPPY_PATH)

    # 4 transaction lines in the file: 3 unique + 1 repeated in the
    # "Últimos Lancamentos" section (metadata, duplicated header, and "Total" footer
    # are ignored).
    assert len(transactions) == 4

    assert transactions[0].description_raw == "PIX RECEBIDO"
    assert transactions[0].type == TransactionType.INCOME
    assert transactions[0].amount == 1500.00

    assert transactions[1].description_raw == "COMPRA CARTAO SUPERMERCADO"
    assert transactions[1].type == TransactionType.EXPENSE
    assert transactions[1].amount == 250.75

    # The line repeated in the "Últimos Lancamentos" section produces the same dedup_hash.
    assert transactions[3].dedup_hash == transactions[2].dedup_hash


def test_parse_inter():
    transactions = inter.parse(INTER_HAPPY_PATH)

    assert len(transactions) == 3

    assert transactions[0].type == TransactionType.INCOME
    assert transactions[0].amount == 1500.00

    # A blank Descrição on the last line falls back to Histórico.
    assert transactions[2].description_raw == "Compra no débito"
    assert transactions[2].type == TransactionType.EXPENSE
    assert transactions[2].amount == 300.00


def test_detect_bank():
    assert detect_bank(BRADESCO_HAPPY_PATH) == Bank.BRADESCO
    assert detect_bank(INTER_HAPPY_PATH) == Bank.INTER


# --- User Story 2: reimport without duplicating ----------------------------------------


def test_reimport_skips_duplicates(tmp_path):
    db_path = str(tmp_path / "test.db")

    first = detect_and_parse(INTER_HAPPY_PATH, db_path)
    assert first.transactions_imported == 3
    assert first.transactions_skipped_duplicate == 0

    second = detect_and_parse(INTER_HAPPY_PATH, db_path)
    assert second.transactions_imported == 0
    assert second.transactions_skipped_duplicate == 3


def test_dedup_within_same_file(tmp_path):
    db_path = str(tmp_path / "test.db")

    result = detect_and_parse(BRADESCO_HAPPY_PATH, db_path)

    assert result.transactions_imported == 3
    assert result.transactions_skipped_duplicate == 1


# --- User Story 3: warning when parsing fails/doesn't reconcile -----------------------


def test_detect_unknown_bank():
    with pytest.raises(UnrecognizedBankError):
        detect_bank(UNRECOGNIZED_BANK)


def test_balance_reconciliation_ok():
    reconciliation, warnings = check_balance_reconciliation(BRADESCO_HAPPY_PATH, Bank.BRADESCO)

    assert reconciliation == BalanceReconciliation.OK
    assert warnings == []


def test_balance_reconciliation_mismatch():
    reconciliation, warnings = check_balance_reconciliation(BRADESCO_WRONG_BALANCE, Bank.BRADESCO)

    assert reconciliation == BalanceReconciliation.MISMATCH
    assert len(warnings) == 1


# --- Regression: cases found while validating against real statements (T028) ----------


def test_parse_bradesco_administrative_line_with_no_amount():
    """A line with Crédito and Débito both blank (e.g. 'COD. LANC. 0') must not crash."""
    transactions = bradesco.parse(BRADESCO_ADMIN_LINE)

    admin_tx = transactions[1]
    assert admin_tx.description_raw == "COD. LANC. 0"
    assert admin_tx.amount == 0.0


def test_balance_reconciliation_preserves_negative_balance_sign():
    """A negative balance (overdraft) must not be normalized to an absolute value."""
    reconciliation, warnings = check_balance_reconciliation(BRADESCO_ADMIN_LINE, Bank.BRADESCO)

    assert reconciliation == BalanceReconciliation.OK
    assert warnings == []


def test_balance_reconciliation_normalizes_descending_file_order():
    """Files with the most recent line first (the pattern observed on Inter) must
    reconcile normally — chronological order is normalized internally."""
    reconciliation, warnings = check_balance_reconciliation(INTER_DESCENDING_ORDER, Bank.INTER)

    assert reconciliation == BalanceReconciliation.OK
    assert warnings == []


# --- Regression: dedup hash collision on same date+description+amount (009) -----------
# See docs/decisions/dedup-hash-discriminator.md for the full rationale.


def test_bradesco_distinct_transactions_same_fields_get_different_hashes():
    """Two real transactions sharing date/description/amount but with different
    Docto. numbers must not collide — only literal file duplicates (same Docto. too)
    should collapse."""
    transactions = bradesco.parse(BRADESCO_SAME_DAY_SAME_AMOUNT)

    assert len(transactions) == 2
    assert transactions[0].dedup_hash != transactions[1].dedup_hash


def test_bradesco_same_day_same_amount_both_survive_import(tmp_path):
    db_path = str(tmp_path / "test.db")

    result = detect_and_parse(BRADESCO_SAME_DAY_SAME_AMOUNT, db_path)

    assert result.transactions_imported == 2
    assert result.transactions_skipped_duplicate == 0


def test_inter_distinct_transactions_same_fields_get_different_hashes():
    """Inter has no document number to disambiguate on, so two real same-day,
    same-description, same-amount transactions must be told apart by their position
    in the file instead of colliding."""
    transactions = inter.parse(INTER_SAME_DAY_SAME_AMOUNT)

    assert len(transactions) == 2
    assert transactions[0].dedup_hash != transactions[1].dedup_hash


def test_inter_same_day_same_amount_reimport_is_still_idempotent(tmp_path):
    """The occurrence-based discriminator must stay deterministic across reimports of
    the same file, or FR-006 (no duplicate on reimport) would regress."""
    db_path = str(tmp_path / "test.db")

    first = detect_and_parse(INTER_SAME_DAY_SAME_AMOUNT, db_path)
    assert first.transactions_imported == 2
    assert first.transactions_skipped_duplicate == 0

    second = detect_and_parse(INTER_SAME_DAY_SAME_AMOUNT, db_path)
    assert second.transactions_imported == 0
    assert second.transactions_skipped_duplicate == 2
