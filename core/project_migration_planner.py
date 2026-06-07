from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MODE = "project_evolution"
SCHEMA_VERSION = "migration_plan_dry_run_v1"
DEFAULT_MAX_FILES = 12
DEFAULT_PROJECT_MAP_NAME = "project_map_v2.json"
DEFAULT_NODE_SUMMARIES_NAME = "node_summaries.json"

PROFILE_KEYWORDS = {
    "embedding_provider": (
        "embedding",
        "embeddings",
        "provider",
        "miniLM",
        "gemini",
        "model2vec",
        "semble",
        "vector",
        "retrieval",
        "search",
    ),
    "web_ui": (
        "web",
        "ui",
        "frontend",
        "route",
        "template",
        "static",
        "component",
    ),
    "database_storage": (
        "database",
        "db",
        "storage",
        "migration",
        "schema",
        "sqlite",
        "postgres",
    ),
    "search_graph": (
        "search",
        "retrieval",
        "indexer",
        "graph",
        "weights",
    ),
}

GOAL_PRIORITY_KEYWORDS = {
    "embedding_provider": (
        "provider",
        "retrieval",
        "indexer",
        "graph",
        "config",
        "settings",
        "test",
        "docs",
        "env",
        "embedding",
    ),
    "web_ui": (
        "web",
        "ui",
        "route",
        "template",
        "static",
        "component",
        "test",
        "docs",
    ),
    "database_storage": (
        "db",
        "database",
        "storage",
        "schema",
        "migration",
        "config",
        "test",
        "docs",
    ),
    "search_graph": (
        "search",
        "retrieval",
        "indexer",
        "graph",
        "weights",
        "provider",
        "test",
        "docs",
    ),
}

EXACT_PATH_BONUS = {
    "embedding_provider": {
        "config.py": 1010,
        "core/indexer.py": 1005,
        "graph/project_map.py": 1550,
        "graph/weights.py": 995,
        "retrieval/provider_router.py": 990,
        "tests/integration/test_provider_migration.py": 985,
        "docs/project_evolution_mode.md": 1500,
        "docs/project_map_upgrade_plan.md": 1450,
        ".env.example": 970,
        "settings.py": 965,
        "requirements.txt": 960,
        "pyproject.toml": 955,
        "package.json": 950,
    },
    "web_ui": {
        "web/app.py": 1000,
        "main.py": 995,
        "app.py": 990,
        "routes.py": 985,
        "templates": 980,
    },
    "database_storage": {
        "database.py": 1000,
        "storage.py": 995,
        "migrations": 990,
        "schema.sql": 985,
    },
    "search_graph": {
        "core/indexer.py": 1000,
        "graph/project_map.py": 995,
        "graph/weights.py": 990,
        "retrieval/provider_router.py": 985,
        "tests/integration/test_provider_migration.py": 980,
        "docs/project_evolution_mode.md": 975,
    },
}

SECTION_ORDER = (
    "Summary",
    "Migration Goal",
    "Source Artifacts",
    "Likely Affected Files",
    "Full Files To Read Before Patching",
    "Impacted Components",
    "Dependency / Config Changes",
    "Test Plan",
    "Docs Plan",
    "Rollout Plan",
    "Rollback Plan",
    "Risks",
    "Open Questions",
    "Human Approval Required",
    "Limitations",
)


