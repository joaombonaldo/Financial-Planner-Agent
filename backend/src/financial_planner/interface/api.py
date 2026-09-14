"""FastAPI interface over the same graph/nodes `interface/cli.py` drives.

Second interface, not a replacement: `cli.py` is untouched, and this module holds
to the same rule it does — an interface never imports `db/repository.py`, it calls
`graph.invoke()` / a `nodes/*.py` function and does nothing but translate between
HTTP and those (specs/015-fastapi-core-api "Architecture"). The manual-edit writes
live in `nodes/transactions.py`, the browsing reads in `nodes/queries.py`.

HITL over HTTP is polling, not push: `POST .../run` and `POST .../review` hand the
blocking `graph.invoke()` call to a background worker and return `202` immediately;
`GET .../run` reads the in-memory run-state registry below. `POST .../run` is safe
to repeat for the same month — `detect_and_parse` is dedup-idempotent and
`categorize` skips already-categorized transactions (commit 1f15917), so a repeat
call fast-forwards to wherever the thread actually is.

Background-execution mechanism: a module-level `ThreadPoolExecutor`, not
`BackgroundTasks`. `graph.invoke()` is a long blocking *sync* call whose lifetime
must outlive the request that started it (the client polls `GET .../run` from a
separate request), which is exactly what `BackgroundTasks` — tied to the request
that scheduled it — does not promise. `Settings.run_synchronously` (set by tests)
runs the same wrapper inline instead, so no test depends on thread timing.

Run it locally with:

    uv run uvicorn financial_planner.interface.api:app --host 127.0.0.1 --port 8000

`127.0.0.1`, never `0.0.0.0`: this API has no auth by design (BRD §10), so it must
not be reachable from other devices on the network. CORS is likewise an explicit
allowlist of the frontend's own dev origin, never `*` — see `Settings`.

Portuguese only appears where it is an internal protocol string (the
`"aceitar"`/`"confirmar"` answers `nodes/review.py` parses). Everything this module
returns to a client is English/technical: it is a JSON API, not a terminal.
"""

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date as date_type
from pathlib import Path as FsPath
from threading import Lock
from typing import Annotated, Callable, Literal

from fastapi import Body, Depends, FastAPI, File, Path, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langgraph.types import Command
from pydantic import BaseModel, Field, field_validator
from starlette.exceptions import HTTPException as StarletteHTTPException

from financial_planner.graph import build_graph
from financial_planner.nodes import budget as budget_node, queries, transactions as transactions_node
from financial_planner.nodes.report import generate_report
from financial_planner.state import (
    Bank,
    Instrument,
    Transaction,
    TransactionNotFoundError,
    TransactionType,
    UnrecognizedBankError,
)

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = "data/financial-planner.db"
DEFAULT_EXTRACTS_DIR = "extracts"
MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # generous but not unbounded: real statements are KB-to-MB
ALLOWED_UPLOAD_EXTENSIONS = frozenset({".csv", ".pdf"})
# The planned Vite dev server origin. An allowlist, never "*": with no auth token,
# a wildcard would let any page open in the same browser drive this API.
ALLOWED_ORIGINS = ["http://localhost:5173"]

MONTH_REF_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"


# --- settings ---------------------------------------------------------------------


@dataclass
class Settings:
    db_path: str = field(
        default_factory=lambda: os.environ.get("SQLITE_DB_PATH") or DEFAULT_DB_PATH
    )
    extracts_dir: str = field(
        default_factory=lambda: os.environ.get("EXTRACTS_DIR") or DEFAULT_EXTRACTS_DIR
    )
    max_upload_bytes: int = MAX_UPLOAD_BYTES
    allowed_extensions: frozenset[str] = ALLOWED_UPLOAD_EXTENSIONS
    allowed_origins: tuple[str, ...] = tuple(ALLOWED_ORIGINS)
    # Tests set this to run the background wrapper inline (see module docstring).
    run_synchronously: bool = False


def get_settings() -> Settings:
    """Dependency, so tests can override it with `app.dependency_overrides`."""
    return Settings()


# --- run-state registry -----------------------------------------------------------


@dataclass
class RunState:
    status: Literal["processing", "pending_review", "completed", "error"]
    item: dict | None = None
    report: dict | None = None
    error: str | None = None

    @classmethod
    def from_graph_result(cls, result: dict) -> "RunState":
        interrupts = result.get("__interrupt__")
        if interrupts:
            # Exactly today's interrupt() payload from nodes/review.py:_build_payload
            # — exposed over HTTP instead of printed. No new payload design.
            return cls(status="pending_review", item=interrupts[0].value)
        return cls(status="completed", report=result.get("report"))

    def to_response(self) -> dict:
        if self.status == "pending_review":
            return {"status": self.status, "item": self.item}
        if self.status == "completed":
            return {"status": self.status, "report": self.report}
        if self.status == "error":
            return {"status": self.status, "message": self.error}
        return {"status": self.status}


