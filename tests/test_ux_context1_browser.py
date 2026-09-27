"""UX.CONTEXT.1 real-Chromium integration: run / repository context binding.

Every scenario drives the shipped page, its static assets and the production
handlers: the agent form produces a run, the session list selects history,
browser history restores a page, and generatePatch / generateCandidates send
their requests.  Each Generate request is captured inside Chromium exactly as
the page sent it; where the backend answer matters, the captured request then
continues to the real route.  The PRE tests replay the same scenarios on the
exact UX.STATE.1 post-state (template and state module), reconstructed from
this phase's reversal receipt and served by the same app.  No model, database
or external host is contacted.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

import pytest

from tests.test_control_fresh1 import FRESH_ANSWER, FRESH_WIRE
from tests.test_ux_state1_browser import (  # noqa: F401  (chromium and live are fixtures)
    PATCH_A, RUN_VALIDATION, _await_held, _click, _flush, _fulfill, _load, _open_more_actions, _snapshot,
    chromium, live,
)

ROOT = Path(__file__).resolve().parents[1]
ENTRY_TEMPLATE_SHA256 = "ba8ad87f324c70abfcdbb733dd30dcb2c5eb543964d2c0ac7222d0f71af6f11d"
ENTRY_MODULE_SHA256 = "36916265f62cc12ae63a6316ac2bca90d0b3c3767d8091b8b568e333e3fc67cd"
RUN_A_MARKER = "UX.CONTEXT.1 CONTROL context of the repository A run"
CONTROL_A = {
    "run_marker": RUN_A_MARKER,
    "query": "make value() return 2",
    "top_hypothesis": {"symbol": "a.py::value", "confidence": 0.82},
    "patch_intent": {"relative_path": "a.py", "source_snippet": "def value():\n    return 1\n"},
    "related_snippets": [{"file": "a.py", "snippet": "def value():\n    return 1\n"}],
}
CONTROL_B = {
    "run_marker": "UX.CONTEXT.1 CONTROL context of the repository B run",
    "query": "rename Greeter.greet to welcome",
    "top_hypothesis": {"symbol": "src/main/java/demo/Greeter.java::greet", "confidence": 0.74},
    "patch_intent": {"relative_path": "src/main/java/demo/Greeter.java",
                     "source_snippet": "public String greet(String name) {"},
    "related_snippets": [{"file": "src/main/java/demo/Main.java", "snippet": "new Greeter().greet(\"world\")"}],
}
QUERY_A = "make value() return 2 in a.py"
JAVA_PROJECT = {
    "src/main/java/demo/Greeter.java": (
        b"package demo;\n\npublic final class Greeter {\n"
        b"    public String greet(String name) {\n        return \"Hello, \" + name;\n    }\n}\n"
    ),
    "src/main/java/demo/Main.java": (
        b"package demo;\n\npublic final class Main {\n"
        b"    public static void main(String[] args) {\n"
        b"        System.out.println(new Greeter().greet(\"world\"));\n    }\n}\n"
    ),
}
JAVA_TWO_FILE_REQUEST = (
    "Rename Greeter.greet to welcome in src/main/java/demo/Greeter.java "
    "and update its call in src/main/java/demo/Main.java"
)
HISTORY_A = "20260917170000"
HISTORY_B = "20260917170100"
GENERATE = ("generatePatch()", "/generate_patch")
CANDIDATES = ("generateCandidates()", "/generate_candidates")
DISPATCHES = pytest.mark.parametrize("dispatch", [GENERATE, CANDIDATES], ids=["generate_patch", "generate_candidates"])
# CONTROL.FRESH.1 made the fresh no-prior-context form explicit (JSON null) and gave it a typed
# bootstrap-boundary answer; the empty form and "Invalid control JSON" stay pinned there as PRE.
FRESH_FORM = FRESH_WIRE
FRESH_FORM_ANSWER = FRESH_ANSWER


def _server_context(control: dict) -> str:
    """The run's context exactly as the backend stores and renders it."""
    return json.dumps(control, indent=2, ensure_ascii=False)


