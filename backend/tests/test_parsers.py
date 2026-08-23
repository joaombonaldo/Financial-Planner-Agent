import pytest

from financial_planner.nodes.ingest import detect_and_parse
from financial_planner.parsers import bradesco, inter
from financial_planner.parsers.detect import detect_bank
from financial_planner.parsers.reconcile import check_balance_reconciliation
from financial_planner.state import Bank, BalanceReconciliation, TransactionType, UnrecognizedBankError

BRADESCO_HAPPY_PATH = "tests/fixtures/bradesco/happy_path.csv"
BRADESCO_WRONG_BALANCE = "tests/fixtures/bradesco/wrong_balance.csv"
BRADESCO_ADMIN_LINE = "tests/fixtures/bradesco/admin_line_and_negative_balance.csv"
INTER_HAPPY_PATH = "tests/fixtures/inter/happy_path.csv"
INTER_DESCENDING_ORDER = "tests/fixtures/inter/descending_order.csv"
UNRECOGNIZED_BANK = "tests/fixtures/unrecognized_bank.csv"


# --- User Story 1: importar extrato de um banco suportado ---------------------------


def test_parse_bradesco():
    transactions = bradesco.parse(BRADESCO_HAPPY_PATH)

    # 4 linhas de transação no arquivo: 3 únicas + 1 repetida na seção
    # "Últimos Lancamentos" (metadado, header duplicado e rodapé "Total" são ignorados).
    assert len(transactions) == 4

    assert transactions[0].description_raw == "PIX RECEBIDO"
    assert transactions[0].type == TransactionType.INCOME
    assert transactions[0].amount == 1500.00

    assert transactions[1].description_raw == "COMPRA CARTAO SUPERMERCADO"
    assert transactions[1].type == TransactionType.EXPENSE
    assert transactions[1].amount == 250.75

    # A linha repetida na seção "Últimos Lancamentos" gera o mesmo dedup_hash.
    assert transactions[3].dedup_hash == transactions[2].dedup_hash


def test_parse_inter():
    transactions = inter.parse(INTER_HAPPY_PATH)

    assert len(transactions) == 3

    assert transactions[0].type == TransactionType.INCOME
    assert transactions[0].amount == 1500.00

    # Descrição vazia na última linha usa Histórico como fallback.
    assert transactions[2].description_raw == "Compra no débito"
    assert transactions[2].type == TransactionType.EXPENSE
    assert transactions[2].amount == 300.00


def test_detect_bank():
    assert detect_bank(BRADESCO_HAPPY_PATH) == Bank.BRADESCO
    assert detect_bank(INTER_HAPPY_PATH) == Bank.INTER


# --- User Story 2: reimportar sem duplicar --------------------------------------------


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


# --- User Story 3: aviso quando o parsing falha/não reconcilia ------------------------


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


# --- Regressão: casos encontrados na validação com extratos reais (T028) --------------


def test_parse_bradesco_administrative_line_with_no_amount():
    """Linha com Crédito e Débito ambos em branco (ex.: 'COD. LANC. 0') não deve crashar."""
    transactions = bradesco.parse(BRADESCO_ADMIN_LINE)

    admin_tx = transactions[1]
    assert admin_tx.description_raw == "COD. LANC. 0"
    assert admin_tx.amount == 0.0


def test_balance_reconciliation_preserves_negative_balance_sign():
    """Saldo negativo (cheque especial) não pode ser normalizado para valor absoluto."""
    reconciliation, warnings = check_balance_reconciliation(BRADESCO_ADMIN_LINE, Bank.BRADESCO)

    assert reconciliation == BalanceReconciliation.OK
    assert warnings == []


def test_balance_reconciliation_normalizes_descending_file_order():
    """Arquivos com a linha mais recente primeiro (padrão observado no Inter) devem
    reconciliar normalmente — a ordem cronológica é normalizada internamente."""
    reconciliation, warnings = check_balance_reconciliation(INTER_DESCENDING_ORDER, Bank.INTER)

    assert reconciliation == BalanceReconciliation.OK
    assert warnings == []