def build_migration_plan_dry_run_record(
    repo_path: str,
    goal: str,
    *,
    constraints: list[str] | None = None,
    risk_tolerance: str | None = None,
    max_files: int = DEFAULT_MAX_FILES,
    source_map_path: str | None = None,
    node_summaries_path: str | None = None,
) -> dict[str, Any]:
    repo_root = Path(repo_path).expanduser().resolve()
    goal_text = (goal or "").strip()
    constraints_list = _normalize_constraints(constraints)
    risk_tolerance_text = (risk_tolerance or "").strip()

    if not goal_text:
        return _build_error_record(
            repo_root=repo_root,
            goal_text=goal_text,
            constraints=constraints_list,
            risk_tolerance_text=risk_tolerance_text,
            max_files=max_files,
            code="missing_migration_goal",
            message="migration goal must not be empty",
            source_artifacts=_source_artifact_records(repo_root, source_map_path, node_summaries_path),
        )

    source_map_path_resolved = _resolve_artifact_path(
        repo_root,
        source_map_path,
        DEFAULT_PROJECT_MAP_NAME,
    )
    source_map_load = _load_json_artifact(source_map_path_resolved, required=True)
    if source_map_load["status"] != "ok":
        return _build_error_record(
            repo_root=repo_root,
            goal_text=goal_text,
            constraints=constraints_list,
            risk_tolerance_text=risk_tolerance_text,
            max_files=max_files,
            code="source_map_unavailable",
            message=source_map_load["message"],
            source_artifacts=_source_artifact_records(
                repo_root,
                source_map_path,
                node_summaries_path,
                source_map_status=source_map_load["status"],
            ),
        )

    map_record = source_map_load["record"]

    node_summaries_path_resolved = _resolve_artifact_path(
        repo_root,
        node_summaries_path,
        DEFAULT_NODE_SUMMARIES_NAME,
    )
    node_summaries_load = _load_json_artifact(node_summaries_path_resolved, required=False)

    goal_profile = _classify_goal(goal_text)
    selected = _select_candidate_files(
        repo_root=repo_root,
        goal_text=goal_text,
        goal_profile=goal_profile,
        map_record=map_record,
        node_summaries=node_summaries_load.get("record"),
        max_files=max_files,
    )
    likely_affected_files = selected["likely_affected_files"]
    full_files = selected["full_files_to_read_before_patching"]
    impacted_components = _build_impacted_components(
        goal_profile,
        likely_affected_files,
        full_files,
    )
    dependency_or_config_changes = _build_dependency_or_config_changes(
        goal_profile,
        likely_affected_files,
    )
    test_plan = _build_test_plan(goal_profile, likely_affected_files, full_files)
    docs_plan = _build_docs_plan(goal_profile, impacted_components)
    rollout_plan = _build_rollout_plan(goal_profile, constraints_list, risk_tolerance_text)
    rollback_plan = _build_rollback_plan(goal_profile, likely_affected_files)
    risks = _build_risks(goal_profile, likely_affected_files, node_summaries_load["status"])
    open_questions = _build_open_questions(goal_profile, goal_text)
    limitations = _build_limitations(
        node_summaries_status=node_summaries_load["status"],
        goal_profile=goal_profile,
    )

    source_artifacts = _source_artifact_records(
        repo_root,
        source_map_path,
        node_summaries_path,
        source_map_status="ok",
        source_map_generated_at=map_record.get("generated_at", ""),
        node_summaries_status=node_summaries_load["status"],
        node_summaries_generated_at=node_summaries_load.get("record", {}).get("generated_at", ""),
    )

    return {
        "generated_at": _utc_now_iso(),
        "repo_path": str(repo_root),
        "mode": MODE,
        "schema_version": SCHEMA_VERSION,
        "migration_goal": goal_text,
        "constraints": constraints_list,
        "risk_tolerance": risk_tolerance_text,
        "source_artifacts": source_artifacts,
        "likely_affected_files": likely_affected_files,
        "full_files_to_read_before_patching": full_files,
        "impacted_components": impacted_components,
        "dependency_or_config_changes": dependency_or_config_changes,
        "test_plan": test_plan,
        "docs_plan": docs_plan,
        "rollout_plan": rollout_plan,
        "rollback_plan": rollback_plan,
        "risks": risks,
        "open_questions": open_questions,
        "human_approval_required": True,
        "approval_gate_reason": (
            "This is a dry run only. Human review is required before any patch planning or application."
        ),
        "patch_generation_allowed": False,
        "limitations": limitations,
        "status": "ok",
    }


