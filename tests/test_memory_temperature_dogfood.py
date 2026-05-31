"""Phase 12.14c - Memory Temperature Dogfood Experiment Record tests.

The dogfood record is a read-only evidence artifact for the cooling-brain /
memory-temperature work (Phase 12.14a core + 12.14b UI/report visibility). These
tests assert:
- it builds a behavior-focused decision marked
  ``behavior_unchanged_memory_temperature_added``,
- it records the required facts (core added, UI/report visibility added, pytest
  passed, benchmark --check, behavior unchanged, retrieval/ranking influence not
  enabled),
- it reuses the benchmark before/after comparison infrastructure,
- it writes JSON + Markdown into .agent/experiments/ safely,
- it performs no model calls / no network imports.
"""
from __future__ import annotations

import ast
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from core import memory_temperature_dogfood as dogfood


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def tmp_path() -> Path:
    root = PROJECT_ROOT / ".tmp" / "pytest-memory-temperature-dogfood"
    root.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="test-", dir=root))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _roots(tmp_path: Path) -> tuple[Path, Path]:
    agent = tmp_path / ".agent"
    benchmark_root = agent / "benchmarks"
    experiments_root = agent / "experiments"
    benchmark_root.mkdir(parents=True)
    return benchmark_root, experiments_root


def _write_report(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# build_dogfood_record
# --------------------------------------------------------------------------

def test_record_marks_behavior_unchanged_memory_temperature_added(tmp_path):
    benchmark_root, _ = _roots(tmp_path)
    record = dogfood.build_dogfood_record(
        repo_path=tmp_path,
        benchmark_root=benchmark_root,
    )
    assert record["experiment_kind"] == "memory_temperature_dogfood"
    assert record["schema_version"] == dogfood.SCHEMA_VERSION
    decision = record["behavior_decision"]
    assert decision["status"] == "behavior_unchanged_memory_temperature_added"
    assert decision["correctness_unchanged"] is True
    assert decision["benchmark_check"] == "32/0"
    assert decision["pytest_passed"] == 1329
    assert decision["memory_temperature_core_added"] is True
    assert decision["memory_temperature_visibility_added"] is True
    assert decision["retrieval_ranking_influence_enabled"] is False
    assert decision["human_review_required"] is False
    assert record["guardrail"]


def test_record_facts_present_in_markdown(tmp_path):
    benchmark_root, _ = _roots(tmp_path)
    record = dogfood.build_dogfood_record(
        repo_path=tmp_path,
        benchmark_root=benchmark_root,
    )
    md = dogfood.render_dogfood_markdown(record)
    assert "behavior_unchanged_memory_temperature_added" in md
    assert "1329" in md
    assert "32/0" in md
    assert "retrieval" in md.lower() and "not enabled" in md.lower()
    assert record["guardrail"] in md


def test_record_flags_review_when_observed_correctness_changes(tmp_path):
    benchmark_root, _ = _roots(tmp_path)
    _write_report(
        benchmark_root / "benchmark_report_001.json",
        {"total": 32, "passed": 31, "failed": 1, "flaky": 0, "created_at": "2026-05-30T10:00:00+00:00"},
    )
    _write_report(
        benchmark_root / "benchmark_report_002.json",
        {"total": 32, "passed": 30, "failed": 2, "flaky": 0, "created_at": "2026-05-31T10:00:00+00:00"},
    )
    record = dogfood.build_dogfood_record(
        repo_path=tmp_path,
        benchmark_root=benchmark_root,
    )
    decision = record["behavior_decision"]
    assert decision["correctness_unchanged"] is False
    assert decision["status"] == "needs_review_correctness_changed"
    assert decision["human_review_required"] is True


def test_deterministic_id_from_now(tmp_path):
    benchmark_root, _ = _roots(tmp_path)
    fixed = datetime(2026, 5, 31, 12, 30, 45, tzinfo=timezone.utc)
    record = dogfood.build_dogfood_record(
        repo_path=tmp_path,
        benchmark_root=benchmark_root,
        now=fixed,
    )
    assert record["experiment_id"] == "20260531_123045_memory-temperature-dogfood"


def test_write_creates_json_and_markdown(tmp_path):
    benchmark_root, experiments_root = _roots(tmp_path)
    record = dogfood.build_dogfood_record(
        repo_path=tmp_path,
        benchmark_root=benchmark_root,
    )
    out = dogfood.write_dogfood_record(record, experiments_root=experiments_root)
    json_path = Path(out["json_path"])
    md_path = Path(out["md_path"])
    assert json_path.is_file()
    assert md_path.is_file()
    assert json_path.name.endswith("_memory-temperature-dogfood.json")
    saved = json.loads(json_path.read_text(encoding="utf-8"))
    assert saved == record
    json_path.resolve().relative_to(experiments_root.resolve())


def test_create_orchestrates_build_and_write(tmp_path):
    benchmark_root, experiments_root = _roots(tmp_path)
    out = dogfood.create_memory_temperature_dogfood(
        repo_path=tmp_path,
        benchmark_root=benchmark_root,
        experiments_root=experiments_root,
    )
    assert Path(out["json_path"]).is_file()
    assert Path(out["md_path"]).is_file()
    assert out["record"]["experiment_kind"] == "memory_temperature_dogfood"


def test_module_has_no_forbidden_imports():
    source = (PROJECT_ROOT / "core" / "memory_temperature_dogfood.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    forbidden = {"requests", "httpx", "urllib", "aiohttp", "socket", "subprocess", "openai"}
    assert not (imported & forbidden), f"forbidden imports found: {imported & forbidden}"
