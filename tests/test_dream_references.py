"""Phase 4.7e - Dream external research reference import."""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

from core import dream_references, dream_trials


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    return r


def test_creates_reference_json_and_markdown(repo):
    fixed = datetime(2026, 5, 27, 8, 9, 10)
    result = dream_references.create_dream_reference(
        repo_path=str(repo),
        topic="Graph role classification",
        raw_input="Notes claim centrality can identify coordinator nodes.",
        source_type="web_summary",
        sources=[
            {
                "title": "Graph roles paper",
                "url": "https://example.test/paper",
                "source_type": "paper",
                "why_relevant": "Reports role features.",
            }
        ],
        now=fixed,
    )

    ref_dir = Path(result.reference_dir)
    assert ref_dir.is_dir()
    assert ref_dir.name.startswith("20260527-080910-graph-role-classification")
    assert Path(result.json_path).is_file()
    assert Path(result.markdown_path).is_file()
    assert Path(result.markdown_path).parent == ref_dir

    data = json.loads(Path(result.json_path).read_text(encoding="utf-8"))
    assert data["reference_id"] == result.reference_id
    assert data["topic"] == "Graph role classification"
    assert data["source_type"] == "web_summary"
    assert data["usable_as_markdown_file"] is True
    assert data["summary"].startswith("Imported notes claim")
    assert data["sources"][0]["url"] == "https://example.test/paper"
    assert data["sources"][0]["reliability"] == "unknown"

    md = Path(result.markdown_path).read_text(encoding="utf-8")
    assert "# Dream Research Reference" in md
    assert "## Topic" in md
    assert "Graph role classification" in md
    assert "## What C.A.T.T.U.S Should Not Assume" in md
    assert "Notes claim centrality" in md


def test_rejects_empty_topic(repo):
    with pytest.raises(ValueError) as exc:
        dream_references.create_dream_reference(
            repo_path=str(repo),
            topic="   ",
            raw_input="notes",
        )
    assert "topic" in str(exc.value).lower()


def test_rejects_empty_raw_input_when_no_structured_fields_exist(repo):
    with pytest.raises(ValueError) as exc:
        dream_references.create_dream_reference(
            repo_path=str(repo),
            topic="Structured blank",
            raw_input="   ",
            sources=[],
            key_ideas=[],
            risks_or_weaknesses=[],
            do_not_assume=[],
        )
    assert "raw_input" in str(exc.value)


def test_allows_empty_raw_input_when_structured_fields_exist(repo):
    result = dream_references.create_dream_reference(
        repo_path=str(repo),
        topic="Structured notes",
        raw_input="",
        key_ideas=["Notes say role classification may reduce search space."],
    )
    data = json.loads(Path(result.json_path).read_text(encoding="utf-8"))
    assert data["raw_input"] == ""
    assert data["key_ideas"] == [
        "Notes say role classification may reduce search space."
    ]


def test_normalizes_source_entries_with_missing_fields(repo):
    result = dream_references.create_dream_reference(
        repo_path=str(repo),
        topic="Docker sandbox security",
        raw_input="Manual notes report namespace isolation concerns.",
        sources=[{"title": "Container note"}],
    )
    data = json.loads(Path(result.json_path).read_text(encoding="utf-8"))
    source = data["sources"][0]
    assert source == {
        "title": "Container note",
        "url": "",
        "source_type": "unknown",
        "reliability": "unknown",
        "why_relevant": "",
    }


def test_stores_risks_and_do_not_assume_separately(repo):
    result = dream_references.create_dream_reference(
        repo_path=str(repo),
        topic="Paper notes",
        raw_input="Paper notes claim promising but narrow results.",
        risks_or_weaknesses=["Small evaluation set."],
        do_not_assume=["Do not assume this generalizes to C.A.T.T.U.S."],
    )
    data = json.loads(Path(result.json_path).read_text(encoding="utf-8"))
    assert data["risks_or_weaknesses"] == ["Small evaluation set."]
    assert data["do_not_assume"] == [
        "Do not assume this generalizes to C.A.T.T.U.S."
    ]

    md = Path(result.markdown_path).read_text(encoding="utf-8")
    assert "## Risks / Weaknesses" in md
    assert "Small evaluation set." in md
    assert "## What C.A.T.T.U.S Should Not Assume" in md
    assert "Do not assume this generalizes" in md


