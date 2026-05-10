from __future__ import annotations
import atexit
import sys
import os
from pathlib import Path

# Add project root to sys.path to allow importing config.py
root_dir = str(Path(__file__).parent.parent)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from config import DATABASE_URL, DB_ENABLED
from typing import Optional, List, Dict, Any
import json

# psycopg_pool / libpq are imported lazily inside get_pool(). Keeping the
# import lazy means DB_ENABLED=false (e.g. Codespaces) doesn't require the
# native libpq library to be installed at all.
_pool = None  # type: ignore[var-annotated]


def db_enabled() -> bool:
    """True iff persistence is on AND a connection string is configured.

    Every public function in this module guards on this so a missing/down
    Postgres never blocks the agent (or stalls 30s on connect timeout).
    """
    return DB_ENABLED and bool(DATABASE_URL)


def get_pool():
    global _pool
    if not db_enabled():
        # Fast fail — never attempt a connection when DB is off.
        raise RuntimeError("DB disabled (DB_ENABLED=false or DATABASE_URL unset).")
    if _pool is None:
        try:
            from psycopg_pool import ConnectionPool  # lazy: needs libpq
        except Exception as e:
            raise RuntimeError(f"psycopg_pool unavailable: {e}")
        try:
            _pool = ConnectionPool(DATABASE_URL)
        except Exception as e:
            raise RuntimeError(f"Could not connect to database at {DATABASE_URL}: {e}")
    return _pool


@atexit.register
def _close_pool() -> None:
    """Shut the pool down before the interpreter starts tearing down threads.
    Without this, psycopg_pool's own finalizer races with shutdown and logs
    'couldn't stop thread pool-1-worker-N within 5.0 seconds'.
    """
    global _pool
    if _pool is not None:
        try:
            _pool.close()
        except Exception:
            pass
        _pool = None


def get_conn():
    return get_pool().connection()


def init_db():
    if not db_enabled():
        return
    schema = """
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
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS patch_attempts_task_run_idx
    ON patch_attempts (task_run_id);

CREATE INDEX IF NOT EXISTS patch_attempts_session_idx
    ON patch_attempts (session_id);

CREATE INDEX IF NOT EXISTS patch_attempts_phase_idx
    ON patch_attempts (phase);

CREATE INDEX IF NOT EXISTS patch_attempts_matched_by_idx
    ON patch_attempts (matched_by);

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


    """

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(schema)
        conn.commit()


def create_session(
    mode: str,
    language: Optional[str],
    title: Optional[str] = None,
    project_tag: Optional[str] = None,
) -> int:
    if not db_enabled():
        # Caller wraps this in try/except and falls back to a synthetic id.
        raise RuntimeError("DB disabled")
    query = """
    INSERT INTO session_s (mode, language, title, project_tag)
    VALUES (%s, %s, %s, %s)
    RETURNING id;
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (mode, language, title, project_tag))
            session_id = cur.fetchone()[0]
        conn.commit()
    return session_id


def save_message(session_id: int, role: str, content: str):
    if not db_enabled():
        return
    query = """
    INSERT INTO messages (session_id, role, content)
    VALUES (%s, %s, %s);
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (session_id, role, content))
        conn.commit()


def save_artifact(session_id: int, kind: str, content: str):
    if not db_enabled():
        return
    query = """
    INSERT INTO artifacts (session_id, kind, content)
    VALUES (%s, %s, %s);
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (session_id, kind, content))
        conn.commit()


def _embed_text(text: str) -> list[float]:
    # Lazy import so simply importing database.memory doesn't pull heavy
    # embedding dependencies (sentence-transformers / torch).
    from core.router import get_model
    model = get_model()
    return model.encode([text])[0].tolist()


def save_memory_note(
    session_id: Optional[int],
    category: str,
    note: str,
    importance: int = 1,
    project_tag: Optional[str] = None,
):
    if not db_enabled():
        return
    embedding_list = _embed_text(note)

    query = """
    INSERT INTO memory_notes (session_id, category, note, importance, embedding, project_tag)
    VALUES (%s, %s, %s, %s, %s::vector, %s);
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (session_id, category, note, max(1, min(5, importance)), str(embedding_list), project_tag),
            )
        conn.commit()