@pytest.fixture
def ctx(live, monkeypatch):
    """The UX.STATE.1 live fixture whose runs render repository-specific CONTROL context."""
    controls = {str(live.repo_a): CONTROL_A, str(live.repo_b): CONTROL_B}

    def run_mode(**kwargs):
        live.submitted.append(kwargs)
        result = {"answer": f"run answer for {kwargs['repo_path']}",
                  "context": _server_context(controls[kwargs["repo_path"]]),
                  "graph": "", "state": "", "patch": "", "validation": RUN_VALIDATION}
        return result, kwargs["project_tag"]

    monkeypatch.setattr(live.wa, "_run_mode", run_mode)
    live.hold_paths.update({GENERATE[1], CANDIDATES[1]})
    _serve_control_fresh1_template(live, monkeypatch)
    return live


def _serve_control_fresh1_template(live, monkeypatch):
    """Keep these invariants on the CONTROL.FRESH.1 page they were re-homed to.

    CONTROL.BOOTSTRAP.1 later makes a fresh ticket also transport its Main Intent;
    tests/test_control_bootstrap1_browser.py proves the same run/repository binding on
    the live page.  The state module stays the live one.
    """
    from jinja2 import DictLoader
    from jinja2.utils import LRUCache

    from tests._control_bootstrap1_maintenance import before_control_bootstrap1

    template = before_control_bootstrap1("web/templates/index.html")
    monkeypatch.setattr(live.app, "jinja_loader", DictLoader({"index.html": template.decode("utf-8")}))
    monkeypatch.setattr(live.app.jinja_env, "cache", LRUCache(8))


def _serve_entry(live, monkeypatch):
    """Serve the reconstructed UX.STATE.1 post-state template and state module."""
    from jinja2 import DictLoader
    from jinja2.utils import LRUCache

    from tests._ux_context1_maintenance import before_ux_context1

    template = before_ux_context1("web/templates/index.html")
    module = before_ux_context1("web/static/workbench_state.js")
    assert hashlib.sha256(template).hexdigest() == ENTRY_TEMPLATE_SHA256
    assert hashlib.sha256(module).hexdigest() == ENTRY_MODULE_SHA256
    monkeypatch.setattr(live.app, "jinja_loader", DictLoader({"index.html": template.decode("utf-8")}))
    monkeypatch.setattr(live.app.jinja_env, "cache", LRUCache(8))

    def entry_module(route):
        response = route.fetch()
        assert response.status == 200
        route.fulfill(response=response, body=module)

    live.page.route("**/static/workbench_state.js", entry_module)
    return live


@pytest.fixture
def entry(ctx, monkeypatch):
    return _serve_entry(ctx, monkeypatch)


# -- helpers -------------------------------------------------------------------

def _run(live, repo, query):
    """Produce a run with the production agent form (a native POST that renders it)."""
    page = live.page
    page.fill("#repoPathInput", str(repo))
    page.fill("textarea[name='query']", query)
    with page.expect_response(lambda response: response.request.method == "POST"
                              and urlsplit(response.url).path == "/"):
        page.locator("#primarySubmit").click()
    page.wait_for_load_state("load")


def _seed_history(live):
    from web import session_store

    def session(session_id, repo, control, title):
        return {
            "id": session_id, "title": title, "query": title, "repo_path": str(repo), "mode": "control",
            "web_mode": "instant", "project_tag": "ux-context1", "created_at": "2026-09-17T17:00:00",
            "result": {"answer": title, "context": _server_context(control), "patch": "",
                       "validation": RUN_VALIDATION, "usage": ""},
        }

    session_store.save_sessions([
        session(HISTORY_B, live.repo_b, CONTROL_B, "repository B run"),
        session(HISTORY_A, live.repo_a, CONTROL_A, "repository A run"),
    ])


def _navigate(live, action):
    with live.page.expect_navigation(wait_until="load"):
        action()


def _select_history(live, session_id):
    """Explicitly select a historical run from the production session list."""
    link = live.page.locator(f'#sessionList a[data-session-id="{session_id}"] .session-title')
    link.wait_for()
    _navigate(live, link.click)
    assert urlsplit(live.page.url).path == f"/session/{session_id}"


def _open_run_a(live, how):
    if how == "produced":
        _load(live)
        _run(live, live.repo_a, QUERY_A)
    else:
        _seed_history(live)
        _load(live)
        live.page.fill("#repoPathInput", str(live.repo_a))
        _select_history(live, HISTORY_A)


