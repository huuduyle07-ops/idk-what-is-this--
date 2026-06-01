import json
from pathlib import Path

from scripts import build_presentation_evidence_pack as pack


EXPECTED_FILES = [
    "00_evidence_index.md",
    "01_full_suite_summary.md",
    "02_held_out_suite_summary.md",
    "03_held_out_watchlist.md",
    "04_patch_minimality_experiment.md",
    "05_same_suite_trends.md",
    "06_graph_weight_explainability.md",
    "07_graph_attraction_explainability.md",
    "08_memory_temperature_explainability.md",
    "09_memory_temperature_tiebreaker_dogfood.md",
]


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _write_benchmark_report(
    bench_dir: Path,
    name: str,
    *,
    total: int = 31,
    passed: int = 31,
    failed: int = 0,
    flaky: int = 0,
    suite_id: str | None = None,
    case_names: list[str] | None = None,
    created_at: str = "2026-05-24T00:00:00+00:00",
    extra: dict | None = None,
) -> Path:
    case_names = case_names or ["ts_nested_dispatch_root_cause", "case_b"]
    payload: dict = {
        "total": total,
        "passed": passed,
        "failed": failed,
        "flaky": flaky,
        "results": [
            {"name": n, "success": True, "duration_sec": 1.0, "fallback_count": 0}
            for n in case_names
        ],
        "avg_duration_sec": 1.0,
        "total_fallbacks": 0,
        "total_tokens": 100,
        "total_estimated_cost_usd": 0.001,
        "created_at": created_at,
    }
    if suite_id is not None:
        payload["suite_id"] = suite_id
    if extra:
        payload.update(extra)
    return _write_json(bench_dir / name, payload)


def test_creates_output_directory(tmp_path):
    project = tmp_path / "project"
    project.mkdir()

    result = pack.build_evidence_pack(project)

    assert result["output_dir"].exists()
    assert result["output_dir"].is_dir()
    assert result["output_dir"] == project / ".agent" / "presentation_evidence"


def test_generates_all_expected_markdown_files(tmp_path):
    project = tmp_path / "project"
    project.mkdir()

    result = pack.build_evidence_pack(project)

    for name in EXPECTED_FILES:
        path = result["output_dir"] / name
        assert path.exists(), f"missing {name}"
        assert path.read_text(encoding="utf-8").strip(), f"empty {name}"


def test_missing_optional_artifacts_create_placeholders(tmp_path):
    project = tmp_path / "project"
    project.mkdir()

    result = pack.build_evidence_pack(project)

    graph_md = (result["output_dir"] / "06_graph_weight_explainability.md").read_text(encoding="utf-8")
    assert "explain_graph_weights.py" in graph_md
    assert "--repo-path ." in graph_md
    assert "--top 15" in graph_md
    assert "--include-zero-penalty" in graph_md
    assert "--hide-empty-symbols" in graph_md

    watchlist_md = (result["output_dir"] / "03_held_out_watchlist.md").read_text(encoding="utf-8")
    assert "No watchlist" in watchlist_md or "no watchlist" in watchlist_md.lower()

    minimality_md = (result["output_dir"] / "04_patch_minimality_experiment.md").read_text(encoding="utf-8")
    assert "No" in minimality_md  # placeholder text


