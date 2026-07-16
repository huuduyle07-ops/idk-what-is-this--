from __future__ import annotations

import json, os
from collections import Counter
from pathlib import Path
from typing import Any
from core.repo_ignore import RepoIgnorePolicy
from config import LANGUAGE_MAP, SUPPORTED_EXTENSIONS, get_agent_dir


# ---- infra-file gating --------------------------------------------------
# Infra files (Dockerfiles, dep manifests, devcontainer configs) are noisy
# for normal code-retrieval queries — they bloat embeddings and surface in
# unrelated results. We skip them by default and only let them through
# when the caller's query clearly mentions an infra concern.

INFRA_FILES = {
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    ".env.example",
    "requirements.txt",
    "pyproject.toml",
}

INFRA_QUERY_TERMS = {
    "docker", "dockerfile", "compose", "container", "devcontainer",
    "env", "environment", "database", "db", "postgres", "postgresql",
    "pgvector", "ollama", "deploy",
    "requirements", "requirements.txt", "dependency", "package", "install",
    "port", "ports", "volume", "volumes",
}


def should_include_infra_file(query: str | None, rel_path: str) -> bool:
    """True if `rel_path` should be read for the given `query`.

    Non-infra files are always allowed. Infra files (see ``INFRA_FILES`` and
    the ``.devcontainer/`` folder) only pass when the query mentions one of
    ``INFRA_QUERY_TERMS``. ``None``/``""`` queries (e.g. indexing time) are
    treated as "no infra need" and skip infra files.
    """
    norm = rel_path.replace("\\", "/")
    name = norm.rsplit("/", 1)[-1]
    if name not in INFRA_FILES and ".devcontainer/" not in norm:
        return True

    q = (query or "").lower()
    return any(term in q for term in INFRA_QUERY_TERMS)


def normalize_repo_path(repo_path: str) -> Path:
    return Path(repo_path).expanduser().resolve()


def _walk_policy_files(root: Path):
    """Yield policy-approved repository files deterministically.

    Ignored directories are removed from ``dir_names`` before ``os.walk``
    descends into them, avoiding unnecessary traversal of temporary,
    generated, cache, dependency, and internal artifact trees.
    """
    policy = RepoIgnorePolicy.load(root)

    for current_root, dir_names, file_names in os.walk(
        root,
        topdown=True,
        followlinks=False,
    ):
        current = Path(current_root)

        try:
            current_rel = current.relative_to(root)
        except ValueError:
            dir_names[:] = []
            continue

        kept_dirs: list[str] = []

        for name in sorted(dir_names):
            rel_dir = current_rel / name

            decision = policy.classify(
                rel_dir,
                is_dir=True,
            )

            if not decision.ignored:
                kept_dirs.append(name)

        # Critical: prevent os.walk from entering ignored directories.
        dir_names[:] = kept_dirs

        for name in sorted(file_names):
            path = current / name

            if not path.is_file():
                continue

            rel = current_rel / name

            decision = policy.classify(
                rel,
                is_dir=False,
            )

            if decision.ignored:
                continue

            yield path, rel


def iter_repo_files(repo_path: str, query: str | None = None):
    """Iterate ``(abs_path, rel_path)`` pairs for files in the repo.

    Repository membership is controlled by RepoIgnorePolicy. Infra files
    remain query-gated as before.
    """
    root = normalize_repo_path(repo_path)

    if not root.exists() or not root.is_dir():
        return

    for path, rel in _walk_policy_files(root):
        rel_str = rel.as_posix()

        if not should_include_infra_file(query, rel_str):
            continue

        yield path, rel


