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


def test_ready_to_apply_revalidation_grades_lesson_without_touching_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    source = repo / "app.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")

    report_dir = tmp_path / "dream-report"
    item = {
        "idx": 1,
        "kind": "bug",
        "title": "Ready patch",
        "status": "ready_to_apply",
        "summary": "Validated in sandbox.",
    }
    item_dir = dream_artifacts.item_dir(report_dir, 1, item["title"])
    item_dir.mkdir(parents=True)
    plan = [
        {
            "op": "replace_snippet",
            "relative_path": "app.py",
            "target_snippet": "VALUE = 1\n",
            "patched_snippet": "VALUE = 2\n",
        }
    ]
    plan_path = item_dir / "patch_plan.json"
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")

    sleeping_consultant._refine_one_pass(str(repo), item, 1, report_dir, 1)

    assert item["status"] == "ready_to_apply"
    assert source.read_text(encoding="utf-8") == "VALUE = 1\n"
    assert json.loads(plan_path.read_text(encoding="utf-8")) == plan
    assert item["refinement_count"] == 1
    assert item["latest_refined_artifact"] == "patch_revalidation_pass1.json"
    assert item["lesson_evaluation"]["promotion"] == "auto_approved"

    artifact = json.loads(
        (item_dir / "patch_revalidation_pass1.json").read_text(encoding="utf-8")
    )
    assert artifact["success"] is True
    assert artifact["changed_files"] == ["app.py"]
    assert artifact["rollback_performed"] is False
    assert "VALUE = 2" in artifact["diff"]
    assert artifact["lesson_evaluation"]["promotion"] == "auto_approved"