def save_engineering_memory(
    session_id: Optional[int],
    memory_type: str,
    value: str,
    importance: int = 3,
    project_tag: Optional[str] = None,
) -> None:
    """
    Convenience wrapper for repo/tooling-oriented memory.
    Example categories:
    - tooling_command
    - repo_convention
    - bug_pattern
    - successful_fix
    - project_context
    """
    save_memory_note(
        session_id=session_id,
        category=memory_type,
        note=value,
        importance=importance,
        project_tag=project_tag
    )


def get_recent_messages(session_id: int, limit: int = 8) -> List[Dict]:
    if not db_enabled():
        return []
    query = """
    SELECT role, content, created_at
    FROM messages
    WHERE session_id = %s
    ORDER BY id DESC
    LIMIT %s;
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (session_id, limit))
            rows = cur.fetchall()

    rows.reverse()
    return [
        {"role": role, "content": content, "created_at": created_at.isoformat()}
        for role, content, created_at in rows
    ]


def get_session_messages(session_id: int, limit: int = 30) -> List[Dict]:
    if not db_enabled():
        return []
    query = """
    SELECT role, content, created_at
    FROM messages
    WHERE session_id = %s
    ORDER BY id ASC
    LIMIT %s;
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (session_id, limit))
            rows = cur.fetchall()

    return [
        {"role": role, "content": content, "created_at": created_at.isoformat()}
        for role, content, created_at in rows
    ]


def memory_note_exists(
    category: str,
    note: str,
    project_tag: Optional[str] = None,
) -> bool:
    """Check if an identical note already exists.

    When project_tag is given, scopes the check to that project only —
    otherwise an identical note in another project would falsely block a save.
    When project_tag is None, falls back to the legacy unscoped behavior.
    """
    if not db_enabled():
        return False
    if project_tag is not None:
        query = """
        SELECT 1
        FROM memory_notes
        WHERE category = %s AND note = %s AND project_tag = %s
        LIMIT 1;
        """
        params = (category, note, project_tag)
    else:
        query = """
        SELECT 1
        FROM memory_notes
        WHERE category = %s AND note = %s AND project_tag IS NULL
        LIMIT 1;
        """
        params = (category, note)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            row = cur.fetchone()
    return row is not None


def get_relevant_memory_notes(
    query_text: Optional[str] = None,
    limit: int = 5,
    categories: Optional[List[str]] = None,
    project_tag: Optional[str] = None,
) -> List[Dict]:
    """Retrieve memory notes, scoped to project_tag when provided.

    Built dynamically so project_tag is honored in EVERY branch (previously
    only one of three branches filtered by it, leaking memory across projects).
    """
    if not db_enabled():
        return []
    where_clauses: List[str] = []
    params: List[Any] = []

    use_embedding = bool(query_text)
    if use_embedding:
        emb_str = str(_embed_text(query_text))
        where_clauses.append("embedding IS NOT NULL")

    if categories:
        where_clauses.append("category = ANY(%s)")
        params.append(categories)

    if project_tag is not None:
        where_clauses.append("project_tag = %s")
        params.append(project_tag)

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    if use_embedding:
        sql = f"""
        SELECT category, note, importance, created_at,
               1 - (embedding <=> %s::vector) AS similarity
        FROM memory_notes
        {where_sql}
        ORDER BY embedding <=> %s::vector
        LIMIT %s;
        """
        # Order: similarity-select, where-params..., order-by, limit
        full_params = [emb_str, *params, emb_str, limit]
    else:
        sql = f"""
        SELECT category, note, importance, created_at
        FROM memory_notes
        {where_sql}
        ORDER BY importance DESC, id DESC
        LIMIT %s;
        """
        full_params = [*params, limit]

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, full_params)
            rows = cur.fetchall()

    if use_embedding:
        return [
            {
                "category": cat,
                "note": note,
                "importance": imp,
                "created_at": ca.isoformat(),
                "similarity": round(float(similarity), 4),
            }
            for cat, note, imp, ca, similarity in rows
        ]

    return [
        {"category": cat, "note": note, "importance": imp, "created_at": ca.isoformat()}
        for cat, note, imp, ca in rows
    ]


