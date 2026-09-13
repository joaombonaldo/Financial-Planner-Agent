/**
 * Render helpers for tests.
 *
 * **Wave 2 default: `renderWithProviders(<ReviewPage />, { route })`** — it gives
 * the component a fresh QueryClient and a MemoryRouter carrying the real route
 * table, so `useParams()` sees a real `:monthRef` and `<Link>`/`navigate()` work.
 *
 * Use `renderApp({ route })` only when the assertion is about routing itself
 * (a redirect, the shared nav, navigating between screens): it mounts the whole
 * `AppRoutes` tree inside `Layout`, so the page under test is chosen by the URL
 * rather than passed in.
 *
 * Both build a brand-new `QueryClient` per call with `retry: false`, so a test
 * asserting a 4xx/5xx path fails fast instead of hanging on retries, and no cache
 * ever leaks between tests.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, type RenderOptions, type RenderResult } from "@testing-library/react"
import type { ReactElement, ReactNode } from "react"
import { MemoryRouter, Navigate, Route, Routes } from "react-router-dom"

import { AppRoutes } from "@/App"
import Layout from "@/components/Layout"

/** Fresh, retry-free client. Exported for tests that want to inspect the cache. */
export function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchOnWindowFocus: false, gcTime: Infinity },
      mutations: { retry: false },
    },
  })
}

export interface RenderWithProvidersOptions extends Omit<RenderOptions, "wrapper"> {
  /** Initial URL. Use a concrete one (e.g. `/months/2026-08/review`) so `useParams` resolves. */
  route?: string
  /** Pass your own client to pre-seed or inspect the cache; one is created otherwise. */
  queryClient?: QueryClient
}

export interface RenderWithProvidersResult extends RenderResult {
  queryClient: QueryClient
}

/**
 * Render a single component with QueryClient + Router context.
 *
 * The component is mounted at the catch-all `*` route, so whatever `route` you
 * pass, the component under test renders and `useParams()` still reads that URL's
 * `:monthRef` — provided `route` matches the page's real path shape.
 */
export function renderWithProviders(
  ui: ReactElement,
  { route = "/", queryClient = createTestQueryClient(), ...options }: RenderWithProvidersOptions = {},
): RenderWithProvidersResult {
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[route]}>
          <Routes>
            <Route path="/months/:monthRef/*" element={children} />
            <Route path="*" element={children} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    )
  }

  return {
    ...render(ui, { wrapper: Wrapper, ...options }),
    queryClient,
  }
}

/** Render the full app (Layout + every route) at `route` — for routing assertions. */
export function renderApp({
  route = "/",
  queryClient = createTestQueryClient(),
}: RenderWithProvidersOptions = {}): RenderWithProvidersResult {
  return {
    ...render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[route]}>
          <AppRoutes />
        </MemoryRouter>
      </QueryClientProvider>,
    ),
    queryClient,
  }
}

/** Render just the shared shell with arbitrary children in its `<Outlet />` slot. */
export function renderInLayout(
  children: ReactNode,
  { route = "/", queryClient = createTestQueryClient() }: RenderWithProvidersOptions = {},
): RenderWithProvidersResult {
  return {
    ...render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[route]}>
          <Routes>
            <Route element={<Layout />}>
              <Route path="/" element={<Navigate to="/months" replace />} />
              <Route path="*" element={<>{children}</>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    ),
    queryClient,
  }
}
