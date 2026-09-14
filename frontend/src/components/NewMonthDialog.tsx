/**
 * The "Novo mês" form: a month-ref input, validated client-side, that kicks off
 * `/months/:monthRef/upload` for a fresh month.
 *
 * Lives in the shared nav (`Layout.tsx`) so it's reachable from every screen, not
 * just `/months` — starting September while looking at August's report shouldn't
 * require navigating back to the month list first. (Previously duplicated: an
 * earlier, unvalidated version lived directly in `Layout.tsx` as a link that
 * guessed the current calendar month, built independently of this one — this is
 * the single surviving "new month" entry point.)
 */
import { useState } from "react"
import { useNavigate } from "react-router-dom"

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

/** Same format the backend enforces for a `monthRef` path param (`YYYY-MM`). */
const MONTH_REF_PATTERN = /^\d{4}-(0[1-9]|1[0-2])$/

export default function NewMonthDialog() {
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
