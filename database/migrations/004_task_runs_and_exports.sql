-- Task run records for flying-check query execution.
-- MVP backend currently persists mock task payloads to backend/runtime/task_runs.jsonl.
-- This table is the production target when a real database is connected.

CREATE TABLE IF NOT EXISTS query_task_runs (
  task_id VARCHAR(64) PRIMARY KEY,
  status VARCHAR(32) NOT NULL,
  rule_item_id VARCHAR(64),
  rule_type VARCHAR(64),
  item_code TEXT,
  item_name TEXT,
  date_start DATE,
  date_end DATE,
  execution_mode VARCHAR(32) NOT NULL DEFAULT 'mock',
  sql_executed BOOLEAN NOT NULL DEFAULT FALSE,
  sql_template_id VARCHAR(128),
  sql_text TEXT,
  sql_parameters_json TEXT,
  sql_validation_json TEXT,
  summary_json TEXT,
  charts_json TEXT,
  details_json TEXT,
  export_json TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_query_task_runs_rule_item_id ON query_task_runs(rule_item_id);
CREATE INDEX IF NOT EXISTS idx_query_task_runs_rule_type ON query_task_runs(rule_type);
CREATE INDEX IF NOT EXISTS idx_query_task_runs_created_at ON query_task_runs(created_at);
