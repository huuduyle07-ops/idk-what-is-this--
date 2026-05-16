from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from config import get_agent_dir


def dreams_root(repo_path: str) -> Path:
    return get_agent_dir(repo_path) / "dreams"


def queue_path(repo_path: str) -> Path:
    return dreams_root(repo_path) / "queue.json"


def today_dir(repo_path: str) -> Path:
    return dreams_root(repo_path) / datetime.now().strftime("%Y-%m-%d")


def latest_report_dir(repo_path: str) -> Path | None:
    root = dreams_root(repo_path)
    if not root.exists():
        return None

    candidates = [
        p for p in root.iterdir()
        if p.is_dir() and (p / "list.json").exists()
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.name)

def _benchmark_seed_key(item: dict) -> tuple:
    return (
        item.get("source"),
        item.get("benchmark_report"),
        item.get("case_name"),
        item.get("kind"),
    )

def list_all_reports(repo_path: str) -> list[dict]:
    """All past dream runs for this repo, newest first.

    Each entry is a small summary dict suitable for the sidebar:
      {date, report_dir, item_count, statuses: {<status>: <count>},
       patch_style, completed_at}
    """
    root = dreams_root(repo_path)
    if not root.exists():
        return []

    summaries: list[dict] = []
    for p in sorted(root.iterdir(), key=lambda x: x.name, reverse=True):
        if not p.is_dir():
            continue
        list_path = p / "list.json"
        if not list_path.exists():
            continue
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
            "date": p.name,
            "report_dir": str(p),
            "item_count": len(items),
            "statuses": statuses,
            "patch_style": data.get("patch_style"),
            "dream_mode": data.get("dream_mode"),
            "completed_at": data.get("completed_at"),
        })
    return summaries


def read_report(report_dir: Path) -> dict:
    """Full content of one dream run for the report viewer."""
    morning_path = report_dir / "morning_report.txt"
    list_path = report_dir / "list.json"

    morning = ""
    if morning_path.exists():
        try:
            morning = morning_path.read_text(encoding="utf-8")
        except Exception:
            morning = ""

    items: list[dict] = []
    patch_style = None
    completed_at = None
    if list_path.exists():
        try:
            data = json.loads(list_path.read_text(encoding="utf-8"))
            items = data.get("items", []) or []
            patch_style = data.get("patch_style")
            completed_at = data.get("completed_at")
        except Exception:
            pass

    dream_mode = None
    if list_path.exists():
        try:
            dream_mode = json.loads(list_path.read_text(encoding="utf-8")).get("dream_mode")
        except Exception:
            pass

    return {
        "report_dir": str(report_dir),
        "morning_report": morning,
        "items": items,
        "patch_style": patch_style,
        "dream_mode": dream_mode,
        "completed_at": completed_at,
    }


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

    # Slowest passing cases → debt items.
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


STATUS_LEGEND: dict[str, str] = {
    "planned_no_patch": "Plan created; patching not attempted.",
    "ready_to_apply": "Patch validated in sandbox; awaiting user apply.",
    "patch_applied": "Patch applied to repo.",
    "patch_skipped_needs_vibe": "Task type requires vibe style; planned only.",
    "research_note_created": "Proposal markdown written; no patch.",
    "needs_manual_review": "Planner is unsure; human review needed.",
    "blocked_missing_context": "Plan blocked because grounding context is missing.",
    "idea_written": "Free-form design note written (legacy idea-flow).",
    "rejected": "Patch failed validation after all attempts.",
    "error": "Item crashed during processing.",
    "skipped_time_budget": "Time budget exhausted before reaching this item.",
    "skipped_user_stop": "Run was manually stopped by user before this item.",
}


def write_report_markdown(
    report_dir: Path,
    items: list[dict],
    dream_mode: str | None = None,
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
        if artifacts:
            lines.append(f"- artifacts: `{artifacts}/`")
        lines.append("")

    out_path = report_dir / "morning_report.txt"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path
