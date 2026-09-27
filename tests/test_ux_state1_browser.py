"""UX.STATE.1 real-Chromium integration: production Flask app, template and JS.

Every scenario drives the shipped page, its static assets and the production
handlers (generatePatch, testPatch, undoPatch, localCritique, setProductMode and
the agent form).  Responses whose arrival order a race depends on are held
inside Chromium and fulfilled deterministically.  Undo outcomes come from the
real DATA.UNDO.1 owner behind /undo_patch wherever a real artifact can produce
them.  The PRE tests replay the same scenarios on the exact entry template,
reconstructed from this phase's reversal receipt and served by the same app.
No model, database or external host is contacted.
"""
from __future__ import annotations

import hashlib
import json
import statistics
import time
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest

from tests.test_auth_web1 import configure_offline_web
from tests.test_auth_web1_browser import _Listener

MERMAID_PREFIX = "https://cdn.jsdelivr.net/npm/mermaid@10/"
SESSION_ID = "20260917160000"
RUN_VALIDATION = "run validation output"
BEFORE = b"def value():\r\n    return 1\r\n"
AFTER = b"def value():\r\n    return 2\r\n"
FLUSH = "() => new Promise(resolve => setTimeout(() => requestAnimationFrame(() => setTimeout(resolve, 0)), 0))"
UNDO_FAILURE_CODES = (
    "backup_not_found", "stale_target", "backup_integrity_failed", "backup_already_consumed", "backup_io_failed",
)
ENTRY_TEMPLATE_SHA256 = "b8b3e9fc5cd73f399315bf3eeae1315f34247b6e3d005afa6fcd9c55d7bdd231"


def _patch(summary: str, relative: str) -> dict:
    return {
        "summary": summary,
        "confidence": 0.7,
        "patch_candidate": {
            "relative_path": relative,
            "file": relative,
            "target_snippet": "def value():\n    return 1\n",
            "patched_snippet": "def value():\n    return 2\n",
        },
    }


PATCH_A = _patch("candidate for repository A", "a.py")
PATCH_B = _patch("candidate for repository B", "b.py")
OLDER = _patch("older request", "older.py")
NEWER = _patch("newer request", "newer.py")


@pytest.fixture(scope="module")
def chromium():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as driver:
        browser = driver.chromium.launch(headless=True)
        yield browser
        browser.close()


class _Held:
    """One browser request paused inside Chromium until the test fulfills it."""

    def __init__(self, route):
        self.route = route
        self.request = route.request
        self.form = parse_qs(route.request.post_data or "", keep_blank_values=True)

    def value(self, name: str) -> str:
        return self.form.get(name, [""])[0]


@pytest.fixture
def live(tmp_path, monkeypatch, chromium):
    state = configure_offline_web(tmp_path, monkeypatch, allow_loopback=True)
    state.submitted = []

    def run_mode(**kwargs):
        state.submitted.append(kwargs)
        result = {"answer": "fixture answer", "context": "{}", "graph": "", "state": "", "patch": "",
                  "validation": RUN_VALIDATION}
        return result, kwargs["project_tag"]

    monkeypatch.setattr(state.wa, "_run_mode", run_mode)
    state.repo_a, state.repo_b = state.root / "repo_a", state.root / "repo_b"
    state.repo_a.mkdir()
    state.repo_b.mkdir()
    listener = _Listener(state.app)
    state.base = f"http://127.0.0.1:{listener.port}"
    state.hold_paths, state.held = set(), {}
    state.posts, state.external, state.errors, state.dialogs = [], [], [], []
    context = chromium.new_context(service_workers="block")

    def route(request_route):
        request = request_route.request
        if request.url.startswith(MERMAID_PREFIX):
            request_route.fulfill(status=200, content_type="application/javascript",
                                  body='window.mermaid={initialize(){},render(){throw new Error("graph outside UX.STATE.1");}};')
        elif request.url.startswith(state.base + "/"):
            path = urlsplit(request.url).path
            if request.method == "POST":
                state.posts.append(path)
            if request.method == "POST" and path in state.hold_paths:
                state.held.setdefault(path, []).append(_Held(request_route))
            else:
                request_route.continue_()
        else:
            state.external.append(request.url)
            request_route.abort()

    context.route("**/*", route)
    page = context.new_page()
    page.on("pageerror", lambda error: state.errors.append(str(error)))

    def on_dialog(dialog):
        state.dialogs.append((dialog.type, dialog.message))
        dialog.accept()

    page.on("dialog", on_dialog)
    state.page, state.context = page, context
    try:
        yield state
    finally:
        context.close()
        listener.close()
    assert state.external == [] and state.errors == [] and state.calls == []


# -- helpers -------------------------------------------------------------------

def _load(live, path="/"):
    response = live.page.goto(live.base + path)
    assert response.status == 200
    live.page.wait_for_load_state("load")


def _flush(page):
    for _ in range(3):
        page.evaluate(FLUSH)


def _await_held(live, path, count):
    deadline = time.monotonic() + 10
    while len(live.held.get(path, [])) < count:
        assert time.monotonic() < deadline, (path, count, live.posts)
        live.page.wait_for_timeout(20)
    return live.held[path][count - 1]


def _fulfill(live, held, payload):
    with live.page.expect_event("requestfinished", lambda request: request is held.request, timeout=10_000):
        held.route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))
    _flush(live.page)