def get_memory_by_category(
    category: str,
    limit: int = 10,
    project_tag: Optional[str] = None,
) -> List[Dict]:
    if not db_enabled():
        return []
    if project_tag is not None:
        sql = """
        SELECT category, note, importance, created_at
        FROM memory_notes
        WHERE category = %s AND project_tag = %s
        ORDER BY importance DESC, id DESC
        LIMIT %s;
        """
        params = (category, project_tag, limit)
    else:
        sql = """
        SELECT category, note, importance, created_at
        FROM memory_notes
        WHERE category = %s
        ORDER BY importance DESC, id DESC
        LIMIT %s;
        """
        params = (category, limit)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    return [
        {"category": cat, "note": note, "importance": imp, "created_at": ca.isoformat()}
        for cat, note, imp, ca in rows
    ]


def get_tooling_context(query_text: str, limit: int = 5, project_tag: Optional[str] = None) -> List[Dict]:
    categories = [
        "tooling_command",
        "repo_convention",
        "project_context",
        "bug_pattern",
        "successful_fix",
    ]
    return get_relevant_memory_notes(
        query_text=query_text,
        limit=limit,
        categories=categories,
        project_tag=project_tag,
    )


def format_memory(notes: List[Dict]) -> str:
    if not notes:
        return ""

    lines = []
    for n in notes:
        base = f"- [{n['category']}] {n['note']}"
        if "importance" in n:
            base += f" (importance={n['importance']})"
        if "similarity" in n:
            base += f" (sim={n['similarity']})"
        lines.append(base)

    return "Memory Context:\n" + "\n".join(lines)


def create_task_run(
    session_id: int,
    audience: str,
    mode: str,
    intent: str,
    complexity: str,
    input_mode: str,
    language: str,
    user_input: str,
) -> int:
    if not db_enabled():
        return 0
    query = """
    INSERT INTO task_runs (
        session_id, audience, mode, intent, complexity, input_mode, language, user_input
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING id;
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (session_id, audience, mode, intent, complexity, input_mode, language, user_input),
            )
            task_run_id = cur.fetchone()[0]
        conn.commit()
    return task_run_id


def finish_task_run(
    task_run_id: int,
    status: str,
    confidence: Optional[float] = None,
    needs_escalation: bool = False,
):
    if not db_enabled():
        return
    query = """
    UPDATE task_runs
    SET status = %s,
        confidence = %s,
        needs_escalation = %s,
        finished_at = CURRENT_TIMESTAMP
    WHERE id = %s;
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (status, confidence, needs_escalation, task_run_id))
        conn.commit()


def save_patch_attempt(
    task_run_id: Optional[int],
    session_id: Optional[int],
    target_file: Optional[str],
    matched_by: Optional[str],
    phase: str,
    risk_level: Optional[str],
    risk_score: Optional[int],
    diff: Optional[str],
    validation_ok: Optional[bool],
    validation_output: Optional[str],
    rollback_performed: bool,
    failure_category: Optional[str],
    failure_reason: Optional[str],
    project_tag: Optional[str],
    patch_payload: Optional[dict],
):
    if not db_enabled():
        return
    query = """
    INSERT INTO patch_attempts (
        task_run_id, session_id, target_file, matched_by, phase,
        risk_level, risk_score, diff, validation_ok, validation_output,
        rollback_performed, failure_category, failure_reason, project_tag, patch_payload
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb);
    """
    payload_json = json.dumps(patch_payload, ensure_ascii=False) if patch_payload else None
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (
                    task_run_id, session_id, target_file, matched_by, phase,
                    risk_level, risk_score, diff, validation_ok, validation_output,
                    rollback_performed, failure_category, failure_reason, project_tag, payload_json
                ),
            )
        conn.commit()


