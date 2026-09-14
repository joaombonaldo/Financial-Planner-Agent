/**
 * `/months/:monthRef/report` — the month's dashboard (specs/016-frontend-core
 * "Screens and routes").
 *
 * Everything here is driven by a single `useReport(monthRef)`. The backend
 * recomputes the report on every GET, so a manual edit made on the transactions
 * page shows up as soon as this query refetches — nothing on this page may cache
 * or derive state that assumes the report is static.
 *
 * ## Visual decisions (dataviz skill)
 *
 * - Headline totals are a **KPI row of stat tiles**, not a chart: "a handful of
 *   headline numbers" is a figure job, and a three-bar bar chart of
 *   income/expense/balance would be a chart that says less than the numbers.
 * - The category breakdown is a **horizontal bar chart**, faceted into expenses
 *   and income (two magnitude scales must never share one axis). It is drawn in
 *   plain HTML/CSS rather than with a chart library: one series of ≤ ~10 bars
 *   with long Portuguese labels needs no scales, axes or layout engine, and the
 *   rows double as the required table view (label · breakdown · value).
 *   **One series → one color** (categorical slot 1) — a darker-where-bigger ramp
 *   would double-encode bar length as hue, which the skill calls out explicitly.
 * - Budget is a **meter** per category ("a single ratio against a limit"), the
 *   unfilled track a lighter step of the fill's own ramp, the fill carrying
 *   severity. Status never rides on color alone: every meter ships with a text
 *   badge.
 * - Credit-card purchases and fatura reconciliation stay **tables** — short,
 *   informational, and a second chart would compete with the one that matters.
 *
 * Colors are the skill's validated default palette, declared as local custom
 * properties (light + `.dark`) so this page never touches the app-wide tokens.
 * `node scripts/validate_palette.js "#2a78d6,#d03b3b" --mode light` and the dark
 * pair both pass every check.
 */
import { Link, useParams } from "react-router-dom"

import { useReport } from "@/api/queries"
import type {
  BudgetComparison,
  CategoryTotal,
  CreditCategoryTotal,
  FaturaReconciliation,
  MonthReport,
} from "@/api/types"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

/**
 * Below this, a reconciliation delta is rounding noise rather than a missing or
 * duplicated purchase. Same threshold the CLI uses (`cli.py:_print_report`).
 */
const DELTA_EPSILON = 0.01

/**
 * `R$ 1.380,20` — pt-BR grouping, always two decimals, plain space before the
 * digits (`Intl` currency style emits a non-breaking space, which makes every
 * assertion and every copy-paste subtly wrong).
 */
