"""Phase 12.13g - Explainability Dogfood Experiment Record tests.

The dogfood record is a read-only evidence artifact. These tests assert:
- it builds a behavior-focused decision (correctness unchanged, 32/0, pytest, explainability added),
- it references the five explainability artifacts from Phase 12.12-12.13f,
- it compares the latest two meaningful benchmark reports when available,
- it writes JSON + Markdown into .agent/experiments/ safely,
- it performs no model calls / no heavy imports.
"""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from core import explainability_dogfood as dogfood


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def tmp_path() -> Path:
    root = PROJECT_ROOT / ".tmp" / "pytest-explainability-dogfood"
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


def _fake_repo_with_sources(root: Path) -> Path:
    """Create the source files the artifact references point at."""
    for rel in (
        "web/graph_evidence.py",
        "graph/attraction.py",
        "core/related_notes.py",
        "scripts/explain_graph_weights.py",
    ):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# stub\n", encoding="utf-8")
    return root


# --------------------------------------------------------------------------
# build_explainability_artifacts
# --------------------------------------------------------------------------

def test_artifacts_cover_the_five_required_references(tmp_path):
    repo = _fake_repo_with_sources(tmp_path)
    artifacts = dogfood.build_explainability_artifacts(repo_path=repo)
    names = [a["name"] for a in artifacts]
    assert len(artifacts) == 5
    joined = " | ".join(names).lower()
    assert "evidence confidence" in joined
    assert "attraction" in joined and "repulsion" in joined
    assert "related notes" in joined
    assert "smoke" in joined
    assert "07_graph_attraction_explainability.md" in joined


def test_artifacts_existence_reflects_source_files(tmp_path):
    repo = _fake_repo_with_sources(tmp_path)
    artifacts = dogfood.build_explainability_artifacts(repo_path=repo)
    by_path = {a["source_path"]: a for a in artifacts}
    assert by_path["core/related_notes.py"]["exists"] is True
    # The presentation pack file is not generated in this fake repo.
    pack = next(a for a in artifacts if a["kind"] == "pack_file")
    assert pack["exists"] is False


# --------------------------------------------------------------------------
# build_dogfood_record
# --------------------------------------------------------------------------

def test_record_has_behavior_focused_decision(tmp_path):
    benchmark_root, _ = _roots(tmp_path)
    record = dogfood.build_dogfood_record(
        repo_path=tmp_path,
        benchmark_root=benchmark_root,
    )
    assert record["experiment_kind"] == "explainability_dogfood"
    assert record["schema_version"] == dogfood.SCHEMA_VERSION
    decision = record["behavior_decision"]
    assert decision["correctness_unchanged"] is True
    assert decision["benchmark_check"] == "32/0"
    assert decision["pytest_passed"] == 1294
    assert decision["explainability_added"] is True
    assert decision["human_review_required"] is False
    assert record["guardrail"]
    assert len(record["explainability_artifacts"]) == 5


def test_record_compares_latest_two_reports_when_available(tmp_path):
    benchmark_root, _ = _roots(tmp_path)
    _write_report(
        benchmark_root / "benchmark_report_001.json",
        {"total": 32, "passed": 31, "failed": 0, "flaky": 1, "created_at": "2026-05-30T10:00:00+00:00"},
    )
    _write_report(
        benchmark_root / "benchmark_report_002.json",
        {"total": 32, "passed": 31, "failed": 0, "flaky": 1, "created_at": "2026-05-31T10:00:00+00:00"},
    )
    record = dogfood.build_dogfood_record(
        repo_path=tmp_path,
        benchmark_root=benchmark_root,
    )
    comparison = record["benchmark_comparison"]
    assert comparison["available"] is True
    # Newer report is the variant (after), older is baseline (before).
    assert comparison["variant_report"] == "benchmark_report_002.json"
    assert comparison["baseline_report"] == "benchmark_report_001.json"
    assert comparison["correctness_unchanged"] is True
    assert comparison["metrics"]["passed"]["delta"] == 0
    assert record["behavior_decision"]["human_review_required"] is False


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
    comparison = record["benchmark_comparison"]
    assert comparison["available"] is True
    assert comparison["correctness_unchanged"] is False
    # Observed regression overrides the asserted default.
    decision = record["behavior_decision"]
    assert decision["correctness_unchanged"] is False
    assert decision["human_review_required"] is True


