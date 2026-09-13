/**
 * Global test setup (referenced by `vite.config.ts`'s `test.setupFiles`).
 *
 * `onUnhandledRequest: "error"` is deliberate: a request with no handler is a
 * test that would have hit a real backend, and that must fail loudly rather than
 * hang (specs/016-frontend-core "Testing strategy").
 */
import "@testing-library/jest-dom/vitest"

import { cleanup } from "@testing-library/react"
import { afterAll, afterEach, beforeAll } from "vitest"

import { server } from "./mocks/server"

beforeAll(() => server.listen({ onUnhandledRequest: "error" }))

afterEach(() => {
  cleanup()
  server.resetHandlers()
})

afterAll(() => server.close())