def test_does_not_modify_source_reports(tmp_path):
    project = tmp_path / "project"
    bench = project / ".agent" / "benchmarks"
    full = _write_benchmark_report(bench, "benchmark_report_full.json", total=31, passed=31)
    held = _write_benchmark_report(
        bench,
        "benchmark_report_held.json",
        total=7,
        passed=7,
        suite_id="held_out_v1",
        case_names=["a", "b"],
        extra={"suite_case_count": 7},
    )
    trends_dir = bench / "trends"
    watchlist = _write_json(
        trends_dir / "suite_watchlist_held_out_v1.json",
        {
            "suite_id": "held_out_v1",
            "watchlist": [],
            "stable": [],
            "cases": [],
            "report_window": {
                "selected": 1,
                "requested": 10,
                "first_report": "x",
                "last_report": "x",
            },
        },
    )
    trend_index = _write_json(
        trends_dir / "benchmark_trend_index.json",
        {"groups": [], "warnings": [], "skipped_reports": []},
    )
    exp_dir = project / ".agent" / "experiments"
    experiment = _write_json(
        exp_dir / "20260525_patch-minimality.json",
        {
            "experiment_id": "20260525_patch-minimality",
            "title": "Patch minimality metric check",
            "hypothesis": "Patch minimality reporting should preserve correctness.",
            "status": "compared",
            "result": {
                "decision": {"status": "greenlight", "warnings": [], "reasons": []},
                "metrics": {
                    "passed": {"baseline": 31, "variant": 31, "delta": 0, "status": "unchanged"},
                },
            },
            "created_at": "2026-05-25T01:30:52+00:00",
        },
    )

    snapshots = {
        path: path.read_text(encoding="utf-8")
        for path in (full, held, watchlist, trend_index, experiment)
    }

    pack.build_evidence_pack(project)

    for path, content in snapshots.items():
        assert path.read_text(encoding="utf-8") == content


def test_selects_latest_full_suite_report(tmp_path):
    project = tmp_path / "project"
    bench = project / ".agent" / "benchmarks"
    _write_benchmark_report(
        bench,
        "benchmark_report_old.json",
        total=31,
        passed=31,
        created_at="2026-05-23T00:00:00+00:00",
    )
    _write_benchmark_report(
        bench,
        "benchmark_report_new.json",
        total=31,
        passed=30,
        failed=1,
        created_at="2026-05-24T00:00:00+00:00",
    )

    result = pack.build_evidence_pack(project)
    md = (result["output_dir"] / "01_full_suite_summary.md").read_text(encoding="utf-8")

    assert "benchmark_report_new.json" in md
    assert "Passed: 30" in md
    assert "Failed: 1" in md
    assert "ts_nested_dispatch_root_cause passed" in md


def test_selects_latest_held_out_v1_report(tmp_path):
    project = tmp_path / "project"
    bench = project / ".agent" / "benchmarks"
    _write_benchmark_report(
        bench,
        "benchmark_report_held_old.json",
        total=7,
        passed=6,
        failed=1,
        suite_id="held_out_v1",
        case_names=["x", "y"],
        extra={"suite_case_count": 7},
        created_at="2026-05-23T00:00:00+00:00",
    )
    _write_benchmark_report(
        bench,
        "benchmark_report_held_new.json",
        total=7,
        passed=7,
        suite_id="held_out_v1",
        case_names=["alpha", "beta"],
        extra={"suite_case_count": 7},
        created_at="2026-05-24T00:00:00+00:00",
    )
    _write_benchmark_report(
        bench,
        "benchmark_report_full.json",
        total=31,
        passed=31,
        created_at="2026-05-25T00:00:00+00:00",
    )

    result = pack.build_evidence_pack(project)
    md = (result["output_dir"] / "02_held_out_suite_summary.md").read_text(encoding="utf-8")

    assert "benchmark_report_held_new.json" in md
    assert "Passed: 7" in md
    assert "`alpha`" in md
    assert "`beta`" in md


def test_summarizes_held_out_watchlist_json(tmp_path):
    project = tmp_path / "project"
    trends_dir = project / ".agent" / "benchmarks" / "trends"
    _write_json(
        trends_dir / "suite_watchlist_held_out_v1.json",
        {
            "suite_id": "held_out_v1",
            "watchlist": ["case_alpha"],
            "stable": ["case_beta", "case_gamma"],
            "cases": [
                {
                    "name": "case_alpha",
                    "watchlisted": True,
                    "watchlist_reasons": ["failures"],
                    "failure_rate": 0.5,
                    "last_status": "fail",
                    "last_seen_report": "benchmark_report_X.json",
                },
                {
                    "name": "case_beta",
                    "watchlisted": False,
                    "watchlist_reasons": [],
                    "failure_rate": 0.0,
                    "last_status": "pass",
                    "last_seen_report": "benchmark_report_X.json",
                },
            ],
            "report_window": {
                "requested": 10,
                "selected": 2,
                "first_report": "a",
                "last_report": "b",
            },
        },
    )

    result = pack.build_evidence_pack(project)
    md = (result["output_dir"] / "03_held_out_watchlist.md").read_text(encoding="utf-8")

    assert "case_alpha" in md
    assert "failures" in md
    assert "fail" in md
    assert "0.5" in md
    assert "observational" in md.lower()
    assert "Stable cases: 2" in md


