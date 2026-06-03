from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime
from pathlib import Path

from config import get_agent_dir


def dreams_root(repo_path: str) -> Path:
    return get_agent_dir(repo_path) / "dreams"


def queue_path(repo_path: str) -> Path:
    return dreams_root(repo_path) / "queue.json"


def today_dir(repo_path: str) -> Path:
    """Legacy: returns just the date dir (no run subdir).

    Kept for backward compatibility with tests that monkey-patch this.
    New runs use `new_run_dir()` (Slice γ.3.1) for per-run isolation.
    """
    return dreams_root(repo_path) / datetime.now().strftime("%Y-%m-%d")


def new_run_dir(repo_path: str) -> Path:
    """Slice γ.3.1: create a fresh per-run directory under today's date dir.

    Path shape: <dreams_root>/<YYYY-MM-DD>/<HHMMSS-run>/

    Each Dream run gets its own isolated artifact directory so multiple
    runs on the same day can't mix `refined_passN` / `refinement_raw_passN`
    / item subdirs between them.

    If the second-resolution timestamp collides (rare — two runs started
    within the same second), appends `-1`, `-2`, ... to disambiguate.

    Always returns an existing directory (parents created if needed).
    """
    now = datetime.now()
    date_dir = dreams_root(repo_path) / now.strftime("%Y-%m-%d")
    base_name = now.strftime("%H%M%S-run")
    candidate = date_dir / base_name
    suffix = 0
    while candidate.exists():
        suffix += 1
        candidate = date_dir / f"{base_name}-{suffix}"
    candidate.mkdir(parents=True, exist_ok=True)
    return candidate


def _iter_report_dirs(repo_path: str) -> list[tuple[str, str | None, Path]]:
    """Slice γ.3.1: yield (date_str, run_id_or_None, report_dir_path) for every
    Dream run that has a `list.json`. Supports BOTH layouts:

      - new (γ.3.1+): <dreams>/<YYYY-MM-DD>/<HHMMSS-run>/list.json
      - legacy: <dreams>/<YYYY-MM-DD>/list.json (pre-γ.3.1 runs)

    Returned list is sorted newest-first by (date_str, run_id or '').
    """
    root = dreams_root(repo_path)
    if not root.exists():
        return []
    entries: list[tuple[str, str | None, Path]] = []
    for date_p in root.iterdir():
        if not date_p.is_dir():
            continue
        date_name = date_p.name
        # New layout: timestamped subdirs.
        for run_p in date_p.iterdir():
            if run_p.is_dir() and (run_p / "list.json").exists():
                entries.append((date_name, run_p.name, run_p))
        # Legacy layout: list.json directly under the date dir.
        if (date_p / "list.json").exists():
            entries.append((date_name, None, date_p))
    # Sort newest-first. None run_id sorts before any timestamp; for legacy
    # entries we want them at the END within a date (so the new runs of the
    # same day appear first). Hack: treat None as empty string.
    entries.sort(key=lambda e: (e[0], e[1] or ""), reverse=True)
    return entries


def latest_report_dir(repo_path: str) -> Path | None:
    entries = _iter_report_dirs(repo_path)
    return entries[0][2] if entries else None

def _benchmark_seed_key(item: dict) -> tuple:
    return (
        item.get("source"),
        item.get("benchmark_report"),
        item.get("case_name"),
        item.get("kind"),
    )


def _first_successful_retry_attempt(result: dict) -> int | None:
    retries = result.get("retry_results")
    if isinstance(retries, list):
        for attempt in retries:
            if not isinstance(attempt, dict):
                continue
            if attempt.get("success") is True and attempt.get("attempt") is not None:
                try:
                    return int(attempt["attempt"])
                except (TypeError, ValueError):
                    return None

    if result.get("success") is True and result.get("attempts") is not None:
        try:
            return int(result["attempts"])
        except (TypeError, ValueError):
            return None

    return None


def _total_attempts(result: dict) -> int | None:
    if result.get("attempts") is not None:
        try:
            return int(result["attempts"])
        except (TypeError, ValueError):
            return None

    retries = result.get("retry_results")
    if isinstance(retries, list) and retries:
        return len(retries)

    return None


def _flaky_case_item(result: dict, report_name: str) -> dict:
    case_name = result.get("name") or "?"
    passed_attempt = _first_successful_retry_attempt(result)
    attempts = _total_attempts(result)
    attempt_label = (
        f"{passed_attempt if passed_attempt is not None else '?'}/"
        f"{attempts if attempts is not None else '?'}"
    )

    item = {
        "kind": "bug",
        "title": f"Flaky case: {case_name}",
        "hint": (
            f"Case passed on retry attempt {attempt_label}. Investigate model "
            "pressure, prompt instability, or case fragility."
        ),
        "source": "benchmark",
        "benchmark_report": report_name,
        "case_name": case_name,
        "flaky": True,
        "attempts": attempts,
    }

    retries = result.get("retry_results")
    if isinstance(retries, list):
        item["retry_results"] = retries

    return item


