-- Quick query and evidence relationship layer.
-- This is a relational graph foundation. Neo4j is not required for the MVP stage.

CREATE TABLE IF NOT EXISTS charge_items (
  charge_item_id VARCHAR(64) PRIMARY KEY,
  item_code VARCHAR(64),
  item_name TEXT NOT NULL,
  item_type VARCHAR(64),
  source_asset_id VARCHAR(64),
  effective_date DATE,
  expire_date DATE,
  status VARCHAR(32) NOT NULL DEFAULT 'draft'
);

CREATE TABLE IF NOT EXISTS charge_codes (
  charge_code VARCHAR(64) PRIMARY KEY,
  charge_item_id VARCHAR(64),
  code_system VARCHAR(64) DEFAULT 'hilist_code',
  status VARCHAR(32) NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS price_versions (
  price_version_id VARCHAR(64) PRIMARY KEY,
  charge_item_id VARCHAR(64),
  price_amount DECIMAL(18, 4),
  payment_category VARCHAR(128),
  document_no VARCHAR(128),
  source_asset_id VARCHAR(64),
  effective_date DATE,
  expire_date DATE
);

CREATE TABLE IF NOT EXISTS policy_clauses (
  clause_id VARCHAR(64) PRIMARY KEY,
  document_id VARCHAR(64),
  title TEXT,
  content TEXT,
  page_no INTEGER,
  source_asset_id VARCHAR(64)
);

CREATE TABLE IF NOT EXISTS evidence_edges (
  edge_id VARCHAR(128) PRIMARY KEY,
  source_type VARCHAR(64) NOT NULL,
  source_id VARCHAR(128) NOT NULL,
  relation VARCHAR(64) NOT NULL,
  target_type VARCHAR(64) NOT NULL,
  target_id VARCHAR(128) NOT NULL,
  evidence_text TEXT,
  source_asset_id VARCHAR(64)
);

CREATE INDEX IF NOT EXISTS idx_charge_items_code ON charge_items(item_code);
CREATE INDEX IF NOT EXISTS idx_charge_items_name ON charge_items(item_name);
CREATE INDEX IF NOT EXISTS idx_evidence_edges_source ON evidence_edges(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_evidence_edges_target ON evidence_edges(target_type, target_id);