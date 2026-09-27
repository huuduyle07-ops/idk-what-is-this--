"""CONTROL.FRESH.1: an explicit no-prior-run CONTROL context contract.

Generate Patch and Generate Candidates read one ``control`` form field.  One
owner, web/control_context.py, gives it exactly three meanings:

    a CONTROL object  -> prior CONTROL: continuation input for the unchanged pipeline
    the JSON null     -> fresh start: a typed fresh-bootstrap-required state that
                         stops at the bootstrap boundary (fresh_control_required)
    anything else     -> a structured rejection

A fresh request is not executable yet: creating CONTROL for it is
CONTROL.BOOTSTRAP.1's job, so it reaches no harness, prompt, provider, graph,
retrieval, preflight or mutation here.  These are direct checks of the owner and
of the production routes through the Flask test client; a deterministic provider
adapter answers wherever prior CONTROL legitimately reaches the provider stage.
Real Chromium integration lives in tests/test_control_fresh1_browser.py.  No live
model, database or network is used.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
import statistics
import sys
import time
from pathlib import Path

import pytest

from tests.test_auth_web1 import _tree, configure_offline_web

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
OWNER = "web/control_context.py"

PRIOR, FRESH, REJECTED = "prior_control", "fresh_bootstrap_required", "rejected"
FRESH_CODE, JSON_CODE, REQUEST_CODE = "fresh_control_required", "invalid_control_json", "invalid_control_request"
FRESH_WIRE = "null"
FRESH_MESSAGE = (
    "Fresh start: this request carries no prior CONTROL context, and Generate cannot create CONTROL yet. "
    "Run CONTROL for this repository or select one of its runs, then Generate again."
)
FRESH_ANSWER = {"error": FRESH_MESSAGE, "code": FRESH_CODE, "control_context": FRESH}
# What the UX.CONTEXT.1 page sent without an eligible run, and what the entry backend answered.
UX_CONTEXT1_FRESH_FORM = ""
ENTRY_INVALID_ANSWER = {"error": "Invalid control JSON"}

CONTROL_A = {
    "run_marker": "CONTROL.FRESH.1 CONTROL context of the repository A run",
    "query": "make value() return 2",
    "top_hypothesis": {"symbol": "a.py::value", "confidence": 0.82},
    "patch_intent": {"relative_path": "a.py", "source_snippet": "def value():\n    return 1\n"},
    "related_snippets": [{"file": "a.py", "snippet": "def value():\n    return 1\n"}],
}
# tests/test_harness_modes_web.py posts this partial CONTROL; it must stay continuation input.
PATCH_INTENT_ONLY = {"patch_intent": {"file": "app.py", "source_snippet": "print('old')"}}
NOTHING_LOCALIZED = {"version": "control_v5", "query": "q", "top_hypothesis": None, "hypotheses": []}
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
PROVIDER_REPLY = json.dumps({
    "summary": "CONTROL.FRESH.1 deterministic provider adapter",
    "issues": [],
    "patch_candidate": None,
    "patch_plan": None,
    "confidence": 0.0,
    "needs_escalation": True,
})
ROUTES = ("/generate_patch", "/generate_candidates")
ROUTE_IDS = ["generate_patch", "generate_candidates"]
# Everything that would acquire source, build a graph, retrieve, route, preflight or run the
# agent pipeline.  None of it may run for a request that stops before the pipeline.
ANALYSIS_ENTRY_POINTS = (
    "build_graph_from_repo", "get_cached_graph", "select_entry_nodes", "run_control_structured", "run_control",
    "index_repository", "run_preflight_validation", "retrieve_context", "collect_analysis_evidence",
    "deep_project_understand", "run_agent_web", "safe_route_live_task", "build_related_snippets",
)
PIPELINE_STAGES = ("decide_harness_mode", "build_control_prompt", "extract_json_block",
                   "enforce_control_grounding_on_payload")


def _owner():
    from web import control_context

    return control_context


# -- the owner: one deterministic normalization ------------------------------------------------

def test_the_canonical_fresh_form_is_a_typed_bootstrap_state_not_invalid_control():
    context = _owner().normalize_control_values([FRESH_WIRE])
    assert (context.state, context.control, context.code, context.reason, context.field) == (
        FRESH, None, FRESH_CODE, None, None)
    assert context.response() == FRESH_ANSWER
    assert "Invalid control JSON" not in json.dumps(context.response())
    assert _owner().FRESH_CONTROL_WIRE == FRESH_WIRE


@pytest.mark.parametrize("control", [
    CONTROL_A, PATCH_INTENT_ONLY, NOTHING_LOCALIZED,
    {"hypotheses": [{"symbol": "a.py::value"}], "top_hypothesis": {"symbol": "a.py::value"}, "live_route": None},
], ids=["run_context", "patch_intent_only", "nothing_localized", "nullable_fields"])
@pytest.mark.parametrize("encode", [
    lambda value: json.dumps(value), lambda value: json.dumps(value, indent=2, ensure_ascii=False),
    lambda value: "\n  " + json.dumps(value) + "\r\n",
], ids=["compact", "page_formatted", "whitespace_padded"])
def test_a_control_object_is_prior_continuation_input_parsed_exactly(control, encode):
    context = _owner().normalize_control_values([encode(control)])
    assert (context.state, context.code, context.reason, context.field) == (PRIOR, None, None, None)
    assert context.control == control
    with pytest.raises(ValueError):
        context.response()


def test_the_canonical_control_producer_output_is_prior_continuation_input(tmp_path):
    from core.control_engine import build_control_result

    produced = build_control_result(query="make value() return 2", repo_path=str(tmp_path), entry_nodes=[],
                                    evidence=[], execution_trace="", entry_resolution={})
    text = json.dumps(produced, indent=2, ensure_ascii=False)  # exactly how a control run stores its context
    context = _owner().normalize_control_values([text])
    assert context.state == PRIOR and context.control == json.loads(text)


# field omitted / null / "" / whitespace-only / valid JSON: one canonical fresh form, no accidental equivalence.
MISSING_NULL_EMPTY = [
    pytest.param([], (REJECTED, REQUEST_CODE, "missing", None), id="omitted"),
    pytest.param(["null"], (FRESH, FRESH_CODE, None, None), id="null"),
    pytest.param([""], (REJECTED, JSON_CODE, "empty", None), id="empty"),
    pytest.param(["   "], (REJECTED, JSON_CODE, "whitespace_only", None), id="spaces"),
    pytest.param(["\r\n\t "], (REJECTED, JSON_CODE, "whitespace_only", None), id="blank_lines"),
    pytest.param([" null"], (REJECTED, REQUEST_CODE, "non_canonical_null", None), id="padded_null"),
    pytest.param(["null\n"], (REJECTED, REQUEST_CODE, "non_canonical_null", None), id="null_newline"),
    pytest.param(["NULL"], (REJECTED, JSON_CODE, "malformed_json", None), id="upper_null"),
    pytest.param(["None"], (REJECTED, JSON_CODE, "malformed_json", None), id="python_none"),
    pytest.param(["undefined"], (REJECTED, JSON_CODE, "malformed_json", None), id="undefined"),
    pytest.param(["null", "null"], (REJECTED, REQUEST_CODE, "repeated", None), id="repeated_null"),
    pytest.param(["null", json.dumps(CONTROL_A)], (REJECTED, REQUEST_CODE, "repeated", None), id="null_and_control"),
    pytest.param([json.dumps(CONTROL_A), json.dumps(CONTROL_A)], (REJECTED, REQUEST_CODE, "repeated", None),
                 id="repeated_control"),
    pytest.param([json.dumps(CONTROL_A)], (PRIOR, None, None, None), id="valid_json"),
]
MALFORMED_CONTROL = [
    pytest.param("{", ("malformed_json", None), id="open_brace"),
    pytest.param("hello", ("malformed_json", None), id="hello"),
    pytest.param("{'patch_intent': {}}", ("malformed_json", None), id="python_literal"),
    pytest.param('{"patch_intent": {}', ("malformed_json", None), id="truncated"),
    pytest.param('{"hypotheses": [], "score": NaN}', ("malformed_json", None), id="nan"),
    pytest.param("Infinity", ("malformed_json", None), id="infinity"),
    pytest.param("[]", ("wrong_top_level_type", None), id="array"),
    pytest.param(json.dumps([CONTROL_A]), ("wrong_top_level_type", None), id="array_of_control"),
    pytest.param(json.dumps(json.dumps(CONTROL_A)), ("wrong_top_level_type", None), id="double_encoded"),
    pytest.param("0", ("wrong_top_level_type", None), id="number"),
    pytest.param("true", ("wrong_top_level_type", None), id="true"),
    pytest.param("false", ("wrong_top_level_type", None), id="false"),
    pytest.param("{}", ("missing_required_fields", None), id="empty_object"),
    pytest.param('{"query": "make value() return 2"}', ("missing_required_fields", None), id="query_only"),
    pytest.param('{"run_marker": "x", "version": "control_v5"}', ("missing_required_fields", None), id="no_anchor"),
    pytest.param('{"top_hypothesis": null, "patch_intent": null}', ("missing_required_fields", None),
                 id="null_anchors"),
    pytest.param('{"hypotheses": null, "related_snippets": null}', ("missing_required_fields", None),
                 id="null_lists"),
    pytest.param('{"patch_intent": []}', ("invalid_field_type", "patch_intent"), id="patch_intent_array"),
    pytest.param('{"top_hypothesis": "a.py::value"}', ("invalid_field_type", "top_hypothesis"), id="top_string"),
    pytest.param('{"hypotheses": {}}', ("invalid_field_type", "hypotheses"), id="hypotheses_object"),
    pytest.param('{"hypotheses": ["a.py::value"]}', ("invalid_field_type", "hypotheses"), id="hypothesis_string"),
    pytest.param('{"related_snippets": [1]}', ("invalid_field_type", "related_snippets"), id="snippet_number"),
    pytest.param('{"patch_intent": {}, "live_route": []}', ("invalid_field_type", "live_route"), id="route_array"),
    pytest.param('{"patch_intent": {}, "query": 5}', ("invalid_field_type", "query"), id="query_number"),
    pytest.param('{"patch_intent": {}, "patch_candidate_state": "eligible"}',
                 ("invalid_field_type", "patch_candidate_state"), id="state_string"),
    pytest.param('{"patch_intent": {}, "scout": [1]}', ("invalid_field_type", "scout"), id="scout_array"),
]


@pytest.mark.parametrize(("values", "expected"), MISSING_NULL_EMPTY)
def test_missing_null_empty_whitespace_and_valid_json_are_pinned_exactly(values, expected):
    context = _owner().normalize_control_values(values)
    assert (context.state, context.code, context.reason, context.field) == expected
    if context.state == REJECTED:
        answer = context.response()
        assert answer["code"] == expected[1] and answer["reason"] == expected[2]
        assert answer != FRESH_ANSWER and context.control is None


@pytest.mark.parametrize(("text", "expected"), MALFORMED_CONTROL)
def test_malformed_control_is_a_structured_invalid_control_rejection(text, expected):
    reason, field = expected
    context = _owner().normalize_control_values([text])
    assert (context.state, context.control, context.code, context.reason, context.field) == (
        REJECTED, None, JSON_CODE, reason, field)
    answer = {"error": "Invalid control JSON", "code": JSON_CODE, "reason": reason}
    if field:
        answer["field"] = field
    assert context.response() == answer


def test_normalization_is_deterministic_and_answers_are_independent_copies():
    owner = _owner()
    for values in (["null"], [""], ["{"], [json.dumps(CONTROL_A)], [], ["null", "null"]):
        first, second = owner.normalize_control_values(values), owner.normalize_control_values(list(values))
        assert first == second
    fresh = owner.normalize_control_values(["null"])
    fresh.response()["error"] = "mutated"
    assert fresh.response() == FRESH_ANSWER
    prior = owner.normalize_control_values([json.dumps(CONTROL_A)])
    prior.control["query"] = "mutated"
    assert owner.normalize_control_values([json.dumps(CONTROL_A)]).control == CONTROL_A


def test_the_owner_reads_the_form_field_list_and_nothing_else():
    class Form:
        def __init__(self, values):
            self.values, self.asked = values, []

        def getlist(self, name):
            self.asked.append(name)
            return list(self.values)

    form = Form(["null"])
    assert _owner().control_context_from_form(form).state == FRESH
    assert form.asked == ["control"]


def test_the_owner_is_pure_standard_library_code():
    tree = ast.parse((ROOT / OWNER).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    assert imported <= {"__future__", "dataclasses", "json", "typing", "collections"}
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert not names & {"open", "Path", "os", "subprocess", "socket", "request", "print", "time", "random"}


# -- the production routes ------------------------------------------------------------------------

def observe_control_boundary(state, monkeypatch):
    """Make every stage behind the CONTROL field observable on an offline app state.

    Analysis entry points raise if reached, pipeline stages are recorded and still
    run, and the providers answer through a deterministic adapter.
    """
    wa = state.wa
    state.stages, state.analysis, state.prompts = [], [], []

    def forbidden(name):
        def call(*args, **kwargs):
            state.analysis.append(name)
            raise AssertionError(f"CONTROL.FRESH.1: {name} is past the CONTROL boundary")
        return call

    for module in tuple(sys.modules.values()):
        module_name = getattr(module, "__name__", "") or ""
        if module_name.startswith(("web.", "core.", "graph.", "reasoning.", "agents.")) and module_name != "web.app":
            for name in ANALYSIS_ENTRY_POINTS:
                if callable(getattr(module, name, None)):
                    monkeypatch.setattr(module, name, forbidden(name))
    for name in ANALYSIS_ENTRY_POINTS:
        if callable(getattr(wa, name, None)):
            monkeypatch.setattr(wa, name, forbidden(name))

    def recorded(name, original):
        def call(*args, **kwargs):
            state.stages.append(name)
            return original(*args, **kwargs)
        return call

    for name in PIPELINE_STAGES:
        monkeypatch.setattr(wa, name, recorded(name, getattr(wa, name)))

    def provider(prompt, *args, **kwargs):
        state.prompts.append(prompt)
        return PROVIDER_REPLY

    monkeypatch.setattr(wa, "run_gemini_request", provider)
    monkeypatch.setattr(wa, "run_deepseek_review", provider)
    return state


@pytest.fixture
def offline(tmp_path, monkeypatch):
    """The production app offline, with every stage behind the CONTROL field observable."""
    state = observe_control_boundary(configure_offline_web(tmp_path, monkeypatch), monkeypatch)
    state.client = state.wa.app.test_client()
    yield state
    assert state.calls == []  # the raising provider installed by configure_offline_web never ran


def _body(route, repo, control=None, *, omit=False):
    """The exact field order each production handler sends."""
    if route == "/generate_patch":
        body = [("repo_path", str(repo)), ("runtime_environment", "auto"), ("control", control),
                ("anti_lesson_control_requested", "false")]
    else:
        body = [("control", control), ("repo_path", str(repo)), ("runtime_environment", "auto")]
    if omit:
        body = [item for item in body if item[0] != "control"]
    values: dict[str, list[str]] = {}
    for key, value in body:
        values.setdefault(key, []).extend(value if isinstance(value, list) else [value])
    return values


def _post(state, route, body):
    before = _tree(state.root)
    response = state.client.post(route, data=body)
    assert _tree(state.root) == before, "a Generate request mutated files"
    return response


@pytest.mark.parametrize("route", ROUTES, ids=ROUTE_IDS)
def test_fresh_generate_stops_at_the_bootstrap_boundary_without_model_graph_or_mutation(offline, route):
    response = _post(offline, route, _body(route, offline.repo, FRESH_WIRE))
    assert response.status_code == 200 and response.is_json
    assert response.get_json() == FRESH_ANSWER
    assert "Invalid control JSON" not in response.get_data(as_text=True)
    assert offline.stages == [] and offline.analysis == [] and offline.prompts == []


@pytest.mark.parametrize("route", ROUTES, ids=ROUTE_IDS)
@pytest.mark.parametrize(("values", "expected"), [
    pytest.param(None, (REQUEST_CODE, "missing"), id="omitted"),
    pytest.param(["null", json.dumps(CONTROL_A)], (REQUEST_CODE, "repeated"), id="repeated"),
    pytest.param([" null"], (REQUEST_CODE, "non_canonical_null"), id="padded_null"),
    pytest.param([""], (JSON_CODE, "empty"), id="empty"),
    pytest.param(["  "], (JSON_CODE, "whitespace_only"), id="whitespace"),
    pytest.param(["{"], (JSON_CODE, "malformed_json"), id="malformed"),
    pytest.param(["hello"], (JSON_CODE, "malformed_json"), id="hello"),
    pytest.param(["[]"], (JSON_CODE, "wrong_top_level_type"), id="array"),
    pytest.param(["{}"], (JSON_CODE, "missing_required_fields"), id="empty_object"),
    pytest.param(['{"patch_intent": []}'], (JSON_CODE, "invalid_field_type"), id="invalid_field"),
])
def test_malformed_or_ambiguous_control_is_rejected_structurally_before_any_stage(offline, route, values, expected):
    body = _body(route, offline.repo, omit=True) if values is None else _body(route, offline.repo, values)
    response = _post(offline, route, body)
    assert response.status_code == 200 and response.is_json
    answer = response.get_json()
    assert (answer["code"], answer["reason"]) == expected
    assert answer["error"] == ("Invalid control JSON" if expected[0] == JSON_CODE else "Invalid control request")
    assert answer.get("control_context") is None and FRESH_MESSAGE not in answer["error"]
    assert offline.stages == [] and offline.analysis == [] and offline.prompts == []


def _entry_views(state):
    """The UX.CONTEXT.1-era Generate routes, executed from their reconstructed entry bytes."""
    from tests._control_fresh1_maintenance import before_control_fresh1

    tree = ast.parse(before_control_fresh1("web/app.py").decode("utf-8"))
    namespace = dict(state.wa.__dict__)  # after every adapter above is installed
    views = {}
    for name in ("generate_patch", "generate_candidates"):
        node = next(item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name == name)
        node.decorator_list = []
        exec(compile(ast.Module(body=[node], type_ignores=[]), f"_control_fresh1_entry_{name}", "exec"), namespace)
        views[name] = namespace[name]
    return views


def _use_entry_routes(state, monkeypatch):
    for name, view in _entry_views(state).items():
        monkeypatch.setitem(state.app.view_functions, name, view)


def _continue_prior(state, route):
    (state.repo / "a.py").write_bytes(b"def value():\n    return 1\n")
    stages, prompts = len(state.stages), len(state.prompts)
    response = state.client.post(route, data=_body(route, state.repo, json.dumps(CONTROL_A, indent=2)))
    assert response.status_code == 200 and response.is_json
    return response.get_json(), state.stages[stages:], state.prompts[prompts:]


@pytest.mark.parametrize("route", ROUTES, ids=ROUTE_IDS)
def test_prior_control_continues_into_harness_prompt_and_deterministic_provider(offline, route):
    answer, stages, prompts = _continue_prior(offline, route)
    assert "code" not in answer and "control_context" not in answer
    providers = 1 if route == "/generate_patch" else 3
    assert len(prompts) == providers and offline.analysis == []
    assert stages[:2] == ["decide_harness_mode", "build_control_prompt"]
    assert stages.count("extract_json_block") == providers
    if route == "/generate_patch":
        assert json.loads(answer["patch"]) == json.loads(PROVIDER_REPLY)
        assert set(answer) == {"patch", "usage", "anti_lesson_control"}
    else:
        assert [item["name"] for item in answer["candidates"]] == ["gemini_default", "gemini_minimal",
                                                                    "deepseek_review"]
        assert set(answer) == {"candidates", "usage"}


@pytest.mark.parametrize("route", ROUTES, ids=ROUTE_IDS)
def test_prior_control_continuation_is_identical_to_the_entry_routes(offline, monkeypatch, route):
    post = _continue_prior(offline, route)
    _use_entry_routes(offline, monkeypatch)
    entry = _continue_prior(offline, route)
    # Same answer, same pipeline stages and byte-identical provider prompts.
    assert post == entry


# -- PRE: the entry routes on the same requests ---------------------------------------------------

@pytest.mark.parametrize("route", ROUTES, ids=ROUTE_IDS)
def test_pre_entry_routes_answer_the_no_prior_run_form_with_invalid_control_json(offline, monkeypatch, route):
    _use_entry_routes(offline, monkeypatch)
    response = _post(offline, route, _body(route, offline.repo, UX_CONTEXT1_FRESH_FORM))
    assert response.get_json() == ENTRY_INVALID_ANSWER
    assert offline.stages == [] and offline.analysis == [] and offline.prompts == []


@pytest.mark.parametrize("route", ROUTES, ids=ROUTE_IDS)
@pytest.mark.parametrize("text", ["null", "[]", "{}", '{"hello": 1}'])
def test_pre_entry_routes_let_null_and_non_control_json_through_to_the_harness(offline, monkeypatch, route, text):
    _use_entry_routes(offline, monkeypatch)
    answer = _post(offline, route, _body(route, offline.repo, text)).get_json()
    # No typed state and no rejection: the harness gate had to refuse for lack of source.
    assert answer["harness_mode"] == "source_missing" and "code" not in answer
    assert offline.stages == ["decide_harness_mode"] and offline.prompts == []


def test_pre_entry_generate_candidates_without_a_control_field_is_an_unstructured_400(offline, monkeypatch):
    _use_entry_routes(offline, monkeypatch)
    response = _post(offline, "/generate_candidates", _body("/generate_candidates", offline.repo, omit=True))
    assert response.status_code == 400 and not response.is_json


# -- Java dogfood: regression only --------------------------------------------------------------------

@pytest.mark.parametrize("route", ROUTES, ids=ROUTE_IDS)
def test_fresh_java_two_file_repository_reaches_the_bootstrap_boundary_without_inherited_control(offline, route):
    java = offline.root / "java_repo"
    for relative, raw in JAVA_PROJECT.items():
        (java / relative).parent.mkdir(parents=True, exist_ok=True)
        (java / relative).write_bytes(raw)
    answer = _post(offline, route, _body(route, java, FRESH_WIRE)).get_json()
    assert answer == FRESH_ANSWER
    assert offline.stages == [] and offline.analysis == [] and offline.prompts == []
    assert {relative: (java / relative).read_bytes() for relative in JAVA_PROJECT} == JAVA_PROJECT


# -- one owner, contained production change ------------------------------------------------------------

TEMPLATE = "web/templates/index.html"
FRESH_TICKET_CONTROL = "control: ticket.requestRun ? ticket.requestRun.context : JSON.stringify(null),"
UX_CONTEXT1_TICKET_CONTROL = 'control: ticket.requestRun ? ticket.requestRun.context : "",'
FRESH_COMMENT = "    // CONTROL.FRESH.1: that form is the explicit JSON null, never an empty value.\r\n"
PIPELINE_TAIL = "    harness_block = _patch_generation_harness_block("
EXISTING_FILES_CHANGED = (
    "web/app.py",
    "web/templates/index.html",
    "docs/roadmap/phase_registry.json",
    "tests/test_phase_registry.py",
    "tests/test_phase_picker.py",
    "tests/_ux_context1_maintenance.py",
    "tests/test_ux_context1.py",
    "tests/test_ux_context1_browser.py",
    "tests/test_ux_state1.py",
    "tests/test_auth_web1.py",
    "tests/test_auth_web_read1.py",
)
NEW_FILES = (
    "web/control_context.py",
    "tests/test_control_fresh1.py",
    "tests/test_control_fresh1_browser.py",
    "tests/_control_fresh1_maintenance.py",
    "tests/fixtures/control_fresh1_reversal.json",
    "tests/fixtures/control_fresh1_frozen_boundaries.json",
    "tests/fixtures/control_fresh1_completion.json",
    "docs/designs/2026-09-18-explicit-no-prior-run-control-context.md",
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _entry_bytes(relative: str) -> bytes:
    from tests._control_fresh1_maintenance import before_control_fresh1

    return before_control_fresh1(relative)


def _post_state(relative: str) -> bytes:
    # CONTROL.FRESH.1's own post-state: later CONTROL.BOOTSTRAP.1 edits are reversed first.
    from tests._control_bootstrap1_maintenance import before_control_bootstrap1

    return before_control_bootstrap1(relative)


def _definitions(raw: bytes) -> tuple[dict[str, str], list[str]]:
    definitions: dict[str, list[str]] = {}
    statements: list[str] = []
    for node in ast.parse(raw.decode("utf-8")).body:
        dump = ast.dump(node, include_attributes=False)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            definitions.setdefault(node.name, []).append(_sha(dump.encode()))
        else:
            statements.append(dump)
    return {name: "|".join(values) for name, values in definitions.items()}, statements


def _route(raw: bytes, name: str) -> str:
    source = raw.decode("utf-8")
    node = next(item for item in ast.parse(source).body if isinstance(item, ast.FunctionDef) and item.name == name)
    return ast.get_source_segment(source, node)


def test_web_app_changes_only_the_generate_routes_control_parse_and_one_owner_import():
    entry, post = _entry_bytes("web/app.py"), _post_state("web/app.py")
    old, old_statements = _definitions(entry)
    new, new_statements = _definitions(post)
    assert set(old) == set(new)
    assert {name for name in old if old[name] != new[name]} == {"generate_patch", "generate_candidates"}
    assert [statement for statement in old_statements if statement not in new_statements] == []
    added = [statement for statement in new_statements if statement not in old_statements]
    assert len(added) == 1
    assert added[0].startswith("ImportFrom(module='web.control_context', names=[alias(name='control_context_from_form')]")
    for name in ("generate_patch", "generate_candidates"):
        before, after = _route(entry, name), _route(post, name)
        assert 'return {"error": "Invalid control JSON"}' in before and "json.loads(control_json)" in before
        # Everything from the harness gate on (prompt, provider, grounding, answer) is byte-identical.
        assert after[after.index(PIPELINE_TAIL):] == before[before.index(PIPELINE_TAIL):], name
        assert after.count("control_context_from_form(request.form)") == 1
        assert after.index("control_context_from_form(") < after.index(PIPELINE_TAIL)
        assert "json.loads" not in after and "Invalid control" not in after and '"control"' not in after


def test_no_other_production_code_reads_or_answers_the_control_field():
    reader = re.compile(r"form(?:\.get(?:list)?\(|\[)\s*['\"]control['\"]")
    for top in ("web", "core", "agents", "patching", "reasoning", "graph", "policy", "database", "cli"):
        for path in (ROOT / top).rglob("*.py"):
            relative = path.relative_to(ROOT).as_posix()
            if relative == OWNER:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            assert "Invalid control JSON" not in text and not reader.search(text), relative
    owner = (ROOT / OWNER).read_text(encoding="utf-8")
    assert owner.count('"Invalid control JSON"') == 1 and owner.count("form.getlist(CONTROL_FIELD)") == 1


def test_generate_handlers_send_json_null_only_when_the_ticket_has_no_eligible_run():
    from tests.test_ux_state1 import _function

    template = _post_state(TEMPLATE).decode("utf-8")
    for name, kind in (("generatePatch", "generate"), ("generateCandidates", "candidates")):
        body = _function(template, f"function {name}(")
        assert body.count(FRESH_TICKET_CONTROL) == 1 and UX_CONTEXT1_TICKET_CONTROL not in body, name
        assert body.index(f'WorkbenchState.begin("{kind}")') < body.index("new URLSearchParams("), name
        # Freshness comes from the ticket alone, never from displayed text.
        assert 'getElementById("context")' not in body and "#context" not in body, name
    # The page is UX.CONTEXT.1's post-state except two serialization expressions and one comment.
    assert template.count(FRESH_TICKET_CONTROL) == 2 and template.count(FRESH_COMMENT) == 1
    restored = template.replace(FRESH_TICKET_CONTROL, UX_CONTEXT1_TICKET_CONTROL).replace(FRESH_COMMENT, "")
    assert restored.encode("utf-8") == _entry_bytes(TEMPLATE)


def test_the_workbench_state_owner_is_byte_identical_to_ux_context1():
    receipt = json.loads((FIXTURES / "ux_context1_reversal.json").read_text(encoding="utf-8"))
    module = _post_state("web/static/workbench_state.js")
    assert _sha(module) == receipt["files"]["web/static/workbench_state.js"]["post_sha256"]


def test_normalization_overhead_is_microseconds():
    owner = _owner()
    control = {
        **CONTROL_A,
        "hypotheses": [{"symbol": f"m{index}.py::f{index}", "reasons": ["x" * 40] * 3} for index in range(200)],
        "related_snippets": [{"file": f"m{index}.py", "snippet": "def f():\n    pass\n" * 20} for index in range(40)],
    }
    text = json.dumps(control, indent=2)

    def per_call_us(operation, size=50, batches=7):
        samples = []
        for _ in range(batches):
            started = time.perf_counter()
            for _ in range(size):
                operation()
            samples.append((time.perf_counter() - started) / size * 1e6)
        return statistics.median(samples)

    measured = {
        "control_bytes": len(text),
        "fresh_us": per_call_us(lambda: owner.normalize_control_values([FRESH_WIRE])),
        "malformed_us": per_call_us(lambda: owner.normalize_control_values(["{"])),
        "prior_us": per_call_us(lambda: owner.normalize_control_values([text])),
        "json_loads_us": per_call_us(lambda: json.loads(text)),
    }
    print("CONTROL_FRESH1_PERFORMANCE=" + json.dumps(measured, sort_keys=True))
    assert measured["fresh_us"] < 500 and measured["malformed_us"] < 2000
    assert measured["prior_us"] < measured["json_loads_us"] * 3 + 5000


# -- registry, reversal, frozen boundaries and completion ---------------------------------------------------

def test_registry_has_one_complete_control_fresh1_phase_directly_after_ux_context1():
    from core.phase_picker import pick_phase_candidates
    from core.phase_registry import load_phase_registry, validate_phase_registry

    registry = load_phase_registry(str(ROOT / "docs/roadmap/phase_registry.json"))
    assert validate_phase_registry(registry)["is_valid"]
    phases = [phase for phase in registry["phases"] if phase["phase_id"] == "CONTROL.FRESH.1"]
    assert len(phases) == 1
    phase = phases[0]
    assert phase["track"] == "CONTROL" and phase["status"] == "complete"
    assert phase["prerequisites"] == ["UX.CONTEXT.1"]
    ids = [entry["phase_id"] for entry in registry["phases"]]
    assert ids.index("CONTROL.FRESH.1") == ids.index("UX.CONTEXT.1") + 1
    assert phase["network_allowed"] is False and phase["model_calls_allowed"] is False
    assert phase["human_approval_required"] is True and phase["merge_allowed"] is False
    assert phase["budget_tier"] == "local_only" and phase["writes_real_repo"] is True
    assert {"web/control_context.py", "web/app.py", TEMPLATE} <= set(phase["allowed_files"])
    for frozen in ("core/", "patching/", "agents/", "web/routes/", "web/runner.py", "web/session_store.py",
                   "web/static/workbench_state.js", "web/static/request_integrity.js", "web/static/safe_content.js"):
        assert frozen in phase["forbidden_files"], frozen
    notes = " ".join(phase["notes"]) + phase["summary"]
    assert "CONTROL.BOOTSTRAP.1 is required" in notes and "not executable" in notes
    assert pick_phase_candidates(registry)["top_recommendation"]["phase_id"] == "DOGFOOD.1B"


def test_reversal_receipt_reconstructs_every_entry_file_on_the_ux_context1_post_state():
    receipt = json.loads((FIXTURES / "control_fresh1_reversal.json").read_text(encoding="utf-8"))
    assert receipt["phase"] == "CONTROL.FRESH.1"
    assert set(receipt["files"]) == set(EXISTING_FILES_CHANGED)
    anchors: dict[str, str] = {}
    for name, key in (("ux_state1_completion.json", "source_sha256"),
                      ("ux_context1_frozen_boundaries.json", "sha256"),
                      ("ux_context1_completion.json", "source_sha256")):
        anchors.update(json.loads((FIXTURES / name).read_text(encoding="utf-8"))[key])  # newest pin wins
    for relative, record in receipt["files"].items():
        restored = _entry_bytes(relative)
        # Each entry digest is an independent UX.CONTEXT.1-era pin, not a digest this phase chose.
        assert _sha(restored) == record["entry_sha256"] == anchors[relative], relative
        assert _sha(_post_state(relative)) == record["post_sha256"], relative


def test_frozen_phase_boundaries_are_byte_exact():
    manifest = json.loads((FIXTURES / "control_fresh1_frozen_boundaries.json").read_text(encoding="utf-8"))
    assert manifest["phase"] == "CONTROL.FRESH.1"
    for relative, digest in manifest["sha256"].items():
        assert _sha(_post_state(relative)) == digest, relative
    groups = manifest["groups"]
    for group in ("UX.CONTEXT.1", "UX.STATE.1", "AUTH.WEB.1", "AUTH.WEB.READ.1", "SEC.UI.1", "DATA.UNDO.1",
                  "EXEC.PLAN.1", "AUTH.DREAM.1", "DATA.ROLLBACK.1", "Track_A", "control_pipeline", "backend_web",
                  "static_assets", "reversal_chain", "audit"):
        assert groups[group] and set(groups[group]) <= set(manifest["sha256"]), group
    assert {"web/static/workbench_state.js", "web/static/request_integrity.js", "web/session_store.py",
            "web/routes/patch_routes.py", "web/runner.py", "core/control_engine.py", "core/harness_modes.py",
            "core/json_utils.py", "agents/gemini_client.py", "agents/deepseek_client.py", "agents/ollama_client.py",
            "core/dream_review_binding.py", "core/human_apply_authorization.py", "core/undo_backup.py",
            "core/pipeline.py", "patching/patch_gates.py", "tests/test_harness_modes_web.py"} <= set(manifest["sha256"])
    assert not set(manifest["sha256"]) & set(EXISTING_FILES_CHANGED + NEW_FILES)
    # Everything UX.CONTEXT.1 froze and this phase did not touch still carries UX.CONTEXT.1's own digest.
    previous = json.loads((FIXTURES / "ux_context1_frozen_boundaries.json").read_text(encoding="utf-8"))["sha256"]
    for relative, digest in previous.items():
        if relative not in EXISTING_FILES_CHANGED:
            assert manifest["sha256"][relative] == digest, relative


def test_completion_receipt_pins_every_phase_source_and_records_the_bootstrap_boundary():
    receipt = json.loads((FIXTURES / "control_fresh1_completion.json").read_text(encoding="utf-8"))
    assert receipt["phase"] == "CONTROL.FRESH.1"
    assert receipt["fresh_generate_executable"] is False
    assert receipt["required_follow_up"] == ["CONTROL.BOOTSTRAP.1"]
    assert receipt["model_calls"] == 0 and receipt["external_network_requests"] == 0
    assert set(receipt["frozen_production_deltas"].values()) == {0}
    assert set(receipt["existing_files_changed"]) == set(EXISTING_FILES_CHANGED)
    assert set(receipt["new_files"]) == set(NEW_FILES)
    expected = set(EXISTING_FILES_CHANGED + NEW_FILES)
    expected.remove("tests/fixtures/control_fresh1_completion.json")
    assert set(receipt["source_sha256"]) == expected
    for relative, digest in receipt["source_sha256"].items():
        assert _sha(_post_state(relative)) == digest, relative
