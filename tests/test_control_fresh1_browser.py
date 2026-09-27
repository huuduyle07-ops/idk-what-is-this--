"""CONTROL.FRESH.1 real-Chromium integration: the explicit no-prior-run form end to end.

Every scenario drives the shipped page and its production handlers: WorkbenchState
decides whether a Generate ticket has an eligible run, generatePatch and
generateCandidates serialize the request, Chromium captures it exactly as sent, and
the captured request then continues to the real routes and the real
web/control_context.py owner.  Analysis entry points raise if reached, pipeline
stages are recorded, and the providers answer through a deterministic adapter.  The
PRE tests replay the scenarios on the exact UX.CONTEXT.1 post-state: the template
reconstructed from this phase's reversal receipt, and the entry Generate routes
executed from reconstructed web/app.py bytes.  No model, database or external host
is contacted.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qsl

import pytest

from tests.test_control_fresh1 import (
    ENTRY_INVALID_ANSWER, FRESH_ANSWER, FRESH_MESSAGE, FRESH_WIRE, UX_CONTEXT1_FRESH_FORM, _entry_views,
    observe_control_boundary,
)
from tests.test_ux_context1_browser import (  # noqa: F401  (ctx, live and chromium are fixtures)
    CANDIDATES, CONTROL_A, DISPATCHES, GENERATE, HISTORY_A, JAVA_PROJECT, JAVA_TWO_FILE_REQUEST, _carries_run_a,
    _continue, _dispatch, _expected, _navigate, _open_run_a, _page_context, _release, _seed_history,
    _select_history, _sent, _write_java_project, ctx, chromium, live,
)
from tests.test_ux_state1_browser import _flush, _load, _snapshot

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def fresh(ctx, monkeypatch):
    """UX.CONTEXT.1's live page with every stage behind the CONTROL field observable."""
    return observe_control_boundary(ctx, monkeypatch)


def _files(state):
    """Every byte a Generate request could mutate: both repositories and the session store."""
    tracked = {}
    for root in (state.repo_a, state.repo_b):
        for path in sorted(root.rglob("*")):
            if path.is_file():
                tracked[path.as_posix()] = path.read_bytes()
    sessions = state.root / "sessions.json"
    tracked["sessions.json"] = sessions.read_bytes() if sessions.exists() else None
    return tracked


def _answer_fresh(state, held):
    """Continue a captured request to the real backend and prove it stopped at the boundary."""
    before, stages = _files(state), len(state.stages)
    answer = _continue(state, held)
    assert answer == FRESH_ANSWER
    assert state.stages[stages:] == [] and state.analysis == [] and state.prompts == []
    assert _files(state) == before
    return answer


def _shown_outcome(state, dispatch):
    page = state.page
    view = _snapshot(page)
    if dispatch == GENERATE:
        assert page.locator("#answer").text_content() == FRESH_MESSAGE
        assert view["action"]["kind"] == "generate" and view["action"]["status"] == "failed"
        assert view["action"]["message"] == FRESH_MESSAGE
    else:
        assert view["candidates"]["items"] is None and view["candidates"]["message"] == FRESH_MESSAGE
    assert view["candidate"] is None
    assert "Invalid control JSON" not in (page.locator("body").text_content() or "")
    return view


# -- New Session: a genuine no-prior-run page ----------------------------------------------------

@DISPATCHES
def test_new_session_generate_sends_the_explicit_fresh_form_and_stops_at_the_bootstrap_boundary(fresh, dispatch):
    page = fresh.page
    _load(fresh, "/new")
    view = _snapshot(page)
    assert view["run"]["source"] == "none" and view["run"]["sessionId"] == "" and view["requestRun"] is None
    page.fill("#repoPathInput", str(fresh.repo_a))
    page.fill("textarea[name='query']", "make value() return 2 in a.py")
    held = _dispatch(fresh, dispatch)
    assert _sent(held) == _expected(fresh, dispatch, fresh.repo_a, FRESH_WIRE)
    _answer_fresh(fresh, held)
    view = _shown_outcome(fresh, dispatch)
    # No run, session or candidate was invented for the fresh request.
    assert view["run"]["sessionId"] == "" and view["requestRun"] is None
    assert not (fresh.root / "sessions.json").exists()


