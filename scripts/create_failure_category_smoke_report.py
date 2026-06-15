"""Phase 14.7a — Failure Category Fresh Run Smoke.

Loads the latest (or an explicit) benchmark report, re-enriches every failing
case through ``with_failure_category_fields()`` (the same call path used in a
real benchmark run), then verifies all display layers:

  * failure_category metadata fields on re-enriched cases
  * Run Health ``failure_category_counts``
  * Markdown "Failure categories" line + per-case "category:" detail
  * Web ``summarize_run_health`` data for the Benchmark UI
  * Backward compatibility: old (pre-Phase-14.6) reports must not crash and
    must not show a noisy empty "Failure categories" row

No model calls, no agent runs, no DB writes, no patch/apply, no lesson
promotion, no Dream/Project-Evolution changes.  Read-only except for the two
audit artifacts written at the end.

Usage:
    python scripts/create_failure_category_smoke_report.py
    python scripts/create_failure_category_smoke_report.py --report <path>
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SMOKE_GUARDRAIL_NOTE = (
    "Phase 14.7a smoke is read-only verification: it re-enriches an existing "
    "report through with_failure_category_fields() and checks display layers. "
    "It does not run benchmarks, call models, apply patches, promote lessons, "
    "modify taxonomy rules, change benchmark scoring, write to any database, or "
    "affect any runtime behavior."
)

OUTPUT_DIR = PROJECT_ROOT / ".agent" / "audits"
BENCH_DIR = PROJECT_ROOT / ".agent" / "benchmarks"

_REQUIRED_CAT_FIELDS = (
    "failure_category",
    "failure_category_confidence",
    "failure_category_rule",
    "failure_category_reason",
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _find_latest_report() -> Path | None:
    if not BENCH_DIR.is_dir():
        return None
    candidates = sorted(
        BENCH_DIR.glob("benchmark_report_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _load_report(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"_load_error": str(exc), "results": []}


def _re_enrich(report: dict[str, Any]) -> dict[str, Any]:
    """Return a new report dict with failure_category fields added to failing cases."""
    from benchmarks.run_benchmarks import with_failure_category_fields

    enriched_results = []
    for case in report.get("results") or []:
        if not isinstance(case, dict):
            enriched_results.append(case)
            continue
        enriched_results.append(with_failure_category_fields(dict(case)))
    out = dict(report)
    out["results"] = enriched_results
    return out


def _check_category_fields(results: list[dict]) -> dict[str, Any]:
    """Return counts/details for category field presence across failing cases."""
    failing = [r for r in results if isinstance(r, dict) and r.get("success") is not True and not r.get("skipped")]
    all_present: list[str] = []
    partial: list[str] = []
    missing: list[str] = []
    for r in failing:
        present = [f for f in _REQUIRED_CAT_FIELDS if isinstance(r.get(f), str) and r[f]]
        if len(present) == len(_REQUIRED_CAT_FIELDS):
            all_present.append(r.get("name", "?"))
        elif present:
            partial.append(r.get("name", "?"))
        else:
            missing.append(r.get("name", "?"))
    return {
        "total_failing": len(failing),
        "all_fields_present": len(all_present),
        "partial_fields": len(partial),
        "no_fields": len(missing),
        "cases_with_all_fields": all_present,
        "cases_with_no_fields": missing,
    }


def _check_run_health(report: dict[str, Any]) -> dict[str, Any]:
    from core.benchmarks_view import summarize_run_health

    health = summarize_run_health(report)
    cat_counts = health.get("failure_category_counts") or {}
    return {
        "passed": health.get("passed"),
        "failed": health.get("failed"),
        "failure_category_counts": dict(cat_counts),
        "category_data_present": bool(cat_counts),
    }


def _check_markdown(report: dict[str, Any]) -> dict[str, Any]:
    from benchmarks.run_benchmarks import write_markdown_report

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "smoke_report.md"
        write_markdown_report(report, out)
        md = out.read_text(encoding="utf-8")

    return {
        "has_failure_categories_line": "Failure categories" in md,
        "has_category_detail_line": "- category:" in md,
        "has_benchmark_report_header": "# Benchmark Report" in md,
        "snippet": _snippet(md, "Failure categories", context=120),
    }


def _snippet(text: str, keyword: str, context: int = 120) -> str | None:
    idx = text.find(keyword)
    if idx < 0:
        return None
    start = max(0, idx - 20)
    end = min(len(text), idx + context)
    return text[start:end].strip()


def _check_web_render(enriched: dict[str, Any], old: dict[str, Any]) -> dict[str, Any]:
    """Check web-layer summarize_run_health data and Flask route health."""
    from core.benchmarks_view import summarize_run_health

    enriched_health = summarize_run_health(enriched)
    old_health = summarize_run_health(old)

    # Flask route smoke — confirm index renders without error
    flask_ok = False
    flask_status = None
    try:
        from web import app as web_app
        with web_app.app.test_client() as client:
            resp = client.get("/")
        flask_status = resp.status_code
        flask_ok = resp.status_code == 200
    except Exception as exc:
        flask_status = f"error: {exc}"

    return {
        "enriched_category_counts": dict(enriched_health.get("failure_category_counts") or {}),
        "enriched_category_data_present": bool(enriched_health.get("failure_category_counts")),
        "old_category_counts": dict(old_health.get("failure_category_counts") or {}),
        "old_category_data_empty": not bool(old_health.get("failure_category_counts")),
        "flask_route_ok": flask_ok,
        "flask_status": flask_status,
        "template_has_category_function": "_benchFailureCategoryText" in (
            PROJECT_ROOT / "web" / "templates" / "index.html"
        ).read_text(encoding="utf-8"),
    }


def _check_backward_compat(old: dict[str, Any]) -> dict[str, Any]:
    """Confirm old report Markdown doesn't crash or emit noisy category row."""
    from benchmarks.run_benchmarks import write_markdown_report

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "old_report.md"
        write_markdown_report(old, out)
        md = out.read_text(encoding="utf-8")

    return {
        "no_crash": True,
        "no_empty_category_row": "Failure categories" not in md,
        "has_benchmark_report_header": "# Benchmark Report" in md,
    }


