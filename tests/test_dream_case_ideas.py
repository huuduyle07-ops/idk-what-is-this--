from __future__ import annotations

import json
import sys
from pathlib import Path

from core import dream_artifacts, sleeping_consultant


def _fixed_report_dir(tmp_path: Path, monkeypatch) -> Path:
    report_dir = tmp_path / ".agent" / "dreams" / "2026-05-25" / "120000-run"
    report_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(dream_artifacts, "new_run_dir", lambda repo_path: report_dir)
    return report_dir


def test_reference_study_creates_case_idea_artifacts_from_notes(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    report_dir = _fixed_report_dir(tmp_path, monkeypatch)
    prompts: list[str] = []

    monkeypatch.setattr(
        dream_artifacts,
        "read_queue",
        lambda repo_path: [
            {
                "kind": "reference_study",
                "title": "Gastown failure modes",
                "notes": "Agents often patch the caller while the invariant lives in the callee.",
            }
        ],
    )

    def fake_model(prompt: str, repo_path: str | None = None) -> str:
        prompts.append(prompt)
        return json.dumps(
            {
                "case_ideas": [
                    {
                        "pattern": "Wrong-file patch temptation",
                        "why_it_matters": "The agent must repair the source of truth.",
                        "suggested_case_name": "python_wrong_file_callee_invariant",
                        "language": "python",
                        "category": "wrong_file",
                        "difficulty": "medium",
                        "minimal_experiment": "Create caller and callee files; only callee fix passes.",
                        "expected_wrong_agent_behavior": "Patch the caller assertion instead.",
                        "human_approved_for_case_creation": True,
                    }
                ],
                "lesson_notes": ["Look for invariant ownership before patching."],
            }
        )

    monkeypatch.setattr(sleeping_consultant, "run_gemini_request_2", fake_model)
    monkeypatch.setattr(
        sleeping_consultant,
        "run_patch_plan_with_artifacts",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("patch executor must not be called")
        ),
    )

    result = sleeping_consultant.run_overnight(
        str(repo),
        dream_mode="case_idea_research",
        max_refine_rounds=0,
    )

    assert len(prompts) == 1
    assert "Dream reference study case-idea mode" in prompts[0]
    assert result["items"][0]["status"] == "case_ideas_created"

    payload = json.loads((report_dir / "case_ideas.json").read_text(encoding="utf-8"))
    ideas = payload["case_ideas"]
    assert len(ideas) == 1
    assert ideas[0]["pattern"] == "Wrong-file patch temptation"
    assert ideas[0]["human_approved_for_case_creation"] is False
    assert ideas[0]["source_item_idx"] == 1
    assert (report_dir / "case_ideas.md").exists()
    assert "python_wrong_file_callee_invariant" in (
        report_dir / "case_ideas.md"
    ).read_text(encoding="utf-8")
    assert "Look for invariant ownership" in (
        report_dir / "LESSONS_LEARNED.md"
    ).read_text(encoding="utf-8")
    assert not (repo / "benchmarks" / "cases").exists()


def test_empty_reference_notes_create_friendly_no_idea_output(
    tmp_path,
    monkeypatch,
):
    repo = tmp_path / "repo"
    repo.mkdir()
    report_dir = _fixed_report_dir(tmp_path, monkeypatch)

    monkeypatch.setattr(
        dream_artifacts,
        "read_queue",
        lambda repo_path: [{"kind": "reference_study", "title": "Empty notes"}],
    )
    monkeypatch.setattr(
        sleeping_consultant,
        "run_gemini_request_2",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("model must not be called without notes")
        ),
    )

    result = sleeping_consultant.run_overnight(
        str(repo),
        dream_mode="case_idea_research",
        max_refine_rounds=0,
    )

    assert result["items"][0]["status"] == "case_idea_no_input"
    payload = json.loads((report_dir / "case_ideas.json").read_text(encoding="utf-8"))
    assert payload["case_ideas"] == []
    assert "No reference notes were provided" in payload["message"]
    assert "No case ideas" in (report_dir / "case_ideas.md").read_text(
        encoding="utf-8"
    )