def _dispatch(live, dispatch):
    handler, path = dispatch
    count = len(live.held.get(path, []))
    if handler == CANDIDATES[0]:
        _open_more_actions(live.page)
    _click(live.page, handler)
    return _await_held(live, path, count + 1)


def _release(live, held):
    """Answer a captured request locally (as a failed generation) without the backend."""
    _fulfill(live, held, {"error": "captured by UX.CONTEXT.1"})


def _continue(live, held):
    """Let a captured request reach the real backend route and return its JSON answer."""
    with live.page.expect_response(lambda response: response.request is held.request) as info:
        held.route.continue_()
    answer = info.value.json()
    _flush(live.page)
    return answer


def _expected(live, dispatch, repo, control):
    # runtime_environment is repository-independent form configuration, sent as displayed.
    runtime = live.page.input_value("#runtimeEnvironmentSelect")
    if dispatch == GENERATE:
        return [("repo_path", str(repo)), ("runtime_environment", runtime), ("control", control),
                ("anti_lesson_control_requested", "false")]
    return [("control", control), ("repo_path", str(repo)), ("runtime_environment", runtime)]


def _sent(held):
    return parse_qsl(held.request.post_data or "", keep_blank_values=True)


def _carries_run_a(held):
    return any(RUN_A_MARKER in value or "a.py" in value for _, value in _sent(held))


def _page_context(page):
    """The run context the page displays (its load-time JSON formatting pass included)."""
    return page.locator("#context").text_content()


# -- repository A -> repository B (the primary regression) -----------------------

@DISPATCHES
@pytest.mark.parametrize("how", ["produced", "history"])
def test_repository_b_generate_never_carries_the_displayed_repository_a_run_control(ctx, dispatch, how):
    page = ctx.page
    _open_run_a(ctx, how)
    shown = _page_context(page)
    assert json.loads(shown) == CONTROL_A
    before = _snapshot(page)
    run = before["run"]
    assert run["source"] == "server" and run["sessionId"] and run["repository"] == str(ctx.repo_a)
    assert run["context"] == shown and run["contextGeneration"] == before["contextGeneration"]
    assert before["requestRun"] == run

    page.fill("#repoPathInput", str(ctx.repo_b))
    _flush(page)
    after = _snapshot(page)
    # Run A stays displayed for reference; it is no longer eligible for a request.
    assert _page_context(page) == shown and after["run"] == run
    assert after["requestRun"] is None
    assert after["contextGeneration"] == before["contextGeneration"] + 1

    held = _dispatch(ctx, dispatch)
    assert _sent(held) == _expected(ctx, dispatch, ctx.repo_b, FRESH_FORM)
    assert not _carries_run_a(held)
    # The fresh no-prior-context form, answered at the bootstrap boundary without a model call.
    assert _continue(ctx, held) == FRESH_FORM_ANSWER
    assert ctx.calls == []


# -- same-repository continuation ---------------------------------------------------

@DISPATCHES
@pytest.mark.parametrize("how", ["produced", "history"])
def test_same_repository_continuation_transports_the_displayed_run_control(ctx, dispatch, how):
    page = ctx.page
    _open_run_a(ctx, how)
    shown = _page_context(page)
    assert json.loads(shown) == CONTROL_A
    held = _dispatch(ctx, dispatch)
    assert _sent(held) == _expected(ctx, dispatch, ctx.repo_a, shown)
    _release(ctx, held)
    # Whitespace that normalizes to the same repository is not a repository change.
    page.fill("#repoPathInput", f"  {ctx.repo_a}  ")
    held = _dispatch(ctx, dispatch)
    assert _sent(held) == _expected(ctx, dispatch, ctx.repo_a, shown)
    view = _snapshot(page)
    assert view["requestRun"] == view["run"] and view["run"]["context"] == shown


