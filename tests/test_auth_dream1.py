"""AUTH-01: real request/executor and Chromium regressions with frozen artifacts."""
from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path
import socket
import subprocess
from urllib.parse import urlsplit
from unittest.mock import Mock

import pytest

from core import dream_artifacts
from core import dream_review_binding as review
from tests.test_harness_blackbox_http import harness

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("AUTH.DREAM.1 forbids network")
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket, "create_connection", deny)


def make_run(harness, run="120000-run", target="reviewed.txt", *, kind="bug", status="ready_to_apply", plan=None):
    path = dream_artifacts.dreams_root(str(harness.repo)) / "2026-09-11"
    if run:
        path /= run
    item_dir = path / "1-item"
    item_dir.mkdir(parents=True)
    item = {"idx": 1, "title": target, "kind": kind, "status": status, "item_dir_name": item_dir.name}
    (path / "list.json").write_text(json.dumps({"items": [item]}), encoding="utf-8")
    (path / "dream_run_summary.md").write_text("# Review this candidate\n", encoding="utf-8")
    plan = plan if plan is not None else [{"op": "create_file", "relative_path": target, "content": target + "\r\n"}]
    (item_dir / "patch_plan.json").write_text(json.dumps(plan), encoding="utf-8")
    return path


def offered(harness, *, run=None):
    params = {"repo_path": str(harness.repo)}
    if run is not None:
        params.update(date="2026-09-11", run=run)
    response = harness.client.get("/dream/report" if run is not None else "/dream/list",
                                  query_string=params, headers=harness.headers)
    assert response.status_code == 200
    return response.get_json()


def binding(harness, **kwargs):
    return offered(harness, **kwargs)["items"][0]["review_binding"]


def apply(harness, bindings, *, repo=None, selection="1", **fields):
    data = {"repo_path": str(repo or harness.repo), "selection": selection, **fields}
    if bindings is not None:
        data["review_bindings"] = json.dumps(bindings)
    response = harness.client.post("/dream/apply", headers=harness.headers, data=data)
    assert response.status_code == 200 and response.is_json
    assert harness.calls == []
    return response.get_json()


def tree(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() if p.is_file() else None for p in root.rglob("*")}


def assert_refusal(result, code):
    assert result["code"] == code and result["status"] == code
    assert result["success"] is False and result["review_required"] is True
    assert result["execution_attempted"] is False
    assert result["execution_authorized"] is False
    assert result["patch_applied"] is False
    assert result["mutation_observed"] is False
    assert "dream_review_receipt" not in result


def forbid_execution(monkeypatch):
    from web import app as wa
    spy = Mock(side_effect=AssertionError("crossed binding gate"))
    monkeypatch.setattr(wa, "run_patch_plan_with_artifacts", spy)
    return spy


def test_exact_audit_pre_latest_selection_executes_unreviewed_b(harness, monkeypatch):
    from tests._auth_dream1_maintenance import before_auth_dream1
    from web import app as wa
    source = before_auth_dream1("web/app.py")
    route = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == "dream_apply_route")
    route.decorator_list = []
    namespace = dict(wa.__dict__)
    exec(compile(ast.Module(body=[route], type_ignores=[]), "_auth01_entry_route", "exec"), namespace)
    monkeypatch.setitem(wa.app.view_functions, "dream_apply_route", namespace["dream_apply_route"])
    make_run(harness)
    reviewed = offered(harness)
    make_run(harness, "120001-run", "unreviewed.txt")
    result = apply(harness, None)["results"][0]
    assert reviewed["items"][0]["title"] == "reviewed.txt"
    assert result["title"] == "unreviewed.txt" and result["status"] == "applied"
    assert (harness.repo / "unreviewed.txt").read_bytes() == b"unreviewed.txt\r\n"
    assert not (harness.repo / "reviewed.txt").exists()