def test_reference_markdown_file_content_is_used(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    docs = repo / "docs"
    docs.mkdir()
    (docs / "reference.md").write_text(
        "# Reference\n\nAsync retry races leave stale cache entries.",
        encoding="utf-8",
    )
    _fixed_report_dir(tmp_path, monkeypatch)
    prompts: list[str] = []

    monkeypatch.setattr(
        dream_artifacts,
        "read_queue",
        lambda repo_path: [
            {
                "kind": "reference_study",
                "title": "Retry notes",
                "reference_files": ["docs/reference.md"],
            }
        ],
    )
    monkeypatch.setattr(
        sleeping_consultant,
        "run_gemini_request_2",
        lambda prompt, repo_path=None: prompts.append(prompt)
        or json.dumps({"case_ideas": []}),
    )

    sleeping_consultant.run_overnight(
        str(repo),
        dream_mode="case_idea_research",
        max_refine_rounds=0,
    )

    assert "Async retry races leave stale cache entries" in prompts[0]


def test_case_idea_report_markdown_renders_table(tmp_path):
    report_dir = tmp_path / "dream-report"
    report_dir.mkdir()
    ideas = [
        {
            "pattern": "Boundary check drift",
            "why_it_matters": "Common off-by-one bug.",
            "suggested_case_name": "cpp_boundary_drift",
            "language": "cpp",
            "category": "bounds",
            "difficulty": "easy",
            "minimal_experiment": "One vector access at size boundary.",
            "expected_wrong_agent_behavior": "Change the test fixture.",
            "human_approved_for_case_creation": False,
        }
    ]

    path = dream_artifacts.write_report_markdown(
        report_dir,
        [{"idx": 1, "kind": "reference_study", "title": "Bounds", "status": "case_ideas_created"}],
        dream_mode="case_idea_research",
        case_ideas=ideas,
    )

    text = path.read_text(encoding="utf-8")
    assert "## Case idea candidates" in text
    assert "| Pattern | Suggested case | Language | Category | Difficulty | Approved? |" in text
    assert "cpp_boundary_drift" in text
    assert "| no |" in text


def test_dream_report_exposes_case_ideas_for_ui(tmp_path):
    report_dir = tmp_path / "dream-report"
    report_dir.mkdir()
    (report_dir / "list.json").write_text(
        json.dumps({"items": [], "dream_mode": "case_idea_research"}),
        encoding="utf-8",
    )
    (report_dir / "case_ideas.json").write_text(
        json.dumps(
            {
                "case_ideas": [
                    {
                        "pattern": "Wrong abstraction boundary",
                        "suggested_case_name": "ts_wrong_boundary",
                        "human_approved_for_case_creation": False,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    report = dream_artifacts.read_report(report_dir)

    assert report["case_ideas"][0]["suggested_case_name"] == "ts_wrong_boundary"


def test_dream_tab_contains_case_idea_candidates_ui():
    html = Path("web/templates/index.html").read_text(encoding="utf-8")

    assert "Case idea candidates" in html
    assert "_renderCaseIdeaCandidates" in html


def test_case_idea_mode_does_not_import_benchmark_runner(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _fixed_report_dir(tmp_path, monkeypatch)
    sys.modules.pop("benchmarks.run_benchmarks", None)
    monkeypatch.setattr(
        dream_artifacts,
        "read_queue",
        lambda repo_path: [
            {
                "kind": "reference_study",
                "title": "Simple notes",
                "notes": "Null guard patterns make good benchmark ideas.",
            }
        ],
    )
    monkeypatch.setattr(
        sleeping_consultant,
        "run_gemini_request_2",
        lambda prompt, repo_path=None: json.dumps({"case_ideas": []}),
    )

    sleeping_consultant.run_overnight(
        str(repo),
        dream_mode="case_idea_research",
        max_refine_rounds=0,
    )

    assert "benchmarks.run_benchmarks" not in sys.modules