def _candidate(page):
    raw = page.locator("#patchRawJson").text_content() or ""
    try:
        summary = json.loads(raw).get("summary")
    except ValueError:
        summary = None
    card = " ".join((page.locator("#patchCard").text_content() or "").split())
    return SimpleNamespace(raw=raw, summary=summary, card=card)


def _last_action(page):
    node = page.locator("#patchCard .patch-card__last-action")
    return " ".join((node.text_content() or "").split()) if node.count() else ""


def _snapshot(page):
    return page.evaluate("() => WorkbenchState.snapshot()")


def _click(page, handler):
    page.locator(f'button[onclick="{handler}"]').click()


def _open_more_actions(page):
    group = page.locator('[data-ui-group="chat-more-actions"]')
    if not group.evaluate("node => node.open"):
        group.locator("summary").click()


def _open_raw_json(page):
    page.locator("details.patch-raw-details").evaluate("node => { node.open = true; }")


def _seed_session(live, repo, payload, *, web_mode="instant", mode="retrieve"):
    from web import session_store

    session_store.save_sessions([{
        "id": SESSION_ID,
        "title": "UX.STATE.1 fixture",
        "query": "UX.STATE.1 fixture query",
        "repo_path": str(repo),
        "mode": mode,
        "web_mode": web_mode,
        "project_tag": "ux-state1",
        "result": {"answer": "run answer", "context": "{}", "patch": json.dumps(payload, indent=2),
                   "validation": RUN_VALIDATION, "usage": "run usage"},
        "created_at": "2026-09-17T16:00:00",
    }])


# -- UX-02: repository / request / candidate ownership ----------------------------

def _repository_race(live, late_a_payload):
    page = live.page
    live.hold_paths.update({"/generate_patch", "/test_patch"})
    _load(live)
    page.fill("#repoPathInput", str(live.repo_a))
    _click(page, "generatePatch()")
    request_a = _await_held(live, "/generate_patch", 1)
    page.fill("#repoPathInput", str(live.repo_b))
    _click(page, "generatePatch()")
    request_b = _await_held(live, "/generate_patch", 2)
    _fulfill(live, request_b, {"patch": json.dumps(PATCH_B, indent=2), "usage": "usage for B"})
    after_b = _candidate(page)
    _fulfill(live, request_a, late_a_payload)
    after_a = _candidate(page)
    observed = SimpleNamespace(
        request_a=request_a, request_b=request_b, after_b=after_b, after_a=after_a,
        repository=page.input_value("#repoPathInput"),
        usage=page.locator("#usage").text_content(), answer=page.locator("#answer").text_content(),
        last_action=_last_action(page),
    )
    # Entry handlers read #patchRawJson.innerText, which is empty while this
    # disclosure is collapsed; open it so PRE and POST differ only by ownership.
    _open_raw_json(page)
    _open_more_actions(page)
    _click(page, "testPatch()")
    observed.review = _await_held(live, "/test_patch", 1)
    return observed


def test_ux02_late_repository_a_response_never_overwrites_repository_b(live):
    race = _repository_race(live, {"patch": json.dumps(PATCH_A, indent=2), "usage": "usage for A"})
    assert race.request_a.value("repo_path") == str(live.repo_a)
    assert race.request_b.value("repo_path") == str(live.repo_b)
    assert race.after_b.summary == PATCH_B["summary"] and "b.py" in race.after_b.card
    # The repository-A response arrives last and is classified stale.
    assert race.after_a.summary == PATCH_B["summary"] and "a.py" not in race.after_a.card
    assert race.repository == str(live.repo_b)
    assert race.usage == "usage for B"
    assert race.last_action == "Last action: generated"
    # Review controls act on candidate B in repository B.
    assert race.review.value("repo_path") == str(live.repo_b)
    assert json.loads(race.review.value("patch"))["summary"] == PATCH_B["summary"]
    view = _snapshot(live.page)
    assert view["repository"] == str(live.repo_b)
    assert view["candidate"]["repository"] == str(live.repo_b)
    assert view["candidate"]["source"] == "generate"
    assert view["candidate"]["contextGeneration"] == view["contextGeneration"]
    telemetry = live.page.evaluate("() => WorkbenchState.telemetry()")
    assert telemetry["ignoredStaleResponses"] == 1
    assert telemetry["lastIgnored"]["kind"] == "generate"
    assert telemetry["lastIgnored"]["reason"] == "context_changed"
    assert live.posts.count("/generate_patch") == 2 and live.posts.count("/test_patch") == 1


def test_ux02_stale_repository_failure_changes_nothing(live):
    race = _repository_race(live, {"error": "repository A generation failed", "usage": "usage for A"})
    assert race.after_a.summary == PATCH_B["summary"]
    assert "repository A generation failed" not in race.answer
    assert race.usage == "usage for B"
    assert race.last_action == "Last action: generated"
    assert json.loads(race.review.value("patch"))["summary"] == PATCH_B["summary"]
    assert live.page.evaluate("() => WorkbenchState.telemetry().ignoredStaleResponses") == 1


