import { QueryClientProvider } from "@tanstack/react-query"
import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { http, HttpResponse } from "msw"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { describe, expect, it } from "vitest"

import { errorResponse, url } from "@/test/mocks/handlers"
import { server } from "@/test/mocks/server"
import { createTestQueryClient, renderWithProviders } from "@/test/utils"

import MonthsPage from "./MonthsPage"

/**
 * Renders `MonthsPage` alongside a stand-in `/months/:monthRef/upload` route so
 * the "Novo mês" form's `navigate()` target is observable, not just its intent.
 */
function renderWithUploadRoute() {
  const queryClient = createTestQueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/months"]}>
        <Routes>
          <Route path="/months" element={<MonthsPage />} />
          <Route
            path="/months/:monthRef/upload"
            element={<div>Upload screen placeholder</div>}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

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
    expect(screen.getByRole("button", { name: "Novo mês" })).toBeInTheDocument()
  })

  it("renders the error message on a failed request", async () => {
    server.use(http.get(url("/months"), () => errorResponse(500, "internal_error", "Falha no servidor.")))

    renderWithProviders(<MonthsPage />, { route: "/months" })

    expect(await screen.findByText("Falha no servidor.")).toBeInTheDocument()
  })

  it("rejects an invalid month reference in the new-month form", async () => {
    const user = userEvent.setup()
    renderWithProviders(<MonthsPage />, { route: "/months" })

    await user.click(await screen.findByRole("button", { name: "Novo mês" }))
    const input = await screen.findByLabelText("Mês (AAAA-MM)")
    await user.type(input, "2026-13")

    expect(screen.getByText(/Formato inválido/)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Continuar" })).toBeDisabled()
  })

  it("navigates to the upload screen for a valid month reference", async () => {
    const user = userEvent.setup()
    renderWithUploadRoute()

    await user.click(await screen.findByRole("button", { name: "Novo mês" }))
    const input = await screen.findByLabelText("Mês (AAAA-MM)")
    await user.type(input, "2026-09")

    const continueButton = screen.getByRole("button", { name: "Continuar" })
    expect(continueButton).toBeEnabled()
    await user.click(continueButton)

    expect(await screen.findByText("Upload screen placeholder")).toBeInTheDocument()
  })
})