def test_same_repository_continuation_bodies_are_byte_identical_to_the_entry_state(ctx, monkeypatch):
    bodies = {}
    for state in ("post", "entry"):
        if state == "entry":
            _serve_entry(ctx, monkeypatch)
        for how in ("produced", "history"):
            _open_run_a(ctx, how)
            for dispatch in (GENERATE, CANDIDATES):
                held = _dispatch(ctx, dispatch)
                bodies[(state, how, dispatch[1])] = held.request.post_data
                _release(ctx, held)
    assert ctx.page.evaluate("() => 'requestRun' in WorkbenchState.snapshot()") is False
    for how in ("produced", "history"):
        for _, path in (GENERATE, CANDIDATES):
            assert bodies[("post", how, path)] == bodies[("entry", how, path)], (how, path)
            assert json.loads(dict(parse_qsl(bodies[("post", how, path)]))["control"]) == CONTROL_A


def test_transported_run_context_no_longer_depends_on_which_result_tab_is_visible(ctx, monkeypatch):
    sent = {}
    for state in ("post", "entry"):
        if state == "entry":
            _serve_entry(ctx, monkeypatch)
        _open_run_a(ctx, "produced")
        for tab in ("answer", "context"):
            ctx.page.evaluate("(tab) => showTab(tab)", tab)
            held = _dispatch(ctx, GENERATE)
            sent[(state, tab)] = dict(_sent(held))["control"]
            _release(ctx, held)
    # The entry read #context.innerText at click time, and the page's load-time JSON
    # formatting stores newlines as <br>: they were sent only while Context was visible.
    assert sent[("post", "answer")] == sent[("post", "context")] == sent[("entry", "answer")]
    assert "\n" not in sent[("entry", "answer")] and "\n" in sent[("entry", "context")]
    assert {json.dumps(json.loads(value), sort_keys=True) for value in sent.values()} == {
        json.dumps(CONTROL_A, sort_keys=True)}


# -- explicit history selection ----------------------------------------------------------

def test_explicit_history_selection_binds_only_the_selected_run_in_its_own_repository(ctx):
    page = ctx.page
    _seed_history(ctx)
    _load(ctx, f"/session/{HISTORY_B}")
    assert _snapshot(page)["requestRun"]["sessionId"] == HISTORY_B
    assert json.loads(_page_context(page)) == CONTROL_B
    held = _dispatch(ctx, GENERATE)
    assert _sent(held) == _expected(ctx, GENERATE, ctx.repo_b, _page_context(page))
    _release(ctx, held)

    # From repository B, the user explicitly selects the historical repository A run.
    _select_history(ctx, HISTORY_A)
    view = _snapshot(page)
    assert page.input_value("#repoPathInput") == str(ctx.repo_a)
    assert view["run"]["sessionId"] == HISTORY_A and view["requestRun"] == view["run"]
    assert json.loads(_page_context(page)) == CONTROL_A
    for dispatch in (GENERATE, CANDIDATES):
        held = _dispatch(ctx, dispatch)
        assert _sent(held) == _expected(ctx, dispatch, ctx.repo_a, _page_context(page))
        _release(ctx, held)


# -- switching away and back ---------------------------------------------------------------

def test_typing_the_old_repository_back_never_resurrects_the_run_context(ctx):
    page = ctx.page
    _open_run_a(ctx, "produced")
    before = _snapshot(page)
    page.fill("#repoPathInput", str(ctx.repo_b))
    page.fill("#repoPathInput", str(ctx.repo_a))
    _flush(page)
    view = _snapshot(page)
    assert page.input_value("#repoPathInput") == view["repository"] == str(ctx.repo_a)
    assert view["contextGeneration"] == before["contextGeneration"] + 2
    assert view["run"] == before["run"] and view["requestRun"] is None
    for dispatch in (GENERATE, CANDIDATES):
        held = _dispatch(ctx, dispatch)
        assert _sent(held) == _expected(ctx, dispatch, ctx.repo_a, FRESH_FORM)
        _release(ctx, held)

    # Explicitly selecting the run again is what restores continuation.
    _select_history(ctx, before["run"]["sessionId"])
    assert _snapshot(page)["requestRun"]["sessionId"] == before["run"]["sessionId"]
    held = _dispatch(ctx, GENERATE)
    assert _sent(held) == _expected(ctx, GENERATE, ctx.repo_a, _page_context(page))
    assert json.loads(_page_context(page)) == CONTROL_A


# -- mismatched history -------------------------------------------------------------------------