def _check_scoring_unchanged(old: dict[str, Any], enriched: dict[str, Any]) -> dict[str, Any]:
    """Confirm re-enrichment does not change pass/fail counts."""
    old_results = old.get("results") or []
    enriched_results = enriched.get("results") or []
    old_pass = sum(1 for r in old_results if isinstance(r, dict) and r.get("success") is True)
    enriched_pass = sum(1 for r in enriched_results if isinstance(r, dict) and r.get("success") is True)
    return {
        "old_pass": old_pass,
        "enriched_pass": enriched_pass,
        "unchanged": old_pass == enriched_pass and len(old_results) == len(enriched_results),
    }


# ── report rendering ──────────────────────────────────────────────────────────

def _render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Failure Category Fresh Run Smoke (Phase 14.7a)")
    lines.append("")
    lines.append(f"> {SMOKE_GUARDRAIL_NOTE}")
    lines.append("")

    meta = result.get("meta") or {}
    lines.append(f"- Source report: `{meta.get('report_path', 'unknown')}`")
    lines.append(f"- Generated at: {meta.get('generated_at_utc', 'unknown')}")
    lines.append("")

    # 1. Category fields check
    fields = result.get("category_fields") or {}
    lines.append("## 1. Category Fields on Re-Enriched Cases")
    lines.append("")
    lines.append(f"- Total failing cases: {fields.get('total_failing', 0)}")
    lines.append(f"- Cases with all 4 category fields: **{fields.get('all_fields_present', 0)}**")
    lines.append(f"- Cases with partial fields: {fields.get('partial_fields', 0)}")
    lines.append(f"- Cases with no fields: {fields.get('no_fields', 0)}")
    if fields.get("cases_with_all_fields"):
        lines.append(f"- Case names: {', '.join(f'`{n}`' for n in fields['cases_with_all_fields'])}")
    if fields.get("cases_with_no_fields"):
        lines.append(f"- WARNING — no fields: {', '.join(fields['cases_with_no_fields'])}")
    all_ok = fields.get("all_fields_present", 0) == fields.get("total_failing", -1)
    lines.append(f"- **Check: {'PASS' if all_ok else 'WARN — some cases missing fields'}**")
    lines.append("")

    # 2. Run health check
    health = result.get("run_health") or {}
    lines.append("## 2. Run Health")
    lines.append("")
    lines.append(f"- passed: {health.get('passed')}, failed: {health.get('failed')}")
    lines.append(f"- failure_category_counts: {json.dumps(health.get('failure_category_counts') or {})}")
    rh_ok = health.get("category_data_present") if fields.get("total_failing", 0) > 0 else True
    lines.append(f"- **Check: {'PASS' if rh_ok else 'WARN — no category counts despite failing cases'}**")
    lines.append("")

    # 3. Markdown check
    md_check = result.get("markdown") or {}
    lines.append("## 3. Markdown Report")
    lines.append("")
    lines.append(f"- 'Failure categories' line present: {md_check.get('has_failure_categories_line')}")
    lines.append(f"- 'category:' detail line present: {md_check.get('has_category_detail_line')}")
    md_ok = (
        (md_check.get("has_failure_categories_line") if fields.get("total_failing", 0) > 0 else True)
        and md_check.get("has_benchmark_report_header")
    )
    lines.append(f"- **Check: {'PASS' if md_ok else 'WARN'}**")
    if md_check.get("snippet"):
        lines.append("")
        lines.append("Snippet around 'Failure categories':")
        lines.append("```")
        lines.append(md_check["snippet"])
        lines.append("```")
    lines.append("")

    # 4. Web render check
    web = result.get("web_render") or {}
    lines.append("## 4. Web Render Smoke")
    lines.append("")
    lines.append(f"- Flask route status: {web.get('flask_status')}")
    lines.append(f"- Template has _benchFailureCategoryText: {web.get('template_has_category_function')}")
    lines.append(f"- enriched failure_category_counts: {json.dumps(web.get('enriched_category_counts') or {})}")
    lines.append(f"- old failure_category_counts: {json.dumps(web.get('old_category_counts') or {})}")
    web_ok = (
        web.get("flask_route_ok")
        and web.get("template_has_category_function")
        and (web.get("enriched_category_data_present") if fields.get("total_failing", 0) > 0 else True)
        and web.get("old_category_data_empty")
    )
    lines.append(f"- **Check: {'PASS' if web_ok else 'WARN'}**")
    lines.append("")

    # 5. Backward compat
    compat = result.get("backward_compat") or {}
    lines.append("## 5. Backward Compatibility (Old Report)")
    lines.append("")
    lines.append(f"- No crash: {compat.get('no_crash')}")
    lines.append(f"- No empty 'Failure categories' row: {compat.get('no_empty_category_row')}")
    lines.append(f"- Report header present: {compat.get('has_benchmark_report_header')}")
    compat_ok = all([compat.get("no_crash"), compat.get("no_empty_category_row"), compat.get("has_benchmark_report_header")])
    lines.append(f"- **Check: {'PASS' if compat_ok else 'FAIL'}**")
    lines.append("")

    # 6. Scoring unchanged
    scoring = result.get("scoring") or {}
    lines.append("## 6. Scoring / Behavior Unchanged")
    lines.append("")
    lines.append(f"- old pass count: {scoring.get('old_pass')}, enriched pass count: {scoring.get('enriched_pass')}")
    lines.append(f"- **Check: {'PASS' if scoring.get('unchanged') else 'FAIL — pass counts differ'}**")
    lines.append("")

    # Overall
    checks = [all_ok, rh_ok, md_ok, web_ok, compat_ok, scoring.get("unchanged")]
    overall = all(checks)
    lines.append("## Overall")
    lines.append("")
    lines.append(f"**{'ALL CHECKS PASSED' if overall else 'SOME CHECKS WARNED — review above'}**")
    lines.append("")

    return "\n".join(lines) + "\n"


