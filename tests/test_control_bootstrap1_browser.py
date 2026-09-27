"""CONTROL.BOOTSTRAP.1 real-Chromium integration: a fresh Generate transports its task and bootstraps.

Every scenario drives the shipped page and its production handlers.  WorkbenchState
decides whether a Generate ticket has an eligible run and, when it has none,
snapshots the Main Intent text into the frozen ticket; generatePatch and
generateCandidates serialize the fresh form (control=null) plus that task; Chromium
captures the request exactly as sent; the captured request then continues to the
real routes and the real web/control_bootstrap.py owner.  Analysis entry points
raise if reached, pipeline stages are recorded, and deterministic authors answer
both the bootstrap and the downstream provider stages.  The PRE tests replay the
scenarios on the exact CONTROL.FRESH.1 post-state (template, state module and
routes reconstructed from this phase's reversal receipt).  No model, database or
external host is contacted.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qsl

import pytest

from tests.test_control_bootstrap1 import (
    A_PY, BOOTSTRAPPED, DISCOVERY, FRESH1_ANSWER, JAVA_REPLY, JAVA_TASK, MAINAPP, TWOSUM, UNRESOLVED, _entry_views,
    _hypothesis, _reply_for, observe_bootstrap_boundary,
)
from tests.test_ux_context1_browser import (  # noqa: F401  (module_page is a fixture)
    CANDIDATES, CONTROL_A, CONTROL_B, DISPATCHES, GENERATE, QUERY_A, RUN_A_MARKER, _continue, _dispatch,
    _open_run_a, _release, _select_history, _sent, _server_context, module_page,
)
from tests.test_ux_state1_browser import (  # noqa: F401  (chromium and live are fixtures)
    RUN_VALIDATION, _flush, _load, _snapshot, chromium, live,
)

ROOT = Path(__file__).resolve().parents[1]
B_PY = b"def b():\n    return 'B'\n"
MAIN_INTENT = "textarea[name='query']"


@pytest.fixture
def boot(live, monkeypatch):
    """The live page with repository-specific runs and every stage behind CONTROL observable."""
    controls = {str(live.repo_a): CONTROL_A, str(live.repo_b): CONTROL_B}

    def run_mode(**kwargs):
        live.submitted.append(kwargs)
        result = {"answer": f"run answer for {kwargs['repo_path']}",
                  "context": _server_context(controls[kwargs["repo_path"]]),
                  "graph": "", "state": "", "patch": "", "validation": RUN_VALIDATION}
        return result, kwargs["project_tag"]

    monkeypatch.setattr(live.wa, "_run_mode", run_mode)
    live.hold_paths.update({GENERATE[1], CANDIDATES[1]})
    return observe_bootstrap_boundary(live, monkeypatch)


def _fresh_body(state, dispatch, repo, task):
    """The fresh form each handler sends: CONTROL.FRESH.1's body, then the task it bootstraps from."""
    runtime = state.page.input_value("#runtimeEnvironmentSelect")
    if dispatch == GENERATE:
        body = [("repo_path", str(repo)), ("runtime_environment", runtime), ("control", "null"),
                ("anti_lesson_control_requested", "false")]
    else:
        body = [("control", "null"), ("repo_path", str(repo)), ("runtime_environment", runtime)]
    return body + [("query", task)]


def _files(*roots):
    return {path.as_posix(): path.read_bytes() for root in roots for path in sorted(root.rglob("*")) if path.is_file()}


def _serve_control_fresh1_page(state, monkeypatch):
    """Serve the exact CONTROL.FRESH.1 post-state template and state module."""
    from jinja2 import DictLoader
    from jinja2.utils import LRUCache

    from tests._control_bootstrap1_maintenance import before_control_bootstrap1

    template = before_control_bootstrap1("web/templates/index.html")
    module = before_control_bootstrap1("web/static/workbench_state.js")
    reversal = json.loads((ROOT / "tests/fixtures/control_fresh1_reversal.json").read_text(encoding="utf-8"))
    frozen = json.loads((ROOT / "tests/fixtures/control_fresh1_frozen_boundaries.json").read_text(encoding="utf-8"))
    assert hashlib.sha256(template).hexdigest() == reversal["files"]["web/templates/index.html"]["post_sha256"]
    assert hashlib.sha256(module).hexdigest() == frozen["sha256"]["web/static/workbench_state.js"]
    monkeypatch.setattr(state.app, "jinja_loader", DictLoader({"index.html": template.decode("utf-8")}))
    monkeypatch.setattr(state.app.jinja_env, "cache", LRUCache(8))

    def entry_module(route):
        response = route.fetch()
        assert response.status == 200
        route.fulfill(response=response, body=module)

    state.page.route("**/static/workbench_state.js", entry_module)