def list_all_reports(repo_path: str) -> list[dict]:
    """All past dream runs for this repo, newest first.

    Slice γ.3.1: each entry now has BOTH `date` (YYYY-MM-DD) and `run_id`
    (HHMMSS-run, or None for legacy reports without a run subdir). The web
    sidebar uses both to identify a specific run; the `/dream/report` route
    accepts an optional `run` query param matching `run_id`.

    Each entry is a small summary dict suitable for the sidebar:
      {date, run_id, report_dir, item_count, statuses: {<status>: <count>},
       patch_style, dream_mode, completed_at}
    """
    summaries: list[dict] = []
    for date_str, run_id, report_dir in _iter_report_dirs(repo_path):
        list_path = report_dir / "list.json"
        try:
            data = json.loads(list_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        items = data.get("items", []) or []
        statuses: dict[str, int] = {}
        for it in items:
            st = it.get("status", "unknown")
            statuses[st] = statuses.get(st, 0) + 1

        summaries.append({
            "date": date_str,
            "run_id": run_id,
            "report_dir": str(report_dir),
            "item_count": len(items),
            "statuses": statuses,
            "patch_style": data.get("patch_style"),
            "dream_mode": data.get("dream_mode"),
            "completed_at": data.get("completed_at"),
        })
    return summaries


def read_report(report_dir: Path) -> dict:
    """Full content of one dream run for the report viewer."""
    # Prefer the new .md file; fall back to legacy .txt for pre-rename run dirs.
    _summary_path = report_dir / "dream_run_summary.md"
    if not _summary_path.exists():
        _summary_path = report_dir / "morning_report.txt"

    list_path = report_dir / "list.json"
    case_ideas_path = report_dir / "case_ideas.json"

    morning = ""
    if _summary_path.exists():
        try:
            morning = _summary_path.read_text(encoding="utf-8")
        except Exception:
            morning = ""

    items: list[dict] = []
    patch_style = None
    completed_at = None
    dream_mode = None
    if list_path.exists():
        try:
            data = json.loads(list_path.read_text(encoding="utf-8"))
            items = data.get("items", []) or []
            patch_style = data.get("patch_style")
            completed_at = data.get("completed_at")
            dream_mode = data.get("dream_mode")
        except Exception:
            pass

    items = enrich_report_patch_blockers(report_dir, items, dream_mode)
    case_ideas_payload: dict = {}
    if case_ideas_path.exists():
        try:
            parsed_case_ideas = json.loads(case_ideas_path.read_text(encoding="utf-8"))
            if isinstance(parsed_case_ideas, dict):
                case_ideas_payload = parsed_case_ideas
        except Exception:
            case_ideas_payload = {}

    return {
        "report_dir": str(report_dir),
        "morning_report": morning,
        "items": items,
        "patch_style": patch_style,
        "dream_mode": dream_mode,
        "completed_at": completed_at,
        "case_ideas": case_ideas_payload.get("case_ideas", []),
        "case_ideas_message": case_ideas_payload.get("message", ""),
        "lesson_notes": case_ideas_payload.get("lesson_notes", []),
    }


def _report_item_dir(report_dir: Path, item: dict) -> Path | None:
    item_dir_name = item.get("item_dir_name")
    if item_dir_name:
        candidate = (report_dir / str(item_dir_name)).resolve()
    else:
        idx = item.get("idx")
        if not isinstance(idx, int):
            return None
        candidate = item_dir(report_dir, idx, item.get("title", "")).resolve()
    try:
        candidate.relative_to(report_dir.resolve())
    except ValueError:
        return None
    return candidate


def _chosen_plan_artifact_name(item: dict) -> str:
    preferred = item.get("preferred_artifact")
    if item.get("preferred_artifact_kind") == "plan" and isinstance(preferred, str):
        try:
            kind, artifact = validate_preferred_artifact_name(preferred)
        except ValueError:
            return "plan_analysis.json"
        if kind == "plan":
            return artifact
    return "plan_analysis.json"


def read_item_plan_analysis(report_dir: Path, item: dict) -> dict | None:
    item_dir_path = _report_item_dir(report_dir, item)
    if item_dir_path is None:
        return None

    plan_path = item_dir_path / _chosen_plan_artifact_name(item)
    if not plan_path.is_file():
        return None
    try:
        parsed = json.loads(plan_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def enrich_report_patch_blockers(
    report_dir: Path,
    items: list[dict],
    dream_mode: str | None = None,
) -> list[dict]:
    enriched: list[dict] = []
    for raw_item in items:
        if not isinstance(raw_item, dict):
            continue
        item = dict(raw_item)
        status = item.get("status")
        refreshable_status = status in {
            "planned_no_patch",
            "patch_skipped_needs_vibe",
            "needs_manual_review",
            "blocked_missing_context",
        }
        should_refresh = (
            (refreshable_status and not item.get("patch_blockers"))
            or item.get("preferred_artifact_kind") == "plan"
        )
        if should_refresh:
            plan = read_item_plan_analysis(report_dir, item)
            plan_context = dict(plan) if isinstance(plan, dict) else {}
            if dream_mode and plan_context:
                plan_context["dream_mode"] = dream_mode
            attach_patch_blockers(item, plan_context)
        enriched.append(item)
    return enriched


def read_queue(repo_path: str) -> list[dict]:
    path = queue_path(repo_path)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return data if isinstance(data, list) else []


def write_queue(repo_path: str, items: list[dict]) -> None:
    path = queue_path(repo_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(items, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def append_to_queue(repo_path: str, item: dict) -> list[dict]:
    items = read_queue(repo_path)
    items.append(item)
    write_queue(repo_path, items)
    return items


def clear_queue(repo_path: str) -> None:
    write_queue(repo_path, [])


def seed_queue_from_latest_benchmark(
    repo_path: str | Path,
    max_failed: int = 5,
    max_slow: int = 3,
    min_total: int = 5,
    report_filename: str | None = None,
) -> list[dict]:
    """Seed the dream queue with items derived from a benchmark report.

    By default reads `<repo_path>/.agent/benchmarks/benchmark_report_*.json`
    and picks the newest report whose `total >= min_total` (skips one-off
    test runs like `total=1`); falls back to the absolute newest if no
    report meets `min_total`.

    If `report_filename` is provided (Phase 5 Slice 3), seeds from that
    specific report instead. Filename is validated against the
    `benchmark_report_*.json` pattern AND must resolve to a file inside
    the bench dir (path-traversal guard).

    From the chosen report:
      - failed cases (`results[i].success == False`) become `kind="bug"` items
        (up to `max_failed`)
      - flaky cases (`results[i].flaky == True`) become `kind="bug"` items
      - top slowest passing cases (from `slowest_cases[]`) become `kind="debt"`
        items (up to `max_slow`)

    Each item carries `source="benchmark"`, `benchmark_report` (filename), and
    `case_name` for traceability. Items are appended to the existing queue via
    `append_to_queue()`.

    Returns the list of items appended (empty if no benchmark report is
    available, or the report has nothing seedable).
    """
    bench_dir = Path(repo_path).resolve() / ".agent" / "benchmarks"
    if not bench_dir.is_dir():
        return []

    chosen: Path | None = None

    if report_filename:
        # Explicit-filename path: validate and use that report directly.
        if not re.match(r"^benchmark_report_\d+\.json$", report_filename):
            return []
        candidate = (bench_dir / report_filename).resolve()
        try:
            candidate.relative_to(bench_dir.resolve())
        except ValueError:
            return []
        if not candidate.is_file():
            return []
        chosen = candidate
    else:
        reports = sorted(bench_dir.glob("benchmark_report_*.json"))
        if not reports:
            return []

        # Prefer newest report with total >= min_total; fall back to newest overall.
        for path in reversed(reports):
            try:
                d = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if (d.get("total") or 0) >= min_total:
                chosen = path
                break
        if chosen is None:
            chosen = reports[-1]

    try:
        data = json.loads(chosen.read_text(encoding="utf-8"))
    except Exception:
        return []

    items: list[dict] = []

    # Failed cases → bug items.
    for r in (data.get("results") or []):
        if r.get("success"):
            continue
        if len(items) >= max_failed:
            break
        reason_bits: list[str] = []
        val_out = r.get("validation_output") or ""
        if val_out and val_out != "OK":
            reason_bits.append(f"validation: {val_out[:200]}")
        if r.get("missing_expected_files"):
            reason_bits.append(f"missing: {r['missing_expected_files']}")
        if r.get("toolchain_issue"):
            reason_bits.append(f"toolchain: {r['toolchain_issue']}")
        items.append({
            "kind": "bug",
            "title": f"Benchmark failure: {r.get('name', '?')}",
            "hint": "; ".join(reason_bits) or "see runner_log_tail in benchmark report",
            "source": "benchmark",
            "benchmark_report": chosen.name,
            "case_name": r.get("name"),
        })

    # Flaky cases -> bug items. Keep separate from failures so retry instability
    # is visible even when the final report status is passing.
    for r in (data.get("results") or []):
        if r.get("flaky") is not True:
            continue
        items.append(_flaky_case_item(r, chosen.name))

    # Slowest passing cases -> debt items.
    for s in (data.get("slowest_cases") or [])[:max_slow]:
        if not s.get("success"):
            continue
        name = s.get("name", "?")
        dur = s.get("duration_sec", 0) or 0
        items.append({
            "kind": "debt",
            "title": f"Slow case: {name} ({dur:.1f}s)",
            "hint": f"Investigate why {name} takes {dur:.1f}s to patch.",
            "source": "benchmark",
            "benchmark_report": chosen.name,
            "case_name": name,
        })

    # Dedupe against existing queue: skip benchmark-seeded items that match
    # (source, benchmark_report, case_name, kind) of something already queued.
    # Re-clicking "Seed from latest benchmark" or "Seed from this report" thus
    # becomes idempotent, which is what users expect.
    existing_queue = read_queue(repo_path)
    existing_keys = {
        _benchmark_seed_key(it)
        for it in existing_queue
        if it.get("source") == "benchmark"
    }

    deduped_items: list[dict] = []
    for it in items:
        key = _benchmark_seed_key(it)
        if key in existing_keys:
            continue
        deduped_items.append(it)
        existing_keys.add(key)

    for it in deduped_items:
        append_to_queue(repo_path, it)

    return deduped_items


def slugify(text: str, max_len: int = 40) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text or "").strip("-").lower()
    return s[:max_len] or "untitled"


def item_dir(report_dir: Path, idx: int, title: str) -> Path:
    return report_dir / f"{idx:02d}-{slugify(title)}"


def _json_evidence(value) -> str:
    try:
        rendered = json.dumps(value, ensure_ascii=False)
    except TypeError:
        rendered = str(value)
    return rendered[:240]


def _context_value(item: dict, plan: dict | None, key: str, default=None):
    if isinstance(plan, dict) and key in plan:
        return plan.get(key)
    return item.get(key, default)


def _is_false_value(value) -> bool:
    if value is False:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"false", "no", "0"}
    return False


def _as_nonempty_list(value) -> list:
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    if isinstance(value, (list, tuple, set)):
        return [v for v in value if str(v or "").strip()]
    return []


_VAGUE_FILE_VALUES = {
    ".",
    "./",
    "unknown",
    "n/a",
    "na",
    "none",
    "null",
    "tbd",
    "todo",
    "various",
    "multiple",
    "repo",
    "repository",
    "project",
    "codebase",
    "source",
    "src",
    "app",
    "core",
    "tests",
    "test",
    "files",
    "file",
}

_VAGUE_FILE_SUBSTRINGS = (
    "unknown",
    "tbd",
    "todo",
    "various",
    "multiple",
    "relevant",
    "appropriate",
    "likely",
    "target file",
    "path/to",
    "relative/path",
    "...",
    "*",
)

_KNOWN_EXTENSIONLESS_FILES = {
    "dockerfile",
    "makefile",
    "rakefile",
    "gemfile",
    "procfile",
    "license",
    "readme",
}


def _is_vague_likely_file(path_value) -> bool:
    path = str(path_value or "").strip().strip("`'\"").replace("\\", "/")
    lower = path.lower()
    if not lower or lower in _VAGUE_FILE_VALUES:
        return True
    if lower.endswith("/"):
        return True
    if any(marker in lower for marker in _VAGUE_FILE_SUBSTRINGS):
        return True

    final = lower.rsplit("/", 1)[-1]
    if final in _VAGUE_FILE_VALUES:
        return True

    # A lone directory-ish token is not enough to safely target a patch.
    if "/" not in lower and "." not in final and final not in _KNOWN_EXTENSIONLESS_FILES:
        return True
    return False


def _has_patch_payload(item: dict, plan: dict | None) -> bool:
    for key in ("patch_plan", "patch_candidate"):
        value = _context_value(item, plan, key)
        if isinstance(value, list) and value:
            return True
        if isinstance(value, dict) and value:
            return True
    return False


_DREAM_BLOCKER_OVERRIDE_HINTS: dict[str, str] = {
    "safe_to_patch_false": (
        "Default policy holds the patch because the planner marked it unsafe. "
        "Future override: re-run the Dream item with `patch_if_safe` after the "
        "planner reclassifies, or open the patch manually with explicit human "
        "approval."
    ),
    "missing_validation_command": (
        "Default policy refuses to auto-patch without a validation command — "
        "there would be no way to detect regressions. "
        "Future override: attach a `validation_commands` entry to the plan and "
        "re-run."
    ),
    "target_file_uncertain": (
        "Default policy will not guess a target file. "
        "Future override: pin `likely_files` in the plan item before retrying."
    ),
    "patch_style_none": (
        "Default policy respects the planner's `patch_style_required=none` "
        "verdict. Future override: change the required style in the plan item, "
        "or apply the change manually."
    ),
    "needs_manual_review": (
        "Item is paused for a human read. Future override: review the item, "
        "set its status to a runnable value, and re-queue."
    ),
    "blocked_missing_context": (
        "Default policy refuses to patch without the required context. "
        "Future override: provide the missing context (Scout snippets, "
        "validation evidence) and re-run."
    ),
    "vibe_required": (
        "Default policy refuses vibe-style patches unless the user opts in. "
        "Future override: switch the queue item's patch_style to `vibe` with "
        "explicit human approval."
    ),
    "patch_generation_failed": (
        "The model did not return a patch payload. "
        "Future override: retry the item, refine the prompt, or hand-write a "
        "proposal and use the manual lesson CLI."
    ),
}


def dream_blocker_override_hint(code: str) -> str:
    """Public lookup for the override hint attached to a blocker code.

    Unknown codes return an empty string so the UI can simply omit the hint
    block instead of fabricating one.
    """
    return _DREAM_BLOCKER_OVERRIDE_HINTS.get(code, "")


def classify_patch_blockers(item: dict, plan: dict | None = None) -> list[dict]:
    """Explain why a Dream item is not currently ready_to_apply.

    Pure metadata: this helper never calls an LLM, edits artifacts, or changes
    whether a patch is generated/applied.

    Each blocker carries the override_hint paired with its code so the Dream
    UI / proposal.md can tell the human what the default-deny rule is and
    what path (if any) would unlock it.
    """
    blockers: list[dict] = []
    status = str(item.get("status") or "")
    mode = str(
        _context_value(item, plan, "dream_mode")
        or _context_value(item, plan, "mode")
        or ""
    ).strip().lower()

    def add(code: str, message: str, evidence: str) -> None:
        if any(existing.get("code") == code for existing in blockers):
            return
        blockers.append({
            "code": code,
            "message": message,
            "evidence": str(evidence)[:240],
            "override_hint": dream_blocker_override_hint(code),
        })

    safe_value = _context_value(item, plan, "safe_to_patch_now")
    safe_is_false = _is_false_value(safe_value)
    if safe_is_false:
        add(
            "safe_to_patch_false",
            "Planner marked this item as not safe to patch now.",
            f"safe_to_patch_now={safe_value!r}",
        )

    validation_commands = _context_value(item, plan, "validation_commands")
    if mode == "patch_if_safe" and not _as_nonempty_list(validation_commands):
        add(
            "missing_validation_command",
            "No validation command was provided for patch_if_safe.",
            f"validation_commands={_json_evidence(validation_commands)}",
        )

    likely_files = _context_value(item, plan, "likely_files")
    has_likely_files_field = (
        (isinstance(plan, dict) and "likely_files" in plan)
        or "likely_files" in item
    )
    likely_file_values = _as_nonempty_list(likely_files)
    if has_likely_files_field and (
        not likely_file_values
        or all(_is_vague_likely_file(path) for path in likely_file_values)
    ):
        add(
            "target_file_uncertain",
            "No concrete target file was identified.",
            f"likely_files={_json_evidence(likely_files)}",
        )

    patch_style = str(_context_value(item, plan, "patch_style_required") or "").strip().lower()
    if patch_style == "none":
        add(
            "patch_style_none",
            "Planner indicated no patch style is appropriate for this item.",
            "patch_style_required=none",
        )

    if status == "needs_manual_review":
        add(
            "needs_manual_review",
            "Item status requires manual review before patching.",
            "status=needs_manual_review",
        )

    if status == "blocked_missing_context":
        add(
            "blocked_missing_context",
            "Item is blocked because required context is missing.",
            "status=blocked_missing_context",
        )

    if status == "patch_skipped_needs_vibe":
        add(
            "vibe_required",
            "This item requires vibe style before patching.",
            "status=patch_skipped_needs_vibe",
        )

    patch_generation_attempted = bool(
        _context_value(item, plan, "patch_generation_attempted")
        or _context_value(item, plan, "patch_generation_failed")
    )
    if (
        status == "planned_no_patch"
        and mode == "patch_if_safe"
        and not _has_patch_payload(item, plan)
        and (patch_generation_attempted or not safe_is_false)
    ):
        add(
            "patch_generation_failed",
            "Patch generation did not produce a patch_plan or patch_candidate.",
            "mode=patch_if_safe; status=planned_no_patch; patch_plan/patch_candidate missing",
        )

    return blockers


def patch_blocker_summary(blockers: list[dict]) -> str:
    if not blockers:
        return ""
    codes = [str(blocker.get("code") or "unknown") for blocker in blockers]
    shown = ", ".join(codes[:3])
    if len(codes) > 3:
        shown = f"{shown}, +{len(codes) - 3} more"
    return f"why no patch: {shown}"


def attach_patch_blockers(item: dict, plan: dict | None = None) -> dict:
    blockers = classify_patch_blockers(item, plan)
    item["patch_blockers"] = blockers
    item["patch_blocker_summary"] = patch_blocker_summary(blockers)
    return item


STATUS_LEGEND: dict[str, str] = {
    "planned_no_patch": "Plan created; patching not attempted.",
    "ready_to_apply": "Patch validated in sandbox; awaiting user apply.",
    "patch_applied": "Patch applied to repo.",
    "patch_skipped_needs_vibe": "Task type requires vibe style; planned only.",
    "research_note_created": "Proposal markdown written; no patch.",
    "needs_manual_review": "Planner is unsure; human review needed.",
    "blocked_missing_context": "Plan blocked because grounding context is missing.",
    "idea_written": "Free-form design note written (legacy idea-flow).",
    "case_ideas_created": "Reference-study case idea candidates written.",
    "case_idea_no_input": "No reference-study notes were provided.",
    "case_idea_no_ideas": "Reference-study notes produced no case ideas.",
    "rejected": "Patch failed validation after all attempts.",
    "error": "Item crashed during processing.",
    "skipped_time_budget": "Time budget exhausted before reaching this item.",
    "skipped_user_stop": "Run was manually stopped by user before this item.",
}


def _md_cell(value) -> str:
    text = str(value if value is not None else "").replace("\n", " ").strip()
    return text.replace("|", "\\|")


def render_case_ideas_markdown(
    case_ideas: list[dict],
    *,
    message: str = "",
) -> str:
    lines: list[str] = ["# Case Idea Candidates", ""]
    if message:
        lines.extend([message.strip(), ""])
    if not case_ideas:
        lines.append("No case ideas were generated from the provided reference notes.")
        return "\n".join(lines)

    lines.extend([
        "| Pattern | Suggested case | Language | Category | Difficulty | Approved? |",
        "| --- | --- | --- | --- | --- | --- |",
    ])
    for idea in case_ideas:
        approved = "yes" if idea.get("human_approved_for_case_creation") is True else "no"
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_cell(idea.get("pattern")),
                    _md_cell(idea.get("suggested_case_name")),
                    _md_cell(idea.get("language")),
                    _md_cell(idea.get("category")),
                    _md_cell(idea.get("difficulty")),
                    approved,
                ]
            )
            + " |"
        )

    lines.append("")
    lines.append("## Details")
    lines.append("")
    for idea in case_ideas:
        name = _md_cell(idea.get("suggested_case_name") or "unnamed_case")
        lines.append(f"### {name}")
        for label, key in (
            ("Pattern", "pattern"),
            ("Why it matters", "why_it_matters"),
            ("Minimal experiment", "minimal_experiment"),
            ("Expected wrong agent behavior", "expected_wrong_agent_behavior"),
        ):
            value = str(idea.get(key) or "").strip()
            if value:
                lines.append(f"- **{label}:** {value}")
        lines.append("- **Human approved for case creation:** false")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_case_idea_artifacts(
    report_dir: Path,
    case_ideas: list[dict],
    *,
    lesson_notes: list[str] | None = None,
    message: str = "",
) -> dict:
    report_dir.mkdir(parents=True, exist_ok=True)
    notes = [str(note).strip() for note in (lesson_notes or []) if str(note).strip()]
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source": "dream_reference_study",
        "message": message,
        "case_ideas": case_ideas,
        "lesson_notes": notes,
    }
    json_path = report_dir / "case_ideas.json"
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    md_path = report_dir / "case_ideas.md"
    md_path.write_text(
        render_case_ideas_markdown(case_ideas, message=message),
        encoding="utf-8",
    )

    lessons_path = None
    if notes:
        lessons_path = report_dir / "LESSONS_LEARNED.md"
        lines = [
            "# Lessons Learned Draft",
            "",
            "Draft notes from reference-study case-idea mode. These are not seeded lessons.",
            "",
        ]
        for note in notes:
            lines.append(f"- {note}")
        lessons_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return {
        "json": str(json_path),
        "markdown": str(md_path),
        "lessons": str(lessons_path) if lessons_path else None,
    }


