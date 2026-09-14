import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { describe, expect, it } from "vitest"

import NewMonthDialog from "./NewMonthDialog"

/** Alongside a stand-in `/months/:monthRef/upload` route so the form's
 * `navigate()` target is observable, not just its intent. No QueryClient
 * needed — this component makes no API calls of its own. */
function renderWithUploadRoute() {
  return render(
    <MemoryRouter initialEntries={["/months"]}>
      <Routes>
        <Route path="/months" element={<NewMonthDialog />} />
        <Route path="/months/:monthRef/upload" element={<div>Upload screen placeholder</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe("NewMonthDialog", () => {
  it("rejects an invalid month reference", async () => {
    const user = userEvent.setup()
    renderWithUploadRoute()

    await user.click(screen.getByRole("button", { name: "Novo mês" }))
    const input = await screen.findByLabelText("Mês (AAAA-MM)")
    await user.type(input, "2026-13")

    expect(screen.getByText(/Formato inválido/)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Continuar" })).toBeDisabled()
  })

  it("navigates to the upload screen for a valid month reference", async () => {
    const user = userEvent.setup()
    renderWithUploadRoute()

    await user.click(screen.getByRole("button", { name: "Novo mês" }))
    const input = await screen.findByLabelText("Mês (AAAA-MM)")
    await user.type(input, "2026-09")

    const continueButton = screen.getByRole("button", { name: "Continuar" })
    expect(continueButton).toBeEnabled()
    await user.click(continueButton)

    expect(await screen.findByText("Upload screen placeholder")).toBeInTheDocument()
  })
})
