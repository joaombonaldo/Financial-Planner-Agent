/**
 * `/months` — month-history landing page (specs/016-frontend-core "Screens
 * and routes"). Lists every processed month and offers a "Novo mês" affordance
 * that kicks off `/months/:monthRef/upload` for a fresh one.
 */
import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"

import { useMonths } from "@/api/queries"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

/** Same format the backend enforces for a `monthRef` path param (`YYYY-MM`). */
const MONTH_REF_PATTERN = /^\d{4}-(0[1-9]|1[0-2])$/

/** The "Novo mês" form: a month-ref input, validated client-side before it can submit. */
function NewMonthDialog() {
  const [open, setOpen] = useState(false)
  const [monthRef, setMonthRef] = useState("")
  const navigate = useNavigate()

  const isValid = MONTH_REF_PATTERN.test(monthRef)

  function handleSubmit() {
    if (!isValid) return
    setOpen(false)
    navigate(`/months/${monthRef}/upload`)
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm">Novo mês</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Novo mês</DialogTitle>
        </DialogHeader>
        <div className="space-y-2">
          <Label htmlFor="month-ref">Mês (AAAA-MM)</Label>
          <Input
            id="month-ref"
            placeholder="2026-09"
            value={monthRef}
            onChange={(event) => setMonthRef(event.target.value)}
          />
          {monthRef && !isValid ? (
            <p className="text-sm text-destructive">
              Formato inválido. Use AAAA-MM, por exemplo 2026-09.
            </p>
          ) : null}
        </div>
        <DialogFooter>
          <Button onClick={handleSubmit} disabled={!isValid}>
            Continuar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default function MonthsPage() {
  const { data: months, isPending, isError, error } = useMonths()

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Meses processados</h1>
        <NewMonthDialog />
      </div>

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