def write_report_markdown(
    report_dir: Path,
    items: list[dict],
    dream_mode: str | None = None,
    case_ideas: list[dict] | None = None,
) -> Path:
    lines: list[str] = [
        f"# Morning report — {datetime.now():%Y-%m-%d %H:%M}",
        "",
        f"Total items: {len(items)}",
    ]
    if dream_mode:
        lines.append(f"Dream mode: `{dream_mode}`")
    lines.append("")

    status_counts: dict[str, int] = {}
    for it in items:
        st = it.get("status", "unknown")
        status_counts[st] = status_counts.get(st, 0) + 1

    if status_counts:
        lines.append("## Summary")
        for st, count in sorted(status_counts.items()):
            descr = STATUS_LEGEND.get(st)
            if descr:
                lines.append(f"- **{st}** ({count}) — {descr}")
            else:
                lines.append(f"- **{st}** ({count})")
        lines.append("")

    if case_ideas is not None:
        lines.append("## Case idea candidates")
        lines.append("")
        if case_ideas:
            lines.append("| Pattern | Suggested case | Language | Category | Difficulty | Approved? |")
            lines.append("| --- | --- | --- | --- | --- | --- |")
            for idea in case_ideas:
                approved = "yes" if idea.get("human_approved_for_case_creation") is True else "no"
                lines.append(
                    "| "
                    + " | ".join(
                        [
                            _md_cell(idea.get("pattern")),
                            _md_cell(idea.get("suggested_case_name")),
                            _md_cell(idea.get("language")),
                            _md_cell(idea.get("category")),
                            _md_cell(idea.get("difficulty")),
                            approved,
                        ]
                    )
                    + " |"
                )
        else:
            lines.append("No case ideas were generated from the provided reference notes.")
        lines.append("")

    lines.append("## Items")
    lines.append("")
    for it in items:
        idx = it.get("idx", "?")
        kind = it.get("kind", "?")
        title = it.get("title", "?")
        status = it.get("status", "?")
        summary = it.get("summary", "")
        artifacts = it.get("item_dir_name", "")

        lines.append(f"### {idx}. [{kind}] {title}")
        lines.append(f"- status: **{status}**")
        if summary:
            lines.append(f"- summary: {summary}")
        blockers = it.get("patch_blockers") or []
        if blockers:
            blocker_summary = it.get("patch_blocker_summary") or patch_blocker_summary(blockers)
            lines.append(f"- {blocker_summary}")
            for blocker in blockers:
                code = blocker.get("code", "unknown")
                message = blocker.get("message", "")
                evidence = blocker.get("evidence", "")
                detail = f"  - `{code}`: {message}"
                if evidence:
                    detail += f" ({evidence})"
                lines.append(detail)
        if artifacts:
            lines.append(f"- artifacts: `{artifacts}/`")
        lines.append("")

    out_path = report_dir / "morning_report.txt"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def write_dream_run_summary(
    report_dir: Path,
    items: list[dict],
    dream_mode: str | None = None,
    case_ideas: list[dict] | None = None,
    lesson_notes: list[str] | None = None,
) -> Path:
    """Write dream_run_summary.md — richer successor to morning_report.txt.

    All content is derived deterministically from the already-processed items
    and lesson_notes. No LLM calls, no subprocess, no patch execution.
    """
    lines: list[str] = [
        f"# Dream run summary — {datetime.now():%Y-%m-%d %H:%M}",
        "",
        f"Total items: {len(items)}",
    ]
    if dream_mode:
        lines.append(f"Dream mode: `{dream_mode}`")
    lines.append("")

    status_counts: dict[str, int] = {}
    for it in items:
        st = it.get("status", "unknown")
        status_counts[st] = status_counts.get(st, 0) + 1

    if status_counts:
        lines.append("## Summary")
        for st, count in sorted(status_counts.items()):
            descr = STATUS_LEGEND.get(st)
            if descr:
                lines.append(f"- **{st}** ({count}) — {descr}")
            else:
                lines.append(f"- **{st}** ({count})")
        lines.append("")

    notes = [str(n).strip() for n in (lesson_notes or []) if str(n or "").strip()]
    if notes:
        lines.append("## Candidate lessons")
        lines.append("")
        for note in notes:
            lines.append(f"- {note}")
        lines.append("")

    if case_ideas is not None:
        lines.append("## Case idea candidates")
        lines.append("")
        if case_ideas:
            lines.append("| Pattern | Suggested case | Language | Category | Difficulty | Approved? |")
            lines.append("| --- | --- | --- | --- | --- | --- |")
            for idea in case_ideas:
                approved = "yes" if idea.get("human_approved_for_case_creation") is True else "no"
                lines.append(
                    "| "
                    + " | ".join([
                        _md_cell(idea.get("pattern")),
                        _md_cell(idea.get("suggested_case_name")),
                        _md_cell(idea.get("language")),
                        _md_cell(idea.get("category")),
                        _md_cell(idea.get("difficulty")),
                        approved,
                    ])
                    + " |"
                )
        else:
            lines.append("No case ideas were generated from the provided reference notes.")
        lines.append("")

    lines.append("## Items")
    lines.append("")
    next_steps: list[str] = []
    for it in items:
        idx = it.get("idx", "?")
        kind = it.get("kind", "?")
        title = it.get("title", "?")
        status = it.get("status", "?")
        summary = it.get("summary", "")
        hint = it.get("hint", "")
        item_dir_name = it.get("item_dir_name", "")

        lines.append(f"### {idx}. [{kind}] {title}")
        lines.append(f"- status: **{status}**")
        if summary:
            lines.append(f"- summary: {summary}")
        if hint:
            lines.append(f"- suspected root cause: {hint}")
        if item_dir_name:
            lines.append(f"- evidence: [{item_dir_name}/](./{item_dir_name}/)")

        blockers = it.get("patch_blockers") or []
        if blockers:
            blocker_summary_text = it.get("patch_blocker_summary") or patch_blocker_summary(blockers)
            lines.append(f"- {blocker_summary_text}")
            for blocker in blockers:
                code = blocker.get("code", "unknown")
                message = blocker.get("message", "")
                evidence = blocker.get("evidence", "")
                override_hint = blocker.get("override_hint", "")
                detail = f"  - `{code}`: {message}"
                if evidence:
                    detail += f" ({evidence})"
                lines.append(detail)
                if override_hint:
                    lines.append(f"    - *Override path*: {override_hint}")
                    next_steps.append(f"**{title}** (`{code}`): {override_hint}")
        lines.append("")

    if next_steps:
        lines.append("## Next steps")
        lines.append("")
        for step in next_steps:
            lines.append(f"- {step}")
        lines.append("")
    else:
        lines.append("## Next steps")
        lines.append("")
        lines.append("No unresolved blockers.")
        lines.append("")

    out_path = report_dir / "dream_run_summary.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


