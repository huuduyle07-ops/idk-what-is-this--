from __future__ import annotations

import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from fnmatch import fnmatch
from pathlib import Path
from typing import Any


MODE = "project_evolution"
SCHEMA_VERSION = "project_map_v2/1"
DEFAULT_MAX_FULL_FILE_CANDIDATES = 30

DEPENDENCY_FILE_NAMES = {
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "poetry.lock",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "go.mod",
    "cargo.toml",
    "pom.xml",
    "build.gradle",
    "composer.json",
    "gemfile",
}

CONFIG_FILE_NAMES = {
    ".env.example",
    "docker-compose.yml",
    "docker-compose.yaml",
    "dockerfile",
    "config.py",
    "settings.py",
    "tsconfig.json",
    "pytest.ini",
    "tox.ini",
}

CONFIG_FILE_PATTERNS = (
    "vite.config.*",
    "webpack.config.*",
    "eslint.*",
)

ENTRYPOINT_PATHS = {
    "main.py",
    "app.py",
    "server.py",
    "index.ts",
    "index.js",
    "main.ts",
    "main.go",
    "src/main.rs",
    "web/app.py",
    "cli.py",
}

DOCUMENTATION_FILE_NAMES = {
    "readme.md",
    "changelog.md",
}

TEST_DIR_NAMES = {
    "tests",
    "test",
    "__tests__",
    "spec",
}

IGNORED_DIR_NAMES = {
    ".agent",
    ".git",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "target",
    "venv",
    ".pytest_tmp",
}

IGNORED_DIR_PREFIXES = (
    ".fresh_tmp",
    ".fresh_tmp_",
)

LANGUAGE_BY_EXTENSION = {
    ".py": "python",
    ".rs": "rust",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".cc": "cpp",
    ".hpp": "cpp",
    ".hxx": "cpp",
    ".cs": "csharp",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "css",
    ".sass": "css",
    ".json": "json",
    ".md": "markdown",
    ".txt": "text",
    ".toml": "toml",
    ".yml": "yaml",
    ".yaml": "yaml",
}

BOUNDARY_KEYWORDS = {
    "db": "database",
    "database": "database",
    "api": "api",
    "web": "web",
    "worker": "worker",
    "queue": "queue",
    "embedding": "embedding",
    "retrieval": "retrieval",
    "graph": "graph",
    "auth": "auth",
    "config": "config",
    "settings": "config",
    "storage": "storage",
    "provider": "provider",
    "client": "client",
}

ENV_ASSIGNMENT_RE = re.compile(r"^\s*([A-Z][A-Z0-9_]{1,})\s*=")
ENV_REFERENCE_PATTERNS = (
    re.compile(r"""os\.getenv\(\s*['"]([A-Z][A-Z0-9_]{1,})['"]"""),
    re.compile(r"""process\.env\.([A-Z][A-Z0-9_]{1,})\b"""),
    re.compile(r"""process\.env\[['"]([A-Z][A-Z0-9_]{1,})['"]\]"""),
    re.compile(r"""\$\{([A-Z][A-Z0-9_]{1,})\}"""),
)


