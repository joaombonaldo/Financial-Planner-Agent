-- Schema da tabela transactions (BRD secao 6.1).
-- Esta feature (detect_and_parse) só preenche as colunas marcadas abaixo; as demais
-- ficam NULL até as features de categorização/parcelamento serem implementadas.
-- SQL padrão, sem sintaxe específica de SQLite, para permitir migração futura para
-- Postgres/Supabase sem alterar o schema (Princípio IV da constituição).

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dedup_hash TEXT NOT NULL UNIQUE,      -- preenchido por esta feature
    date TEXT NOT NULL,                   -- preenchido por esta feature (ISO 8601)
    description_raw TEXT NOT NULL,        -- preenchido por esta feature
    account TEXT NOT NULL,                -- preenchido por esta feature
    type TEXT NOT NULL,                   -- preenchido por esta feature (income | expense)
    amount REAL NOT NULL,                 -- preenchido por esta feature
    month_ref TEXT NOT NULL,              -- preenchido por esta feature
    category TEXT,                        -- feature futura: categorize
    subcategory TEXT,                     -- feature futura: categorize
    confidence TEXT,                      -- feature futura: categorize
    installment_id INTEGER                -- feature futura: parcelamentos
);

CREATE INDEX IF NOT EXISTS idx_transactions_dedup_hash ON transactions (dedup_hash);