# Backward-compat alias — remove once all callers are updated.
write_report_markdown = write_dream_run_summary


# === Slice γ3.2: preferred refined artifact (metadata pointer) ===
#
# Lets the user mark one refined artifact (`plan_analysis.refined_passN.json`
# or `proposal.refined_passN.md`) as the preferred one for an item, by writing
# `preferred_artifact` / `preferred_artifact_kind` fields into the item record
# in list.json. Originals (`plan_analysis.json`, `proposal.md`) are never
# touched; artifact files are never rewritten; this is pure metadata.
#
# Promote vs run-end-of-write is safe: run_overnight writes list.json exactly
# once at the end, and _iter_report_dirs filters by (list.json).exists() at
# core/dream_artifacts.py:73, so a report becomes promotable only AFTER the
# run-end write completes.

_PREFERRED_ARTIFACT_RE = re.compile(
    r"^(?:plan_analysis\.refined_pass\d+\.json|proposal\.refined_pass\d+\.md)$"
)

_PROMOTE_LOCKS: dict[str, threading.Lock] = {}
_PROMOTE_LOCKS_GUARD = threading.Lock()


def _get_promote_lock(report_dir: Path) -> threading.Lock:
    key = str(report_dir.resolve())
    with _PROMOTE_LOCKS_GUARD:
        lock = _PROMOTE_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _PROMOTE_LOCKS[key] = lock
        return lock