def build_project_map_v2_record(
    repo_path: str,
    max_full_file_candidates: int = DEFAULT_MAX_FULL_FILE_CANDIDATES,
) -> dict[str, Any]:
    repo_root = Path(repo_path).expanduser().resolve()
    if not repo_root.exists() or not repo_root.is_dir():
        raise ValueError(f"repo_path is not a directory: {repo_root}")

    snapshot = _scan_repo(repo_root)
    files = snapshot["files"]
    dependency_files = _select_matching_files(files, _is_dependency_file)
    config_files = _select_matching_files(files, _is_config_file)
    entrypoints = _select_matching_files(files, _is_entrypoint_file)
    test_roots = _detect_test_roots(files)
    documentation_files = _detect_documentation_files(files)
    languages = _detect_languages(files)
    architecture_layers = _detect_architecture_layers(files)
    integration_boundaries = _detect_integration_boundaries(files)
    external_services_or_env_vars = _detect_external_services_or_env_vars(
        repo_root,
        files,
        config_files,
    )

    record = {
        "generated_at": _utc_now_iso(),
        "repo_path": str(repo_root),
        "mode": MODE,
        "schema_version": SCHEMA_VERSION,
        "languages": languages,
        "dependency_files": dependency_files,
        "config_files": config_files,
        "entrypoints": entrypoints,
        "test_roots": test_roots,
        "documentation_files": documentation_files,
        "ignored_generated_or_build_paths": snapshot["ignored_paths"],
        "likely_architecture_layers": architecture_layers,
        "integration_boundaries": integration_boundaries,
        "external_services_or_env_vars": external_services_or_env_vars,
        "full_file_read_candidates": _build_full_file_read_candidates(
            files=files,
            dependency_files=dependency_files,
            config_files=config_files,
            entrypoints=entrypoints,
            documentation_files=documentation_files,
            repo_root=repo_root,
            max_candidates=max_full_file_candidates,
        ),
        "migration_risk_notes": _build_migration_risk_notes(
            languages=languages,
            dependency_files=dependency_files,
            entrypoints=entrypoints,
            test_roots=test_roots,
            ignored_paths=snapshot["ignored_paths"],
            integration_boundaries=integration_boundaries,
            external_services_or_env_vars=external_services_or_env_vars,
        ),
        "source_components_used": _source_components_used(),
        "limitations": _limitations(max_full_file_candidates),
    }
    return record


def render_project_map_v2_markdown(record: dict[str, Any]) -> str:
    summary_lines = [
        f"- Repo path: `{record['repo_path']}`",
        f"- Mode: `{record['mode']}`",
        f"- Schema version: `{record['schema_version']}`",
        f"- Generated at: `{record['generated_at']}`",
        f"- Languages detected: {len(record['languages'])}",
        f"- Full-file-read candidates: {len(record['full_file_read_candidates'])}",
    ]

    lines = [
        "# Project Map v2",
        "",
        "## Summary",
        *summary_lines,
        "",
        "## Languages",
        *_render_language_lines(record["languages"]),
        "",
        "## Dependency Files",
        *_render_string_list(record["dependency_files"]),
        "",
        "## Config Files",
        *_render_string_list(record["config_files"]),
        "",
        "## Entrypoints",
        *_render_string_list(record["entrypoints"]),
        "",
        "## Test Roots",
        *_render_string_list(record["test_roots"]),
        "",
        "## Documentation Files",
        *_render_string_list(record["documentation_files"]),
        "",
        "## Ignored Generated / Build Paths",
        *_render_string_list(record["ignored_generated_or_build_paths"]),
        "",
        "## Likely Architecture Layers",
        *_render_architecture_layers(record["likely_architecture_layers"]),
        "",
        "## Integration Boundaries",
        *_render_integration_boundaries(record["integration_boundaries"]),
        "",
        "## External Services / Env Vars",
        *_render_external_services(record["external_services_or_env_vars"]),
        "",
        "## Full-File Read Candidates",
        *_render_full_file_read_candidates(record["full_file_read_candidates"]),
        "",
        "## Migration Risk Notes",
        *_render_string_list(record["migration_risk_notes"]),
        "",
        "## Source Components Used",
        *_render_source_components(record["source_components_used"]),
        "",
        "## Limitations",
        *_render_string_list(record["limitations"]),
        "",
    ]
    return "\n".join(lines)


def write_project_map_v2_artifacts(
    repo_path: str,
    output_root: str | None = None,
    max_full_file_candidates: int = DEFAULT_MAX_FULL_FILE_CANDIDATES,
) -> dict[str, Any]:
    repo_root = Path(repo_path).expanduser().resolve()
    record = build_project_map_v2_record(
        str(repo_root),
        max_full_file_candidates=max_full_file_candidates,
    )
    markdown = render_project_map_v2_markdown(record)
    artifact_root = _resolve_output_root(repo_root, output_root)
    json_path = artifact_root / "project_map_v2.json"
    md_path = artifact_root / "project_map_v2.md"
    json_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    return {
        "record": record,
        "json_path": str(json_path),
        "md_path": str(md_path),
    }


