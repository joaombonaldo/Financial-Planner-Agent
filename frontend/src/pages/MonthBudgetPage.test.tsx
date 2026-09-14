import { http, HttpResponse } from "msw"
import { beforeAll, describe, expect, it, vi } from "vitest"
import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { errorResponse, url } from "@/test/mocks/handlers"
import { monthBudgetFixture } from "@/test/mocks/fixtures"
import { server } from "@/test/mocks/server"
import { renderWithProviders } from "@/test/utils"
import MonthBudgetPage from "./MonthBudgetPage"

const ROUTE = "/months/2026-08/budget"

beforeAll(() => {
  Element.prototype.hasPointerCapture = vi.fn(() => false)
  Element.prototype.setPointerCapture = vi.fn()
  Element.prototype.releasePointerCapture = vi.fn()
  Element.prototype.scrollIntoView = vi.fn()
})

describe("MonthBudgetPage", () => {
  it("renders this month's overrides and the merged effective table", async () => {
    renderWithProviders(<MonthBudgetPage />, { route: ROUTE })

    expect(await screen.findByDisplayValue("500")).toBeInTheDocument()
    expect(screen.getByText("Metas efetivas neste mês")).toBeInTheDocument()
    expect(screen.getByText("Alimentação")).toBeInTheDocument()
    expect(screen.getByText(/300,00/)).toBeInTheDocument()
  })

  it("saves the edited overrides via PUT /months/:monthRef/budget", async () => {
    const user = userEvent.setup()
    let capturedBody: unknown
    server.use(
      http.put(url("/months/:monthRef/budget"), async ({ request }) => {
        capturedBody = await request.json()
        return HttpResponse.json({
          overrides: { Lazer: 600 },
          effective: { ...monthBudgetFixture.effective, Lazer: 600 },
        })
      }),
    )
    renderWithProviders(<MonthBudgetPage />, { route: ROUTE })

    const amountInput = await screen.findByDisplayValue("500")
    await user.clear(amountInput)
    await user.type(amountInput, "600")
    await user.click(screen.getByRole("button", { name: "Salvar" }))

    await waitFor(() => expect(capturedBody).toBeDefined())
    expect(capturedBody).toMatchObject({ goals: { Lazer: 600 } })
  })

  it("shows the error message when loading the month budget fails", async () => {
    server.use(
      http.get(url("/months/:monthRef/budget"), () => errorResponse(500, "internal_error", "boom")),
    )
    renderWithProviders(<MonthBudgetPage />, { route: ROUTE })

    expect(await screen.findByText(/boom|internal_error|Erro/i)).toBeInTheDocument()
  })
})