def test_browser_restored_repository_b_over_historical_run_a_never_transports_it(ctx):
    page = ctx.page
    _seed_history(ctx)
    _load(ctx, f"/session/{HISTORY_A}")
    page.fill("#repoPathInput", str(ctx.repo_b))
    _navigate(ctx, page.locator("#newSessionLink").click)
    page.go_back(wait_until="load")
    assert urlsplit(page.url).path == f"/session/{HISTORY_A}"
    # The historical run A is viewable again while the page shows repository B.
    assert page.input_value("#repoPathInput") == str(ctx.repo_b)
    assert json.loads(_page_context(page)) == CONTROL_A
    for dispatch in (GENERATE, CANDIDATES):
        held = _dispatch(ctx, dispatch)
        assert _sent(held) == _expected(ctx, dispatch, ctx.repo_b, FRESH_FORM)
        assert not _carries_run_a(held)
        _release(ctx, held)
    view = _snapshot(page)
    assert view["run"]["sessionId"] == HISTORY_A and view["requestRun"] is None


# -- dogfood: a Java two-file request in repository B -------------------------------------------------

def _write_java_project(repo):
    for relative, raw in JAVA_PROJECT.items():
        target = repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)


def test_java_two_file_request_in_repository_b_cannot_inherit_the_repository_a_run_control(ctx):
    page = ctx.page
    _write_java_project(ctx.repo_b)
    _open_run_a(ctx, "produced")
    assert json.loads(_page_context(page)) == CONTROL_A
    page.fill("#repoPathInput", str(ctx.repo_b))
    page.fill("textarea[name='query']", JAVA_TWO_FILE_REQUEST)
    for dispatch in (GENERATE, CANDIDATES):
        held = _dispatch(ctx, dispatch)
        assert _sent(held) == _expected(ctx, dispatch, ctx.repo_b, FRESH_FORM)
        assert not _carries_run_a(held)
        assert _continue(ctx, held) == FRESH_FORM_ANSWER
    assert {relative: (ctx.repo_b / relative).read_bytes() for relative in JAVA_PROJECT} == JAVA_PROJECT
    view = _snapshot(page)
    assert view["candidate"] is None and view["requestRun"] is None
    assert ctx.calls == []


# -- the in-flight request and late responses -----------------------------------------------------

def test_in_flight_generate_keeps_its_dispatch_context_and_late_responses_stay_context_bound(ctx):
    page = ctx.page
    _open_run_a(ctx, "produced")
    held = _dispatch(ctx, GENERATE)
    assert _sent(held) == _expected(ctx, GENERATE, ctx.repo_a, _page_context(page))
    page.fill("#repoPathInput", str(ctx.repo_b))
    _fulfill(ctx, held, {"patch": json.dumps(PATCH_A, indent=2), "usage": "late usage for A"})
    view = _snapshot(page)
    assert view["candidate"] is None and view["requestRun"] is None
    assert page.locator("#usage").text_content() != "late usage for A"
    telemetry = page.evaluate("() => WorkbenchState.telemetry()")
    assert (telemetry["lastIgnored"]["kind"], telemetry["lastIgnored"]["reason"]) == ("generate", "context_changed")


# -- the state owner's binding contract ------------------------------------------------------------------

MODULE_CONTRACT = """(seed) => {
    const W = WorkbenchState;
    const out = {};
    const present = view => ("requestRun" in view ? view.requestRun : "missing");
    W.hydrate(seed);
    const view = W.snapshot();
    out.hydrated = { run: view.run, requestRun: present(view), generation: view.contextGeneration };
    const generate = W.begin("generate");
    const candidates = W.begin("candidates");
    const upload = W.begin("upload");
    out.tickets = {
        generate: "requestRun" in generate ? generate.requestRun : "missing",
        candidates: "requestRun" in candidates ? candidates.requestRun : "missing",
        upload: "requestRun" in upload ? upload.requestRun : "missing",
        frozen: Object.isFrozen(generate) && (!generate.requestRun || Object.isFrozen(generate.requestRun)),
    };
    out.kinds = Object.keys(W.KINDS).filter(kind => W.KINDS[kind].requestRun === true);
    W.setRepository("  " + seed.repository + "  ");
    out.sameRepository = present(W.snapshot());
    W.setRepository(seed.repository + "-other");
    out.otherRepository = { requestRun: present(W.snapshot()), run: W.snapshot().run };
    out.inFlight = {
        requestRun: "requestRun" in candidates ? candidates.requestRun : "missing",
        stale: W.settle(candidates, { status: "succeeded", items: [] }),
    };
    W.setRepository(seed.repository);
    out.typedBack = present(W.snapshot());
    out.telemetry = W.telemetry();
    return out;
}"""