def validate_preferred_artifact_name(name: str) -> tuple[str, str]:
    """Strict allow-list for promotable artifact filenames.

    Returns (kind, name) where kind is "plan" or "proposal". Raises ValueError
    on anything else — including originals (`plan_analysis.json`,
    `proposal.md`), refinement raw/error dumps, patch_revalidation files, and
    obvious traversal attempts (`../foo`).
    """
    if not isinstance(name, str) or not _PREFERRED_ARTIFACT_RE.match(name):
        raise ValueError("invalid refined artifact filename")
    kind = "plan" if name.startswith("plan_analysis.") else "proposal"
    return kind, name


def resolve_run_dir(repo_path: str, date: str, run_id: str) -> Path:
    """Compose the report directory for a (date, run_id) under the repo's dreams root.

    Guards against path traversal via `.resolve().relative_to(dreams_root)`.
    Caller is responsible for regex-validating `date` and `run_id` first;
    this helper accepts already-validated values.
    """
    root = dreams_root(repo_path)
    report_dir = (root / date / run_id).resolve()
    try:
        report_dir.relative_to(root.resolve())
    except ValueError:
        raise ValueError("report path escapes dreams root")
    if not report_dir.is_dir():
        raise FileNotFoundError(f"no report for date={date} run={run_id}")
    return report_dir