def test_record_inconclusive_when_suite_size_differs(tmp_path):
    # A partial run (7 cases) vs a full run (32 cases) is not a comparable
    # before/after pair: passed "increasing" is not a regression.
    benchmark_root, _ = _roots(tmp_path)
    _write_report(
        benchmark_root / "benchmark_report_001.json",
        {"total": 7, "passed": 7, "failed": 0, "flaky": 0, "created_at": "2026-05-30T10:00:00+00:00"},
    )
    _write_report(
        benchmark_root / "benchmark_report_002.json",
        {"total": 32, "passed": 31, "failed": 0, "flaky": 1, "created_at": "2026-05-31T10:00:00+00:00"},
    )
    record = dogfood.build_dogfood_record(
        repo_path=tmp_path,
        benchmark_root=benchmark_root,
    )
    comparison = record["benchmark_comparison"]
    assert comparison["available"] is True
    assert comparison["correctness_unchanged"] is None
    assert comparison["correctness_note"]
    # Inconclusive observation falls back to the asserted "unchanged" fact.
    decision = record["behavior_decision"]
    assert decision["correctness_unchanged"] is True
    assert decision["correctness_basis"] == "asserted"
    assert decision["human_review_required"] is False


def test_record_handles_no_reports_gracefully(tmp_path):
    benchmark_root, _ = _roots(tmp_path)
    record = dogfood.build_dogfood_record(
        repo_path=tmp_path,
        benchmark_root=benchmark_root,
    )
    comparison = record["benchmark_comparison"]
    assert comparison["available"] is False
    assert comparison["note"]
    # Falls back to the asserted behavior facts.
    assert record["behavior_decision"]["correctness_unchanged"] is True


def test_deterministic_id_from_now(tmp_path):
    from datetime import datetime, timezone

    benchmark_root, _ = _roots(tmp_path)
    fixed = datetime(2026, 5, 31, 12, 30, 45, tzinfo=timezone.utc)
    record = dogfood.build_dogfood_record(
        repo_path=tmp_path,
        benchmark_root=benchmark_root,
        now=fixed,
    )
    assert record["experiment_id"] == "20260531_123045_explainability-stack-dogfood"


# --------------------------------------------------------------------------
# render_dogfood_markdown
# --------------------------------------------------------------------------

def test_markdown_includes_references_and_decision(tmp_path):
    benchmark_root, _ = _roots(tmp_path)
    record = dogfood.build_dogfood_record(
        repo_path=tmp_path,
        benchmark_root=benchmark_root,
    )
    md = dogfood.render_dogfood_markdown(record)
    assert "Evidence Confidence" in md
    assert "Graph Attraction / Repulsion" in md
    assert "Related Notes" in md
    assert "07_graph_attraction_explainability.md" in md
    assert "32/0" in md
    assert "1294" in md
    assert record["guardrail"] in md


# --------------------------------------------------------------------------
# write_dogfood_record / create_explainability_dogfood
# --------------------------------------------------------------------------

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
    assert json_path.suffix == ".json"
    assert md_path.suffix == ".md"
    assert json_path.name.endswith("_explainability-stack-dogfood.json")
    saved = json.loads(json_path.read_text(encoding="utf-8"))
    assert saved == record
    # Output stays inside the experiments root.
    json_path.resolve().relative_to(experiments_root.resolve())


def test_create_orchestrates_build_and_write(tmp_path):
    benchmark_root, experiments_root = _roots(tmp_path)
    out = dogfood.create_explainability_dogfood(
        repo_path=tmp_path,
        benchmark_root=benchmark_root,
        experiments_root=experiments_root,
    )
    assert Path(out["json_path"]).is_file()
    assert Path(out["md_path"]).is_file()
    assert out["record"]["experiment_kind"] == "explainability_dogfood"


# --------------------------------------------------------------------------
# Guardrails: no model / no network imports
# --------------------------------------------------------------------------

def test_cli_happy_path(tmp_path, monkeypatch, capsys):
    from scripts import create_explainability_dogfood as cli

    benchmark_root, experiments_root = _roots(tmp_path)
    _fake_repo_with_sources(tmp_path)

    # Point the default experiment/benchmark roots at the temp dirs.
    monkeypatch.setattr(
        dogfood.experiments, "default_experiments_root", lambda: experiments_root
    )
    monkeypatch.setattr(
        dogfood.experiments, "default_benchmark_root", lambda: benchmark_root
    )

    rc = cli.main(["--repo-path", str(tmp_path)])
    assert rc == 0
    captured = capsys.readouterr().out
    assert "experiment_id:" in captured
    assert "_explainability-stack-dogfood" in captured
    # The record landed in the temp experiments root.
    produced = list(experiments_root.glob("*_explainability-stack-dogfood.json"))
    assert len(produced) == 1


def test_module_has_no_forbidden_imports():
    import ast

    source = (PROJECT_ROOT / "core" / "explainability_dogfood.py").read_text(encoding="utf-8")
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
