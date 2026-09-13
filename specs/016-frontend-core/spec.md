# Feature Specification: Frontend core (Phase 2 UI)

**Feature Branch**: TBD (not started)

**Created**: 2026-09-12

**Status**: Specified, not implemented.

**Input**: A brainstorming conversation covering the frontend stack, the review
UX given the API's one-item-at-a-time design, visual direction, and test
rigor. See BRD §10 "Frontend architecture decisions (2026-09-12)" for the
summary and rationale — this spec is the concrete design built on top of
those decisions and on the already-implemented, smoke-tested
`specs/015-fastapi-core-api`.

## Decisions this spec builds on (see BRD §10 for rationale)

- Vite + React + TypeScript SPA, Tailwind + shadcn/ui, React Router, TanStack
  Query, Recharts.
- Dev server on `http://localhost:5173` (required by the API's CORS
  allowlist), API base URL via `VITE_API_BASE_URL` env var.
- API client generated from `GET /openapi.json`, never hand-maintained.
- Review queue is one-at-a-time only, matching the API exactly.
- Minimal, data-forward visual style.
- UI chrome in Portuguese, matching the CLI's existing rule.
- Same test rigor as the backend: Vitest + RTL + MSW, no test ever hits a
  real backend or (transitively) real Ollama.

## Screens and routes

| Route | Screen | Backing endpoint(s) |
|---|---|---|
| `/` | Redirects to `/months` | — |
| `/months` | Month history list | `GET /months` |
| `/months/:monthRef/upload` | Upload statement files for a month, then start the run | `POST /months/:monthRef/uploads`, `POST /months/:monthRef/run` |
| `/months/:monthRef/review` | The review flow — shown automatically while a run is `processing`/`pending_review` | `GET /months/:monthRef/run`, `POST /months/:monthRef/review` |
| `/months/:monthRef/report` | Dashboard: totals, category breakdown, budget comparison, credit-card reconciliation, insights summary | `GET /months/:monthRef/report` |
| `/months/:monthRef/transactions` | Browse/manually edit a month's transactions | `GET /months/:monthRef/transactions`, `PATCH /transactions/:dedupHash` |

A month's natural path through these is upload → review → report, but each
route is independently reachable — `/months/:monthRef/report` and
`/months/:monthRef/transactions` work for any month regardless of run state
(report recomputes fresh regardless, per the API's design), so revisiting a
past month never depends on "starting" anything.

## The review flow — client state machine

This is the part of the UI that has to get the polling model right. One
`monthRef` maps to one of these client states, driven entirely by `GET
.../run`'s `status` field (no separate client-side state machine library
needed — this is exactly what a `useQuery` with `refetchInterval` already
gives you):

```
not_started ──(POST .../run)──▶ processing ──(poll)──▶ pending_review
                                     ▲                        │
                                     │                (POST .../review)
                                     └────────────────────────┘
                                     │
                                     ▼ (poll, no more pending items)
                                 completed ──▶ navigate to /report
                                     
                                 error ──▶ show message + retry (re-POST .../run)
```

- While `status: "processing"`, poll `GET .../run` on an interval (start at
  ~1s; the smoke test showed a real Ollama categorization call taking a few
  seconds — don't poll faster than that, and don't need to poll much slower
  either, this is a single local user watching their own screen).
- On `status: "pending_review"`, stop polling, render the item, wait for the
  user's answer. `POST .../review` returns `202` immediately (itself
  `"processing"`) — resume polling right after that call, don't wait for a
  fresh `GET` first.
- On `status: "completed"`, stop polling and navigate to
  `/months/:monthRef/report`.
- On `status: "error"`, stop polling, show the sanitized `message`, offer a
  retry button that re-issues `POST .../run` — safe and cheap per the API's
  idempotency design (specs/015's "Why start and resume can be the
  safely-repeatable same call").
- Leaving the review screen (navigating away) does not need to cancel
  anything server-side — there's nothing to cancel, the background run keeps
  going, and returning to `/months/:monthRef/review` later just resumes
  polling into whatever state it's actually in.

### Rendering the pending item

The `item` shape is exactly `nodes/review.py:_build_payload`'s nested
structure (confirmed against the real smoke-tested response, not the
flattened sample in an earlier draft of specs/015):

```jsonc
{
  "transaction": {
    "date": "2026-08-21", "description_raw": "...", "amount": 250.75,
    "account": "bradesco", "category": "Compras", "subcategory": "Casa/Outros",
    "confidence": "medium", "instrument": "debit"
  },
  "is_transfer_candidate": false,
  "suggested_subcategories": ["Roupas/Calçados", "Perfumes/Cosméticos", ...],
  "error": "..."  // present only after an invalid answer, not applicable over HTTP
                  // the same way it was for the CLI's re-ask loop — see below
}
```

The CLI's `error` field existed for its terminal re-ask loop (invalid text
input, ask again). Over HTTP, `POST .../review` validates the request body
with Pydantic before it ever reaches the graph (`ReviewRequest`), so a
malformed answer is a `422` on the `POST`, not a re-served `item.error` — the
UI's error handling for a bad review submission is the same as for any other
form validation error (see "Error handling" below), not a special case.

Three answer actions map to UI controls:
- **Accept** button — always available. `{"action": "accept"}`.
- **Confirm transfer** button — shown instead of "Accept" when
  `is_transfer_candidate` is true. `{"action": "confirm_transfer"}`.
