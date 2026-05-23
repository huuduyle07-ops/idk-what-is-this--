from __future__ import annotations

from dataclasses import dataclass, field

from core.lesson_store import list_lessons
from core.project_tag import build_project_tag
from database.memory import db_enabled, get_pool
from graph.penalty_constants import OMEGA_BLOCKED, OMEGA_TRANSIENT


_PATCH_FAILURE_SQL = """
SELECT target_file,
       target_node_name,
       COUNT(*) AS fail_count
FROM patch_attempts
WHERE project_tag = %s
  AND target_file IS NOT NULL
  AND (
      phase IN ('validation_failed', 'apply_failed', 'dry_run_blocked')
      OR validation_ok IS FALSE
      OR rollback_performed IS TRUE
  )
GROUP BY target_file, target_node_name;
"""


@dataclass(frozen=True)
class PenaltyResult:
    penalty_map: dict[str, float] = field(default_factory=dict)
    unmatched_paths: list[str] = field(default_factory=list)


def _file_node_index(graph) -> tuple[set[str], dict[str, str]]:
    file_nodes: set[str] = set()
    lower_to_canonical: dict[str, str] = {}
    for node_id, node in graph.nodes.items():
        if getattr(node, "type", "") == "file":
            file_nodes.add(node_id)
            lower_to_canonical.setdefault(node_id.lower(), node_id)
    return file_nodes, lower_to_canonical


def _normalize_path(raw: str) -> str:
    norm = raw.replace("\\", "/")
    if norm.startswith("./"):
        norm = norm[2:]
    return norm


def _resolve_file(
    norm_path: str,
    file_nodes: set[str],
    lower_to_canonical: dict[str, str],
) -> str | None:
    if norm_path in file_nodes:
        return norm_path
    return lower_to_canonical.get(norm_path.lower())


def _read_blocked_counts(
    file_nodes: set[str],
    lower_to_canonical: dict[str, str],
) -> tuple[dict[str, int], list[str]]:
    counts: dict[str, int] = {}
    unmatched: list[str] = []
    for lesson in list_lessons(status="blocked"):
        if not isinstance(lesson, dict):
            continue
        candidate = lesson.get("candidate")
        if not isinstance(candidate, dict):
            continue
        changed = candidate.get("changed_files")
        if not isinstance(changed, list):
            continue
        for path in changed:
            if not isinstance(path, str):
                continue
            canonical = _resolve_file(_normalize_path(path), file_nodes, lower_to_canonical)
            if canonical is not None:
                counts[canonical] = counts.get(canonical, 0) + 1
            else:
                unmatched.append(path)
    return counts, unmatched


def _fetch_patch_attempt_rows(project_tag: str) -> list[tuple]:
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(_PATCH_FAILURE_SQL, (project_tag,))
            return list(cur.fetchall())


def _read_transient_counts(
    graph,
    file_nodes: set[str],
    lower_to_canonical: dict[str, str],
    project_tag: str,
) -> tuple[dict[str, int], list[str]]:
    counts: dict[str, int] = {}
    unmatched: list[str] = []
    for row in _fetch_patch_attempt_rows(project_tag):
        target_file, target_node_name, fail_count = row[0], row[1], row[2]
        if not isinstance(target_file, str):
            continue
        canonical_file = _resolve_file(
            _normalize_path(target_file), file_nodes, lower_to_canonical
        )
        if target_node_name is None:
            if canonical_file is not None:
                counts[canonical_file] = counts.get(canonical_file, 0) + int(fail_count)
            else:
                unmatched.append(target_file)
        else:
            if canonical_file is not None:
                symbol_id = f"{canonical_file}::{target_node_name}"
                if symbol_id in graph.nodes:
                    counts[symbol_id] = counts.get(symbol_id, 0) + int(fail_count)
                else:
                    unmatched.append(symbol_id)
            else:
                unmatched.append(f"{target_file}::{target_node_name}")
    return counts, unmatched


def build_penalty_map(graph, repo_path: str) -> PenaltyResult:
    if not getattr(graph, "nodes", None):
        return PenaltyResult({}, [])

    file_nodes, lower_to_canonical = _file_node_index(graph)
    blocked_counts, blocked_unmatched = _read_blocked_counts(
        file_nodes, lower_to_canonical
    )

    transient_counts: dict[str, int] = {}
    transient_unmatched: list[str] = []
    if db_enabled():
        project_tag = build_project_tag(repo_path)
        if project_tag:
            transient_counts, transient_unmatched = _read_transient_counts(
                graph, file_nodes, lower_to_canonical, project_tag
            )

    penalty_map: dict[str, float] = {}
    for node_id, count in blocked_counts.items():
        penalty_map[node_id] = penalty_map.get(node_id, 0.0) + OMEGA_BLOCKED * count
    for node_id, count in transient_counts.items():
        penalty_map[node_id] = penalty_map.get(node_id, 0.0) + OMEGA_TRANSIENT * count

    unmatched = blocked_unmatched + transient_unmatched
    return PenaltyResult(penalty_map, unmatched)
