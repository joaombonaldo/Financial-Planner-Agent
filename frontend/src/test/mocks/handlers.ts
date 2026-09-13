/**
 * Default happy-path MSW handlers for all 9 endpoints.
 *
 * **No test ever reaches a real backend** (and therefore never transitively
 * reaches real Ollama) — specs/016-frontend-core "Testing strategy".
 *
 * ## Overriding per test — do this, don't edit this file
 *
 *   import { http, HttpResponse } from "msw"
 *   import { server } from "@/test/mocks/server"
 *   import { url, errorResponse } from "@/test/mocks/handlers"
 *
 *   server.use(
 *     http.get(url("/months/:monthRef/run"), () =>
 *       HttpResponse.json({ status: "completed", report: reportFixture })),
 *     http.get(url("/months"), () => errorResponse(500, "internal_error", "boom")),
 *   )
 *
 * `server.resetHandlers()` runs after every test (see `src/test/setup.ts`), so an
 * override never leaks into the next test. Sequencing a poll across calls (the
 * processing -> pending_review -> completed path) is just a counter in a closure
 * inside a single `http.get(url("/months/:monthRef/run"), ...)` override.
 */
import { http, HttpResponse } from "msw"

import { API_BASE_URL } from "@/api/client"
import {
  monthsFixture,
  reportFixture,
  reviewItemFixture,
  taxonomyFixture,
  transactionsFixture,
} from "./fixtures"

/**
 * Absolute URL for a path — the client uses an absolute `baseUrl`, so handlers
 * must match absolutely. Always build override patterns with this.
 */
export function url(path: string): string {
  return `${API_BASE_URL}${path}`
}

/** The backend's one error envelope, for tests that need a failure response. */
export function errorResponse(status: number, code: string, message: string) {
  return HttpResponse.json({ error: { code, message } }, { status })
}

export const handlers = [
  // GET /taxonomy
  http.get(url("/taxonomy"), () => HttpResponse.json(taxonomyFixture)),

  // GET /months
  http.get(url("/months"), () => HttpResponse.json(monthsFixture)),

  // POST /months/:monthRef/uploads  -> 201
  http.post(url("/months/:monthRef/uploads"), async ({ params, request }) => {
    const form = await request.formData()
    const names = form
      .getAll("files")
      .map((entry) => (entry instanceof File ? entry.name : String(entry)))
    return HttpResponse.json(
      { files: names.map((name) => `extracts/${params.monthRef}/${name}`) },
      { status: 201 },
    )
  }),

  // POST /months/:monthRef/run  -> 202, always "processing"
  http.post(url("/months/:monthRef/run"), () =>
    HttpResponse.json({ status: "processing" }, { status: 202 }),
  ),

  // GET /months/:monthRef/run
  // Default is "pending_review": the most useful resting state for the review
  // screen. Override for any other leg of the state machine.
  http.get(url("/months/:monthRef/run"), () =>
    HttpResponse.json({ status: "pending_review", item: reviewItemFixture }),
  ),

  // POST /months/:monthRef/review  -> 202, back to "processing"
  http.post(url("/months/:monthRef/review"), () =>
    HttpResponse.json({ status: "processing" }, { status: 202 }),
  ),

  // GET /months/:monthRef/report
  http.get(url("/months/:monthRef/report"), ({ params }) =>
    HttpResponse.json({ ...reportFixture, month_ref: String(params.monthRef) }),
  ),

  // GET /months/:monthRef/transactions — honours ?instrument, ?category,
  // ?include_deleted so filter tests exercise the real query-string wiring.
  http.get(url("/months/:monthRef/transactions"), ({ params, request }) => {
    const query = new URL(request.url).searchParams
    const instrument = query.get("instrument")
    const category = query.get("category")
    const includeDeleted = query.get("include_deleted") === "true"

    const rows = transactionsFixture
      .map((t) => ({ ...t, month_ref: String(params.monthRef) }))
      .filter((t) => (instrument ? t.instrument === instrument : true))
      .filter((t) => (category ? t.category === category : true))
      .filter((t) => (includeDeleted ? true : t.deleted_at === null))

    return HttpResponse.json(rows)
  }),

  // PATCH /transactions/:dedupHash — echoes the patch back onto the matching
  // fixture row, the way the real endpoint returns the updated transaction.
  http.patch(url("/transactions/:dedupHash"), async ({ params, request }) => {
    const body = (await request.json()) as {
      category?: string | null
      subcategory?: string | null
      deleted?: boolean | null
    }
    const existing =
      transactionsFixture.find((t) => t.dedup_hash === params.dedupHash) ??
      transactionsFixture[0]

    return HttpResponse.json({
      ...existing,
      dedup_hash: String(params.dedupHash),
      category: body.category ?? existing.category,
      subcategory: body.category ? (body.subcategory ?? null) : existing.subcategory,
      deleted_at: body.deleted === true ? "2026-09-12T12:00:00" : null,
    })
  }),
]