# Module-level and in-memory on purpose (spec): a restart just loses the registry,
# and re-issuing POST .../run is safe and cheap. Single process only — see the
# spec's "Extensibility and known constraints" before ever running >1 worker.
_registry: dict[str, RunState] = {}
_registry_lock = Lock()
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="fp-run")


def _get_state(month_ref: str) -> RunState | None:
    with _registry_lock:
        return _registry.get(month_ref)


def _set_state(month_ref: str, state: RunState) -> None:
    with _registry_lock:
        _registry[month_ref] = state


def reset_run_registry() -> None:
    """Test helper — the registry is process-global, so tests must clear it."""
    with _registry_lock:
        _registry.clear()


# --- safe error messages ----------------------------------------------------------

# A raw exception string can carry local filesystem paths and other internals, so
# clients get a fixed message per known failure and a generic one otherwise. The
# real traceback only ever goes to the server log.
_SAFE_MESSAGES: dict[type[Exception], str] = {
    UnrecognizedBankError: "One of the uploaded files does not match any supported bank format.",
    TransactionNotFoundError: "Transaction not found",
}


def _safe_message(exc: Exception) -> str:
    for exc_type, message in _SAFE_MESSAGES.items():
        if isinstance(exc, exc_type):
            return message
    return "Processing failed. See the server log for details."


class ApiError(Exception):
    """A deliberate, client-facing failure: code + already-safe message."""

    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content={"error": {"code": code, "message": message}}
    )


# --- background execution ---------------------------------------------------------


def _run_in_background(
    month_ref: str, invoke: Callable[[], dict], settings: Settings
) -> None:
    """Mark the month as processing and run `invoke` — inline under test, on the
    executor otherwise."""
    _set_state(month_ref, RunState(status="processing"))
    if settings.run_synchronously:
        _execute(month_ref, invoke)
    else:
        _executor.submit(_execute, month_ref, invoke)


def _execute(month_ref: str, invoke: Callable[[], dict]) -> None:
    """The one wrapper around every graph.invoke() call.

    The broad `except Exception` is deliberate (same pattern as nodes/insights.py):
    without it an exception in the worker thread dies silently, the registry stays
    at "processing" forever, and the client polls a run that will never finish.
    """
    try:
        result = invoke()
        _set_state(month_ref, RunState.from_graph_result(result))
    except Exception as exc:  # noqa: BLE001 — see docstring
        logger.exception("run failed for month_ref=%s", month_ref)
        _set_state(month_ref, RunState(status="error", error=_safe_message(exc)))


def _graph_config(month_ref: str) -> dict:
    # thread_id == month_ref is exactly what a "run" already means (graph.py/cli.py).
    return {"configurable": {"thread_id": month_ref}}


# --- request bodies ---------------------------------------------------------------


class RunRequest(BaseModel):
    files: list[str] = Field(default_factory=list)


class ReviewRequest(BaseModel):
    action: Literal["accept", "confirm_transfer", "correct"]
    category: str | None = None
    subcategory: str | None = None


class TransactionPatch(BaseModel):
    category: str | None = None
    subcategory: str | None = None
    deleted: bool | None = None


class CreateTransactionRequest(BaseModel):
    """A transaction the bank statement never had — e.g. cash spending. Always
    lands at confidence='high': a human is directly asserting date/amount/
    category, there's nothing left to review (nodes/transactions.py:create)."""

    date: date_type
    description_raw: str = Field(min_length=1)
    account: Bank
    type: TransactionType
    amount: float = Field(gt=0)
    category: str = Field(min_length=1)
    subcategory: str | None = None
    instrument: Instrument = Instrument.DEBIT


class BudgetGoalsRequest(BaseModel):
    """Full replace of one budget scope (the global default, or one month's
    overrides) — a settings page naturally edits the whole set and saves once."""

    goals: dict[str, float] = Field(default_factory=dict)

    @field_validator("goals")
    @classmethod
    def _goals_are_non_negative(cls, goals: dict[str, float]) -> dict[str, float]:
        if any(goal < 0 for goal in goals.values()):
            raise ValueError("Budget goals must not be negative.")
        return goals


