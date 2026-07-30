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
import subprocess
from typing import Literal

from core.credential_redaction import redact_credentials

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
        detail = redact_credentials(
            e,
            known_secrets=(db_url,),
        )
        return _check(
            "Database (Postgres)",
            "error",
            detail[:160],
        )


# ---------------------------------------------------------------------------
# Embeddings — Phase 9.1b pluggable provider awareness
# ---------------------------------------------------------------------------
def check_embeddings() -> dict:
    """Surface the configured embedding provider, its model, dimension, and
    whether the provider is actually ready to call.

    Three signals matter to the user:
      * the legacy ``*_USE_EMBEDDINGS`` flags — kept for backward compat,
      * ``EMBEDDING_PROVIDER`` (off / local_minilm / gemini),
      * whether the chosen provider's dependency / credential is present.
    """
    enabled_vars = [
        "RETRIEVER_USE_EMBEDDINGS",
        "INDEX_USE_EMBEDDINGS",
        "ROUTER_USE_EMBEDDINGS",
    ]
    enabled = [
        v for v in enabled_vars
        if os.getenv(v, "false").strip().lower() == "true"
    ]
    raw_provider = (os.getenv("EMBEDDING_PROVIDER") or "").strip().lower()

    # Lazy import so the health endpoint stays usable even if the new module
    # ever fails to import.
    try:
        from core import embedding_providers as ep
    except Exception as exc:
        return _check(
            "Embeddings",
            "error",
            f"embedding_providers import failed: {type(exc).__name__}: {exc}",
        )

    # Normalize EMBEDDING_PROVIDER. Unknown values are surfaced as errors so
    # the panel doesn't silently swallow a typo.
    try:
        provider_id = ep._normalize_provider_id(raw_provider)
    except ep.EmbeddingProviderError as exc:
        return _check("Embeddings", "error", str(exc))

    if provider_id == ep.OFF_PROVIDER_ID:
        legacy_note = (
            f" (legacy *_USE_EMBEDDINGS still on: {','.join(enabled)})"
            if enabled else ""
        )
        return _check(
            "Embeddings",
            "off",
            f"EMBEDDING_PROVIDER=off — vector retrieval disabled{legacy_note}",
        )

    if provider_id == ep.LOCAL_MINILM_PROVIDER_ID:
        provider = ep.LocalMiniLMProvider()
        if importlib.util.find_spec("sentence_transformers") is None:
            return _check(
                "Embeddings",
                "error",
                "EMBEDDING_PROVIDER=local_minilm but `sentence_transformers` "
                "is not installed (run `pip install -r requirements_embeddings.txt`)",
            )
        return _check(
            "Embeddings",
            "available",
            f"provider={provider.provider_id} · model={provider.model} · "
            f"dimension={provider.dimension}",
        )

    if provider_id == ep.GEMINI_PROVIDER_ID:
        provider = ep.GeminiProvider()
        api_key = (
            os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or ""
        ).strip()
        if _is_placeholder(api_key):
            return _check(
                "Embeddings",
                "missing",
                "EMBEDDING_PROVIDER=gemini but GOOGLE_API_KEY is not set",
            )
        if importlib.util.find_spec("google.genai") is None:
            return _check(
                "Embeddings",
                "error",
                "EMBEDDING_PROVIDER=gemini but `google-genai` is not installed",
            )
        return _check(
            "Embeddings",
            "available",
            f"provider={provider.provider_id} · model={provider.model} · "
            f"dimension={provider.dimension} · GOOGLE_API_KEY present "
            f"(len={len(api_key)})",
        )

    # Shouldn't happen — _normalize_provider_id already validated.
    return _check(
        "Embeddings",
        "error",
        f"unhandled provider id {provider_id!r}",
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
        # language-pack >=1.8 ships a native Parser whose parse() is str-only;
        # bytes go through parse_bytes(). Older releases wrap tree_sitter.Parser
        # whose parse() takes bytes directly.
        if hasattr(parser, "parse_bytes"):
            parser.parse_bytes(b"x = 1")
        else:
            parser.parse(b"x = 1")
        return _check("Tree-sitter", "ok", "python parser loaded + parsed sample")
    except Exception as e:
        return _check("Tree-sitter", "error", str(e)[:160])


# ---------------------------------------------------------------------------
# Docker sandbox backend (Phase 7.3a)
# ---------------------------------------------------------------------------
def _docker_image_pulled(docker: str, image: str, timeout_sec: int = 2) -> bool:
    """Return True if ``image`` is present in the local Docker image store.

    ``docker image inspect`` is local-only — it never touches the network, so
    the probe stays cheap even when many images are listed.
    """
    try:
        inspected = subprocess.run(
            [docker, "image", "inspect", image],
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
    except Exception:
        return False
    return inspected.returncode == 0


def check_docker_sandbox() -> dict:
    """Probe the ``docker_ubuntu`` sandbox backend.

    Three outcomes:
      - ``missing``  → ``docker`` CLI not on PATH; backend unavailable.
      - ``error``    → CLI present but ``docker info`` failed (engine off, no
                       permission, daemon socket missing, etc.).
      - ``ok``       → engine responding; detail enumerates which
                       per-language sandbox images are pulled locally so the
                       user can see whether the next run triggers a fetch.

    The probe is intentionally cheap (≤ ~6 s worst case): one ``docker info``
    call plus one local ``docker image inspect`` per language image. No
    containers are started, no images are pulled.
    """
    label = "Docker sandbox (docker_ubuntu backend)"
    docker = shutil.which("docker")
    if not docker:
        return _check(
            label,
            "missing",
            "`docker` not on PATH (docker_ubuntu sandbox backend unavailable; temp_clone still works)",
        )

    try:
        info = subprocess.run(
            [docker, "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return _check(label, "error", "`docker info` timed out (engine not responding)")
    except Exception as e:
        return _check(label, "error", f"`docker info` failed: {str(e)[:120]}")

    if info.returncode != 0:
        stderr_first = (info.stderr or "").strip().splitlines()
        msg = stderr_first[0] if stderr_first else "non-zero exit"
        return _check(label, "error", f"docker engine unreachable: {msg[:120]}")

    server_version = (info.stdout or "").strip() or "unknown"

    # Walk the per-language image inventory. Fail-soft on import so a missing
    # ``core.sandbox_runner`` doesn't break the health endpoint.
    try:
        from core.sandbox_runner import (
            DEFAULT_DOCKER_IMAGE,
            SANDBOX_LANGUAGE_IMAGES,
        )
    except Exception:
        DEFAULT_DOCKER_IMAGE = "python:3.12-slim"
        SANDBOX_LANGUAGE_IMAGES = (("python", DEFAULT_DOCKER_IMAGE),)

    pulled: list[str] = []
    missing: list[str] = []
    for tool_label, image in SANDBOX_LANGUAGE_IMAGES:
        if _docker_image_pulled(docker, image):
            pulled.append(f"{tool_label} ({image})")
        else:
            missing.append(f"{tool_label} ({image})")

    detail_parts = [f"engine v{server_version}"]
    if pulled:
        detail_parts.append("pulled: " + ", ".join(pulled))
    if missing:
        detail_parts.append("not pulled: " + ", ".join(missing))
    # Highlight the default image so users see at a glance whether the most
    # common path (``python -m pytest``) needs a fetch on first run.
    default_ready = _docker_image_pulled(docker, DEFAULT_DOCKER_IMAGE)
    if not default_ready:
        detail_parts.append(
            f"default {DEFAULT_DOCKER_IMAGE} not pulled (first run will fetch)"
        )

    return _check(label, "ok", " · ".join(detail_parts))


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

    Worst-case duration: ~11s (DB connect_timeout=3s + Ollama timeout=2s +
    Docker info+inspect ≤6s, sequential). Most checks complete in
    microseconds.
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
        check_docker_sandbox(),
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