# -- repository A -> repository B -------------------------------------------------------------------

@DISPATCHES
@pytest.mark.parametrize("how", ["produced", "history"])
def test_repository_b_after_run_a_sends_the_fresh_form_and_never_run_a_control(fresh, dispatch, how):
    page = fresh.page
    _open_run_a(fresh, how)
    run = _snapshot(page)["run"]
    assert json.loads(_page_context(page)) == CONTROL_A and _snapshot(page)["requestRun"] == run
    page.fill("#repoPathInput", str(fresh.repo_b))
    _flush(page)
    held = _dispatch(fresh, dispatch)
    assert _sent(held) == _expected(fresh, dispatch, fresh.repo_b, FRESH_WIRE)
    assert not _carries_run_a(held)
    _answer_fresh(fresh, held)
    view = _shown_outcome(fresh, dispatch)
    # Run A stays displayed for reference and ineligible.
    assert view["run"] == run and view["requestRun"] is None and view["repository"] == str(fresh.repo_b)


# -- same-repository continuation ------------------------------------------------------------------------

@DISPATCHES
def test_same_repository_continuation_transports_run_a_control_into_the_real_pipeline(fresh, dispatch):
    page = fresh.page
    _open_run_a(fresh, "produced")
    (fresh.repo_a / "a.py").write_bytes(b"def value():\n    return 1\n")
    shown = _page_context(page)
    held = _dispatch(fresh, dispatch)
    assert _sent(held) == _expected(fresh, dispatch, fresh.repo_a, shown)
    answer = _continue(fresh, held)
    # The exact run context crossed the real parser into the harness, prompt and provider stages.
    assert "code" not in answer and fresh.analysis == []
    assert fresh.stages[:2] == ["decide_harness_mode", "build_control_prompt"]
    assert len(fresh.prompts) == (1 if dispatch == GENERATE else 3)
    if dispatch == GENERATE:
        assert _snapshot(page)["candidate"]["source"] == "generate"
    else:
        assert len(_snapshot(page)["candidates"]["items"]) == 3


def _serve_ux_context1_post_state(state, monkeypatch):
    """Serve the exact UX.CONTEXT.1 post-state template (the state module is unchanged)."""
    from jinja2 import DictLoader
    from jinja2.utils import LRUCache

    from tests._control_fresh1_maintenance import before_control_fresh1

    template = before_control_fresh1("web/templates/index.html")
    receipt = json.loads((ROOT / "tests/fixtures/ux_context1_reversal.json").read_text(encoding="utf-8"))
    assert hashlib.sha256(template).hexdigest() == receipt["files"]["web/templates/index.html"]["post_sha256"]
    monkeypatch.setattr(state.app, "jinja_loader", DictLoader({"index.html": template.decode("utf-8")}))
    monkeypatch.setattr(state.app.jinja_env, "cache", LRUCache(8))


def test_same_repository_continuation_bodies_are_byte_identical_to_the_ux_context1_post_state(fresh, monkeypatch):
    bodies = {}
    for state in ("post", "entry"):
        if state == "entry":
            _serve_ux_context1_post_state(fresh, monkeypatch)
        for how in ("produced", "history"):
            _open_run_a(fresh, how)
            for dispatch in (GENERATE, CANDIDATES):
                held = _dispatch(fresh, dispatch)
                bodies[(state, how, dispatch[1])] = held.request.post_data
                _release(fresh, held)
    for how in ("produced", "history"):
        for _, path in (GENERATE, CANDIDATES):
            assert bodies[("post", how, path)] == bodies[("entry", how, path)], (how, path)
            assert json.loads(dict(parse_qsl(bodies[("post", how, path)]))["control"]) == CONTROL_A


# -- mismatched history and switching back -----------------------------------------------------------------

