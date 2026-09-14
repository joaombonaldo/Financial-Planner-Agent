"""FastAPI interface tests (specs/015-fastapi-core-api "Testing strategy").

Every test runs the background graph call inline (`Settings.run_synchronously`), so
nothing here depends on thread timing or sleeps. Anything that would reach
categorize/generate_insights gets the existing FakeChatModel — never a real Ollama
call, same as every node test in this suite.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from financial_planner.db import repository
from financial_planner.interface import api
from financial_planner.interface.api import Settings, create_app, reset_run_registry
from financial_planner.state import Instrument
from tests.fixtures.categorization.builders import make_transaction, seed_transaction
from tests.fixtures.categorization.llm_double import FakeChatModel

MONTH_REF = "2026-08"
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        db_path=str(tmp_path / "test.db"),
        extracts_dir=str(tmp_path / "extracts"),
        run_synchronously=True,
    )


@pytest.fixture
def client(settings):
    reset_run_registry()
    with TestClient(create_app(settings)) as test_client:
        yield test_client
    reset_run_registry()


@pytest.fixture(autouse=True)
def no_real_llm(monkeypatch):
    """Both LLM entry points answer deterministically; a real Ollama is never hit."""
    categorizer_model = FakeChatModel("Alimentação|Mercado")
    insights_model = FakeChatModel("Resumo do mês.")
    monkeypatch.setattr(
        "financial_planner.categorization.llm_categorizer.get_chat_model",
        lambda: categorizer_model,
    )
    monkeypatch.setattr(
        "financial_planner.nodes.insights.get_chat_model", lambda: insights_model
    )
    return categorizer_model


def _seed(settings: Settings, dedup_hash: str, description: str, **kwargs) -> None:
    conn = repository.connect(settings.db_path)
    transaction = make_transaction(dedup_hash, description, **kwargs)
    seed_transaction(conn, transaction)
    conn.close()


def _confirm(settings: Settings, dedup_hash: str, category: str, subcategory: str | None) -> None:
    conn = repository.connect(settings.db_path)
    repository.update_transaction_category(conn, dedup_hash, category, subcategory, "high")
    conn.close()


def _upload(client: TestClient, fixture: str, filename: str | None = None) -> list[str]:
    source = FIXTURES / fixture
    response = client.post(
        f"/months/{MONTH_REF}/uploads",
        files={"files": (filename or source.name, source.read_bytes(), "text/csv")},
    )
    assert response.status_code == 201, response.text
    return response.json()["files"]


def _drive_to_completion(client: TestClient, max_items: int = 20) -> dict:
    """Answer every pending review item the way the CLI's operator would."""
    state = client.get(f"/months/{MONTH_REF}/run").json()
    for _ in range(max_items):
        if state["status"] != "pending_review":
            return state
        item = state["item"]
        action = "confirm_transfer" if item["is_transfer_candidate"] else "accept"
        response = client.post(f"/months/{MONTH_REF}/review", json={"action": action})
        assert response.status_code == 202, response.text
        state = client.get(f"/months/{MONTH_REF}/run").json()
    raise AssertionError(f"review never finished, last state: {state}")


# --- uploads ----------------------------------------------------------------------


def test_upload_saves_file_under_the_month_directory(client, settings):
    saved = _upload(client, "inter/happy_path.csv")

    assert len(saved) == 1
    path = Path(saved[0])
    assert path.parent == Path(settings.extracts_dir) / MONTH_REF
    assert path.read_bytes() == (FIXTURES / "inter/happy_path.csv").read_bytes()