def _same_repository_race(live, first_payload, second_payload):
    page = live.page
    live.hold_paths.add("/generate_patch")
    _load(live)
    page.fill("#repoPathInput", str(live.repo_a))
    _click(page, "generatePatch()")
    first = _await_held(live, "/generate_patch", 1)
    _click(page, "generatePatch()")
    second = _await_held(live, "/generate_patch", 2)
    _fulfill(live, second, second_payload)
    after_second = SimpleNamespace(candidate=_candidate(page), answer=page.locator("#answer").text_content())
    _fulfill(live, first, first_payload)
    after_first = SimpleNamespace(candidate=_candidate(page), answer=page.locator("#answer").text_content())
    return after_second, after_first


def test_same_repository_newer_request_owns_the_candidate_slot_regardless_of_arrival(live):
    after_second, after_first = _same_repository_race(
        live, {"patch": json.dumps(OLDER, indent=2)}, {"patch": json.dumps(NEWER, indent=2)}
    )
    assert after_second.candidate.summary == NEWER["summary"]
    assert after_first.candidate.summary == NEWER["summary"]
    telemetry = live.page.evaluate("() => WorkbenchState.telemetry()")
    assert telemetry["ignoredStaleResponses"] == 1 and telemetry["lastIgnored"]["reason"] == "superseded"


def test_same_repository_stale_failure_does_not_replace_a_newer_success(live):
    after_second, after_first = _same_repository_race(
        live, {"error": "older request failed"}, {"patch": json.dumps(NEWER, indent=2)}
    )
    assert after_first.candidate.summary == NEWER["summary"]
    assert "older request failed" not in after_first.answer
    assert _last_action(live.page) == "Last action: generated"


def test_newer_failure_is_not_overwritten_by_an_older_success(live):
    after_second, after_first = _same_repository_race(
        live, {"patch": json.dumps(OLDER, indent=2)}, {"error": "newer request failed"}
    )
    assert after_second.answer == "newer request failed" and after_second.candidate.raw == ""
    assert after_first.answer == "newer request failed"
    assert after_first.candidate.raw == "" and after_first.candidate.summary is None
    action = _snapshot(live.page)["action"]
    assert (action["kind"], action["status"], action["message"]) == ("generate", "failed", "newer request failed")


def test_repository_switch_invalidates_candidate_review_list_and_critique(live):
    page = live.page
    live.hold_paths.update({"/test_patch", "/generate_candidates", "/local_critique"})
    _seed_session(live, live.repo_a, PATCH_A)
    _load(live, f"/session/{SESSION_ID}")
    assert _candidate(page).summary == PATCH_A["summary"]
    assert page.locator("#validation").text_content() == RUN_VALIDATION
    _open_more_actions(page)
    _click(page, "testPatch()")
    _fulfill(live, _await_held(live, "/test_patch", 1), {
        "success": True, "message": "tested A", "diff": "+A = 2", "validation": "A validation",
        "risk": {"level": "low", "score": 1, "reasons": []}, "validation_command": "pytest -q",
        "patch_safety": {"ok": True, "blocked_paths": [], "reasons": []},
    })
    assert "+A = 2" in page.locator("#diff").text_content()
    assert "A validation" in page.locator("#validation").text_content()
    _click(page, "generateCandidates()")
    _fulfill(live, _await_held(live, "/generate_candidates", 1), {
        "candidates": [{"name": "first", "confidence": 0.4, "patch": PATCH_A["patch_candidate"]}], "usage": "",
    })
    assert page.locator("#candidates button").count() == 1
    _click(page, "localCritique()")
    critique = _await_held(live, "/local_critique", 1)
    assert page.locator("#localCritiqueSection").is_visible()

    page.fill("#repoPathInput", str(live.repo_b))
    _flush(page)
    after = _candidate(page)
    assert after.raw == "" and after.summary is None and "No patch yet" in after.card
    assert page.locator("#diff").text_content() == ""
    assert page.locator("#validation").text_content() == RUN_VALIDATION
    assert page.locator("#candidates button").count() == 0
    assert not page.locator("#localCritiqueSection").is_visible()
    view = _snapshot(page)
    assert view["candidate"] is None and view["review"] is None and view["candidates"] is None
    assert view["action"]["status"] == "idle"

    _fulfill(live, critique, {"ok": True, "critic": {"verdict": "accept", "confidence": 0.9,
                                                      "critic_summary": "late critique for A",
                                                      "risk_flags": [], "must_fix": []}})
    assert not page.locator("#localCritiqueSection").is_visible()
    assert "late critique for A" not in (page.locator("#localCritiqueMain").text_content() or "")
    _click(page, "testPatch()")
    _flush(page)
    assert live.posts.count("/test_patch") == 1
    assert ("alert", "Patch tab does not contain valid JSON.") in live.dialogs
    assert live.page.evaluate("() => WorkbenchState.telemetry().ignoredStaleResponses") == 1


