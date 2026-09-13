import { http, HttpResponse } from "msw"
import { beforeAll, describe, expect, it, vi } from "vitest"
import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { errorResponse, url } from "@/test/mocks/handlers"
import { taxonomyFixture, transactionsFixture } from "@/test/mocks/fixtures"
import { server } from "@/test/mocks/server"
import { renderWithProviders } from "@/test/utils"
import TransactionsPage from "./TransactionsPage"

const ROUTE = "/months/2026-08/transactions"

// Radix's Select drives itself with Pointer Events APIs jsdom does not
// implement. These are the standard no-op shims; without them opening a
// dropdown throws (see ReviewPage.test.tsx).
beforeAll(() => {
  Element.prototype.hasPointerCapture = vi.fn(() => false)
  Element.prototype.setPointerCapture = vi.fn()
  Element.prototype.releasePointerCapture = vi.fn()
  Element.prototype.scrollIntoView = vi.fn()
})

const deletedTransaction = {
  ...transactionsFixture[0],
  dedup_hash: "deadbeefdeadbeefdeadbeefdeadbeef",
  description_raw: "ASSINATURA CANCELADA STREAMING",
  deleted_at: "2026-08-15T10:00:00",
}

function seedTransactions(rows = transactionsFixture) {
  server.use(
    http.get(url("/months/:monthRef/transactions"), ({ request }) => {
      const query = new URL(request.url).searchParams
      const instrument = query.get("instrument")
      const category = query.get("category")
      const includeDeleted = query.get("include_deleted") === "true"

      const filtered = rows
        .filter((t) => (instrument ? t.instrument === instrument : true))
        .filter((t) => (category ? t.category === category : true))
        .filter((t) => (includeDeleted ? true : t.deleted_at === null))

      return HttpResponse.json(filtered)
    }),
  )
}

