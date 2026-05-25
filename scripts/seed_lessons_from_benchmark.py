#!/usr/bin/env python
"""Phase 6.4b: seed lesson candidates from existing benchmark reports.

This script is intentionally read-only toward benchmark artifacts and never
runs benchmarks, models, patch application, or retrieval. Lesson records are
created only through core.lesson_store.save_candidate_lesson(), so the normal
lesson_quality gate remains the routing authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_BENCHMARK_ROOT = PROJECT_ROOT / ".agent" / "benchmarks"
DEFAULT_REPORTS_ROOT = PROJECT_ROOT / ".agent" / "reports"

SOURCE = "benchmark_report"
_MAX_TEXT_CHARS = 600


def _as_str(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _as_bool_or_raw(value: Any) -> bool | Any:
    return value if isinstance(value, bool) else value


def _as_str_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return []


def _first_int(*values: Any) -> int | None:
    for value in values:
        if isinstance(value, bool) or value is None:
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            try:
                return int(value.strip())
            except ValueError:
                continue
    return None


def _truncate(value: Any, limit: int = _MAX_TEXT_CHARS) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"invalid JSON in {path.name}: {e}") from e
    except OSError as e:
        raise ValueError(f"could not read {path}: {e}") from e
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return data


def _resolve_report_name(
    raw: str,
    *,
    benchmarks_root: str | Path | None = None,
) -> Path:
    text = _as_str(raw)
    if (
        not text
        or "/" in text
        or "\\" in text
        or not text.startswith("benchmark_report_")
        or not text.endswith(".json")
        or Path(text).name != text
    ):
        raise ValueError("--report must be a benchmark_report_*.json filename")

    root = Path(benchmarks_root or DEFAULT_BENCHMARK_ROOT).resolve()
    path = (root / text).resolve()
    try:
        path.relative_to(root)
    except ValueError as e:
        raise ValueError(f"report path escapes benchmark root: {text}") from e
    if not path.is_file():
        raise ValueError(f"benchmark report not found: {path}")
    return path


def _latest_report_path(
    benchmarks_root: str | Path | None = None,
) -> Path:
    root = Path(benchmarks_root or DEFAULT_BENCHMARK_ROOT).resolve()
    if not root.is_dir():
        raise ValueError(f"benchmark reports directory not found: {root}")
    candidates = list(root.glob("benchmark_report_*.json"))
    if not candidates:
        raise ValueError(f"no benchmark_report_*.json files found in {root}")
    return max(candidates, key=lambda p: (p.stat().st_mtime, p.name))


def _parse_agent_answer(result: dict[str, Any]) -> dict[str, Any] | None:
    raw = result.get("agent_answer")
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _has_patch_evidence(
    result: dict[str, Any],
    proposal: dict[str, Any] | None,
    changed_files: list[str],
) -> bool:
    if changed_files:
        return True
    if not proposal:
        return False
    if proposal.get("patch_plan") is not None:
        return True
    if proposal.get("patch_candidate") is not None:
        return True
    return bool(_as_str(proposal.get("summary")))


def _hash_payload(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def _source_hash(
    result: dict[str, Any],
    proposal: dict[str, Any] | None,
    changed_files: list[str],
) -> tuple[str, str]:
    if proposal and (
        proposal.get("patch_plan") is not None
        or proposal.get("patch_candidate") is not None
    ):
        payload = {
            "patch_plan": proposal.get("patch_plan"),
            "patch_candidate": proposal.get("patch_candidate"),
        }
        return "patch_hash", _hash_payload(payload)

    raw = result.get("agent_answer")
    if isinstance(raw, str) and raw.strip():
        return "patch_hash", hashlib.sha256(raw.strip().encode("utf-8")).hexdigest()[:16]

    return "changed_files_hash", _hash_payload(sorted(changed_files))


def _existing_source_keys(repo_path: str | None = None) -> set[str]:
    from core.lesson_store import list_lessons

    keys: set[str] = set()
    for lesson in list_lessons(repo_path=repo_path):
        candidate = lesson.get("candidate")
        if isinstance(candidate, dict):
            key = candidate.get("source_key")
            if isinstance(key, str) and key.strip():
                keys.add(key)
    return keys


def _patch_summary(result: dict[str, Any], proposal: dict[str, Any] | None) -> str:
    if proposal:
        summary = _truncate(proposal.get("summary"))
        if summary:
            return summary
    for key in ("patch_summary", "summary"):
        summary = _truncate(result.get(key))
        if summary:
            return summary
    return ""


def _diff_stats(result: dict[str, Any]) -> dict[str, int]:
    minimality = result.get("patch_minimality")
    if not isinstance(minimality, dict):
        minimality = {}

    added = _first_int(minimality.get("added_lines"), result.get("added_lines"))
    removed = _first_int(minimality.get("removed_lines"), result.get("removed_lines"))
    changed = _first_int(
        minimality.get("total_changed_lines"),
        result.get("total_changed_lines"),
        minimality.get("changed_lines"),
        result.get("changed_lines"),
    )

    stats: dict[str, int] = {}
    if added is not None:
        stats["added"] = max(0, added)
    if removed is not None:
        stats["removed"] = max(0, removed)
    if changed is not None:
        stats["changed"] = max(0, changed)
    return stats


def _minimality_fields(result: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    minimality = result.get("patch_minimality")
    if isinstance(minimality, dict):
        out["patch_minimality"] = dict(minimality)

    for key in (
        "files_touched",
        "added_lines",
        "removed_lines",
        "net_changed_lines",
        "total_changed_lines",
        "touched_test_files",
        "patch_size_score",
    ):
        if key in result:
            out[key] = result.get(key)
        elif isinstance(minimality, dict) and key in minimality:
            out[key] = minimality.get(key)
    return out


def _validation_summary(result: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "success": bool(result.get("success")),
        "validation_ok": result.get("validation_ok"),
    }
    output = _truncate(result.get("validation_output"))
    if output:
        summary["validation_output_tail"] = output
    agent_validation = _truncate(result.get("agent_validation"))
    if agent_validation:
        summary["agent_validation_tail"] = agent_validation
    return summary


def _benchmark_status(result: dict[str, Any]) -> str:
    if result.get("flaky"):
        return "flaky"
    if result.get("skipped"):
        return "skipped"
    if result.get("success"):
        return "passed"
    return "failed"


def _build_candidate(
    result: dict[str, Any],
    *,
    source_report: str,
) -> tuple[dict[str, Any] | None, str | None]:
    case_name = _as_str(result.get("name") or result.get("case_name"))
    if not case_name:
        return None, "missing_case_name"

    changed_files = _as_str_list(result.get("changed_files"))
    proposal = _parse_agent_answer(result)
    if not _has_patch_evidence(result, proposal, changed_files):
        return None, "missing_patch_evidence"

    hash_kind, evidence_hash = _source_hash(result, proposal, changed_files)
    source_key = f"{source_report}:{case_name}:{hash_kind}:{evidence_hash}"

    patch_summary = _patch_summary(result, proposal)
    status = _benchmark_status(result)
    flaky = bool(result.get("flaky"))
    review_evidence: list[str] = []
    if flaky:
        review_evidence.append("flaky benchmark case")

    candidate: dict[str, Any] = {
        "source": SOURCE,
        "source_report": source_report,
        "source_key": source_key,
        hash_kind: evidence_hash,
        "case_name": case_name,
        "language": _as_str(result.get("language")),
        "category": _as_str(result.get("category")),
        "difficulty": _as_str(result.get("difficulty")),
        "benchmark_status": status,
        "benchmark_passed": status in {"passed", "flaky"},
        "benchmark_failed": status == "failed",
        "benchmark_flaky": flaky,
        "validation_ok": _as_bool_or_raw(result.get("validation_ok")),
        "touched_forbidden_files": _as_str_list(result.get("touched_forbidden_files")),
        "missing_expected_files": _as_str_list(result.get("missing_expected_files")),
        "patch_kind": _as_str(result.get("patch_kind")) or "unknown",
        "rollback_happened": bool(result.get("rollback_happened")),
        "changed_files": changed_files,
        "patch_summary": patch_summary,
        "validation_summary": _validation_summary(result),
    }

    if review_evidence:
        candidate["needs_human_review"] = True
        candidate["review_evidence"] = "; ".join(review_evidence)

    diff_stats = _diff_stats(result)
    if diff_stats:
        candidate["diff_stats"] = diff_stats

    candidate.update(_minimality_fields(result))
    return candidate, None


def _selection_rank(index_and_result: tuple[int, dict[str, Any]]) -> tuple[int, int]:
    index, result = index_and_result
    if result.get("flaky"):
        return 1, index
    if result.get("success") and result.get("validation_ok") is True:
        return 0, index
    if result.get("success"):
        return 2, index
    return 3, index


def _selected_results(
    report: dict[str, Any],
    *,
    case_name: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    raw_results = report.get("results")
    if not isinstance(raw_results, list):
        return []

    selected: list[tuple[int, dict[str, Any]]] = []
    for index, item in enumerate(raw_results):
        if not isinstance(item, dict):
            continue
        name = _as_str(item.get("name") or item.get("case_name"))
        if case_name and name != case_name:
            continue
        selected.append((index, item))

    selected.sort(key=_selection_rank)
    results = [item for _index, item in selected]
    if limit is not None:
        results = results[:limit]
    return results


def _quality_evaluation(candidate: dict[str, Any]) -> dict[str, Any]:
    from core.lesson_quality import evaluate_lesson_candidate

    return evaluate_lesson_candidate(candidate)


def _quality_status(evaluation: dict[str, Any]) -> str:
    return "blocked" if evaluation.get("promotion") == "blocked" else "candidate"


def _has_unsafe_changes(candidate: dict[str, Any]) -> bool:
    if _as_str_list(candidate.get("touched_forbidden_files")):
        return True

    from core.patch_safety import evaluate_patch_safety

    safety = evaluate_patch_safety(candidate.get("changed_files") or [])
    return not bool(safety.get("ok"))


def _save_lesson_candidate(
    candidate: dict[str, Any],
    *,
    source_report: str,
    repo_path: str | None = None,
) -> dict[str, Any]:
    from core import lesson_store

    title = f"Benchmark report lesson: {candidate.get('case_name')}"
    summary = candidate.get("patch_summary") or ""
    case_name = candidate.get("case_name") or None
    tags = lesson_store.derive_lesson_tags(
        candidate,
        case_name=case_name,
        title=title,
        summary=summary,
    )

    previous_auto_active = getattr(lesson_store.config, "LESSON_AUTO_ACTIVE", False)
    lesson_store.config.LESSON_AUTO_ACTIVE = False
    try:
        return lesson_store.save_candidate_lesson(
            candidate,
            source=SOURCE,
            source_report=source_report,
            case_name=case_name,
            title=title,
            summary=summary,
            tags=tags,
            repo_path=repo_path,
        )
    finally:
        lesson_store.config.LESSON_AUTO_ACTIVE = previous_auto_active


def _new_summary(report_path: Path, *, dry_run: bool) -> dict[str, Any]:
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": SOURCE,
        "source_report": report_path.name,
        "source_report_path": str(report_path),
        "dry_run": dry_run,
        "counts": {
            "created": 0,
            "blocked": 0,
            "skipped": 0,
            "duplicates": 0,
            "dry_run": 0,
        },
        "created": [],
        "blocked": [],
        "skipped": [],
        "duplicates": [],
        "dry_run_items": [],
        "summary_files": {},
    }


def _append_lesson_summary(summary: dict[str, Any], lesson: dict[str, Any]) -> None:
    entry = {
        "case_name": lesson.get("case_name"),
        "lesson_id": lesson.get("id"),
        "status": lesson.get("status"),
        "promotion": (lesson.get("evaluation") or {}).get("promotion"),
        "source_key": ((lesson.get("candidate") or {}).get("source_key")),
    }
    if lesson.get("status") == "blocked":
        summary["counts"]["blocked"] += 1
        summary["blocked"].append(entry)
    else:
        summary["counts"]["created"] += 1
        summary["created"].append(entry)


def _skip(summary: dict[str, Any], case_name: str | None, reason: str) -> None:
    summary["counts"]["skipped"] += 1
    summary["skipped"].append({"case_name": case_name, "reason": reason})


def seed_lessons_from_report(
    report_path: str | Path,
    *,
    case_name: str | None = None,
    limit: int | None = None,
    dry_run: bool = False,
    repo_path: str | None = None,
    write_json_summary: bool = False,
    write_markdown_summary: bool = False,
    reports_root: str | Path | None = None,
) -> dict[str, Any]:
    if limit is not None and limit < 0:
        raise ValueError("--limit must be >= 0")

    path = Path(report_path).resolve()
    report = _load_json_object(path)
    summary = _new_summary(path, dry_run=dry_run)
    existing_keys = _existing_source_keys(repo_path=repo_path)

    for result in _selected_results(report, case_name=case_name, limit=limit):
        result_name = _as_str(result.get("name") or result.get("case_name")) or None
        if result.get("skipped"):
            _skip(summary, result_name, "benchmark_case_skipped")
            continue

        candidate, skip_reason = _build_candidate(result, source_report=path.name)
        if candidate is None:
            _skip(summary, result_name, skip_reason or "invalid_candidate")
            continue

        source_key = candidate.get("source_key")
        if isinstance(source_key, str) and source_key in existing_keys:
            summary["counts"]["duplicates"] += 1
            summary["duplicates"].append(
                {
                    "case_name": candidate.get("case_name"),
                    "source_key": source_key,
                }
            )
            continue

        evaluation = _quality_evaluation(candidate)
        promotion = evaluation.get("promotion")
        failed_case = candidate.get("benchmark_status") == "failed"
        unsafe_changes = _has_unsafe_changes(candidate)

        if failed_case and promotion != "blocked":
            _skip(summary, candidate.get("case_name"), "failed_case_not_blocked_by_quality")
            continue
        if unsafe_changes and promotion != "blocked":
            _skip(summary, candidate.get("case_name"), "unsafe_changes_not_blocked_by_quality")
            continue

        if dry_run:
            summary["counts"]["dry_run"] += 1
            summary["dry_run_items"].append(
                {
                    "case_name": candidate.get("case_name"),
                    "source_key": source_key,
                    "would_status": _quality_status(evaluation),
                    "promotion": promotion,
                }
            )
            continue

        lesson = _save_lesson_candidate(
            candidate,
            source_report=path.name,
            repo_path=repo_path,
        )
        _append_lesson_summary(summary, lesson)
        if isinstance(source_key, str):
            existing_keys.add(source_key)

    if write_json_summary or write_markdown_summary:
        written = write_summary_files(
            summary,
            reports_root=reports_root or DEFAULT_REPORTS_ROOT,
            output_json=write_json_summary,
            output_markdown=write_markdown_summary,
        )
        summary["summary_files"].update(written)

    return summary


def _summary_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")


def render_markdown_summary(summary: dict[str, Any]) -> str:
    counts = summary.get("counts") or {}
    lines = [
        "# Lesson Seed Report",
        "",
        f"- Source report: `{summary.get('source_report')}`",
        f"- Dry run: {bool(summary.get('dry_run'))}",
        f"- Created: {counts.get('created', 0)}",
        f"- Blocked: {counts.get('blocked', 0)}",
        f"- Skipped: {counts.get('skipped', 0)}",
        f"- Duplicates: {counts.get('duplicates', 0)}",
        f"- Dry-run candidates: {counts.get('dry_run', 0)}",
        "",
    ]

    for section, title in (
        ("created", "Created"),
        ("blocked", "Blocked"),
        ("duplicates", "Duplicates"),
        ("skipped", "Skipped"),
        ("dry_run_items", "Dry Run"),
    ):
        items = summary.get(section) or []
        if not items:
            continue
        lines.extend([f"## {title}", ""])
        for item in items:
            case = item.get("case_name") or "(unknown)"
            detail = item.get("lesson_id") or item.get("reason") or item.get("would_status")
            lines.append(f"- `{case}`: {detail}")
        lines.append("")

    return "\n".join(lines)


def write_summary_files(
    summary: dict[str, Any],
    *,
    reports_root: str | Path = DEFAULT_REPORTS_ROOT,
    output_json: bool = False,
    output_markdown: bool = False,
) -> dict[str, str]:
    root = Path(reports_root)
    root.mkdir(parents=True, exist_ok=True)
    ts = _summary_timestamp()
    written: dict[str, str] = {}

    if output_json:
        path = root / f"lesson_seed_report_{ts}.json"
        path.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        written["json"] = str(path)

    if output_markdown:
        path = root / f"lesson_seed_report_{ts}.md"
        path.write_text(render_markdown_summary(summary), encoding="utf-8")
        written["markdown"] = str(path)

    return written


def print_summary(summary: dict[str, Any]) -> None:
    counts = summary.get("counts") or {}
    print(f"Source report: {summary.get('source_report')}")
    print(f"Created: {counts.get('created', 0)}")
    print(f"Blocked: {counts.get('blocked', 0)}")
    print(f"Skipped: {counts.get('skipped', 0)}")
    print(f"Duplicates: {counts.get('duplicates', 0)}")
    if summary.get("dry_run"):
        print(f"Dry-run candidates: {counts.get('dry_run', 0)}")

    for key, label in (
        ("created", "created"),
        ("blocked", "blocked"),
        ("duplicates", "duplicate"),
        ("skipped", "skipped"),
        ("dry_run_items", "dry-run"),
    ):
        for item in summary.get(key) or []:
            case = item.get("case_name") or "(unknown)"
            detail = (
                item.get("lesson_id")
                or item.get("reason")
                or item.get("would_status")
                or item.get("source_key")
                or ""
            )
            print(f"  {label}: {case} {detail}".rstrip())

    files = summary.get("summary_files") or {}
    if files.get("json"):
        print(f"JSON summary: {files['json']}")
    if files.get("markdown"):
        print(f"Markdown summary: {files['markdown']}")


def _main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Create lesson candidates from existing benchmark reports.",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--latest",
        action="store_true",
        help="Use the newest benchmark_report_*.json in .agent/benchmarks/.",
    )
    source.add_argument(
        "--report",
        help="Benchmark report filename under .agent/benchmarks/.",
    )
    parser.add_argument("--case", dest="case_name", help="Only seed one case name.")
    parser.add_argument("--limit", type=int, help="Seed at most N selected cases.")
    parser.add_argument("--dry-run", action="store_true", help="Do not write lessons.")
    parser.add_argument(
        "--json-summary",
        action="store_true",
        help="Write .agent/reports/lesson_seed_report_*.json.",
    )
    parser.add_argument(
        "--markdown-summary",
        action="store_true",
        help="Write .agent/reports/lesson_seed_report_*.md.",
    )
    args = parser.parse_args(argv)

    try:
        report_path = (
            _latest_report_path()
            if args.latest
            else _resolve_report_name(args.report or "")
        )
        summary = seed_lessons_from_report(
            report_path,
            case_name=args.case_name,
            limit=args.limit,
            dry_run=args.dry_run,
            write_json_summary=args.json_summary,
            write_markdown_summary=args.markdown_summary,
        )
    except ValueError as e:
        print(f"[lesson_seed] error: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(
            f"[lesson_seed] unexpected {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        return 1

    print_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