def test_review_controls_act_on_the_owned_candidate_while_raw_json_is_collapsed(live):
    page = live.page
    live.hold_paths.update({"/generate_patch", "/test_patch", "/apply_patch", "/local_critique"})
    _load(live)
    page.fill("#repoPathInput", str(live.repo_a))
    _click(page, "generatePatch()")
    _fulfill(live, _await_held(live, "/generate_patch", 1), {"patch": json.dumps(PATCH_A, indent=2)})
    assert page.locator("#patch").is_visible()
    assert not page.locator("details.patch-raw-details").evaluate("node => node.open")
    _open_more_actions(page)
    _click(page, "testPatch()")
    test = _await_held(live, "/test_patch", 1)
    assert json.loads(test.value("patch")) == PATCH_A and test.value("repo_path") == str(live.repo_a)
    _fulfill(live, test, {"success": False, "message": "validation failed", "diff": "", "validation": "1 failed"})
    assert _last_action(page) == "Last action: test failed — validation failed"
    _click(page, "localCritique()")
    critique = _await_held(live, "/local_critique", 1)
    assert json.loads(critique.value("patch")) == PATCH_A
    _fulfill(live, critique, {"ok": True, "critic": {"verdict": "accept", "confidence": 0.5, "critic_summary": "fine",
                                                      "risk_flags": [], "must_fix": []}})
    _click(page, "applyPatch()")
    apply = _await_held(live, "/apply_patch", 1)
    assert json.loads(apply.value("patch")) == PATCH_A and apply.value("repo_path") == str(live.repo_a)
    assert apply.value("apply_policy") == "ask"
    assert ("confirm", "Apply this patch to your project?") in live.dialogs
    assert not any("does not contain valid JSON" in message or "No patch" in message for _, message in live.dialogs)


def test_opening_a_session_or_new_session_never_keeps_an_unrelated_live_candidate(live):
    page = live.page
    live.hold_paths.add("/generate_patch")
    _seed_session(live, live.repo_a, PATCH_A)
    _load(live)
    page.fill("#repoPathInput", str(live.repo_b))
    _click(page, "generatePatch()")
    _fulfill(live, _await_held(live, "/generate_patch", 1), {"patch": json.dumps(PATCH_B, indent=2)})
    assert _snapshot(page)["candidate"]["source"] == "generate"
    page.locator(f'#sessionList a[data-session-id="{SESSION_ID}"] .session-title').click()
    page.wait_for_load_state("load")
    view = _snapshot(page)
    assert (view["candidate"]["source"], view["candidate"]["repository"]) == ("server", str(live.repo_a))
    assert view["run"]["sessionId"] == SESSION_ID and _candidate(page).summary == PATCH_A["summary"]
    page.locator("#newSessionLink").click()
    page.wait_for_load_state("load")
    view = _snapshot(page)
    assert view["candidate"] is None and view["run"]["sessionId"] == "" and _candidate(page).raw == ""


def test_selecting_a_listed_candidate_replaces_the_candidate_and_its_review(live):
    page = live.page
    live.hold_paths.update({"/test_patch", "/generate_candidates"})
    _seed_session(live, live.repo_a, PATCH_A)
    _load(live, f"/session/{SESSION_ID}")
    _open_more_actions(page)
    _click(page, "testPatch()")
    pending_test = _await_held(live, "/test_patch", 1)
    _click(page, "generateCandidates()")
    _fulfill(live, _await_held(live, "/generate_candidates", 1), {
        "candidates": [{"name": "listed", "confidence": 0.9, "patch": NEWER["patch_candidate"]}], "usage": "",
    })
    page.locator("#candidates button").click()
    _flush(page)
    assert json.loads(_candidate(page).raw)["relative_path"] == "newer.py"
    assert _last_action(page) == "Last action: candidate selected — listed"
    _fulfill(live, pending_test, {"success": True, "message": "tested A", "diff": "+old", "validation": "old"})
    assert page.locator("#diff").text_content() == ""
    assert _last_action(page) == "Last action: candidate selected — listed"
    telemetry = page.evaluate("() => WorkbenchState.telemetry()")
    assert telemetry["lastIgnored"] == {"requestId": telemetry["lastIgnored"]["requestId"], "kind": "test",
                                        "reason": "candidate_changed"}


# -- UX-03: action state derives from the structured backend outcome ---------------

def _undo_fixture(live, *, receipt=None):
    from core.undo_backup import UndoBackupStore

    target = live.repo_a / "app.py"
    target.write_bytes(BEFORE)
    store = UndoBackupStore(live.wa.BACKUP_DIR)
    pending = store.prepare(live.repo_a, "app.py")
    target.write_bytes(AFTER)
    artifact = store.complete(pending, live.repo_a, "app.py")
    sent = receipt or {"backup_id": artifact.backup_id, "transaction_id": artifact.transaction_id}
    _seed_session(live, live.repo_a, {**_patch("applied candidate", "app.py"), "undo_backup": sent})
    return SimpleNamespace(store=store, artifact=artifact, target=target, receipt=sent)


def _click_undo_and_wait(live):
    page = live.page
    _open_more_actions(page)
    with page.expect_response(lambda response: urlsplit(response.url).path == "/undo_patch"):
        _click(page, "undoPatch()")
    _flush(page)


def test_real_undo_success_is_the_only_undone_state(live):
    fixture = _undo_fixture(live)
    _load(live, f"/session/{SESSION_ID}")
    _click_undo_and_wait(live)
    assert fixture.target.read_bytes() == BEFORE
    assert _last_action(live.page) == "Last action: undone — Undo successful"
    view = _snapshot(live.page)
    assert (view["action"]["kind"], view["action"]["status"], view["action"]["code"]) == ("undo", "succeeded", None)
    assert view["slots"]["review"]["status"] == "succeeded"
    assert view["candidate"]["repository"] == str(live.repo_a)
    assert ("alert", "Undo successful") in live.dialogs
    assert live.posts.count("/undo_patch") == 1


