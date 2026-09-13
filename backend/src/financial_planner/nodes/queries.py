"""Node queries: read-only lookups that back the API's browsing endpoints.

Why this module exists: specs/015-fastapi-core-api "Architecture" makes it binding
that `interface/api.py` never imports `db/repository.py` — the dependency direction
is `interface -> nodes -> db/repository`, for *every* endpoint, not just the
manual-edit one. `nodes/transactions.py` owns the manual-edit writes; this module
owns the equivalent reads (`GET /months`, `GET /months/{month_ref}/transactions`,
`GET /taxonomy` — specs/016-frontend-core) so the interface layer stays as thin as
`interface/cli.py` is, even for a lookup (`get_taxonomy`) that isn't `db/repository.py`
-backed at all: `api.py` importing `categorization.taxonomy` directly would be the
same kind of layering shortcut this module exists to avoid.
"""

from financial_planner.categorization.taxonomy import load_taxonomy
from financial_planner.db import repository
from financial_planner.state import Instrument, Transaction


def get_taxonomy() -> dict[str, list[str]]:
    """The full category -> subcategories tree (config/categories.yaml).

    A review item's `suggested_subcategories` only covers the *currently
    suggested* category's subcategories — a UI letting the user correct to a
    wholly different category needs the full tree, which nothing else exposes
    over HTTP. No db_path/connection needed: this is static config, not data."""
    taxonomy = load_taxonomy()
    return {name: taxonomy.subcategories_for(name) for name in taxonomy.category_names()}


def list_month_refs(db_path: str) -> list[str]:
    """Every month that has at least one non-deleted transaction, newest first."""
    conn = repository.connect(db_path)
    try:
        return repository.list_month_refs(conn)
    finally:
        conn.close()


def list_month_summaries(db_path: str) -> list[dict]:
    """`[{"month_ref", "transaction_count", "has_pending_review"}, ...]`.

    `transaction_count` counts both streams (debit and credit): this backs a
    month-history list, where "how much did this month import" means every row the
    user can browse, not only the ones feeding the headline debit totals.
    """
    summaries = []
    conn = repository.connect(db_path)
    try:
        for month_ref in list_month_refs(db_path):
            transactions = repository.list_transactions_by_month(
                conn, month_ref, instrument=None
            )
            pending = repository.list_pending_review(conn, month_ref)
            summaries.append(
                {
                    "month_ref": month_ref,
                    "transaction_count": len(transactions),
                    "has_pending_review": bool(pending),
                }
            )
    finally:
        conn.close()
    return summaries


def list_month_transactions(
    db_path: str,
    month_ref: str,
    instrument: Instrument | None = None,
    category: str | None = None,
    include_deleted: bool = False,
) -> list[Transaction]:
    """Transactions of a month, optionally narrowed by instrument and category.

    Unlike `repository.list_transactions_by_month`, `instrument=None` (the default
    here) means "both streams": this backs a browsing/manual-edit UI, which must be
    able to show a credit-card purchase just as much as a debit line.
    """
    conn = repository.connect(db_path)
    try:
        transactions = repository.list_transactions_by_month(
            conn, month_ref, instrument=instrument, include_deleted=include_deleted
        )
    finally:
        conn.close()

    if category is not None:
        transactions = [t for t in transactions if t.category == category]
    return transactions
