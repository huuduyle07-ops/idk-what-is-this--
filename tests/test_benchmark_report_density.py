"""Phase 5P.2 — Benchmark tab report density polish.

The Benchmarks tab detail panel used to render failures as long blocks and never
surfaced per-case model / fallback / token / cost info or a compact, scannable
case table. Phase 5P.2 adds, client-side only:

- a compact per-case rows table (status / case / lang+cat / duration / model /
  fallbacks / tokens / cost),
- per-case model + fallback visibility (graceful "unknown"/"—" when absent),
- client-side quick-filter chips (language / category / difficulty) that filter
  the displayed rows WITHOUT calling any benchmark execution route,
- the raw report JSON kept behind a collapsed <details> so it never overwhelms.

All of this is rendering polish: no benchmark runner / scoring / case-file /
CONTROL-prompt / DB / model-API behavior changes. These are template-contract
tests (the repo's established UI-test style — see test_dream_trial_visibility.py)
plus route + client-side-only guards.
"""
from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDEX_TEMPLATE = PROJECT_ROOT / "web" / "templates" / "index.html"
STYLE_SHEET = PROJECT_ROOT / "web" / "static" / "style.css"
APP_PY = PROJECT_ROOT / "web" / "app.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _template() -> str:
    return INDEX_TEMPLATE.read_text(encoding="utf-8")


def _styles() -> str:
    return STYLE_SHEET.read_text(encoding="utf-8")


def _js_function_source(text: str, name: str) -> str:
    """Return the source of JS ``function name(...)`` up to the next top-level
    ``function`` declaration. Good enough for contract checks on a single
    function's body without a full JS parser."""
    start = text.index(f"function {name}(")
    nxt = text.find("\nfunction ", start + 1)
    return text[start:] if nxt == -1 else text[start:nxt]


# ---------------------------------------------------------------------------
# Part A — summary + compact rows; existing sections stay visible
# ---------------------------------------------------------------------------

def test_detail_still_renders_total_passed_failed_flaky_counts():
    tpl = _template()
    detail = _js_function_source(tpl, "_renderBenchmarkDetail")
    # The compact summary row keeps the headline counts.
    assert "passed: " in detail
    assert "failed: " in detail
    assert "total: " in detail
    assert "flaky: " in detail
    # Flaky count helper is still wired in.
    assert "_benchFlakyCount(report)" in detail


def test_report_detail_has_compact_per_case_rows():
    tpl = _template()
    assert "function _renderCompactCasesTable(" in tpl
    # Compact table + tagged rows that the client-side filter can show/hide.
    assert "bench-case-compact" in tpl
    assert "bench-case-compact-row" in tpl
    assert "data-bench-lang" in tpl
    assert "data-bench-cat" in tpl
    assert "data-bench-diff" in tpl
    assert "data-bench-status" in tpl
    # The compact table is actually wired into the detail render.
    detail = _js_function_source(tpl, "_renderBenchmarkDetail")
    assert "_renderCompactCasesTable(report)" in detail


def test_failed_cases_remain_visible():
    detail = _js_function_source(_template(), "_renderBenchmarkDetail")
    assert "Failed cases (" in detail
    assert "!r.success" in detail  # failures still derived from results


def test_flaky_cases_remain_visible():
    tpl = _template()
    assert "function _renderFlakyCasesTable(" in tpl
    assert "Flaky cases (" in tpl
    detail = _js_function_source(tpl, "_renderBenchmarkDetail")
    assert "_renderFlakyCasesTable(report)" in detail


def test_slowest_cases_remain_visible():
    detail = _js_function_source(_template(), "_renderBenchmarkDetail")
    assert "Slowest cases" in detail
    assert "report.slowest_cases" in detail


# ---------------------------------------------------------------------------
# Part B — per-case model / fallback visibility, graceful when absent
# ---------------------------------------------------------------------------

def test_model_and_fallback_fields_render_when_present():
    tpl = _template()
    assert "function _benchModelLabel(" in tpl
    # Per-case model + fallback come straight from the report JSON fields.
    assert "selected_model" in tpl
    assert "fallback_count" in tpl
    compact = _js_function_source(tpl, "_renderCompactCasesTable")
    assert "_benchModelLabel(" in compact
    assert "fallback_count" in compact
    # Tokens + cost surfaced per case using the existing cost formatter.
    assert "total_tokens" in compact
    assert "_benchFmtCost(" in compact


def test_missing_model_fields_render_as_unknown_not_crash():
    tpl = _template()
    label = _js_function_source(tpl, "_benchModelLabel")
    # Absent / empty selected_model degrades to a literal "unknown".
    assert "unknown" in label
    # The helper guards against a null/undefined result object.
    assert "selected_model" in label
    compact = _js_function_source(tpl, "_renderCompactCasesTable")
    # Numeric fields use a graceful em-dash / zero fallback, never a bare
    # access that would throw on a missing field.
    assert "—" in compact or "&mdash;" in compact