def _scan_repo(repo_root: Path) -> dict[str, Any]:
    files: list[str] = []
    ignored_paths: set[str] = set()

    for current_root, dirnames, filenames in os.walk(repo_root, topdown=True):
        current = Path(current_root)
        rel_dir = Path(".")
        if current != repo_root:
            rel_dir = current.relative_to(repo_root)

        kept_dirs: list[str] = []
        for name in dirnames:
            rel_path = (rel_dir / name).as_posix() if rel_dir != Path(".") else name
            if _should_ignore_directory(name):
                ignored_paths.add(rel_path)
                if name == ".agent" and (current / name / "benchmarks").exists():
                    ignored_paths.add(f"{rel_path}/benchmarks")
                continue
            kept_dirs.append(name)
        dirnames[:] = kept_dirs

        for filename in filenames:
            rel_path = (rel_dir / filename).as_posix() if rel_dir != Path(".") else filename
            files.append(rel_path)

    return {
        "files": sorted(files),
        "ignored_paths": sorted(ignored_paths),
    }


def _should_ignore_directory(name: str) -> bool:
    lowered = name.lower()
    if lowered in IGNORED_DIR_NAMES:
        return True
    return any(lowered.startswith(prefix) for prefix in IGNORED_DIR_PREFIXES)


def _select_matching_files(files: list[str], predicate) -> list[str]:
    return [rel_path for rel_path in files if predicate(rel_path)]


def _is_dependency_file(rel_path: str) -> bool:
    return Path(rel_path).name.lower() in DEPENDENCY_FILE_NAMES


def _is_config_file(rel_path: str) -> bool:
    name = Path(rel_path).name.lower()
    if name in CONFIG_FILE_NAMES:
        return True
    return any(fnmatch(name, pattern) for pattern in CONFIG_FILE_PATTERNS)


def _is_entrypoint_file(rel_path: str) -> bool:
    rel_lower = rel_path.lower()
    name = Path(rel_path).name.lower()
    return rel_lower in ENTRYPOINT_PATHS or name in ENTRYPOINT_PATHS


def _detect_test_roots(files: list[str]) -> list[str]:
    roots: set[str] = set()
    for rel_path in files:
        path = Path(rel_path)
        parts = path.parts
        for idx, part in enumerate(parts):
            if part.lower() in TEST_DIR_NAMES:
                roots.add("/".join(parts[: idx + 1]))
                break
        else:
            name = path.name.lower()
            if name.endswith("_test.go") or (name.startswith("test_") and path.suffix.lower() == ".py"):
                parent = path.parent.as_posix()
                roots.add(parent if parent and parent != "." else rel_path)
    return sorted(roots)


def _detect_documentation_files(files: list[str]) -> list[str]:
    docs: list[str] = []
    for rel_path in files:
        path = Path(rel_path)
        name = path.name.lower()
        rel_lower = rel_path.lower()
        if name in DOCUMENTATION_FILE_NAMES:
            docs.append(rel_path)
        elif rel_lower.startswith("docs/"):
            docs.append(rel_path)
        elif "architecture" in name and path.suffix.lower() == ".md":
            docs.append(rel_path)
    return sorted(dict.fromkeys(docs))