# -- New Session: a named file becomes the first CONTROL --------------------------------------------------

@DISPATCHES
def test_new_session_generate_transports_the_task_and_bootstraps_the_first_control(boot, dispatch):
    page = boot.page
    (boot.repo_a / "a.py").write_bytes(A_PY)
    boot.bootstrap_reply = _reply_for("a.py")
    _load(boot, "/new")
    assert _snapshot(page)["requestRun"] is None
    page.fill("#repoPathInput", str(boot.repo_a))
    task = "fix a.py: value() must return 2"
    page.fill(MAIN_INTENT, task)
    before = _files(boot.repo_a)
    held = _dispatch(boot, dispatch)
    assert _sent(held) == _fresh_body(boot, dispatch, boot.repo_a, task)
    answer = _continue(boot, held)
    receipt = answer["control_bootstrap"]
    assert receipt["status"] == BOOTSTRAPPED and receipt["evidence_targets"] == ["a.py"]
    assert boot.bootstrap_seen == {"a.py": A_PY.decode()}
    # The unchanged CONTROL-dependent pipeline ran after the one bootstrap call.
    assert boot.stages[:2] == ["decide_harness_mode", "build_control_prompt"] and boot.analysis == []
    view = _snapshot(page)
    if dispatch == GENERATE:
        assert view["candidate"]["source"] == "generate" and view["action"]["status"] == "succeeded"
    else:
        assert len(view["candidates"]["items"]) == 3
    # No run, session or history entry was invented for the fresh request.
    assert view["run"]["sessionId"] == "" and view["requestRun"] is None
    assert not (boot.root / "sessions.json").exists()
    assert _files(boot.repo_a) == before


@DISPATCHES
def test_a_task_that_names_no_file_shows_the_typed_discovery_answer(boot, dispatch):
    page = boot.page
    _load(boot, "/new")
    page.fill("#repoPathInput", str(boot.repo_a))
    page.fill(MAIN_INTENT, "Why is the build slow?")
    held = _dispatch(boot, dispatch)
    answer = _continue(boot, held)
    assert (answer["code"], answer["reason"]) == (DISCOVERY, "no_explicit_target")
    view = _snapshot(page)
    if dispatch == GENERATE:
        assert page.locator("#answer").text_content() == answer["error"]
        assert view["action"]["status"] == "failed" and view["action"]["message"] == answer["error"]
    else:
        assert view["candidates"]["items"] is None and view["candidates"]["message"] == answer["error"]
    assert view["candidate"] is None and boot.prompts == [] and boot.stages == []
    assert "Invalid control JSON" not in (page.locator("body").text_content() or "")


def test_the_dispatched_ticket_keeps_its_task_while_main_intent_is_edited(boot):
    page = boot.page
    (boot.repo_a / "a.py").write_bytes(A_PY)
    boot.bootstrap_reply = _reply_for("a.py")
    _load(boot, "/new")
    page.fill("#repoPathInput", str(boot.repo_a))
    page.fill(MAIN_INTENT, "fix a.py")
    held = _dispatch(boot, GENERATE)
    page.fill(MAIN_INTENT, "fix something else entirely in b.py")
    assert dict(_sent(held))["query"] == "fix a.py"
    answer = _continue(boot, held)
    assert answer["control_bootstrap"]["requested_targets"] == ["a.py"]