def upsert_tooling_profile(
    project_tag: str,
    language: Optional[str] = None,
    test_command: Optional[str] = None,
    build_command: Optional[str] = None,
    lint_command: Optional[str] = None,
    format_command: Optional[str] = None,
    run_command: Optional[str] = None,
    notes: Optional[str] = None,
):
    if not db_enabled():
        return
    query = """
    INSERT INTO tooling_profiles (
        project_tag, language, test_command, build_command, lint_command,
        format_command, run_command, notes, updated_at
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
    ON CONFLICT (project_tag, language)
    DO UPDATE SET
        test_command = COALESCE(EXCLUDED.test_command, tooling_profiles.test_command),
        build_command = COALESCE(EXCLUDED.build_command, tooling_profiles.build_command),
        lint_command = COALESCE(EXCLUDED.lint_command, tooling_profiles.lint_command),
        format_command = COALESCE(EXCLUDED.format_command, tooling_profiles.format_command),
        run_command = COALESCE(EXCLUDED.run_command, tooling_profiles.run_command),
        notes = COALESCE(EXCLUDED.notes, tooling_profiles.notes),
        updated_at = CURRENT_TIMESTAMP;
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (
                    project_tag, language, test_command, build_command,
                    lint_command, format_command, run_command, notes
                ),
            )
        conn.commit()


def save_code_unit(
    file_path: str,
    kind: str,
    name: str,
    content: str,
    embedding: List[float],
    project_tag: Optional[str] = None,
):
    if not db_enabled():
        return
    query = """
    INSERT INTO code_units (file_path, kind, name, content, embedding, project_tag)
    VALUES (%s, %s, %s, %s, %s::vector, %s);
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (file_path, kind, name, content, str(embedding), project_tag))
        conn.commit()


