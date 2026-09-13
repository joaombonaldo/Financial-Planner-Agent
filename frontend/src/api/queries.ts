/**
 * Read hooks — one per GET endpoint.
 *
 * Components never call the client directly; they call these (specs/016-frontend-core
 * "API client and data-fetching layer"). Every hook rejects with `ApiError`.
 *
 * Query keys are plain tuples: ["months"], ["taxonomy"], ["run", monthRef],
 * ["report", monthRef], ["transactions", monthRef, filters].
 */
import { useQuery } from "@tanstack/react-query"

import { client, unwrap } from "./client"
import type {
  Instrument,
  MonthReport,
  MonthSummary,
  RunState,
  Taxonomy,
  Transaction,
} from "./types"

/** How fast to re-poll `GET .../run` while a run is actually working. */
export const RUN_POLL_INTERVAL_MS = 1000

export interface TransactionFilters {
  instrument?: string
  category?: string
  includeDeleted?: boolean
}

/** `GET /months` — the month history list. */
export function useMonths() {
  return useQuery<MonthSummary[], Error>({
    queryKey: ["months"],
    queryFn: () => unwrap<MonthSummary[]>(client.GET("/months")),
  })
}

/**
 * `GET /taxonomy` — the full category -> subcategories tree.
 *
 * Static config read off `config/categories.yaml`, not data: fetch it once and
 * keep it for the session.
 */
export function useTaxonomy() {
  return useQuery<Taxonomy, Error>({
    queryKey: ["taxonomy"],
    queryFn: () => unwrap<Taxonomy>(client.GET("/taxonomy")),
    staleTime: Infinity,
    gcTime: Infinity,
  })
}

/**
 * `GET /months/{monthRef}/run` — the review flow's state machine, polled.
 *
 * Polls every second while the last-known status is "processing" and stops on
 * every other status (not_started / pending_review / completed / error), which is
 * exactly the spec's diagram: the only state the server leaves on its own is
 * "processing".
 *
 * `opts.enabled` lets a page hold the query back until it has a monthRef.
 */
export function useRunStatus(monthRef: string, opts?: { enabled?: boolean }) {
  return useQuery<RunState, Error>({
    queryKey: ["run", monthRef],
    queryFn: () =>
      unwrap<RunState>(
        client.GET("/months/{month_ref}/run", {
          params: { path: { month_ref: monthRef } },
        }),
      ),
    enabled: (opts?.enabled ?? true) && Boolean(monthRef),
    refetchInterval: (query) =>
      query.state.data?.status === "processing" ? RUN_POLL_INTERVAL_MS : false,
  })
}

/**
 * `GET /months/{monthRef}/report` — always recomputed server-side, so a manual
 * edit shows up as soon as this refetches.
 */
export function useReport(monthRef: string) {
  return useQuery<MonthReport, Error>({
    queryKey: ["report", monthRef],
    queryFn: () =>
      unwrap<MonthReport>(
        client.GET("/months/{month_ref}/report", {
          params: { path: { month_ref: monthRef } },
        }),
      ),
    enabled: Boolean(monthRef),
  })
}

/** `GET /months/{monthRef}/transactions`, optionally narrowed. */
export function useTransactions(monthRef: string, filters?: TransactionFilters) {
  return useQuery<Transaction[], Error>({
    queryKey: ["transactions", monthRef, filters],
    queryFn: () =>
      unwrap<Transaction[]>(
        client.GET("/months/{month_ref}/transactions", {
          params: {
            path: { month_ref: monthRef },
            query: {
              // camelCase in the hook's API, snake_case on the wire.
              instrument: filters?.instrument as Instrument | undefined,
              category: filters?.category,
              include_deleted: filters?.includeDeleted,
            },
          },
        }),
      ),
    enabled: Boolean(monthRef),
  })
}