@pytest.mark.parametrize("code", UNDO_FAILURE_CODES)
def test_real_undo_failures_are_failed_states_with_their_code(live, monkeypatch, code):
    receipt = {"backup_id": "c" * 64, "transaction_id": "d" * 32} if code == "backup_not_found" else None
    fixture = _undo_fixture(live, receipt=receipt)
    expected = AFTER
    if code == "stale_target":
        expected = b"a later user edit\n"
        fixture.target.write_bytes(expected)
    elif code == "backup_integrity_failed":
        (fixture.store.directory / f"{fixture.artifact.backup_id}.bak").write_bytes(b"tampered")
    elif code == "backup_already_consumed":
        assert fixture.store.undo(live.repo_a, fixture.artifact.backup_id, relative="app.py")["success"]
        expected = BEFORE
    elif code == "backup_io_failed":
        from core import undo_backup

        def refuse_restore(path, raw):
            raise OSError("injected restore failure")

        monkeypatch.setattr(undo_backup, "_atomic_replace_bytes", refuse_restore)
    _load(live, f"/session/{SESSION_ID}")
    _click_undo_and_wait(live)
    last = _last_action(live.page)
    assert last.startswith("Last action: undo failed — ") and "undone" not in last
    assert fixture.target.read_bytes() == expected
    view = _snapshot(live.page)
    action = view["action"]
    assert (action["kind"], action["status"], action["code"]) == ("undo", "failed", code)
    assert view["slots"]["review"]["status"] == "failed"
    assert last == f"Last action: undo failed — {action['message']}" and action["message"]
    assert [message for kind, message in live.dialogs if kind == "alert"] == [action["message"]]
    assert "Undo successful" not in _candidate(live.page).card
    assert view["candidate"]["repository"] == str(live.repo_a)


def _audit_success_false(live):
    live.hold_paths.add("/undo_patch")
    _seed_session(live, live.repo_a, {**_patch("applied candidate", "app.py"),
                                     "undo_backup": {"backup_id": "e" * 64, "transaction_id": "f" * 32}})
    _load(live, f"/session/{SESSION_ID}")
    _open_more_actions(live.page)
    _click(live.page, "undoPatch()")
    held = _await_held(live, "/undo_patch", 1)
    _fulfill(live, held, {"success": False, "message": "Backup not found"})
    return SimpleNamespace(last=_last_action(live.page), form=held.form)


def test_ux03_audit_success_false_response_is_recorded_as_failed(live):
    result = _audit_success_false(live)
    assert result.last == "Last action: undo failed — Backup not found"
    action = _snapshot(live.page)["action"]
    assert (action["status"], action["code"], action["message"]) == ("failed", "undo_failed", "Backup not found")
    assert result.form["backup_id"] == ["e" * 64] and result.form["transaction_id"] == ["f" * 32]


@pytest.mark.parametrize("response", [
    {"success": True, "message": "Undo successful"},
    {"success": True, "message": "Undo successful", "backup_id": "e" * 64, "transaction_id": "f" * 32},
    {"success": True, "message": "Undo successful", "backup_id": "0" * 64, "transaction_id": "f" * 32,
     "restored_sha256": "1" * 64},
    {"success": True, "message": "Undo successful", "backup_id": "e" * 64, "transaction_id": "0" * 32,
     "restored_sha256": "1" * 64},
    {"success": "true", "message": "Undo successful", "backup_id": "e" * 64, "transaction_id": "f" * 32,
     "restored_sha256": "1" * 64},
], ids=["no_receipt", "no_restored_hash", "other_backup", "other_transaction", "string_success"])
def test_undo_success_requires_the_exact_structured_receipt(live, response):
    live.hold_paths.add("/undo_patch")
    _seed_session(live, live.repo_a, {**_patch("applied candidate", "app.py"),
                                     "undo_backup": {"backup_id": "e" * 64, "transaction_id": "f" * 32}})
    _load(live, f"/session/{SESSION_ID}")
    _open_more_actions(live.page)
    _click(live.page, "undoPatch()")
    _fulfill(live, _await_held(live, "/undo_patch", 1), response)
    assert _last_action(live.page).startswith("Last action: undo failed")
    action = _snapshot(live.page)["action"]
    assert action["status"] == "failed"
    expected = "undo_failed" if response["success"] is not True else "undo_receipt_incomplete"
    assert action["code"] == expected


