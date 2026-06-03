"""Phase 14.2 — Failure Taxonomy Report Export.

Read an existing benchmark report JSON, apply the Phase 14.1 deterministic
failure taxonomy classifier (``core.failure_taxonomy.classify_failure``) to the
*failing* case results, and write a JSON + Markdown failure taxonomy report.

This exporter is read-only with respect to the system under test: it never runs
benchmarks, generates/applies patches, runs validation, promotes lessons, runs
Dream automation, calls a model/API, writes a database, spawns subprocesses,
touches Docker, or makes network calls. The *only* writes it performs are the
two report artifacts it is explicitly asked to produce; it never mutates the
source benchmark report. Nothing here is wired into live benchmark scoring or
the web UI.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.failure_taxonomy import (  # noqa: E402
    CATEGORIES,
    GUARDRAIL_NOTE,
    classify_failure,
)
DEFAULT_OUTPUT_DIR = ".agent/failure_taxonomy"
BENCHMARK_SUBDIR = (".agent", "benchmarks")
BENCHMARK_GLOB = "benchmark_report_*.json"

# Keys under which a benchmark report may hold its per-case result list, in
# precedence order (newest shape first, older shapes after).
_RESULT_KEYS = ("results", "case_results", "cases")


# --- loading / selection ----------------------------------------------------


def load_benchmark_report(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Load a benchmark report JSON. Returns ``(data, error)``.

    ``error`` is a short, friendly reason string when loading fails; ``data``
    is ``None`` in that case. Never raises for the expected failure modes.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None, f"benchmark report not found: {path}"
    except OSError as exc:
        return None, f"could not read benchmark report: {exc}"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON in benchmark report: {exc}"
    if not isinstance(data, dict):
        return None, "benchmark report is not a JSON object"
    return data, None


def _benchmark_report_sort_key(path: Path) -> tuple[int, float, str]:
    """Sort newest-last: prefer the numeric suffix, fall back to mtime."""
    stem = path.stem  # benchmark_report_<suffix>
    suffix = stem.rsplit("_", 1)[-1]
    try:
        numeric = int(suffix)
    except ValueError:
        numeric = -1
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0
    return (numeric, mtime, path.name)


def find_latest_benchmark_report(repo_path: str | Path) -> Path | None:
    """Return the newest ``benchmark_report_*.json`` under the repo, or None."""
    bench_dir = Path(repo_path).joinpath(*BENCHMARK_SUBDIR)
    if not bench_dir.is_dir():
        return None
    paths = sorted(bench_dir.glob(BENCHMARK_GLOB), key=_benchmark_report_sort_key)
    return paths[-1] if paths else None


# --- classification ---------------------------------------------------------


def _iter_case_results(report: dict[str, Any]) -> list[dict[str, Any]]:
    for key in _RESULT_KEYS:
        value = report.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _clearly_passed(case: dict[str, Any]) -> bool:
    for key in ("success", "passed", "ok", "correct"):
        if case.get(key) is True:
            return True
    status = str(case.get("status") or "").lower()
    return status in {"pass", "passed", "ok", "success"}


def _case_name(case: dict[str, Any], index: int) -> str:
    name = str(case.get("name") or "").strip()
    return name or f"case_{index}"


def build_failure_taxonomy(
    report: dict[str, Any],
    *,
    source_path: str,
    generated_at: float,
) -> dict[str, Any]:
    """Build the failure-taxonomy report dict from an already-loaded report.

    Only cases that did not clearly pass are classified — a failure taxonomy
    over passing cases would be meaningless. The loaded ``report`` is never
    mutated.
    """
    cases = _iter_case_results(report)
    classifications: list[dict[str, Any]] = []
    counts: dict[str, int] = {}

    for index, case in enumerate(cases):
        if _clearly_passed(case):
            continue
        # classify_failure copies its input and never mutates it.
        result = classify_failure(case)
        counts[result.category] = counts.get(result.category, 0) + 1
        entry = {"name": _case_name(case, index)}
        for extra in ("language", "category", "difficulty"):
            if case.get(extra) is not None:
                entry[extra] = case.get(extra)
        entry.update(result.to_dict())
        classifications.append(entry)

    ordered_counts = {
        category: counts[category]
        for category in CATEGORIES
        if category in counts
    }

    generated_iso = datetime.fromtimestamp(
        generated_at, tz=timezone.utc
    ).isoformat()

    return {
        "report_kind": "failure_taxonomy",
        "source_benchmark_report": source_path,
        "generated_at": generated_iso,
        "generated_at_epoch": generated_at,
        "total_cases": len(cases),
        "total_classified": len(classifications),
        "counts_by_category": ordered_counts,
        "classifications": classifications,
        "guardrail_note": GUARDRAIL_NOTE,
    }


# --- rendering --------------------------------------------------------------


def render_markdown(taxonomy: dict[str, Any]) -> str:
    counts = taxonomy.get("counts_by_category") or {}
    classifications = taxonomy.get("classifications") or []
    lines = [
        "# Failure Taxonomy Report",
        "",
        f"- Source report: `{taxonomy.get('source_benchmark_report')}`",
        f"- Generated at: {taxonomy.get('generated_at')}",
        f"- Total cases: {taxonomy.get('total_cases', 0)}",
        f"- Classified failures: {taxonomy.get('total_classified', 0)}",
        "",
        f"> {GUARDRAIL_NOTE}",
        "",
        "_Read-only export: classification only. It does not change benchmark"
        " scoring, patching, validation, or lessons._",
        "",
        "## Summary counts",
        "",
    ]
    if counts:
        for category, count in counts.items():
            lines.append(f"- {category}: {count}")
    else:
        lines.append("_No failing cases were classified._")

    lines.extend(["", "## Cases by category", ""])
    if classifications:
        for category in CATEGORIES:
            grouped = [
                item for item in classifications if item.get("category") == category
            ]
            if not grouped:
                continue
            lines.append(f"### {category} ({len(grouped)})")
            lines.append("")
            for item in grouped:
                lines.append(f"- **{item.get('name')}**")
                explanation = item.get("explanation") or "_no explanation_"
                lines.append(f"  - Explanation: {explanation}")
                action = item.get("recommended_next_action") or "_none_"
                lines.append(f"  - Recommended next action: {action}")
            lines.append("")
    else:
        lines.append("_No failing cases were classified._")
        lines.append("")

    return "\n".join(lines) + "\n"


# --- export -----------------------------------------------------------------


def export_failure_taxonomy_report(
    *,
    benchmark_report: str | None,
    output_dir: str,
    repo_path: str = ".",
    use_latest: bool = False,
    generated_at: float,
) -> dict[str, Any]:
    """Load, classify, and write the JSON + Markdown failure taxonomy report.

    Returns a result dict with ``ok``; on success it includes ``json_path`` and
    ``md_path``; on failure it includes a friendly ``error`` and null paths.
    """
    if use_latest and not benchmark_report:
        latest = find_latest_benchmark_report(repo_path)
        if latest is None:
            return _failure("no benchmark_report_*.json found under repo_path")
        report_path = latest
    elif benchmark_report:
        report_path = Path(benchmark_report)
    else:
        return _failure("no benchmark report specified (use --benchmark-report or --latest)")

    report, error = load_benchmark_report(report_path)
    if error is not None:
        return _failure(error)
    assert report is not None

    taxonomy = build_failure_taxonomy(
        report,
        source_path=str(report_path),
        generated_at=generated_at,
    )

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = int(generated_at)
    json_path = out_dir / f"{stamp}_failure_taxonomy.json"
    md_path = out_dir / f"{stamp}_failure_taxonomy.md"
    json_path.write_text(
        json.dumps(taxonomy, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    md_path.write_text(render_markdown(taxonomy), encoding="utf-8")

    return {
        "ok": True,
        "json_path": str(json_path),
        "md_path": str(md_path),
        "taxonomy": taxonomy,
    }


def _failure(error: str) -> dict[str, Any]:
    return {"ok": False, "error": error, "json_path": None, "md_path": None}


# --- CLI --------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export a read-only failure taxonomy report from a benchmark "
            "report JSON. Does not change scoring, patching, or lessons."
        ),
    )
    parser.add_argument(
        "--benchmark-report",
        default=None,
        help="Path to a benchmark_report_*.json to classify.",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for report artifacts (default: {DEFAULT_OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--repo-path",
        default=".",
        help="Repo root used to locate .agent/benchmarks for --latest (default: .).",
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Classify the newest .agent/benchmarks/benchmark_report_*.json.",
    )
    args = parser.parse_args(argv)

    if not args.benchmark_report and not args.latest:
        parser.error("provide --benchmark-report <path> or --latest")

    result = export_failure_taxonomy_report(
        benchmark_report=args.benchmark_report,
        output_dir=args.output_dir,
        repo_path=args.repo_path,
        use_latest=args.latest,
        generated_at=datetime.now(tz=timezone.utc).timestamp(),
    )

    if not result["ok"]:
        print(f"Failed: {result['error']}")
        return 1

    taxonomy = result["taxonomy"]
    print(
        f"Classified {taxonomy['total_classified']} failing case(s) of "
        f"{taxonomy['total_cases']} from {taxonomy['source_benchmark_report']}."
    )
    if taxonomy["counts_by_category"]:
        for category, count in taxonomy["counts_by_category"].items():
            print(f"  {category}: {count}")
    print(f"JSON: {result['json_path']}")
    print(f"Markdown: {result['md_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