def test_upload_rejects_path_traversal_filename(client, settings):
    response = client.post(
        f"/months/{MONTH_REF}/uploads",
        files={"files": ("../../evil.csv", b"x,y\n", "text/csv")},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_filename"
    escaped = Path(settings.extracts_dir).parent.parent / "evil.csv"
    assert not escaped.exists()


def test_upload_rejects_disallowed_extension(client):
    response = client.post(
        f"/months/{MONTH_REF}/uploads",
        files={"files": ("statement.txt", b"whatever", "text/plain")},
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_file_type"


def test_upload_rejects_oversized_file(tmp_path):
    small_cap = Settings(
        db_path=str(tmp_path / "test.db"),
        extracts_dir=str(tmp_path / "extracts"),
        max_upload_bytes=1024,
        run_synchronously=True,
    )
    with TestClient(create_app(small_cap)) as client:
        response = client.post(
            f"/months/{MONTH_REF}/uploads",
            files={"files": ("big.csv", b"a" * 2048, "text/csv")},
        )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"
    assert not (tmp_path / "extracts" / MONTH_REF / "big.csv").exists()


def test_upload_rejects_invalid_month_ref(client):
    response = client.post(
        "/months/2026-13/uploads", files={"files": ("a.csv", b"x", "text/csv")}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


# --- run / review -----------------------------------------------------------------


def test_get_run_before_anything_started(client):
    assert client.get(f"/months/{MONTH_REF}/run").json() == {"status": "not_started"}


def test_run_then_review_until_completed(client, settings):
    saved = _upload(client, "inter/happy_path.csv")

    started = client.post(f"/months/{MONTH_REF}/run", json={"files": saved})
    assert started.status_code == 202

    pending = client.get(f"/months/{MONTH_REF}/run").json()
    assert pending["status"] == "pending_review"
    # Exactly nodes/review.py:_build_payload's shape, including feature 014's
    # `instrument`.
    assert pending["item"]["transaction"]["instrument"] == "debit"
    assert "suggested_subcategories" in pending["item"]

    final = _drive_to_completion(client)
    assert final["status"] == "completed"
    assert final["report"]["month_ref"] == MONTH_REF
    assert final["report"]["transaction_count"] == 3


def test_run_is_a_noop_while_the_month_is_already_processing(client, settings, monkeypatch):
    api._set_state(MONTH_REF, api.RunState(status="processing"))

    def explode(_db_path):
        raise AssertionError("a second worker must not be spawned")

    monkeypatch.setattr(api, "build_graph", explode)

    response = client.post(f"/months/{MONTH_REF}/run", json={"files": []})

    assert response.status_code == 202
    assert response.json() == {"status": "processing"}


def test_run_rejects_a_file_outside_the_extracts_directory(client, tmp_path):
    stray = tmp_path / "elsewhere.csv"
    stray.write_text("x")

    response = client.post(f"/months/{MONTH_REF}/run", json={"files": [str(stray)]})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_path"


def test_review_without_a_pending_item_is_a_conflict(client):
    response = client.post(f"/months/{MONTH_REF}/review", json={"action": "accept"})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "no_pending_review"


def test_review_correct_applies_the_given_category(client, settings):
    saved = _upload(client, "inter/happy_path.csv")
    client.post(f"/months/{MONTH_REF}/run", json={"files": saved})

    state = client.get(f"/months/{MONTH_REF}/run").json()
    assert state["status"] == "pending_review"
    target = state["item"]["transaction"]["description_raw"]

    response = client.post(
        f"/months/{MONTH_REF}/review",
        json={"action": "correct", "category": "Lazer", "subcategory": "Restaurante/Bar"},
    )
    assert response.status_code == 202

    listed = client.get(f"/months/{MONTH_REF}/transactions").json()
    corrected = [t for t in listed if t["description_raw"] == target]
    assert corrected and corrected[0]["category"] == "Lazer"
    assert corrected[0]["subcategory"] == "Restaurante/Bar"
    assert corrected[0]["confidence"] == "high"


def test_a_failing_run_surfaces_an_error_instead_of_hanging(client, monkeypatch, caplog):
    """The background wrapper's mandatory catch-all: an exception must land in the
    registry as `{"status": "error"}`, never leave the poll stuck at "processing"."""

    def boom(_db_path):
        raise RuntimeError("secret detail /Users/someone/private.db")

    monkeypatch.setattr(api, "build_graph", boom)

    started = client.post(f"/months/{MONTH_REF}/run", json={"files": []})
    assert started.status_code == 202

    state = client.get(f"/months/{MONTH_REF}/run").json()
    assert state["status"] == "error"
    assert state["message"] == "Processing failed. See the server log for details."
    # Sanitized for the client, full traceback server-side only.
    assert "private.db" not in state["message"]


# --- months / report / transactions -------------------------------------------------


# --- budget goals ----------------------------------------------------------------------


def test_default_budget_starts_empty(client):
    assert client.get("/budget").json() == {}


def test_put_default_budget_replaces_the_whole_set(client):
    first = client.put("/budget", json={"goals": {"Moradia": 1500.0, "Lazer": 300.0}})
    assert first.json() == {"Moradia": 1500.0, "Lazer": 300.0}

    # A second PUT replaces, it doesn't merge -- "Lazer" disappears.
    second = client.put("/budget", json={"goals": {"Moradia": 1600.0}})
    assert second.json() == {"Moradia": 1600.0}
    assert client.get("/budget").json() == {"Moradia": 1600.0}


def test_put_default_budget_rejects_a_negative_goal(client):
    response = client.put("/budget", json={"goals": {"Moradia": -1.0}})
    assert response.status_code == 422


def test_month_budget_overrides_the_default(client):
    client.put("/budget", json={"goals": {"Lazer": 300.0, "Transporte": 100.0}})
    client.put(f"/months/{MONTH_REF}/budget", json={"goals": {"Lazer": 800.0}})

    month_budget = client.get(f"/months/{MONTH_REF}/budget").json()
    assert month_budget["overrides"] == {"Lazer": 800.0}
    assert month_budget["effective"] == {"Lazer": 800.0, "Transporte": 100.0}

    # A different, unrelated month never sees this month's override.
    other = client.get("/months/2026-07/budget").json()
    assert other["overrides"] == {}
    assert other["effective"] == {"Lazer": 300.0, "Transporte": 100.0}


def test_month_budget_feeds_into_the_report(client, settings):
    client.put("/budget", json={"goals": {"Alimentação": 500.0}})
    client.put(f"/months/{MONTH_REF}/budget", json={"goals": {"Alimentação": 900.0}})
    _seed(settings, "hash-1", "Supermercado ABC", amount=100.0)
    _confirm(settings, "hash-1", "Alimentação", "Mercado")

    report = client.get(f"/months/{MONTH_REF}/report").json()
    entry = next(e for e in report["budget_report"] if e["category"] == "Alimentação")

    assert entry["goal"] == 900.0


def test_list_months_is_derived_from_the_transactions(client, settings):
    _seed(settings, "hash-1", "Supermercado ABC")
    _confirm(settings, "hash-1", "Alimentação", "Mercado")
    _seed(settings, "hash-2", "Loja Desconhecida")
    # list_pending_review matches on confidence != 'high'; a row with NULL
    # confidence hasn't been categorized yet, so it isn't pending review.
    _conn = repository.connect(settings.db_path)
    repository.update_transaction_category(_conn, "hash-2", "Outros", None, "low")
    _conn.close()

    months = client.get("/months").json()

    assert months == [
        {"month_ref": MONTH_REF, "transaction_count": 2, "has_pending_review": True}
    ]


def test_report_is_recomputed_from_current_data(client, settings):
    _seed(settings, "hash-1", "Supermercado ABC", amount=100.0)
    _confirm(settings, "hash-1", "Alimentação", "Mercado")

    report = client.get(f"/months/{MONTH_REF}/report").json()

    assert report["month_ref"] == MONTH_REF
    assert report["total_expense"] == 100.0
    assert report["transaction_count"] == 1

    # A manual edit must show up on the very next call — never cached.
    client.patch("/transactions/hash-1", json={"deleted": True})
    assert client.get(f"/months/{MONTH_REF}/report").json()["transaction_count"] == 0


def test_list_transactions_filters(client, settings):
    _seed(settings, "hash-debit", "Supermercado ABC")
    _confirm(settings, "hash-debit", "Alimentação", "Mercado")
    _seed(settings, "hash-credit", "Livraria", instrument=Instrument.CREDIT)
    _confirm(settings, "hash-credit", "Lazer", "Livros")

    all_rows = client.get(f"/months/{MONTH_REF}/transactions").json()
    assert {row["dedup_hash"] for row in all_rows} == {"hash-debit", "hash-credit"}

    credit = client.get(
        f"/months/{MONTH_REF}/transactions", params={"instrument": "credit"}
    ).json()
    assert [row["dedup_hash"] for row in credit] == ["hash-credit"]

    by_category = client.get(
        f"/months/{MONTH_REF}/transactions", params={"category": "Alimentação"}
    ).json()
    assert [row["dedup_hash"] for row in by_category] == ["hash-debit"]


def test_list_transactions_include_deleted(client, settings):
    _seed(settings, "hash-1", "Não é meu")
    client.patch("/transactions/hash-1", json={"deleted": True})

    assert client.get(f"/months/{MONTH_REF}/transactions").json() == []

    with_deleted = client.get(
        f"/months/{MONTH_REF}/transactions", params={"include_deleted": True}
    ).json()
    assert [row["dedup_hash"] for row in with_deleted] == ["hash-1"]
    assert with_deleted[0]["deleted_at"] is not None


# --- manual create --------------------------------------------------------------------


def test_create_transaction(client):
    response = client.post(
        "/transactions",
        json={
            "date": "2026-08-15",
            "description_raw": "Feira livre",
            "account": "inter",
            "type": "expense",
            "amount": 45.0,
            "category": "Alimentação",
            "subcategory": "Mercado",
            "instrument": "debit",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["description_raw"] == "Feira livre"
    assert body["month_ref"] == "2026-08"
    assert body["confidence"] == "high"
    assert body["dedup_hash"]


def test_created_transaction_appears_in_its_derived_month(client):
    client.post(
        "/transactions",
        json={
            "date": "2026-03-01",
            "description_raw": "Ajuste",
            "account": "bradesco",
            "type": "expense",
            "amount": 10.0,
            "category": "Outros",
            "instrument": "debit",
        },
    )

    listed = client.get("/months/2026-03/transactions").json()
    assert [row["description_raw"] for row in listed] == ["Ajuste"]


def test_create_transaction_rejects_a_non_positive_amount(client):
    response = client.post(
        "/transactions",
        json={
            "date": "2026-08-15",
            "description_raw": "Feira livre",
            "account": "inter",
            "type": "expense",
            "amount": 0,
            "category": "Alimentação",
            "instrument": "debit",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_create_transaction_rejects_an_empty_description(client):
    response = client.post(
        "/transactions",
        json={
            "date": "2026-08-15",
            "description_raw": "",
            "account": "inter",
            "type": "expense",
            "amount": 10.0,
            "category": "Outros",
            "instrument": "debit",
        },
    )

    assert response.status_code == 422


# --- manual edit ---------------------------------------------------------------------


def test_patch_recategorizes(client, settings):
    _seed(settings, "hash-1", "Supermercado ABC")

    response = client.patch(
        "/transactions/hash-1", json={"category": "Alimentação", "subcategory": "Mercado"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["category"] == "Alimentação"
    assert body["subcategory"] == "Mercado"
    assert body["confidence"] == "high"


def test_patch_soft_deletes_and_restores(client, settings):
    _seed(settings, "hash-1", "Não é meu")

    deleted = client.patch("/transactions/hash-1", json={"deleted": True}).json()
    assert deleted["deleted_at"] is not None

    restored = client.patch("/transactions/hash-1", json={"deleted": False}).json()
    assert restored["deleted_at"] is None


def test_patch_unknown_hash_uses_the_error_envelope(client):
    response = client.patch("/transactions/nope", json={"deleted": True})

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "not_found", "message": "Transaction not found"}
    }


def test_patch_with_both_actions_is_a_validation_error(client, settings):
    _seed(settings, "hash-1", "Supermercado ABC")

    response = client.patch(
        "/transactions/hash-1", json={"category": "Alimentação", "deleted": True}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_body_validation_error_uses_the_error_envelope(client):
    response = client.post(f"/months/{MONTH_REF}/review", json={"action": "nonsense"})

    assert response.status_code == 422
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message"}
    assert body["error"]["code"] == "validation_error"


def test_unexpected_error_is_sanitized_into_the_envelope(settings, monkeypatch, tmp_path):
    _seed(settings, "hash-1", "Supermercado ABC")

    def boom(*_args, **_kwargs):
        raise RuntimeError("leaky detail /Users/someone/private.db")

    monkeypatch.setattr(api.transactions_node, "soft_delete", boom)

    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        response = client.patch("/transactions/hash-1", json={"deleted": True})

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "private.db" not in response.json()["error"]["message"]


# --- CORS ------------------------------------------------------------------------------


def test_cors_allows_only_the_frontend_origin(client):
    allowed = client.get("/months", headers={"Origin": "http://localhost:5173"})
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"

    other = client.get("/months", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in other.headers


def test_cors_never_uses_a_wildcard():
    assert "*" not in api.ALLOWED_ORIGINS
    assert api.ALLOWED_ORIGINS == ["http://localhost:5173"]


# --- taxonomy ----------------------------------------------------------------------------


def test_taxonomy_returns_the_full_category_tree(client):
    tree = client.get("/taxonomy").json()

    assert "Alimentação" in tree
    assert "Mercado" in tree["Alimentação"]
    # Categories with no subcategories (e.g. transfers, catch-all) still appear,
    # just with an empty list — the picker needs to know they're valid choices too.
    assert tree["Transferência interna"] == []


def test_taxonomy_needs_no_month_or_db_state(client):
    # Static config — works even with no month ever processed.
    response = client.get("/taxonomy")
    assert response.status_code == 200