@pytest.mark.parametrize("late", ["success", "failure"])
def test_overlapping_undo_response_belongs_only_to_its_own_context(live, late):
    page = live.page
    live.hold_paths.update({"/undo_patch", "/generate_patch"})
    fixture = _undo_fixture(live)
    _load(live, f"/session/{SESSION_ID}")
    _open_more_actions(page)
    _click(page, "undoPatch()")
    undo = _await_held(live, "/undo_patch", 1)
    assert _last_action(page) == "Last action: undo pending"
    _click(page, "undoPatch()")
    _flush(page)
    assert live.posts.count("/undo_patch") == 1
    assert any(kind == "alert" and "already pending" in message for kind, message in live.dialogs)

    page.fill("#repoPathInput", str(live.repo_b))
    _click(page, "generatePatch()")
    generate = _await_held(live, "/generate_patch", 1)
    payload = ({"success": True, "message": "Undo successful", "restored_sha256": "a" * 64, **fixture.receipt}
               if late == "success" else
               {"success": False, "code": "stale_target", "message": "Target changed since this mutation; Undo refused."})
    _fulfill(live, undo, payload)
    view = _snapshot(page)
    assert (view["action"]["kind"], view["action"]["status"]) == ("generate", "pending")
    assert view["slots"]["candidate"]["status"] == "pending"
    assert view["candidate"] is None
    telemetry = page.evaluate("() => WorkbenchState.telemetry()")
    assert telemetry["lastIgnored"]["kind"] == "undo" and telemetry["lastIgnored"]["reason"] == "context_changed"
    _fulfill(live, generate, {"patch": json.dumps(PATCH_B, indent=2)})
    assert _candidate(page).summary == PATCH_B["summary"]
    assert _last_action(page) == "Last action: generated"
    assert fixture.target.read_bytes() == AFTER
    assert not any(message == "Undo successful" for _, message in live.dialogs)


# -- UX-04: workspace mode and per-mode execution configuration ---------------------

MODE_VIEW = """() => ({
    mode: document.getElementById("modeSelect").value,
    policy: document.getElementById("applyPolicy").value,
    web_mode: document.getElementById("webModeInput").value,
    button: document.getElementById("primarySubmit").textContent.trim(),
    hint: document.getElementById("workbenchSubmitHint").textContent.trim(),
    title: document.getElementById("modeTitle").textContent.trim(),
    current: document.getElementById("workbenchCurrentMode").textContent.trim(),
    body: document.body.dataset.productMode,
    chips: [...document.querySelectorAll(".workbench-mode-chip--active")].map(chip => chip.dataset.workbenchMode),
    pressed: [...document.querySelectorAll(".mode-switcher__item[aria-pressed='true']")].map(item => item.dataset.productMode),
})"""
SWITCHES = {
    "sidebar": ('.mode-switcher__item[data-product-mode="chat"]', '.mode-switcher__item[data-product-mode="instant"]'),
    "confirmation": ('button.workbench-confirmation:text-is("Ask")', 'button.workbench-confirmation:text-is("Preview Run")'),
}
MODE_LABELS = {"retrieve": "Retrieve", "deep": "Deep Understand", "control": "Control", "full": "Full Agent"}
POLICY_LABELS = {"ask": "Ask before apply", "auto": "Auto apply", "plan": "Plan only"}


def _mode_view(page):
    return page.evaluate(MODE_VIEW)


def _open_options(page):
    details = page.locator("details.instant-run-controls")
    if not details.evaluate("node => node.open"):
        details.locator("summary").click()


def _choose(page, mode=None, policy=None):
    _open_options(page)
    if mode is not None:
        page.select_option("#modeSelect", mode)
    if policy is not None:
        page.select_option("#applyPolicy", policy)


def _round_trip(live, mode, policy, via="sidebar"):
    page = live.page
    _load(live)
    _choose(page, mode, policy)
    before = _mode_view(page)
    chat, instant = SWITCHES[via]
    page.locator(chat).click()
    in_chat = _mode_view(page)
    page.locator(instant).click()
    return before, in_chat, _mode_view(page)


def test_ux04_full_ask_chat_instant_round_trip_preserves_instant_configuration(live):
    before, in_chat, after = _round_trip(live, "full", "ask")
    assert (before["mode"], before["policy"], before["button"]) == ("full", "ask", "Run")
    assert (after["web_mode"], after["mode"], after["policy"], after["button"]) == ("instant", "full", "ask", "Run")
    assert "Full Agent" in after["hint"] and "Ask before apply" in after["hint"]
    # Chat's own contract is displayed while Chat is active, never written into Instant.
    assert (in_chat["web_mode"], in_chat["mode"], in_chat["policy"], in_chat["button"]) == ("chat", "retrieve", "plan", "Ask")
    assert "Retrieve" in in_chat["hint"] and "Plan only" in in_chat["hint"]
    execution = live.page.evaluate("() => WorkbenchState.execution()")
    assert execution == {"web_mode": "instant", "mode": "full", "apply_policy": "ask"}


@pytest.mark.parametrize(("mode", "policy", "via"), [
    ("control", "auto", "sidebar"),
    ("deep", "plan", "confirmation"),
    ("retrieve", "auto", "confirmation"),
    ("full", "ask", "confirmation"),
])
def test_other_execution_values_round_trip_through_chat(live, mode, policy, via):
    before, in_chat, after = _round_trip(live, mode, policy, via)
    assert (after["mode"], after["policy"], after["web_mode"]) == (mode, policy, "instant")
    assert (in_chat["mode"], in_chat["policy"], in_chat["web_mode"]) == ("retrieve", "plan", "chat")
    assert MODE_LABELS[mode] in after["hint"] and POLICY_LABELS[policy] in after["hint"]


