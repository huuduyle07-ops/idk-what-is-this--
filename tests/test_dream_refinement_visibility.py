import json

from core import dream_artifacts, sleeping_consultant


def test_failed_refinement_attempt_is_visible_metadata(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    report_dir = tmp_path / "dream-report"
    item = {
        "idx": 1,
        "kind": "bug",
        "title": "Needs better plan",
        "hint": "tighten edge cases",
        "status": "planned_no_patch",
    }
    item_dir = dream_artifacts.item_dir(report_dir, 1, item["title"])
    item_dir.mkdir(parents=True)
    original_plan = item_dir / "plan_analysis.json"
    original_plan.write_text(
        json.dumps({"problem_summary": "original plan"}),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sleeping_consultant,
        "run_gemini_request_2",
        lambda prompt, repo_path: "not json, so this becomes refinement_raw",
    )

    sleeping_consultant._refine_one_pass(str(repo), item, 1, report_dir, 1)

    assert item["refinement_count"] == 0
    assert item["refinement_attempt_count"] == 1
    assert item["latest_failed_refinement_artifact"] == "refinement_raw_pass1.txt"
    assert "not json" in item["latest_refinement_error_summary"]
    history_entry = item["refinement_history"][0]
    assert history_entry["pass"] == 1
    assert history_entry["before_summary"] == '{"problem_summary": "original plan"}'
    assert history_entry["after_summary"] == "not json, so this becomes refinement_raw"
    assert history_entry["artifact"] is None
    assert history_entry["ok"] is False
    assert history_entry["failed_artifact"] == "refinement_raw_pass1.txt"
    assert (item_dir / "refinement_raw_pass1.txt").exists()
    assert original_plan.read_text(encoding="utf-8") == json.dumps(
        {"problem_summary": "original plan"}
    )


def test_item_done_snapshot_includes_refinement_failure_metadata():
    item = {
        "idx": 7,
        "kind": "bug",
        "title": "Visible failure",
        "status": "planned_no_patch",
        "refinement_count": 0,
        "refinement_attempt_count": 1,
        "latest_failed_refinement_artifact": "refinement_raw_pass1.txt",
        "latest_refinement_error_summary": "not json",
        "refinement_history": [
            {
                "pass": 1,
                "ok": False,
                "failed_artifact": "refinement_raw_pass1.txt",
                "after_summary": "not json",
            }
        ],
    }

    with sleeping_consultant._STATE_LOCK:
        sleeping_consultant._RUN_STATE["items_done"] = []

    sleeping_consultant._update_item_done(item)

    snapshot = sleeping_consultant.get_run_state()["items_done"][0]
    assert snapshot["refinement_attempt_count"] == 1
    assert snapshot["refinement_history"][0]["ok"] is False
    assert snapshot["latest_failed_refinement_artifact"] == "refinement_raw_pass1.txt"
