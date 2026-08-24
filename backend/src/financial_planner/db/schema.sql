-- Schema das tabelas transactions e merchant_memory.
-- SQL padrão, sem sintaxe específica de SQLite, para permitir migração futura para
-- Postgres/Supabase sem alterar o schema (Princípio IV da constituição).

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dedup_hash TEXT NOT NULL UNIQUE,      -- preenchido pela feature de ingestão
    date TEXT NOT NULL,                   -- preenchido pela feature de ingestão (ISO 8601)
    description_raw TEXT NOT NULL,        -- preenchido pela feature de ingestão
    account TEXT NOT NULL,                -- preenchido pela feature de ingestão
    type TEXT NOT NULL,                   -- preenchido pela feature de ingestão (income | expense)
    amount REAL NOT NULL,                 -- preenchido pela feature de ingestão
    month_ref TEXT NOT NULL,              -- preenchido pela feature de ingestão
    category TEXT,                        -- preenchido por esta feature (categorize)
    subcategory TEXT,                     -- preenchido por esta feature (categorize)
    confidence TEXT,                      -- preenchido por esta feature (categorize)
    installment_id INTEGER                -- feature futura: parcelamentos
);

CREATE INDEX IF NOT EXISTS idx_transactions_dedup_hash ON transactions (dedup_hash);

-- Mapeamento merchant -> categoria já confirmada em execuções anteriores.
-- Esta feature (categorize) só lê; gravar é responsabilidade de uma feature futura
-- (update_memory).
CREATE TABLE IF NOT EXISTS merchant_memory (
    merchant_key TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    subcategory TEXT
);