def render_migration_plan_dry_run_markdown(record: dict[str, Any]) -> str:
    lines = [
        "# Migration Plan Dry Run",
        "",
        "## Summary",
        f"- Repo path: `{record['repo_path']}`",
        f"- Mode: `{record['mode']}`",
        f"- Status: `{record.get('status', 'ok')}`",
        f"- Generated at: `{record['generated_at']}`",
        f"- Patch generation allowed: `{record['patch_generation_allowed']}`",
        f"- Human approval required: `{record['human_approval_required']}`",
        "",
        "## Migration Goal",
        f"- {record.get('migration_goal', '')}",
        "",
        "## Source Artifacts",
        *_render_artifact_lines(record.get("source_artifacts", [])),
        "",
        "## Likely Affected Files",
        *_render_file_lines(record.get("likely_affected_files", [])),
        "",
        "## Full Files To Read Before Patching",
        *_render_file_lines(record.get("full_files_to_read_before_patching", [])),
        "",
        "## Impacted Components",
        *_render_string_list(record.get("impacted_components", [])),
        "",
        "## Dependency / Config Changes",
        *_render_string_list(record.get("dependency_or_config_changes", [])),
        "",
        "## Test Plan",
        *_render_string_list(record.get("test_plan", [])),
        "",
        "## Docs Plan",
        *_render_string_list(record.get("docs_plan", [])),
        "",
        "## Rollout Plan",
        *_render_string_list(record.get("rollout_plan", [])),
        "",
        "## Rollback Plan",
        *_render_string_list(record.get("rollback_plan", [])),
        "",
        "## Risks",
        *_render_string_list(record.get("risks", [])),
        "",
        "## Open Questions",
        *_render_string_list(record.get("open_questions", [])),
        "",
        "## Human Approval Required",
        f"- `{record.get('human_approval_required', False)}`",
        f"- Approval gate reason: {record.get('approval_gate_reason', '')}",
        "",
        "## Limitations",
        *_render_string_list(record.get("limitations", [])),
        "",
    ]
    if record.get("status") != "ok" and record.get("error"):
        lines.extend(
            [
                "## Error",
                f"- {record['error']['message']}",
                "",
            ]
        )
    return "\n".join(lines)


def write_migration_plan_dry_run_artifacts(
    repo_path: str,
    goal: str,
    *,
    constraints: list[str] | None = None,
    risk_tolerance: str | None = None,
    max_files: int = DEFAULT_MAX_FILES,
    output_root: str | None = None,
    source_map_path: str | None = None,
    node_summaries_path: str | None = None,
) -> dict[str, Any]:
    repo_root = Path(repo_path).expanduser().resolve()
    record = build_migration_plan_dry_run_record(
        str(repo_root),
        goal,
        constraints=constraints,
        risk_tolerance=risk_tolerance,
        max_files=max_files,
        source_map_path=source_map_path,
        node_summaries_path=node_summaries_path,
    )
    markdown = render_migration_plan_dry_run_markdown(record)
    artifact_root = _resolve_output_root(repo_root, output_root)
    json_path = artifact_root / "migration_plan_dry_run.json"
    md_path = artifact_root / "migration_plan_dry_run.md"
    json_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    return {
        "record": record,
        "json_path": str(json_path),
        "md_path": str(md_path),
    }


