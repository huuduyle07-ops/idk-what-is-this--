"""Phase 6.4a tests: scripts/create_lesson_from_proposal.py."""
import json
from pathlib import Path

import pytest

from core import lesson_store
from scripts import create_lesson_from_proposal as cl


# --- helpers --------------------------------------------------------------


def _write_artifacts(
    item_dir: Path,
    *,
    validation_ok: bool = True,
    apply_success: bool = True,
    changed_files=None,
    forbidden_files=None,
    expected_files=None,
    case_name: str = "python_discount_validation",
    language: str = "python",
    category: str = "logic_validation",
    summary: str = "Fix the discount validation logic for edge cases.",
    omit: tuple[str, ...] = (),
) -> None:
    """Write a full set of proposal artifacts to `item_dir`."""
    item_dir.mkdir(parents=True, exist_ok=True)
    changed_files = list(changed_files or ["pricing.py"])
    forbidden_files = list(forbidden_files or ["main.py"])
    expected_files = list(expected_files or ["pricing.py"])

    files = {
        "item.json": {
            "kind": "slow_passing_case",
            "case_name": case_name,
            "language": language,
            "category": category,
            "difficulty": "easy",
        },
        "case.json": {
            "name": case_name,
            "language": language,
            "category": category,
            "validation_command": "python main.py",
            "expected_changed_files": expected_files,
            "forbidden_changed_files": forbidden_files,
        },
        "patch_proposal.json": {
            "summary": summary,
            "patch_candidate": None,
            "patch_plan": [
                {
                    "op": "replace_snippet",
                    "relative_path": f,
                    "target_snippet": "x",
                    "patched_snippet": "y",
                }
                for f in changed_files
            ],
            "needs_human_review": False,
        },
        "apply_result.json": {
            "success": apply_success,
            "applied_ops": [
                {
                    "op": "replace_snippet",
                    "relative_path": f,
                    "target_snippet": "x",
                    "patched_snippet": "y",
                }
                for f in changed_files
            ],
            "diffs": [
                f"--- a/{f}\n+++ b/{f}\n@@ -1,1 +1,2 @@\n-old\n+new1\n+new2\n"
                for f in changed_files
            ],
            "rollback_performed": False,
            "failed_op_index": None,
            "failed_op": None,
            "error": None,
        },
        "validation.json": {
            "ok": validation_ok,
            "validation_ok": validation_ok,
            "command": "python main.py",
            "duration_sec": 1.2,
            "output": "OK" if validation_ok else "AssertionError: failed",
        },
    }
    for name, data in files.items():
        if name in omit:
            continue
        (item_dir / name).write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


@pytest.fixture
def proposals_repo(tmp_path, monkeypatch):
    """Set up tmp .agent/proposals/<run>/<item>/ and redirect storage."""
    monkeypatch.setattr(
        lesson_store,
        "get_agent_dir",
        lambda repo_path=None: tmp_path / ".agent",
    )
    monkeypatch.setattr(lesson_store.config, "LESSON_AUTO_ACTIVE", False)

    proposals_root = tmp_path / ".agent" / "proposals"
    proposals_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(cl, "_default_proposals_root", lambda: proposals_root)

    return tmp_path


def _item_dir(repo: Path, run: str = "20260517_120000", item: str = "01-test") -> Path:
    return repo / ".agent" / "proposals" / run / item


# --- success path ---------------------------------------------------------


def test_validated_proposal_creates_lesson_candidate(proposals_repo):
    item_dir = _item_dir(proposals_repo)
    _write_artifacts(item_dir)

    lesson = cl.create_lesson_from_proposal(item_dir)

    # Auto_approved evaluation (no forbidden, validation ok, small diff) →
    # candidate bucket with active_knowledge_allowed=False (LESSON_AUTO_ACTIVE
    # defaults False, so it stays in candidate per the 6.0 invariant).
    assert lesson["status"] == "candidate"
    assert lesson["active_knowledge_allowed"] is False
    assert lesson["evaluation"]["promotion"] == "auto_approved"
    assert lesson["source"] == "patch_proposal"
    assert lesson["case_name"] == "python_discount_validation"
    assert lesson["title"].startswith("Patch proposal:")
    assert "discount validation" in lesson["summary"].lower()

    candidate = lesson["candidate"]
    assert candidate["validation_ok"] is True
    assert candidate["rollback_happened"] is False
    assert candidate["changed_files"] == ["pricing.py"]
    assert candidate["touched_forbidden_files"] == []
    assert candidate["missing_expected_files"] == []
    assert candidate["patch_kind"] == "patch_plan"
    assert candidate["language"] == "python"
    assert candidate["category"] == "logic_validation"
    assert candidate["diff_stats"]["added"] == 2
    assert candidate["diff_stats"]["removed"] == 1


# --- failure-mode refusal -------------------------------------------------


