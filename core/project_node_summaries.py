from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MODE = "project_evolution"
SCHEMA_VERSION = "node_summaries_v1"
DEFAULT_MAX_NODES = 40

NOISE_PREFIXES = (
    ".agent/",
    ".claude/",
    ".codex/",
    ".pytest_cache/",
    ".tmp/",
    "benchmarks/cases/",
    "docs/superpowers/",
)

IMPORTANT_SOURCE_PREFIXES = (
    "core/",
    "graph/",
    "reasoning/",
    "retrieval/",
    "tests/",
    "docs/",
    "web/",
    "scripts/",
)

IMPORTANT_KEYWORDS = (
    "provider",
    "retrieval",
    "indexer",
    "graph",
    "weights",
    "project_map",
    "embedding",
    "config",
    "settings",
    "migration",
    "integration",
)

IGNORED_PARTS = {
    ".git",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "target",
    "venv",
}


def build_project_node_summaries_record(
    repo_path: str,
    *,
    source_map_path: str | None = None,
    max_nodes: int = DEFAULT_MAX_NODES,
) -> dict[str, Any]:
    repo_root = Path(repo_path).expanduser().resolve()
    source_path = _resolve_source_map_path(repo_root, source_map_path)
    source_map = _load_source_map(source_path)

    if source_map["status"] != "ok":
        return _build_error_record(repo_root, source_path, source_map["message"], max_nodes)

    map_record = source_map["record"]
    summaries = _build_summaries(repo_root, map_record, max_nodes=max_nodes)

    return {
        "generated_at": _utc_now_iso(),
        "repo_path": str(repo_root),
        "mode": MODE,
        "schema_version": SCHEMA_VERSION,
        "status": "ok",
        "source_map_path": str(source_path),
        "source_map_generated_at": map_record.get("generated_at", ""),
        "summary_count": len(summaries),
        "max_nodes": max_nodes,
        "selection_policy": (
            "Selected important nodes only: dependency files, config files, entrypoints, "
            "provider/retrieval/indexer/graph surfaces, integration tests, and key docs. "
            "Noise paths and generated/build folders are excluded."
        ),
        "summaries": summaries,
        "source_components_used": [
            "project_map_v2.json",
            "project_map_v2.full_file_read_candidates",
            "project_map_v2.integration_boundaries",
            "project_map_v2.external_services_or_env_vars",
        ],
        "limitations": [
            "Heuristic only; no model/API calls and no semantic or LLM summarization.",
            "Summaries are capped and intentionally omit noisy fixtures, generated artifacts, and real .env values.",
            "This artifact does not change graph ranking, CONTROL behavior, Debug Mode, patching, or validation.",
        ],
    }


def render_project_node_summaries_markdown(record: dict[str, Any]) -> str:
    lines = [
        "# Heuristic Project Node Summaries",
        "",
        "## Summary",
        f"- Repo path: `{record['repo_path']}`",
        f"- Mode: `{record['mode']}`",
        f"- Status: `{record['status']}`",
        f"- Generated at: `{record['generated_at']}`",
        f"- Source map path: `{record['source_map_path']}`",
        f"- Nodes summarized: {record['summary_count']}",
        "",
    ]

    if record["status"] != "ok":
        lines.extend(
            [
                "## Error",
                f"- {record['error']['message']}",
                "",
            ]
        )
        return "\n".join(lines)

    lines.extend(
        [
            "## Selection Policy",
            f"- {record['selection_policy']}",
            "",
            "## Node Summaries",
        ]
    )
    for item in record["summaries"]:
        lines.extend(
            [
                f"### `{item['path']}`",
                f"- Node id: `{item['node_id']}`",
                f"- Node type: `{item['node_type']}`",
                f"- Category: `{item['category']}`",
                f"- Confidence: {item['confidence']:.2f}",
                f"- Summary source: `{item['summary_source']}`",
                f"- Summary: {item['summary']}",
                "- Responsibilities:",
                *[f"  - {value}" for value in item["responsibilities"]],
                f"- Migration relevance: {item['migration_relevance']}",
                "- Risk notes:",
                *[f"  - {value}" for value in item["risk_notes"]],
                "- Evidence:",
                *[f"  - {value}" for value in item["evidence"]],
                "",
            ]
        )

    lines.extend(
        [
            "## Limitations",
            *[f"- {value}" for value in record["limitations"]],
            "",
        ]
    )
    return "\n".join(lines)


