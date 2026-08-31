from langgraph.types import Command

from financial_planner.db import repository
from tests.fixtures.review.builders import seed_categorized_transaction
from tests.fixtures.review.graph_harness import build_review_only_graph, drive_review

MONTH_REF = "2026-08"


def _category_row(db_path: str, dedup_hash: str) -> tuple:
    conn = repository.connect(db_path)
    row = conn.execute(
        "SELECT category, subcategory, confidence FROM transactions WHERE dedup_hash = ?",
        (dedup_hash,),
    ).fetchone()
    conn.close()
    return row


# --- User Story 1: review and correct medium/low confidence -----------------------------


def test_review_accept_suggestion(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    seed_categorized_transaction(
        conn, "hash-1", "Supermercado XYZ", category="Alimentação", subcategory="Mercado", confidence="medium"
    )
    conn.close()

    graph = build_review_only_graph(db_path)
    payloads = drive_review(graph, "thread-1", MONTH_REF, db_path, answers=["aceitar"])

    assert len(payloads) == 1
    assert payloads[0]["transaction"]["description_raw"] == "Supermercado XYZ"
    assert _category_row(db_path, "hash-1") == ("Alimentação", "Mercado", "high")


def test_review_correct_with_new_category(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    seed_categorized_transaction(conn, "hash-2", "Estabelecimento Genérico", category="Outros", confidence="low")
    conn.close()

    graph = build_review_only_graph(db_path)
    drive_review(graph, "thread-2", MONTH_REF, db_path, answers=["Transporte|Uber/99"])

    assert _category_row(db_path, "hash-2") == ("Transporte", "Uber/99", "high")


def test_review_no_pending_items_never_interrupts(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    seed_categorized_transaction(
        conn, "hash-3", "Uber", category="Transporte", subcategory="Uber/99", confidence="high"
    )
    conn.close()

    graph = build_review_only_graph(db_path)
    payloads = drive_review(graph, "thread-3", MONTH_REF, db_path, answers=[])

    assert payloads == []
    assert _category_row(db_path, "hash-3") == ("Transporte", "Uber/99", "high")


def test_review_rejects_invalid_category_and_reasks(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    seed_categorized_transaction(conn, "hash-4", "Loja Nova", category="Outros", confidence="low")
    conn.close()

    graph = build_review_only_graph(db_path)
    payloads = drive_review(
        graph,
        "thread-4",
        MONTH_REF,
        db_path,
        answers=["Categoria Que Não Existe", "Compras|Roupas/Calçados"],
    )

    assert len(payloads) == 2
    assert "error" not in payloads[0]
    assert "error" in payloads[1]
    assert _category_row(db_path, "hash-4") == ("Compras", "Roupas/Calçados", "high")


# --- Feature 008: list valid subcategories while reviewing -------------------------------


def test_review_payload_lists_valid_subcategories_for_suggested_category(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    seed_categorized_transaction(
        conn, "hash-7", "Aluguel Imobiliaria", category="Moradia", confidence="low"
    )
    conn.close()

    graph = build_review_only_graph(db_path)
    payloads = drive_review(graph, "thread-7", MONTH_REF, db_path, answers=["aceitar"])

    assert payloads[0]["suggested_subcategories"] == [
        "Aluguel/Financiamento",
        "Condomínio",
        "Energia",
        "Água",
        "Internet",
        "Gás",
    ]


def test_review_payload_has_no_subcategories_for_category_without_any(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    seed_categorized_transaction(conn, "hash-8", "Loja Nova", category="Outros", confidence="low")
    conn.close()

    graph = build_review_only_graph(db_path)
    payloads = drive_review(graph, "thread-8", MONTH_REF, db_path, answers=["aceitar"])

    assert payloads[0]["suggested_subcategories"] == []


# --- User Story 2: confirm or reject transfer candidates ---------------------------------


def test_review_confirm_transfer(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    seed_categorized_transaction(
        conn, "hash-5", "PIX ENVIADO", category="Transferência interna", confidence="medium"
    )
    conn.close()

    graph = build_review_only_graph(db_path)
    payloads = drive_review(graph, "thread-5", MONTH_REF, db_path, answers=["confirmar"])

    assert payloads[0]["is_transfer_candidate"] is True
    assert _category_row(db_path, "hash-5") == ("Transferência interna", None, "high")


def test_review_reject_transfer_with_new_category(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    seed_categorized_transaction(
        conn, "hash-6", "PIX ENVIADO", category="Transferência interna", confidence="medium"
    )
    conn.close()

    graph = build_review_only_graph(db_path)
    drive_review(
        graph, "thread-6", MONTH_REF, db_path, answers=["Alimentação|Restaurante/Delivery"]
    )

    assert _category_row(db_path, "hash-6") == ("Alimentação", "Restaurante/Delivery", "high")


# --- User Story 3: resume an interrupted session without losing progress -----------------


def _seed_three_pending(conn):
    seed_categorized_transaction(conn, "hash-a", "Item A", category="Outros", confidence="low")
    seed_categorized_transaction(conn, "hash-b", "Item B", category="Outros", confidence="low")
    seed_categorized_transaction(conn, "hash-c", "Item C", category="Outros", confidence="low")


def test_review_partial_session_persists_immediately(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    _seed_three_pending(conn)
    conn.close()

    graph = build_review_only_graph(db_path)
    config = {"configurable": {"thread_id": "thread-partial"}}

    result = graph.invoke(
        {"source_files": [], "month_ref": MONTH_REF, "db_path": db_path}, config=config
    )
    first_hash = result["__interrupt__"][0].value["transaction"]["description_raw"]
    assert first_hash == "Item A"

    # Decide the first item and "stop" — don't keep advancing the graph.
    graph.invoke(Command(resume="Transporte|Uber/99"), config=config)

    assert _category_row(db_path, "hash-a") == ("Transporte", "Uber/99", "high")
    # The other two haven't been touched yet.
    assert _category_row(db_path, "hash-b")[2] != "high"
    assert _category_row(db_path, "hash-c")[2] != "high"


def test_review_resume_does_not_reask_decided_items(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = repository.connect(db_path)
    _seed_three_pending(conn)
    conn.close()

    graph = build_review_only_graph(db_path)
    config = {"configurable": {"thread_id": "thread-resume"}}

    graph.invoke({"source_files": [], "month_ref": MONTH_REF, "db_path": db_path}, config=config)
    # Decide the first item (Item A).
    result = graph.invoke(Command(resume="Transporte|Uber/99"), config=config)

    # "Resume" with the same thread_id: the next interrupt should already be the second item.
    next_payload = result["__interrupt__"][0].value
    assert next_payload["transaction"]["description_raw"] == "Item B"
    assert _category_row(db_path, "hash-a") == ("Transporte", "Uber/99", "high")
