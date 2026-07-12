CREATE TABLE IF NOT EXISTS source_assets (
    asset_id TEXT PRIMARY KEY,
    source_package TEXT NOT NULL,
    original_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_ext TEXT,
    file_size BIGINT,
    content_hash TEXT,
    category TEXT,
    target_module TEXT,
    convert_required BOOLEAN DEFAULT FALSE,
    parse_status TEXT NOT NULL,
    parse_error TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rule_definitions (
    rule_id TEXT PRIMARY KEY,
    rule_code TEXT NOT NULL,
    rule_name TEXT NOT NULL,
    rule_type TEXT NOT NULL,
    target_type TEXT NOT NULL,
    condition JSONB NOT NULL DEFAULT '{}'::jsonb,
    sql_template_id TEXT NOT NULL,
    executor_class TEXT NOT NULL,
    policy_basis TEXT,
    source_file TEXT,
    version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    effective_from DATE,
    effective_to DATE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rule_items (
    id BIGSERIAL PRIMARY KEY,
    rule_id TEXT NOT NULL REFERENCES rule_definitions(rule_id),
    item_code TEXT,
    item_name TEXT,
    item_type TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS policy_documents (
    document_id TEXT PRIMARY KEY,
    asset_id TEXT REFERENCES source_assets(asset_id),
    title TEXT,
    doc_no TEXT,
    issuer TEXT,
    publish_date DATE,
    effective_date DATE,
    region TEXT,
    source_file TEXT NOT NULL,
    content_hash TEXT,
    parse_status TEXT NOT NULL DEFAULT 'raw_registered',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS policy_chunks (
    chunk_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES policy_documents(document_id),
    chunk_index INTEGER NOT NULL,
    section_title TEXT,
    content TEXT NOT NULL,
    page_no TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS query_tasks (
    task_id TEXT PRIMARY KEY,
    expert_name TEXT,
    original_question TEXT NOT NULL,
    structured_conditions JSONB,
    matched_rule_ids TEXT[],
    policy_citations JSONB,
    generated_sql TEXT,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_message TEXT
);


CREATE TABLE IF NOT EXISTS linked_rule_items (
    item_rule_id TEXT PRIMARY KEY,
    rule_type TEXT NOT NULL,
    source_file TEXT NOT NULL,
    source_sheet TEXT NOT NULL,
    knowledge_point_id TEXT,
    item_code TEXT NOT NULL,
    item_name TEXT,
    condition_text TEXT,
    gender_limit TEXT,
    age_limit TEXT,
    raw_row JSONB NOT NULL DEFAULT '{}'::jsonb,
    link_status TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_linked_rule_items_rule_type
    ON linked_rule_items(rule_type);

CREATE INDEX IF NOT EXISTS idx_linked_rule_items_item_code
    ON linked_rule_items(item_code);

CREATE INDEX IF NOT EXISTS idx_linked_rule_items_status
    ON linked_rule_items(status);
