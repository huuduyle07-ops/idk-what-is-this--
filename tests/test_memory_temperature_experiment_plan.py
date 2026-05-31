"""Phase 12.14d - Memory Temperature Retrieval Experiment Plan tests.

The plan is a read-only experiment-design artifact. It does NOT enable memory
temperature to affect retrieval or ranking. These tests assert it writes a
JSON + Markdown plan under ``.agent/experiments/`` that states the safety
constraints, the default-off feature flags, the tie-breaker-only first
experiment, the no-cold-filtering / frozen-excluded rules, the
greenlight/needs_review/reject decision policy, and the full guardrail text;
and that the module imports/calls nothing dangerous.
"""
from __future__ import annotations

import ast
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from core import memory_temperature_experiment_plan as plan


PROJECT_ROOT = Path(__file__).resolve().parent.parent

FULL_GUARDRAIL = (
    "This phase only writes an experiment plan. It does not change lesson "
    "retrieval, CONTROL prompts, ranking, patch generation, validation, "
    "benchmark scoring, lesson storage, model calls, or DB behavior."
)


@pytest.fixture
def tmp_path() -> Path:
    root = PROJECT_ROOT / ".tmp" / "pytest-memory-temperature-plan"
    root.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="test-", dir=root))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _experiments_root(tmp_path: Path) -> Path:
    return tmp_path / ".agent" / "experiments"


# --------------------------------------------------------------------------
# 1 + 2 + 9: artifacts are written under .agent/experiments
# --------------------------------------------------------------------------

def test_plan_json_written_under_experiments(tmp_path):
    out = plan.create_memory_temperature_retrieval_plan(
        experiments_root=_experiments_root(tmp_path),
    )
    json_path = Path(out["json_path"])
    assert json_path.is_file()
    assert json_path.suffix == ".json"
    assert json_path.name.endswith("_memory-temperature-retrieval-plan.json")
    json_path.resolve().relative_to(_experiments_root(tmp_path).resolve())
    saved = json.loads(json_path.read_text(encoding="utf-8"))
    assert saved == out["record"]


def test_plan_markdown_written_under_experiments(tmp_path):
    out = plan.create_memory_temperature_retrieval_plan(
        experiments_root=_experiments_root(tmp_path),
    )
    md_path = Path(out["md_path"])
    assert md_path.is_file()
    assert md_path.suffix == ".md"
    assert md_path.read_text(encoding="utf-8").strip()


def test_cli_writes_both_artifacts(tmp_path, monkeypatch, capsys):
    from scripts import plan_memory_temperature_retrieval_experiment as cli

    experiments_root = _experiments_root(tmp_path)
    monkeypatch.setattr(
        plan.experiments, "default_experiments_root", lambda: experiments_root
    )

    rc = cli.main([])
    assert rc == 0
    captured = capsys.readouterr().out
    assert "experiment_id:" in captured
    produced_json = list(experiments_root.glob("*_memory-temperature-retrieval-plan.json"))
    produced_md = list(experiments_root.glob("*_memory-temperature-retrieval-plan.md"))
    assert len(produced_json) == 1
    assert len(produced_md) == 1


# --------------------------------------------------------------------------
# 3 + 4 + 5 + 6: safety content
# --------------------------------------------------------------------------

def _build_md(tmp_path) -> str:
    record = plan.build_experiment_plan()
    return plan.render_plan_markdown(record)


def test_plan_includes_default_off_feature_flag(tmp_path):
    record = plan.build_experiment_plan()
    md = plan.render_plan_markdown(record).lower()
    assert "memory_temperature_retrieval_enabled" in md
    assert "false" in md
    assert "default off" in md
    # The flag is also structured in the record.
    flags = {f["name"]: f for f in record["feature_flags"]}
    assert flags["MEMORY_TEMPERATURE_RETRIEVAL_ENABLED"]["default"] == "false"


