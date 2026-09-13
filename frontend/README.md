# Frontend — Planejador Financeiro (Phase 2 UI)

Vite + React + TypeScript SPA over the FastAPI backend in `../backend`.
See `specs/016-frontend-core/spec.md` for the binding design and
`specs/015-fastapi-core-api/spec.md` for the API it consumes.

## Running it

```bash
npm install
npm run dev          # http://localhost:5173
```

The dev server **must** stay on port 5173: the backend's CORS allowlist is
hardcoded to `http://localhost:5173` (`interface/api.py` `ALLOWED_ORIGINS`).

The backend, in a second terminal:

```bash
cd ../backend
uv run uvicorn financial_planner.interface.api:app --host 127.0.0.1 --port 8000
```

`VITE_API_BASE_URL` defaults to `http://127.0.0.1:8000` in code, so no `.env` is
needed. Copy `.env.example` to `.env` only to point somewhere else.

## Scripts

| Script | What it does |
|---|---|
| `npm run dev` | Dev server on 5173 |
| `npm run build` | `tsc -b` + production build |
| `npm run test` | Vitest, once |
| `npm run test:watch` | Vitest, watching |
| `npm run typecheck` | `tsc -b` only |
| `npm run generate-api` | Regenerates the typed API client — see below |

## Regenerating the API client

The client types are **generated, never hand-edited**. No running backend is
needed: `app.openapi()` builds the schema offline.

```bash
npm run generate-api
```

which is exactly:

```bash
cd ../backend \
  && (chflags nohidden .venv/lib/python3.12/site-packages/*.pth 2>/dev/null || true) \
  && uv run --no-sync python scripts/dump_openapi.py \
  && cd ../frontend \
  && openapi-typescript openapi.json -o src/api/generated/schema.d.ts
```

The `chflags` line is the known macOS venv quirk documented in
`../backend/README.md` — without it the import fails with `ModuleNotFoundError:
No module named 'financial_planner'`. It is a no-op everywhere else.

Both `openapi.json` and `src/api/generated/schema.d.ts` are committed, so a fresh
clone builds without touching Python. Re-run `generate-api` whenever the backend's
routes or Pydantic models change.

## Layout

```
src/
├── api/
│   ├── generated/schema.d.ts  # generated — do not edit
│   ├── client.ts              # openapi-fetch instance + ApiError
│   ├── types.ts               # the app's type vocabulary (import from HERE)
│   ├── queries.ts             # useMonths, useTaxonomy, useRunStatus, useReport, useTransactions
│   └── mutations.ts           # useUploadFiles, useStartRun, useAnswerReview, usePatchTransaction
├── components/
│   ├── ui/                    # shadcn primitives
│   └── Layout.tsx             # shared shell (nav + <Outlet />)
├── pages/                     # one file per route
├── test/                      # setup, render helpers, MSW mocks
├── App.tsx                    # providers + routes
└── main.tsx
```

Two rules carried over from the backend's architecture:

1. **No component ever calls `fetch` or the generated client directly.** Pages use
   the hooks in `src/api/queries.ts` / `mutations.ts`; those use `client.ts`;
   nothing skips a layer.
2. **Nothing imports `src/api/generated/schema.d.ts` directly.** All types come
   from `src/api/types.ts`.

Every non-2xx response is thrown as an `ApiError` (`code`, `message`, `status`)
built from the backend's `{"error": {"code", "message"}}` envelope. Pages catch
`ApiError`, never a raw HTTP error.

UI chrome is in Portuguese, matching the CLI. The API itself is English/technical.

## Testing

Vitest + React Testing Library + MSW, jsdom environment.

```bash
npm run test
```

**No test ever reaches a real backend** (and therefore never transitively reaches
real Ollama). `src/test/setup.ts` starts the MSW server with
`onUnhandledRequest: "error"`, so an unmocked request fails the test loudly.

- `src/test/mocks/handlers.ts` — default happy-path handlers for all 9 endpoints,
  plus `url()` and `errorResponse()` helpers.
- `src/test/mocks/fixtures.ts` — realistic payloads shaped against the real
  serializers.
- `src/test/utils.tsx` — `renderWithProviders(ui, { route })` (the default),
  `renderApp({ route })` for routing assertions, `renderInLayout(children)` for
  the shell.

Override a handler inside one test — never by editing the shared handlers file:

```tsx
server.use(
  http.get(url("/months/:monthRef/run"), () =>
    HttpResponse.json({ status: "completed", report: reportFixture })),
)
```

`server.resetHandlers()` runs after every test, so overrides never leak.