def _select_candidate_files(
    *,
    repo_root: Path,
    goal_text: str,
    goal_profile: str,
    map_record: dict[str, Any],
    node_summaries: dict[str, Any] | None,
    max_files: int,
) -> dict[str, list[dict[str, Any]]]:
    candidates: dict[str, dict[str, Any]] = {}
    goal_keywords = GOAL_PRIORITY_KEYWORDS.get(goal_profile, ())

    def add_candidate(
        rel_path: str,
        *,
        category: str,
        reason: str,
        source: str,
        confidence: float,
        weight: int,
    ) -> None:
        normalized = _normalize_rel_path(rel_path)
        if not normalized:
            return
        if not _is_repo_local_path(repo_root, normalized):
            return
        if not _should_consider_plan_path(normalized):
            return
        if not (repo_root / normalized).exists():
            return
        score = _score_candidate(normalized, goal_profile, goal_keywords, weight)
        row = candidates.setdefault(
            normalized,
            {
                "path": normalized,
                "category": category,
                "reason": reason,
                "confidence": confidence,
                "score": score,
                "sources": [source],
            },
        )
        if score > row["score"]:
            row["score"] = score
        if confidence > row["confidence"]:
            row["confidence"] = confidence
        if source not in row["sources"]:
            row["sources"].append(source)
        if weight >= row.get("weight", -1):
            row["category"] = category
            row["reason"] = reason
            row["weight"] = weight

    for rel_path in map_record.get("dependency_files", []):
        add_candidate(
            rel_path,
            category="dependency",
            reason="Dependency file from Project Map v2.",
            source="project_map_v2.dependency_files",
            confidence=0.92,
            weight=930,
        )
    for rel_path in map_record.get("config_files", []):
        add_candidate(
            rel_path,
            category="config",
            reason="Config file from Project Map v2.",
            source="project_map_v2.config_files",
            confidence=0.95,
            weight=950,
        )
    for rel_path in map_record.get("entrypoints", []):
        add_candidate(
            rel_path,
            category="entrypoint",
            reason="Entrypoint from Project Map v2.",
            source="project_map_v2.entrypoints",
            confidence=0.9,
            weight=900,
        )
    for rel_path in map_record.get("documentation_files", []):
        add_candidate(
            rel_path,
            category="doc",
            reason="Documentation file from Project Map v2.",
            source="project_map_v2.documentation_files",
            confidence=0.8,
            weight=820,
        )
    for item in map_record.get("full_file_read_candidates", []):
        add_candidate(
            item.get("path", ""),
            category=_normalize_category(item.get("category"), item.get("path", "")),
            reason=item.get("reason", "Full-file-read candidate from Project Map v2."),
            source="project_map_v2.full_file_read_candidates",
            confidence=_clamp_confidence(item.get("confidence", 0.75)),
            weight=880,
        )
    for item in map_record.get("integration_boundaries", []):
        add_candidate(
            item.get("path", ""),
            category=_normalize_category(item.get("category"), item.get("path", "")),
            reason=item.get("reason", "Integration boundary from Project Map v2."),
            source="project_map_v2.integration_boundaries",
            confidence=0.78,
            weight=860,
        )

    if node_summaries and isinstance(node_summaries, dict):
        for item in node_summaries.get("summaries", []):
            confidence = _clamp_confidence(item.get("confidence", 0.7))
            if confidence < 0.55:
                continue
            add_candidate(
                item.get("path", ""),
                category=_normalize_category(item.get("category"), item.get("path", "")),
                reason=item.get("summary", "Heuristic node summary."),
                source="node_summaries.summaries",
                confidence=confidence,
                weight=_node_summary_weight(item),
            )

    ranked = sorted(
        candidates.values(),
        key=lambda item: (-item["score"], item["path"]),
    )

    likely_affected_files = [
        _render_candidate(item)
        for item in ranked[: max(1, max_files * 2)]
    ]
    full_files = [
        _render_candidate(item)
        for item in ranked[: max(1, max_files)]
    ]
    return {
        "likely_affected_files": likely_affected_files,
        "full_files_to_read_before_patching": full_files,
    }


def _build_impacted_components(
    goal_profile: str,
    likely_affected_files: list[dict[str, Any]],
    full_files: list[dict[str, Any]],
) -> list[str]:
    components: list[str] = []
    if goal_profile == "embedding_provider":
        components.extend(["provider", "retrieval", "indexer", "graph", "config", "tests", "docs"])
    elif goal_profile == "web_ui":
        components.extend(["web", "routes", "templates", "config", "tests", "docs"])
    elif goal_profile == "database_storage":
        components.extend(["database", "storage", "migrations", "config", "tests", "docs"])
    elif goal_profile == "search_graph":
        components.extend(["search", "retrieval", "indexer", "graph", "tests", "docs"])

    for item in [*likely_affected_files, *full_files]:
        path = item["path"].lower()
        if "config" in path or "settings" in path or ".env" in path:
            components.append("config")
        if "indexer" in path:
            components.append("indexer")
        if "retrieval" in path or "provider" in path:
            components.append("provider")
            components.append("retrieval")
        if "graph" in path or "weights" in path:
            components.append("graph")
        if "/tests/" in path or path.startswith("tests/") or "test_" in Path(path).name:
            components.append("tests")
        if path.startswith("docs/") or path.endswith(".md"):
            components.append("docs")

    return _unique_preserve_order(components)


