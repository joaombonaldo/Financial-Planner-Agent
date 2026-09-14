import { http, HttpResponse } from "msw"
import { beforeAll, describe, expect, it, vi } from "vitest"
import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { errorResponse, url } from "@/test/mocks/handlers"
import { defaultBudgetFixture } from "@/test/mocks/fixtures"
import { server } from "@/test/mocks/server"
import { renderWithProviders } from "@/test/utils"
import BudgetPage from "./BudgetPage"

const ROUTE = "/budget"

// Radix's Select drives itself with Pointer Events APIs jsdom does not
// implement — standard no-op shims (see TransactionsPage.test.tsx).
beforeAll(() => {
  Element.prototype.hasPointerCapture = vi.fn(() => false)
  Element.prototype.setPointerCapture = vi.fn()
  Element.prototype.releasePointerCapture = vi.fn()
  Element.prototype.scrollIntoView = vi.fn()
})

describe("BudgetPage", () => {
  it("renders the default goals as editable rows", async () => {
    renderWithProviders(<BudgetPage />, { route: ROUTE })

    expect(await screen.findByDisplayValue("800")).toBeInTheDocument()
    expect(screen.getAllByRole("combobox", { name: "Categoria" })).toHaveLength(
      Object.keys(defaultBudgetFixture).length,
    )
  })

  it("saves the edited goal set via PUT /budget", async () => {
    const user = userEvent.setup()
    let capturedBody: unknown
    server.use(
      http.put(url("/budget"), async ({ request }) => {
        capturedBody = await request.json()
        return HttpResponse.json({ Alimentação: 900, Transporte: 300, Lazer: 200 })
      }),
    )
    renderWithProviders(<BudgetPage />, { route: ROUTE })

    const amountInput = await screen.findByDisplayValue("800")
    await user.clear(amountInput)
    await user.type(amountInput, "900")

    await user.click(screen.getByRole("button", { name: "Salvar" }))

    await waitFor(() => expect(capturedBody).toBeDefined())
    expect(capturedBody).toMatchObject({
      goals: { Alimentação: 900, Transporte: 300, Lazer: 200 },
    })
  })

  it("removes a category row and saves without it", async () => {
    const user = userEvent.setup()
    let capturedBody: unknown
    server.use(
      http.put(url("/budget"), async ({ request }) => {
        capturedBody = await request.json()
        return HttpResponse.json({ Transporte: 300, Lazer: 200 })
      }),
    )
    renderWithProviders(<BudgetPage />, { route: ROUTE })

    await screen.findByDisplayValue("800")
    await user.click(screen.getAllByRole("button", { name: "Remover meta" })[0])
    await user.click(screen.getByRole("button", { name: "Salvar" }))

    await waitFor(() => expect(capturedBody).toBeDefined())
    expect(capturedBody).toMatchObject({ goals: { Transporte: 300, Lazer: 200 } })
  })

  it("shows the error message when loading the default budget fails", async () => {
    server.use(http.get(url("/budget"), () => errorResponse(500, "internal_error", "boom")))
    renderWithProviders(<BudgetPage />, { route: ROUTE })

    expect(await screen.findByText(/boom|internal_error|Erro/i)).toBeInTheDocument()
  })
})