def test_models_used_summary_line_present():
    tpl = _template()
    detail = _js_function_source(tpl, "_renderBenchmarkDetail")
    assert "bench-models-line" in tpl
    # Top-level fallback total surfaced in the summary, when present.
    assert "total_fallbacks" in detail


# ---------------------------------------------------------------------------
# Part C — client-side quick filters (no execution route calls)
# ---------------------------------------------------------------------------

def test_quick_filter_chips_present():
    tpl = _template()
    assert "function _renderBenchFilters(" in tpl
    assert "bench-filter-chip" in tpl
    assert "data-bench-dim" in tpl
    assert "data-bench-val" in tpl
    # All three dimensions are offered.
    filters = _js_function_source(tpl, "_renderBenchFilters")
    assert "language" in filters
    assert "category" in filters
    assert "difficulty" in filters


def test_quick_filters_are_client_side_only():
    tpl = _template()
    for name in ("benchFilterCases", "_applyBenchCaseFilters", "_renderBenchFilters"):
        body = _js_function_source(tpl, name)
        assert "fetch(" not in body, f"{name} must not call fetch()"
        assert "/benchmarks/run" not in body, f"{name} must not trigger a run"
        assert "/benchmarks/stop" not in body
        assert "/benchmarks/report" not in body
    # The filter actually toggles row visibility client-side.
    apply_body = _js_function_source(tpl, "_applyBenchCaseFilters")
    assert "hidden" in apply_body
    assert "bench-case-compact-row" in apply_body


# ---------------------------------------------------------------------------
# Part A — raw JSON stays collapsed
# ---------------------------------------------------------------------------

def test_raw_report_json_is_collapsed_details():
    tpl = _template()
    assert '<details class="bench-raw-json">' in tpl
    # Collapsed by default — the raw-json details must NOT be force-opened.
    assert '<details class="bench-raw-json" open>' not in tpl
    detail = _js_function_source(tpl, "_renderBenchmarkDetail")
    # The collapsed block contains the full report serialized + escaped.
    assert "JSON.stringify(report, null, 2)" in detail
    assert "_escapeHtml(JSON.stringify(report" in detail


# ---------------------------------------------------------------------------
# Existing Run controls still render (point 10)
# ---------------------------------------------------------------------------

def test_existing_run_controls_still_render():
    tpl = _template()
    assert "runAllBenchmarks()" in tpl
    assert "openBenchmarkCasePicker()" in tpl
    assert "toggleBenchmarkOptions()" in tpl
    assert 'id="benchOptionsToggle"' in tpl
    assert 'id="stopBenchBtn"' in tpl


# ---------------------------------------------------------------------------
# Styling contract
# ---------------------------------------------------------------------------

def test_style_sheet_has_density_classes():
    css = _styles()
    assert ".bench-case-compact" in css
    assert ".bench-filter-chip" in css
    assert ".bench-raw-json" in css


# ---------------------------------------------------------------------------
# Guardrails (point 11) — backend untouched, routes intact, render is pure
# ---------------------------------------------------------------------------

def test_benchmark_routes_still_registered():
    from web.app import app

    rules = {r.rule for r in app.url_map.iter_rules()}
    for route in [
        "/benchmarks/list",
        "/benchmarks/report",
        "/benchmarks/run",
        "/benchmarks/cases",
        "/benchmarks/status",
        "/benchmarks/stop",
        "/benchmarks/create-case",
    ]:
        assert route in rules, f"benchmark route disappeared: {route}"


def test_report_route_still_backed_by_read_benchmark_report():
    # Backend semantics for the detail panel are unchanged: it still reads the
    # report JSON via core.benchmarks_view.read_benchmark_report.
    app_src = APP_PY.read_text(encoding="utf-8")
    assert "read_benchmark_report" in app_src


def test_render_helpers_do_not_execute_benchmarks():
    """The new/updated render helpers must stay pure UI — no runner, scoring,
    patch-execution, or model-API calls leaked into the web layer."""
    tpl = _template()
    forbidden = ("/benchmarks/run", "/benchmarks/stop")
    for name in (
        "_renderBenchmarkDetail",
        "_renderCompactCasesTable",
        "_renderBenchFilters",
        "_benchModelLabel",
    ):
        body = _js_function_source(tpl, name)
        for needle in forbidden:
            assert needle not in body, f"{name} leaked execution call: {needle}"
        assert "fetch(" not in body, f"{name} must not fetch during render"