def test_reference_markdown_can_feed_structured_dream_trial(repo):
    reference = dream_references.create_dream_reference(
        repo_path=str(repo),
        topic="Graph role classification",
        raw_input="Notes claim hub and bridge roles can guide code search.",
        key_ideas=["Imported notes say graph roles are only hypotheses."],
    )

    trial = dream_trials.create_structured_dream_trial(
        repo_path=str(repo),
        dream_type="reference_study",
        action_level="report_only",
        title="Use imported graph role research",
        markdown_files=[reference.markdown_path],
    )

    data = json.loads(Path(trial.trial_path).read_text(encoding="utf-8"))
    details = data["markdown_file_details"]
    assert details[0]["status"] == "loaded"
    evidence = "\n".join(data["reference_study"]["evidence"])
    assert "Graph role classification" in evidence


def test_reference_output_stays_inside_dream_references_root(repo):
    result = dream_references.create_dream_reference(
        repo_path=str(repo),
        topic="../escape attempt",
        raw_input="Notes claim nothing should escape.",
    )
    root = dream_references.references_root(str(repo)).resolve()
    Path(result.reference_dir).resolve().relative_to(root)
    Path(result.json_path).resolve().relative_to(root)
    Path(result.markdown_path).resolve().relative_to(root)


def test_read_reference_file_blocks_path_traversal(repo):
    dream_references.create_dream_reference(
        repo_path=str(repo),
        topic="Traversal anchor",
        raw_input="Notes claim traversal should be blocked.",
    )
    with pytest.raises(ValueError):
        dream_references.read_dream_reference_file(
            repo_path=str(repo),
            reference_id="../outside",
            file_name="reference.md",
        )


def test_core_and_cli_have_no_forbidden_imports():
    root = Path(__file__).resolve().parents[1]
    targets = [
        Path(dream_references.__file__),
        root / "scripts" / "import_dream_reference.py",
    ]
    forbidden = [
        "subprocess",
        "patch_engine",
        "patch_plan_executor",
        "patch_planner",
        "run_patch_plan",
        "run_benchmarks",
        "benchmark_runner",
        "anthropic",
        "openai",
        "google.genai",
        "litellm",
        "requests",
        "httpx",
        "urllib",
        "aiohttp",
        "socket",
    ]
    for target in targets:
        src = target.read_text(encoding="utf-8").lower()
        for needle in forbidden:
            assert needle.lower() not in src, f"{target} leaked {needle}"


def _import_cli():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "import_dream_reference.py"
    if str(script_path.parent.parent) not in sys.path:
        sys.path.insert(0, str(script_path.parent.parent))
    spec = importlib.util.spec_from_file_location("import_dream_reference", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_imports_reference_from_raw(repo, capsys):
    cli = _import_cli()
    exit_code = cli.main([
        "--repo-path", str(repo),
        "--topic", "Graph role classification",
        "--raw", "Pasted notes claim roles can guide search.",
        "--source-type", "zapier_discord",
    ])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "reference_id:" in out
    assert "reference.md:" in out
    assert "reference.json:" in out
    assert "summary:" in out


def test_cli_imports_reference_from_input_file(repo, tmp_path, capsys):
    notes = tmp_path / "notes.md"
    notes.write_text("Manual notes report sandbox hardening ideas.", encoding="utf-8")
    cli = _import_cli()
    exit_code = cli.main([
        "--repo-path", str(repo),
        "--topic", "Docker sandbox security",
        "--input-file", str(notes),
    ])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Docker sandbox security" not in out
    assert "reference.md:" in out

