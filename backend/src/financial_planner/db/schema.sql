-- Schema for the transactions and merchant_memory tables.
-- Standard SQL, no SQLite-specific syntax, to allow a future migration to
-- Postgres/Supabase without changing the schema (Principle IV of the constitution).

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dedup_hash TEXT NOT NULL UNIQUE,      -- filled in by the ingestion feature
    date TEXT NOT NULL,                   -- filled in by the ingestion feature (ISO 8601)
    description_raw TEXT NOT NULL,        -- filled in by the ingestion feature
    account TEXT NOT NULL,                -- filled in by the ingestion feature
    type TEXT NOT NULL,                   -- filled in by the ingestion feature (income | expense)
    amount REAL NOT NULL,                 -- filled in by the ingestion feature
    month_ref TEXT NOT NULL,              -- filled in by the ingestion feature
    category TEXT,                        -- filled in by this feature (categorize)
    subcategory TEXT,                     -- filled in by this feature (categorize)
    confidence TEXT,                      -- filled in by this feature (categorize)
    installment_id INTEGER,               -- future feature: installments
    instrument TEXT NOT NULL DEFAULT 'debit',  -- feature 013: 'debit' | 'credit' (credit = itemized fatura purchase)
    fatura_ref TEXT,                      -- feature 013: YYYY-MM of the fatura this row belongs to (credit rows) or settles (debit payment line, later)
    deleted_at TEXT                       -- feature 015: soft-delete (NULL = active). Never a real DELETE -- see db/repository.py
);

CREATE INDEX IF NOT EXISTS idx_transactions_dedup_hash ON transactions (dedup_hash);
CREATE INDEX IF NOT EXISTS idx_transactions_instrument_month ON transactions (instrument, month_ref);
CREATE INDEX IF NOT EXISTS idx_transactions_fatura_ref ON transactions (fatura_ref);
CREATE INDEX IF NOT EXISTS idx_transactions_deleted_at ON transactions (deleted_at);

-- Merchant -> category mapping already confirmed in previous runs.
-- This feature (categorize) only reads it; writing is a future feature's
-- responsibility (update_memory).
CREATE TABLE IF NOT EXISTS merchant_memory (
    merchant_key TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    subcategory TEXT
);

-- Budget goals (feature: budget UI, 2026-09-14). Replaces config/budget.local.yaml --
-- BRD §5.5 always anticipated goals eventually moving to a real store "without
-- changing the rest of the system", i.e. nodes/budget.py's callers don't change.
-- month_ref = '__default__' (the DEFAULT_BUDGET_SCOPE sentinel, db/repository.py) is
-- the global default; any other month_ref is that month's override for the given
-- category, merged over the default at read time (repository.get_effective_budget).
-- A sentinel string, not NULL, because SQLite's UNIQUE treats every NULL as
-- distinct -- NULL would not actually stop two default rows for the same category.
CREATE TABLE IF NOT EXISTS budget_goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    month_ref TEXT NOT NULL DEFAULT '__default__',
    category TEXT NOT NULL,
    goal REAL NOT NULL,
    UNIQUE(month_ref, category)
);

CREATE INDEX IF NOT EXISTS idx_budget_goals_month_ref ON budget_goals (month_ref);