def test_plan_says_tiebreaker_only(tmp_path):
    record = plan.build_experiment_plan()
    md = plan.render_plan_markdown(record).lower()
    assert "tie-breaker" in md
    assert "memory_temperature_tiebreak_only" in md
    flags = {f["name"]: f for f in record["feature_flags"]}
    assert flags["MEMORY_TEMPERATURE_TIEBREAK_ONLY"]["default"] == "true"


def test_plan_forbids_cold_memory_hard_filtering(tmp_path):
    md = _build_md(tmp_path).lower()
    assert "cold" in md
    assert "no hard filtering" in md or "must not" in md
    # Explicitly scoped to the first experiment.
    assert "first experiment" in md


def test_plan_keeps_frozen_audit_only_excluded(tmp_path):
    md = _build_md(tmp_path).lower()
    assert "frozen" in md
    assert "audit-only" in md
    assert "excluded" in md or "never" in md


# --------------------------------------------------------------------------
# 7: decision policy
# --------------------------------------------------------------------------

def test_plan_includes_decision_policy(tmp_path):
    record = plan.build_experiment_plan()
    policy = record["decision_policy"]
    assert policy["greenlight"]
    assert policy["needs_review"]
    assert policy["reject"]

    md = plan.render_plan_markdown(record).lower()
    assert "greenlight" in md
    assert "needs_review" in md or "needs review" in md
    assert "reject" in md
    # Key reject triggers from the spec.
    assert "passed" in md
    assert "failed" in md
    assert "flaky" in md
    # Frozen/audit-only becoming retrievable is a hard reject.
    assert "retrievable" in md


def test_plan_protocol_runs_dev_then_held_out(tmp_path):
    md = _build_md(tmp_path).lower()
    assert "dev suite" in md
    assert "held-out" in md
    # held-out only after dev passes.
    assert "after dev" in md or "only after" in md
    # baseline vs experiment via existing registry.
    assert "baseline" in md and "experiment" in md
    assert "registry" in md


# --------------------------------------------------------------------------
# 8: full guardrail text
# --------------------------------------------------------------------------

def test_plan_includes_full_guardrail_text(tmp_path):
    record = plan.build_experiment_plan()
    assert record["guardrail"] == FULL_GUARDRAIL
    md = plan.render_plan_markdown(record)
    assert FULL_GUARDRAIL in md


def test_deterministic_id_from_now(tmp_path):
    fixed = datetime(2026, 5, 31, 9, 8, 7, tzinfo=timezone.utc)
    record = plan.build_experiment_plan(now=fixed)
    assert record["experiment_id"] == "20260531_090807_memory-temperature-retrieval-plan"


# --------------------------------------------------------------------------
# 10: forbidden imports / calls AST guard
# --------------------------------------------------------------------------

def test_module_has_no_forbidden_imports_or_calls():
    source = (
        PROJECT_ROOT / "core" / "memory_temperature_experiment_plan.py"
    ).read_text(encoding="utf-8")
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

    # No patching, model/API, validation, benchmark runner, or lesson-behavior
    # modules may be imported (names may still appear in plain plan text).
    forbidden_import_areas = (
        "model",
        "api",
        "patching",
        "validation",
        "validator",
        "run_benchmarks",
        "lesson_retrieval",
        "lesson_store",
        "control_engine",
    )
    for imported in imported_modules:
        parts = imported.split(".")
        for forbidden in forbidden_import_areas:
            assert not any(part == forbidden for part in parts), imported

    # No network / DB clients.
    forbidden_top_level = {
        "requests",
        "httpx",
        "urllib",
        "aiohttp",
        "socket",
        "subprocess",
        "openai",
        "psycopg2",
        "sqlite3",
        "sqlalchemy",
    }
    assert forbidden_top_level.isdisjoint(part.split(".")[0] for part in imported_modules)

    forbidden_calls = {
        "call_model",
        "call_api",
        "run_gemini_request",
        "validate",
        "run_benchmarks",
        "start_benchmark_run_async",
        "promote_lesson",
        "save_candidate_lesson",
        "find_active_lessons",
        "list_active_lessons",
    }
    assert forbidden_calls.isdisjoint(call_names)