def test_failed_validation_refuses_by_default(proposals_repo):
    item_dir = _item_dir(proposals_repo)
    _write_artifacts(item_dir, validation_ok=False)

    with pytest.raises(RuntimeError, match="refusing"):
        cl.create_lesson_from_proposal(item_dir)


def test_failed_apply_refuses_by_default(proposals_repo):
    item_dir = _item_dir(proposals_repo)
    _write_artifacts(item_dir, apply_success=False)

    with pytest.raises(RuntimeError, match="refusing"):
        cl.create_lesson_from_proposal(item_dir)


def test_allow_failed_creates_blocked_lesson(proposals_repo):
    item_dir = _item_dir(proposals_repo)
    _write_artifacts(item_dir, validation_ok=False)

    lesson = cl.create_lesson_from_proposal(item_dir, allow_failed=True)

    # validation_ok=False → lesson_quality blocks promotion.
    assert lesson["status"] == "blocked"
    assert lesson["active_knowledge_allowed"] is False
    assert lesson["evaluation"]["promotion"] == "blocked"
    assert lesson["candidate"]["validation_ok"] is False


def test_forbidden_file_touch_yields_blocked_lesson(proposals_repo):
    item_dir = _item_dir(proposals_repo)
    _write_artifacts(
        item_dir,
        changed_files=["pricing.py", "main.py"],
        forbidden_files=["main.py"],
    )

    lesson = cl.create_lesson_from_proposal(item_dir)

    assert lesson["candidate"]["touched_forbidden_files"] == ["main.py"]
    assert lesson["status"] == "blocked"
    assert lesson["evaluation"]["promotion"] == "blocked"


# --- missing files --------------------------------------------------------


def test_missing_required_file_returns_friendly_error(proposals_repo):
    item_dir = _item_dir(proposals_repo)
    _write_artifacts(item_dir, omit=("validation.json",))

    with pytest.raises(FileNotFoundError, match="validation.json"):
        cl.create_lesson_from_proposal(item_dir)


def test_missing_multiple_required_files_lists_all(proposals_repo):
    item_dir = _item_dir(proposals_repo)
    _write_artifacts(item_dir, omit=("validation.json", "apply_result.json"))

    with pytest.raises(FileNotFoundError) as exc_info:
        cl.create_lesson_from_proposal(item_dir)
    msg = str(exc_info.value)
    assert "validation.json" in msg
    assert "apply_result.json" in msg


# --- path traversal -------------------------------------------------------


def test_path_traversal_rejected(proposals_repo):
    proposals_root = proposals_repo / ".agent" / "proposals"

    for bad in (
        "",
        "   ",
        "../../etc/passwd",
        str(proposals_repo / "outside" / "evil"),
        str(proposals_root.parent / "not_proposals" / "x"),
    ):
        with pytest.raises(ValueError):
            cl._resolve_proposal_dir(bad)


def test_resolve_proposal_dir_accepts_real_proposal(proposals_repo):
    item_dir = _item_dir(proposals_repo)
    _write_artifacts(item_dir)

    resolved = cl._resolve_proposal_dir(str(item_dir))
    assert resolved == item_dir.resolve()


def test_resolve_proposal_dir_rejects_nonexistent_inside_root(proposals_repo):
    proposals_root = proposals_repo / ".agent" / "proposals"
    bogus = proposals_root / "ghost_run" / "ghost_item"

    with pytest.raises(ValueError, match="does not exist"):
        cl._resolve_proposal_dir(str(bogus))


# --- CLI entry point ------------------------------------------------------


def test_cli_main_exit_code_success(proposals_repo, capsys):
    item_dir = _item_dir(proposals_repo)
    _write_artifacts(item_dir)

    exit_code = cl._main(["--proposal-dir", str(item_dir)])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "saved lesson:" in out
    assert "status=candidate" in out


def test_cli_main_exit_code_refused(proposals_repo, capsys):
    item_dir = _item_dir(proposals_repo)
    _write_artifacts(item_dir, validation_ok=False)

    exit_code = cl._main(["--proposal-dir", str(item_dir)])

    assert exit_code == 3
    err = capsys.readouterr().err
    assert "refused" in err


def test_cli_main_exit_code_missing_file(proposals_repo, capsys):
    item_dir = _item_dir(proposals_repo)
    _write_artifacts(item_dir, omit=("case.json",))

    exit_code = cl._main(["--proposal-dir", str(item_dir)])

    assert exit_code == 1
    err = capsys.readouterr().err
    assert "case.json" in err


def test_cli_main_exit_code_path_traversal(proposals_repo, capsys):
    exit_code = cl._main(["--proposal-dir", "../../../etc/passwd"])

    assert exit_code == 2
    err = capsys.readouterr().err
    assert "must live inside" in err or "does not exist" in err