TICKETS = """(seed) => {
    const W = WorkbenchState;
    W.hydrate(seed);
    const typed = { task: "  fix a.py\\n  exactly  " };
    const generate = W.begin("generate", typed);
    typed.task = "edited after dispatch";
    const candidates = W.begin("candidates", { task: "fix b.py" });
    const bare = W.begin("generate");
    const upload = W.begin("upload", { task: "not a Generate request" });
    return {
        generate: generate.task, candidates: candidates.task, bare: bare.task, upload: upload.task,
        frozen: Object.isFrozen(generate), bound: generate.requestRun !== null,
    };
}"""


def test_state_owner_snapshots_the_task_only_for_fresh_generate_tickets(module_page):
    fresh = module_page.evaluate(TICKETS, {"repository": "repository-A"})
    # Lossless, captured at dispatch, never parsed: the later edit does not reach the ticket.
    assert fresh == {"generate": "  fix a.py\n  exactly  ", "candidates": "fix b.py", "bare": "", "upload": None,
                     "frozen": True, "bound": False}


def test_state_owner_gives_a_continuation_ticket_no_task(module_page):
    run = {"sessionId": "run-A", "repository": "repository-A", "context": _server_context(CONTROL_A)}
    bound = module_page.evaluate(TICKETS, {"repository": "repository-A", "run": run})
    assert bound == {"generate": None, "candidates": None, "bare": None, "upload": None, "frozen": True,
                     "bound": True}


# -- repository A -> repository B: never A's CONTROL, bootstrap from B's files ----------------------------

@DISPATCHES
@pytest.mark.parametrize("how", ["produced", "history"])
def test_repository_b_after_run_a_bootstraps_from_b_and_never_carries_run_a(boot, dispatch, how):
    page = boot.page
    (boot.repo_b / "b.py").write_bytes(B_PY)
    boot.bootstrap_reply = {"hypotheses": [_hypothesis("b.py", "b")], "evidence_gaps": []}
    _open_run_a(boot, how)
    run = _snapshot(page)["run"]
    page.fill("#repoPathInput", str(boot.repo_b))
    page.fill(MAIN_INTENT, "fix b.py")
    _flush(page)
    held = _dispatch(boot, dispatch)
    sent = _sent(held)
    assert sent == _fresh_body(boot, dispatch, boot.repo_b, "fix b.py")
    assert not any(RUN_A_MARKER in value or "a.py" in value for _, value in sent)
    answer = _continue(boot, held)
    receipt = answer["control_bootstrap"]
    assert receipt["status"] == BOOTSTRAPPED
    assert receipt["repository"]["canonical_root"] == str(boot.repo_b.resolve())
    assert boot.bootstrap_seen == {"b.py": B_PY.decode()}
    assert all(RUN_A_MARKER not in prompt and "def value():" not in prompt for prompt in boot.prompts)
    view = _snapshot(page)
    assert view["run"] == run and view["requestRun"] is None and view["repository"] == str(boot.repo_b)


def test_run_a_intent_left_in_main_intent_is_grounded_in_repository_b_only(boot):
    page = boot.page
    (boot.repo_a / "a.py").write_bytes(A_PY)
    _open_run_a(boot, "produced")
    assert page.input_value(MAIN_INTENT) == QUERY_A
    page.fill("#repoPathInput", str(boot.repo_b))
    _flush(page)
    held = _dispatch(boot, GENERATE)
    sent = dict(_sent(held))
    # The typed intent travels; run A's CONTROL does not.
    assert sent["control"] == "null" and sent["query"] == QUERY_A and RUN_A_MARKER not in json.dumps(sent)
    answer = _continue(boot, held)
    # a.py exists only in repository A, so repository B cannot ground it: nothing read, no model.
    assert (answer["code"], answer["reason"]) == (UNRESOLVED, "not_found")
    assert boot.prompts == [] and boot.stages == []


def test_switching_back_stays_fresh_until_the_run_is_selected_again(boot):
    page = boot.page
    _open_run_a(boot, "produced")
    session_id = _snapshot(page)["run"]["sessionId"]
    page.fill("#repoPathInput", str(boot.repo_b))
    page.fill("#repoPathInput", str(boot.repo_a))
    _flush(page)
    held = _dispatch(boot, GENERATE)
    sent = dict(_sent(held))
    assert sent["control"] == "null" and sent["query"] == QUERY_A
    _release(boot, held)
    _select_history(boot, session_id)
    held = _dispatch(boot, GENERATE)
    sent = dict(_sent(held))
    assert json.loads(sent["control"]) == CONTROL_A and "query" not in sent
    _release(boot, held)


