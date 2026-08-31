"""Feature 013 - credit-card fatura (PDF) ingestion as a separate stream.

Deterministic, no Ollama, no network. Row extraction, installment parsing and
fatura metadata are checked against committed anonymized text fixtures; detection
routing and dedup idempotency go through a minimal generated PDF so the real
extension-sniff -> pdfplumber -> issuer-match -> adapter path is exercised.
"""

from pathlib import Path

import pytest

from financial_planner.db import repository
from financial_planner.nodes.ingest import detect_and_parse
from financial_planner.parsers import credit_card_bradesco, credit_card_inter
from financial_planner.parsers.detect import detect_bank, detect_instrument
from financial_planner.state import (
    Bank,
    Instrument,
    TransactionType,
    UnrecognizedBankError,
)
from tests.fixtures.credit_card.pdf_builder import write_pdf

_FIX = Path(__file__).parent / "fixtures" / "credit_card"
BRADESCO_TEXT = (_FIX / "bradesco_fatura.txt").read_text(encoding="utf-8")
INTER_TEXT = (_FIX / "inter_fatura.txt").read_text(encoding="utf-8")


# --- Bradesco: row extraction + installments + metadata ------------------------------


def test_bradesco_row_extraction():
    txs = credit_card_bradesco.parse_text_fixture(BRADESCO_TEXT)

    assert [t.description_raw for t in txs] == [
        "PAGTO. POR DEB EM C/C",
        "IOF S/ TRANS INTER REAIS",
        "HOTEL VILA MICHEL BENTO",
        "NittioLtda Tubarao",
        "ANTHROPIC* CLAUDE SUB",
    ]
    # every row is a credit-stream row, dated by purchase date, tagged with the fatura
    assert {t.instrument for t in txs} == {Instrument.CREDIT}
    assert {t.fatura_ref for t in txs} == {"2026-09"}
    assert {t.account for t in txs} == {Bank.BRADESCO}


def test_bradesco_payment_line_is_income_rest_are_expense():
    txs = credit_card_bradesco.parse_text_fixture(BRADESCO_TEXT)
    assert txs[0].type == TransactionType.INCOME and txs[0].amount == 638.06
    assert all(t.type == TransactionType.EXPENSE for t in txs[1:])


def test_bradesco_installment_marker_parsed_and_stripped():
    txs = credit_card_bradesco.parse_text_fixture(BRADESCO_TEXT)
    hotel = next(t for t in txs if t.description_raw.startswith("HOTEL"))
    assert (hotel.installment_index, hotel.installment_count) == (3, 6)
    assert "03/06" not in hotel.description_raw


def test_bradesco_year_inferred_from_due_date():
    txs = credit_card_bradesco.parse_text_fixture(BRADESCO_TEXT)
    hotel = next(t for t in txs if t.description_raw.startswith("HOTEL"))
    # purchase "30/05" on a fatura due 04/09/2026 -> 2026-05, grouped by purchase month
    assert hotel.date.isoformat() == "2026-05-30"
    assert hotel.month_ref == "2026-05"


def test_bradesco_fatura_metadata():
    meta = credit_card_bradesco.parse_metadata(BRADESCO_TEXT)
    assert meta.total == 700.05
    assert meta.due_date.isoformat() == "2026-09-04"
    assert meta.fatura_ref == "2026-09"
    assert meta.closing_date.isoformat() == "2026-09-23"
    assert meta.previous_balance == 638.06


def test_bradesco_purchases_reconcile_against_fatura_total():
    meta = credit_card_bradesco.parse_metadata(BRADESCO_TEXT)
    txs = credit_card_bradesco.parse_text_fixture(BRADESCO_TEXT)
    spent = sum(t.amount for t in txs if t.type == TransactionType.EXPENSE)
    assert round(spent, 2) == meta.total


# --- Inter: row extraction + installments + metadata --------------------------------


def test_inter_row_extraction_skips_subtotals_fx_detail_and_next_fatura():
    txs = credit_card_inter.parse_statement_text(INTER_TEXT)
    descriptions = [t.description_raw for t in txs]

    assert descriptions == [
        "PAGTO DEBITO AUTOMATICO",
        "Google YouTubePremium",
        "AMAZON BR",
        "CP PARC DUO GOURMET",
        "GIANLUCA - DINARTE",
        "WWW.WORKHUMAN.COM",
        "IOF INTERNACIONAL",
        "AMAZONMKTPLC*AHDASILVA",
        "SABOR DE LUNA",
        "SABOR DE LUNA",
    ]
    # "Total CARTÃO ...", the USD detail lines, and the "Próxima fatura" installment
    # (no date prefix) are all excluded.
    assert "Total" not in " ".join(descriptions)


