"""Web-facing summary helpers for benchmark reports (Phase 5 Slice 3).

The CLI summarizers in benchmarks/run_benchmarks.py (`summarize_report` etc.)
print to stdout. The web UI needs structured data, so this module reads the
JSON reports and returns dicts safe to serialize.

All file lookups are scoped to <repo_path>/.agent/benchmarks/. Filenames are
validated against a regex AND resolved+checked-against the bench dir to
prevent path-traversal via the web routes.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

_FILENAME_RE = re.compile(r"^benchmark_report_(\d+)\.json$")
_META_FILENAME = "history_meta.json"


def _bench_dir(repo_path: str | Path) -> Path:
    return Path(repo_path).resolve() / ".agent" / "benchmarks"


def _meta_path(repo_path: str | Path) -> Path:
    return _bench_dir(repo_path) / _META_FILENAME


def read_benchmark_meta(repo_path: str | Path) -> dict:
    path = _meta_path(repo_path)
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_benchmark_meta(repo_path: str | Path, meta: dict) -> None:
    path = _meta_path(repo_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def update_benchmark_entry(repo_path: str | Path, filename: str, **fields) -> dict:
    meta = read_benchmark_meta(repo_path)
    entry = dict(meta.get(filename, {}))
    entry.update(fields)
    meta[filename] = entry
    write_benchmark_meta(repo_path, meta)
    return entry


def _summarize_one(path: Path) -> dict | None:
    """Return a small metadata dict for one report file. Returns None if the
    filename doesn't match the expected pattern OR the JSON can't be parsed
    (silently skipped in lists)."""
    m = _FILENAME_RE.match(path.name)
    if not m:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    ts = int(m.group(1))
    iso = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    return {
        "filename": path.name,
        "timestamp_epoch": ts,
        "timestamp_iso": iso,
        "total": data.get("total", 0),
        "passed": data.get("passed", 0),
        "failed": data.get("failed", 0),
        "skipped": data.get("skipped", 0),
        "success_rate": data.get("success_rate", 0),
        "duration_sec": data.get("duration_sec", 0),
        "total_tokens": data.get("total_tokens", 0),
        "total_estimated_cost_usd": data.get("total_estimated_cost_usd", 0),
    }


def list_benchmark_reports(
    repo_path: str | Path,
    include_archived: bool = False,
) -> list[dict]:
    """All benchmark reports for a repo, newest first.

    Returns an empty list if .agent/benchmarks/ doesn't exist or contains no
    parseable reports. Entries with deleted=True are always hidden.
    Entries with archived=True are hidden unless include_archived is set."""
    bench_dir = _bench_dir(repo_path)
    if not bench_dir.is_dir():
        return []
    meta = read_benchmark_meta(repo_path)
    summaries: list[dict] = []
    for p in bench_dir.glob("benchmark_report_*.json"):
        s = _summarize_one(p)
        if s is None:
            continue
        entry = meta.get(s["filename"], {})
        s["archived"] = bool(entry.get("archived", False))
        s["pinned"] = bool(entry.get("pinned", False))
        s["deleted"] = bool(entry.get("deleted", False))
        if s["deleted"]:
            continue
        if s["archived"] and not include_archived:
            continue
        summaries.append(s)
    summaries.sort(key=lambda s: s["timestamp_epoch"], reverse=True)
    return summaries


def read_benchmark_report(repo_path: str | Path, filename: str) -> dict | None:
    """Return the full JSON of one report, or None if not found / invalid name.

    Filename validation prevents path traversal: must match
    `benchmark_report_<digits>.json` AND resolve to a file inside the bench
    dir. Anything else returns None.
    """
    if not _FILENAME_RE.match(filename):
        return None
    bench_dir = _bench_dir(repo_path)
    target = (bench_dir / filename).resolve()
    try:
        target.relative_to(bench_dir.resolve())
    except ValueError:
        return None
    if not target.is_file():
        return None
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return None