def write_project_node_summaries_artifacts(
    repo_path: str,
    *,
    source_map_path: str | None = None,
    output_root: str | None = None,
    max_nodes: int = DEFAULT_MAX_NODES,
) -> dict[str, Any]:
    repo_root = Path(repo_path).expanduser().resolve()
    record = build_project_node_summaries_record(
        str(repo_root),
        source_map_path=source_map_path,
        max_nodes=max_nodes,
    )
    markdown = render_project_node_summaries_markdown(record)
    artifact_root = _resolve_output_root(repo_root, output_root)
    json_path = artifact_root / "node_summaries.json"
    md_path = artifact_root / "node_summaries.md"
    json_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    return {
        "record": record,
        "json_path": str(json_path),
        "md_path": str(md_path),
    }


def _build_summaries(repo_root: Path, map_record: dict[str, Any], *, max_nodes: int) -> list[dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}

    def add_candidate(rel_path: str, category: str, score: int, evidence: str) -> None:
        normalized = rel_path.replace("\\", "/")
        if not _should_include_path(normalized):
            return
        if not (repo_root / normalized).exists():
            return
        effective_score = max(score, _path_priority(normalized))
        row = candidates.setdefault(
            normalized,
            {
                "path": normalized,
                "category": category,
                "score": effective_score,
                "evidence": [],
            },
        )
        if effective_score > row["score"]:
            row["score"] = effective_score
            row["category"] = category
        row["evidence"].append(evidence)

    for rel_path in map_record.get("dependency_files", []):
        add_candidate(rel_path, "dependency", 100, "Selected from Project Map v2 dependency_files.")
    for rel_path in map_record.get("config_files", []):
        add_candidate(rel_path, "config", 98, "Selected from Project Map v2 config_files.")
    for rel_path in map_record.get("entrypoints", []):
        add_candidate(rel_path, "entrypoint", 95, "Selected from Project Map v2 entrypoints.")
    for rel_path in map_record.get("documentation_files", []):
        if _is_key_doc(rel_path):
            add_candidate(rel_path, "doc", 82, "Selected as a key documentation file for migration planning.")
    for item in map_record.get("full_file_read_candidates", []):
        rel_path = item.get("path", "")
        category = _normalize_candidate_category(item.get("category", "file"), rel_path)
        reason = item.get("reason", "Selected from Project Map v2 full-file-read candidates.")
        add_candidate(rel_path, category, 90, f"Full-file-read candidate: {reason}")
    for item in map_record.get("integration_boundaries", []):
        rel_path = item.get("path", "")
        category = _boundary_category(rel_path, item.get("category", "file"))
        reason = item.get("reason", "Detected integration boundary.")
        add_candidate(rel_path, category, 88, f"Integration boundary: {reason}")

    for rel_path in _scan_repo_for_important_files(repo_root):
        add_candidate(
            rel_path,
            _classify_node_type(rel_path),
            _path_priority(rel_path),
            "Selected by heuristic repo scan for provider/retrieval/indexer/graph/test/doc importance.",
        )

    ranked = sorted(
        candidates.values(),
        key=lambda item: (-item["score"], item["category"], item["path"]),
    )

    env_names_by_source = _env_names_by_source(map_record)
    source_map_generated_at = map_record.get("generated_at", "")
    summaries: list[dict[str, Any]] = []
    for item in ranked[:max_nodes]:
        summaries.append(
            _build_summary_row(
                item["path"],
                item["category"],
                item["evidence"],
                source_map_generated_at=source_map_generated_at,
                env_names=env_names_by_source.get(item["path"], []),
            )
        )
    return summaries


def _scan_repo_for_important_files(repo_root: Path) -> list[str]:
    selected: list[str] = []
    for current_root, dirnames, filenames in os.walk(repo_root, topdown=True):
        current = Path(current_root)
        rel_dir = Path(".") if current == repo_root else current.relative_to(repo_root)
        kept_dirs: list[str] = []
        for name in dirnames:
            lowered = name.lower()
            if lowered in IGNORED_PARTS:
                continue
            kept_dirs.append(name)
        dirnames[:] = kept_dirs

        for filename in filenames:
            rel_path = (rel_dir / filename).as_posix() if rel_dir != Path(".") else filename
            if not _should_include_path(rel_path):
                continue
            lowered = rel_path.lower()
            if _is_integration_test(rel_path) or _is_key_doc(rel_path):
                selected.append(rel_path)
                continue
            if rel_path.startswith(IMPORTANT_SOURCE_PREFIXES) and any(keyword in lowered for keyword in IMPORTANT_KEYWORDS):
                selected.append(rel_path)
    return sorted(dict.fromkeys(selected))


