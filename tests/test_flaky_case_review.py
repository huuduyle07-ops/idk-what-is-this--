"""Tests for A.17 — Flaky Case Review Report (report-only).

Covers the prescribed cases:
1.  explicit ``flaky: true`` is detected.
2.  attempts > 1 with a final pass is detected.
3.  first fail then later pass classifies as model variance.
4.  timeout / env-like validation output classifies as environment.
5.  generated-artifact involvement classifies as scope noise.
6.  unexpected-mutation involvement classifies as mutation noise.
7.  provider / fallback variance classification.
8.  ambiguous / missing fields classify as unknown or report-shape.
9.  no flaky cases produces a valid empty review.
10. Markdown contains summary / table / boundaries.
11. JSON output carries source report path and benchmarks_run_by_tool=false.
12. CLI writes JSON + Markdown.
13. deterministic ``--review-id`` and ``--created-at``.
14. the source report is never modified.
15. no forbidden imports / calls (model, patch apply, validation execution,
    Dream, Project Evolution, network, lesson promotion, proposal import,
    worker launch, benchmark execution).
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from core.flaky_case_review import (
    FLAKY_CATEGORIES,
    FLAKY_REVIEW_GUARDRAIL_NOTE,
    RECOMMENDED_ACTIONS,
    build_flaky_case_review,
    build_flaky_case_review_from_empty,
    classify_flaky_case,
    find_latest_benchmark_report,
    flaky_signals,
    load_benchmark_report,
    render_flaky_case_review_markdown,
)
import scripts.create_flaky_case_review as script


# ── helpers ───────────────────────────────────────────────────────────────────

def _retry(attempt: int, success: bool, vout: str = "", rlog: str = "") -> dict:
    return {
        "attempt": attempt,
        "success": success,
        "validation_ok": success,
        "validation_output_tail": vout,
        "runner_log_tail": rlog,
        "duration_sec": 1.0,
    }


def _result(name: str = "case_x", success: bool = True, **over) -> dict:
    base = {
        "name": name,
        "success": success,
        "attempts": 1,
        "flaky": False,
        "retry_results": [],
        "language": "python",
        "category": "logic_error",
        "difficulty": "medium",
        "changed_files": [],
        "patched_files": [],
        "generated_artifacts": [],
        "unexpected_mutations": [],
        "missing_expected_files": [],
        "touched_forbidden_files": [],
        "validation_output": "",
        "runner_log_tail": "",
        "toolchain_issue": None,
        "rollback_happened": False,
        "fallback_count": 0,
        "selected_model": "model-a",
        "models_by_role": {"reviewer": "model-a"},
        "duration_sec": 1.0,
        "total_tokens": 100,
        "estimated_cost_usd": 0.001,
    }
    base.update(over)
    return base


def _report(results: list[dict], **over) -> dict:
    base = {
        "total": len(results),
        "passed": sum(1 for r in results if r.get("success")),
        "failed": sum(1 for r in results if r.get("success") is False),
        "skipped": 0,
        "flaky": sum(1 for r in results if r.get("flaky")),
        "results": results,
    }
    base.update(over)
    return base


def _flaky_clean(name: str, **over) -> dict:
    """A well-formed flaky result: failed attempt 1, passed attempt 2."""
    defaults = dict(
        success=True,
        attempts=2,
        flaky=True,
        retry_results=[_retry(1, False), _retry(2, True)],
    )
    defaults.update(over)
    return _result(name, **defaults)


def _find(review: dict, name: str) -> dict | None:
    for c in review.get("flaky_cases", []):
        if c.get("name") == name:
            return c
    return None


# ── 1. explicit flaky: true ───────────────────────────────────────────────────

def test_explicit_flaky_flag_detected():
    r = _flaky_clean("c1", flaky=True)
    review = build_flaky_case_review(_report([r]))
    assert review["summary"]["flaky_cases_found"] == 1
    case = _find(review, "c1")
    assert case is not None
    assert case["flaky_flag"] is True
    assert "explicit_flaky_flag" in case["flaky_signals"]


def test_explicit_flaky_flag_without_retry_still_detected():
    # flaky asserted with no attempt trail — still surfaced.
    r = _result("c1b", success=True, flaky=True, attempts=1, retry_results=[])
    review = build_flaky_case_review(_report([r]))
    assert _find(review, "c1b") is not None


def test_report_flaky_list_names_case():
    r = _result("c1c", success=True, attempts=1, flaky=False)
    review = build_flaky_case_review(_report([r], flaky_cases=["c1c"]))
    case = _find(review, "c1c")
    assert case is not None
    assert "named_in_report_flaky_list" in case["flaky_signals"]


# ── 2. attempts > 1 with final pass ───────────────────────────────────────────

def test_attempts_gt_one_final_pass_detected():
    r = _result(
        "c2",
        success=True,
        attempts=3,
        flaky=False,
        retry_results=[_retry(1, False), _retry(2, False), _retry(3, True)],
    )
    review = build_flaky_case_review(_report([r]))
    case = _find(review, "c2")
    assert case is not None
    assert case["attempts"] == 3
    assert "multiple_attempts_final_pass" in case["flaky_signals"]


# ── 3. first fail then later pass → model variance ────────────────────────────

def test_first_fail_then_pass_classified_model_variance():
    r = _flaky_clean(
        "c3",
        retry_results=[
            _retry(1, False, vout="AssertionError: expected 3 got 2"),
            _retry(2, True),
        ],
    )
    case = _find(build_flaky_case_review(_report([r])), "c3")
    assert case["category"] == "model_variance_or_prompt_instability"
    assert case["confidence"] == "high"
    assert case["recommended_action"] == "add_stability_replay"


# ── 4. timeout / env validation output → environment ──────────────────────────

def test_env_validation_output_classified_environment():
    # mirrors the real cpp_string_view_lifetime_trap flake (ld permission denied).
    r = _flaky_clean(
        "c4",
        retry_results=[
            _retry(1, False, vout="ld.exe: cannot open output file ... Permission denied"),
            _retry(2, True),
        ],
    )
    case = _find(build_flaky_case_review(_report([r])), "c4")
    assert case["category"] == "validation_timing_or_environment"
    assert case["recommended_action"] == "inspect_validation_environment"


def test_timeout_validation_output_classified_environment():
    r = _flaky_clean(
        "c4t",
        retry_results=[_retry(1, False, vout="TimeoutError: validation timed out"), _retry(2, True)],
    )
    case = _find(build_flaky_case_review(_report([r])), "c4t")
    assert case["category"] == "validation_timing_or_environment"


def test_toolchain_issue_classified_environment():
    r = _flaky_clean("c4b", toolchain_issue="python command not available")
    case = _find(build_flaky_case_review(_report([r])), "c4b")
    assert case["category"] == "validation_timing_or_environment"


def test_node_module_not_found_classified_environment():
    # Node/TS import error — spec lists "import error" under environment, and
    # this must classify the same way as the Python ModuleNotFoundError signal.
    r = _flaky_clean(
        "c4n",
        retry_results=[
            _retry(1, False, vout="Error [ERR_MODULE_NOT_FOUND]: Cannot find module './pricing.ts'"),
            _retry(2, True),
        ],
    )
    case = _find(build_flaky_case_review(_report([r])), "c4n")
    assert case["category"] == "validation_timing_or_environment"


# ── 5. generated artifact → scope noise ───────────────────────────────────────

def test_generated_artifact_classified_scope_noise():
    r = _flaky_clean("c5", generated_artifacts=["build/out.o"], unexpected_mutations=[])
    case = _find(build_flaky_case_review(_report([r])), "c5")
    assert case["category"] == "generated_artifact_scope_noise"
    assert case["recommended_action"] == "tighten_allowed_files_or_generated_ignore"


# ── 6. unexpected mutation → mutation noise ───────────────────────────────────

def test_unexpected_mutation_classified():
    r = _flaky_clean("c6", unexpected_mutations=["src/secret_state.py"])
    case = _find(build_flaky_case_review(_report([r])), "c6")
    assert case["category"] == "unexpected_mutation_noise"
    assert case["confidence"] == "high"


# ── 7. provider / fallback variance ───────────────────────────────────────────

def test_fallback_variance_classified():
    r = _flaky_clean("c7", fallback_count=2)
    case = _find(build_flaky_case_review(_report([r])), "c7")
    assert case["category"] == "fallback_or_provider_variance"
    assert case["recommended_action"] == "inspect_model_fallback_path"


# ── 8. ambiguous / missing fields → unknown or report-shape ───────────────────

def test_ambiguous_fields_classified_unknown_or_shape():
    # flaky asserted but success is non-boolean and no attempt trail.
    r = _result("c8", success=None, flaky=True, attempts=1, retry_results=[])
    case = _find(build_flaky_case_review(_report([r])), "c8")
    assert case is not None
    assert case["category"] in (
        "test_harness_or_report_shape_issue",
        "unknown_flake",
    )


def test_classify_returns_valid_members():
    r = _flaky_clean("cz")
    sigs = flaky_signals(r, _report([r]))
    out = classify_flaky_case(r, sigs)
    assert out["category"] in FLAKY_CATEGORIES
    assert out["recommended_action"] in RECOMMENDED_ACTIONS
    assert out["confidence"] in ("high", "low")


# ── 9. no flaky cases → valid empty review ────────────────────────────────────

def test_no_flaky_cases_valid_empty_review():
    r = _result("clean", success=True, attempts=1, flaky=False, retry_results=[])
    review = build_flaky_case_review(_report([r]), source_report_path="x.json")
    assert review["summary"]["flaky_cases_found"] == 0
    assert review["summary"]["total_cases_read"] == 1
    assert review["flaky_cases"] == []
    assert not review.get("no_input")
    # rendering an empty review still works.
    md = render_flaky_case_review_markdown(review)
    assert "Flaky Case Review" in md


def test_build_from_empty_is_valid():
    review = build_flaky_case_review_from_empty()
    assert review["report_kind"] == "flaky_case_review"
    assert review["summary"]["flaky_cases_found"] == 0
    assert review["summary"]["benchmarks_run_by_tool"] is False
    assert review["no_input"] is True
    assert review["flaky_cases"] == []


# ── 10. Markdown contains summary / table / boundaries ────────────────────────

def test_markdown_contains_summary_table_boundaries():
    r = _flaky_clean("c10")
    md = render_flaky_case_review_markdown(build_flaky_case_review(_report([r])))
    assert "# Flaky Case Review" in md
    assert "## Summary" in md
    assert "## Flaky Cases" in md
    assert (
        "| Case | Final | Attempts | Category | Confidence | Recommended action |"
        in md
    )
    assert "## Case Details" in md
    assert "## Boundaries" in md
    # boundary statements
    low = md.lower()
    assert "does not fix" in low
    assert "does not run benchmark" in low
    assert "does not call" in low and "model" in low
    # per-case detail sub-points
    assert "Evidence" in md
    assert "Why this category" in md
    assert "Next action" in md
    assert "What not to change yet" in md


# ── 11. JSON carries source report path + benchmarks_run_by_tool=false ────────

def test_json_summary_contains_source_and_flags():
    r = _flaky_clean("c11")
    review = build_flaky_case_review(
        _report([r]), source_report_path="/a/b/benchmark_report_1.json"
    )
    assert review["source_report_path"] == "/a/b/benchmark_report_1.json"
    assert review["summary"]["benchmarks_run_by_tool"] is False
    assert review["summary"]["source_report_modified"] is False
    assert review["boundaries"]["runs_benchmarks"] is False
    assert review["boundaries"]["calls_models"] is False
    assert review["report_kind"] == "flaky_case_review"
    assert review["guardrail_note"] == FLAKY_REVIEW_GUARDRAIL_NOTE


def test_summary_category_and_confidence_counts():
    results = [
        _flaky_clean("m1"),  # model variance, high
        _flaky_clean("e1", toolchain_issue="go command not available"),  # env, high
        _flaky_clean("g1", generated_artifacts=["a/b.o"]),  # generated, low
    ]
    review = build_flaky_case_review(_report(results))
    summary = review["summary"]
    assert summary["flaky_cases_found"] == 3
    # category counts cover every category key
    assert set(summary["category_counts"]) == set(FLAKY_CATEGORIES)
    assert summary["category_counts"]["model_variance_or_prompt_instability"] == 1
    assert summary["category_counts"]["validation_timing_or_environment"] == 1
    assert summary["category_counts"]["generated_artifact_scope_noise"] == 1
    assert summary["high_confidence_count"] + summary["low_confidence_count"] == 3
    assert summary["high_confidence_count"] == 2


# ── 12. CLI writes JSON + Markdown ────────────────────────────────────────────

def test_cli_writes_json_and_markdown(tmp_path):
    bdir = tmp_path / ".agent" / "benchmarks"
    bdir.mkdir(parents=True)
    rp = bdir / "benchmark_report_1700000000.json"
    rp.write_text(json.dumps(_report([_flaky_clean("c12")])), encoding="utf-8")

    out = tmp_path / "out"
    res = script.run_flaky_case_review(
        repo_path=str(tmp_path),
        report=str(rp),
        review_id="rev1",
        created_at="2026-06-16T00:00:00+00:00",
        output_root=str(out),
    )
    assert res["ok"] is True
    jp = Path(res["json_path"])
    mp = Path(res["md_path"])
    assert jp.is_file()
    assert mp.is_file()
    assert jp.parent.name == "rev1"
    assert jp.name == "flaky_case_review.json"
    assert mp.name == "flaky_case_review.md"

    data = json.loads(jp.read_text(encoding="utf-8"))
    assert data["review_id"] == "rev1"
    assert data["summary"]["flaky_cases_found"] == 1
    assert data["source_report_path"] == str(rp)

    md = mp.read_text(encoding="utf-8")
    assert "# Flaky Case Review" in md
    assert "## Boundaries" in md


def test_run_with_latest_finds_newest(tmp_path):
    bdir = tmp_path / ".agent" / "benchmarks"
    bdir.mkdir(parents=True)
    (bdir / "benchmark_report_1700000000.json").write_text(
        json.dumps(_report([_result("old_clean")])), encoding="utf-8"
    )
    (bdir / "benchmark_report_1800000000.json").write_text(
        json.dumps(_report([_flaky_clean("newcase")])), encoding="utf-8"
    )
    res = script.run_flaky_case_review(
        repo_path=str(tmp_path),
        use_latest=True,
        review_id="rev2",
        created_at="2026-06-16T00:00:00+00:00",
        output_root=str(tmp_path / "o"),
    )
    assert res["ok"] is True
    assert "benchmark_report_1800000000.json" in res["review"]["source_report_path"]
    assert res["review"]["summary"]["flaky_cases_found"] == 1


def test_explicit_missing_report_returns_error(tmp_path):
    res = script.run_flaky_case_review(
        repo_path=str(tmp_path),
        report=str(tmp_path / "nope.json"),
        review_id="rev",
        created_at="2026-06-16T00:00:00+00:00",
        output_root=str(tmp_path / "o"),
    )
    assert res["ok"] is False
    assert "not found" in res["error"]


def test_no_report_found_produces_empty_review(tmp_path):
    res = script.run_flaky_case_review(
        repo_path=str(tmp_path),
        use_latest=True,
        review_id="rev",
        created_at="2026-06-16T00:00:00+00:00",
        output_root=str(tmp_path / "o"),
    )
    assert res["ok"] is True
    assert res["review"]["no_input"] is True
    assert Path(res["json_path"]).is_file()


# ── 13. deterministic review-id and created-at ───────────────────────────────

def test_deterministic_review_id_and_created_at(tmp_path):
    rp = tmp_path / "r.json"
    rp.write_text(json.dumps(_report([_flaky_clean("c13")])), encoding="utf-8")

    def run(outname: str) -> dict:
        return script.run_flaky_case_review(
            repo_path=str(tmp_path),
            report=str(rp),
            review_id="fixed-id",
            created_at="2026-06-16T12:00:00+00:00",
            output_root=str(tmp_path / outname),
        )

    a = run("a")
    b = run("b")
    da = Path(a["json_path"]).read_text(encoding="utf-8")
    db = Path(b["json_path"]).read_text(encoding="utf-8")
    assert da == db  # byte-for-byte deterministic
    data = json.loads(da)
    assert data["review_id"] == "fixed-id"
    assert data["created_at"] == "2026-06-16T12:00:00+00:00"
    assert Path(a["json_path"]).parent.name == "fixed-id"


# ── 14. source report not modified ────────────────────────────────────────────

def test_source_report_not_modified(tmp_path):
    rp = tmp_path / "r.json"
    rp.write_text(json.dumps(_report([_flaky_clean("c14")]), indent=2), encoding="utf-8")
    before = rp.read_bytes()
    script.run_flaky_case_review(
        repo_path=str(tmp_path),
        report=str(rp),
        review_id="rev",
        created_at="2026-06-16T00:00:00+00:00",
        output_root=str(tmp_path / "o"),
    )
    assert rp.read_bytes() == before


# ── find_latest / load helpers ────────────────────────────────────────────────

def test_find_latest_benchmark_report_picks_newest(tmp_path):
    bdir = tmp_path / ".agent" / "benchmarks"
    bdir.mkdir(parents=True)
    (bdir / "benchmark_report_1700000000.json").write_text("{}", encoding="utf-8")
    (bdir / "benchmark_report_1800000000.json").write_text("{}", encoding="utf-8")
    found = find_latest_benchmark_report(tmp_path)
    assert found is not None
    assert found.name == "benchmark_report_1800000000.json"


def test_find_latest_returns_none_when_absent(tmp_path):
    assert find_latest_benchmark_report(tmp_path) is None


def test_load_benchmark_report_rejects_non_dict(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("[1, 2, 3]", encoding="utf-8")
    assert load_benchmark_report(p) is None


# ── 15. import / side-effect guard ────────────────────────────────────────────

_CORE = Path(__file__).parent.parent / "core" / "flaky_case_review.py"
_SCRIPT = Path(__file__).parent.parent / "scripts" / "create_flaky_case_review.py"
_CORE_SRC = _CORE.read_text(encoding="utf-8")
_SCRIPT_SRC = _SCRIPT.read_text(encoding="utf-8")
_BOTH = _CORE_SRC + "\n" + _SCRIPT_SRC


def test_core_imports_only_stdlib():
    stdlib_ok = {"__future__", "json", "pathlib", "typing"}
    tree = ast.parse(_CORE_SRC)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            top = (node.module or "").split(".")[0]
            assert top in stdlib_ok, f"Unexpected import in core: {node.module!r}"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                assert top in stdlib_ok, f"Unexpected import in core: {alias.name!r}"


def test_no_model_clients():
    for bad in ("anthropic", "openai", "litellm", "ollama", "bedrock", "generativeai"):
        assert bad not in _BOTH, f"Found model client token {bad!r}"


def test_no_subprocess_or_exec():
    for bad in ("subprocess", "Popen", "os.system", "exec(", "eval("):
        assert bad not in _BOTH, f"Found process-spawning token {bad!r}"


def test_no_patch_apply():
    for bad in ("apply_patch", "patch_apply", "run_patch"):
        assert bad not in _BOTH, f"Found patch-apply token {bad!r}"


def test_no_validation_execution():
    for bad in ("run_validation_command", "run_validation"):
        assert bad not in _BOTH, f"Found validation-execution token {bad!r}"


def test_no_network_clients():
    for bad in ("requests", "httpx", "urllib.request", "socket", "aiohttp"):
        assert bad not in _BOTH, f"Found network token {bad!r}"


def test_no_dream_or_project_evolution_execution():
    for bad in ("dream_taxonomy", "dream_trials", "project_evolution", "reverse_dream"):
        assert bad not in _BOTH, f"Found subsystem token {bad!r}"


def test_no_lesson_promotion():
    for bad in ("promote_lesson", "lesson_store", "save_active_lesson"):
        assert bad not in _BOTH, f"Found lesson-promotion token {bad!r}"


def test_no_proposal_import_or_worker_launch():
    for bad in ("import_proposal", "proposal_runner", "worker_launch", "launch_worker"):
        assert bad not in _BOTH, f"Found proposal/worker token {bad!r}"


def test_no_benchmark_execution():
    for bad in ("run_benchmarks", "run_agent_web", "run_case("):
        assert bad not in _BOTH, f"Found benchmark-execution token {bad!r}"


def test_categories_and_actions_are_stable():
    assert set(FLAKY_CATEGORIES) == {
        "model_variance_or_prompt_instability",
        "validation_timing_or_environment",
        "generated_artifact_scope_noise",
        "unexpected_mutation_noise",
        "fallback_or_provider_variance",
        "test_harness_or_report_shape_issue",
        "safety_gate_boundary_case",
        "unknown_flake",
    }
    assert set(RECOMMENDED_ACTIONS) == {
        "add_stability_replay",
        "tighten_allowed_files_or_generated_ignore",
        "inspect_validation_environment",
        "inspect_model_fallback_path",
        "add_report_schema_guard",
        "promote_to_honeypot_or_regression_case",
        "manual_review_required",
        "no_action_yet_monitor_only",
    }
