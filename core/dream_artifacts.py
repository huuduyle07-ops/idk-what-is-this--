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

    return {
        "report_dir": str(report_dir),
        "morning_report": morning,
        "items": items,
        "patch_style": patch_style,
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


def slugify(text: str, max_len: int = 40) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text or "").strip("-").lower()
    return s[:max_len] or "untitled"


def item_dir(report_dir: Path, idx: int, title: str) -> Path:
    return report_dir / f"{idx:02d}-{slugify(title)}"


def write_report_markdown(report_dir: Path, items: list[dict]) -> Path:
    lines: list[str] = [
        f"# Morning report — {datetime.now():%Y-%m-%d %H:%M}",
        "",
        f"Total items: {len(items)}",
        "",
    ]

    status_counts: dict[str, int] = {}
    for it in items:
        st = it.get("status", "unknown")
        status_counts[st] = status_counts.get(st, 0) + 1

    if status_counts:
        lines.append("## Summary")
        for st, count in sorted(status_counts.items()):
            lines.append(f"- {st}: {count}")
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
