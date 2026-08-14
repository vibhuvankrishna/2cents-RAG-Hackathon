-- SQLite schema for Valura client book + market
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS clients (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS accounts (
  id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL REFERENCES clients(id),
  opened TEXT,
  broker_ref TEXT,
  base_currency TEXT
);

CREATE TABLE IF NOT EXISTS kyc (
  id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL UNIQUE REFERENCES clients(id),
  pan TEXT,
  kyc_status TEXT,
  risk_profile TEXT,
  date_of_birth TEXT,
  address TEXT,
  annual_income_band TEXT,
  bank_name TEXT,
  bank_account TEXT,
  ifsc TEXT,
  employer TEXT,
  occupation TEXT
);

CREATE TABLE IF NOT EXISTS suitability_reviews (
  id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL REFERENCES clients(id),
  date TEXT,
  risk_profile TEXT,
  reviewer TEXT,
  outcome TEXT
);

CREATE TABLE IF NOT EXISTS target_allocations (
  review_id TEXT NOT NULL REFERENCES suitability_reviews(id),
  symbol TEXT NOT NULL,
  pct TEXT NOT NULL,
  PRIMARY KEY (review_id, symbol)
);

CREATE TABLE IF NOT EXISTS notes (
  id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL REFERENCES clients(id),
  date TEXT,
  author TEXT,
  text TEXT
);

CREATE TABLE IF NOT EXISTS transactions (
  id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL REFERENCES clients(id),
  date TEXT NOT NULL,
  type TEXT NOT NULL,
  symbol TEXT,
  quantity TEXT,
  price_usd TEXT,
  gross_usd TEXT,
  fees_usd TEXT,
  net_usd TEXT,
  amount_usd TEXT,
  amount_inr TEXT,
  fx_rate TEXT,
  lrs_ref TEXT,
  description TEXT,
  destination TEXT,
  withholding_tax_usd TEXT,
  memo TEXT
);

CREATE INDEX IF NOT EXISTS idx_txn_client_date ON transactions(client_id, date, type);
CREATE INDEX IF NOT EXISTS idx_txn_symbol ON transactions(client_id, symbol, type);

CREATE TABLE IF NOT EXISTS positions_snapshot (
  id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL REFERENCES clients(id),
  symbol TEXT NOT NULL,
  quantity TEXT,
  avg_cost_usd TEXT,
  market_value_usd TEXT
);

CREATE TABLE IF NOT EXISTS instruments (
  symbol TEXT PRIMARY KEY,
  sector TEXT,
  industry TEXT,
  currency TEXT,
  listed_on TEXT
);

CREATE TABLE IF NOT EXISTS prices (
  symbol TEXT NOT NULL,
  date TEXT NOT NULL,
  close TEXT NOT NULL,
  PRIMARY KEY (symbol, date)
);

CREATE TABLE IF NOT EXISTS news (
  id TEXT PRIMARY KEY,
  date TEXT,
  symbol TEXT,
  headline TEXT,
  body TEXT,
  source TEXT
);

CREATE TABLE IF NOT EXISTS covered_symbols (
  symbol TEXT PRIMARY KEY
);

CREATE INDEX IF NOT EXISTS idx_notes_client ON notes(client_id);
CREATE INDEX IF NOT EXISTS idx_news_symbol_date ON news(symbol, date);
