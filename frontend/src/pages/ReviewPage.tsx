/**
 * Review screen: `/months/:monthRef/review`.
 *
 * The whole page is a render of `GET .../run`'s `status` — the client state
 * machine in specs/016-frontend-core "The review flow — client state machine".
 * `useRunStatus` owns the polling itself (1s while "processing", stopped
 * otherwise), so there is deliberately no local copy of the run's state here:
 *
 *   not_started    -> "envie os extratos primeiro" + link back to /upload
 *   processing     -> spinner
 *   pending_review -> the item card + accept / confirm-transfer / correct
 *   completed      -> navigate to /report
 *   error          -> sanitized message + retry (re-POST .../run)
 *
 * `useAnswerReview` primes `["run", monthRef]` with the `202` body itself, so an
 * answer flips this back to "processing" and the poller resumes without any
 * manual refetch here.
 */
import { type ReactNode, useEffect, useState } from "react"
import { Link, useLocation, useNavigate, useParams } from "react-router-dom"

import { useAnswerReview, useStartRun } from "@/api/mutations"
import { useRunStatus, useTaxonomy } from "@/api/queries"
import type { ReviewItem, Taxonomy } from "@/api/types"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

/** Router state handed over by `UploadPage`: the saved server-side paths. */
interface ReviewLocationState {
  files?: string[]
}

const currency = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
})

export default function ReviewPage() {
  const { monthRef = "" } = useParams<{ monthRef: string }>()
  const location = useLocation()
  const navigate = useNavigate()

  // Carried through the navigation from /upload so a failed run can be retried
  // without re-uploading. Empty when this screen was opened directly — a run
  // with no files is still valid, it just ingests nothing new.
  const files = (location.state as ReviewLocationState | null)?.files ?? []

  const runStatus = useRunStatus(monthRef)
  const startRun = useStartRun()
  const status = runStatus.data?.status

  // "completed" is terminal: the report is the next screen, no extra click.
  useEffect(() => {
    if (status === "completed") {
      navigate(`/months/${monthRef}/report`, { replace: true })
    }
  }, [status, monthRef, navigate])

  if (runStatus.isLoading) {
    return <StatusCard title="Revisão">Carregando...</StatusCard>
  }

  if (runStatus.isError) {
    return (
      <StatusCard title="Ocorreu um erro">
        <p className="text-sm text-muted-foreground">{runStatus.error.message}</p>
      </StatusCard>
    )
  }

  const run = runStatus.data
  if (!run) return null

  switch (run.status) {
    case "not_started":
      return (
        <StatusCard title="Envie os extratos primeiro">
          <p className="text-sm text-muted-foreground">
            Nenhum processamento foi iniciado para {monthRef}.
          </p>
          <Link className="text-sm underline" to={`/months/${monthRef}/upload`}>
            Ir para o envio de extratos
          </Link>
        </StatusCard>
      )

    case "processing":
      return (
        <StatusCard title="Revisão pendente">
          <div className="flex items-center gap-3">
            <span
              aria-hidden="true"
              className="size-4 animate-spin rounded-full border-2 border-muted-foreground border-t-transparent"
            />
            <p role="status" className="text-sm text-muted-foreground">
              Processando...
            </p>
          </div>
        </StatusCard>
      )

    case "completed":
      return <StatusCard title="Concluído">Redirecionando para o relatório...</StatusCard>

    case "error":
      return (
        <StatusCard title="Ocorreu um erro">
          <p className="text-sm text-muted-foreground">{run.message}</p>
          <Button
            disabled={startRun.isPending}
            onClick={() => startRun.mutate({ monthRef, files })}
          >
            Tentar novamente
          </Button>
        </StatusCard>
      )

    case "pending_review":
      // Defensive: `to_response` always pairs this status with an item, but a
      // missing one must not blank-screen the reviewer.
      if (!run.item) {
        return <StatusCard title="Nenhuma revisão pendente" />
      }
      return <PendingReview monthRef={monthRef} item={run.item} />
  }
}

/** Shared chrome for the non-item states — one card, a title, some content. */
function StatusCard({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="mx-auto max-w-xl">
      <Card>
        <CardHeader>
          <CardTitle>{title}</CardTitle>
        </CardHeader>
        {children ? (
          <CardContent className="flex flex-col items-start gap-3">{children}</CardContent>
        ) : null}
      </Card>
    </div>
  )
}