def test_explicit_instant_edits_persist_per_mode_and_chat_contract_is_not_editable(live):
    page = live.page
    chat, instant = SWITCHES["sidebar"]
    _load(live)
    _choose(page, "control", "auto")
    page.locator(chat).click()
    page.locator(instant).click()
    assert (_mode_view(page)["mode"], _mode_view(page)["policy"]) == ("control", "auto")
    _choose(page, mode="deep")
    page.locator(chat).click()
    page.locator(instant).click()
    assert (_mode_view(page)["mode"], _mode_view(page)["policy"]) == ("deep", "auto")
    page.locator(chat).click()
    assert page.evaluate("() => WorkbenchState.setExecutionOption('mode', 'full')") is False
    assert page.evaluate("() => WorkbenchState.execution()") == {"web_mode": "chat", "mode": "retrieve", "apply_policy": "plan"}
    assert (_mode_view(page)["mode"], _mode_view(page)["policy"]) == ("retrieve", "plan")
    page.locator(instant).click()
    assert page.evaluate("() => WorkbenchState.execution()") == {"web_mode": "instant", "mode": "deep", "apply_policy": "auto"}


def test_primary_action_label_and_mode_preview_derive_from_the_state_owner(live):
    page = live.page
    chat, instant = SWITCHES["confirmation"]
    _load(live)
    _choose(page, "full", "auto")
    for selector in (chat, instant, SWITCHES["sidebar"][0], SWITCHES["sidebar"][1]):
        page.locator(selector).click()
        view = _mode_view(page)
        execution = page.evaluate("() => WorkbenchState.execution()")
        mode = execution["web_mode"]
        assert view["web_mode"] == view["body"] == mode
        assert view["chips"] == [mode] and view["pressed"] == [mode]
        assert view["title"] == view["current"] == ("Chat" if mode == "chat" else "Instant Run")
        assert view["button"] == ("Ask" if mode == "chat" else "Run")
        assert (view["mode"], view["policy"]) == (execution["mode"], execution["apply_policy"])
        assert MODE_LABELS[execution["mode"]] in view["hint"]
        assert POLICY_LABELS[execution["apply_policy"]] in view["hint"]
    # Displayed labels are projections only; editing one never feeds back into state.
    page.evaluate("() => { document.getElementById('workbenchCurrentMode').textContent = 'Chat'; }")
    page.locator('.mode-switcher__item[data-product-mode="instant"]').click()
    assert page.evaluate("() => WorkbenchState.execution()")["web_mode"] == "instant"
    assert _mode_view(page)["current"] == "Instant Run"


def test_submit_serializes_exactly_the_displayed_execution_state(live):
    page = live.page
    _load(live)
    page.fill("#repoPathInput", str(live.repo_a))
    page.fill("textarea[name='query']", "explain the module")
    _choose(page, "full", "ask")
    page.locator(SWITCHES["sidebar"][0]).click()
    page.locator(SWITCHES["sidebar"][1]).click()
    shown = _mode_view(page)
    with page.expect_request(lambda request: request.method == "POST" and urlsplit(request.url).path == "/") as info:
        page.locator("#primarySubmit").click()
    page.wait_for_load_state("load")
    form = parse_qs(info.value.post_data)
    assert (form["web_mode"], form["mode"], form["apply_policy"]) == (["instant"], [shown["mode"]], [shown["policy"]])
    assert shown["mode"] == "full" and live.submitted[-1]["mode"] == "full"

    page.locator(SWITCHES["sidebar"][0]).click()
    shown = _mode_view(page)
    with page.expect_request(lambda request: request.method == "POST" and urlsplit(request.url).path == "/") as info:
        page.locator("#primarySubmit").click()
    page.wait_for_load_state("load")
    form = parse_qs(info.value.post_data)
    assert (form["web_mode"], form["mode"], form["apply_policy"]) == (["chat"], ["retrieve"], ["plan"])
    assert (shown["mode"], shown["policy"], shown["button"]) == ("retrieve", "plan", "Ask")
    assert live.submitted[-1]["mode"] == "retrieve"
    assert page.evaluate("() => WorkbenchState.execution().web_mode") == "chat"


def test_hydration_is_derived_once_from_the_server_rendered_page(live):
    page = live.page
    _seed_session(live, live.repo_a, PATCH_A, web_mode="chat")
    _load(live, f"/session/{SESSION_ID}")
    view = _snapshot(page)
    assert view["hydrated"] is True and view["mode"] == "chat"
    assert view["repository"] == str(live.repo_a) and view["run"]["sessionId"] == SESSION_ID
    assert view["candidate"]["source"] == "server" and view["candidate"]["repository"] == str(live.repo_a)
    assert page.evaluate("() => { try { WorkbenchState.hydrate({}); return 'rehydrated'; } catch (error) { return 'refused'; } }") == "refused"
    # The dormant generic hook (for example a future sign-in) drops context-bound state only.
    page.evaluate("() => WorkbenchState.invalidate('session_changed')")
    invalidated = _snapshot(page)
    assert invalidated["candidate"] is None and invalidated["contextGeneration"] == view["contextGeneration"] + 1
    assert (invalidated["repository"], invalidated["mode"]) == (str(live.repo_a), "chat")
    assert page.evaluate("() => WorkbenchState.telemetry().lastInvalidation") == "session_changed"
    assert _candidate(page).raw == ""
    # A reload re-derives from the server: no browser-only execution memory or candidate authority.
    _load(live)
    _choose(page, "full", "auto")
    _load(live)
    assert page.evaluate("() => WorkbenchState.execution()") == {"web_mode": "instant", "mode": "retrieve", "apply_policy": "ask"}
    assert page.evaluate("() => WorkbenchState.snapshot().candidate") is None