@pytest.fixture
def module_page(chromium):
    source = (ROOT / "web/static/workbench_state.js").read_text(encoding="utf-8")
    context = chromium.new_context(service_workers="block")
    context.route("**/*", lambda route: route.abort())
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.set_content("<!doctype html><title>WorkbenchState contract</title>")
    page.add_script_tag(content=source)
    try:
        yield page
    finally:
        context.close()
    assert errors == []


def test_state_owner_binds_a_hydrated_run_to_its_repository_generation_only(module_page):
    run = {"sessionId": HISTORY_A, "repository": "repository-A", "context": _server_context(CONTROL_A)}
    out = module_page.evaluate(MODULE_CONTRACT, {"repository": "repository-A", "run": run})
    expected_run = {**run, "source": "server", "contextGeneration": 0}
    assert out["hydrated"] == {"run": expected_run, "requestRun": expected_run, "generation": 0}
    assert out["tickets"] == {"generate": expected_run, "candidates": expected_run, "upload": None, "frozen": True}
    assert sorted(out["kinds"]) == ["candidates", "generate"]
    assert out["sameRepository"] == expected_run
    # A different repository keeps run A displayed but never eligible, even after typing A back.
    assert out["otherRepository"] == {"requestRun": None, "run": expected_run}
    assert out["typedBack"] is None
    # The in-flight ticket keeps what it captured; its late response is still context_changed.
    assert out["inFlight"]["requestRun"] == expected_run
    assert out["inFlight"]["stale"] == {"accepted": False, "reason": "context_changed"}
    assert out["telemetry"]["lastIgnored"]["reason"] == "context_changed"


def test_state_owner_never_binds_a_run_hydrated_into_another_repository(module_page):
    run = {"sessionId": HISTORY_A, "repository": "repository-A", "context": _server_context(CONTROL_A)}
    out = module_page.evaluate(MODULE_CONTRACT, {"repository": "repository-B", "run": run})
    assert out["hydrated"]["run"] == {**run, "source": "server", "contextGeneration": None}
    assert out["hydrated"]["requestRun"] is None
    assert out["tickets"]["generate"] is None and out["tickets"]["candidates"] is None


def test_state_owner_without_a_run_has_nothing_to_transport(module_page):
    out = module_page.evaluate(MODULE_CONTRACT, {"repository": "repository-A"})
    assert out["hydrated"]["run"] == {"sessionId": "", "repository": "", "source": "none", "contextGeneration": None,
                                      "context": ""}
    assert out["hydrated"]["requestRun"] is None and out["tickets"]["generate"] is None


BOUND = """() => {
    const view = WorkbenchState.snapshot();
    return "requestRun" in view ? view.requestRun && view.requestRun.sessionId : "missing";
}"""
HYDRATE_RUN_A = """() => WorkbenchState.hydrate({
    repository: "repository-A", run: { sessionId: "run-A", repository: "repository-A", context: "{}" },
})"""


def test_an_upload_into_another_repository_ends_the_binding(module_page):
    module_page.evaluate(HYDRATE_RUN_A)
    observed = [module_page.evaluate(BOUND)]
    module_page.evaluate("""() => WorkbenchState.settle(WorkbenchState.begin("upload"),
        { status: "succeeded", repository: "repository-A" })""")
    observed.append(module_page.evaluate(BOUND))
    module_page.evaluate("""() => WorkbenchState.settle(WorkbenchState.begin("upload"),
        { status: "succeeded", repository: "repository-C" })""")
    observed.append(module_page.evaluate(BOUND))
    assert observed == ["run-A", "run-A", None]
    assert module_page.evaluate("() => WorkbenchState.snapshot().run.sessionId") == "run-A"


def test_the_generic_invalidation_hook_ends_the_binding(module_page):
    module_page.evaluate(HYDRATE_RUN_A)
    before = module_page.evaluate(BOUND)
    module_page.evaluate("() => WorkbenchState.invalidate('session_changed')")
    assert [before, module_page.evaluate(BOUND)] == ["run-A", None]
    assert module_page.evaluate("() => WorkbenchState.telemetry().lastInvalidation") == "session_changed"