def get_tooling_profile(project_tag: str, language: str) -> dict:
    if not db_enabled():
        return {}
    query = """
    SELECT test_command, build_command, lint_command, format_command, run_command, notes
    FROM tooling_profiles
    WHERE project_tag = %s AND language = %s
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (project_tag, language))
            row = cur.fetchone()
            if row:
                return {
                    "test_command": row[0],
                    "build_command": row[1],
                    "lint_command": row[2],
                    "format_command": row[3],
                    "run_command": row[4],
                    "notes": row[5]
                }
    return {}


def clear_code_units_for_file(file_path: str, project_tag: Optional[str] = None):
    """Delete code units for a file. Scoped by project_tag when given so we
    don't delete a same-named file's symbols belonging to a different project."""
    if not db_enabled():
        return
    if project_tag is not None:
        query = "DELETE FROM code_units WHERE file_path = %s AND project_tag = %s;"
        params = (file_path, project_tag)
    else:
        query = "DELETE FROM code_units WHERE file_path = %s;"
        params = (file_path,)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
        conn.commit()


def search_code_units(
    query_text: str,
    limit: int = 5,
    project_tag: Optional[str] = None,
) -> List[Dict]:
    if not db_enabled():
        return []
    embedding = _embed_text(query_text)
    emb_str = str(embedding)

    if project_tag is not None:
        sql = """
        SELECT file_path, kind, name, content,
               1 - (embedding <=> %s::vector) AS similarity
        FROM code_units
        WHERE project_tag = %s
        ORDER BY embedding <=> %s::vector
        LIMIT %s;
        """
        params = (emb_str, project_tag, emb_str, limit)
    else:
        sql = """
        SELECT file_path, kind, name, content,
               1 - (embedding <=> %s::vector) AS similarity
        FROM code_units
        ORDER BY embedding <=> %s::vector
        LIMIT %s;
        """
        params = (emb_str, emb_str, limit)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    return [
        {
            "file_path": fp,
            "kind": kind,
            "name": name,
            "content": content,
            "similarity": float(sim),
        }
        for fp, kind, name, content, sim in rows
    ]
def get_engineering_memory(query_text: str, limit: int = 5, project_tag: str = None) -> List[Dict]:
    """
    Returns engineering-focused memory in the shape expected by main.py:
    [{"memory_type": "...", "value": "...", "importance": 3, ...}, ...]
    """
    categories = [
        "bug_pattern",
        "successful_fix",
        "tooling_command",
        "repo_convention",
        "project_context",
    ]

    notes = get_relevant_memory_notes(
        query_text=query_text,
        limit=limit,
        categories=categories,
        project_tag=project_tag,
    )

    return [
        {
            "memory_type": item["category"],
            "value": item["note"],
            "importance": item.get("importance"),
            "similarity": item.get("similarity"),
            "created_at": item.get("created_at"),
        }
        for item in notes
    ]

def save_dependency(
    source_file: str,
    dependency_type: str,
    target_file: Optional[str] = None,
    source_symbol: Optional[str] = None,
    target_symbol: Optional[str] = None,
    project_tag: Optional[str] = None,
):
    if not db_enabled():
        return
    query = """
    INSERT INTO code_dependencies
        (source_file, target_file, source_symbol, target_symbol, dependency_type, project_tag)
    VALUES (%s, %s, %s, %s, %s, %s);
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (source_file, target_file, source_symbol, target_symbol, dependency_type, project_tag),
            )
        conn.commit()


def clear_dependencies_for_file(source_file: str, project_tag: Optional[str] = None):
    """Delete dependency edges for a file. Scoped by project_tag when given so
    we don't delete the same file path belonging to a different project."""
    if not db_enabled():
        return
    if project_tag is not None:
        query = "DELETE FROM code_dependencies WHERE source_file = %s AND project_tag = %s;"
        params = (source_file, project_tag)
    else:
        query = "DELETE FROM code_dependencies WHERE source_file = %s;"
        params = (source_file,)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
        conn.commit()


def search_dependencies(
    query_text: str,
    limit: int = 10,
    project_tag: Optional[str] = None,
) -> List[Dict]:
    if not db_enabled():
        return []
    embedding = _embed_text(query_text)
    emb_str = str(embedding)

    if project_tag is not None:
        sql = """
        WITH top_files AS (
            SELECT file_path
            FROM code_units
            WHERE project_tag = %s
            ORDER BY embedding <=> %s::vector
            LIMIT 3
        )

        SELECT source_file, target_file, source_symbol, target_symbol, dependency_type
        FROM code_dependencies
        WHERE project_tag = %s
            AND (
                source_file IN (SELECT file_path FROM top_files)
                OR target_file IN (SELECT file_path FROM top_files)
            )
        LIMIT %s;
        """
        params = (project_tag, emb_str, project_tag, limit)
    else:
        sql = """
        WITH top_files AS (
            SELECT file_path
            FROM code_units
            ORDER BY embedding <=> %s::vector
            LIMIT 3
        )
        SELECT source_file, target_file, source_symbol, target_symbol, dependency_type
        FROM code_dependencies
        WHERE source_file IN (SELECT file_path FROM top_files)
            OR target_file IN (SELECT file_path FROM top_files)
        LIMIT %s;
        """
        params = (emb_str, limit)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    return [
        {
            "source_file": sf,
            "target_file": tf,
            "source_symbol": ss,
            "target_symbol": ts,
            "dependency_type": dt,
        }
        for sf, tf, ss, ts, dt in rows
    ]