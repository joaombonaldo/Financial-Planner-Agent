/**
 * Write hooks — one per POST/PATCH endpoint.
 *
 * Cache invalidation lives here, not in pages: a page must never have to
 * remember that editing a transaction also changes the report
 * (specs/016-frontend-core "Query invalidation").
 *
 * Every mutation rejects with `ApiError`.
 */
import { useMutation, useQueryClient } from "@tanstack/react-query"

import { client, unwrap } from "./client"
import type {
  Instrument,
  ReviewAction,
  RunState,
  Transaction,
  TransactionType,
  UploadResponse,
} from "./types"

export interface UploadFilesInput {
  monthRef: string
  files: File[]
}

export interface StartRunInput {
  monthRef: string
  /** Server-side paths returned by `useUploadFiles` — not local filenames. */
  files: string[]
  budgetPath?: string
}

export interface AnswerReviewInput {
  monthRef: string
  action: ReviewAction
  category?: string
  subcategory?: string
}

export interface PatchTransactionInput {
  dedupHash: string
  category?: string
  subcategory?: string
  deleted?: boolean
}

export interface CreateTransactionInput {
  /** ISO date, `YYYY-MM-DD` — its `YYYY-MM` decides which month this lands in. */
  date: string
  descriptionRaw: string
  // Deliberately the strict pair, not the app's widened `Bank` display type
  // (`"bradesco" | "inter" | (string & {})`) — a new transaction is always one
  // of the two known accounts, never an arbitrary server-supplied value.
  account: "bradesco" | "inter"
  type: TransactionType
  amount: number
  category: string
  subcategory?: string
  instrument?: Instrument
}

/**
 * `POST /months/{monthRef}/uploads` — multipart, one `files` part per file.
 *
 * Resolves to the saved server-side paths; feed those straight into `useStartRun`
 * (the run endpoint rejects any path outside `extracts/`).
 */
export function useUploadFiles() {
  return useMutation<UploadResponse, Error, UploadFilesInput>({
    mutationFn: ({ monthRef, files }) => {
      const form = new FormData()
      for (const file of files) form.append("files", file)
      return unwrap<UploadResponse>(
        client.POST("/months/{month_ref}/uploads", {
          params: { path: { month_ref: monthRef } },
          // FormData, not JSON: let the browser set the multipart boundary.
          body: form as unknown as never,
          bodySerializer: (body: unknown) => body as FormData,
        }),
      )
    },
  })
}

/**
 * `POST /months/{monthRef}/run` — starts (or safely re-starts) the run.
 *
 * Returns `202` with the run's current state, so the answer is primed straight
 * into the `["run", monthRef]` cache and the poller picks up from there without
 * a wasted round trip.
 */
export function useStartRun() {
  const queryClient = useQueryClient()
  return useMutation<RunState, Error, StartRunInput>({
    mutationFn: ({ monthRef, files, budgetPath }) =>
      unwrap<RunState>(
        client.POST("/months/{month_ref}/run", {
          params: { path: { month_ref: monthRef } },
          body: { files, budget_path: budgetPath ?? null },
        }),
      ),
    onSuccess: (data, { monthRef }) => {
      queryClient.setQueryData(["run", monthRef], data)
      void queryClient.invalidateQueries({ queryKey: ["months"] })
    },
  })
}

/**
 * `POST /months/{monthRef}/review` — answers the pending item.
 *
 * Also `202` with the new state ("processing"), which is why the spec says to
 * resume polling right after this call instead of waiting for a fresh GET.
 */
export function useAnswerReview() {
  const queryClient = useQueryClient()
  return useMutation<RunState, Error, AnswerReviewInput>({
    mutationFn: ({ monthRef, action, category, subcategory }) =>
      unwrap<RunState>(
        client.POST("/months/{month_ref}/review", {
          params: { path: { month_ref: monthRef } },
          body: {
            action,
            category: category ?? null,
            subcategory: subcategory ?? null,
          },
        }),
      ),
    onSuccess: (data, { monthRef }) => {
      queryClient.setQueryData(["run", monthRef], data)
    },
  })
}

/**
 * `PATCH /transactions/{dedupHash}` — recategorize, or soft-delete/restore.
 *
 * Send either `{category, subcategory}` or `{deleted}`, never both — the API
 * returns 422 for the combination.
 *
 * The response carries `month_ref`, so the month whose caches to invalidate is
 * known without the caller passing it: both `["transactions", monthRef]` and
 * `["report", monthRef]` change immediately server-side.
 */
export function usePatchTransaction() {
  const queryClient = useQueryClient()
  return useMutation<Transaction, Error, PatchTransactionInput>({
    mutationFn: ({ dedupHash, category, subcategory, deleted }) =>
      unwrap<Transaction>(
        client.PATCH("/transactions/{dedup_hash}", {
          params: { path: { dedup_hash: dedupHash } },
          body: {
            category: category ?? null,
            subcategory: subcategory ?? null,
            deleted: deleted ?? null,
          },
        }),
      ),
    onSuccess: (transaction) => {
      const monthRef = transaction.month_ref
      // Prefix match: ["transactions", monthRef, filters] invalidates for every
      // filter combination currently cached for that month.
      void queryClient.invalidateQueries({ queryKey: ["transactions", monthRef] })
      void queryClient.invalidateQueries({ queryKey: ["report", monthRef] })
    },
  })
}

/**
 * `POST /transactions` — a hand-entered transaction the statement never had
 * (e.g. cash spending). `date` decides the month it lands in server-side; the
 * caller doesn't pick a `monthRef` directly.
 *
 * Invalidates that month's transactions/report/months-list caches on success —
 * same reasoning as `usePatchTransaction`.
 */
export function useCreateTransaction() {
  const queryClient = useQueryClient()
  return useMutation<Transaction, Error, CreateTransactionInput>({
    mutationFn: (input) =>
      unwrap<Transaction>(
        client.POST("/transactions", {
          body: {
            date: input.date,
            description_raw: input.descriptionRaw,
            account: input.account,
            type: input.type,
            amount: input.amount,
            category: input.category,
            subcategory: input.subcategory ?? null,
            instrument: input.instrument ?? "debit",
          },
        }),
      ),
    onSuccess: (transaction) => {
      const monthRef = transaction.month_ref
      void queryClient.invalidateQueries({ queryKey: ["transactions", monthRef] })
      void queryClient.invalidateQueries({ queryKey: ["report", monthRef] })
      void queryClient.invalidateQueries({ queryKey: ["months"] })
    },
  })
}