def test_exact_audit_post_executes_a_and_receipt_proves_equality(harness, monkeypatch):
    make_run(harness)
    a = binding(harness)
    make_run(harness, "120001-run", "unreviewed.txt")
    b = binding(harness)
    assert a["item_idx"] == b["item_idx"] == 1
    assert a["candidate_fingerprint"] != b["candidate_fingerprint"]
    assert a["run_key"] != b["run_key"]
    # No authoritative Apply code may even consult latest.
    monkeypatch.setattr(dream_artifacts, "latest_report_dir", Mock(side_effect=AssertionError("latest authority")))
    result = apply(harness, [a])["results"][0]
    assert result["status"] == "applied" and result["title"] == "reviewed.txt"
    assert result["execution_attempted"] and result["mutation_observed"]
    receipt = result["dream_review_receipt"]
    assert receipt["identity_verified"] and receipt["reviewed"] == receipt["resolved"] == receipt["executed"] == a
    assert (harness.repo / "reviewed.txt").read_bytes() == b"reviewed.txt\r\n"
    assert not (harness.repo / "unreviewed.txt").exists()
    # Existing lifecycle persisted reviewed/resolved provenance before execution.
    controls = list((harness.repo / ".agent/replays").rglob("control_result.json"))
    assert any(json.loads(p.read_text())["dream_review_receipt"]["reviewed"] == a for p in controls
               if "dream_review_receipt" in json.loads(p.read_text()))


def test_same_content_different_run_keeps_provenance(harness):
    make_run(harness)
    a = binding(harness)
    make_run(harness, "120001-run")
    b = binding(harness)
    assert a["candidate_fingerprint"] == b["candidate_fingerprint"]
    assert a["artifact_fingerprint"] != b["artifact_fingerprint"]
    assert review.resolve_reviewed_candidate(str(harness.repo), a).binding.run_key == a["run_key"]
    assert_refusal(apply(harness, [{**a, "run_key": b["run_key"]}]), "reviewed_artifact_stale")


@pytest.mark.parametrize("change,code", [
    ("run_missing", "reviewed_run_not_found"),
    ("run_other", "reviewed_candidate_changed"),
    ("idx", "reviewed_candidate_not_found"),
    ("fingerprint", "reviewed_candidate_changed"),
    ("artifact_hash", "reviewed_artifact_stale"),
    ("repo", "reviewed_repository_mismatch"),
    ("delete_report", "reviewed_run_not_found"),
    ("delete_item", "reviewed_candidate_not_found"),
    ("delete_plan", "reviewed_candidate_changed"),
    ("duplicate_idx", "reviewed_artifact_stale"),
    ("edit_content", "reviewed_candidate_changed"),
    ("edit_title", "reviewed_artifact_stale"),
    ("edit_summary", "reviewed_artifact_stale"),
    ("replace_list_bytes", "reviewed_artifact_stale"),
    ("plan_whitespace", "reviewed_artifact_stale"),
    ("malformed_plan", "reviewed_artifact_stale"),
    ("malformed_list", "reviewed_artifact_stale"),
    ("plan_only_upgrade", "reviewed_candidate_changed"),
])
def test_owner_and_http_fail_closed(harness, monkeypatch, change, code):
    path = make_run(harness, status="planned_no_patch" if change == "plan_only_upgrade" else "ready_to_apply")
    a = binding(harness)
    plan_path, list_path = path / "1-item/patch_plan.json", path / "list.json"
    repo = harness.repo
    if change == "run_missing": a["run_key"] = "2026-09-11/000000-run"
    elif change == "run_other":
        make_run(harness, "120001-run", "unreviewed.txt")
        a["run_key"] = "2026-09-11/120001-run"
    elif change == "idx": a["item_idx"] = 2
    elif change == "fingerprint": a["candidate_fingerprint"] = "0" * 64
    elif change == "artifact_hash": a["artifact_fingerprint"] = "0" * 64
    elif change == "repo":
        repo = harness.root / "other" / "repo"
        repo.mkdir(parents=True)
    elif change == "delete_report": list_path.unlink()
    elif change == "delete_plan": plan_path.unlink()
    elif change == "edit_content":
        plan = json.loads(plan_path.read_text()); plan[0]["content"] = "unreviewed"
        plan_path.write_text(json.dumps(plan))
    elif change in {"delete_item", "duplicate_idx", "edit_title", "plan_only_upgrade"}:
        data = json.loads(list_path.read_text())
        if change == "delete_item": data["items"] = []
        elif change == "duplicate_idx": data["items"] *= 2
        elif change == "plan_only_upgrade": data["items"][0]["status"] = "ready_to_apply"
        else: data["items"][0]["title"] = "Changed presentation"
        list_path.write_text(json.dumps(data))
    elif change == "edit_summary": (path / "dream_run_summary.md").write_text("changed")
    elif change == "replace_list_bytes": list_path.write_bytes(list_path.read_bytes() + b"\n")
    elif change == "plan_whitespace": plan_path.write_bytes(plan_path.read_bytes() + b"\n")
    elif change == "malformed_plan": plan_path.write_bytes(b"{")
    elif change == "malformed_list": list_path.write_bytes(b"{")
    before = tree(repo)
    spy = forbid_execution(monkeypatch)
    with pytest.raises(review.DreamReviewError) as error:
        review.resolve_reviewed_candidate(str(repo), a)
    assert error.value.code == code
    assert_refusal(apply(harness, [a], repo=repo, selection=str(a["item_idx"])), code)
    assert tree(repo) == before and spy.call_count == 0