# --- serialization ----------------------------------------------------------------


def _serialize_transaction(transaction: Transaction) -> dict:
    return {
        "dedup_hash": transaction.dedup_hash,
        "date": transaction.date.isoformat(),
        "description_raw": transaction.description_raw,
        "account": transaction.account.value,
        "type": transaction.type.value,
        "amount": transaction.amount,
        "month_ref": transaction.month_ref,
        "category": transaction.category,
        "subcategory": transaction.subcategory,
        "confidence": transaction.confidence,
        "instrument": transaction.instrument.value,
        "fatura_ref": transaction.fatura_ref,
        "deleted_at": transaction.deleted_at,
    }


def _serialize_report(report) -> dict:
    """Same shape graph.py's _report_node projects into the graph state, so a report
    polled from `GET .../run` and one recomputed by `GET .../report` are identical.
    (graph.py is frozen for this feature, hence the deliberate duplication.)"""
    return {
        "month_ref": report.month_ref,
        "total_income": report.total_income,
        "total_expense": report.total_expense,
        "net_balance": report.net_balance,
        "transfer_total": report.transfer_total,
        "category_breakdown": [
            {
                "category": e.category,
                "type": e.type.value,
                "total": e.total,
                "gross": getattr(e, "gross", e.total),
                "reimbursed": getattr(e, "reimbursed", 0.0),
            }
            for e in report.category_breakdown
        ],
        "transaction_count": report.transaction_count,
        "budget_report": report.budget_report,
        "insights_summary": report.insights_summary,
        "insights_error": report.insights_error,
        "total_reimbursements": getattr(report, "total_reimbursements", 0.0),
        "unattributed_reimbursements": getattr(report, "unattributed_reimbursements", 0.0),
        "credit_category_breakdown": [
            {"category": e.category, "type": e.type.value, "total": e.total}
            for e in getattr(report, "credit_category_breakdown", [])
        ],
        "credit_total": getattr(report, "credit_total", 0.0),
        "fatura_reconciliations": [
            {
                "fatura_ref": r.fatura_ref,
                "debit_payment": r.debit_payment,
                "credit_purchases_total": r.credit_purchases_total,
                "delta": r.delta,
            }
            for r in getattr(report, "fatura_reconciliations", [])
        ],
    }


# --- uploads ----------------------------------------------------------------------


def _safe_upload_path(settings: Settings, month_ref: str, filename: str | None) -> FsPath:
    """`Path(filename).name` only — a filename carrying `../` or an absolute path
    must never be able to write outside `extracts/{month_ref}/`. `month_ref` itself
    is pattern-validated at the route, so it can't traverse either.

    A filename that isn't already its own basename is *rejected*, not silently
    rewritten: nothing legitimate sends one, and a caller that gets a 422 learns
    what happened instead of finding the file under a name it never chose."""
    name = FsPath(filename or "").name
    if not name or name in (".", ".."):
        raise ApiError(422, "invalid_filename", "Upload is missing a usable filename.")
    if name != filename:
        raise ApiError(422, "invalid_filename", "Filename must not contain a path.")
    if FsPath(name).suffix.lower() not in settings.allowed_extensions:
        raise ApiError(
            415,
            "unsupported_file_type",
            "Only .csv and .pdf statement files are accepted.",
        )
    return FsPath(settings.extracts_dir) / month_ref / name


def _read_capped(upload: UploadFile, max_bytes: int) -> bytes:
    """Read the whole upload with a hard cap, before anything touches the disk."""
    chunks: list[bytes] = []
    total = 0
    while chunk := upload.file.read(1024 * 1024):
        total += len(chunk)
        if total > max_bytes:
            raise ApiError(
                413,
                "payload_too_large",
                f"Uploaded file exceeds the {max_bytes // (1024 * 1024)}MB limit.",
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _resolve_source_file(settings: Settings, raw_path: str) -> str:
    """Run inputs must be files inside `extracts/` — i.e. files that came through
    `POST .../uploads`. Without this, an unauthenticated local API would happily
    read (and try to parse) any path on the machine."""
    root = FsPath(settings.extracts_dir).resolve()
    candidate = FsPath(raw_path)
    if not candidate.is_absolute():
        candidate = FsPath.cwd() / candidate
    candidate = candidate.resolve()
    if not candidate.is_relative_to(root):
        raise ApiError(422, "invalid_path", "Statement files must be uploaded first.")
    if not candidate.is_file():
        raise ApiError(404, "file_not_found", "Statement file not found.")
    return str(candidate)


# --- app ---------------------------------------------------------------------------

MonthRef = Annotated[str, Path(pattern=MONTH_REF_PATTERN, description="e.g. 2026-08")]


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="Financial Planner API", version="0.1.0")

    origins = list(settings.allowed_origins) if settings else ALLOWED_ORIGINS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["*"],
    )

    if settings is not None:
        app.dependency_overrides[get_settings] = lambda: settings

    _register_exception_handlers(app)
    _register_routes(app)
    return app