def _detect_languages(files: list[str]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    for rel_path in files:
        language = LANGUAGE_BY_EXTENSION.get(Path(rel_path).suffix.lower())
        if language:
            counts[language] += 1
    rows = [
        {"language": language, "count": count}
        for language, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    return rows


def _detect_architecture_layers(files: list[str]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    root_file_count = 0
    for rel_path in files:
        path = Path(rel_path)
        if len(path.parts) == 1:
            root_file_count += 1
            continue
        counts[path.parts[0]] += 1

    layers = [{"path": "root", "responsibility": _folder_responsibility("root"), "file_count": root_file_count}]
    for folder, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        layers.append(
            {
                "path": folder,
                "responsibility": _folder_responsibility(folder),
                "file_count": count,
            }
        )
    return layers[:15]


def _folder_responsibility(folder: str) -> str:
    lowered = folder.lower()
    if lowered == "root":
        return "Top-level orchestration, configuration, and entrypoints."
    if any(token in lowered for token in ("test", "tests", "spec", "__tests__")):
        return "Test and regression coverage."
    if "doc" in lowered:
        return "Project documentation and migration notes."
    if any(token in lowered for token in ("script", "scripts", "tool", "tools")):
        return "Developer tooling and automation."
    if any(token in lowered for token in ("config", "settings")):
        return "Configuration and environment loading."
    if any(token in lowered for token in ("api", "routes", "handler", "controller")):
        return "API and request-handling surface."
    if any(token in lowered for token in ("worker", "queue")):
        return "Background jobs and asynchronous processing."
    if any(token in lowered for token in ("storage", "client", "provider")):
        return "Integration adapters and external service boundaries."
    if any(token in lowered for token in ("retrieval", "embedding", "graph")):
        return "Retrieval, graph, or semantic-analysis infrastructure."
    if any(token in lowered for token in ("web", "ui", "view", "component")):
        return "Presentation and web application surface."
    if any(token in lowered for token in ("src", "core")):
        return "Primary source implementation."
    return "Project submodule."


def _detect_integration_boundaries(files: list[str]) -> list[dict[str, str]]:
    boundaries: list[dict[str, str]] = []
    seen_paths: set[str] = set()
    for rel_path in files:
        lowered = rel_path.lower()
        for keyword, category in BOUNDARY_KEYWORDS.items():
            if keyword in lowered and rel_path not in seen_paths:
                boundaries.append(
                    {
                        "path": rel_path,
                        "category": category,
                        "reason": f"Path includes '{keyword}', which often marks a service or integration boundary.",
                    }
                )
                seen_paths.add(rel_path)
                break
    return boundaries[:25]


def _detect_external_services_or_env_vars(
    repo_root: Path,
    files: list[str],
    config_files: list[str],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for rel_path in files:
        if Path(rel_path).name == ".env":
            _add_external_row(
                rows,
                seen,
                name=".env",
                source=rel_path,
                kind="env_file_present",
                inferred_service="manual_review",
                note="exists but values were intentionally not read",
            )

    for rel_path in config_files:
        name = Path(rel_path).name
        abs_path = repo_root / rel_path
        if not abs_path.exists():
            continue
        if name == ".env.example":
            for line in abs_path.read_text(encoding="utf-8", errors="replace").splitlines():
                match = ENV_ASSIGNMENT_RE.match(line)
                if not match:
                    continue
                env_name = match.group(1)
                _add_external_row(
                    rows,
                    seen,
                    name=env_name,
                    source=rel_path,
                    kind="env_var",
                    inferred_service=_infer_service_from_env_name(env_name),
                )
            continue

        text = abs_path.read_text(encoding="utf-8", errors="replace")
        for pattern in ENV_REFERENCE_PATTERNS:
            for env_name in pattern.findall(text):
                _add_external_row(
                    rows,
                    seen,
                    name=env_name,
                    source=rel_path,
                    kind="env_var",
                    inferred_service=_infer_service_from_env_name(env_name),
                )

    return rows


def _add_external_row(
    rows: list[dict[str, str]],
    seen: set[tuple[str, str]],
    *,
    name: str,
    source: str,
    kind: str,
    inferred_service: str,
    note: str = "",
) -> None:
    key = (name, source)
    if key in seen:
        return
    row = {
        "name": name,
        "source": source,
        "kind": kind,
        "inferred_service": inferred_service,
    }
    if note:
        row["note"] = note
    rows.append(row)
    seen.add(key)


def _infer_service_from_env_name(env_name: str) -> str:
    lowered = env_name.lower()
    if "openai" in lowered:
        return "openai"
    if "database" in lowered or lowered.endswith("_url"):
        return "database"
    if "auth" in lowered:
        return "auth"
    if "s3" in lowered or "storage" in lowered:
        return "storage"
    if "api" in lowered:
        return "api"
    return "configuration"


def _build_full_file_read_candidates(
    *,
    files: list[str],
    dependency_files: list[str],
    config_files: list[str],
    entrypoints: list[str],
    documentation_files: list[str],
    repo_root: Path,
    max_candidates: int,
) -> list[dict[str, str]]:
    candidates: dict[str, dict[str, Any]] = {}

    def add_candidate(rel_path: str, category: str, confidence: str, reason: str, priority: int) -> None:
        if rel_path not in files:
            return
        existing = candidates.get(rel_path)
        row = {
            "path": rel_path,
            "category": category,
            "confidence": confidence,
            "reason": reason,
            "_priority": priority,
        }
        if existing is None or priority > existing["_priority"]:
            candidates[rel_path] = row

    for rel_path in dependency_files:
        add_candidate(
            rel_path,
            "dependency",
            "high",
            "Dependency manifest anchors package, runtime, and lockfile migration planning.",
            100,
        )
    for rel_path in config_files:
        add_candidate(
            rel_path,
            "config",
            "high",
            "Configuration file defines environment, tooling, or deployment behavior that migrations must preserve.",
            95,
        )
    for rel_path in entrypoints:
        add_candidate(
            rel_path,
            "entrypoint",
            "high",
            "Entrypoint reveals execution flow, startup wiring, and primary integration surfaces.",
            92,
        )
    for rel_path in documentation_files:
        add_candidate(
            rel_path,
            "docs",
            "medium",
            "Documentation captures architectural intent, rollout notes, or migration constraints.",
            80,
        )

    for rel_path in files:
        lowered = rel_path.lower()
        if lowered.endswith((".py", ".ts", ".tsx", ".js", ".go", ".rs")):
            if any(token in lowered for token in ("provider", "client", "embedding", "retrieval")):
                add_candidate(
                    rel_path,
                    "provider",
                    "high",
                    "Provider or retrieval adapter likely concentrates cross-system migration logic.",
                    90,
                )
            elif any(token in lowered for token in ("config", "settings", "auth", "storage")):
                add_candidate(
                    rel_path,
                    "integration",
                    "medium",
                    "Integration-facing source file may hide environment coupling or external service assumptions.",
                    78,
                )
            elif Path(rel_path).name.lower().startswith("test_") or Path(rel_path).suffix.lower() == ".go" and Path(rel_path).name.lower().endswith("_test.go"):
                add_candidate(
                    rel_path,
                    "test",
                    "medium",
                    "Targeted test coverage can expose expected migration-safe behavior.",
                    74,
                )

    ranked = sorted(
        candidates.values(),
        key=lambda item: (-item["_priority"], item["category"], item["path"]),
    )

    result: list[dict[str, str]] = []
    for item in ranked[:max_candidates]:
        candidate = dict(item)
        candidate.pop("_priority", None)
        (repo_root / candidate["path"]).resolve().relative_to(repo_root)
        result.append(candidate)
    return result


def _build_migration_risk_notes(
    *,
    languages: list[dict[str, Any]],
    dependency_files: list[str],
    entrypoints: list[str],
    test_roots: list[str],
    ignored_paths: list[str],
    integration_boundaries: list[dict[str, str]],
    external_services_or_env_vars: list[dict[str, str]],
) -> list[str]:
    notes: list[str] = []
    dependency_names = {Path(rel_path).name.lower() for rel_path in dependency_files}

    if len(languages) > 1:
        notes.append("Polyglot source layout increases migration coordination across language-specific build and runtime conventions.")
    if {"package.json", "pyproject.toml"} <= dependency_names or {"package.json", "requirements.txt"} <= dependency_names:
        notes.append("Multiple dependency ecosystems were detected, so upgrade order and lockfile drift need explicit coordination.")
    if len(entrypoints) > 1:
        notes.append("Multiple entrypoints suggest more than one runtime surface, which raises rollout and smoke-test complexity.")
    if not test_roots:
        notes.append("No test roots were detected, so migration safety may rely on manual verification.")
    if ignored_paths:
        notes.append("Generated/build folders were intentionally ignored, so any generated code contract should be rechecked separately.")
    if integration_boundaries:
        notes.append("Provider, retrieval, auth, storage, or API boundaries were detected and may concentrate migration-sensitive wiring.")
    if any(item["name"] == ".env" for item in external_services_or_env_vars):
        notes.append("A real .env file exists but was not read; secret-backed configuration still needs manual review.")

    if not notes:
        notes.append("No major migration risks were inferred from the static structure scan alone.")
    return notes


def _source_components_used() -> list[dict[str, str]]:
    return [
        {
            "component": "core.repo_librarian",
            "role": "Existing inventory/walker contract referenced for Evolution Mode repo scanning heuristics.",
        },
        {
            "component": "core.indexer",
            "role": "Existing Tree-sitter/indexing layer referenced as the upgrade baseline for richer future maps.",
        },
        {
            "component": "graph.project_map",
            "role": "Existing project-map structure and folder-responsibility conventions mirrored by this richer artifact.",
        },
        {
            "component": "graph.builder",
            "role": "Existing graph builder remains the deeper relationship layer that Evolution Mode can consult later.",
        },
        {
            "component": "graph.weights",
            "role": "Existing hotspot ranking remains the graph weighting reference for critical-file follow-up work.",
        },
        {
            "component": "core.semantic_graph_pipeline",
            "role": "Existing semantic graph pipeline remains the graph-context export path for future richer evolution reads.",
        },
        {
            "component": "reasoning.deep_project_understand",
            "role": "Existing deep-understand workflow remains an adjacent planning aid after the map chooses files to read.",
        },
    ]


def _limitations(max_full_file_candidates: int) -> list[str]:
    return [
        "Read-only static scan only; no model/API calls, no patch generation, and no validation or benchmark execution.",
        "Real .env files are detected but never read for values; only .env.example and config references contribute env-name hints.",
        "Generated/build folders are intentionally ignored to keep the map focused on human-maintained source and docs.",
        f"Full-file-read candidates are heuristic and capped at {max_full_file_candidates} by default.",
    ]


def _resolve_output_root(repo_root: Path, output_root: str | None) -> Path:
    if output_root is None:
        resolved = (repo_root / ".agent" / "project_evolution").resolve()
    else:
        candidate = Path(output_root).expanduser()
        resolved = candidate.resolve() if candidate.is_absolute() else (repo_root / candidate).resolve()
    resolved.relative_to(repo_root)
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _render_language_lines(languages: list[dict[str, Any]]) -> list[str]:
    if not languages:
        return ["- None detected"]
    return [f"- `{item['language']}` ({item['count']} files)" for item in languages]


def _render_string_list(values: list[str]) -> list[str]:
    if not values:
        return ["- None detected"]
    return [f"- `{value}`" for value in values]


def _render_architecture_layers(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return ["- None detected"]
    return [
        f"- `{row['path']}` ({row['file_count']} files): {row['responsibility']}"
        for row in rows
    ]


def _render_integration_boundaries(rows: list[dict[str, str]]) -> list[str]:
    if not rows:
        return ["- None detected"]
    return [
        f"- `{row['path']}` [{row['category']}]: {row['reason']}"
        for row in rows
    ]


def _render_external_services(rows: list[dict[str, str]]) -> list[str]:
    if not rows:
        return ["- None detected"]
    result = []
    for row in rows:
        note = f" ({row['note']})" if row.get("note") else ""
        result.append(
            f"- `{row['name']}` from `{row['source']}` [{row['kind']}, {row['inferred_service']}]"
            f"{note}"
        )
    return result


def _render_full_file_read_candidates(rows: list[dict[str, str]]) -> list[str]:
    if not rows:
        return ["- None selected"]
    return [
        f"- `{row['path']}` [{row['category']}, {row['confidence']}]: {row['reason']}"
        for row in rows
    ]


def _render_source_components(rows: list[dict[str, str]]) -> list[str]:
    return [f"- `{row['component']}`: {row['role']}" for row in rows]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
