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
        <nav className="mx-auto flex max-w-6xl items-center gap-6 px-6 py-4 text-sm">
          <Link to="/months" className="text-base font-semibold tracking-tight">
            Planejador Financeiro
          </Link>

          <NavLink to="/months" end className={navClass}>
            Meses
          </NavLink>
          <NavLink to="/budget" className={navClass}>
            Orçamento
          </NavLink>

          {monthRef ? (
            <>
              <span className="text-muted-foreground">/</span>
              <span className="font-mono text-muted-foreground">{monthRef}</span>
              <NavLink to={`/months/${monthRef}/report`} className={navClass}>
                Relatório
              </NavLink>
              <NavLink to={`/months/${monthRef}/transactions`} className={navClass}>
                Transações
              </NavLink>
              <NavLink to={`/months/${monthRef}/budget`} className={navClass}>
                Orçamento do mês
              </NavLink>
            </>
          ) : null}

          <div className="ml-auto">
            <NewMonthDialog />
          </div>
        </nav>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-8">
        <Outlet />
      </main>
    </div>
  )
}