def _build_summary_row(
    rel_path: str,
    category: str,
    evidence_lines: list[str],
    *,
    source_map_generated_at: str,
    env_names: list[str],
) -> dict[str, Any]:
    node_type = _classify_node_type(rel_path, category)
    summary = _summary_for(rel_path, node_type)
    responsibilities = _responsibilities_for(rel_path, node_type)
    migration_relevance = _migration_relevance_for(rel_path, node_type)
    risk_notes = _risk_notes_for(rel_path, node_type)
    evidence = list(dict.fromkeys(evidence_lines))

    if env_names:
        evidence.append(
            "Environment variable names referenced in the source map: "
            + ", ".join(env_names[:6])
            + ("." if len(env_names) <= 6 else ", ...")
        )
    evidence.append(f"Path-based heuristic classified this node as `{node_type}` in category `{category}`.")

    return {
        "node_id": f"file:{rel_path}",
        "path": rel_path,
        "node_type": node_type,
        "summary": summary,
        "responsibilities": responsibilities,
        "migration_relevance": migration_relevance,
        "risk_notes": risk_notes,
        "evidence": evidence,
        "summary_source": "heuristic",
        "confidence": _confidence_for(node_type, rel_path),
        "category": category,
        "source_map_generated_at": source_map_generated_at,
    }


def _summary_for(rel_path: str, node_type: str) -> str:
    lowered = rel_path.lower()
    name = Path(rel_path).name.lower()
    if node_type == "dependency":
        if name in {"requirements.txt", "pyproject.toml"}:
            return "Dependency surface for the Python runtime and migration compatibility."
        if name == "package.json":
            return "Dependency surface for the JavaScript/TypeScript toolchain and runtime compatibility."
        return "Dependency manifest that influences runtime, package resolution, or migration compatibility."
    if node_type == "config":
        if name in {".env.example", "config.py", "settings.py"}:
            return "Configuration and environment surface; migration risk centers on provider IDs, flags, and secrets wiring."
        return "Configuration file that shapes environment, deployment, or runtime behavior."
    if "indexer" in lowered:
        return "Indexing and project-map surface; migration risk centers on retrieval and search output shape."
    if "weights" in lowered:
        return "Graph ranking and weighting surface; migration risk centers on evidence ordering and hotspot interpretation."
    if node_type == "entrypoint":
        return "Entrypoint surface that bootstraps runtime wiring and reveals migration-sensitive startup flow."
    if node_type == "provider":
        return "Provider or integration surface that concentrates cross-system wiring, retrieval, or graph behavior."
    if node_type == "test":
        return "Validation surface for migration behavior and expected compatibility checks."
    if node_type == "doc":
        return "Documentation surface that captures architecture, migration intent, or operator guidance."
    return "Important project file selected for heuristic migration review."


def _responsibilities_for(rel_path: str, node_type: str) -> list[str]:
    if node_type == "dependency":
        return [
            "Declares package or runtime compatibility boundaries.",
            "Signals which ecosystems must be upgraded together.",
        ]
    if node_type == "config":
        return [
            "Defines environment or deployment-facing behavior.",
            "Carries provider, database, or feature-flag coupling that migrations must preserve.",
        ]
    if node_type == "entrypoint":
        return [
            "Bootstraps the application or CLI execution path.",
            "Reveals startup dependencies and high-level wiring.",
        ]
    if node_type == "provider":
        return [
            "Implements or coordinates provider, retrieval, indexing, or graph-related boundaries.",
            "Exposes abstractions that broad migrations are likely to touch.",
        ]
    if node_type == "test":
        return [
            "Asserts expected migration-safe behavior.",
            "Provides a regression target for provider or architecture changes.",
        ]
    if node_type == "doc":
        return [
            "Records architecture or migration context for human review.",
            "Documents intent and constraints that code-only scans can miss.",
        ]
    return [
        "Selected as an important project node for evolution planning.",
        "Should be reviewed before broad migration decisions are made.",
    ]