def _register_exception_handlers(app: FastAPI) -> None:
    """Every error response — ours, FastAPI's, and unexpected ones — leaves through
    the same `{"error": {"code", "message"}}` envelope, with details log-only."""

    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
        logger.info("api error: %s", exc.message)
        return _error_response(exc.status_code, exc.code, exc.message)

    @app.exception_handler(TransactionNotFoundError)
    async def _not_found(request: Request, exc: TransactionNotFoundError) -> JSONResponse:
        return _error_response(404, "not_found", "Transaction not found")

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        logger.info("validation error on %s: %s", request.url.path, exc.errors())
        return _error_response(422, "validation_error", "Request is not valid.")

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        codes = {404: "not_found", 405: "method_not_allowed", 409: "conflict"}
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return _error_response(
            exc.status_code, codes.get(exc.status_code, "http_error"), message
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error on %s", request.url.path)
        return _error_response(500, "internal_error", _safe_message(exc))


SettingsDep = Annotated[Settings, Depends(get_settings)]


def _register_routes(app: FastAPI) -> None:
    @app.get("/taxonomy")
    def taxonomy() -> dict:
        # Static config, not data — no db_path needed. specs/016-frontend-core:
        # the review flow's "correct" picker needs the full tree, not just the
        # current suggestion's suggested_subcategories.
        return queries.get_taxonomy()

    @app.get("/budget")
    def get_default_budget(settings: SettingsDep) -> dict:
        return budget_node.get_default_goals(settings.db_path)

    @app.put("/budget")
    def put_default_budget(settings: SettingsDep, body: Annotated[BudgetGoalsRequest, Body()]) -> dict:
        return budget_node.set_default_goals(body.goals, settings.db_path)

    @app.get("/months/{month_ref}/budget")
    def get_month_budget(month_ref: MonthRef, settings: SettingsDep) -> dict:
        overrides, effective = budget_node.get_month_goals(month_ref, settings.db_path)
        return {"overrides": overrides, "effective": effective}

    @app.put("/months/{month_ref}/budget")
    def put_month_budget(
        month_ref: MonthRef,
        settings: SettingsDep,
        body: Annotated[BudgetGoalsRequest, Body()],
    ) -> dict:
        overrides, effective = budget_node.set_month_goals(month_ref, body.goals, settings.db_path)
        return {"overrides": overrides, "effective": effective}

    @app.post("/months/{month_ref}/uploads", status_code=201)
    def upload_statements(
        month_ref: MonthRef,
        settings: SettingsDep,
        files: Annotated[list[UploadFile], File()],
    ) -> dict:
        if not files:
            raise ApiError(422, "validation_error", "At least one file is required.")

        # Validate everything (name, extension, size) before a single byte is
        # written, so a rejected batch leaves nothing behind.
        validated: list[tuple[FsPath, bytes]] = []
        for upload in files:
            destination = _safe_upload_path(settings, month_ref, upload.filename)
            validated.append((destination, _read_capped(upload, settings.max_upload_bytes)))

        saved = []
        for destination, content in validated:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
            saved.append(str(destination))
        return {"files": saved}

    @app.post("/months/{month_ref}/run", status_code=202)
    def start_run(
        month_ref: MonthRef,
        settings: SettingsDep,
        body: Annotated[RunRequest, Body()] = RunRequest(),
    ) -> dict:
        current = _get_state(month_ref)
        if current is not None and current.status == "processing":
            # Concurrency guard: never spawn a second worker for the same month.
            return current.to_response()

        source_files = [_resolve_source_file(settings, path) for path in body.files]
        db_path = settings.db_path
        graph_input = {
            "source_files": source_files,
            "month_ref": month_ref,
            "db_path": db_path,
        }

        def invoke() -> dict:
            return build_graph(db_path).invoke(graph_input, config=_graph_config(month_ref))

        _run_in_background(month_ref, invoke, settings)
        return (_get_state(month_ref) or RunState(status="processing")).to_response()

    @app.get("/months/{month_ref}/run")
    def poll_run(month_ref: MonthRef) -> dict:
        state = _get_state(month_ref)
        if state is None:
            return {"status": "not_started"}
        return state.to_response()

    @app.post("/months/{month_ref}/review", status_code=202)
    def answer_review(
        month_ref: MonthRef,
        settings: SettingsDep,
        body: Annotated[ReviewRequest, Body()],
    ) -> dict:
        state = _get_state(month_ref)
        if state is None or state.status != "pending_review":
            raise ApiError(409, "no_pending_review", "No review item is pending for this month.")

        answer = _review_answer(body)
        db_path = settings.db_path

        def invoke() -> dict:
            return build_graph(db_path).invoke(
                Command(resume=answer), config=_graph_config(month_ref)
            )

        _run_in_background(month_ref, invoke, settings)
        return (_get_state(month_ref) or RunState(status="processing")).to_response()

    @app.get("/months")
    def list_months(settings: SettingsDep) -> list[dict]:
        return queries.list_month_summaries(settings.db_path)

    @app.get("/months/{month_ref}/report")
    def month_report(month_ref: MonthRef, settings: SettingsDep) -> dict:
        # Always recomputed, never cached: a manual edit to a past month has to show
        # up immediately. Budget goals are cheap and deterministic, so they are
        # recomputed too; insights are not — they need the LLM, and the month's
        # generated summary belongs to the run that produced it.
        comparisons = budget_node.check_budget(month_ref, settings.db_path)
        budget_report = [
            {
                "category": c.category,
                "goal": c.goal,
                "actual_spend": c.actual_spend,
                "difference": c.difference,
                "status": c.status.value,
            }
            for c in comparisons
        ]

        report = generate_report(month_ref, settings.db_path, budget_report=budget_report)
        return _serialize_report(report)

    @app.get("/months/{month_ref}/transactions")
    def list_transactions(
        month_ref: MonthRef,
        settings: SettingsDep,
        instrument: Annotated[Instrument | None, Query()] = None,
        category: Annotated[str | None, Query()] = None,
        include_deleted: Annotated[bool, Query()] = False,
    ) -> list[dict]:
        found = queries.list_month_transactions(
            settings.db_path,
            month_ref,
            instrument=instrument,
            category=category,
            include_deleted=include_deleted,
        )
        return [_serialize_transaction(t) for t in found]

    @app.post("/transactions", status_code=201)
    def create_transaction(
        settings: SettingsDep,
        body: Annotated[CreateTransactionRequest, Body()],
    ) -> dict:
        # month_ref isn't a path param here (unlike every other transaction
        # endpoint) -- it's derived from the date the caller supplies, same as
        # ingest. No repository import, same rule as every other handler.
        created = transactions_node.create(
            date=body.date,
            description_raw=body.description_raw,
            account=body.account,
            type=body.type,
            amount=body.amount,
            category=body.category,
            subcategory=body.subcategory,
            instrument=body.instrument,
            db_path=settings.db_path,
        )
        return _serialize_transaction(created)

    @app.patch("/transactions/{dedup_hash}")
    def edit_transaction(
        dedup_hash: str,
        settings: SettingsDep,
        body: Annotated[TransactionPatch, Body()],
    ) -> dict:
        # Validation + dispatch only: no SQL, no repository import (see spec's
        # "Architecture"). TransactionNotFoundError from the node becomes a 404
        # through the handler registered above.
        recategorizing = body.category is not None
        deleting = body.deleted is not None

        if recategorizing == deleting:
            raise ApiError(
                422,
                "validation_error",
                'Send either {"category", "subcategory"} or {"deleted"}, not both.',
            )
        if recategorizing and body.subcategory is not None and not body.category:
            raise ApiError(422, "validation_error", "A subcategory needs a category.")

        if recategorizing:
            updated = transactions_node.recategorize(
                dedup_hash, body.category, body.subcategory, settings.db_path
            )
        elif body.deleted:
            updated = transactions_node.soft_delete(dedup_hash, settings.db_path)
        else:
            updated = transactions_node.restore(dedup_hash, settings.db_path)

        return _serialize_transaction(updated)


def _review_answer(body: ReviewRequest) -> str:
    """Translate the structured body into the string protocol `nodes/review.py`
    already parses. This translation is an interface concern, so it lives here —
    `nodes/review.py` is untouched, exactly as `cli.py` keeps it today."""
    if body.action == "accept":
        return "aceitar"
    if body.action == "confirm_transfer":
        return "confirmar"
    if not body.category:
        raise ApiError(422, "validation_error", 'Action "correct" requires a category.')
    return f"{body.category}|{body.subcategory or ''}"


app = create_app()