def test_ready_to_apply_missing_patch_plan_records_refinement_error(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("VALUE = 1\n", encoding="utf-8")

    report_dir = tmp_path / "dream-report"
    item = {
        "idx": 1,
        "kind": "bug",
        "title": "Missing plan",
        "status": "ready_to_apply",
    }
    item_dir = dream_artifacts.item_dir(report_dir, 1, item["title"])
    item_dir.mkdir(parents=True)

    sleeping_consultant._refine_one_pass(str(repo), item, 1, report_dir, 1)

    assert item["status"] == "ready_to_apply"
    assert item["refinement_count"] == 0
    assert item["refinement_attempt_count"] == 1
    assert item["latest_failed_refinement_artifact"] == "refinement_error_pass1.txt"
    assert "lesson_evaluation" not in item
    history_entry = item["refinement_history"][0]
    assert history_entry["ok"] is False
    assert history_entry["failed_artifact"] == "refinement_error_pass1.txt"
    assert (item_dir / "refinement_error_pass1.txt").exists()


def test_item_done_snapshot_includes_lesson_evaluation():
    item = {
        "idx": 8,
        "kind": "bug",
        "title": "Lesson badge",
        "status": "ready_to_apply",
        "lesson_evaluation": {
            "promotion": "needs_human_review",
            "score": 0.5,
            "reasons": ["diff is too large"],
        },
    }

    with sleeping_consultant._STATE_LOCK:
        sleeping_consultant._RUN_STATE["items_done"] = []

    sleeping_consultant._update_item_done(item)

    snapshot = sleeping_consultant.get_run_state()["items_done"][0]
    assert snapshot["lesson_evaluation"]["promotion"] == "needs_human_review"


def test_patch_if_safe_routes_debt_to_patch_generation(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    report_dir = tmp_path / "dream-report"
    calls = []

    monkeypatch.setattr(
        dream_artifacts,
        "read_queue",
        lambda repo_path: [
            {
                "kind": "debt",
                "title": "Narrow doc patch",
                "hint": "Add one sentence to an existing doc.",
            }
        ],
    )
    # Slice γ.3.1: sleeping_consultant now calls new_run_dir() (which creates
    # a timestamped subdir). For tests we want a deterministic path — patch
    # new_run_dir to return our pre-built report_dir and ensure it exists.
    # Also patch today_dir to keep backward-compat with any tests / call sites
    # that still expect the date-only path.
    def _fake_new_run_dir(repo_path):
        report_dir.mkdir(parents=True, exist_ok=True)
        return report_dir
    monkeypatch.setattr(dream_artifacts, "new_run_dir", _fake_new_run_dir)
    monkeypatch.setattr(dream_artifacts, "today_dir", lambda repo_path: report_dir)

    def fake_patch_if_safe_item(repo_path, item, idx, retry_per_item, item_dir_path):
        calls.append((item["kind"], item_dir_path.name))
        item_dir_path.mkdir(parents=True, exist_ok=True)
        return {
            **item,
            "idx": idx,
            "status": "ready_to_apply",
            "summary": "Debt patch generated.",
            "item_dir_name": item_dir_path.name,
        }

    monkeypatch.setattr(
        sleeping_consultant,
        "_run_patch_if_safe_item",
        fake_patch_if_safe_item,
    )
    monkeypatch.setattr(
        sleeping_consultant,
        "_run_plan_only_item",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("debt should not stay plan-only in patch_if_safe")
        ),
    )

    with sleeping_consultant._STATE_LOCK:
        sleeping_consultant._RUN_STATE["items_done"] = []
        sleeping_consultant._RUN_STATE["stop_requested"] = False

    result = sleeping_consultant.run_overnight(
        str(repo),
        dream_mode="patch_if_safe",
        max_refine_rounds=0,
    )

    assert calls == [("debt", "01-narrow-doc-patch")]
    assert result["items"][0]["status"] == "ready_to_apply"
    saved = json.loads((report_dir / "list.json").read_text(encoding="utf-8"))
    assert saved["items"][0]["status"] == "ready_to_apply"


def test_dream_patch_generation_hydrates_markdown_source_from_scout(
    tmp_path,
    monkeypatch,
):
    repo = tmp_path / "repo"
    repo.mkdir()
    note = repo / "NOTE.md"
    note.write_text(
        "# Gamma2 Smoke Note\n\nStatus: TODO_GAMMA2_NOTE\n",
        encoding="utf-8",
    )
    control = {
        "patch_intent": {},
        "top_hypothesis": {},
        "related_snippets": [],
    }

    monkeypatch.setattr(
        sleeping_consultant,
        "run_control_structured",
        lambda query, repo_path: control,
    )

    def fake_scout(query, repo_path, control_result, force=False):
        control_result["scout"] = {
            "likely_files": ["NOTE.md"],
            "likely_symbols": [],
            "target_concepts": ["gamma2 smoke note"],
        }
        return control_result

    monkeypatch.setattr(sleeping_consultant, "maybe_enrich_with_scout", fake_scout)
    monkeypatch.setattr(
        sleeping_consultant,
        "inspect_repo_inventory",
        lambda repo_path: {"primary_language": "unknown"},
    )
    monkeypatch.setattr(
        sleeping_consultant,
        "run_gemini_request_2",
        lambda prompt, repo_path: json.dumps({"patch_plan": [{"op": "noop"}]}),
    )

    patch, _raw = sleeping_consultant._generate_patch_plan(
        str(repo),
        {
            "kind": "debt",
            "title": "Gamma2 markdown patch",
            "hint": "Patch exactly NOTE.md.",
        },
    )

    assert patch == {"patch_plan": [{"op": "noop"}]}
    assert control["patch_intent"]["target_file"] == "NOTE.md"
    assert "Status: TODO_GAMMA2_NOTE" in control["patch_intent"]["source_snippet"]


# ----------------------------------------------------------------------
# Slice γ3.2: preferred / promoted refined artifact
# ----------------------------------------------------------------------

import os
import pytest


def _build_promotable_run(tmp_path, *, raw_list=False, item_dir_name="01-needs-better-plan",
                          extra_files=None, item_overrides=None):
    """Build a fake .agent/dreams/<date>/<run>/ layout with one item and the
    originals + one refined artifact in each family. Returns the helpers the
    promotion tests need: (repo_path, dreams_root, date, run_id, report_dir,
    item_dir).

    Tests monkey-patch `dream_artifacts.dreams_root` to point at our fake root
    so promote_artifact resolves to it.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    dreams = tmp_path / "dreams"
    date = "2026-05-16"
    run_id = "010203-run"
    report_dir = dreams / date / run_id
    item_dir_path = report_dir / item_dir_name
    item_dir_path.mkdir(parents=True)

    # Originals (never touched by promotion).
    (item_dir_path / "plan_analysis.json").write_text(
        json.dumps({"problem_summary": "original"}), encoding="utf-8"
    )
    (item_dir_path / "proposal.md").write_text("# original proposal\n", encoding="utf-8")
    # Refined artifacts (promotable).
    (item_dir_path / "plan_analysis.refined_pass1.json").write_text(
        json.dumps({"problem_summary": "refined v1"}), encoding="utf-8"
    )
    (item_dir_path / "plan_analysis.refined_pass2.json").write_text(
        json.dumps({"problem_summary": "refined v2"}), encoding="utf-8"
    )
    (item_dir_path / "proposal.refined_pass1.md").write_text(
        "# refined proposal v1\n", encoding="utf-8"
    )
    for name, content in (extra_files or {}).items():
        (item_dir_path / name).write_text(content, encoding="utf-8")

    item = {
        "idx": 1,
        "kind": "bug",
        "title": "Needs better plan",
        "status": "planned_no_patch",
        "item_dir_name": item_dir_name,
        "latest_refined_artifact": "plan_analysis.refined_pass2.json",
        "refinement_count": 2,
    }
    if item_overrides:
        item.update(item_overrides)

    list_path = report_dir / "list.json"
    payload = [item] if raw_list else {
        "items": [item],
        "patch_style": "balanced",
        "dream_mode": "plan_only",
        "completed_at": "2026-05-16T01:02:03",
    }
    list_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    return repo, dreams, date, run_id, report_dir, item_dir_path


def test_promote_refined_plan_writes_preferred_metadata(tmp_path, monkeypatch):
    repo, dreams, date, run_id, report_dir, item_dir_path = _build_promotable_run(tmp_path)
    monkeypatch.setattr(dream_artifacts, "dreams_root", lambda repo_path: dreams)

    original_plan = item_dir_path / "plan_analysis.json"
    before_stat = original_plan.stat()

    out = dream_artifacts.promote_artifact(
        str(repo), date, run_id, 1, "plan_analysis.refined_pass2.json"
    )

    assert out == {
        "ok": True,
        "preferred_artifact": "plan_analysis.refined_pass2.json",
        "preferred_artifact_kind": "plan",
        "item_idx": 1,
    }
    saved = json.loads((report_dir / "list.json").read_text(encoding="utf-8"))
    assert saved["items"][0]["preferred_artifact"] == "plan_analysis.refined_pass2.json"
    assert saved["items"][0]["preferred_artifact_kind"] == "plan"

    after_stat = original_plan.stat()
    assert (before_stat.st_size, before_stat.st_mtime_ns) == (
        after_stat.st_size,
        after_stat.st_mtime_ns,
    )


def test_promote_refined_proposal_writes_kind_proposal(tmp_path, monkeypatch):
    repo, dreams, date, run_id, report_dir, _ = _build_promotable_run(tmp_path)
    monkeypatch.setattr(dream_artifacts, "dreams_root", lambda repo_path: dreams)

    out = dream_artifacts.promote_artifact(
        str(repo), date, run_id, 1, "proposal.refined_pass1.md"
    )

    assert out["preferred_artifact_kind"] == "proposal"
    saved = json.loads((report_dir / "list.json").read_text(encoding="utf-8"))
    assert saved["items"][0]["preferred_artifact"] == "proposal.refined_pass1.md"
    assert saved["items"][0]["preferred_artifact_kind"] == "proposal"


def test_promote_rejects_non_refined_filename(tmp_path, monkeypatch):
    repo, dreams, date, run_id, _, _ = _build_promotable_run(tmp_path)
    monkeypatch.setattr(dream_artifacts, "dreams_root", lambda repo_path: dreams)

    with pytest.raises(ValueError, match="invalid refined artifact filename"):
        dream_artifacts.promote_artifact(
            str(repo), date, run_id, 1, "plan_analysis.json"
        )


def test_promote_rejects_missing_artifact_file(tmp_path, monkeypatch):
    repo, dreams, date, run_id, _, item_dir_path = _build_promotable_run(tmp_path)
    monkeypatch.setattr(dream_artifacts, "dreams_root", lambda repo_path: dreams)
    # Remove the refined file so the regex passes but disk doesn't have it.
    (item_dir_path / "proposal.refined_pass1.md").unlink()

    with pytest.raises(FileNotFoundError):
        dream_artifacts.promote_artifact(
            str(repo), date, run_id, 1, "proposal.refined_pass1.md"
        )


def test_promote_rejects_path_traversal(tmp_path, monkeypatch):
    repo, dreams, date, run_id, _, _ = _build_promotable_run(tmp_path)
    monkeypatch.setattr(dream_artifacts, "dreams_root", lambda repo_path: dreams)

    with pytest.raises(ValueError, match="invalid refined artifact filename"):
        dream_artifacts.promote_artifact(
            str(repo), date, run_id, 1, "../../etc/passwd"
        )


def test_promote_route_rejects_legacy_layout(tmp_path, monkeypatch):
    # Build a valid timestamped layout but POST with run="" to hit the
    # route-level legacy rejection (helpers can't return that specific message
    # because helpers don't know it's a legacy case).
    repo, dreams, date, _, _, _ = _build_promotable_run(tmp_path)
    monkeypatch.setattr(dream_artifacts, "dreams_root", lambda repo_path: dreams)

    from web.app import app

    client = app.test_client()
    resp = client.post(
        "/dream/promote-artifact",
        data={
            "repo_path": str(repo),
            "date": date,
            "run": "",
            "item_idx": "1",
            "artifact": "plan_analysis.refined_pass1.json",
        },
    )
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["ok"] is False
    assert "Promotion only supported for timestamped run directories" in body["error"]


def test_promote_is_idempotent_and_originals_untouched(tmp_path, monkeypatch):
    repo, dreams, date, run_id, report_dir, item_dir_path = _build_promotable_run(tmp_path)
    monkeypatch.setattr(dream_artifacts, "dreams_root", lambda repo_path: dreams)

    plan = item_dir_path / "plan_analysis.json"
    proposal = item_dir_path / "proposal.md"
    before = (plan.stat().st_size, plan.stat().st_mtime_ns,
              proposal.stat().st_size, proposal.stat().st_mtime_ns)

    out1 = dream_artifacts.promote_artifact(
        str(repo), date, run_id, 1, "plan_analysis.refined_pass2.json"
    )
    out2 = dream_artifacts.promote_artifact(
        str(repo), date, run_id, 1, "plan_analysis.refined_pass2.json"
    )

    assert out1["ok"] is True and out2["ok"] is True
    after = (plan.stat().st_size, plan.stat().st_mtime_ns,
             proposal.stat().st_size, proposal.stat().st_mtime_ns)
    assert before == after
    assert not (report_dir / "list.json.tmp").exists()


def test_promote_accepts_raw_list_json_shape(tmp_path, monkeypatch):
    repo, dreams, date, run_id, report_dir, _ = _build_promotable_run(
        tmp_path, raw_list=True
    )
    monkeypatch.setattr(dream_artifacts, "dreams_root", lambda repo_path: dreams)

    # Pre-condition: list.json was written as a raw list.
    pre = json.loads((report_dir / "list.json").read_text(encoding="utf-8"))
    assert isinstance(pre, list)

    out = dream_artifacts.promote_artifact(
        str(repo), date, run_id, 1, "plan_analysis.refined_pass1.json"
    )

    assert out["preferred_artifact"] == "plan_analysis.refined_pass1.json"
    post = json.loads((report_dir / "list.json").read_text(encoding="utf-8"))
    # Tolerant load + uniform write → file is now a dict with "items".
    assert isinstance(post, dict)
    assert post["items"][0]["preferred_artifact"] == "plan_analysis.refined_pass1.json"
    assert post["items"][0]["preferred_artifact_kind"] == "plan"


def test_promote_rejects_item_dir_name_traversal(tmp_path, monkeypatch):
    # Same fake run, but the list.json item points item_dir_name at an
    # escape path. promote_artifact must reject before reading anything
    # outside the report dir.
    repo, dreams, date, run_id, report_dir, _ = _build_promotable_run(
        tmp_path, item_overrides={"item_dir_name": "../../escape"}
    )
    # Put a sentinel file at the escape target so we can detect if it was read.
    sentinel_dir = tmp_path / "escape"
    sentinel_dir.mkdir(exist_ok=True)
    sentinel = sentinel_dir / "plan_analysis.refined_pass1.json"
    sentinel.write_text("if this was read the guard failed", encoding="utf-8")
    monkeypatch.setattr(dream_artifacts, "dreams_root", lambda repo_path: dreams)

    with pytest.raises(ValueError, match="item_dir_name path escapes report dir"):
        dream_artifacts.promote_artifact(
            str(repo), date, run_id, 1, "plan_analysis.refined_pass1.json"
        )