@pytest.mark.parametrize("payload", [None, [], {}, [None], [{}], [1], "legacy"])
def test_missing_or_malformed_binding_never_grants_authority(harness, monkeypatch, payload):
    make_run(harness)
    spy = forbid_execution(monkeypatch)
    assert_refusal(apply(harness, payload), "review_binding_required")
    assert spy.call_count == 0


@pytest.mark.parametrize("field,value", [
    ("run_key", "../../outside"), ("run_key", "2026-09-11/120000-run\n"),
    ("run_key", "C:\\outside"), ("run_key", "/outside"), ("run_key", ["bad"]),
    ("item_idx", True), ("item_idx", "1"), ("item_idx", -1),
    ("repository_id", "repo"), ("candidate_fingerprint", []), ("schema_version", "legacy"),
])
def test_typed_transport_rejects_invalid_fields(harness, monkeypatch, field, value):
    make_run(harness)
    a = binding(harness)
    spy = forbid_execution(monkeypatch)
    assert_refusal(apply(harness, [{**a, field: value}]), "review_binding_required")
    assert spy.call_count == 0


@pytest.mark.parametrize("name", ["../escape", "..\\escape", "/outside", "C:\\outside", ".", ".."])
def test_stored_item_path_escape_never_becomes_reviewable(harness, name):
    path = make_run(harness)
    a = binding(harness)
    data = json.loads((path / "list.json").read_text())
    data["items"][0]["item_dir_name"] = name
    (path / "list.json").write_text(json.dumps(data))
    assert_refusal(apply(harness, [a]), "reviewed_artifact_stale")
    assert "review_binding" not in offered(harness)["items"][0]


def test_real_artifact_junction_escape(harness):
    path = make_run(harness)
    a = binding(harness)
    external = harness.root / "external"
    external.mkdir()
    junction = path / "linked"
    import os
    if os.name == "nt":
        result = subprocess.run(["powershell", "-NoProfile", "-Command",
                                 "New-Item -ItemType Junction -Path '" + str(junction).replace("'", "''") +
                                 "' -Target '" + str(external).replace("'", "''") + "'"], capture_output=True)
        assert result.returncode == 0, result.stderr
    else:
        junction.symlink_to(external, target_is_directory=True)
    data = json.loads((path / "list.json").read_text())
    data["items"][0]["item_dir_name"] = "linked"
    (path / "list.json").write_text(json.dumps(data))
    assert_refusal(apply(harness, [a]), "reviewed_artifact_stale")