def test_summarizes_patch_minimality_experiment(tmp_path):
    project = tmp_path / "project"
    exp_dir = project / ".agent" / "experiments"
    _write_json(
        exp_dir / "20260525_patch-minimality-metric-check.json",
        {
            "experiment_id": "20260525_patch-minimality-metric-check",
            "title": "Patch minimality metric report check",
            "hypothesis": "Patch minimality reporting should preserve correctness.",
            "status": "compared",
            "result": {
                "decision": {
                    "status": "greenlight",
                    "warnings": ["model_calls unknown"],
                    "reasons": ["no critical regressions"],
                    "human_review_required": False,
                },
                "metrics": {
                    "total": {"baseline": 31, "variant": 31, "delta": 0, "status": "unchanged"},
                    "passed": {"baseline": 31, "variant": 31, "delta": 0, "status": "unchanged"},
                    "failed": {"baseline": 0, "variant": 0, "delta": 0, "status": "unchanged"},
                    "flaky": {"baseline": 0, "variant": 0, "delta": 0, "status": "unchanged"},
                    "average_duration": {
                        "baseline": 36.31,
                        "variant": 30.7,
                        "delta": -5.61,
                        "status": "decreased",
                    },
                    "fallback_count": {
                        "baseline": 16,
                        "variant": 14,
                        "delta": -2,
                        "status": "decreased",
                    },
                },
            },
            "created_at": "2026-05-25T01:30:52+00:00",
        },
    )
    _write_json(
        exp_dir / "20260524_other-experiment.json",
        {
            "experiment_id": "20260524_other-experiment",
            "title": "Unrelated experiment",
            "status": "compared",
            "created_at": "2026-05-24T00:00:00+00:00",
        },
    )

    result = pack.build_evidence_pack(project)
    md = (result["output_dir"] / "04_patch_minimality_experiment.md").read_text(encoding="utf-8")

    assert "greenlight" in md.lower()
    assert "Patch minimality metric report check" in md
    assert "-5.61" in md
    assert "-2" in md
    assert "model_calls unknown" in md
    # the older unrelated experiment should NOT be the selected one
    assert "Unrelated experiment" not in md


def test_index_links_all_generated_files(tmp_path):
    project = tmp_path / "project"
    project.mkdir()

    result = pack.build_evidence_pack(project)
    index = (result["output_dir"] / "00_evidence_index.md").read_text(encoding="utf-8")

    for name in EXPECTED_FILES[1:]:
        assert f"]({name})" in index, f"index missing link to {name}"
    assert "Full benchmark suite passed" in index
    assert "Held-out suite exists" in index
    assert "Watchlist tracks instability" in index
    assert "Patch minimality" in index
    assert "Same-suite trends prevent fake comparisons" in index