def build_repo_manifest(repo_path: str) -> dict[str, Any]:
    root = normalize_repo_path(repo_path)

    files: list[str] = []
    indexable_files: list[str] = []
    skipped_files: list[str] = []
    language_counts: Counter[str] = Counter()
    extension_counts: Counter[str] = Counter()

    if not root.exists() or not root.is_dir():
        return {
            "ok": False,
            "reason": "repo_path is not a directory",
            "repo_root": str(root),
            "files_total": 0,
            "indexable_count": 0,
            "primary_language": "unknown",
            "languages": {},
            "extensions": {},
            "files": [],
            "indexable_files": [],
            "skipped_files": [],
            "sample_files": [],
            "sample_indexable_files": [],            
            "warnings": [],

        }

    for path, rel in _walk_policy_files(root):
        rel_str = rel.as_posix()

        if not should_include_infra_file(None, rel_str):
            skipped_files.append(rel_str)
            continue

        files.append(rel_str)

        ext = path.suffix.lower()
        extension_counts[ext] += 1

        if ext in SUPPORTED_EXTENSIONS:
            indexable_files.append(rel_str)

            lang = LANGUAGE_MAP.get(ext, "unknown")
            if lang not in {
                "text",
                "document",
                "json",
                "unknown",
            }:
                language_counts[lang] += 1
    
    primary_language = (
        language_counts.most_common(1)[0][0]
        if language_counts
        else "unknown"
    )

    warnings: list[str] = []

    if " " in str(root):
        warnings.append("repo_path contains spaces")

    if not indexable_files:
        warnings.append("repo has 0 indexable files")

    if primary_language == "unknown":
        warnings.append("could not infer primary language from file extensions")

    return {
        "ok": len(indexable_files) > 0,
        "reason": "" if indexable_files else "0 indexable files found",
        "repo_root": str(root),
        "files_total": len(files),
        "indexable_count": len(indexable_files),
        "primary_language": primary_language,
        "languages": dict(language_counts),
        "extensions": dict(extension_counts),
        "files": files,
        "indexable_files": indexable_files,
        "skipped_files": skipped_files[:50],
        "sample_files": files[:20],
        "sample_indexable_files": indexable_files[:20],
        "warnings": warnings,
    }


def inspect_repo_inventory(repo_path: str) -> dict[str, Any]:
    """
    Backward-compatible name for older code.
    """
    manifest = build_repo_manifest(repo_path)

    return {
        "ok": manifest["ok"],
        "reason": manifest["reason"],
        "repo_path": manifest["repo_root"],
        "saved_count": manifest["files_total"],
        "indexable_count": manifest["indexable_count"],
        "sample_files": manifest["sample_files"],
        "sample_indexable_files": manifest["sample_indexable_files"],
        "primary_language": manifest["primary_language"],
        "languages": manifest["languages"],
        "sample_files": manifest.get("sample_files", []),
        "sample_indexable_files": manifest.get("sample_indexable_files", []),
        "warnings": manifest["warnings"],
    }


def write_phantom_limb_report(repo_path: str, findings: list[dict[str, Any]]) -> str:
    out_path = get_agent_dir(str(normalize_repo_path(repo_path))) / "PHANTOM_LIMB.json"
    payload = {
        "version": "phantom_limb_v1",
        "repo_path": str(normalize_repo_path(repo_path)),
        "count": len(findings),
        "findings": findings,
    }
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(out_path)


def load_phantom_limb_report(repo_path: str) -> dict[str, Any]:
    path = get_agent_dir(str(normalize_repo_path(repo_path))) / "PHANTOM_LIMB.json"
    if not path.exists():
        return {
            "version": "phantom_limb_v1",
            "repo_path": str(normalize_repo_path(repo_path)),
            "count": 0,
            "findings": [],
        }

    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        payload = {}

    findings = payload.get("findings") if isinstance(payload, dict) else []
    if not isinstance(findings, list):
        findings = []

    return {
        "version": payload.get("version", "phantom_limb_v1") if isinstance(payload, dict) else "phantom_limb_v1",
        "repo_path": payload.get("repo_path", str(normalize_repo_path(repo_path))) if isinstance(payload, dict) else str(normalize_repo_path(repo_path)),
        "count": len(findings),
        "findings": findings,
    }


def detect_repo_language(repo_path: str) -> str:
    manifest = build_repo_manifest(repo_path)
    return manifest.get("primary_language", "unknown")
