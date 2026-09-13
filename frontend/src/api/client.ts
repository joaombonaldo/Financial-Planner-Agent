/**
 * The one place this app talks HTTP.
 *
 * Layering (specs/016-frontend-core "API client and data-fetching layer"):
 * components -> hooks (queries.ts / mutations.ts) -> this file -> the backend.
 * No component ever imports this module directly.
 *
 * Every non-2xx response becomes a thrown `ApiError` built from the backend's
 * single `{"error": {"code", "message"}}` envelope (interface/api.py
 * `_error_response` / `_register_exception_handlers`), so callers only ever
 * catch one error type — never a raw fetch/HTTP error.
 */
import createClient from "openapi-fetch"

import type { paths } from "./generated/schema"

/** `VITE_API_BASE_URL`, with the dev default baked in so `npm run dev` needs no setup. */
export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000"

/** The backend's error envelope, thrown as an exception. */
export class ApiError extends Error {
  readonly code: string
  readonly message: string
  readonly status: number

  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = "ApiError"
    this.code = code
    this.message = message
    this.status = status
  }
}

/** Shape of `{"error": {"code", "message"}}` as it arrives over the wire. */
type ErrorEnvelope = { error?: { code?: unknown; message?: unknown } }

function toApiError(status: number, body: unknown): ApiError {
  const envelope = (body ?? {}) as ErrorEnvelope
  const code =
    typeof envelope.error?.code === "string" ? envelope.error.code : "unknown_error"
  const message =
    typeof envelope.error?.message === "string"
      ? envelope.error.message
      : "A requisição falhou."
  return new ApiError(status, code, message)
}

/**
 * `credentials: "omit"` is a spec requirement, not a style choice: the API sets
 * `allow_credentials=False` and there is no cookie/session to send.
 */
export const client = createClient<paths>({
  baseUrl: API_BASE_URL,
  credentials: "omit",
  // Resolve `fetch` per call instead of letting openapi-fetch capture
  // `globalThis.fetch` once at creation time. Required for MSW: this module is
  // imported (and the client created) before `server.listen()` swaps the global
  // in, so a captured reference would bypass every mock and hit the network.
  fetch: (request) => globalThis.fetch(request),
})

/** What every `client.GET/POST/PATCH` call resolves to. */
type FetchResult = {
  data?: unknown
  error?: unknown
  response: Response
}

/**
 * Turn an openapi-fetch result into either the parsed body or a thrown `ApiError`.
 *
 * The generic is a cast on purpose: every route in `interface/api.py` is annotated
 * `-> dict` / `-> list[dict]`, so FastAPI emits untyped `object` response schemas
 * and the generated types carry no response shape. `types.ts` holds the
 * hand-written, reviewed-against-`api.py` shapes instead, and this is where they
 * get applied.
 */
export async function unwrap<T>(call: Promise<FetchResult>): Promise<T> {
  let result: FetchResult
  try {
    result = await call
  } catch (cause) {
    // Connection refused, DNS failure, CORS rejection — never reached the API.
    // Status 0 is the marker for "no HTTP response at all".
    const error = new ApiError(
      0,
      "network_error",
      "Não foi possível falar com o servidor. Ele está rodando?",
    )
    error.cause = cause
    throw error
  }

  if (result.error !== undefined || !result.response.ok) {
    throw toApiError(result.response.status, result.error)
  }
  return result.data as T
}
