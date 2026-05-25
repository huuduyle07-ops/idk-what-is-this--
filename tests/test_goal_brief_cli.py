from __future__ import annotations

import json
from pathlib import Path

from core import goal_brief
from scripts import create_goal_brief as cli


def test_cli_empty_goal_returns_friendly_error(capsys):
    code = cli.main(["--goal", "   ", "--dry-run"])

    captured = capsys.readouterr()
    assert code == 2
    assert "goal must be a non-empty string" in captured.err


def test_cli_dry_run_prints_draft_without_writing(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(goal_brief, "DEFAULT_GOAL_BRIEFS_ROOT", tmp_path)

    code = cli.main(["--goal", "Fix odd logs", "--dry-run"])

    captured = capsys.readouterr()
    assert code == 0
    payload = json.loads(captured.out)
    assert payload["brief"]["goal"] == "Fix odd logs"
    assert list(tmp_path.glob("**/*")) == []


def test_cli_updates_existing_brief_and_exports_markdown(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(goal_brief, "DEFAULT_GOAL_BRIEFS_ROOT", tmp_path)
    created = goal_brief.create_goal_brief(goal="Fix API error", goal_briefs_root=tmp_path)

    code = cli.main(
        [
            "--brief-ref",
            created["brief_path"],
            "--answer",
            json.dumps(
                {
                    "evidence": {"actual_result": "500 from /api/items"},
                    "validation": {"success_criteria": "endpoint returns 200"},
                }
            ),
            "--export-md",
        ]
    )

    captured = capsys.readouterr()
    assert code == 0
    payload = json.loads(captured.out)
    assert payload["brief"]["evidence"]["actual_result"] == "500 from /api/items"
    assert Path(payload["markdown_path"]).is_file()
