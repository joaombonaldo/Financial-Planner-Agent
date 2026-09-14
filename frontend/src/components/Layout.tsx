/**
 * The app shell: top nav + the routed page.
 *
 * UI chrome is Portuguese (specs/016-frontend-core "UI chrome in Portuguese",
 * matching the CLI's rule) even though the API itself speaks English/technical.
 *
 * No "Revisão" tab here on purpose: review is a transient step in the upload ->
 * process flow, not a standing page you come back to (see ReviewPage.tsx's own
 * docstring). It's reached only via UploadPage's automatic handoff, or from
 * MonthsPage's row link when a month actually has something pending. Once a
 * month is processed, Transações is where any further change happens.
 */
import { Link, NavLink, Outlet, useParams } from "react-router-dom"

import NewMonthDialog from "@/components/NewMonthDialog"

function navClass({ isActive }: { isActive: boolean }): string {
  return isActive
    ? "text-foreground font-medium"
    : "text-muted-foreground hover:text-foreground"
}

export default function Layout() {
  const { monthRef } = useParams<{ monthRef: string }>()

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b">
        <div className="mx-auto flex max-w-6xl items-center gap-6 px-6 py-4 text-sm">
          <Link to="/months" className="text-base font-semibold tracking-tight">
            Planejador Financeiro
          </Link>

          <nav className="flex items-center gap-6">
            <NavLink to="/months" end className={navClass}>
              Meses
            </NavLink>
            <NavLink to="/budget" className={navClass}>
              Orçamento
            </NavLink>
          </nav>

          <div className="ml-auto">
            <NewMonthDialog />
          </div>
        </div>

        {/* A second bar, separate from the global nav above, so a month's own
            tabs don't have to compete for space with "Meses"/"Orçamento" in one
            crowded row. Only rendered once a month is actually selected. */}
        {monthRef ? (
          <div className="border-t bg-muted/40">
            <div className="mx-auto flex max-w-6xl items-center gap-6 px-6 py-3 text-sm">
              <span className="font-mono font-medium">{monthRef}</span>
              <nav className="flex items-center gap-6">
                <NavLink to={`/months/${monthRef}/report`} className={navClass}>
                  Relatório
                </NavLink>
                <NavLink to={`/months/${monthRef}/transactions`} className={navClass}>
                  Transações
                </NavLink>
                <NavLink to={`/months/${monthRef}/budget`} className={navClass}>
                  Orçamento do mês
                </NavLink>
              </nav>
            </div>
          </div>
        ) : null}
      </header>

      <main className="mx-auto max-w-6xl px-6 py-8">
        <Outlet />
      </main>
    </div>
  )
}