def test_batch_checks_every_binding_before_any_execution(harness, monkeypatch):
    path = make_run(harness)
    data = json.loads((path / "list.json").read_text())
    data["items"].append({**data["items"][0], "idx": 2})
    (path / "list.json").write_text(json.dumps(data))
    bindings = [it["review_binding"] for it in offered(harness)["items"]]
    bindings[1]["candidate_fingerprint"] = "0" * 64
    spy = forbid_execution(monkeypatch)
    assert_refusal(apply(harness, bindings, selection="all"), "reviewed_candidate_changed")
    assert spy.call_count == 0


@pytest.mark.parametrize("selection", ["2", "1,2", "1,1", "", "bogus"])
def test_selection_is_cross_check_not_identity(harness, selection):
    make_run(harness)
    assert_refusal(apply(harness, [binding(harness)], selection=selection), "review_binding_required")


def test_browser_candidate_payload_is_never_executed(harness):
    make_run(harness)
    out = apply(harness, [binding(harness)], patch_plan=json.dumps([
        {"op": "create_file", "relative_path": "unreviewed.txt", "content": "bad"}]))
    assert out["results"][0]["status"] == "applied"
    assert not (harness.repo / "unreviewed.txt").exists()


@pytest.mark.parametrize("kind,status,expected", [
    ("idea", "ready_to_apply", "skipped_idea"),
    ("research", "ready_to_apply", "skipped_research"),
    *[("bug", status, "skipped_plan_only") for status in (
        "planned_no_patch", "patch_skipped_needs_vibe", "research_note_created",
        "needs_manual_review", "blocked_missing_context")],
    ("bug", "error", "skipped_not_ready"),
])
def test_exact_binding_does_not_upgrade_capability(harness, monkeypatch, kind, status, expected):
    make_run(harness, kind=kind, status=status)
    spy = forbid_execution(monkeypatch)
    result = apply(harness, [binding(harness)])["results"][0]
    assert result["status"] == expected
    assert result["dream_review_receipt"]["executed"] is None
    assert not (harness.repo / "reviewed.txt").exists() and spy.call_count == 0


def test_legacy_report_requires_fresh_explicit_binding(harness):
    make_run(harness, run="")
    assert_refusal(apply(harness, None), "review_binding_required")
    fresh = binding(harness, run="")
    assert fresh["run_key"] == "2026-09-11"
    assert apply(harness, [fresh])["results"][0]["status"] == "applied"


def test_legacy_unresolvable_item_stays_viewable_without_binding(harness):
    path = make_run(harness, run="")
    data = json.loads((path / "list.json").read_text())
    del data["items"][0]["item_dir_name"]
    data["items"][0]["review_binding"] = {"forged": True}
    (path / "list.json").write_text(json.dumps(data))
    item = offered(harness, run="")["items"][0]
    assert item["title"] == "reviewed.txt" and "review_binding" not in item


@pytest.mark.parametrize("payload", [b"null", b"7", b"{}", b'"plan"', '[]'.encode("utf-16")])
def test_invalid_executable_representation_remains_unbound(harness, payload):
    path = make_run(harness)
    (path / "1-item/patch_plan.json").write_bytes(payload)
    item = offered(harness)["items"][0]
    assert item["review_error"] == "reviewed_artifact_stale"
    assert "review_binding" not in item
    assert_refusal(apply(harness, None), "review_binding_required")


def test_replay_preserves_existing_executor_preconditions(harness):
    make_run(harness)
    a = binding(harness)
    assert apply(harness, [a])["results"][0]["status"] == "applied"
    result = apply(harness, [a])["results"][0]
    assert result["status"] == "apply_failed"
    assert result["dream_review_receipt"]["identity_verified"]
    assert "already exists" in result["message"]
    assert review.resolve_reviewed_candidate(str(harness.repo), a).binding.as_dict() == a


def test_rechecks_artifact_after_inventory_before_execution(harness, monkeypatch):
    from web import app as wa
    path = make_run(harness)
    a = binding(harness)
    def inventory(_):
        (path / "1-item/patch_plan.json").write_bytes(b"[]")
        return {"primary_language": "unknown"}
    monkeypatch.setattr(wa, "inspect_repo_inventory", inventory)
    spy = forbid_execution(monkeypatch)
    assert_refusal(apply(harness, [a])["results"][0], "reviewed_candidate_changed")
    assert spy.call_count == 0