def _build_dependency_or_config_changes(
    goal_profile: str,
    likely_affected_files: list[dict[str, Any]],
) -> list[str]:
    notes: list[str] = []
    if goal_profile == "embedding_provider":
        notes.extend(
            [
                "Review dependency pins for embedding providers, vector backends, and any model client libraries.",
                "Check configuration and environment contracts for provider IDs, API keys, model names, and fallback routing.",
            ]
        )
    elif goal_profile == "web_ui":
        notes.extend(
            [
                "Review route, template, and static-asset configuration before any migration change.",
                "Check feature flags or environment variables that change user-visible rendering paths.",
            ]
        )
    elif goal_profile == "database_storage":
        notes.extend(
            [
                "Review database connection settings, migration tooling, and storage credentials before changes.",
                "Check schema or DSN configuration for compatibility with the target storage path.",
            ]
        )
    elif goal_profile == "search_graph":
        notes.extend(
            [
                "Review dependency pins for search, indexing, and graph-related packages.",
                "Check configuration for retrieval behavior, evidence ordering, and graph weights.",
            ]
        )

    for item in likely_affected_files:
        path = item["path"].lower()
        if path.endswith((".toml", ".json", ".yaml", ".yml")) or path in {"config.py", "settings.py", ".env.example"}:
            notes.append(f"Verify {item['path']} still matches the updated runtime contract.")
    return _unique_preserve_order(notes)


def _build_test_plan(
    goal_profile: str,
    likely_affected_files: list[dict[str, Any]],
    full_files: list[dict[str, Any]],
) -> list[str]:
    if goal_profile == "embedding_provider":
        plan = [
            "Add or update regression tests for the provider abstraction and migration-safe fallback behavior.",
            "Run focused tests for indexing, retrieval, and graph-related code paths that depend on embedding output shape.",
            "Check that configuration and environment parsing still passes under the new provider contract.",
        ]
    elif goal_profile == "web_ui":
        plan = [
            "Add or update route, rendering, and interaction tests for the changed UI surface.",
            "Run integration tests for startup, templates, and static asset handling.",
            "Verify the migration does not break existing layout or request flow tests.",
        ]
    elif goal_profile == "database_storage":
        plan = [
            "Add or update storage and migration tests that validate schema compatibility.",
            "Run integration tests against the database connection path and config handling.",
            "Verify rollback-oriented tests cover downgrade or fallback behavior.",
        ]
    else:
        plan = [
            "Add or update regression tests for the affected source files and migration boundary behavior.",
            "Run the narrowest useful integration tests that exercise the selected files.",
            "Confirm the existing test coverage still passes around any changed config or entrypoint wiring.",
        ]

    if any(item["path"].startswith("tests/") for item in [*likely_affected_files, *full_files]):
        plan.append("Prioritize the selected test files before making any broad code changes.")
    return _unique_preserve_order(plan)


def _build_docs_plan(goal_profile: str, impacted_components: list[str]) -> list[str]:
    if goal_profile == "embedding_provider":
        return [
            "Update migration or architecture docs to describe the provider abstraction and any new terminology.",
            "Document config and environment changes so operators know which keys or defaults must be updated.",
            "Add rollout notes for any retrieval or graph behavior that changes user-visible quality.",
        ]
    if goal_profile == "web_ui":
        return [
            "Update UI or route documentation to reflect the new request and rendering flow.",
            "Document any asset or template changes that operators or maintainers need to know about.",
        ]
    if goal_profile == "database_storage":
        return [
            "Update schema and migration notes so operators can understand rollout and rollback steps.",
            "Document any new storage environment variables or connection settings.",
        ]
    return [
        "Update the relevant migration or architecture docs for the selected components.",
        f"Document the impact on: {', '.join(impacted_components)}.",
    ]


def _build_rollout_plan(
    goal_profile: str,
    constraints: list[str],
    risk_tolerance: str,
) -> list[str]:
    base = [
        "Review the dry run and confirm the selected files before any patch planning starts.",
        "Stage the smallest safe change set first and keep rollback-friendly boundaries.",
        "Validate configuration-sensitive paths before any broad rollout.",
    ]
    if goal_profile == "embedding_provider":
        base.insert(1, "Prefer a compatibility-first rollout that preserves retrieval output shape while provider wiring changes.")
    if constraints:
        base.append(f"Respect the stated constraints during implementation: {', '.join(constraints)}.")
    if risk_tolerance:
        base.append(f"Risk tolerance noted as: {risk_tolerance}.")
    return base


