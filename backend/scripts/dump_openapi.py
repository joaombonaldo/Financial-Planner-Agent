"""Dump the FastAPI app's OpenAPI schema to `frontend/openapi.json`.

No uvicorn needed: `app.openapi()` builds the schema from the route definitions
alone, so this is a pure, offline, repeatable step — the first half of the
frontend's `npm run generate-api` (specs/016-frontend-core "API client and
data-fetching layer"). The second half feeds this file to `openapi-typescript`.

Run from `backend/`:

    uv run --no-sync python scripts/dump_openapi.py
"""

import json
from pathlib import Path

from financial_planner.interface.api import app

OUTPUT = Path(__file__).resolve().parents[2] / "frontend" / "openapi.json"


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    schema = app.openapi()
    OUTPUT.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()