def _migration_relevance_for(rel_path: str, node_type: str) -> str:
    if node_type == "dependency":
        return "High relevance because dependency manifests anchor runtime compatibility and upgrade sequencing."
    if node_type == "config":
        return "High relevance because provider flags, environment contracts, and secret wiring often break first in migrations."
    if node_type == "entrypoint":
        return "High relevance because entrypoints reveal the real startup path and integration wiring."
    if node_type == "provider":
        return "High relevance because provider and graph surfaces often concentrate the code that migrations actually change."
    if node_type == "test":
        return "Medium-to-high relevance because migration success depends on preserving the behavior these tests capture."
    if node_type == "doc":
        return "Medium relevance because docs explain architecture intent and rollout constraints that code alone cannot show."
    return "Selected for targeted review before migration planning."


def _risk_notes_for(rel_path: str, node_type: str) -> list[str]:
    lowered = rel_path.lower()
    notes: list[str] = []
    if node_type == "dependency":
        notes.append("Lockstep upgrades may be required across multiple packages or runtimes.")
    if node_type == "config":
        notes.append("Environment or provider identifiers can drift silently during migrations.")
        notes.append("Secret-backed behavior must be reviewed manually because real .env values are intentionally excluded.")
    if node_type == "entrypoint":
        notes.append("Startup or import wiring can hide the first observable migration breakage.")
    if node_type == "provider":
        notes.append("Provider abstractions may leak assumptions into retrieval, indexing, or graph behavior.")
    if node_type == "test":
        notes.append("Tests may encode legacy behavior that broad migrations are tempted to bypass.")
    if node_type == "doc":
        notes.append("Documentation can lag behind code and should be verified against the current source.")
    if "graph/weights" in lowered:
        notes.append("Behavior changes here could alter evidence ordering even when correctness is unchanged.")
    if "core/indexer" in lowered:
        notes.append("Changes here could shift indexing, retrieval, or project-map shape across the repo.")
    return notes or ["Review manually; this node was selected because it is likely migration-sensitive."]


def _confidence_for(node_type: str, rel_path: str) -> float:
    base = {
        "dependency": 0.9,
        "config": 0.88,
        "entrypoint": 0.86,
        "provider": 0.8,
        "test": 0.76,
        "doc": 0.72,
        "file": 0.65,
        "unknown": 0.55,
    }.get(node_type, 0.55)
    lowered = rel_path.lower()
    if "indexer" in lowered or "weights" in lowered:
        base += 0.04
    return round(min(0.99, max(0.0, base)), 2)


def _classify_node_type(rel_path: str, category: str | None = None) -> str:
    lowered = rel_path.lower()
    name = Path(rel_path).name.lower()
    effective = category or "unknown"
    if effective == "dependency" or name in {"requirements.txt", "pyproject.toml", "package.json", "package-lock.json"}:
        return "dependency"
    if effective == "config" or name in {".env.example", "config.py", "settings.py", "docker-compose.yml", "dockerfile", "pytest.ini"}:
        return "config"
    if effective == "entrypoint" or name in {"main.py", "app.py", "cli.py", "server.py", "index.ts", "main.ts"} or lowered == "web/app.py":
        return "entrypoint"
    if effective == "doc" or lowered.endswith(".md"):
        return "doc"
    if effective == "test" or _is_integration_test(rel_path) or name.startswith("test_"):
        return "test"
    if effective == "provider" or any(keyword in lowered for keyword in ("provider", "retrieval", "indexer", "graph", "embedding", "weights")):
        return "provider"
    if lowered.endswith((".py", ".ts", ".tsx", ".js", ".go", ".rs")):
        return "file"
    return "unknown"


def _resolve_source_map_path(repo_root: Path, source_map_path: str | None) -> Path:
    if source_map_path is None:
        return repo_root / ".agent" / "project_evolution" / "project_map_v2.json"
    candidate = Path(source_map_path).expanduser()
    return candidate if candidate.is_absolute() else repo_root / candidate


def _load_source_map(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "status": "error",
            "message": f"source Project Map v2 artifact does not exist: {path}",
        }
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "status": "error",
            "message": f"source Project Map v2 artifact is invalid JSON: {path} ({exc})",
        }
    except OSError as exc:
        return {
            "status": "error",
            "message": f"source Project Map v2 artifact could not be read: {path} ({exc})",
        }
    if not isinstance(record, dict) or record.get("schema_version") != "project_map_v2/1":
        return {
            "status": "error",
            "message": f"source Project Map v2 artifact is missing or has an unexpected schema: {path}",
        }
    return {"status": "ok", "record": record}


