import { screen, within } from "@testing-library/react"
import { http, HttpResponse } from "msw"
import { describe, expect, it } from "vitest"

import { errorResponse, url } from "@/test/mocks/handlers"
import { server } from "@/test/mocks/server"
import { renderWithProviders } from "@/test/utils"

import MonthsPage from "./MonthsPage"

// The "Novo mês" form itself (format validation, navigating to /upload) is
// tested at @/components/NewMonthDialog.test.tsx — it moved into the shared
// nav (Layout.tsx) so it's reachable from every screen, not just this one.

describe("MonthsPage", () => {
  it("renders the fixture months with transaction counts and pending-review status", async () => {
    renderWithProviders(<MonthsPage />, { route: "/months" })

    expect(await screen.findByText("2026-08")).toBeInTheDocument()
    expect(screen.getByText("2026-07")).toBeInTheDocument()

    const rowAugust = screen.getByText("2026-08").closest("tr")
    const rowJuly = screen.getByText("2026-07").closest("tr")
    expect(rowAugust).not.toBeNull()
    expect(rowJuly).not.toBeNull()

    expect(within(rowAugust as HTMLElement).getByText("142")).toBeInTheDocument()
    expect(within(rowAugust as HTMLElement).getByText("Revisão pendente")).toBeInTheDocument()

    expect(within(rowJuly as HTMLElement).getByText("118")).toBeInTheDocument()
    expect(within(rowJuly as HTMLElement).queryByText("Revisão pendente")).not.toBeInTheDocument()
  })

  it("links a month with pending review toward the review screen", async () => {
    renderWithProviders(<MonthsPage />, { route: "/months" })

    const row = (await screen.findByText("2026-08")).closest("tr") as HTMLElement
    const link = within(row).getByRole("link", { name: "Revisar" })
    expect(link).toHaveAttribute("href", "/months/2026-08/review")
  })

  it("links a month without pending review toward the report screen", async () => {
    renderWithProviders(<MonthsPage />, { route: "/months" })

    const row = (await screen.findByText("2026-07")).closest("tr") as HTMLElement
    const link = within(row).getByRole("link", { name: "Ver relatório" })
    expect(link).toHaveAttribute("href", "/months/2026-07/report")
  })

  it("renders the empty state, not an error, for an empty list", async () => {
    server.use(http.get(url("/months"), () => HttpResponse.json([])))

    renderWithProviders(<MonthsPage />, { route: "/months" })

    expect(await screen.findByText("Nenhum mês processado ainda.")).toBeInTheDocument()
  })

  it("renders the error message on a failed request", async () => {
    server.use(http.get(url("/months"), () => errorResponse(500, "internal_error", "Falha no servidor.")))

    renderWithProviders(<MonthsPage />, { route: "/months" })

    expect(await screen.findByText("Falha no servidor.")).toBeInTheDocument()
  })
})
