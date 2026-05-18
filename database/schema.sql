CREATE EXTENSION IF NOT EXISTS vector;

-- =========================
-- Sessions
-- =========================
CREATE TABLE IF NOT EXISTS session_s (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    mode TEXT NOT NULL,
    language TEXT,
    title TEXT,
    project_tag TEXT
);

-- =========================
-- Messages
-- =========================
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES session_s(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS messages_session_idx
    ON messages (session_id, id);

-- =========================
-- Artifacts
-- =========================
CREATE TABLE IF NOT EXISTS artifacts (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES session_s(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS artifacts_session_kind_idx
    ON artifacts (session_id, kind);

-- =========================
-- Long-term memory
-- =========================
CREATE TABLE IF NOT EXISTS memory_notes (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES session_s(id) ON DELETE SET NULL,
    category TEXT NOT NULL,
    note TEXT NOT NULL,
    importance INTEGER NOT NULL DEFAULT 1 CHECK (importance BETWEEN 1 AND 5),
    project_tag TEXT,
    embedding vector(384),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS memory_notes_embedding_idx
    ON memory_notes USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS memory_notes_category_idx
    ON memory_notes (category);

CREATE INDEX IF NOT EXISTS memory_notes_session_idx
    ON memory_notes (session_id);

-- =========================
-- Task runs
-- 1 row = 1 agent task execution
-- =========================
CREATE TABLE IF NOT EXISTS task_runs (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES session_s(id) ON DELETE CASCADE,
    audience TEXT NOT NULL,                     -- human | agent
    mode TEXT NOT NULL,                         -- tutor | explainer | reviewer | planner
    intent TEXT,                                -- bug_fix | code_review | ...
    complexity TEXT,                            -- simple | complex | extreme
    input_mode TEXT,                            -- code | question | error_log | patch_request | architecture
    language TEXT,
    user_input TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'started',     -- started | succeeded | failed | escalated | blocked
    confidence REAL,
    needs_escalation BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS task_runs_session_idx
    ON task_runs (session_id);

CREATE INDEX IF NOT EXISTS task_runs_status_idx
    ON task_runs (status);

CREATE INDEX IF NOT EXISTS task_runs_intent_idx
    ON task_runs (intent);

-- =========================
-- Tooling / repo profiles
-- reusable commands and conventions
-- =========================
CREATE TABLE IF NOT EXISTS tooling_profiles (
    id SERIAL PRIMARY KEY,
    project_tag TEXT NOT NULL,
    language TEXT,
    test_command TEXT,
    build_command TEXT,
    lint_command TEXT,
    format_command TEXT,
    run_command TEXT,
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_tag, language)
);

-- =========================
-- Patch attempts
-- 1 row = 1 attempt by executor
-- =========================
CREATE TABLE IF NOT EXISTS patch_attempts (
    id SERIAL PRIMARY KEY,
    task_run_id INTEGER REFERENCES task_runs(id) ON DELETE CASCADE,
    session_id INTEGER REFERENCES session_s(id) ON DELETE CASCADE,
    target_file TEXT,
    matched_by TEXT,                            -- ast | fuzzy | literal
    phase TEXT NOT NULL,                        -- dry_run_blocked | apply_failed | validated | validation_failed ...
    risk_level TEXT,                            -- low | medium | high
    risk_score INTEGER,
    diff TEXT,
    validation_ok BOOLEAN,
    validation_output TEXT,
    rollback_performed BOOLEAN NOT NULL DEFAULT FALSE,
    failure_category TEXT,                      -- syntax_error | import_error | assertion_failure | ...
    failure_reason TEXT,
    project_tag TEXT,
    patch_payload JSONB,                        -- original patch JSON
    target_node_name TEXT,                      -- ghost-graph: symbol the patch targeted
    target_node_kind TEXT,                      -- ghost-graph: function | class | method | ...
    ghost_key TEXT,                             -- sha256(project_tag|file|node_name|normalized_snippet)
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Ghost-graph migration for pre-existing deployments.
ALTER TABLE patch_attempts ADD COLUMN IF NOT EXISTS target_node_name TEXT;
ALTER TABLE patch_attempts ADD COLUMN IF NOT EXISTS target_node_kind TEXT;
ALTER TABLE patch_attempts ADD COLUMN IF NOT EXISTS ghost_key TEXT;

-- Mutation oracle (Phase 2). NULL when oracle is disabled or no mutants applied.
ALTER TABLE patch_attempts ADD COLUMN IF NOT EXISTS oracle_strength REAL;
ALTER TABLE patch_attempts ADD COLUMN IF NOT EXISTS oracle_tested INTEGER;
ALTER TABLE patch_attempts ADD COLUMN IF NOT EXISTS oracle_killed INTEGER;

CREATE INDEX IF NOT EXISTS patch_attempts_task_run_idx
    ON patch_attempts (task_run_id);

CREATE INDEX IF NOT EXISTS patch_attempts_session_idx
    ON patch_attempts (session_id);

CREATE INDEX IF NOT EXISTS patch_attempts_phase_idx
    ON patch_attempts (phase);

CREATE INDEX IF NOT EXISTS patch_attempts_matched_by_idx
    ON patch_attempts (matched_by);

-- Ghost-graph lookup paths:
--   (project_tag, target_file, target_node_name) → "have I touched this symbol before?"
--   (project_tag, ghost_key)                     → "have I tried this exact edit before?"
CREATE INDEX IF NOT EXISTS patch_attempts_ghost_symbol_idx
    ON patch_attempts (project_tag, target_file, target_node_name);

CREATE INDEX IF NOT EXISTS patch_attempts_ghost_key_idx
    ON patch_attempts (project_tag, ghost_key);

-- =========================
-- Optional: symbol snapshots
-- useful later for repo-aware memory
-- =========================
CREATE TABLE IF NOT EXISTS code_snapshots (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES session_s(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    language TEXT,
    summary JSONB NOT NULL,                     -- compact code_analysis result
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS code_snapshots_session_idx
    ON code_snapshots (session_id);

CREATE INDEX IF NOT EXISTS code_snapshots_file_idx
    ON code_snapshots (file_path);

-- =========================
-- Code Units
-- 1 row = 1 indexed code symbol (function, class, etc.) with embedding
-- =========================
CREATE TABLE IF NOT EXISTS code_units (
    id SERIAL PRIMARY KEY,
    file_path TEXT NOT NULL,
    kind TEXT,
    name TEXT,
    content TEXT,
    embedding vector(384),
    project_tag TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Migrate older deployments that pre-date the project_tag column.
ALTER TABLE code_units ADD COLUMN IF NOT EXISTS project_tag TEXT;

CREATE INDEX IF NOT EXISTS code_units_file_idx
    ON code_units (file_path);

CREATE INDEX IF NOT EXISTS code_units_project_tag_idx
    ON code_units (project_tag);

CREATE INDEX IF NOT EXISTS code_units_embedding_idx
    ON code_units USING hnsw (embedding vector_cosine_ops);

-- =========================
-- Code Dependencies
-- 1 row = 1 directed dependency edge (call, import, etc.)
-- =========================
CREATE TABLE IF NOT EXISTS code_dependencies (
    id SERIAL PRIMARY KEY,
    source_file TEXT NOT NULL,
    target_file TEXT,
    source_symbol TEXT,
    target_symbol TEXT,
    dependency_type TEXT NOT NULL,
    project_tag TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Migrate older deployments that pre-date the project_tag column.
ALTER TABLE code_dependencies ADD COLUMN IF NOT EXISTS project_tag TEXT;

CREATE INDEX IF NOT EXISTS code_dependencies_source_idx
    ON code_dependencies (source_file, source_symbol);

CREATE INDEX IF NOT EXISTS code_dependencies_target_idx
    ON code_dependencies (target_file, target_symbol);

CREATE INDEX IF NOT EXISTS code_dependencies_project_tag_idx
    ON code_dependencies (project_tag);




-- -- Drop dependent tables first (foreign key order)

-- DROP TABLE IF EXISTS code_dependencies;
-- DROP TABLE IF EXISTS code_snapshots;
-- DROP TABLE IF EXISTS patch_attempts;
-- DROP TABLE IF EXISTS task_runs;
-- DROP TABLE IF EXISTS messages;
-- DROP TABLE IF EXISTS artifacts;
-- DROP TABLE IF EXISTS tooling_profiles;
-- DROP TABLE IF EXISTS memory_notes;
-- DROP TABLE IF EXISTS session_s;
-- DROP TABLE IF EXISTS code_units;