def test_mismatched_history_is_viewable_while_generate_starts_fresh_in_the_current_repository(fresh):
    page = fresh.page
    _seed_history(fresh)
    _load(fresh, f"/session/{HISTORY_A}")
    page.fill("#repoPathInput", str(fresh.repo_b))
    _navigate(fresh, page.locator("#newSessionLink").click)
    page.go_back(wait_until="load")
    assert page.input_value("#repoPathInput") == str(fresh.repo_b)
    assert json.loads(_page_context(page)) == CONTROL_A
    for dispatch in (GENERATE, CANDIDATES):
        held = _dispatch(fresh, dispatch)
        assert _sent(held) == _expected(fresh, dispatch, fresh.repo_b, FRESH_WIRE)
        assert not _carries_run_a(held)
        _answer_fresh(fresh, held)
        _shown_outcome(fresh, dispatch)
    view = _snapshot(page)
    assert view["run"]["sessionId"] == HISTORY_A and view["requestRun"] is None


def test_switching_away_and_back_stays_fresh_until_the_run_is_selected_again(fresh):
    page = fresh.page
    _open_run_a(fresh, "produced")
    session_id = _snapshot(page)["run"]["sessionId"]
    page.fill("#repoPathInput", str(fresh.repo_b))
    page.fill("#repoPathInput", str(fresh.repo_a))
    _flush(page)
    for dispatch in (GENERATE, CANDIDATES):
        held = _dispatch(fresh, dispatch)
        assert _sent(held) == _expected(fresh, dispatch, fresh.repo_a, FRESH_WIRE)
        _answer_fresh(fresh, held)
    _select_history(fresh, session_id)
    held = _dispatch(fresh, GENERATE)
    assert _sent(held) == _expected(fresh, GENERATE, fresh.repo_a, _page_context(page))
    assert json.loads(_page_context(page)) == CONTROL_A
    _release(fresh, held)


# -- Java dogfood: regression only ---------------------------------------------------------------------------

def test_fresh_java_two_file_repository_reaches_the_bootstrap_boundary_without_inherited_control(fresh):
    page = fresh.page
    _write_java_project(fresh.repo_b)
    _open_run_a(fresh, "produced")
    page.fill("#repoPathInput", str(fresh.repo_b))
    page.fill("textarea[name='query']", JAVA_TWO_FILE_REQUEST)
    for dispatch in (GENERATE, CANDIDATES):
        held = _dispatch(fresh, dispatch)
        assert _sent(held) == _expected(fresh, dispatch, fresh.repo_b, FRESH_WIRE)
        assert not _carries_run_a(held)
        _answer_fresh(fresh, held)
        _shown_outcome(fresh, dispatch)
    assert {relative: (fresh.repo_b / relative).read_bytes() for relative in JAVA_PROJECT} == JAVA_PROJECT


# -- PRE: the UX.CONTEXT.1 post-state page and routes ---------------------------------------------------------

@pytest.fixture
def entry(fresh, monkeypatch):
    _serve_ux_context1_post_state(fresh, monkeypatch)
    for name, view in _entry_views(fresh).items():
        monkeypatch.setitem(fresh.app.view_functions, name, view)
    return fresh


def _answer_entry_invalid(state, held):
    before = _files(state)
    assert _continue(state, held) == ENTRY_INVALID_ANSWER
    assert state.stages == [] and state.analysis == [] and state.prompts == []
    assert _files(state) == before


@DISPATCHES
def test_pre_entry_new_session_generate_sends_empty_control_and_is_refused_as_invalid_control_json(entry, dispatch):
    page = entry.page
    _load(entry, "/new")
    assert _snapshot(page)["requestRun"] is None
    page.fill("#repoPathInput", str(entry.repo_a))
    held = _dispatch(entry, dispatch)
    assert _sent(held) == _expected(entry, dispatch, entry.repo_a, UX_CONTEXT1_FRESH_FORM)
    _answer_entry_invalid(entry, held)
    shown = page.locator("#answer").text_content() if dispatch == GENERATE else _snapshot(page)["candidates"]["message"]
    assert shown == "Invalid control JSON"


@DISPATCHES
def test_pre_entry_repository_b_generate_after_run_a_is_refused_as_invalid_control_json(entry, dispatch):
    page = entry.page
    _open_run_a(entry, "produced")
    page.fill("#repoPathInput", str(entry.repo_b))
    held = _dispatch(entry, dispatch)
    assert _sent(held) == _expected(entry, dispatch, entry.repo_b, UX_CONTEXT1_FRESH_FORM)
    assert not _carries_run_a(held)
    _answer_entry_invalid(entry, held)
