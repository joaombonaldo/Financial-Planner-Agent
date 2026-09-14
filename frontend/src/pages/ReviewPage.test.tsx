/**
 * ReviewPage — one test per transition of the spec's client state machine
 * (specs/016-frontend-core "The review flow — client state machine").
 *
 * Every `GET .../run` leg is an MSW override; the default handler already
 * serves "pending_review", which is the resting state most tests want.
 */
import { QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { http, HttpResponse } from "msw"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { beforeAll, describe, expect, it, vi } from "vitest"

import type { ReviewRequest, RunRequest } from "@/api/types"
import ReviewPage from "@/pages/ReviewPage"
import { errorResponse, url } from "@/test/mocks/handlers"
import {
  reportFixture,
  reviewItemFixture,
  taxonomyFixture,
  transferReviewItemFixture,
} from "@/test/mocks/fixtures"
import { server } from "@/test/mocks/server"
import { createTestQueryClient, renderWithProviders } from "@/test/utils"

const ROUTE = "/months/2026-08/review"

// Radix's Select drives itself with Pointer Events APIs jsdom does not
// implement. These are the standard no-op shims; without them opening the
// category dropdown throws.
beforeAll(() => {
  Element.prototype.hasPointerCapture = vi.fn(() => false)
  Element.prototype.setPointerCapture = vi.fn()
  Element.prototype.releasePointerCapture = vi.fn()
  Element.prototype.scrollIntoView = vi.fn()
})

/** `GET .../run` answering with a fixed state. */
function runStatus(body: unknown) {
  return http.get(url("/months/:monthRef/run"), () => HttpResponse.json(body))
}

/**
 * Renders the page inside a router whose initial entry carries `state`, which
 * `renderWithProviders`'s string-only `route` cannot express.
 */
function renderWithRouterState(state: unknown) {
  const queryClient = createTestQueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[{ pathname: ROUTE, state }]}>
        <Routes>
          <Route path="/months/:monthRef/review" element={<ReviewPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe("ReviewPage", () => {
  it("silently resolves 'not_started' instead of asking to re-upload", async () => {
    // "not_started" means the backend's in-memory registry doesn't recognize
    // this month, not that it was never processed (specs/015's registry is
    // ephemeral) -- this page has no standing "Revisão" nav entry (Layout), so
    // the only sane behavior on landing here in that state is to resolve it,
    // not hand the user a dead end.
    const bodies: RunRequest[] = []
    server.use(
      runStatus({ status: "not_started" }),
      http.post(url("/months/:monthRef/run"), async ({ request }) => {
        bodies.push((await request.json()) as RunRequest)
        return HttpResponse.json({ status: "processing" }, { status: 202 })
      }),
    )
    renderWithProviders(<ReviewPage />, { route: ROUTE })

    expect(await screen.findByText("Verificando o mês...")).toBeInTheDocument()
    await waitFor(() => expect(bodies).toHaveLength(1))
    expect(bodies[0].files).toEqual([])
  })

  it("carries files from the upload screen when auto-resolving 'not_started'", async () => {
    const uploaded = ["extracts/2026-08/bradesco.csv", "extracts/2026-08/inter.pdf"]
    const bodies: RunRequest[] = []
    server.use(
      runStatus({ status: "not_started" }),
      http.post(url("/months/:monthRef/run"), async ({ request }) => {
        bodies.push((await request.json()) as RunRequest)
        return HttpResponse.json({ status: "processing" }, { status: 202 })
      }),
    )
    renderWithRouterState({ files: uploaded })

    await waitFor(() => expect(bodies).toHaveLength(1))
    expect(bodies[0].files).toEqual(uploaded)
  })

  it("shows an error if auto-resolving 'not_started' itself fails", async () => {
    server.use(
      runStatus({ status: "not_started" }),
      http.post(url("/months/:monthRef/run"), () =>
        errorResponse(500, "internal_error", "falha ao iniciar o processamento"),
      ),
    )
    renderWithProviders(<ReviewPage />, { route: ROUTE })

    expect(await screen.findByText("falha ao iniciar o processamento")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Tentar novamente" })).toBeInTheDocument()
  })

  it("shows a loading state while the run is processing", async () => {
    server.use(runStatus({ status: "processing" }))
    renderWithProviders(<ReviewPage />, { route: ROUTE })

    expect(await screen.findByText("Processando...")).toBeInTheDocument()
  })

  it("renders the pending item and accepts it", async () => {
    const bodies: ReviewRequest[] = []
    server.use(
      http.post(url("/months/:monthRef/review"), async ({ request }) => {
        bodies.push((await request.json()) as ReviewRequest)
        return HttpResponse.json({ status: "processing" }, { status: 202 })
      }),
    )
    renderWithProviders(<ReviewPage />, { route: ROUTE })

    expect(await screen.findByText("Revisão pendente")).toBeInTheDocument()
    expect(screen.getByText(reviewItemFixture.transaction.description_raw)).toBeInTheDocument()
    expect(screen.getByText(reviewItemFixture.transaction.date)).toBeInTheDocument()
    expect(screen.getByText(/250,75/)).toBeInTheDocument()
    expect(screen.getByText(reviewItemFixture.transaction.account)).toBeInTheDocument()
    // instrument: "credit" — the reviewer must see which stream this is.
    expect(screen.getByText("cartão de crédito")).toBeInTheDocument()

    await userEvent.click(screen.getByRole("button", { name: "Aceitar" }))

    await waitFor(() => expect(bodies).toHaveLength(1))
    expect(bodies[0].action).toBe("accept")
  })

  it("offers 'Confirmar transferência' instead of 'Aceitar' for a transfer candidate", async () => {
    const bodies: ReviewRequest[] = []
    server.use(
      runStatus({ status: "pending_review", item: transferReviewItemFixture }),
      http.post(url("/months/:monthRef/review"), async ({ request }) => {
        bodies.push((await request.json()) as ReviewRequest)
        return HttpResponse.json({ status: "processing" }, { status: 202 })
      }),
    )
    renderWithProviders(<ReviewPage />, { route: ROUTE })

    const confirm = await screen.findByRole("button", { name: "Confirmar transferência" })
    expect(screen.queryByRole("button", { name: "Aceitar" })).not.toBeInTheDocument()

    await userEvent.click(confirm)

    await waitFor(() => expect(bodies).toHaveLength(1))
    expect(bodies[0].action).toBe("confirm_transfer")
  })

  it("corrects the category with a subcategory drawn from the taxonomy", async () => {
    const bodies: ReviewRequest[] = []
    server.use(
      http.post(url("/months/:monthRef/review"), async ({ request }) => {
        bodies.push((await request.json()) as ReviewRequest)
        return HttpResponse.json({ status: "processing" }, { status: 202 })
      }),
    )
    renderWithProviders(<ReviewPage />, { route: ROUTE })

    await userEvent.click(await screen.findByRole("button", { name: "Corrigir" }))

    // A category other than the item's suggested one, so its subcategories come
    // from the taxonomy rather than `suggested_subcategories`.
    await userEvent.click(screen.getByRole("combobox", { name: "Categoria" }))
    await userEvent.click(await screen.findByRole("option", { name: "Alimentação" }))

    await userEvent.click(await screen.findByRole("combobox", { name: "Subcategoria" }))
    for (const name of taxonomyFixture["Alimentação"]) {
      expect(await screen.findByRole("option", { name })).toBeInTheDocument()
    }
    await userEvent.click(screen.getByRole("option", { name: "Delivery" }))

    await userEvent.click(screen.getByRole("button", { name: "Enviar correção" }))

    await waitFor(() => expect(bodies).toHaveLength(1))
    expect(bodies[0]).toMatchObject({
      action: "correct",
      category: "Alimentação",
      subcategory: "Delivery",
    })
  })

  it("navigates to the report once the run completes", async () => {
    server.use(runStatus({ status: "completed", report: reportFixture }))
    const queryClient = createTestQueryClient()
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[ROUTE]}>
          <Routes>
            <Route path="/months/:monthRef/review" element={<ReviewPage />} />
            <Route path="/months/:monthRef/report" element={<p>relatório do mês</p>} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )

    expect(await screen.findByText("relatório do mês")).toBeInTheDocument()
  })

  it("shows the sanitized error message and retries the run", async () => {
    const bodies: RunRequest[] = []
    server.use(
      runStatus({ status: "error", message: "falha ao ler o extrato" }),
      http.post(url("/months/:monthRef/run"), async ({ request }) => {
        bodies.push((await request.json()) as RunRequest)
        return HttpResponse.json({ status: "processing" }, { status: 202 })
      }),
    )
    renderWithProviders(<ReviewPage />, { route: ROUTE })

    expect(await screen.findByText("falha ao ler o extrato")).toBeInTheDocument()

    await userEvent.click(screen.getByRole("button", { name: "Tentar novamente" }))

    await waitFor(() => expect(bodies).toHaveLength(1))
    expect(bodies[0].files).toEqual([])
  })

  it("retries with the files carried over from the upload screen", async () => {
    const uploaded = ["extracts/2026-08/bradesco.csv", "extracts/2026-08/inter.pdf"]
    const bodies: RunRequest[] = []
    server.use(
      runStatus({ status: "error", message: "falha ao ler o extrato" }),
      http.post(url("/months/:monthRef/run"), async ({ request }) => {
        bodies.push((await request.json()) as RunRequest)
        return HttpResponse.json({ status: "processing" }, { status: 202 })
      }),
    )
    renderWithRouterState({ files: uploaded })

    await userEvent.click(await screen.findByRole("button", { name: "Tentar novamente" }))

    await waitFor(() => expect(bodies).toHaveLength(1))
    expect(bodies[0].files).toEqual(uploaded)
  })

  it("does not crash when a pending review carries no item", async () => {
    server.use(runStatus({ status: "pending_review" }))
    renderWithProviders(<ReviewPage />, { route: ROUTE })

    expect(await screen.findByText("Nenhuma revisão pendente")).toBeInTheDocument()
  })

  it("surfaces a failed status request", async () => {
    server.use(
      http.get(url("/months/:monthRef/run"), () =>
        errorResponse(500, "internal_error", "backend indisponível"),
      ),
    )
    renderWithProviders(<ReviewPage />, { route: ROUTE })

    expect(await screen.findByText("Ocorreu um erro")).toBeInTheDocument()
  })
})