def _build_rollback_plan(goal_profile: str, likely_affected_files: list[dict[str, Any]]) -> list[str]:
    if goal_profile == "embedding_provider":
        return [
            "Keep the current provider path available until the new provider abstraction is proven in tests.",
            "Be ready to restore configuration defaults and dependency pins if retrieval quality or startup regressions appear.",
            "Revert the smallest affected files first, especially config, entrypoint, and provider wiring surfaces.",
        ]
    if goal_profile == "web_ui":
        return [
            "Keep the prior routes or templates available until the new UI path is verified.",
            "Revert asset or route changes first if rendering or navigation regresses.",
        ]
    if goal_profile == "database_storage":
        return [
            "Preserve the current storage path until schema changes are verified.",
            "Be prepared to roll back migration scripts or DSN/config updates first.",
        ]
    return [
        "Revert the selected files in reverse dependency order if the migration fails validation.",
        "Restore config and entrypoint surfaces before broader source changes.",
    ]


def _build_risks(
    goal_profile: str,
    likely_affected_files: list[dict[str, Any]],
    node_summaries_status: str,
) -> list[str]:
    risks: list[str] = []
    if goal_profile == "embedding_provider":
        risks.extend(
            [
                "Provider wiring can change embedding shape or retrieval behavior even when the code still imports cleanly.",
                "Config or environment drift can silently break provider selection, fallback routing, or secrets handling.",
                "Graph or indexer changes can alter evidence ordering or search output quality.",
            ]
        )
    elif goal_profile == "web_ui":
        risks.extend(
            [
                "Route or template changes can break startup paths or user-visible rendering.",
                "Static assets and client-side assumptions may diverge during migration.",
            ]
        )
    elif goal_profile == "database_storage":
        risks.extend(
            [
                "Schema or storage changes can produce data compatibility issues during rollout.",
                "Migration or DSN config mistakes may surface only after deployment.",
            ]
        )
    else:
        risks.append("The selected files are migration-sensitive and should be validated before any patch work begins.")

    if node_summaries_status != "ok":
        risks.append("Node summaries were unavailable, so some file selection and risk ranking is narrower than intended.")
    if any(item["path"].startswith("tests/") for item in likely_affected_files):
        risks.append("Test selection may encode legacy assumptions that need deliberate review instead of blind preservation.")
    return _unique_preserve_order(risks)


def _build_open_questions(goal_profile: str, goal_text: str) -> list[str]:
    if goal_profile == "embedding_provider":
        return [
            "Which provider abstraction is authoritative for the migrated embedding path?",
            "Do we need dual-write, compatibility shims, or a straight cutover for embeddings?",
            "Are provider names, environment variables, or defaults allowed to change in this migration?",
        ]
    if goal_profile == "web_ui":
        return [
            "Which routes or templates are considered the source of truth after the migration?",
            "Do we need to preserve old URLs or request shapes for compatibility?",
        ]
    if goal_profile == "database_storage":
        return [
            "Which schema or storage source should be treated as the canonical target?",
            "Do we need a backfill or migration step that can be safely retried?",
        ]
    return [
        f"What is the minimally safe target state for the goal: {goal_text}?",
        "Are there compatibility constraints that would change which files should be prioritized first?",
    ]


def _build_limitations(node_summaries_status: str, goal_profile: str) -> list[str]:
    limitations = [
        "Heuristic dry run only; no model/API calls, patch generation, validation execution, benchmark execution, or runtime mutation occurs here.",
        "Patch generation remains disabled until a human approves a separate follow-up step.",
        "The planner does not invent exact code changes and instead prioritizes likely review targets.",
    ]
    if node_summaries_status != "ok":
        limitations.append("node_summaries.json is missing or unreadable, so the planner relies on Project Map v2 alone.")
    if goal_profile == "embedding_provider":
        limitations.append("Embedding-provider migrations are prioritized heuristically from path keywords and source artifacts, not semantic analysis.")
    return limitations


def _build_error_record(
    *,
    repo_root: Path,
    goal_text: str,
    constraints: list[str],
    risk_tolerance_text: str,
    max_files: int,
    code: str,
    message: str,
    source_artifacts: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "generated_at": _utc_now_iso(),
        "repo_path": str(repo_root),
        "mode": MODE,
        "schema_version": SCHEMA_VERSION,
        "migration_goal": goal_text,
        "constraints": constraints,
        "risk_tolerance": risk_tolerance_text,
        "source_artifacts": source_artifacts,
        "likely_affected_files": [],
        "full_files_to_read_before_patching": [],
        "impacted_components": [],
        "dependency_or_config_changes": [],
        "test_plan": [],
        "docs_plan": [],
        "rollout_plan": [],
        "rollback_plan": [],
        "risks": [],
        "open_questions": [],
        "human_approval_required": True,
        "approval_gate_reason": (
            "This is a dry run only. Human review is required before any patch planning or application."
        ),
        "patch_generation_allowed": False,
        "limitations": [
            "No patch planning is produced until the required source artifacts are available.",
            "The planner remains read-only and heuristic-only.",
        ],
        "status": "error",
        "error": {
            "code": code,
            "message": message,
        },
    }