# -- same-repository continuation is unchanged --------------------------------------------------------------

def test_same_repository_continuation_bodies_are_byte_identical_to_the_control_fresh1_page(boot, monkeypatch):
    bodies = {}
    for state in ("post", "entry"):
        if state == "entry":
            _serve_control_fresh1_page(boot, monkeypatch)
        for how in ("produced", "history"):
            _open_run_a(boot, how)
            for dispatch in (GENERATE, CANDIDATES):
                held = _dispatch(boot, dispatch)
                bodies[(state, how, dispatch[1])] = held.request.post_data
                _release(boot, held)
    for how in ("produced", "history"):
        for _, path in (GENERATE, CANDIDATES):
            assert bodies[("post", how, path)] == bodies[("entry", how, path)], (how, path)
            sent = dict(parse_qsl(bodies[("post", how, path)]))
            assert json.loads(sent["control"]) == CONTROL_A and "query" not in sent
    assert boot.prompts == []


# -- Java dogfood ---------------------------------------------------------------------------------------------

@DISPATCHES
def test_java_dogfood_new_session_reviews_both_requested_files(boot, dispatch):
    page = boot.page
    for name, raw in (("Twosum.java", TWOSUM), ("MainApp.java", MAINAPP)):
        (boot.repo_b / name).write_bytes(raw)
    boot.bootstrap_reply = JAVA_REPLY
    _load(boot, "/new")
    page.fill("#repoPathInput", str(boot.repo_b))
    page.fill(MAIN_INTENT, JAVA_TASK)
    held = _dispatch(boot, dispatch)
    assert _sent(held) == _fresh_body(boot, dispatch, boot.repo_b, JAVA_TASK)
    answer = _continue(boot, held)
    receipt = answer["control_bootstrap"]
    assert receipt["requested_targets"] == receipt["evidence_targets"] == ["Twosum.java", "MainApp.java"]
    assert receipt["evidence_gap_needs"] == ["compile_evidence"] and receipt["localized_patch_targets"] is None
    assert boot.bootstrap_seen == {"Twosum.java": TWOSUM.decode(), "MainApp.java": MAINAPP.decode()}
    for prompt in boot.prompts[1:]:
        assert "file=Twosum.java" in prompt and "file=MainApp.java" in prompt
    view = _snapshot(page)
    if dispatch == GENERATE:
        # The downstream gate refused to patch without executed evidence; that is allowed.
        assert view["candidate"]["payload"]["patch_candidate"] is None
    else:
        assert all(item["patch"]["patch_candidate"] is None for item in view["candidates"]["items"])
    assert (boot.repo_b / "Twosum.java").read_bytes() == TWOSUM
    assert (boot.repo_b / "MainApp.java").read_bytes() == MAINAPP
    assert not (boot.root / "sessions.json").exists()


# -- PRE: the CONTROL.FRESH.1 page and routes ---------------------------------------------------------------

@DISPATCHES
def test_pre_control_fresh1_page_sends_no_task_and_stops_at_the_boundary(boot, monkeypatch, dispatch):
    _serve_control_fresh1_page(boot, monkeypatch)
    for name, view in _entry_views(boot).items():
        monkeypatch.setitem(boot.app.view_functions, name, view)
    page = boot.page
    (boot.repo_a / "a.py").write_bytes(A_PY)
    _load(boot, "/new")
    page.fill("#repoPathInput", str(boot.repo_a))
    page.fill(MAIN_INTENT, "fix a.py: value() must return 2")
    held = _dispatch(boot, dispatch)
    sent = dict(_sent(held))
    assert sent["control"] == "null" and "query" not in sent
    assert _continue(boot, held) == FRESH1_ANSWER
    assert boot.prompts == [] and boot.stages == [] and boot.analysis == []