def test_graph_section_auto_embeds_ranked_table_when_available(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()

    fake_rows = [
        {
            "node_id": "core/foo.py::do_thing",
            "node_kind": "function",
            "total_weight": 0.91,
            "topology_contribution": 0.42,
            "complexity_contribution": 0.12,
            "failure_penalty": 0.0,
            "reasons": ["in_degree=4", "out_degree=2"],
            "in_degree": 4,
            "out_degree": 2,
            "complexity": 3,
        },
    ]

    from graph import builder as graph_builder
    from graph import weights as graph_weights

    monkeypatch.setattr(graph_builder, "build_graph_from_repo", lambda repo_path: "GRAPH_SENTINEL")
    monkeypatch.setattr(
        graph_weights,
        "explain_node_weights",
        lambda graph, **kwargs: fake_rows,
    )

    result = pack.build_evidence_pack(project)
    md = (result["output_dir"] / "06_graph_weight_explainability.md").read_text(encoding="utf-8")

    assert "Graph explainer ran automatically" in md
    assert "## Top-ranked nodes" in md
    assert "`core/foo.py::do_thing`" in md
    assert "in_degree=4" in md
    assert result["graph_auto_explanation"] is not None
    assert result["graph_auto_explanation"]["rows"]


def test_graph_section_falls_back_to_placeholder_when_build_fails(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()

    from graph import builder as graph_builder

    def _boom(repo_path):
        raise RuntimeError("simulated graph build failure")

    monkeypatch.setattr(graph_builder, "build_graph_from_repo", _boom)

    result = pack.build_evidence_pack(project)
    md = (result["output_dir"] / "06_graph_weight_explainability.md").read_text(encoding="utf-8")

    assert "could not be auto-run" in md
    assert "explain_graph_weights.py" in md
    assert "--top 15" in md
    assert result["graph_auto_explanation"] is None


# --------------------------------------------------------------------------
# Phase 12.14c - Memory Temperature evidence pack file
# --------------------------------------------------------------------------

MEMORY_TEMPERATURE_FILE = "08_memory_temperature_explainability.md"


def test_memory_temperature_file_is_emitted(tmp_path):
    project = tmp_path / "project"
    project.mkdir()

    result = pack.build_evidence_pack(project)

    path = result["output_dir"] / MEMORY_TEMPERATURE_FILE
    assert path.exists()
    assert path.read_text(encoding="utf-8").strip()


def test_index_links_memory_temperature_file(tmp_path):
    project = tmp_path / "project"
    project.mkdir()

    result = pack.build_evidence_pack(project)
    index = (result["output_dir"] / "00_evidence_index.md").read_text(encoding="utf-8")

    assert f"]({MEMORY_TEMPERATURE_FILE})" in index
    assert "memory temperature" in index.lower()


def test_memory_temperature_placeholder_when_no_report(tmp_path):
    project = tmp_path / "project"
    project.mkdir()

    result = pack.build_evidence_pack(project)
    md = (result["output_dir"] / MEMORY_TEMPERATURE_FILE).read_text(encoding="utf-8")

    # Graceful placeholder when there is no memory-temperature report yet.
    assert "No memory" in md or "no memory" in md.lower()


def test_memory_temperature_includes_formula_and_bands(tmp_path):
    project = tmp_path / "project"
    project.mkdir()

    result = pack.build_evidence_pack(project)
    md = (result["output_dir"] / MEMORY_TEMPERATURE_FILE).read_text(encoding="utf-8")

    # Formula (Test 4).
    assert "T_now" in md
    assert "exp(" in md
    assert "clamp(" in md
    # hot/warm/cold/frozen explanation (Test 4).
    for band in ("hot", "warm", "cold", "frozen"):
        assert band in md.lower()
    # Hard-freeze override is explained (Test 6 placeholder spec).
    assert "freeze" in md.lower()


def test_memory_temperature_includes_explain_only_guardrail(tmp_path):
    from core.memory_temperature import MEMORY_TEMPERATURE_GUARDRAIL

    project = tmp_path / "project"
    project.mkdir()

    result = pack.build_evidence_pack(project)
    md = (result["output_dir"] / MEMORY_TEMPERATURE_FILE).read_text(encoding="utf-8")

    # Explain-only guardrail (Test 5).
    assert "explain-only" in md.lower()
    assert MEMORY_TEMPERATURE_GUARDRAIL in md


def test_memory_temperature_embeds_existing_report(tmp_path):
    project = tmp_path / "project"
    report_dir = project / ".agent" / "reports" / "memory_temperature"
    report_dir.mkdir(parents=True)
    (report_dir / "latest.md").write_text(
        "# Memory Temperature (explain-only)\n\nSENTINEL_REPORT_BODY\n",
        encoding="utf-8",
    )

    result = pack.build_evidence_pack(project)
    md = (result["output_dir"] / MEMORY_TEMPERATURE_FILE).read_text(encoding="utf-8")

    assert "SENTINEL_REPORT_BODY" in md
    assert "explain-only" in md.lower()
    assert result["memory_temperature_artifact_path"] is not None


def test_memory_temperature_does_not_modify_source_report(tmp_path):
    project = tmp_path / "project"
    report_dir = project / ".agent" / "reports" / "memory_temperature"
    report_dir.mkdir(parents=True)
    source = report_dir / "latest.md"
    source.write_text("# existing\n\nbody\n", encoding="utf-8")
    before = source.read_text(encoding="utf-8")

    pack.build_evidence_pack(project)

    assert source.read_text(encoding="utf-8") == before


def test_pack_module_has_no_forbidden_imports_or_calls():
    import ast

    source = Path(pack.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules: list[str] = []
    call_names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                call_names.append(func.id)
            elif isinstance(func, ast.Attribute):
                call_names.append(func.attr)

    forbidden_import_areas = (
        "model",
        "api",
        "patching",
        "validation",
        "validator",
        "run_benchmarks",
    )
    for imported in imported_modules:
        parts = imported.split(".")
        for forbidden in forbidden_import_areas:
            assert not any(part == forbidden for part in parts), imported

    forbidden_network = {"requests", "httpx", "urllib", "aiohttp", "socket", "subprocess", "openai"}
    assert forbidden_network.isdisjoint(part.split(".")[0] for part in imported_modules)

    forbidden_calls = {
        "call_model",
        "call_api",
        "run_gemini_request",
        "validate",
        "run_benchmarks",
        "start_benchmark_run_async",
        "promote_lesson",
        "save_candidate_lesson",
    }
    assert forbidden_calls.isdisjoint(call_names)


# --------------------------------------------------------------------------
# Phase 13.11b - Memory Temperature Tie-breaker Dogfood evidence pack file
# --------------------------------------------------------------------------

TIEBREAKER_DOGFOOD_FILE = "09_memory_temperature_tiebreaker_dogfood.md"


def test_tiebreaker_dogfood_file_is_emitted(tmp_path):
    project = tmp_path / "project"
    project.mkdir()

    result = pack.build_evidence_pack(project)

    path = result["output_dir"] / TIEBREAKER_DOGFOOD_FILE
    assert path.exists()
    assert path.read_text(encoding="utf-8").strip()


def test_index_links_tiebreaker_dogfood_file(tmp_path):
    project = tmp_path / "project"
    project.mkdir()

    result = pack.build_evidence_pack(project)
    index = (result["output_dir"] / "00_evidence_index.md").read_text(encoding="utf-8")

    assert f"]({TIEBREAKER_DOGFOOD_FILE})" in index
    assert "tie-breaker" in index.lower()


def test_tiebreaker_dogfood_states_live_retrieval_unchanged(tmp_path):
    project = tmp_path / "project"
    project.mkdir()

    result = pack.build_evidence_pack(project)
    md = (result["output_dir"] / TIEBREAKER_DOGFOOD_FILE).read_text(encoding="utf-8")

    assert "live retrieval is unchanged" in md.lower()


def test_tiebreaker_dogfood_states_control_prompt_unchanged(tmp_path):
    project = tmp_path / "project"
    project.mkdir()

    result = pack.build_evidence_pack(project)
    md = (result["output_dir"] / TIEBREAKER_DOGFOOD_FILE).read_text(encoding="utf-8")

    assert "control prompt is unchanged" in md.lower()


def test_tiebreaker_dogfood_states_flag_false_unwired(tmp_path):
    project = tmp_path / "project"
    project.mkdir()

    result = pack.build_evidence_pack(project)
    md = (result["output_dir"] / TIEBREAKER_DOGFOOD_FILE).read_text(encoding="utf-8")

    assert "MEMORY_TEMPERATURE_RETRIEVAL_ENABLED" in md
    lowered = md.lower()
    assert "false" in lowered and "unwired" in lowered


def test_tiebreaker_dogfood_states_cold_not_hard_filtered(tmp_path):
    project = tmp_path / "project"
    project.mkdir()

    result = pack.build_evidence_pack(project)
    md = (result["output_dir"] / TIEBREAKER_DOGFOOD_FILE).read_text(encoding="utf-8")

    lowered = md.lower()
    assert "cold" in lowered
    assert "hard-filter" in lowered  # "never/not hard-filtered"


def test_tiebreaker_dogfood_marks_frozen_audit_blocked_excluded(tmp_path):
    project = tmp_path / "project"
    project.mkdir()

    result = pack.build_evidence_pack(project)
    md = (result["output_dir"] / TIEBREAKER_DOGFOOD_FILE).read_text(encoding="utf-8")

    lowered = md.lower()
    # Explicit statement and the per-candidate exclusion column.
    assert "excluded from control" in lowered
    assert "excluded_from_control" in md
    for term in ("frozen", "audit-only", "blocked"):
        assert term in lowered


def test_tiebreaker_dogfood_contains_representative_table(tmp_path):
    project = tmp_path / "project"
    project.mkdir()

    result = pack.build_evidence_pack(project)
    md = (result["output_dir"] / TIEBREAKER_DOGFOOD_FILE).read_text(encoding="utf-8")

    # The dogfood table header from core.memory_temperature_retrieval_dogfood.
    assert "| item_id |" in md
    assert "original_rank" in md
    assert "adjusted_rank" in md
    assert "temperature_band" in md
    # At least one representative built-in sample candidate is shown.
    assert "blocked-lesson" in md


def test_tiebreaker_dogfood_build_is_read_only(tmp_path):
    project = tmp_path / "project"
    bench = project / ".agent" / "benchmarks"
    full = _write_benchmark_report(bench, "benchmark_report_full.json", total=31, passed=31)
    exp_dir = project / ".agent" / "experiments"
    experiment = _write_json(
        exp_dir / "20260525_patch-minimality.json",
        {
            "experiment_id": "20260525_patch-minimality",
            "title": "Patch minimality metric check",
            "status": "compared",
            "result": {"decision": {"status": "greenlight"}, "metrics": {}},
            "created_at": "2026-05-25T01:30:52+00:00",
        },
    )
    snapshots = {
        path: path.read_text(encoding="utf-8") for path in (full, experiment)
    }

    pack.build_evidence_pack(project)

    # The tie-breaker dogfood is built from a built-in sample; it must not
    # touch (or even read into) the benchmark / experiment source artifacts.
    for path, content in snapshots.items():
        assert path.read_text(encoding="utf-8") == content
    # No stray report files were written under the source artifact dirs.
    assert sorted(p.name for p in bench.glob("*.json")) == ["benchmark_report_full.json"]
    assert sorted(p.name for p in exp_dir.glob("*.json")) == ["20260525_patch-minimality.json"]


def test_pack_module_has_no_tiebreaker_live_wiring():
    import ast

    source = Path(pack.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules: list[str] = []
    call_names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                call_names.append(func.id)
            elif isinstance(func, ast.Attribute):
                call_names.append(func.attr)

    # No live-retrieval / CONTROL-prompt / storage / DB / docker wiring.
    forbidden_modules = {
        "lesson_store",
        "lesson_retrieval",
        "control_engine",
        "database",
        "db",
        "docker",
        "subprocess",
    }
    for imported in imported_modules:
        parts = imported.split(".")
        assert forbidden_modules.isdisjoint(parts), imported

    # No enabling the harness flag, no patching / validation / benchmark exec,
    # no DB writes, no model/API calls.
    forbidden_calls = {
        "enable_control",
        "set_harness_control",
        "apply_patch_plan",
        "generate_patch",
        "run_validation",
        "validate_patch",
        "run_benchmarks",
        "execute",
        "commit",
        "list_lessons",
        "list_active_lessons",
        "save_lesson",
        "promote_lesson",
        "block_lesson",
        "Popen",
        "check_call",
    }
    assert forbidden_calls.isdisjoint(call_names)

    # The harness flag is only ever *described* as false/unwired, never set true.
    assert "MEMORY_TEMPERATURE_RETRIEVAL_ENABLED = True" not in source
    assert "MEMORY_TEMPERATURE_RETRIEVAL_ENABLED=True" not in source