def test_immutable_snapshot_no_walk_and_no_mutation(harness, monkeypatch):
    make_run(harness)
    a = binding(harness)
    spy = Mock(side_effect=AssertionError("unexpected traversal or mutation"))
    for name in ("iterdir", "glob", "rglob", "walk", "write_bytes", "write_text", "unlink"):
        monkeypatch.setattr(Path, name, spy)
    current = review.resolve_reviewed_candidate(str(harness.repo), a)
    with pytest.raises(FrozenInstanceError):
        current.binding.run_key = "different"
    plan = current.plan
    plan[0]["content"] = "changed local copy"
    assert current.plan[0]["content"] == "reviewed.txt\r\n"
    assert spy.call_count == 0


@pytest.mark.parametrize("field", review._EXECUTABLE_FIELDS)
def test_each_execution_relevant_field_changes_digest(field):
    item = {"kind": "bug", "status": "ready_to_apply"}
    plan = [{"op": "create_file", "relative_path": "a", "content": "original"}]
    original = review.candidate_fingerprint(item, plan)
    plan[0][field] = "changed"
    assert review.candidate_fingerprint(item, plan) != original


def test_presentation_is_separate_from_executable_digest():
    item = {"kind": "bug", "status": "ready_to_apply", "title": "title"}
    plan = [{"op": "create_file", "relative_path": "a", "content": "x"}]
    original = review.candidate_fingerprint(item, plan)
    item["title"] = "different"
    plan[0]["explanation"] = "presentation only"
    assert review.candidate_fingerprint(item, plan) == original


@pytest.fixture(scope="module")
def chromium():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as driver:
        browser = driver.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def browser(harness, chromium):
    """Chromium handlers -> actual Flask requests, no listening/external server."""
    responses, requests, errors = [], [], []
    context = chromium.new_context(service_workers="block")
    def route(r):
        req = r.request
        url = urlsplit(req.url)
        if url.hostname != "dream.test":
            # Existing graph CDN is outside this phase; never contact it.
            r.fulfill(status=200, content_type="application/javascript", body="window.mermaid={initialize(){}};")
            return
        endpoint = url.path + ("?" + url.query if url.query else "")
        requests.append((endpoint, req.post_data))
        headers = {**harness.headers}
        if req.headers.get("content-type"):
            headers["Content-Type"] = req.headers["content-type"]
        response = harness.client.open(endpoint, method=req.method, data=req.post_data, headers=headers)
        if url.path == "/dream/apply":
            responses.append(response.get_json())
        r.fulfill(status=response.status_code, body=response.get_data(), headers={"Content-Type": response.content_type})
    context.route("**/*", route)
    page = context.new_page()
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto("http://dream.test/")
    page.locator("#repoPathInput").fill(str(harness.repo))
    yield page, responses, requests
    assert errors == [] and harness.calls == []
    context.close()


def open_review(page):
    page.evaluate("applyDream()")
    page.locator("#dreamApplyList .dream-item-card__check").wait_for()


def test_browser_exact_a_selection_survives_b_arrival(harness, browser):
    page, responses, requests = browser
    make_run(harness)
    open_review(page)
    control = page.locator("#dreamApplyList .dream-item-card__check")
    assert control.evaluate("c => c._reviewedCandidateBinding") is None
    assert "reviewed.txt" in page.locator("#dreamApplyList pre").inner_text()
    control.check()
    a = control.evaluate("c => c._reviewedCandidateBinding")
    make_run(harness, "120001-run", "unreviewed.txt")
    page.evaluate("refreshDreamRuns()")
    assert control.evaluate("c => c._reviewedCandidateBinding") == a
    page.get_by_role("button", name="Apply selected", exact=True).click()
    page.wait_for_function("document.querySelector('#dreamApplyResults').textContent.includes('applied')")
    assert responses[0]["results"][0]["dream_review_receipt"]["executed"] == a
    assert (harness.repo / "reviewed.txt").exists() and not (harness.repo / "unreviewed.txt").exists()
    from urllib.parse import parse_qs
    body = parse_qs(next(body for path, body in requests if path == "/dream/apply"))
    assert json.loads(body["review_bindings"][0]) == [a]


