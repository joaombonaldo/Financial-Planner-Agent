/**
 * `/budget` — configure the global default budget goals.
 *
 * These are the fallback goals `get_effective_budget` (backend db/repository.py)
 * merges into every month that doesn't override a given category itself — see
 * MonthBudgetPage for per-month overrides. A full `PUT /budget` replaces the
 * whole set, so `BudgetGoalsEditor` always saves the complete edited dict.
 */
import { useDefaultBudget, useTaxonomy } from "@/api/queries"
import { useSetDefaultBudget } from "@/api/mutations"
import BudgetGoalsEditor from "@/components/BudgetGoalsEditor"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

export default function BudgetPage() {
  const { data: goals, isPending, isError, error } = useDefaultBudget()
  const { data: taxonomy } = useTaxonomy()
  const setDefaultBudget = useSetDefaultBudget()

  const categories = Object.keys(taxonomy ?? {})

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-xl font-semibold">Orçamento</h1>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Metas padrão</CardTitle>
        </CardHeader>
        <CardContent>
          {isPending ? (
            <Skeleton className="h-20 w-full" />
          ) : isError ? (
            <p className="text-sm text-destructive">{error.message}</p>
          ) : (
            <BudgetGoalsEditor
              goals={goals}
              categories={categories}
              onSave={(next) => setDefaultBudget.mutate(next)}
              isSaving={setDefaultBudget.isPending}
              saveError={setDefaultBudget.error?.message}
            />
          )}
        </CardContent>
      </Card>

      <p className="text-sm text-muted-foreground">
        Um mês específico pode sobrepor essas metas — veja "Editar orçamento" no
        relatório do mês.
      </p>
    </div>
  )
}
