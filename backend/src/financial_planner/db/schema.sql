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
    fatura_ref TEXT                       -- feature 013: YYYY-MM of the fatura this row belongs to (credit rows) or settles (debit payment line, later)
);

CREATE INDEX IF NOT EXISTS idx_transactions_dedup_hash ON transactions (dedup_hash);
CREATE INDEX IF NOT EXISTS idx_transactions_instrument_month ON transactions (instrument, month_ref);
CREATE INDEX IF NOT EXISTS idx_transactions_fatura_ref ON transactions (fatura_ref);

-- Merchant -> category mapping already confirmed in previous runs.
-- This feature (categorize) only reads it; writing is a future feature's
-- responsibility (update_memory).
CREATE TABLE IF NOT EXISTS merchant_memory (
    merchant_key TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    subcategory TEXT
);