def test_state_transitions_are_cheap_and_never_issue_requests(live):
    page = live.page
    _load(live)
    before = list(live.posts)
    result = page.evaluate("""() => {
        const perOperationUs = (operation, batches = 9, size = 200) => {
            const samples = [];
            for (let batch = 0; batch < batches; batch += 1) {
                const started = performance.now();
                for (let index = 0; index < size; index += 1) operation(index);
                samples.push((performance.now() - started) / size * 1000);
            }
            samples.sort((a, b) => a - b);
            return samples[Math.floor(samples.length / 2)];
        };
        const repository = document.getElementById("repoPathInput");
        return {
            mode_round_trip_render_us: perOperationUs(() => { setProductMode("chat", { persist: false }); setProductMode("instant", { persist: false }); }),
            execution_option_render_us: perOperationUs(index => WorkbenchState.setExecutionOption("mode", index % 2 ? "full" : "deep")),
            repository_invalidation_render_us: perOperationUs(index => WorkbenchState.setRepository("perf-repo-" + index)),
            stale_request_settle_us: perOperationUs(index => {
                const ticket = WorkbenchState.begin("candidates");
                WorkbenchState.setRepository("perf-stale-" + index);
                WorkbenchState.settle(ticket, { status: "succeeded", items: [] });
            }),
        };
    }""")
    print("UX_STATE1_PERFORMANCE=" + json.dumps(result, sort_keys=True))
    assert live.posts == before
    assert all(value < 5000 for value in result.values()), result
    assert statistics.median(result.values()) >= 0


# -- PRE: the same scenarios on the exact AUTH.WEB.READ.1 entry template -------------

@pytest.fixture
def entry(live, monkeypatch):
    """Serve the reconstructed entry template through the same production app."""
    from jinja2 import DictLoader
    from jinja2.utils import LRUCache

    from tests._ux_state1_maintenance import before_ux_state1

    template = before_ux_state1("web/templates/index.html")
    assert hashlib.sha256(template).hexdigest() == ENTRY_TEMPLATE_SHA256
    monkeypatch.setattr(live.app, "jinja_loader", DictLoader({"index.html": template.decode("utf-8")}))
    monkeypatch.setattr(live.app.jinja_env, "cache", LRUCache(8))
    return live


def test_ux02_pre_entry_template_lets_repository_a_overwrite_repository_b(entry):
    race = _repository_race(entry, {"patch": json.dumps(PATCH_A, indent=2), "usage": "usage for A"})
    assert entry.page.evaluate("() => typeof WorkbenchState") == "undefined"
    assert race.after_b.summary == PATCH_B["summary"]
    assert race.after_a.summary == PATCH_A["summary"] and race.repository == str(entry.repo_b)
    assert race.usage == "usage for A"
    # Review controls send repository A's candidate with repository B.
    assert race.review.value("repo_path") == str(entry.repo_b)
    assert json.loads(race.review.value("patch"))["summary"] == PATCH_A["summary"]


def test_ux02_pre_entry_template_lets_an_older_same_repository_request_win(entry):
    after_second, after_first = _same_repository_race(
        entry, {"patch": json.dumps(OLDER, indent=2)}, {"patch": json.dumps(NEWER, indent=2)}
    )
    assert after_second.candidate.summary == NEWER["summary"]
    assert after_first.candidate.summary == OLDER["summary"]


def test_ux03_pre_entry_template_records_undone_after_success_false(entry):
    result = _audit_success_false(entry)
    assert result.last == "Last action: undone — Backup not found"


def test_ux03_pre_entry_template_records_undone_for_a_real_stale_target_refusal(entry):
    fixture = _undo_fixture(entry)
    fixture.target.write_bytes(b"a later user edit\n")
    _load(entry, f"/session/{SESSION_ID}")
    _click_undo_and_wait(entry)
    assert _last_action(entry.page) == "Last action: undone — Target changed since this mutation; Undo refused."
    assert fixture.target.read_bytes() == b"a later user edit\n"


def test_ux04_pre_entry_template_rewrites_full_ask_to_retrieve_plan(entry):
    before, in_chat, after = _round_trip(entry, "full", "ask")
    assert (before["mode"], before["policy"], before["button"]) == ("full", "ask", "Run")
    assert (after["web_mode"], after["mode"], after["policy"], after["button"]) == ("instant", "retrieve", "plan", "Run")


def test_pre_entry_review_controls_lose_the_candidate_while_raw_json_is_collapsed(entry):
    page = entry.page
    entry.hold_paths.update({"/generate_patch", "/test_patch"})
    _load(entry)
    page.fill("#repoPathInput", str(entry.repo_a))
    _click(page, "generatePatch()")
    _fulfill(entry, _await_held(entry, "/generate_patch", 1), {"patch": json.dumps(PATCH_A, indent=2)})
    assert page.locator("#patch").is_visible() and _candidate(page).summary == PATCH_A["summary"]
    _open_more_actions(page)
    _click(page, "testPatch()")
    _flush(page)
    assert entry.posts.count("/test_patch") == 0
    assert ("alert", "Patch tab does not contain valid JSON.") in entry.dialogs