describe("TransactionsPage", () => {
  it("renders fixture transactions with category, instrument and amount", async () => {
    seedTransactions()
    renderWithProviders(<TransactionsPage />, { route: ROUTE })

    expect(await screen.findByText("PIX ENVIADO IMOBILIARIA CENTRO")).toBeInTheDocument()
    expect(screen.getByText("RENNER LOJA 233 SAO PAULO")).toBeInTheDocument()
    expect(screen.getByText(/Moradia/)).toBeInTheDocument()
    expect(screen.getByText("Cartão de crédito")).toBeInTheDocument()
    expect(screen.getByText(/2\.450,00/)).toBeInTheDocument()
  })

  it("re-requests transactions with the selected instrument filter", async () => {
    const user = userEvent.setup()
    let lastInstrument: string | null = null
    server.use(
      http.get(url("/months/:monthRef/transactions"), ({ request }) => {
        const query = new URL(request.url).searchParams
        lastInstrument = query.get("instrument")
        const rows = transactionsFixture.filter((t) =>
          lastInstrument ? t.instrument === lastInstrument : true,
        )
        return HttpResponse.json(rows)
      }),
    )
    renderWithProviders(<TransactionsPage />, { route: ROUTE })
    await screen.findByText("PIX ENVIADO IMOBILIARIA CENTRO")

    await user.click(screen.getByRole("combobox", { name: "Instrumento" }))
    await user.click(await screen.findByRole("option", { name: "Cartão de crédito" }))

    await waitFor(() => expect(lastInstrument).toBe("credit"))
  })

  it("hides soft-deleted rows by default and shows them, muted, once included", async () => {
    const user = userEvent.setup()
    seedTransactions([...transactionsFixture, deletedTransaction])
    renderWithProviders(<TransactionsPage />, { route: ROUTE })

    await screen.findByText("PIX ENVIADO IMOBILIARIA CENTRO")
    expect(screen.queryByText("ASSINATURA CANCELADA STREAMING")).not.toBeInTheDocument()

    await user.click(screen.getByLabelText("Incluir excluídas"))

    const deletedCell = await screen.findByText("ASSINATURA CANCELADA STREAMING")
    expect(deletedCell).toBeInTheDocument()
    const row = deletedCell.closest("tr")
    expect(row).toHaveClass("line-through")
  })

  it("recategorizes a row and sends exactly {category, subcategory}", async () => {
    const user = userEvent.setup()
    seedTransactions()
    let capturedBody: unknown
    server.use(
      http.get(url("/taxonomy"), () => HttpResponse.json(taxonomyFixture)),
      http.patch(url("/transactions/:dedupHash"), async ({ request, params }) => {
        capturedBody = await request.json()
        const existing = transactionsFixture.find((t) => t.dedup_hash === params.dedupHash)!
        return HttpResponse.json({
          ...existing,
          category: "Alimentação",
          subcategory: "Supermercado",
        })
      }),
    )
    renderWithProviders(<TransactionsPage />, { route: ROUTE })

    await screen.findByText("PIX ENVIADO IMOBILIARIA CENTRO")
    const row = screen.getByText("PIX ENVIADO IMOBILIARIA CENTRO").closest("tr")!
    await user.click(within(row).getByRole("button", { name: "Editar categoria" }))

    await user.click(screen.getByRole("combobox", { name: "Categoria" }))
    await user.click(await screen.findByRole("option", { name: "Alimentação" }))

    await user.click(screen.getByRole("combobox", { name: "Subcategoria" }))
    await user.click(await screen.findByRole("option", { name: "Supermercado" }))

    await user.click(screen.getByRole("button", { name: "Salvar" }))

    await waitFor(() =>
      expect(capturedBody).toEqual({
        category: "Alimentação",
        subcategory: "Supermercado",
        deleted: null,
      }),
    )
  })

  it("asks for confirmation before soft-deleting, then sends {deleted: true}", async () => {
    const user = userEvent.setup()
    seedTransactions()
    let capturedBody: unknown
    server.use(
      http.patch(url("/transactions/:dedupHash"), async ({ request, params }) => {
        capturedBody = await request.json()
        const existing = transactionsFixture.find((t) => t.dedup_hash === params.dedupHash)!
        const body = capturedBody as { deleted?: boolean | null }
        return HttpResponse.json({
          ...existing,
          deleted_at: body.deleted === true ? "2026-09-12T12:00:00" : null,
        })
      }),
    )
    renderWithProviders(<TransactionsPage />, { route: ROUTE })

    await screen.findByText("PIX ENVIADO IMOBILIARIA CENTRO")
    const row = screen.getByText("PIX ENVIADO IMOBILIARIA CENTRO").closest("tr")!
    await user.click(within(row).getByRole("button", { name: "Excluir" }))

    // Clicking the row action only opens the confirmation -- no request yet.
    const dialog = await screen.findByRole("alertdialog")
    expect(capturedBody).toBeUndefined()

    await user.click(within(dialog).getByRole("button", { name: "Excluir" }))

    await waitFor(() =>
      expect(capturedBody).toEqual({ category: null, subcategory: null, deleted: true }),
    )
  })

  it("restores a soft-deleted row directly, with no confirmation", async () => {
    const user = userEvent.setup()
    seedTransactions([...transactionsFixture, deletedTransaction])
    let capturedBody: unknown
    server.use(
      http.patch(url("/transactions/:dedupHash"), async ({ request, params }) => {
        capturedBody = await request.json()
        const existing = deletedTransaction.dedup_hash === params.dedupHash ? deletedTransaction : transactionsFixture[0]
        return HttpResponse.json({ ...existing, deleted_at: null })
      }),
    )
    renderWithProviders(<TransactionsPage />, { route: ROUTE })

    await user.click(screen.getByLabelText("Incluir excluídas"))
    await screen.findByText("ASSINATURA CANCELADA STREAMING")
    const row = screen.getByText("ASSINATURA CANCELADA STREAMING").closest("tr")!
    await user.click(within(row).getByRole("button", { name: "Restaurar" }))

    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument()
    await waitFor(() =>
      expect(capturedBody).toEqual({ category: null, subcategory: null, deleted: false }),
    )
  })

  it("renders the empty state when there are no results", async () => {
    seedTransactions([])
    renderWithProviders(<TransactionsPage />, { route: ROUTE })

    expect(
      await screen.findByText("Nenhuma transação encontrada para os filtros selecionados."),
    ).toBeInTheDocument()
  })

  it("renders the error state on a 500", async () => {
    server.use(
      http.get(url("/months/:monthRef/transactions"), () =>
        errorResponse(500, "internal_error", "boom"),
      ),
    )
    renderWithProviders(<TransactionsPage />, { route: ROUTE })

    expect(await screen.findByText("boom")).toBeInTheDocument()
  })
})
