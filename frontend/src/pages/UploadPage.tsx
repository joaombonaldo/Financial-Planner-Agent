/**
 * Upload + start-run screen: `/months/:monthRef/upload`.
 *
 * Two-step submit — `useUploadFiles()` then `useStartRun()` — then hand off to
 * the review screen. The server-side paths from the upload response are passed
 * through router state (`location.state.files: string[]`) so the review screen
 * can retry a failed run without asking the user to re-upload
 * (specs/016-frontend-core "Upload -> run handoff").
 */
import { type ChangeEvent, type FormEvent, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { toast } from "sonner"

import { useStartRun, useUploadFiles } from "@/api/mutations"
import type { ApiError } from "@/api/client"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

export default function UploadPage() {
  const { monthRef } = useParams<{ monthRef: string }>()
  const navigate = useNavigate()
  const uploadFiles = useUploadFiles()
  const startRun = useStartRun()
  const [files, setFiles] = useState<File[]>([])
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const isSubmitting = uploadFiles.isPending || startRun.isPending

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    setFiles(event.target.files ? Array.from(event.target.files) : [])
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!monthRef || files.length === 0) return
    setErrorMessage(null)

    try {
      const uploadResult = await uploadFiles.mutateAsync({ monthRef, files })
      await startRun.mutateAsync({ monthRef, files: uploadResult.files })
      navigate(`/months/${monthRef}/review`, { state: { files: uploadResult.files } })
    } catch (error) {
      const message = (error as ApiError).message
      setErrorMessage(message)
      toast.error(message)
    }
  }

  const statusLabel = uploadFiles.isPending
    ? "Enviando..."
    : startRun.isPending
      ? "Processando..."
      : "Processar mês"

  return (
    <div className="mx-auto max-w-xl">
      <Card>
        <CardHeader>
          <CardTitle>Enviar extratos — {monthRef}</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={handleSubmit}>
            <div className="space-y-2">
              <Label htmlFor="statement-files">Escolher arquivos</Label>
              <Input
                id="statement-files"
                type="file"
                multiple
                accept=".csv,.pdf"
                disabled={isSubmitting}
                onChange={handleFileChange}
              />
              <p className="text-sm text-muted-foreground">
                Extratos de débito (.csv) e faturas de cartão (.pdf).
              </p>
            </div>

            {files.length > 0 ? (
              <ul className="text-sm text-muted-foreground">
                {files.map((file) => (
                  <li key={file.name}>{file.name}</li>
                ))}
              </ul>
            ) : null}

            {errorMessage ? (
              <p role="alert" className="text-sm text-destructive">
                {errorMessage}
              </p>
            ) : null}

            <Button type="submit" disabled={files.length === 0 || isSubmitting}>
              {statusLabel}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