def _source_artifact_records(
    repo_root: Path,
    source_map_path: str | None,
    node_summaries_path: str | None,
    *,
    source_map_status: str | None = None,
    source_map_generated_at: str = "",
    node_summaries_status: str | None = None,
    node_summaries_generated_at: str = "",
) -> list[dict[str, Any]]:
    source_map_resolved = _resolve_artifact_path(repo_root, source_map_path, DEFAULT_PROJECT_MAP_NAME)
    node_summaries_resolved = _resolve_artifact_path(repo_root, node_summaries_path, DEFAULT_NODE_SUMMARIES_NAME)
    return [
        {
            "name": "project_map_v2",
            "path": str(source_map_resolved),
            "status": source_map_status or _artifact_status(source_map_resolved),
            "generated_at": source_map_generated_at,
        },
        {
            "name": "node_summaries",
            "path": str(node_summaries_resolved),
            "status": node_summaries_status or _artifact_status(node_summaries_resolved),
            "generated_at": node_summaries_generated_at,
        },
    ]


def _load_json_artifact(path: Path, *, required: bool) -> dict[str, Any]:
    if not path.exists():
        if required:
            return {
                "status": "error",
                "message": f"source Project Map v2 artifact does not exist: {path}",
            }
        return {
            "status": "missing",
            "message": f"node summaries artifact does not exist: {path}",
        }
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        status = "error" if required else "invalid"
        kind = "source Project Map v2 artifact" if required else "node summaries artifact"
        return {
            "status": status,
            "message": f"{kind} is invalid JSON: {path} ({exc})",
        }
    except OSError as exc:
        status = "error" if required else "invalid"
        kind = "source Project Map v2 artifact" if required else "node summaries artifact"
        return {
            "status": status,
            "message": f"{kind} could not be read: {path} ({exc})",
        }
    if required:
        if not isinstance(record, dict) or record.get("schema_version") != "project_map_v2/1":
            return {
                "status": "error",
                "message": f"source Project Map v2 artifact is missing or has an unexpected schema: {path}",
            }
    else:
        if not isinstance(record, dict) or record.get("schema_version") != "node_summaries_v1":
            return {
                "status": "invalid",
                "message": f"node summaries artifact is missing or has an unexpected schema: {path}",
            }
    return {"status": "ok", "record": record}


def _artifact_status(path: Path) -> str:
    return "ok" if path.exists() else "missing"


def _resolve_artifact_path(repo_root: Path, explicit_path: str | None, filename: str) -> Path:
    default_path = (repo_root / ".agent" / "project_evolution" / filename).resolve()
    if explicit_path:
        candidate = Path(explicit_path).expanduser()
        resolved = candidate if candidate.is_absolute() else (repo_root / candidate)
        resolved = resolved.resolve()
        try:
            resolved.relative_to(repo_root)
        except ValueError:
            return default_path
        return resolved
    return default_path


def _resolve_output_root(repo_root: Path, output_root: str | None) -> Path:
    if output_root is None:
        resolved = (repo_root / ".agent" / "project_evolution").resolve()
    else:
        candidate = Path(output_root).expanduser()
        resolved = candidate.resolve() if candidate.is_absolute() else (repo_root / candidate).resolve()
    resolved.relative_to(repo_root)
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _classify_goal(goal_text: str) -> str:
    lowered = goal_text.lower()
    for profile, keywords in PROFILE_KEYWORDS.items():
        if any(keyword.lower() in lowered for keyword in keywords):
            return profile
    return "generic"


