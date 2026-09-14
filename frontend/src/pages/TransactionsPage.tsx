/**
 * `/months/:monthRef/transactions` — browse a month's transactions and edit
 * them one at a time (specs/016-frontend-core "Screens and routes").
 *
 * Deliberately **not** a batch operation: the BRD calls for review here to be
 * one-transaction-at-a-time via `PATCH`, matching the review flow's own
 * one-item-at-a-time design. Every edit is its own request via
 * `usePatchTransaction()`, which already invalidates this month's
 * `transactions`/`report` caches on success — this page never refetches
 * manually.
 */
import { PencilIcon, PlusIcon, RotateCcwIcon, Trash2Icon } from "lucide-react"
import { useMemo, useState } from "react"
import { useParams } from "react-router-dom"

import type { TransactionFilters } from "@/api/queries"
import { useTaxonomy, useTransactions } from "@/api/queries"
import { useCreateTransaction, usePatchTransaction } from "@/api/mutations"
import type { Instrument, Transaction, TransactionType } from "@/api/types"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

const INSTRUMENT_LABEL: Record<Instrument, string> = {
  debit: "Débito",
  credit: "Cartão de crédito",
}

const ALL_INSTRUMENTS = "all"

function formatAmount(amount: number): string {
  return amount.toLocaleString("pt-BR", { style: "currency", currency: "BRL" })
}