/**
 * The pending item and its three answers.
 *
 * Keyed by description in the parent's render tree implicitly: the component
 * remounts nothing between items, so the correction picker is reset explicitly
 * whenever the item changes (see the `useEffect` below).
 */
function PendingReview({ monthRef, item }: { monthRef: string; item: ReviewItem }) {
  const transaction = item.transaction
  const answerReview = useAnswerReview()
  const taxonomyQuery = useTaxonomy()
  const taxonomy: Taxonomy = taxonomyQuery.data ?? {}

  const [correcting, setCorrecting] = useState(false)
  const [category, setCategory] = useState<string>("")
  const [subcategory, setSubcategory] = useState<string>("")

  // A new item means a new suggestion: never carry the previous pick over.
  useEffect(() => {
    setCorrecting(false)
    setCategory("")
    setSubcategory("")
  }, [transaction.date, transaction.description_raw, transaction.amount])

  /**
   * Subcategory options for the chosen category: the item's own
   * `suggested_subcategories` while the pick still matches the suggested
   * category, the taxonomy's own list for anything else.
   */
  const subcategories =
    category === "" ? [] : category === transaction.category
      ? item.suggested_subcategories
      : (taxonomy[category] ?? [])

  const isPending = answerReview.isPending

  return (
    <div className="mx-auto max-w-xl">
      <Card>
        <CardHeader>
          <CardTitle>Revisão pendente</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="font-medium">{transaction.description_raw}</span>
              {transaction.instrument === "credit" ? (
                <Badge variant="secondary">cartão de crédito</Badge>
              ) : null}
            </div>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm text-muted-foreground">
              <dt>Data</dt>
              <dd>{transaction.date}</dd>
              <dt>Valor</dt>
              <dd>{currency.format(transaction.amount)}</dd>
              <dt>Conta</dt>
              <dd>{transaction.account}</dd>
              <dt>Categoria</dt>
              <dd>
                {transaction.category ?? "—"}
                {transaction.subcategory ? ` / ${transaction.subcategory}` : ""}
              </dd>
              <dt>Confiança</dt>
              <dd>{transaction.confidence ?? "—"}</dd>
            </dl>
          </div>

          <div className="flex flex-wrap gap-2">
            {item.is_transfer_candidate ? (
              <Button
                disabled={isPending}
                onClick={() => answerReview.mutate({ monthRef, action: "confirm_transfer" })}
              >
                Confirmar transferência
              </Button>
            ) : (
              <Button
                disabled={isPending}
                onClick={() => answerReview.mutate({ monthRef, action: "accept" })}
              >
                Aceitar
              </Button>
            )}
            <Button
              variant="outline"
              disabled={isPending}
              onClick={() => setCorrecting((open) => !open)}
            >
              Corrigir
            </Button>
          </div>

          {correcting ? (
            <form
              className="space-y-4"
              onSubmit={(event) => {
                event.preventDefault()
                if (!category) return
                answerReview.mutate({
                  monthRef,
                  action: "correct",
                  category,
                  // Omitted when the category has no subcategories at all.
                  subcategory: subcategories.length > 0 ? subcategory || undefined : undefined,
                })
              }}
            >
              <div className="space-y-2">
                <Label htmlFor="correct-category">Categoria</Label>
                <Select
                  value={category}
                  onValueChange={(value) => {
                    setCategory(value)
                    setSubcategory("")
                  }}
                >
                  <SelectTrigger id="correct-category" className="w-full">
                    <SelectValue placeholder="Categoria" />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.keys(taxonomy).map((name) => (
                      <SelectItem key={name} value={name}>
                        {name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {subcategories.length > 0 ? (
                <div className="space-y-2">
                  <Label htmlFor="correct-subcategory">Subcategoria</Label>
                  <Select value={subcategory} onValueChange={setSubcategory}>
                    <SelectTrigger id="correct-subcategory" className="w-full">
                      <SelectValue placeholder="Subcategoria" />
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
              ) : null}

              <Button type="submit" disabled={isPending || !category}>
                Enviar correção
              </Button>
            </form>
          ) : null}
        </CardContent>
      </Card>
    </div>
  )
}