def _score_candidate(
    rel_path: str,
    goal_profile: str,
    goal_keywords: tuple[str, ...],
    base_weight: int,
) -> int:
    lowered = rel_path.lower()
    score = base_weight
    bonus = EXACT_PATH_BONUS.get(goal_profile, {})
    for exact, points in bonus.items():
        if exact in lowered:
            score += points
    for keyword in goal_keywords:
        if keyword.lower() in lowered:
            score += 40
    if lowered.endswith(".md"):
        score += 10
    if lowered.startswith("tests/"):
        score += 24
    if lowered.startswith("docs/"):
        score += 20
    if lowered.startswith("core/") or lowered.startswith("graph/") or lowered.startswith("retrieval/"):
        score += 28
    if "config" in lowered or "settings" in lowered or ".env" in lowered:
        score += 18
    return score


def _render_candidate(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": item["path"],
        "category": item["category"],
        "reason": item["reason"],
        "confidence": _clamp_confidence(item.get("confidence", 0.7)),
    }


def _node_summary_weight(item: dict[str, Any]) -> int:
    weight = 840
    node_type = str(item.get("node_type", "")).lower()
    if node_type == "dependency":
        weight += 100
    elif node_type == "config":
        weight += 90
    elif node_type == "entrypoint":
        weight += 80
    elif node_type == "provider":
        weight += 70
    elif node_type == "test":
        weight += 60
    elif node_type == "doc":
        weight += 50
    lowered = str(item.get("path", "")).lower()
    if "indexer" in lowered or "weights" in lowered:
        weight += 40
    if "provider" in lowered or "retrieval" in lowered:
        weight += 35
    return weight


def _normalize_category(category: Any, rel_path: str) -> str:
    lowered = str(category or "").lower()
    if lowered in {"dependency", "config", "entrypoint", "doc", "test", "provider"}:
        return lowered
    path = rel_path.lower()
    if path.endswith(".md"):
        return "doc"
    if path.startswith("tests/") or "test_" in Path(path).name:
        return "test"
    if "config" in path or "settings" in path or ".env" in path:
        return "config"
    if "provider" in path or "retrieval" in path or "indexer" in path or "graph" in path or "weights" in path:
        return "provider"
    if path in {"main.py", "app.py", "cli.py", "server.py"} or path.endswith("/app.py"):
        return "entrypoint"
    return "file"


def _normalize_rel_path(rel_path: str) -> str:
    if not rel_path:
        return ""
    normalized = str(rel_path).replace("\\", "/").strip()
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _is_repo_local_path(repo_root: Path, rel_path: str) -> bool:
    candidate = (repo_root / rel_path).resolve()
    try:
        candidate.relative_to(repo_root)
    except ValueError:
        return False
    return True


def _should_consider_plan_path(rel_path: str) -> bool:
    lowered = rel_path.lower()
    if lowered.startswith((".agent/", ".claude/", ".codex/")):
        return False
    if lowered.startswith(("build/", "dist/", "node_modules/", "target/", "venv/", ".venv/", ".git/")):
        return False
    if lowered.startswith(("benchmarks/", ".tmp/", ".pytest_cache/")):
        return False
    if "/buggy_repo/" in lowered or lowered.startswith("buggy_repo/"):
        return False
    if Path(rel_path).name == ".env":
        return False
    return True


def _normalize_constraints(constraints: list[str] | None) -> list[str]:
    if not constraints:
        return []
    cleaned = [constraint.strip() for constraint in constraints if constraint and constraint.strip()]
    return _unique_preserve_order(cleaned)


def _clamp_confidence(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.7
    return round(min(0.99, max(0.0, number)), 2)


def _unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def _render_artifact_lines(items: list[dict[str, Any]]) -> list[str]:
    if not items:
        return ["- None"]
    lines: list[str] = []
    for item in items:
        details = f"`{item.get('name', '')}` at `{item.get('path', '')}`"
        status = item.get("status", "")
        generated_at = item.get("generated_at", "")
        suffix = f" ({status})" if status else ""
        if generated_at:
            suffix += f" generated at `{generated_at}`"
        lines.append(f"- {details}{suffix}")
    return lines


def _render_file_lines(items: list[dict[str, Any]]) -> list[str]:
    if not items:
        return ["- None"]
    lines: list[str] = []
    for item in items:
        lines.append(
            f"- `{item.get('path', '')}` - {item.get('reason', '')} "
            f"(category: `{item.get('category', '')}`, confidence: {item.get('confidence', 0.0):.2f})"
        )
    return lines


def _render_string_list(values: list[str]) -> list[str]:
    if not values:
        return ["- None"]
    return [f"- {value}" for value in values]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
