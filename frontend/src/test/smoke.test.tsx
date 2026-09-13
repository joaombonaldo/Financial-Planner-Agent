/**
 * Harness smoke test: proves the pieces every page depends on actually work —
 * rendering through the shared shell, routing to the real Wave 2 pages (not
 * exhaustive per-page coverage, that's each page's own colocated test file),
 * MSW interception, and the ApiError envelope.
 */
import { screen, waitFor } from "@testing-library/react"
import { http } from "msw"
import { describe, expect, it } from "vitest"

import { ApiError, client, unwrap } from "@/api/client"
import type { MonthSummary } from "@/api/types"
import { errorResponse, url } from "./mocks/handlers"
import { monthsFixture } from "./mocks/fixtures"
import { server } from "./mocks/server"
import { renderApp, renderInLayout } from "./utils"

describe("test harness", () => {
  it("renders the shared layout around a child", () => {
    renderInLayout(<div>conteúdo</div>, { route: "/months/2026-08/review" })

    expect(screen.getByText("Planejador Financeiro")).toBeInTheDocument()
    expect(screen.getByText("conteúdo")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Novo mês" })).toBeInTheDocument()
  })

  it("redirects / to /months", async () => {
    renderApp({ route: "/" })

    expect(await screen.findByText("Meses processados")).toBeInTheDocument()
  })

  it("routes to the real page for every screen (Wave 2, post-stub)", async () => {
    for (const [route, text] of [
      ["/months/2026-08/upload", "Enviar extratos"],
      ["/months/2026-08/review", "Revisão pendente"],
      ["/months/2026-08/report", "Relatório de"],
      ["/months/2026-08/transactions", "Transações"],
    ] as const) {
      const { unmount } = renderApp({ route })
      expect((await screen.findAllByText(text, { exact: false })).length).toBeGreaterThan(0)
      unmount()
    }
  })

  it("serves API calls from MSW, never a real backend", async () => {
    const months = await unwrap<MonthSummary[]>(client.GET("/months"))

    expect(months).toEqual(monthsFixture)
  })

  it("turns the error envelope into a typed ApiError", async () => {
    server.use(
      http.get(url("/months"), () =>
        errorResponse(500, "internal_error", "Processing failed."),
      ),
    )

    const error = await unwrap(client.GET("/months")).catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({
      code: "internal_error",
      message: "Processing failed.",
      status: 500,
    })
  })

  it("resets overrides between tests", async () => {
    await waitFor(async () => {
      expect(await unwrap<MonthSummary[]>(client.GET("/months"))).toEqual(monthsFixture)
    })
  })
})
