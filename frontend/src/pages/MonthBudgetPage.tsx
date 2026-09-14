/**
 * `/months/:monthRef/budget` — edit this month's own budget overrides.
 *
 * A category left out here falls back to the global default (`/budget`,
 * BudgetPage) — `get_effective_budget` merges the two server-side. The
 * "effective" table below shows that merged result so it's clear which goal
 * actually applies, even for categories this month never overrode.
 */
import { useParams } from "react-router-dom"

import { useMonthBudget, useTaxonomy } from "@/api/queries"
import { useSetMonthBudget } from "@/api/mutations"
import BudgetGoalsEditor from "@/components/BudgetGoalsEditor"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

function formatAmount(amount: number): string {
  return amount.toLocaleString("pt-BR", { style: "currency", currency: "BRL" })
}

export default function MonthBudgetPage() {
  const { monthRef } = useParams<{ monthRef: string }>()
  const { data, isPending, isError, error } = useMonthBudget(monthRef ?? "")
  const { data: taxonomy } = useTaxonomy()
  const setMonthBudget = useSetMonthBudget()

  const categories = Object.keys(taxonomy ?? {})

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-xl font-semibold">Orçamento de {monthRef}</h1>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Metas específicas deste mês</CardTitle>
        </CardHeader>
        <CardContent>
          {isPending ? (
            <Skeleton className="h-20 w-full" />
          ) : isError ? (
            <p className="text-sm text-destructive">{error.message}</p>
          ) : (
            <BudgetGoalsEditor
              goals={data.overrides}
              categories={categories}
              onSave={(goals) => setMonthBudget.mutate({ monthRef: monthRef ?? "", goals })}
              isSaving={setMonthBudget.isPending}
              saveError={setMonthBudget.error?.message}
            />
          )}
        </CardContent>
      </Card>

      {!isPending && !isError && Object.keys(data.effective).length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Metas efetivas neste mês</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Categoria</TableHead>
                  <TableHead className="text-right">Meta</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {Object.entries(data.effective).map(([category, amount]) => (
                  <TableRow key={category}>
                    <TableCell>{category}</TableCell>
                    <TableCell className="text-right font-mono">
                      {formatAmount(amount)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      ) : null}
    </div>
  )
}
