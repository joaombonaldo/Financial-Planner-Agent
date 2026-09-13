/**
 * The app's API vocabulary. **Import types from here, never from
 * `./generated/schema` directly** — that is the entire reason this file exists.
 *
 * Two kinds of types live here:
 *
 * 1. *Derived* — request bodies and query params, aliased straight off the
 *    generated schema (`components["schemas"][...]`). FastAPI models them with
 *    Pydantic (`RunRequest`, `ReviewRequest`, `TransactionPatch`, `Instrument`),
 *    so these are genuinely generated and will break loudly if the backend changes.
 *
 * 2. *Hand-written* — response bodies. Every route in `interface/api.py` is
 *    annotated `-> dict` / `-> list[dict]`, so its OpenAPI response schema is an
 *    untyped `object` and the generator has nothing to work with. These
 *    interfaces are therefore transcribed by hand from the real serializers and
 *    must be kept in step with them:
 *      - `Transaction`  <- `_serialize_transaction` (api.py)
 *      - `MonthReport`  <- `_serialize_report` (api.py)
 *      - `ReviewItem`   <- `_build_payload` (nodes/review.py)
 *      - `MonthSummary` <- `list_month_summaries` (nodes/queries.py)
 *      - `RunState`     <- `RunState.to_response` (api.py)
 *      - `Taxonomy`     <- `get_taxonomy` (nodes/queries.py)
 */
import type { components } from "./generated/schema"

// --- derived from the generated schema -------------------------------------------

/** `"debit" | "credit"` — the payment stream (state.py `Instrument`). */
export type Instrument = components["schemas"]["Instrument"]

/** Body of `POST /months/{monthRef}/run`. */
export type RunRequest = components["schemas"]["RunRequest"]

/** Body of `POST /months/{monthRef}/review`. */
export type ReviewRequest = components["schemas"]["ReviewRequest"]

/** The three answers the review flow can submit. */
export type ReviewAction = ReviewRequest["action"]

/** Body of `PATCH /transactions/{dedupHash}`. */
export type TransactionPatch = components["schemas"]["TransactionPatch"]

// --- hand-written response shapes -------------------------------------------------

/** `"income" | "expense"` (state.py `TransactionType`). */
export type TransactionType = "income" | "expense"

/** `"bradesco" | "inter"` (state.py `Bank`). Widened: a new bank must not break the UI. */
export type Bank = "bradesco" | "inter" | (string & {})

/** One row of `GET /months/{monthRef}/transactions` and of `PATCH /transactions/{hash}`. */
export interface Transaction {
  dedup_hash: string
  /** ISO date, `YYYY-MM-DD`. */
  date: string
  description_raw: string
  account: Bank
  type: TransactionType
  amount: number
  /** `YYYY-MM`. */
  month_ref: string
  category: string | null
  subcategory: string | null
  confidence: string | null
  instrument: Instrument
  fatura_ref: string | null
  /** Soft delete: `null` means active. */
  deleted_at: string | null
}

/** One row of `GET /months`. */
export interface MonthSummary {
  /** `YYYY-MM`. */
  month_ref: string
  /** Both streams, debit and credit. */
  transaction_count: number
  has_pending_review: boolean
}

/** The full category -> subcategories tree from `GET /taxonomy`. */
export type Taxonomy = Record<string, string[]>

/** One entry of `report.category_breakdown`. */
export interface CategoryTotal {
  category: string
  type: TransactionType
  total: number
  gross: number
  reimbursed: number
}

/** One entry of `report.credit_category_breakdown` (no reimbursement split). */
export interface CreditCategoryTotal {
  category: string
  type: TransactionType
  total: number
}

/** `"within_budget" | "over_budget"` (state.py `BudgetStatus`). */
export type BudgetStatus = "within_budget" | "over_budget"

/** One entry of `report.budget_report`. Empty array when no budget is configured. */
export interface BudgetComparison {
  category: string
  goal: number
  actual_spend: number
  difference: number
  status: BudgetStatus
}

/** One entry of `report.fatura_reconciliations` (credit-card statement vs. purchases). */
export interface FaturaReconciliation {
  fatura_ref: string
  debit_payment: number
  credit_purchases_total: number
  delta: number
}

/** `GET /months/{monthRef}/report`, and the `report` field of a completed run. */
export interface MonthReport {
  month_ref: string
  total_income: number
  total_expense: number
  net_balance: number
  transfer_total: number
  category_breakdown: CategoryTotal[]
  transaction_count: number
  budget_report: BudgetComparison[]
  /** Free-form LLM text. Render as plain text — never `dangerouslySetInnerHTML`. */
  insights_summary: string | null
  insights_error: string | null
  total_reimbursements: number
  unattributed_reimbursements: number
  credit_category_breakdown: CreditCategoryTotal[]
  credit_total: number
  fatura_reconciliations: FaturaReconciliation[]
}

/**
 * The transaction as it appears *inside a review item* — a narrower projection
 * than `Transaction`: `_build_payload` sends only these eight fields (no
 * `dedup_hash`, no `type`, no `month_ref`).
 */
export interface ReviewItemTransaction {
  /** ISO date, `YYYY-MM-DD`. */
  date: string
  description_raw: string
  amount: number
  account: Bank
  category: string | null
  subcategory: string | null
  confidence: string | null
  instrument: Instrument
}

/** The pending review item, exactly `nodes/review.py:_build_payload`'s nested shape. */
export interface ReviewItem {
  transaction: ReviewItemTransaction
  is_transfer_candidate: boolean
  /** Subcategories of the *currently suggested* category only — pair with `useTaxonomy()`. */
  suggested_subcategories: string[]
  /**
   * Only ever set by the CLI's re-ask loop. Over HTTP an invalid answer is a 422
   * on the POST, so this is never present in practice (spec: "Rendering the
   * pending item").
   */
  error?: string
}

/** The run status union driving the review flow's client state machine. */
export type RunStatus =
  | "not_started"
  | "processing"
  | "pending_review"
  | "completed"
  | "error"

/**
 * `GET /months/{monthRef}/run` — a discriminated union, because `to_response`
 * only includes the field that belongs to the current status.
 */
export type RunState =
  | { status: "not_started" }
  | { status: "processing" }
  | { status: "pending_review"; item: ReviewItem }
  | { status: "completed"; report: MonthReport | null }
  | { status: "error"; message: string }

/** `POST /months/{monthRef}/uploads` — the saved server-side paths, to feed into a run. */
export interface UploadResponse {
  files: string[]
}