/** The recategorize dialog: category select -> dependent subcategory select. */
function RecategorizeDialog({
  transaction,
  onClose,
}: {
  transaction: Transaction
  onClose: () => void
}) {
  const { data: taxonomy, isPending, isError, error } = useTaxonomy()
  const [category, setCategory] = useState(transaction.category ?? "")
  const [subcategory, setSubcategory] = useState(transaction.subcategory ?? "")
  const patch = usePatchTransaction()

  const subcategories = useMemo(
    () => (category ? (taxonomy?.[category] ?? []) : []),
    [taxonomy, category],
  )

  function handleCategoryChange(value: string) {
    setCategory(value)
    setSubcategory("")
  }

  function handleSubmit() {
    if (!category) return
    patch.mutate(
      { dedupHash: transaction.dedup_hash, category, subcategory: subcategory || undefined },
      { onSuccess: onClose },
    )
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Editar categoria</DialogTitle>
        </DialogHeader>

        {isPending ? (
          <Skeleton className="h-20 w-full" />
        ) : isError ? (
          <p className="text-sm text-destructive">{error.message}</p>
        ) : (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="recat-category">Categoria</Label>
              <Select value={category} onValueChange={handleCategoryChange}>
                <SelectTrigger id="recat-category" className="w-full">
                  <SelectValue placeholder="Selecione uma categoria" />
                </SelectTrigger>
                <SelectContent>
                  {Object.keys(taxonomy ?? {}).map((cat) => (
                    <SelectItem key={cat} value={cat}>
                      {cat}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="recat-subcategory">Subcategoria</Label>
              <Select
                value={subcategory}
                onValueChange={setSubcategory}
                disabled={subcategories.length === 0}
              >
                <SelectTrigger id="recat-subcategory" className="w-full">
                  <SelectValue placeholder="Selecione uma subcategoria" />
                </SelectTrigger>
                <SelectContent>
                  {subcategories.map((sub) => (
                    <SelectItem key={sub} value={sub}>
                      {sub}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {patch.isError ? (
              <p className="text-sm text-destructive">{patch.error.message}</p>
            ) : null}
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancelar
          </Button>
          <Button onClick={handleSubmit} disabled={!category || patch.isPending}>
            Salvar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function TransactionRow({ transaction }: { transaction: Transaction }) {
  const [editing, setEditing] = useState(false)
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const patch = usePatchTransaction()
  const isDeleted = transaction.deleted_at !== null

  // Deleting is destructive-looking (even though it's a recoverable soft
  // delete) and needs a confirmation; restoring undoes it, so it doesn't.
  function handleDeleteClick() {
    if (isDeleted) {
      patch.mutate({ dedupHash: transaction.dedup_hash, deleted: false })
    } else {
      setConfirmingDelete(true)
    }
  }

  function handleConfirmDelete() {
    patch.mutate(
      { dedupHash: transaction.dedup_hash, deleted: true },
      { onSuccess: () => setConfirmingDelete(false) },
    )
  }

  return (
    <>
      <TableRow className={isDeleted ? "text-muted-foreground line-through" : undefined}>
        <TableCell className="whitespace-nowrap font-mono">{transaction.date}</TableCell>
        <TableCell
          className="max-w-[220px] truncate"
          title={transaction.description_raw}
        >
          {transaction.description_raw}
        </TableCell>
        <TableCell className="font-mono">{transaction.account}</TableCell>
        <TableCell className="text-right font-mono whitespace-nowrap">
          {formatAmount(transaction.amount)}
        </TableCell>
        <TableCell
          className="max-w-[180px] truncate"
          title={
            transaction.subcategory
              ? `${transaction.category ?? "—"} / ${transaction.subcategory}`
              : (transaction.category ?? "—")
          }
        >
          {transaction.category ?? "—"}
          {transaction.subcategory ? ` / ${transaction.subcategory}` : ""}
        </TableCell>
        <TableCell className="whitespace-nowrap">{transaction.confidence ?? "—"}</TableCell>
        <TableCell className="whitespace-nowrap">
          <Badge variant={transaction.instrument === "credit" ? "secondary" : "outline"}>
            {INSTRUMENT_LABEL[transaction.instrument]}
          </Badge>
        </TableCell>
        {/* Sticky so the actions never require a sideways scroll to reach, even
            when the columns above don't all fit a narrow viewport. */}
        <TableCell className="sticky right-0 z-10 bg-background text-right whitespace-nowrap shadow-[-8px_0_8px_-8px_rgba(0,0,0,0.15)]">
          <div className="flex justify-end gap-1">
            <Button
              size="icon"
              variant="outline"
              onClick={() => setEditing(true)}
              title="Editar categoria"
              aria-label="Editar categoria"
            >
              <PencilIcon />
            </Button>
            <Button
              size="icon"
              variant={isDeleted ? "outline" : "destructive"}
              onClick={handleDeleteClick}
              disabled={patch.isPending}
              title={isDeleted ? "Restaurar" : "Excluir"}
              aria-label={isDeleted ? "Restaurar" : "Excluir"}
            >
              {isDeleted ? <RotateCcwIcon /> : <Trash2Icon />}
            </Button>
          </div>
        </TableCell>
      </TableRow>
      {editing ? (
        <RecategorizeDialog transaction={transaction} onClose={() => setEditing(false)} />
      ) : null}
      <AlertDialog open={confirmingDelete} onOpenChange={setConfirmingDelete}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Excluir esta transação?</AlertDialogTitle>
            <AlertDialogDescription>
              "{transaction.description_raw}" ({formatAmount(transaction.amount)}) deixará de
              contar em relatórios e totais. Isso pode ser desfeito depois com "Restaurar".
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={patch.isPending}>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmDelete}
              disabled={patch.isPending}
              className="bg-destructive text-white hover:bg-destructive/90"
            >
              Excluir
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}

// The strict pair, not the app's widened `Bank` display type -- a new
// transaction is always one of the two known accounts (see mutations.ts).
type AccountValue = "bradesco" | "inter"

const ACCOUNT_LABEL: Record<AccountValue, string> = { bradesco: "Bradesco", inter: "Inter" }
const TYPE_LABEL: Record<TransactionType, string> = { expense: "Despesa", income: "Receita" }

/**
 * "Adicionar transação" — something the bank statement never had (cash
 * spending, an adjustment). Its date decides which month it lands in
 * server-side; `monthRef` here is only used to prefill a sensible default date
 * so adding from August's page defaults to a day in August.
 */
function AddTransactionDialog({ monthRef }: { monthRef: string }) {
  const [open, setOpen] = useState(false)
  const [date, setDate] = useState(`${monthRef}-01`)
  const [description, setDescription] = useState("")
  const [account, setAccount] = useState<AccountValue>("bradesco")
  const [type, setType] = useState<TransactionType>("expense")
  const [amount, setAmount] = useState("")
  const [category, setCategory] = useState("")
  const [subcategory, setSubcategory] = useState("")
  const [instrument, setInstrument] = useState<Instrument>("debit")

  const { data: taxonomy } = useTaxonomy()
  const create = useCreateTransaction()

  const subcategories = category ? (taxonomy?.[category] ?? []) : []
  const amountValue = Number(amount)
  const isValid =
    date.length > 0 &&
    description.trim().length > 0 &&
    Number.isFinite(amountValue) &&
    amountValue > 0 &&
    category.length > 0

  function reset() {
    setDate(`${monthRef}-01`)
    setDescription("")
    setAccount("bradesco")
    setType("expense")
    setAmount("")
    setCategory("")
    setSubcategory("")
    setInstrument("debit")
  }

  function handleSubmit() {
    if (!isValid) return
    create.mutate(
      {
        date,
        descriptionRaw: description.trim(),
        account,
        type,
        amount: amountValue,
        category,
        subcategory: subcategory || undefined,
        instrument,
      },
      {
        onSuccess: () => {
          setOpen(false)
          reset()
        },
      },
    )
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (!next) reset()
      }}
    >
      <DialogTrigger asChild>
        <Button size="sm">
          <PlusIcon /> Adicionar transação
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Adicionar transação</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="add-date">Data</Label>
              <Input
                id="add-date"
                type="date"
                value={date}
                onChange={(event) => setDate(event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="add-amount">Valor</Label>
              <Input
                id="add-amount"
                type="number"
                min="0.01"
                step="0.01"
                placeholder="0,00"
                value={amount}
                onChange={(event) => setAmount(event.target.value)}
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="add-description">Descrição</Label>
            <Input
              id="add-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Ex.: Feira livre"
            />
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label htmlFor="add-account">Conta</Label>
              <Select value={account} onValueChange={(value) => setAccount(value as AccountValue)}>
                <SelectTrigger id="add-account" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(ACCOUNT_LABEL).map(([value, label]) => (
                    <SelectItem key={value} value={value}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="add-type">Tipo</Label>
              <Select
                value={type}
                onValueChange={(value) => setType(value as TransactionType)}
              >
                <SelectTrigger id="add-type" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(TYPE_LABEL).map(([value, label]) => (
                    <SelectItem key={value} value={value}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="add-instrument">Instrumento</Label>
              <Select
                value={instrument}
                onValueChange={(value) => setInstrument(value as Instrument)}
              >
                <SelectTrigger id="add-instrument" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="debit">Débito</SelectItem>
                  <SelectItem value="credit">Cartão de crédito</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="add-category">Categoria</Label>
              <Select
                value={category}
                onValueChange={(value) => {
                  setCategory(value)
                  setSubcategory("")
                }}
              >
                <SelectTrigger id="add-category" className="w-full">
                  <SelectValue placeholder="Selecione uma categoria" />
                </SelectTrigger>
                <SelectContent>
                  {Object.keys(taxonomy ?? {}).map((name) => (
                    <SelectItem key={name} value={name}>
                      {name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="add-subcategory">Subcategoria</Label>
              <Select
                value={subcategory}
                onValueChange={setSubcategory}
                disabled={subcategories.length === 0}
              >
                <SelectTrigger id="add-subcategory" className="w-full">
                  <SelectValue placeholder="Selecione uma subcategoria" />
                </SelectTrigger>
                <SelectContent>
                  {subcategories.map((name) => (
                    <SelectItem key={name} value={name}>
                      {name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {create.isError ? (
            <p className="text-sm text-destructive">{create.error.message}</p>
          ) : null}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            Cancelar
          </Button>
          <Button onClick={handleSubmit} disabled={!isValid || create.isPending}>
            Adicionar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default function TransactionsPage() {
  const { monthRef } = useParams<{ monthRef: string }>()
  const [instrument, setInstrument] = useState<string>(ALL_INSTRUMENTS)
  const [category, setCategory] = useState<string>("")
  const [includeDeleted, setIncludeDeleted] = useState(false)

  const { data: taxonomy } = useTaxonomy()

  const filters: TransactionFilters = {
    instrument: instrument === ALL_INSTRUMENTS ? undefined : instrument,
    category: category || undefined,
    includeDeleted,
  }

  const {
    data: transactions,
    isPending,
    isError,
    error,
  } = useTransactions(monthRef ?? "", filters)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Transações</h1>
        <AddTransactionDialog monthRef={monthRef ?? ""} />
      </div>

      <div className="flex flex-wrap items-end gap-4">
        <div className="space-y-2">
          <Label htmlFor="filter-instrument">Instrumento</Label>
          <Select value={instrument} onValueChange={setInstrument}>
            <SelectTrigger id="filter-instrument" className="w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL_INSTRUMENTS}>Todos</SelectItem>
              <SelectItem value="debit">Débito</SelectItem>
              <SelectItem value="credit">Cartão de crédito</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label htmlFor="filter-category">Categoria</Label>
          <Select
            value={category || "__all__"}
            onValueChange={(value) => setCategory(value === "__all__" ? "" : value)}
          >
            <SelectTrigger id="filter-category" className="w-48">
              <SelectValue placeholder="Todas" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">Todas</SelectItem>
              {Object.keys(taxonomy ?? {}).map((cat) => (
                <SelectItem key={cat} value={cat}>
                  {cat}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <label className="flex items-center gap-2 pb-2 text-sm" htmlFor="filter-include-deleted">
          <Checkbox
            id="filter-include-deleted"
            checked={includeDeleted}
            onCheckedChange={(checked) => setIncludeDeleted(checked === true)}
          />
          Incluir excluídas
        </label>
      </div>

      {isPending ? (
        <div className="space-y-2">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : isError ? (
        <p className="text-sm text-destructive">{error.message}</p>
      ) : transactions.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Nenhuma transação encontrada para os filtros selecionados.
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Data</TableHead>
              <TableHead>Descrição</TableHead>
              <TableHead>Conta</TableHead>
              <TableHead className="text-right">Valor</TableHead>
              <TableHead>Categoria</TableHead>
              <TableHead>Confiança</TableHead>
              <TableHead>Instrumento</TableHead>
              <TableHead className="sticky right-0 z-10 bg-background text-right shadow-[-8px_0_8px_-8px_rgba(0,0,0,0.15)]">
                Ações
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {transactions.map((transaction) => (
              <TransactionRow key={transaction.dedup_hash} transaction={transaction} />
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  )
}