# ── main ──────────────────────────────────────────────────────────────────────

def run_smoke(
    *,
    report_path: Path | None = None,
    output_dir: Path = OUTPUT_DIR,
    generated_at: float,
) -> dict[str, Any]:
    if report_path is None:
        report_path = _find_latest_report()
    if report_path is None or not report_path.exists():
        return {
            "ok": False,
            "error": "No benchmark report found. Run benchmarks first.",
        }

    old_report = _load_report(report_path)
    if old_report.get("_load_error"):
        return {"ok": False, "error": old_report["_load_error"]}

    enriched_report = _re_enrich(old_report)

    cat_fields = _check_category_fields(enriched_report.get("results") or [])
    run_health = _check_run_health(enriched_report)
    md_check = _check_markdown(enriched_report)
    web_render = _check_web_render(enriched_report, old_report)
    compat = _check_backward_compat(old_report)
    scoring = _check_scoring_unchanged(old_report, enriched_report)

    dt = datetime.fromtimestamp(generated_at, tz=timezone.utc)
    ts = dt.strftime("%Y%m%d_%H%M%S")
    generated_at_utc = dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    result: dict[str, Any] = {
        "phase": "14.7a",
        "guardrail_note": SMOKE_GUARDRAIL_NOTE,
        "meta": {
            "report_path": str(report_path),
            "generated_at_utc": generated_at_utc,
            "generated_at_ts": generated_at,
        },
        "category_fields": cat_fields,
        "run_health": run_health,
        "markdown": md_check,
        "web_render": web_render,
        "backward_compat": compat,
        "scoring": scoring,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    slug = "failure-category-fresh-run-smoke"
    json_path = output_dir / f"{ts}_{slug}.json"
    md_path = output_dir / f"{ts}_{slug}.md"

    json_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    md_path.write_text(_render_markdown(result), encoding="utf-8")

    result["ok"] = True
    result["json_path"] = str(json_path)
    result["md_path"] = str(md_path)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", help="Explicit benchmark report JSON path")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    args = parser.parse_args()

    import time

    report_path = Path(args.report) if args.report else None
    result = run_smoke(
        report_path=report_path,
        output_dir=Path(args.output_dir),
        generated_at=time.time(),
    )

    if not result.get("ok"):
        print(f"ERROR: {result.get('error')}", file=sys.stderr)
        sys.exit(1)

    print(f"Smoke report written:")
    print(f"  JSON: {result['json_path']}")
    print(f"  MD:   {result['md_path']}")

    cat_fields = result.get("category_fields") or {}
    print(f"\nCategory fields: {cat_fields.get('all_fields_present')}/{cat_fields.get('total_failing')} failing cases have all 4 fields")

    run_health = result.get("run_health") or {}
    print(f"Run Health category counts: {run_health.get('failure_category_counts')}")

    md_check = result.get("markdown") or {}
    print(f"Markdown 'Failure categories' line: {md_check.get('has_failure_categories_line')}")

    compat = result.get("backward_compat") or {}
    print(f"Backward compat: no_crash={compat.get('no_crash')}, no_empty_row={compat.get('no_empty_category_row')}")

    scoring = result.get("scoring") or {}
    print(f"Scoring unchanged: {scoring.get('unchanged')} (old={scoring.get('old_pass')}, enriched={scoring.get('enriched_pass')})")


if __name__ == "__main__":
    main()