def _build_error_record(repo_root: Path, source_path: Path, message: str, max_nodes: int) -> dict[str, Any]:
    return {
        "generated_at": _utc_now_iso(),
        "repo_path": str(repo_root),
        "mode": MODE,
        "schema_version": SCHEMA_VERSION,
        "status": "error",
        "source_map_path": str(source_path),
        "source_map_generated_at": "",
        "summary_count": 0,
        "max_nodes": max_nodes,
        "selection_policy": "No summaries produced because the source Project Map v2 artifact could not be loaded.",
        "summaries": [],
        "error": {
            "code": "source_map_unavailable",
            "message": message,
        },
        "source_components_used": ["project_map_v2.json"],
        "limitations": [
            "Node summaries depend on a readable Project Map v2 artifact.",
            "No fallback model or runtime analysis is attempted when the source map is missing.",
        ],
    }


def _should_include_path(rel_path: str) -> bool:
    normalized = rel_path.replace("\\", "/")
    lowered = normalized.lower()
    if normalized.startswith(NOISE_PREFIXES):
        return False
    if any(part in IGNORED_PARTS for part in Path(normalized).parts):
        return False
    if "/buggy_repo/" in lowered or lowered.startswith("buggy_repo/"):
        return False
    if Path(normalized).name == ".env":
        return False
    return True


def _is_key_doc(rel_path: str) -> bool:
    lowered = rel_path.lower()
    if lowered in {"readme.md", "changelog.md"}:
        return True
    if lowered in {
        "docs/project_evolution_mode.md",
        "docs/project_map_upgrade_plan.md",
        "docs/architecture.md",
    }:
        return True
    return lowered.startswith("docs/") and ("architecture" in lowered or "project_" in lowered or "roadmap" in lowered)


def _is_integration_test(rel_path: str) -> bool:
    lowered = rel_path.lower()
    name = Path(rel_path).name.lower()
    return (
        lowered.startswith("tests/")
        and ("integration" in lowered or "migration" in lowered or any(keyword in name for keyword in ("provider", "indexer", "graph", "project_map", "evolution")))
    )


def _path_priority(rel_path: str) -> int:
    lowered = rel_path.lower()
    score = 70
    if lowered in {"requirements.txt", "pyproject.toml", "package.json", ".env.example", "config.py"}:
        score += 30
    if lowered in {
        "config.py",
        "settings.py",
        "core/indexer.py",
        "core/repo_librarian.py",
        "core/project_map_v2.py",
        "graph/project_map.py",
        "graph/weights.py",
        "docs/project_evolution_mode.md",
        "docs/project_map_upgrade_plan.md",
        "tests/integration/test_provider_migration.py",
    }:
        score += 28
    if lowered.startswith(("core/", "graph/", "retrieval/", "tests/", "docs/")):
        score += 12
    if "indexer" in lowered or "weights" in lowered or "provider" in lowered:
        score += 10
    if _is_integration_test(rel_path):
        score += 8
    if _is_key_doc(rel_path):
        score += 6
    return score


def _normalize_candidate_category(category: str, rel_path: str) -> str:
    lowered = category.lower()
    if lowered in {"dependency", "config", "entrypoint", "doc", "test", "provider"}:
        return lowered
    return _classify_node_type(rel_path)


def _boundary_category(rel_path: str, boundary_category: str) -> str:
    lowered = boundary_category.lower()
    if lowered in {"provider", "retrieval", "graph", "client", "storage", "auth", "api"}:
        return "provider"
    if lowered == "config":
        return "config"
    return _classify_node_type(rel_path)


def _env_names_by_source(map_record: dict[str, Any]) -> dict[str, list[str]]:
    names: dict[str, list[str]] = {}
    for item in map_record.get("external_services_or_env_vars", []):
        source = item.get("source")
        name = item.get("name")
        if not source or not name or name == ".env":
            continue
        names.setdefault(source, [])
        if name not in names[source]:
            names[source].append(name)
    return names


def _resolve_output_root(repo_root: Path, output_root: str | None) -> Path:
    if output_root is None:
        resolved = (repo_root / ".agent" / "project_evolution").resolve()
    else:
        candidate = Path(output_root).expanduser()
        resolved = candidate.resolve() if candidate.is_absolute() else (repo_root / candidate).resolve()
    resolved.relative_to(repo_root)
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
