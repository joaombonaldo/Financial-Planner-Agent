/**
 * Realistic example payloads, shaped against the real serializers in
 * `interface/api.py` / `nodes/review.py` / `nodes/queries.py` — not invented
 * separately (specs/016-frontend-core "Testing strategy").
 *
 * Wave 2 tests can import these and spread over them for per-test variants:
 *
 *   server.use(
 *     http.get(url("/months/:monthRef/report"), () =>
 *       HttpResponse.json({ ...reportFixture, total_expense: 0 })),
 *   )
 */
import type {
  MonthReport,
  MonthSummary,
  ReviewItem,
  Taxonomy,
  Transaction,
} from "@/api/types"

export const MONTH_REF = "2026-08"

/** A real subset of `config/categories.yaml`'s tree. */
export const taxonomyFixture: Taxonomy = {
  Moradia: ["Aluguel", "Condomínio", "Contas/Utilidades"],
  Alimentação: ["Supermercado", "Restaurantes", "Delivery"],
  Transporte: ["Combustível", "Transporte por aplicativo", "Estacionamento"],
  Compras: ["Roupas/Calçados", "Perfumes/Cosméticos", "Casa/Outros"],
  Saúde: ["Farmácia", "Consultas/Exames", "Plano de saúde"],
  Lazer: ["Streaming/Assinaturas", "Viagens", "Eventos"],
  Renda: ["Salário", "Reembolso", "Outros"],
  Transferências: [],
}

export const monthsFixture: MonthSummary[] = [
  { month_ref: "2026-08", transaction_count: 142, has_pending_review: true },
  { month_ref: "2026-07", transaction_count: 118, has_pending_review: false },
]

export const transactionsFixture: Transaction[] = [
  {
    dedup_hash: "a1b2c3d4e5f60718293a4b5c6d7e8f90",
    date: "2026-08-03",
    description_raw: "PIX ENVIADO IMOBILIARIA CENTRO",
    account: "bradesco",
    type: "expense",
    amount: 2450.0,
    month_ref: MONTH_REF,
    category: "Moradia",
    subcategory: "Aluguel",
    confidence: "high",
    instrument: "debit",
    fatura_ref: null,
    deleted_at: null,
  },
  {
    dedup_hash: "f0e9d8c7b6a5948372615f4e3d2c1b0a",
    date: "2026-08-21",
    description_raw: "RENNER LOJA 233 SAO PAULO",
    account: "inter",
    type: "expense",
    amount: 250.75,
    month_ref: MONTH_REF,
    category: "Compras",
    subcategory: "Roupas/Calçados",
    confidence: "medium",
    instrument: "credit",
    fatura_ref: "2026-09",
    deleted_at: null,
  },
]

export const reportFixture: MonthReport = {
  month_ref: MONTH_REF,
  total_income: 9800.0,
  total_expense: 6312.45,
  net_balance: 3487.55,
  transfer_total: 1200.0,
  category_breakdown: [
    { category: "Moradia", type: "expense", total: 2450.0, gross: 2450.0, reimbursed: 0.0 },
    { category: "Alimentação", type: "expense", total: 1380.2, gross: 1480.2, reimbursed: 100.0 },
    { category: "Transporte", type: "expense", total: 482.25, gross: 482.25, reimbursed: 0.0 },
    { category: "Renda", type: "income", total: 9800.0, gross: 9800.0, reimbursed: 0.0 },
  ],
  transaction_count: 142,
  budget_report: [
    {
      category: "Alimentação",
      goal: 1200.0,
      actual_spend: 1380.2,
      difference: -180.2,
      status: "over_budget",
    },
    {
      category: "Transporte",
      goal: 600.0,
      actual_spend: 482.25,
      difference: 117.75,
      status: "within_budget",
    },
  ],
  insights_summary:
    "Seus gastos com Alimentação ficaram 15% acima da meta neste mês, puxados por delivery.",
  insights_error: null,
  total_reimbursements: 100.0,
  unattributed_reimbursements: 0.0,
  credit_category_breakdown: [
    { category: "Compras", type: "expense", total: 250.75 },
    { category: "Lazer", type: "expense", total: 89.9 },
  ],
  credit_total: 340.65,
  fatura_reconciliations: [
    {
      fatura_ref: "2026-08",
      debit_payment: 1840.32,
      credit_purchases_total: 1840.32,
      delta: 0.0,
    },
  ],
}

/** Exactly `nodes/review.py:_build_payload`'s nested shape. */
export const reviewItemFixture: ReviewItem = {
  transaction: {
    date: "2026-08-21",
    description_raw: "RENNER LOJA 233 SAO PAULO",
    amount: 250.75,
    account: "inter",
    category: "Compras",
    subcategory: "Casa/Outros",
    confidence: "medium",
    instrument: "credit",
  },
  is_transfer_candidate: false,
  suggested_subcategories: taxonomyFixture["Compras"],
}

/** A transfer-candidate item — the branch that shows "Confirmar" instead of "Aceitar". */
export const transferReviewItemFixture: ReviewItem = {
  transaction: {
    date: "2026-08-05",
    description_raw: "TRANSFERENCIA ENTRE CONTAS PROPRIAS",
    amount: 1200.0,
    account: "bradesco",
    category: "Transferências",
    subcategory: null,
    confidence: "low",
    instrument: "debit",
  },
  is_transfer_candidate: true,
  suggested_subcategories: [],
}
