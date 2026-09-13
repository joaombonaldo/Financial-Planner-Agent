/**
 * Contract test for the hook layer Wave 2 builds on: the query keys, the poll
 * gating, and the PATCH invalidation the spec requires hooks (not pages) to own.
 */
import { QueryClientProvider } from "@tanstack/react-query"
import { renderHook, waitFor } from "@testing-library/react"
import { http, HttpResponse } from "msw"
import type { ReactNode } from "react"
import { describe, expect, it } from "vitest"

import { ApiError } from "@/api/client"
import { usePatchTransaction, useStartRun } from "@/api/mutations"
import { useMonths, useReport, useRunStatus, useTaxonomy, useTransactions } from "@/api/queries"
import { monthsFixture, MONTH_REF, taxonomyFixture, transactionsFixture } from "./mocks/fixtures"
import { errorResponse, url } from "./mocks/handlers"
import { server } from "./mocks/server"
import { createTestQueryClient } from "./utils"

function wrapperFor(queryClient = createTestQueryClient()) {
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return { Wrapper, queryClient }
}

describe("query hooks", () => {
  it("useMonths returns the month history", async () => {
    const { Wrapper } = wrapperFor()
    const { result } = renderHook(() => useMonths(), { wrapper: Wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(monthsFixture)
  })

  it("useTaxonomy returns the full tree", async () => {
    const { Wrapper } = wrapperFor()
    const { result } = renderHook(() => useTaxonomy(), { wrapper: Wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(taxonomyFixture)
  })

  it("useRunStatus surfaces the pending review item", async () => {
    const { Wrapper } = wrapperFor()
    const { result } = renderHook(() => useRunStatus(MONTH_REF), { wrapper: Wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.status).toBe("pending_review")
  })

  it("useRunStatus does not fire when disabled", () => {
    const { Wrapper } = wrapperFor()
    const { result } = renderHook(() => useRunStatus(MONTH_REF, { enabled: false }), {
      wrapper: Wrapper,
    })

    expect(result.current.fetchStatus).toBe("idle")
  })

  it("useReport returns the month's report", async () => {
    const { Wrapper } = wrapperFor()
    const { result } = renderHook(() => useReport(MONTH_REF), { wrapper: Wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.month_ref).toBe(MONTH_REF)
    expect(result.current.data?.budget_report).toHaveLength(2)
  })

  it("useTransactions passes filters through as query params", async () => {
    const { Wrapper } = wrapperFor()
    const { result } = renderHook(
      () => useTransactions(MONTH_REF, { instrument: "credit" }),
      { wrapper: Wrapper },
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toHaveLength(1)
    expect(result.current.data?.[0].instrument).toBe("credit")
  })

  it("rejects with a typed ApiError", async () => {
    server.use(
      http.get(url("/months/:monthRef/report"), () =>
        errorResponse(404, "not_found", "Transaction not found"),
      ),
    )
    const { Wrapper } = wrapperFor()
    const { result } = renderHook(() => useReport(MONTH_REF), { wrapper: Wrapper })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error).toBeInstanceOf(ApiError)
    expect((result.current.error as ApiError).code).toBe("not_found")
  })
})

describe("mutation hooks", () => {
  it("useStartRun primes the run cache from its 202 response", async () => {
    const { Wrapper, queryClient } = wrapperFor()
    const { result } = renderHook(() => useStartRun(), { wrapper: Wrapper })

    result.current.mutate({ monthRef: MONTH_REF, files: ["extracts/2026-08/a.csv"] })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(queryClient.getQueryData(["run", MONTH_REF])).toEqual({ status: "processing" })
  })

  it("usePatchTransaction invalidates transactions and report for that month", async () => {
    const { Wrapper, queryClient } = wrapperFor()

    // Seed both caches as a page would have them.
    queryClient.setQueryData(["transactions", MONTH_REF, undefined], transactionsFixture)
    queryClient.setQueryData(["report", MONTH_REF], { month_ref: MONTH_REF })

    const { result } = renderHook(() => usePatchTransaction(), { wrapper: Wrapper })
    result.current.mutate({
      dedupHash: transactionsFixture[0].dedup_hash,
      category: "Lazer",
      subcategory: "Viagens",
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    await waitFor(() => {
      expect(
        queryClient.getQueryState(["transactions", MONTH_REF, undefined])?.isInvalidated,
      ).toBe(true)
      expect(queryClient.getQueryState(["report", MONTH_REF])?.isInvalidated).toBe(true)
    })
  })

  it("usePatchTransaction sends a soft delete as {deleted: true}", async () => {
    let sent: unknown
    server.use(
      http.patch(url("/transactions/:dedupHash"), async ({ request }) => {
        sent = await request.json()
        return HttpResponse.json({
          ...transactionsFixture[0],
          deleted_at: "2026-09-12T12:00:00",
        })
      }),
    )
    const { Wrapper } = wrapperFor()
    const { result } = renderHook(() => usePatchTransaction(), { wrapper: Wrapper })

    result.current.mutate({ dedupHash: transactionsFixture[0].dedup_hash, deleted: true })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    // `category: null` is what the API reads as "not recategorizing".
    expect(sent).toEqual({ category: null, subcategory: null, deleted: true })
    expect(result.current.data?.deleted_at).not.toBeNull()
  })
})