# -- performance --------------------------------------------------------------------------------------

PERFORMANCE = """() => {
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
    // Each state serializes the Generate Candidates body the way its own handler does:
    // the entry reads the displayed #context text, the post-state reads the ticket.
    const body = () => {
        const bound = "requestRun" in WorkbenchState.snapshot();
        const displayed = bound ? null : document.getElementById("context").innerText;
        const ticket = WorkbenchState.begin("candidates");
        const control = bound ? (ticket.requestRun ? ticket.requestRun.context : "") : displayed;
        return new URLSearchParams({ control, repo_path: ticket.repository, runtime_environment: "auto" }).toString();
    };
    const sample = body();
    return {
        body_length: sample.length,
        snapshot_us: perOperationUs(() => WorkbenchState.snapshot()),
        ticket_and_body_us: perOperationUs(body),
    };
}"""


def test_run_binding_and_request_serialization_overhead_is_negligible(ctx, monkeypatch):
    measured = {}
    for state in ("post", "entry"):
        if state == "entry":
            _serve_entry(ctx, monkeypatch)
        _open_run_a(ctx, "produced")
        before = list(ctx.posts)
        measured[state] = ctx.page.evaluate(PERFORMANCE)
        assert ctx.posts == before
    print("UX_CONTEXT1_PERFORMANCE=" + json.dumps(measured, sort_keys=True))
    # Same-repository continuation serializes a body of the same size in both states.
    assert measured["post"]["body_length"] == measured["entry"]["body_length"]
    assert all(value < 5000 for values in measured.values() for key, value in values.items() if key.endswith("_us"))


# -- PRE: the same scenarios on the exact UX.STATE.1 post-state -----------------------------------------

@DISPATCHES
def test_pre_entry_repository_b_generate_carries_the_repository_a_run_control(entry, dispatch):
    page = entry.page
    _open_run_a(entry, "produced")
    assert page.evaluate("() => 'requestRun' in WorkbenchState.snapshot()") is False
    page.fill("#repoPathInput", str(entry.repo_b))
    held = _dispatch(entry, dispatch)
    sent = dict(_sent(held))
    assert sent["repo_path"] == str(entry.repo_b)
    assert json.loads(sent["control"]) == CONTROL_A and _carries_run_a(held)
    _release(entry, held)


def test_pre_entry_typing_the_old_repository_back_sends_the_run_control_again(entry):
    page = entry.page
    _open_run_a(entry, "produced")
    page.fill("#repoPathInput", str(entry.repo_b))
    page.fill("#repoPathInput", str(entry.repo_a))
    held = _dispatch(entry, GENERATE)
    assert _sent(held) == _expected(entry, GENERATE, entry.repo_a, _page_context(page))
    assert json.loads(_page_context(page)) == CONTROL_A
    _release(entry, held)


def test_pre_entry_restored_repository_b_over_historical_run_a_sends_its_control(entry):
    page = entry.page
    _seed_history(entry)
    _load(entry, f"/session/{HISTORY_A}")
    page.fill("#repoPathInput", str(entry.repo_b))
    _navigate(entry, page.locator("#newSessionLink").click)
    page.go_back(wait_until="load")
    assert page.input_value("#repoPathInput") == str(entry.repo_b)
    held = _dispatch(entry, GENERATE)
    sent = dict(_sent(held))
    assert sent["repo_path"] == str(entry.repo_b) and json.loads(sent["control"]) == CONTROL_A
    _release(entry, held)


def test_pre_entry_java_two_file_request_in_repository_b_inherits_the_repository_a_control(entry):
    page = entry.page
    _write_java_project(entry.repo_b)
    _open_run_a(entry, "produced")
    page.fill("#repoPathInput", str(entry.repo_b))
    page.fill("textarea[name='query']", JAVA_TWO_FILE_REQUEST)
    for dispatch in (GENERATE, CANDIDATES):
        held = _dispatch(entry, dispatch)
        sent = dict(_sent(held))
        assert sent["repo_path"] == str(entry.repo_b)
        assert json.loads(sent["control"]) == CONTROL_A and _carries_run_a(held)
        _release(entry, held)
