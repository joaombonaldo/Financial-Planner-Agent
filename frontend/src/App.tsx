/**
 * Providers + routes. The route table matches specs/016-frontend-core
 * "Screens and routes" exactly; `src/test/utils.tsx` re-declares the same table
 * for tests, so the two must stay in step.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom"

import Layout from "@/components/Layout"
import { Toaster } from "@/components/ui/sonner"
import MonthsPage from "@/pages/MonthsPage"
import ReportPage from "@/pages/ReportPage"
import ReviewPage from "@/pages/ReviewPage"
import TransactionsPage from "@/pages/TransactionsPage"
import UploadPage from "@/pages/UploadPage"

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // A single local user watching their own screen: refetching on every window
      // focus just adds noise (and, on the report, real recomputation).
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

/** The routed tree, shared with the test harness. */
export function AppRoutes() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Navigate to="/months" replace />} />
        <Route path="/months" element={<MonthsPage />} />
        <Route path="/months/:monthRef/upload" element={<UploadPage />} />
        <Route path="/months/:monthRef/review" element={<ReviewPage />} />
        <Route path="/months/:monthRef/report" element={<ReportPage />} />
        <Route path="/months/:monthRef/transactions" element={<TransactionsPage />} />
      </Route>
    </Routes>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
      <Toaster />
    </QueryClientProvider>
  )
}