function formatBRL(value: number): string {
  return `R$ ${value.toLocaleString("pt-BR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

/** `+` for income, `−` for expense — mirrors the CLI's per-category sign. */
function signFor(type: CategoryTotal["type"]): string {
  return type === "income" ? "+" : "−"
}

/**
 * The chart palette, scoped to this page.
 *
 * Slot 1 (blue) is the single series; `critical` is the reserved status color for
 * an over-budget meter and a nonzero fatura delta. The dark steps are the same
 * hues re-stepped for the dark surface, not an automatic flip.
 */
const VIZ_STYLES = `
.fp-viz {
  --viz-series-1: #2a78d6;
  --viz-track: #cde2fb;
  --viz-critical: #d03b3b;
  --viz-critical-track: #f6dcdc;
}
.dark .fp-viz {
  --viz-series-1: #3987e5;
  --viz-track: #184f95;
  --viz-critical: #d03b3b;
  --viz-critical-track: #4a2020;
}
`

interface StatTileProps {
  label: string
  value: number
  /** The one number the dashboard leads with, rendered larger. */
  hero?: boolean
}

/** Label + value. Proportional figures — `tabular-nums` is for columns only. */
function StatTile({ label, value, hero = false }: StatTileProps) {
  return (
    // `data-stat` disambiguates the tile from a category row that happens to
    // carry the same amount (income total vs. the "Renda" category).
    <Card data-stat={label}>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {label}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className={hero ? "text-3xl font-semibold" : "text-2xl font-semibold"}>
          {formatBRL(value)}
        </p>
      </CardContent>
    </Card>
  )
}

interface CategoryBarsProps {
  title: string
  entries: CategoryTotal[]
}

/**
 * One facet of the category breakdown: a single-series horizontal bar chart whose
 * rows are also its table view. Bars are scaled against the largest value *in this
 * facet* — expenses and income never share a scale.
 *
 * A single series carries no legend (the facet heading names what is plotted), and
 * values sit in their own right-aligned column so a short bar can never clip or
 * overflow its own label.
 */
function CategoryBars({ title, entries }: CategoryBarsProps) {
  if (entries.length === 0) return null

  const max = Math.max(...entries.map((entry) => Math.abs(entry.total)), 0)

  return (
    <section className="space-y-3">
      <h3 className="text-sm font-medium text-muted-foreground">{title}</h3>
      <ul className="space-y-3">
        {entries.map((entry) => {
          const width = max > 0 ? (Math.abs(entry.total) / max) * 100 : 0
          return (
            <li key={entry.category} className="space-y-1">
              <div className="flex items-baseline justify-between gap-4 text-sm">
                <span>
                  {signFor(entry.type)} {entry.category}
                </span>
                <span className="font-medium tabular-nums">
                  {formatBRL(entry.total)}
                </span>
              </div>
              {/* Track is the 100% reference, so the chart needs no gridlines. */}
              <div
                className="h-3 w-full overflow-hidden rounded-sm"
                style={{ backgroundColor: "var(--viz-track)" }}
              >
                <div
                  className="h-full rounded-r-[4px]"
                  style={{
                    width: `${width}%`,
                    backgroundColor: "var(--viz-series-1)",
                  }}
                />
              </div>
              {entry.reimbursed > 0 ? (
                <p className="text-xs text-muted-foreground">
                  {`bruto ${formatBRL(entry.gross)} − reembolso ${formatBRL(
                    entry.reimbursed,
                  )} = líquido ${formatBRL(entry.total)}`}
                </p>
              ) : null}
            </li>
          )
        })}
      </ul>
    </section>
  )
}

/**
 * A budget meter: actual spend against its goal. The fill carries severity
 * (series blue within budget, critical red over it) over a lighter step of the
 * same ramp, and the badge repeats the state as text so the color never carries
 * it alone.
 */
function BudgetMeter({ entry }: { entry: BudgetComparison }) {
  const over = entry.status === "over_budget"
  const ratio = entry.goal > 0 ? entry.actual_spend / entry.goal : 0
  const width = Math.min(Math.max(ratio, 0), 1) * 100

  return (
    <li className="space-y-1.5" data-budget-status={entry.status}>
      <div className="flex items-baseline justify-between gap-4 text-sm">
        <span>{entry.category}</span>
        <span className="tabular-nums">
          {formatBRL(entry.actual_spend)} de {formatBRL(entry.goal)}
        </span>
      </div>
      <div
        className="h-3 w-full overflow-hidden rounded-sm"
        style={{
          backgroundColor: over ? "var(--viz-critical-track)" : "var(--viz-track)",
        }}
      >
        <div
          className="h-full rounded-r-[4px]"
          style={{
            width: `${width}%`,
            backgroundColor: over ? "var(--viz-critical)" : "var(--viz-series-1)",
          }}
        />
      </div>
      <div className="flex items-baseline justify-between gap-4">
        <Badge variant={over ? "destructive" : "secondary"}>
          {over ? "Acima do orçamento" : "Dentro do orçamento"}
        </Badge>
        <span className="text-xs text-muted-foreground tabular-nums">
          diferença: {formatBRL(entry.difference)}
        </span>
      </div>
    </li>
  )
}

/** The credit stream — informational only, explicitly outside the totals above. */
function CreditSection({
  monthRef,
  entries,
  total,
}: {
  monthRef: string
  entries: CreditCategoryTotal[]
  total: number
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Compras no cartão de crédito</CardTitle>
        <p className="text-sm text-muted-foreground">
          Compras de {monthRef}, cobradas em uma fatura futura — não entram nas
          receitas, despesas nem no saldo acima.
        </p>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Categoria</TableHead>
              <TableHead className="text-right">Total</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {entries.map((entry) => (
              <TableRow key={entry.category}>
                <TableCell>
                  {signFor(entry.type)} {entry.category}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatBRL(entry.total)}
                </TableCell>
              </TableRow>
            ))}
            <TableRow>
              <TableCell className="font-medium">Total no cartão</TableCell>
              <TableCell className="text-right font-medium tabular-nums">
                {formatBRL(total)}
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}

/**
 * Fatura reconciliation: what was paid vs. what was bought. A delta that isn't
 * rounding noise is the whole point of this section — it means a purchase is
 * missing or duplicated — so it gets the critical status treatment *and* a text
 * label, never color alone.
 */
function FaturaSection({ entries }: { entries: FaturaReconciliation[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Reconciliação da fatura</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Fatura</TableHead>
              <TableHead className="text-right">Pago</TableHead>
              <TableHead className="text-right">Compras</TableHead>
              <TableHead className="text-right">Diferença</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {entries.map((entry) => {
              const mismatch = Math.abs(entry.delta) >= DELTA_EPSILON
              return (
                <TableRow
                  key={entry.fatura_ref}
                  data-delta-state={mismatch ? "mismatch" : "ok"}
                >
                  <TableCell className="font-mono">{entry.fatura_ref}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatBRL(entry.debit_payment)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatBRL(entry.credit_purchases_total)}
                  </TableCell>
                  <TableCell className="text-right">
                    {mismatch ? (
                      <span className="font-medium text-destructive tabular-nums">
                        {formatBRL(entry.delta)} — verificar
                      </span>
                    ) : (
                      <span className="text-muted-foreground tabular-nums">
                        {formatBRL(entry.delta)} — confere
                      </span>
                    )}
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}

/** The whole dashboard, once the report has actually loaded. */
function ReportBody({ report }: { report: MonthReport }) {
  const expenses = report.category_breakdown.filter(
    (entry) => entry.type === "expense",
  )
  const income = report.category_breakdown.filter((entry) => entry.type === "income")
  const hasCredit =
    report.credit_category_breakdown.length > 0 || report.credit_total > 0

  return (
    <div className="fp-viz space-y-6">
      <style>{VIZ_STYLES}</style>

      <div>
        <h1 className="text-xl font-semibold">Relatório de {report.month_ref}</h1>
        <p className="text-sm text-muted-foreground">
          {report.transaction_count} transações
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <StatTile label="Receitas" value={report.total_income} />
        <StatTile label="Despesas" value={report.total_expense} />
        <StatTile label="Saldo" value={report.net_balance} hero />
      </div>

      {report.transfer_total !== 0 ? (
        <p className="text-sm text-muted-foreground">
          Transferências internas (fora do saldo):{" "}
          <span className="tabular-nums">{formatBRL(report.transfer_total)}</span>
        </p>
      ) : null}

      {report.total_reimbursements > 0 ? (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Reembolsos</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-sm">
            <p>
              Reembolsos de despesas compartilhadas (abatidos das despesas):{" "}
              <span className="tabular-nums">
                {formatBRL(report.total_reimbursements)}
              </span>
            </p>
            {report.unattributed_reimbursements > 0 ? (
              <p className="text-muted-foreground">
                não atribuídos a uma categoria:{" "}
                <span className="tabular-nums">
                  {formatBRL(report.unattributed_reimbursements)}
                </span>
              </p>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Por categoria</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {report.category_breakdown.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Nenhuma transação categorizada neste mês.
            </p>
          ) : (
            <>
              <CategoryBars title="Despesas por categoria" entries={expenses} />
              <CategoryBars title="Receitas por categoria" entries={income} />
            </>
          )}
        </CardContent>
      </Card>

      {hasCredit ? (
        <CreditSection
          monthRef={report.month_ref}
          entries={report.credit_category_breakdown}
          total={report.credit_total}
        />
      ) : null}

      {report.fatura_reconciliations.length > 0 ? (
        <FaturaSection entries={report.fatura_reconciliations} />
      ) : null}

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base">Orçamento</CardTitle>
          <Button asChild variant="outline" size="sm">
            <Link to={`/months/${report.month_ref}/budget`}>Editar orçamento</Link>
          </Button>
        </CardHeader>
        <CardContent>
          {report.budget_report.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Nenhuma meta de orçamento configurada.
            </p>
          ) : (
            <ul className="space-y-5">
              {report.budget_report.map((entry) => (
                <BudgetMeter key={entry.category} entry={entry} />
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Resumo do mês</CardTitle>
        </CardHeader>
        <CardContent>
          {report.insights_summary ? (
            // Plain text, always. Free-form output from a local LLM — never
            // `dangerouslySetInnerHTML` (specs/016-frontend-core "Security").
            <p className="text-sm whitespace-pre-line">{report.insights_summary}</p>
          ) : report.insights_error ? (
            // Insights are optional per the BRD: a failure here is a footnote,
            // not a failure of the report.
            <p className="text-sm text-muted-foreground">
              Não foi possível gerar insights: {report.insights_error}
            </p>
          ) : (
            <p className="text-sm text-muted-foreground">
              Nenhum resumo disponível para este mês.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

export default function ReportPage() {
  const { monthRef = "" } = useParams<{ monthRef: string }>()
  const { data: report, isPending, isError, error } = useReport(monthRef)

  if (isPending) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <div className="grid gap-4 sm:grid-cols-3">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (isError) {
    return <p className="text-sm text-destructive">{error.message}</p>
  }

  return <ReportBody report={report} />
}