def test_inter_payment_line_marked_income():
    txs = credit_card_inter.parse_statement_text(INTER_TEXT)
    assert txs[0].type == TransactionType.INCOME and txs[0].amount == 1217.08
    assert all(t.type == TransactionType.EXPENSE for t in txs[1:])


def test_inter_installment_markers():
    txs = credit_card_inter.parse_statement_text(INTER_TEXT)
    by_desc = {t.description_raw: t for t in txs}
    assert (by_desc["AMAZON BR"].installment_index, by_desc["AMAZON BR"].installment_count) == (6, 7)
    assert (by_desc["CP PARC DUO GOURMET"].installment_index, by_desc["CP PARC DUO GOURMET"].installment_count) == (5, 5)
    assert (by_desc["AMAZONMKTPLC*AHDASILVA"].installment_index, by_desc["AMAZONMKTPLC*AHDASILVA"].installment_count) == (1, 11)
    assert "(Parcela" not in by_desc["AMAZON BR"].description_raw


def test_inter_full_date_and_purchase_month_grouping():
    txs = credit_card_inter.parse_statement_text(INTER_TEXT)
    amazon = next(t for t in txs if t.description_raw == "AMAZON BR")
    assert amazon.date.isoformat() == "2026-03-06"
    assert amazon.month_ref == "2026-03"


def test_inter_fatura_metadata():
    meta = credit_card_inter.parse_metadata(INTER_TEXT)
    assert meta.total == 3122.62
    assert meta.due_date.isoformat() == "2026-09-02"
    assert meta.fatura_ref == "2026-09"
    assert meta.closing_date.isoformat() == "2026-09-25"
    assert meta.previous_balance == 0.0


def test_inter_same_day_same_merchant_distinct_amounts_get_distinct_hashes():
    txs = credit_card_inter.parse_statement_text(INTER_TEXT)
    sabor = [t for t in txs if t.description_raw == "SABOR DE LUNA"]
    assert len(sabor) == 2
    assert sabor[0].amount != sabor[1].amount
    assert sabor[0].dedup_hash != sabor[1].dedup_hash


# --- Detection routing (real PDF path) ---------------------------------------------


def test_detects_bradesco_fatura_pdf(tmp_path):
    pdf = write_pdf(tmp_path / "b.pdf", BRADESCO_TEXT)
    assert detect_bank(pdf) == Bank.BRADESCO
    assert detect_instrument(pdf) == Instrument.CREDIT


def test_detects_inter_fatura_pdf_even_with_nul_padding(tmp_path):
    pdf = write_pdf(tmp_path / "i.pdf", INTER_TEXT, leading_nul=4096)
    assert detect_bank(pdf) == Bank.INTER
    assert detect_instrument(pdf) == Instrument.CREDIT


def test_unrecognized_pdf_is_rejected(tmp_path):
    pdf = write_pdf(tmp_path / "x.pdf", "Some unrelated document\n01/01/2026 nothing 10,00")
    with pytest.raises(UnrecognizedBankError):
        detect_bank(pdf)


# --- Ingestion: credit rows land with instrument + fatura_ref, idempotent -----------


def test_ingest_bradesco_fatura_pdf_persists_credit_rows(tmp_path):
    db_path = str(tmp_path / "t.db")
    pdf = write_pdf(tmp_path / "b.pdf", BRADESCO_TEXT)

    result = detect_and_parse(pdf, db_path)
    assert result.instrument == Instrument.CREDIT
    assert result.transactions_imported == 5

    conn = repository.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT instrument, fatura_ref FROM transactions"
        ).fetchall()
        assert rows and all(r[0] == "credit" and r[1] == "2026-09" for r in rows)

        # credit rows do NOT leak into the debit stream the report/budget read
        assert repository.list_transactions_by_month(conn, "2026-08") == []
        # ...but are reachable via the credit queries
        assert len(repository.list_credit_transactions_by_fatura_ref(conn, "2026-09")) == 5
        assert len(repository.list_credit_transactions_by_month(conn, "2026-05")) == 1
    finally:
        conn.close()


def test_ingest_inter_fatura_pdf_is_idempotent_on_reimport(tmp_path):
    db_path = str(tmp_path / "t.db")
    pdf = write_pdf(tmp_path / "i.pdf", INTER_TEXT, leading_nul=2048)

    first = detect_and_parse(pdf, db_path)
    assert first.transactions_imported == 10
    assert first.transactions_skipped_duplicate == 0

    second = detect_and_parse(pdf, db_path)
    assert second.transactions_imported == 0
    assert second.transactions_skipped_duplicate == 10
