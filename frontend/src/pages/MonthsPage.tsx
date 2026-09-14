/**
 * `/months` — month-history landing page (specs/016-frontend-core "Screens
 * and routes"). Lists every processed month. The "Novo mês" affordance lives in
 * the shared nav (`components/NewMonthDialog.tsx`, used from `Layout.tsx`) since
 * it needs to be reachable from every screen, not just this one.
 */
import { Link } from "react-router-dom"

import { useMonths } from "@/api/queries"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

export default function MonthsPage() {
  const { data: months, isPending, isError, error } = useMonths()

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Meses processados</h1>

      {isPending ? (
        <div className="space-y-2">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : isError ? (
        <p className="text-sm text-destructive">{error.message}</p>
      ) : months.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Nenhum mês processado ainda.
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Mês</TableHead>
              <TableHead>Transações</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Ações</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {months.map((month) => (
              <TableRow key={month.month_ref}>
                <TableCell className="font-mono">{month.month_ref}</TableCell>
                <TableCell>{month.transaction_count}</TableCell>
                <TableCell>
                  {month.has_pending_review ? (
                    <Badge variant="destructive">Revisão pendente</Badge>
                  ) : (
                    <Badge variant="secondary">Em dia</Badge>
                  )}
                </TableCell>
                <TableCell className="flex justify-end gap-4 text-sm">
                  {month.has_pending_review ? (
                    <Link
                      to={`/months/${month.month_ref}/review`}
                      className="text-primary underline-offset-4 hover:underline"
                    >
                      Revisar
                    </Link>
                  ) : (
                    <Link
                      to={`/months/${month.month_ref}/report`}
                      className="text-primary underline-offset-4 hover:underline"
                    >
                      Ver relatório
                    </Link>
                  )}
                  <Link
                    to={`/months/${month.month_ref}/transactions`}
                    className="text-primary underline-offset-4 hover:underline"
                  >
                    Ver transações
                  </Link>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  )
}
