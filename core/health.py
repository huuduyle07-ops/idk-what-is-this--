"""Health checks for the Settings/Health workspace panel (Phase 5 Slice 2).

All checks must be cheap and non-blocking. No model loads, no large network
traffic. Use short timeouts on anything that touches the network/DB.

Each check returns a dict shaped like:
    {"name": "Display label", "status": "ok"|"available"|"off"|"missing"|"error", "detail": "..."}

Status semantics:
    ok        — configured AND verified responding (e.g., DB connect succeeded)
    available — configured but not actively probed (e.g., API keys present)
    off       — explicitly disabled by env var (e.g., DB_ENABLED=false)
    missing   — would be useful but not configured (env var unset/placeholder)
    error     — configured but failed when probed
"""
from __future__ import annotations

import importlib.util
import os
import shutil
from typing import Literal

Status = Literal["ok", "available", "off", "missing", "error"]


def _check(name: str, status: Status, detail: str = "") -> dict:
    return {"name": name, "status": status, "detail": detail}


def _is_placeholder(value: str) -> bool:
    """Treat .env.example placeholders like 'your_google_api_key_here' as unset."""
    if not value:
        return True
    v = value.strip().lower()
    return v.startswith("your_") or v == "changeme" or v == "todo"


# ---------------------------------------------------------------------------
# API key checks
# ---------------------------------------------------------------------------
def check_google_api() -> dict:
    key = os.getenv("GOOGLE_API_KEY", "")
    if _is_placeholder(key):
        return _check("Google API", "missing", "GOOGLE_API_KEY not set")
    return _check("Google API", "available", f"key present (len={len(key.strip())})")


def check_optional_api(env_name: str, label: str) -> dict:
    key = os.getenv(env_name, "")
    if _is_placeholder(key):
        return _check(label, "off", f"{env_name} not set (optional)")
    return _check(label, "available", "key present")


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
def check_db() -> dict:
    if os.getenv("DB_ENABLED", "false").strip().lower() != "true":
        return _check("Database (Postgres)", "off", "DB_ENABLED=false")

    db_url = (
        os.getenv("DATABASE_URL")
        or os.getenv("DATABASE_URL_LOCAL")
        or ""
    ).strip()
    if not db_url:
        return _check("Database (Postgres)", "missing", "DATABASE_URL not set")

    try:
        import psycopg
    except ImportError:
        return _check("Database (Postgres)", "error", "psycopg not installed")

    try:
        with psycopg.connect(db_url, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return _check("Database (Postgres)", "ok", "connect+SELECT 1 OK")
    except Exception as e:
        return _check("Database (Postgres)", "error", str(e)[:160])


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------
def check_embeddings() -> dict:
    enabled_vars = [
        "RETRIEVER_USE_EMBEDDINGS",
        "INDEX_USE_EMBEDDINGS",
        "ROUTER_USE_EMBEDDINGS",
    ]
    enabled = [v for v in enabled_vars if os.getenv(v, "false").strip().lower() == "true"]
    if not enabled:
        return _check("Embeddings", "off", "all *_USE_EMBEDDINGS=false")

    if importlib.util.find_spec("sentence_transformers") is None:
        return _check("Embeddings", "error", "sentence_transformers not installed")

    model = os.getenv("EMBEDDING_MODEL", "")
    if _is_placeholder(model):
        return _check("Embeddings", "missing", "EMBEDDING_MODEL not set")

    return _check(
        "Embeddings",
        "available",
        f"enabled by: {','.join(enabled)} · model={model.strip()}",
    )


# ---------------------------------------------------------------------------
# Ollama (local critic)
# ---------------------------------------------------------------------------
def check_ollama() -> dict:
    if os.getenv("OLLAMA_ENABLED", "false").strip().lower() != "true":
        return _check("Ollama (local critic)", "off", "OLLAMA_ENABLED=false")

    host = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")

    try:
        import requests
    except ImportError:
        return _check("Ollama (local critic)", "error", "requests not installed")

    try:
        r = requests.get(host + "/api/tags", timeout=2)
        if r.status_code != 200:
            return _check("Ollama (local critic)", "error", f"{host} returned {r.status_code}")
        try:
            tags = r.json().get("models") or []
        except Exception:
            tags = []
        names = ", ".join(m.get("name", "?") for m in tags[:3])
        extra = f" (+{len(tags) - 3} more)" if len(tags) > 3 else ""
        return _check(
            "Ollama (local critic)",
            "ok",
            f"{host} · models: {names or '(none pulled)'}{extra}",
        )
    except Exception as e:
        return _check("Ollama (local critic)", "error", f"{host}: {str(e)[:120]}")


# ---------------------------------------------------------------------------
# Tree-sitter
# ---------------------------------------------------------------------------
def check_tree_sitter() -> dict:
    if importlib.util.find_spec("tree_sitter_language_pack") is None:
        return _check("Tree-sitter", "missing", "tree_sitter_language_pack not installed")
    try:
        from tree_sitter_language_pack import get_parser
        parser = get_parser("python")
        parser.parse(b"x = 1")
        return _check("Tree-sitter", "ok", "python parser loaded + parsed sample")
    except Exception as e:
        return _check("Tree-sitter", "error", str(e)[:160])


# ---------------------------------------------------------------------------
# Toolchain binaries
# ---------------------------------------------------------------------------
def check_toolchain(tool: str, label: str | None = None) -> dict:
    label = label or tool
    path = shutil.which(tool)
    if path:
        return _check(label, "ok", path)
    return _check(label, "missing", f"`{tool}` not on PATH")


# ---------------------------------------------------------------------------
# Top-level aggregator
# ---------------------------------------------------------------------------
def get_system_health() -> dict:
    """Run all health checks and return a structured report.

    Worst-case duration: ~5s (DB connect_timeout=3s + Ollama timeout=2s,
    sequential). Most checks complete in microseconds.
    """
    checks: list[dict] = [
        check_google_api(),
        check_optional_api("DEEPSEEK_API_KEY", "DeepSeek API"),
        check_optional_api("ANTHROPIC_API_KEY", "Claude (Anthropic) API"),
        check_optional_api("OPENAI_API_KEY", "OpenAI API"),
        check_optional_api("OPENROUTER_API_KEY", "OpenRouter API"),
        check_optional_api("HF_TOKEN", "HuggingFace token"),
        check_db(),
        check_embeddings(),
        check_ollama(),
        check_tree_sitter(),
        check_toolchain("python"),
        check_toolchain("node"),
        check_toolchain("go"),
        check_toolchain("cargo", "Rust (cargo)"),
        check_toolchain("g++"),
    ]
    summary = {
        "ok": sum(1 for c in checks if c["status"] == "ok"),
        "available": sum(1 for c in checks if c["status"] == "available"),
        "off": sum(1 for c in checks if c["status"] == "off"),
        "missing": sum(1 for c in checks if c["status"] == "missing"),
        "error": sum(1 for c in checks if c["status"] == "error"),
    }
    return {"checks": checks, "summary": summary}