@pytest.mark.parametrize("scenario", ["tamper", "during_apply", "repo_switch", "reload", "select_all", "explicit_new_review"])
def test_browser_review_transition_failures_and_reload(harness, browser, monkeypatch, scenario):
    page, responses, _ = browser
    path = make_run(harness)
    open_review(page)
    control = page.locator("#dreamApplyList .dream-item-card__check")
    if scenario == "select_all": page.locator("#dreamApplySelectAll").check()
    else: control.check()
    a = control.evaluate("c => c._reviewedCandidateBinding")
    assert a is not None
    if scenario == "reload":
        page.reload()
        assert page.locator("#dreamApplyList").count() == 0
        page.locator("#repoPathInput").fill(str(harness.repo))
        open_review(page)
        assert control.evaluate("c => c._reviewedCandidateBinding") is None
        assert responses == []
        return
    if scenario == "explicit_new_review":
        make_run(harness, "120001-run", "unreviewed.txt")
        open_review(page)
        assert control.evaluate("c => c._reviewedCandidateBinding") is None
        control.check()
        assert control.evaluate("c => c._reviewedCandidateBinding.run_key") != a["run_key"]
        return
    if scenario == "tamper": (path / "1-item/patch_plan.json").write_bytes(b"[]")
    if scenario == "during_apply":
        from web import app as wa
        def inventory(_):
            (path / "1-item/patch_plan.json").write_bytes(b"[]")
            return {"primary_language": "unknown"}
        monkeypatch.setattr(wa, "inspect_repo_inventory", inventory)
    if scenario == "repo_switch":
        other = harness.root / "other_repo"; other.mkdir()
        page.locator("#repoPathInput").fill(str(other))
    page.get_by_role("button", name="Apply selected", exact=True).click()
    if scenario == "select_all":
        page.wait_for_function("document.querySelector('#dreamApplyResults').textContent.includes('applied')")
        assert responses[0]["results"][0]["dream_review_receipt"]["executed"] == a
    else:
        page.wait_for_function("document.querySelector('#dreamApplyResults').textContent.includes('Review the Dream candidate again')")
        assert control.is_disabled() and not control.is_checked()
        assert control.evaluate("c => c._reviewedCandidateBinding") is None
        failure = responses[0]["results"][0] if scenario == "during_apply" else responses[0]
        assert_refusal(failure, "reviewed_candidate_changed" if scenario in {"tamper", "during_apply"} else "reviewed_repository_mismatch")
        assert not (harness.repo / "reviewed.txt").exists()


def test_exact_frozen_entry_reversal():
    from tests._auth_dream1_maintenance import before_auth_dream1
    manifest = json.loads((ROOT / "tests/fixtures/auth_dream1_frozen_boundaries.json").read_text())
    for name, digest in manifest["sha256"].items():
        assert hashlib.sha256(before_auth_dream1(name)).hexdigest() == digest, name


def test_phase_registry_and_picker():
    from core.phase_registry import load_phase_registry, validate_phase_registry
    from core.phase_picker import pick_phase_candidates
    registry = load_phase_registry(str(ROOT / "docs/roadmap/phase_registry.json"))
    assert validate_phase_registry(registry)["is_valid"]
    phase = next(p for p in registry["phases"] if p["phase_id"] == "AUTH.DREAM.1")
    assert phase["status"] == "complete" and phase["track"] == "HARDEN"
    assert not phase["network_allowed"] and not phase["model_calls_allowed"]
    assert pick_phase_candidates(registry)["top_recommendation"]["phase_id"] == "DOGFOOD.1B"