def load_item_for_promotion(report_dir: Path, item_idx: int) -> tuple[dict, dict]:
    """Read list.json and find the item with matching `idx`.

    Tolerates two shapes:
      - dict with "items": [...]  (current shape, written by run_overnight)
      - raw list [...]            (legacy/test shape)

    Anything else raises RuntimeError. Returns (list_data, item) where
    `list_data` is always a dict (raw lists are wrapped as {"items": [...]}
    in memory so the rest of the pipeline is uniform). `item` is a reference
    into `list_data["items"]`, so caller mutation is visible on writeback.
    """
    list_path = report_dir / "list.json"
    try:
        parsed = json.loads(list_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise
    except Exception:
        raise RuntimeError("failed to parse list.json")

    if isinstance(parsed, dict):
        list_data = parsed
        items = list_data.get("items") or []
        if not isinstance(items, list):
            raise RuntimeError("unexpected list.json shape")
    elif isinstance(parsed, list):
        list_data = {"items": parsed}
        items = parsed
    else:
        raise RuntimeError("unexpected list.json shape")

    for it in items:
        if isinstance(it, dict) and it.get("idx") == item_idx:
            return list_data, it
    raise LookupError(f"item idx {item_idx} not found")


def atomic_write_list_json(report_dir: Path, list_data: dict) -> None:
    """Write list.json atomically via temp file + os.replace.

    On failure, tries to clean up the leftover .tmp file and re-raises so the
    caller can surface a 500. Uses the same formatting as run_overnight.
    """
    final = report_dir / "list.json"
    tmp = report_dir / "list.json.tmp"
    payload = json.dumps(list_data, indent=2, ensure_ascii=False)
    try:
        tmp.write_text(payload, encoding="utf-8")
        os.replace(tmp, final)
    except OSError:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        raise


def promote_artifact(
    repo_path: str,
    date: str,
    run_id: str,
    item_idx: int,
    artifact: str,
) -> dict:
    """Mark one refined artifact as the preferred one for an item.

    Pure metadata operation. No LLM calls, no patching, no artifact writes;
    only `list.json` is rewritten. Caller is responsible for validating
    `date`/`run_id` against the regex (the Flask route does so).
    """
    kind, artifact = validate_preferred_artifact_name(artifact)
    report_dir = resolve_run_dir(repo_path, date, run_id)

    with _get_promote_lock(report_dir):
        list_data, item = load_item_for_promotion(report_dir, item_idx)

        item_dir_name = item.get("item_dir_name")
        if not item_dir_name:
            raise LookupError("item has no item_dir_name")
        item_dir_path = (report_dir / item_dir_name).resolve()
        try:
            item_dir_path.relative_to(report_dir.resolve())
        except ValueError:
            raise ValueError("item_dir_name path escapes report dir")

        artifact_path = (item_dir_path / artifact).resolve()
        try:
            artifact_path.relative_to(item_dir_path)
        except ValueError:
            raise ValueError("artifact path escapes item dir")
        if not artifact_path.is_file():
            raise FileNotFoundError(f"artifact not found: {artifact}")

        item["preferred_artifact"] = artifact
        item["preferred_artifact_kind"] = kind
        atomic_write_list_json(report_dir, list_data)

    return {
        "ok": True,
        "preferred_artifact": artifact,
        "preferred_artifact_kind": kind,
        "item_idx": item_idx,
    }