- **Correct** — a category/subcategory picker (populated from
  `suggested_subcategories` when the chosen category has any, freeform/full
  taxonomy otherwise — the taxonomy itself isn't exposed by an endpoint yet,
  see "Open questions"). `{"action": "correct", "category": ..., "subcategory": ...}`.

## API client and data-fetching layer

- Generate a typed client from `GET /openapi.json` (tool choice: `openapi-typescript` +
  a thin typed-fetch wrapper — lighter than a full codegen-with-runtime tool
  like `orval` for an API this size; revisit if the API grows much larger).
  Regenerate via an `npm run generate-api` script pointed at a running local
  backend — commit the generated output (so `npm install && npm run dev` works
  without a backend already running), but treat it as generated, never
  hand-edited.
- **No component ever calls `fetch`/the generated client directly.** Every
  endpoint is wrapped in a TanStack Query hook in `src/api/` (`useMonths`,
  `useRunStatus(monthRef)`, `useStartRun`, `useAnswerReview`, `useReport
  (monthRef)`, `useTransactions(monthRef, filters)`, `usePatchTransaction`).
  This is the frontend's equivalent of the backend's "interface never touches
  the layer below it directly" rule (specs/015 "Architecture") — components
  depend on hooks, hooks depend on the generated client, nothing skips a
  layer.
- Query invalidation: a successful `PATCH` invalidates that month's
  `transactions` and `report` queries (both change immediately, per the
  soft-delete smoke test's live-recompute behavior); a completed run
  invalidates `months` (transaction count / pending flag changed) and primes
  `report`.

## Folder structure

Deliberately flat to start — reorganize into `features/*` only if it actually
grows unwieldy, not preemptively:

```
frontend/src/
├── api/            # generated client (generated/) + hooks (queries.ts, mutations.ts)
├── components/      # shared UI (shadcn primitives + small composed components)
├── pages/           # one file per route in the table above
├── App.tsx          # router setup
└── main.tsx
```

## Security

- **No secrets in the frontend** — there are none to have (no auth token, no
  API keys; `VITE_API_BASE_URL` is not sensitive).
- **The LLM-generated insights summary is rendered as plain text, never
  `dangerouslySetInnerHTML`.** It's free-form text from a local LLM; treating
  it as anything but plain text is an unnecessary XSS surface for zero
  benefit (there's no legitimate HTML in a Portuguese financial summary).
- **`credentials: "omit"` on every request** — matches the API's
  `allow_credentials=False`; there is no cookie/session to send, and not
  sending one is one less thing to reason about.
- Same-origin-only CORS on the backend already prevents this frontend from
  being driven cross-origin by another page; the frontend doesn't need its
  own additional protection against that class of issue.

## Extensibility and known constraints

- **The frontend is single-backend, single-user by construction** — no
  concept of switching accounts/environments beyond changing
  `VITE_API_BASE_URL`. Consistent with the backend's own "no user_id
  scoping anywhere" constraint (specs/015) — extending either one to
  multi-user is a bigger, later decision, not a frontend-only change.
- **The generated API client is a hard dependency on the backend's OpenAPI
  schema staying accurate.** FastAPI derives it from the route
  definitions/Pydantic models automatically, so this holds as long as new
  endpoints keep using typed request/response models (already true of
  everything in specs/015).

## Testing strategy

Same discipline as the backend (BRD §9, specs/015 "Testing strategy"):

- Vitest + React Testing Library for component/page tests.
- **MSW (Mock Service Worker) intercepts every request in every test** —
  no test ever reaches a real backend process, and therefore never
  transitively reaches real Ollama. MSW handlers are built from the same
  response shapes documented in specs/015 (the exact `item`/`report`/error-
  envelope shapes), not invented separately.
- The review flow's state machine gets explicit coverage for each transition
  in the diagram above, including the error → retry path and the
  transfer-candidate branch.
- A "recategorize" and a "soft-delete" test on the transactions page,
  asserting the report/transactions queries actually refetch afterward (the
  invalidation behavior above), not just that the `PATCH` call was made.

## Out of scope (this feature)

- A budget-goals editor screen (BRD: explicitly deferred past the first UI
  cut).
- Batch/table-based review via `PATCH` (BRD: deliberately deferred, see
  "Decisions this spec builds on").
- Any change to `interface/api.py` or any other backend file — this feature
  is purely additive on top of the already-implemented, already-tested API.
- E2E tests (Playwright or similar) — Vitest/RTL/MSW component-level
  coverage only, for now.
- Any deployment/hosting concern — this runs locally via `npm run dev`
  against a locally-running `uvicorn`, same as the backend's own local-only
  scope.

## Open questions for the planning/tasks pass

- **The full category/subcategory taxonomy isn't exposed by any endpoint
  yet.** The review item's `suggested_subcategories` only covers the *current
  suggested category's* subcategories — correcting to a wholly different
  category needs the full tree (`config/categories.yaml`) somewhere the
  frontend can read it. Cheapest fix is likely a small new read-only endpoint
  (`GET /taxonomy` or similar) — that's a (tiny) backend addition this spec
  surfaces but doesn't itself own; flag before starting the "Correct" picker
  UI.
- Exact polling interval tuning (starting guess: 1s while `processing`) —
  needs eyeballing against real Ollama latency once the UI exists, not a
  brainstorm-level decision.
- Whether month-history (`/months`) needs pagination — currently a personal
  project processing one month at a time, unlikely to need it soon, but
  worth a one-line decision once real usage accumulates more than a
  handful of months.
