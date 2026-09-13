/// <reference types="node" />
import { File as NodeFile } from "node:buffer"

import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { http, HttpResponse } from "msw"
import { describe, expect, it } from "vitest"

import { errorResponse, url } from "@/test/mocks/handlers"
import { server } from "@/test/mocks/server"
import { renderApp, renderWithProviders } from "@/test/utils"

import UploadPage from "./UploadPage"

// `node:buffer`'s File, not jsdom's global one: MSW's Node-side request
// handling (`request.formData()` in the default upload handler) runs on
// undici, whose multipart parser rejects jsdom's File instances.
function csvFile(name = "extrato.csv"): File {
  return new NodeFile(["a,b\n1,2"], name, { type: "text/csv" }) as unknown as File
}

describe("UploadPage", () => {
  it("uploads files, starts the run, and navigates to the review screen", async () => {
    const user = userEvent.setup()
    renderApp({ route: "/months/2026-08/upload" })

    const input = screen.getByLabelText(/escolher arquivos/i)
    await user.upload(input, csvFile())

    await user.click(screen.getByRole("button", { name: /processar mês/i }))

    // Don't assert on ReviewPage's own content (built in parallel) — just that
    // navigation left the upload screen, which only happens on the success path.
    await waitFor(() => {
      expect(screen.queryByLabelText(/escolher arquivos/i)).not.toBeInTheDocument()
    })
  })

  it("sends the upload response's server-side paths to the run endpoint", async () => {
    let capturedRunFiles: string[] | undefined
    server.use(
      http.post(url("/months/:monthRef/uploads"), () =>
        HttpResponse.json({ files: ["extracts/2026-08/extrato.csv"] }, { status: 201 }),
      ),
      http.post(url("/months/:monthRef/run"), async ({ request }) => {
        const body = (await request.json()) as { files: string[] }
        capturedRunFiles = body.files
        return HttpResponse.json({ status: "processing" }, { status: 202 })
      }),
    )

    const user = userEvent.setup()
    renderWithProviders(<UploadPage />, { route: "/months/2026-08/upload" })

    await user.upload(screen.getByLabelText(/escolher arquivos/i), csvFile())
    await user.click(screen.getByRole("button", { name: /processar mês/i }))

    await waitFor(() => {
      expect(capturedRunFiles).toEqual(["extracts/2026-08/extrato.csv"])
    })
  })

  it("shows an error and does not call the run endpoint when upload fails", async () => {
    let runCalled = false
    server.use(
      http.post(url("/months/:monthRef/uploads"), () =>
        errorResponse(400, "invalid_file", "Arquivo inválido."),
      ),
      http.post(url("/months/:monthRef/run"), () => {
        runCalled = true
        return HttpResponse.json({ status: "processing" }, { status: 202 })
      }),
    )

    const user = userEvent.setup()
    renderWithProviders(<UploadPage />, { route: "/months/2026-08/upload" })

    await user.upload(screen.getByLabelText(/escolher arquivos/i), csvFile())
    await user.click(screen.getByRole("button", { name: /processar mês/i }))

    await waitFor(() => {
      expect(screen.getByText("Arquivo inválido.")).toBeInTheDocument()
    })
    expect(runCalled).toBe(false)
  })

  it("shows an error when the run fails to start after a successful upload", async () => {
    server.use(
      http.post(url("/months/:monthRef/uploads"), () =>
        HttpResponse.json({ files: ["extracts/2026-08/extrato.csv"] }, { status: 201 }),
      ),
      http.post(url("/months/:monthRef/run"), () =>
        errorResponse(500, "internal_error", "Falha ao iniciar o processamento."),
      ),
    )

    const user = userEvent.setup()
    renderWithProviders(<UploadPage />, { route: "/months/2026-08/upload" })

    await user.upload(screen.getByLabelText(/escolher arquivos/i), csvFile())
    await user.click(screen.getByRole("button", { name: /processar mês/i }))

    await waitFor(() => {
      expect(screen.getByText("Falha ao iniciar o processamento.")).toBeInTheDocument()
    })
  })
})
