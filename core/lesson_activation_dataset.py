"""MODEL.3 - Lesson Graph Activation Dataset (report-only).

Reads the MODEL.1 artifact dataset and lesson / anti-lesson candidate files, then
builds deterministic advisory rows for future lesson activation scoring.

MODEL.3 builds data only. It does not change lesson retrieval, does not inject
lessons into prompts, does not call models, does not call embeddings, does not
write to a database, does not apply patches, does not run validation or
benchmarks, does not launch workers, and does not promote, merge, or block
lessons. Rows are advisory only and grant no execution authority.

This module is stdlib-only. Source artifacts are read only; only the writer
touches the filesystem, and only under the chosen output directory.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


REPORT_KIND = "lesson_activation_dataset"

JSONL_NAME = "lesson_activation_dataset.jsonl"
REPORT_JSON_NAME = "lesson_activation_dataset_report.json"
REPORT_MD_NAME = "lesson_activation_dataset_report.md"

LESSON_ACTIVATION_GUARDRAIL_NOTE = (
    "Lesson Graph Activation Dataset is report-only: it reads the MODEL.1 artifact "
    "dataset and lesson / anti-lesson candidates, builds deterministic overlap and "
    "evidence-link features, and writes advisory dataset rows. It changes no lesson "
    "retrieval or prompt behavior, calls no models or embeddings, writes no database, "
    "does not apply patches, does not run validation or benchmarks, does not launch "
    "workers, and does not promote, merge, or block lessons."
)

LESSON_SOURCE_DIRS: tuple[str, ...] = (".agent/lessons", "lessons")
ANTI_LESSON_REPORT_PATTERNS: tuple[str, ...] = (
    ".agent/**/*anti*lesson*.json",
    ".agent/**/*anti*lesson*.jsonl",
)

SUPPRESS_STATUSES = {"archived", "superseded", "blocked", "duplicate", "weak"}
ACTIVE_STATUSES = {"active"}
KNOWN_SCOPES = {"global", "project", "file", "repo"}

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "before",
        "by",
        "do",
        "for",
        "from",
        "if",
        "in",
        "into",
        "is",
        "it",
        "no",
        "not",
        "of",
        "on",
        "or",
        "the",
        "then",
        "this",
        "to",
        "use",
        "when",
        "with",
    }
)


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _first_text(*values: Any) -> str:
    for value in values:
        text = _text(value)
        if text:
            return text
    return ""


def _norm_path(value: Any) -> str:
    return str(value).replace("\\", "/").strip()


def _get_path(row: dict[str, Any], dotted: str) -> Any:
    node: Any = row
    for key in dotted.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


def _str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        token = str(value)
        if token not in seen:
            seen.add(token)
            out.append(token)
    return out


def _tokens(*values: Any) -> set[str]:
    text = " ".join(_text(value).replace("_", " ").replace("-", " ") for value in values)
    out: set[str] = set()
    for match in _TOKEN_RE.finditer(text.lower()):
        token = match.group(0)
        if len(token) < 3 or token in _STOPWORDS:
            continue
        out.add(token)
    return out


def _counts(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value)
        counts[key] = counts.get(key, 0) + 1
    return {key: counts[key] for key in sorted(counts)}


def _rel_to_repo(path: Path, repo: Path) -> str:
    try:
        return _norm_path(path.relative_to(repo))
    except ValueError:
        return _norm_path(path)


def _row_hash(parts: list[str]) -> str:
    payload = "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def load_model1_dataset(dataset_path: str | Path) -> dict[str, Any]:
    """Read MODEL.1 JSONL rows, skipping malformed lines with warnings."""
    path = Path(dataset_path)
    if not path.exists():
        return {
            "rows": [],
            "present": False,
            "skipped": 0,
            "skipped_files": [],
            "warnings": [f"MODEL.1 dataset not found at {_norm_path(dataset_path)}"],
        }

    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    skipped_files: list[dict[str, str]] = []
    skipped = 0
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return {
            "rows": [],
            "present": False,
            "skipped": 0,
            "skipped_files": [{"path": _norm_path(dataset_path), "error": str(exc)}],
            "warnings": [f"could not read MODEL.1 dataset at {_norm_path(dataset_path)}: {exc}"],
        }

    for lineno, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            parsed = json.loads(stripped)
        except ValueError as exc:
            skipped += 1
            msg = f"skipped malformed MODEL.1 JSONL line {lineno}: {exc}"
            warnings.append(msg)
            skipped_files.append({"path": f"{_norm_path(dataset_path)}:{lineno}", "error": msg})
            continue
        if not isinstance(parsed, dict):
            skipped += 1
            msg = f"skipped non-object MODEL.1 JSONL line {lineno}"
            warnings.append(msg)
            skipped_files.append({"path": f"{_norm_path(dataset_path)}:{lineno}", "error": msg})
            continue
        rows.append(parsed)

    return {
        "rows": rows,
        "present": True,
        "skipped": skipped,
        "skipped_files": skipped_files,
        "warnings": warnings,
    }


def _read_json_candidates(path: Path) -> tuple[list[dict[str, Any]], str]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [], f"could not read file: {exc}"

    if path.suffix.lower() == ".jsonl":
        out: list[dict[str, Any]] = []
        for lineno, line in enumerate(raw.splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                parsed = json.loads(stripped)
            except ValueError as exc:
                return out, f"could not parse JSONL line {lineno}: {exc}"
            out.extend(_extract_candidate_objects(parsed))
        return out, ""

    try:
        parsed = json.loads(raw)
    except ValueError as exc:
        return [], f"could not parse JSON: {exc}"
    return _extract_candidate_objects(parsed), ""


def _extract_candidate_objects(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        out: list[dict[str, Any]] = []
        for item in value:
            out.extend(_extract_candidate_objects(item))
        return out

    if not isinstance(value, dict):
        return []

    if _looks_like_lesson(value):
        return [value]

    out: list[dict[str, Any]] = []
    for key in (
        "records",
        "lessons",
        "lesson_candidates",
        "anti_lessons",
        "candidates",
        "selected_matches",
        "shadow_matches",
    ):
        child = value.get(key)
        if isinstance(child, list):
            for item in child:
                out.extend(_extract_candidate_objects(item))
    return out


def _looks_like_lesson(value: dict[str, Any]) -> bool:
    if value.get("kind") in {"lesson", "anti_lesson"}:
        return True
    if value.get("anti_lesson") is True:
        return True
    if isinstance(value.get("candidate"), dict) and value["candidate"].get("anti_lesson") is True:
        return True
    if _first_text(value.get("id"), value.get("lesson_id")) and (
        _first_text(value.get("title"), value.get("summary"))
        or _str_list(value.get("tags"))
        or _first_text(value.get("status"))
    ):
        return True
    return False


def scan_lesson_candidates(repo_path: str | Path) -> dict[str, Any]:
    """Scan lesson and anti-lesson candidate sources under a repo.

    Missing source directories are warnings, not failures. Malformed JSON files are
    skipped with warnings. Candidate records are normalized later so this scanner
    can keep extraction broad and read-only.
    """
    repo = Path(repo_path)
    candidates: list[dict[str, Any]] = []
    scanned_paths: list[str] = []
    skipped_files: list[dict[str, str]] = []
    warnings: list[str] = []
    seen_files: set[Path] = set()

    for base_rel in LESSON_SOURCE_DIRS:
        base = repo / base_rel
        if not base.exists():
            warnings.append(f"lesson source not present: {base_rel}")
            continue
        scanned_paths.append(base_rel)
        for pattern in ("**/*.json", "**/*.jsonl"):
            for path in sorted(base.glob(pattern)):
                if not path.is_file() or path in seen_files:
                    continue
                seen_files.add(path)
                rel = _rel_to_repo(path, repo)
                found, error = _read_json_candidates(path)
                if error:
                    skipped_files.append({"path": rel, "error": error})
                    warnings.append(f"skipped {rel}: {error}")
                    continue
                for index, candidate in enumerate(found):
                    copy = dict(candidate)
                    copy["_source_path"] = rel
                    copy["_source_index"] = index
                    candidates.append(copy)

    agent_root = repo / ".agent"
    if agent_root.exists():
        for pattern in ANTI_LESSON_REPORT_PATTERNS:
            for path in sorted(repo.glob(pattern)):
                if not path.is_file() or path in seen_files:
                    continue
                seen_files.add(path)
                rel = _rel_to_repo(path, repo)
                found, error = _read_json_candidates(path)
                if error:
                    skipped_files.append({"path": rel, "error": error})
                    warnings.append(f"skipped {rel}: {error}")
                    continue
                if found:
                    scanned_paths.append(str(Path(pattern).parent).replace("\\", "/"))
                for index, candidate in enumerate(found):
                    copy = dict(candidate)
                    copy["_source_path"] = rel
                    copy["_source_index"] = index
                    candidates.append(copy)

    return {
        "candidates": candidates,
        "scanned_paths": _dedupe(scanned_paths),
        "skipped_files": skipped_files,
        "warnings": warnings,
    }


def _candidate_payload(candidate: dict[str, Any]) -> dict[str, Any]:
    payload = candidate.get("candidate")
    return payload if isinstance(payload, dict) else {}


def _lesson_kind(candidate: dict[str, Any]) -> str:
    payload = _candidate_payload(candidate)
    if candidate.get("kind") == "anti_lesson" or candidate.get("anti_lesson") is True:
        return "anti_lesson"
    if payload.get("anti_lesson") is True:
        return "anti_lesson"
    return "lesson"


def _lesson_status(candidate: dict[str, Any]) -> str:
    if candidate.get("archived") is True:
        return "archived"
    if _first_text(candidate.get("superseded_by")):
        return "superseded"
    if _first_text(candidate.get("duplicate_of")):
        return "duplicate"
    raw = _text(candidate.get("status")).lower()
    if raw in ACTIVE_STATUSES or raw in SUPPRESS_STATUSES or raw in {"candidate", "unknown"}:
        return raw
    return "unknown"


def _lesson_scope(candidate: dict[str, Any]) -> str:
    raw = _text(candidate.get("scope")).lower()
    if raw == "repo":
        return "project"
    if raw in KNOWN_SCOPES:
        return raw
    return "unknown"


def _lesson_confidence(candidate: dict[str, Any]) -> float:
    raw = candidate.get("confidence")
    if raw is None and isinstance(candidate.get("evaluation"), dict):
        raw = candidate["evaluation"].get("confidence")
        if raw is None:
            raw = candidate["evaluation"].get("confidence_score")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0.0
    return round(max(0.0, min(1.0, value)), 6)


def _lesson_tags(candidate: dict[str, Any]) -> list[str]:
    tags = _str_list(candidate.get("tags"))
    payload = _candidate_payload(candidate)
    tags.extend(_str_list(payload.get("tags")))
    return _dedupe([tag.lower() for tag in tags])


def _lesson_title(candidate: dict[str, Any]) -> str:
    payload = _candidate_payload(candidate)
    return _first_text(
        candidate.get("title"),
        payload.get("title"),
        payload.get("tempting_wrong_pattern"),
        candidate.get("lesson_title"),
    )


def _lesson_summary(candidate: dict[str, Any]) -> str:
    payload = _candidate_payload(candidate)
    parts = [
        candidate.get("summary"),
        payload.get("summary"),
        payload.get("why_wrong"),
        payload.get("safer_alternative"),
        payload.get("recommendation"),
    ]
    return " ".join(_text(part) for part in parts if _text(part))


def _lesson_id(candidate: dict[str, Any]) -> str:
    explicit = _first_text(candidate.get("lesson_id"), candidate.get("id"))
    if explicit:
        return explicit
    source_path = _text(candidate.get("_source_path"))
    source_index = _text(candidate.get("_source_index"))
    digest = _row_hash([source_path, source_index, _lesson_title(candidate), _lesson_kind(candidate)])
    return f"candidate-{digest}"


def _evidence_refs(candidate: dict[str, Any]) -> list[str]:
    payload = _candidate_payload(candidate)
    refs: list[str] = []
    for key in ("evidence_refs", "evidence", "source_report", "source_path", "artifact_path"):
        refs.extend(_str_list(candidate.get(key)))
        refs.extend(_str_list(payload.get(key)))
    return _dedupe([_norm_path(ref) for ref in refs])


def _query_path(query: dict[str, Any], dataset_path: str = "") -> str:
    return _first_text(query.get("artifact_path"), dataset_path)


def _normalize_query(query: dict[str, Any], *, dataset_path: str = "") -> dict[str, Any]:
    target = query.get("target") if isinstance(query.get("target"), dict) else {}
    return {
        "path": _norm_path(_query_path(query, dataset_path)),
        "row_id": _text(query.get("row_id")),
        "artifact_kind": _text(query.get("artifact_kind")) or "unknown",
        "task_title": _text(query.get("task_title")),
        "task_summary": _text(query.get("task_summary")),
        "risk_level": _text(query.get("risk_level")).lower() or "unknown",
        "dataset_task": _text(target.get("dataset_task")) or "unknown",
    }


def _normalize_lesson_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    kind = _lesson_kind(candidate)
    status = _lesson_status(candidate)
    return {
        "lesson_id": _lesson_id(candidate),
        "kind": kind,
        "title": _lesson_title(candidate),
        "status": status,
        "scope": _lesson_scope(candidate),
        "confidence": _lesson_confidence(candidate),
        "tags": _lesson_tags(candidate),
    }


def _candidate_tokens(candidate: dict[str, Any]) -> set[str]:
    return _tokens(_lesson_title(candidate), _lesson_summary(candidate), " ".join(_lesson_tags(candidate)))


def _query_tokens(query: dict[str, Any]) -> set[str]:
    return _tokens(
        query.get("artifact_kind"),
        query.get("task_title"),
        query.get("task_summary"),
        query.get("risk_level"),
        query.get("dataset_task"),
    )


def _has_evidence_link(query: dict[str, Any], candidate: dict[str, Any]) -> bool:
    refs = _evidence_refs(candidate)
    if not refs:
        return False
    query_values = {
        _norm_path(query.get("path")),
        _norm_path(query.get("row_id")),
    }
    query_values = {value for value in query_values if value}
    for ref in refs:
        for value in query_values:
            if ref == value or ref.endswith("/" + value) or value.endswith("/" + ref):
                return True
            if value and value in ref:
                return True
    return False


def _missing_fields(query: dict[str, Any], lesson: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for name, value in (
        ("query_artifact.row_id", query.get("row_id")),
        ("query_artifact.path", query.get("path")),
        ("lesson_candidate.lesson_id", lesson.get("lesson_id")),
        ("lesson_candidate.title", lesson.get("title")),
    ):
        if not _text(value):
            missing.append(name)
    return missing


def _activation_label(
    lesson: dict[str, Any],
    features: dict[str, Any],
    *,
    min_overlap: int,
) -> tuple[str, str]:
    status = _text(lesson.get("status")).lower()
    if status in SUPPRESS_STATUSES:
        return "suppress", "heuristic"

    has_signal = bool(lesson.get("title") or lesson.get("tags"))
    if not has_signal:
        return "unknown", "unknown"

    if status not in ACTIVE_STATUSES:
        return "unknown", "unknown"

    if features["has_evidence_refs"]:
        return "activate", "explicit"

    threshold = max(0, int(min_overlap))
    if (
        int(features["token_overlap"]) >= threshold
        or int(features["title_overlap"]) >= threshold
        or int(features["tag_overlap"]) >= threshold
    ):
        return "activate", "heuristic"

    return "ignore", "heuristic"


def _build_row(
    query_raw: dict[str, Any],
    candidate_raw: dict[str, Any],
    *,
    dataset_path: str = "",
    min_overlap: int = 1,
) -> dict[str, Any]:
    query = _normalize_query(query_raw, dataset_path=dataset_path)
    lesson = _normalize_lesson_candidate(candidate_raw)

    q_tokens = _query_tokens(query)
    c_tokens = _candidate_tokens(candidate_raw)
    q_title_tokens = _tokens(query.get("task_title"))
    c_title_tokens = _tokens(lesson.get("title"))
    tag_tokens = _tokens(" ".join(lesson.get("tags") or []))

    status = _text(lesson.get("status")).lower()
    evidence_linked = _has_evidence_link(query, candidate_raw)
    features = {
        "token_overlap": len(q_tokens & c_tokens),
        "title_overlap": len(q_title_tokens & c_title_tokens),
        "tag_overlap": len(q_tokens & tag_tokens),
        "risk_match": query.get("risk_level") != "unknown"
        and query.get("risk_level") in (lesson.get("tags") or []),
        "kind_match": query.get("artifact_kind") in (lesson.get("tags") or [])
        or bool(_tokens(query.get("artifact_kind")) & c_tokens),
        "has_evidence_refs": evidence_linked,
        "is_active": status == "active",
        "is_archived": status in {"archived", "superseded"},
        "is_anti_lesson": lesson.get("kind") == "anti_lesson",
    }
    label, source = _activation_label(lesson, features, min_overlap=min_overlap)
    missing = _missing_fields(query, lesson)
    warnings = []
    if missing:
        warnings.append("missing fields: " + ", ".join(missing))

    row_id = "lesson-activation-" + _row_hash(
        [
            query.get("row_id", ""),
            query.get("path", ""),
            lesson.get("lesson_id", ""),
            lesson.get("kind", ""),
            lesson.get("title", ""),
        ]
    )

    return {
        "row_id": row_id,
        "query_artifact": query,
        "lesson_candidate": lesson,
        "activation_features": features,
        "target": {
            "activation_label": label,
            "target_source": source,
            "authority": "advisory_only",
        },
        "quality": {
            "parse_status": "ok" if not missing else "partial",
            "missing_fields": missing,
            "warnings": warnings,
        },
    }


def _row_sort_key(row: dict[str, Any]) -> tuple[str, str, str]:
    query = row.get("query_artifact") if isinstance(row.get("query_artifact"), dict) else {}
    lesson = row.get("lesson_candidate") if isinstance(row.get("lesson_candidate"), dict) else {}
    return (
        str(query.get("row_id") or query.get("path") or ""),
        str(lesson.get("lesson_id") or ""),
        str(row.get("row_id") or ""),
    )


def build_activation_rows(
    query_artifacts: Any,
    lesson_candidates: Any,
    *,
    dataset_path: str = "",
    min_overlap: int = 1,
    limit: Any = None,
) -> list[dict[str, Any]]:
    """Build deterministic advisory activation rows from parsed inputs."""
    queries = [q for q in query_artifacts if isinstance(q, dict)] if isinstance(query_artifacts, list) else []
    candidates = [c for c in lesson_candidates if isinstance(c, dict)] if isinstance(lesson_candidates, list) else []

    rows: list[dict[str, Any]] = []
    for query in sorted(queries, key=lambda q: (_text(q.get("row_id")), _text(q.get("artifact_path")))):
        for candidate in sorted(candidates, key=lambda c: (_lesson_id(c), _text(c.get("_source_path")))):
            rows.append(_build_row(query, candidate, dataset_path=dataset_path, min_overlap=min_overlap))

    rows.sort(key=_row_sort_key)
    if isinstance(limit, int) and limit >= 0:
        rows = rows[:limit]
    return rows


def _guardrails() -> dict[str, bool]:
    return {
        "lesson_retrieval_changed": False,
        "prompt_injection_changed": False,
        "lesson_promotion_performed": False,
        "lesson_merge_performed": False,
        "lesson_block_performed": False,
        "model_call_performed": False,
        "embedding_call_performed": False,
        "database_write_performed": False,
        "network_call_performed": False,
        "patch_applied": False,
        "validation_run": False,
        "benchmark_run": False,
        "worker_launch_performed": False,
        "merge_performed": False,
    }


def build_lesson_activation_report(
    *,
    repo_path: str | Path,
    rows: list[dict[str, Any]],
    query_artifact_count: int,
    lesson_candidate_count: int,
    scanned_paths: list[str],
    skipped_files: list[dict[str, str]],
    warnings: list[str],
    report_id: str = "",
    created_at: str = "",
    output_dir: str = "",
    jsonl_path: str = "",
    sample_size: int = 5,
) -> dict[str, Any]:
    return {
        "report_kind": REPORT_KIND,
        "guardrail_note": LESSON_ACTIVATION_GUARDRAIL_NOTE,
        "report_id": str(report_id or ""),
        "created_at": str(created_at or ""),
        "repo_path": _norm_path(repo_path),
        "output_dir": _norm_path(output_dir) if output_dir else "",
        "jsonl_path": _norm_path(jsonl_path) if jsonl_path else "",
        "query_artifact_count": int(query_artifact_count),
        "lesson_candidate_count": int(lesson_candidate_count),
        "row_count": len(rows),
        "counts_by_lesson_kind": _counts([_get_path(row, "lesson_candidate.kind") or "unknown" for row in rows]),
        "counts_by_activation_label": _counts([_get_path(row, "target.activation_label") or "unknown" for row in rows]),
        "counts_by_query_artifact_kind": _counts([_get_path(row, "query_artifact.artifact_kind") or "unknown" for row in rows]),
        "counts_by_target_source": _counts([_get_path(row, "target.target_source") or "unknown" for row in rows]),
        "scanned_paths": list(scanned_paths),
        "skipped_files": list(skipped_files),
        "warnings": list(warnings),
        "guardrails": _guardrails(),
        "sample_rows": [dict(row) for row in rows[:sample_size]],
    }


def _counts_table(lines: list[str], title: str, counts: dict[str, int]) -> None:
    lines += [f"## {title}", ""]
    if counts:
        lines += ["| Key | Count |", "| --- | --- |"]
        for key in sorted(counts):
            lines.append(f"| `{_md(key)}` | {counts[key]} |")
    else:
        lines.append("_None._")
    lines.append("")


def render_lesson_activation_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = [
        "# Lesson Graph Activation Dataset Report",
        "",
        f"> {report.get('guardrail_note', LESSON_ACTIVATION_GUARDRAIL_NOTE)}",
        "",
        "_Report only: MODEL.3 builds advisory lesson activation data and grants no "
        "execution authority._",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- **Report id:** `{_md(report.get('report_id') or '(none)')}`",
        f"- **Created at:** `{_md(report.get('created_at') or '(none)')}`",
        f"- **Repo path:** `{_md(report.get('repo_path') or '(none)')}`",
        f"- **Row count:** {report.get('row_count', 0)}",
        "",
        "## Dataset Files",
        "",
        f"- **JSONL:** `{_md(report.get('jsonl_path') or '(none)')}`",
        f"- **Output directory:** `{_md(report.get('output_dir') or '(none)')}`",
        "",
        "## Query Artifacts",
        "",
        f"- **Count:** {report.get('query_artifact_count', 0)}",
        "",
        "## Lesson Candidates",
        "",
        f"- **Count:** {report.get('lesson_candidate_count', 0)}",
        "",
    ]

    _counts_table(lines, "Counts by Lesson Kind", report.get("counts_by_lesson_kind") or {})
    _counts_table(lines, "Counts by Activation Label", report.get("counts_by_activation_label") or {})
    _counts_table(lines, "Counts by Query Artifact Kind", report.get("counts_by_query_artifact_kind") or {})
    _counts_table(lines, "Counts by Target Source", report.get("counts_by_target_source") or {})

    lines += ["## Skipped Files", ""]
    skipped = report.get("skipped_files") or []
    if skipped:
        lines += ["| Path | Reason |", "| --- | --- |"]
        for entry in skipped:
            lines.append(f"| `{_md(entry.get('path'))}` | {_md(entry.get('error'))} |")
    else:
        lines.append("_None._")
    lines.append("")

    lines += ["## Warnings", ""]
    warnings = report.get("warnings") or []
    if warnings:
        for warning in warnings:
            lines.append(f"- {_md(warning)}")
    else:
        lines.append("_None._")
    lines.append("")

    lines += ["## Sample Rows", ""]
    sample_rows = report.get("sample_rows") or []
    if sample_rows:
        lines += [
            "| Row id | Query kind | Lesson kind | Lesson status | Label | Source |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for row in sample_rows:
            query = row.get("query_artifact") or {}
            lesson = row.get("lesson_candidate") or {}
            target = row.get("target") or {}
            lines.append(
                f"| `{_md(row.get('row_id'))}` | {_md(query.get('artifact_kind'))} | "
                f"{_md(lesson.get('kind'))} | {_md(lesson.get('status'))} | "
                f"{_md(target.get('activation_label'))} | {_md(target.get('target_source'))} |"
            )
    else:
        lines.append("_None - the dataset is empty._")
    lines.append("")

    lines += ["## Boundaries", ""]
    lines += [
        "- MODEL.3 does not change lesson retrieval.",
        "- MODEL.3 does not inject lessons into prompts.",
        "- MODEL.3 does not promote lessons.",
        "- MODEL.3 does not merge or block lessons.",
        "- MODEL.3 does not call models.",
        "- MODEL.3 does not call embeddings.",
        "- MODEL.3 does not write to databases.",
        "- MODEL.3 does not apply patches.",
        "- MODEL.3 does not run validation or benchmarks.",
        "- MODEL.3 does not launch workers.",
        "- MODEL.3 rows are advisory only and grant no execution authority.",
        "",
    ]
    return "\n".join(lines) + "\n"


def _render_jsonl(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    return "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n"


def write_lesson_activation_dataset(
    repo_path: str | Path,
    output_dir: str | Path,
    *,
    artifact_dataset_path: str | Path,
    report_id: str = "",
    created_at: str = "",
    limit: Any = None,
    min_overlap: int = 1,
) -> dict[str, Any]:
    """Read sources, build activation rows, and write JSONL + JSON + Markdown."""
    loaded = load_model1_dataset(artifact_dataset_path)
    scanned = scan_lesson_candidates(repo_path)

    warnings = list(loaded["warnings"]) + list(scanned["warnings"])
    skipped_files = list(loaded["skipped_files"]) + list(scanned["skipped_files"])
    scanned_paths = []
    if loaded["present"]:
        scanned_paths.append(_norm_path(artifact_dataset_path))
    scanned_paths.extend(scanned["scanned_paths"])
    scanned_paths = _dedupe(scanned_paths)

    rows = build_activation_rows(
        loaded["rows"],
        scanned["candidates"],
        dataset_path=_norm_path(artifact_dataset_path),
        min_overlap=min_overlap,
        limit=limit,
    )

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / JSONL_NAME
    json_path = out_dir / REPORT_JSON_NAME
    md_path = out_dir / REPORT_MD_NAME

    report = build_lesson_activation_report(
        repo_path=repo_path,
        rows=rows,
        query_artifact_count=len(loaded["rows"]),
        lesson_candidate_count=len(scanned["candidates"]),
        scanned_paths=scanned_paths,
        skipped_files=skipped_files,
        warnings=warnings,
        report_id=report_id,
        created_at=created_at,
        output_dir=str(out_dir),
        jsonl_path=str(jsonl_path),
    )

    jsonl_path.write_text(_render_jsonl(rows), encoding="utf-8")
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_lesson_activation_markdown(report), encoding="utf-8")

    return {
        "ok": True,
        "jsonl_path": str(jsonl_path),
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": report,
        "rows": rows,
    }
