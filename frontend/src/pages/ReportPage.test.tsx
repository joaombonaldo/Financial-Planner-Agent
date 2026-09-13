/**
 * `ReportPage` — the month dashboard.
 *
 * Every request is intercepted by MSW; nothing here reaches a real backend and
 * therefore never transitively reaches Ollama (specs/016-frontend-core "Testing
 * strategy"). Per-test variants spread over `reportFixture` rather than building
 * a second, drifting shape by hand.
 */
import { screen } from "@testing-library/react"
import { http, HttpResponse } from "msw"
import { describe, expect, it } from "vitest"

import type { MonthReport } from "@/api/types"
import ReportPage from "@/pages/ReportPage"
import { reportFixture } from "@/test/mocks/fixtures"
import { errorResponse, url } from "@/test/mocks/handlers"
import { server } from "@/test/mocks/server"
import { renderWithProviders } from "@/test/utils"

const ROUTE = "/months/2026-08/report"

/** Serve `reportFixture` with these fields replaced. */
function serveReport(overrides: Partial<MonthReport> = {}) {
  server.use(
    http.get(url("/months/:monthRef/report"), () =>
      HttpResponse.json({ ...reportFixture, ...overrides }),
    ),
  )
}

describe("ReportPage", () => {
  it("renders the headline totals", async () => {
    const { container } = renderWithProviders(<ReportPage />, { route: ROUTE })

    expect(await screen.findByText("Receitas")).toBeInTheDocument()

    // Scoped per tile: the income total also appears as the "Renda" category row.
    expect(container.querySelector('[data-stat="Receitas"]')).toHaveTextContent(
      "R$ 9.800,00",
    )
    expect(container.querySelector('[data-stat="Despesas"]')).toHaveTextContent(
      "R$ 6.312,45",
    )
    expect(container.querySelector('[data-stat="Saldo"]')).toHaveTextContent(
      "R$ 3.487,55",
    )

    // Internal transfers are excluded from those totals and must say so.
    expect(
      screen.getByText(/Transferências internas \(fora do saldo\)/),
    ).toBeInTheDocument()
    expect(screen.getByText("R$ 1.200,00")).toBeInTheDocument()
  })

  it("shows gross/reimbursed/net only for a category with reimbursements", async () => {
    renderWithProviders(<ReportPage />, { route: ROUTE })

    // Alimentação: gross 1480.20, reimbursed 100.00, net 1380.20.
    expect(
      await screen.findByText(
        "bruto R$ 1.480,20 − reembolso R$ 100,00 = líquido R$ 1.380,20",
      ),
    ).toBeInTheDocument()

    // Moradia has reimbursed 0 — flat total, no breakdown line of its own.
    expect(screen.getByText("R$ 2.450,00")).toBeInTheDocument()
    expect(screen.queryByText(/bruto R\$ 2\.450,00/)).not.toBeInTheDocument()
  })

  it("omits the credit-card section when there is no credit activity", async () => {
    serveReport({ credit_category_breakdown: [], credit_total: 0 })
    renderWithProviders(<ReportPage />, { route: ROUTE })

    await screen.findByText("Receitas")
    expect(
      screen.queryByText("Compras no cartão de crédito"),
    ).not.toBeInTheDocument()
  })

  it("renders the credit-card section, labelled as outside the totals", async () => {
    renderWithProviders(<ReportPage />, { route: ROUTE })

    expect(
      await screen.findByText("Compras no cartão de crédito"),
    ).toBeInTheDocument()
    expect(screen.getByText(/cobradas em uma fatura futura/)).toBeInTheDocument()
    expect(screen.getByText("R$ 250,75")).toBeInTheDocument()
    expect(screen.getByText("R$ 89,90")).toBeInTheDocument()
    expect(screen.getByText("Total no cartão")).toBeInTheDocument()
    expect(screen.getByText("R$ 340,65")).toBeInTheDocument()
  })

  it("flags a fatura reconciliation whose delta is not near zero", async () => {
    serveReport({
      fatura_reconciliations: [
        {
          fatura_ref: "2026-08",
          debit_payment: 1840.32,
          credit_purchases_total: 1840.32,
          delta: 0.0,
        },
        {
          fatura_ref: "2026-07",
          debit_payment: 1500.0,
          credit_purchases_total: 1412.5,
          delta: 87.5,
        },
      ],
    })
    const { container } = renderWithProviders(<ReportPage />, { route: ROUTE })

    expect(await screen.findByText("Reconciliação da fatura")).toBeInTheDocument()

    const ok = container.querySelectorAll('[data-delta-state="ok"]')
    const mismatch = container.querySelectorAll('[data-delta-state="mismatch"]')
    expect(ok).toHaveLength(1)
    expect(mismatch).toHaveLength(1)
    expect(mismatch[0]).toHaveTextContent("2026-07")
    expect(mismatch[0]).toHaveTextContent("R$ 87,50 — verificar")
    expect(ok[0]).toHaveTextContent("R$ 0,00 — confere")
  })

  it("renders an empty budget as a note, without fabricating rows", async () => {
    serveReport({ budget_report: [] })
    const { container } = renderWithProviders(<ReportPage />, { route: ROUTE })

    expect(await screen.findByText("Orçamento")).toBeInTheDocument()
    expect(
      screen.getByText("Nenhuma meta de orçamento configurada."),
    ).toBeInTheDocument()
    expect(screen.queryByText("Dentro do orçamento")).not.toBeInTheDocument()
    expect(screen.queryByText("Acima do orçamento")).not.toBeInTheDocument()
    expect(container.querySelectorAll("[data-budget-status]")).toHaveLength(0)
  })

  it("distinguishes over-budget from within-budget categories", async () => {
    const { container } = renderWithProviders(<ReportPage />, { route: ROUTE })

    expect(await screen.findByText("Acima do orçamento")).toBeInTheDocument()
    expect(screen.getByText("Dentro do orçamento")).toBeInTheDocument()

    const over = container.querySelector('[data-budget-status="over_budget"]')
    expect(over).toHaveTextContent("Alimentação")
    expect(over).toHaveTextContent("R$ 1.380,20 de R$ 1.200,00")
  })

  it("renders the insights summary as plain text, never as HTML", async () => {
    const hostile = "<script>alert('xss')</script> Gastos sob controle."
    serveReport({ insights_summary: hostile })
    const { container } = renderWithProviders(<ReportPage />, { route: ROUTE })

    // Present as a text node, verbatim — including the tag, which must read as
    // literal characters rather than have been parsed into an element.
    expect(await screen.findByText(hostile)).toBeInTheDocument()
    expect(container.querySelector("script")).toBeNull()
  })

  it("falls back to a note when insights failed, without erroring the page", async () => {
    serveReport({
      insights_summary: null,
      insights_error: "ollama indisponível",
    })
    renderWithProviders(<ReportPage />, { route: ROUTE })

    expect(
      await screen.findByText("Não foi possível gerar insights: ollama indisponível"),
    ).toBeInTheDocument()
    // The rest of the report still rendered — insights are optional.
    expect(screen.getByText("R$ 3.487,55")).toBeInTheDocument()
    expect(screen.getByText("Por categoria")).toBeInTheDocument()
  })

  it("renders the page-level error state when the report request fails", async () => {
    server.use(
      http.get(url("/months/:monthRef/report"), () =>
        errorResponse(500, "internal_error", "Falha ao gerar o relatório."),
      ),
    )
    renderWithProviders(<ReportPage />, { route: ROUTE })

    expect(
      await screen.findByText("Falha ao gerar o relatório."),
    ).toBeInTheDocument()
    expect(screen.queryByText("Por categoria")).not.toBeInTheDocument()
  })
})
