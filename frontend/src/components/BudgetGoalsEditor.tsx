/**
 * Shared row-based editor for one budget scope's goals (category -> amount),
 * used by BudgetPage (the global default) and MonthBudgetPage (one month's
 * overrides). A full `PUT` replaces the whole scope, so this always saves the
 * complete edited set, never a diff.
 */
import { PlusIcon, Trash2Icon } from "lucide-react"
import { useEffect, useState } from "react"

import type { BudgetGoals } from "@/api/types"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

interface GoalRow {
  id: number
  category: string
  amount: string
}

function goalsToRows(goals: BudgetGoals): GoalRow[] {
  return Object.entries(goals).map(([category, amount], index) => ({
    id: index,
    category,
    amount: String(amount),
  }))
}

export interface BudgetGoalsEditorProps {
  /** The scope's current goals — reinitializes the editor whenever it changes
   * (e.g. after `useSetDefaultBudget`/`useSetMonthBudget` resolves). */
  goals: BudgetGoals
  categories: string[]
  onSave: (goals: BudgetGoals) => void
  isSaving: boolean
  saveError?: string
}

export default function BudgetGoalsEditor({
  goals,
  categories,
  onSave,
  isSaving,
  saveError,
}: BudgetGoalsEditorProps) {
  const [rows, setRows] = useState<GoalRow[]>(() => goalsToRows(goals))
  const [nextId, setNextId] = useState(() => goalsToRows(goals).length)

  useEffect(() => {
    setRows(goalsToRows(goals))
    setNextId(goalsToRows(goals).length)
  }, [goals])

  const usedCategories = new Set(rows.map((row) => row.category))
  const availableCategories = categories.filter((category) => !usedCategories.has(category))

  const isValid = rows.every((row) => {
    const value = Number(row.amount)
    return row.category.length > 0 && Number.isFinite(value) && value >= 0
  })

  function addRow() {
    const category = availableCategories[0]
    if (!category) return
    setRows((current) => [...current, { id: nextId, category, amount: "0" }])
    setNextId((id) => id + 1)
  }

  function removeRow(id: number) {
    setRows((current) => current.filter((row) => row.id !== id))
  }

  function updateRow(id: number, patch: Partial<Pick<GoalRow, "category" | "amount">>) {
    setRows((current) => current.map((row) => (row.id === id ? { ...row, ...patch } : row)))
  }

  function handleSave() {
    if (!isValid) return
    const nextGoals: BudgetGoals = {}
    for (const row of rows) nextGoals[row.category] = Number(row.amount)
    onSave(nextGoals)
  }

  return (
    <div className="space-y-4">
      {rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nenhuma meta configurada.</p>
      ) : (
        <div className="space-y-3">
          {rows.map((row) => (
            <div key={row.id} className="flex items-end gap-3">
              <div className="flex-1 space-y-2">
                <Label htmlFor={`goal-category-${row.id}`}>Categoria</Label>
                <Select
                  value={row.category}
                  onValueChange={(value) => updateRow(row.id, { category: value })}
                >
                  <SelectTrigger id={`goal-category-${row.id}`} className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={row.category}>{row.category}</SelectItem>
                    {availableCategories.map((category) => (
                      <SelectItem key={category} value={category}>
                        {category}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="w-36 space-y-2">
                <Label htmlFor={`goal-amount-${row.id}`}>Meta mensal</Label>
                <Input
                  id={`goal-amount-${row.id}`}
                  type="number"
                  min="0"
                  step="0.01"
                  value={row.amount}
                  onChange={(event) => updateRow(row.id, { amount: event.target.value })}
                />
              </div>
              <Button
                size="icon"
                variant="outline"
                onClick={() => removeRow(row.id)}
                aria-label="Remover meta"
                title="Remover meta"
              >
                <Trash2Icon />
              </Button>
            </div>
          ))}
        </div>
      )}

      <Button
        variant="outline"
        size="sm"
        onClick={addRow}
        disabled={availableCategories.length === 0}
      >
        <PlusIcon /> Adicionar categoria
      </Button>

      {saveError ? <p className="text-sm text-destructive">{saveError}</p> : null}

      <div>
        <Button onClick={handleSave} disabled={!isValid || isSaving}>
          Salvar
        </Button>
      </div>
    </div>
  )
}
