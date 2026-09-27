"""WAITER.LIVE.1 — live task-shape routing and change-need separation.

Four things are proved here.

The **routing matrix**: an architecture comparison answers, a claimed defect
localizes, an explicit feature request plans, and an unreadable order asks.  The
two black-box field failures are pinned as named regressions — the deepseek
comparison that spent twenty-six minutes indexing on its way to "cannot safely
generate patch", and the five-operation feature plan that was discarded for
failing to prove a defect it was never claiming.

The **separation**: ``change_requested``, ``defect_established`` and
``write_authority`` are three facts, not one.  A feature has the first without
the second; nothing on this path has the third.

The **boundary**: routing calls no model, opens no socket, reads no file and
builds no index, and it happens before CONTROL.

The **preservation**: CONTROL.SAFETY.LIVE.1's guarantees survive intact.  Rank
still cannot mint a defect, a false bug report still gets no patch eligibility,
and inconclusive validation still establishes nothing.
"""

from __future__ import annotations

import builtins
import json

import pytest

from core.analysis_evidence import (
    MAX_EVIDENCE_FILES,
    ROLE_PACKAGE_MANIFEST,
    ROLE_PROJECT_DOCUMENT,
    ROLE_REQUESTED_PATH,
    build_analysis_answer_prompt,
    collect_analysis_evidence,
    select_analysis_paths,
)
from core.live_task_routing import (
    GROUNDING_ACQUIRED_SOURCE_QUOTE,
    GROUNDING_CONTROL_EXACT_SOURCE,
    GROUNDING_NONE,
    WORKFLOW_ANALYSIS_ANSWER,
    WORKFLOW_CLARIFICATION,
    WORKFLOW_DEFECT_REPAIR,
    WORKFLOW_EXPLICIT_CHANGE,
    LiveRouteReceipt,
    render_live_route_json,
    route_allows_patch_localization,
    route_change_need_source,
    route_is_explicit_change,
    route_is_read_only,
    route_live_task,
    safe_route_live_task,
)
from core.live_task_shape import (
    CHANGE_NEED_EXPLICIT_USER_REQUEST,
    CHANGE_NEED_GROUNDED_DEFECT,
    CHANGE_NEED_NONE,
    CHANGE_NEED_UNRESOLVED,
    LIVE_TASK_SHAPES,
    REASON_MIXED_OBLIGATIONS,
    REASON_NO_DETERMINABLE_OBLIGATION,
    SHAPE_ANALYSIS_ONLY,
    SHAPE_DEFECT_REPAIR,
    SHAPE_EXPLICIT_CHANGE,
    SHAPE_NEEDS_CLARIFICATION,
    derive_live_task_shape,
    live_shape_from_waiter_family,
    split_obligations,
)


ARCHITECTURE_COMPARISON = (
    "Compare repository A and repository B on:\n"
    "  agent loop\n"
    "  extension/plugin model\n"
    "  retrieval/context system\n"
    "Ground the answer in files actually read."
)
DEEPSEEK_FIELD_PROMPT = "Compare deepseek-harness and C.A.T.T.U.S architecture."
FEATURE_FIELD_PROMPT = "Add task priority support across model/store/CLI."
CALC_DEFECT_PROMPT = "add(2,2) returns 0 / test fails"
AMBIGUOUS_PROMPT = "Improve the agent."
MIXED_PROMPT = "Explain how validation works, then fix the pytest detection bug."


# ── 1. deterministic task-shape units ─────────────────────────────────────────

@pytest.mark.parametrize(
    ("prompt", "expected"),
    [
        (DEEPSEEK_FIELD_PROMPT, SHAPE_ANALYSIS_ONLY),
        (ARCHITECTURE_COMPARISON, SHAPE_ANALYSIS_ONLY),
        ("Explain how the retrieval subsystem works.", SHAPE_ANALYSIS_ONLY),
        ("Review how this repository handles validation.", SHAPE_ANALYSIS_ONLY),
        ("What does the control engine do?", SHAPE_ANALYSIS_ONLY),
        (FEATURE_FIELD_PROMPT, SHAPE_EXPLICIT_CHANGE),
        ("Add task priority support.", SHAPE_EXPLICIT_CHANGE),
        ("refactor the executor", SHAPE_EXPLICIT_CHANGE),
        ("rename the validation API", SHAPE_EXPLICIT_CHANGE),
        ("migrate the store to sqlite", SHAPE_EXPLICIT_CHANGE),
        ("add a CLI option for json output", SHAPE_EXPLICIT_CHANGE),
        (CALC_DEFECT_PROMPT, SHAPE_DEFECT_REPAIR),
        ("this returns the wrong value", SHAPE_DEFECT_REPAIR),
        ("tests fail when the repo has no pyproject", SHAPE_DEFECT_REPAIR),
        ("indentation detector returns wrong style", SHAPE_DEFECT_REPAIR),
        ("fix this bug", SHAPE_DEFECT_REPAIR),
        (AMBIGUOUS_PROMPT, SHAPE_NEEDS_CLARIFICATION),
        (MIXED_PROMPT, SHAPE_NEEDS_CLARIFICATION),
        ("", SHAPE_NEEDS_CLARIFICATION),
    ],
)
def test_live_task_shape_matrix(prompt, expected):
    shape = derive_live_task_shape(prompt, repository_available=True)
    assert shape.task_shape == expected


def test_task_shape_derivation_is_deterministic():
    first = derive_live_task_shape(ARCHITECTURE_COMPARISON, repository_available=True)
    second = derive_live_task_shape(ARCHITECTURE_COMPARISON, repository_available=True)
    assert first.as_dict() == second.as_dict()


def test_call_position_does_not_read_a_defect_report_as_a_feature_request():
    """``add(2,2)`` names a function; it does not ask for one to be added."""
    shape = derive_live_task_shape(CALC_DEFECT_PROMPT, repository_available=True)
    assert shape.task_shape == SHAPE_DEFECT_REPAIR
    assert shape.markers.change_request_present is False


@pytest.mark.parametrize(
    "prompt",
    [
        "Change app.py: make advance(value) return value + 2 instead of value + 1.",
        "  Please change advance in app.py to return value + 2.",
        "Could you please update advance in app.py to return value + 2?",
        "I want you to modify advance in app.py to return value + 2.",
        "Edit app.py so advance returns value + 2.",
        "In app.py, adjust advance to return value + 2.",
        "Hãy thay đổi app.py để advance trả về value + 2.",
        "Vui lòng cập nhật app.py để advance trả về value + 2.",
    ],
)
def test_equivalent_change_requests_select_change_without_granting_authority(prompt):
    route = route_live_task(prompt, repository_available=True)

    assert route.selected_workflow == WORKFLOW_EXPLICIT_CHANGE
    assert route.change_requested is True
    assert route.write_authority is False


@pytest.mark.parametrize(
    "prompt",
    [
        "Explain how to change app.py.",
        "Describe the update to app.py.",
        "What would change if advance returned value + 2?",
        "Do not change app.py.",
        "Don't modify or update any files. Explain advance in app.py.",
        "Explain app.py without editing it. Do not edit files.",
        "Explain app.py. Never implement changes.",
        "Explain the change(value) function in app.py.",
        "Review the message: 'change app.py'.",
        "Đừng thay đổi app.py. Giải thích advance.",
    ],
)
def test_change_mentions_and_prohibitions_remain_read_only(prompt):
    route = route_live_task(prompt, repository_available=True)

    assert route_is_read_only(route.as_dict())
    assert route.change_requested is False
    assert route.patch_localization_allowed is False
    assert route.write_authority is False


def test_negative_scope_does_not_erase_a_separate_positive_change_request():
    prompt = "Update app.py to return value + 2, but do not change database/schema.py."
    shape = derive_live_task_shape(prompt, repository_available=True)

    assert shape.task_shape == SHAPE_EXPLICIT_CHANGE
    assert shape.markers.explicit_changes == ("Update",)
    assert any(
        "database/schema.py" in item.text
        for item in shape.contract.explicit_evidence.constraints
        if item.kind == "prohibition"
    )


def test_every_live_shape_is_in_the_bounded_vocabulary():
    for prompt in (
        DEEPSEEK_FIELD_PROMPT,
        FEATURE_FIELD_PROMPT,
        CALC_DEFECT_PROMPT,
        AMBIGUOUS_PROMPT,
    ):
        assert derive_live_task_shape(prompt).task_shape in LIVE_TASK_SHAPES


# ── 2. reuse of the frozen WAITER.1 / INPUT.1 contracts ───────────────────────

def test_live_adapter_produces_a_real_input_1_contract():
    shape = derive_live_task_shape(DEEPSEEK_FIELD_PROMPT, repository_available=True)
    contract = shape.contract

    assert contract is not None
    # INPUT.1's lossless invariant: the raw request survives verbatim.
    assert contract.raw_request.text == DEEPSEEK_FIELD_PROMPT
    assert contract.preservation.passed is True
    assert contract.routing_allowed is True


def test_live_adapter_reuses_waiter_1_shape_and_capability_derivation():
    shape = derive_live_task_shape(DEEPSEEK_FIELD_PROMPT, repository_available=True)

    assert shape.waiter_task_shape is not None
    assert shape.waiter_task_shape.task_family == "comparative_analysis"
    assert shape.waiter_task_shape.change_shape == "no_change"
    assert shape.capability_requirements is not None
    assert shape.capability_requirements.requires("repository_read_required")
    assert not shape.capability_requirements.requires("code_change_required")


def test_live_vocabulary_agrees_with_the_waiter_1_family_table():
    for prompt in (DEEPSEEK_FIELD_PROMPT, FEATURE_FIELD_PROMPT, CALC_DEFECT_PROMPT):
        shape = derive_live_task_shape(prompt, repository_available=True)
        assert shape.waiter_task_shape is not None
        assert (
            live_shape_from_waiter_family(shape.waiter_task_shape.task_family)
            == shape.task_shape
        )


def test_adapter_is_labelled_a_compatibility_adapter_not_a_semantic_replacement():
    shape = derive_live_task_shape(FEATURE_FIELD_PROMPT, repository_available=True)
    assert shape.as_dict()["adapter_kind"] == "live compatibility adapter"


def test_explicit_constraints_and_order_survive_routing():
    prompt = "Refactor core/executor.py but do not touch database/schema.py"
    shape = derive_live_task_shape(prompt, repository_available=True)

    assert shape.task_shape == SHAPE_EXPLICIT_CHANGE
    assert shape.contract is not None
    prohibitions = [
        item.text
        for item in shape.contract.explicit_evidence.constraints
        if item.kind == "prohibition"
    ]
    assert prohibitions, "the user's prohibition must survive routing"
    assert any("database/schema.py" in text for text in prohibitions)


def test_ordered_obligations_are_preserved_in_the_order_written():
    obligations = split_obligations("compare X and Y, then recommend Z")
    assert obligations == ("compare X and Y", "recommend Z")


# ── 3. the route receipt ──────────────────────────────────────────────────────

def test_architecture_comparison_route_regression():
    """The deepseek field failure, pinned.

    An architecture comparison must not reach patch localization, must not be
    asked for a replacement snippet, and must not acquire write authority.
    """
    route = route_live_task(ARCHITECTURE_COMPARISON, repository_available=True)

    assert route.task_shape == SHAPE_ANALYSIS_ONLY
    assert route.selected_workflow == WORKFLOW_ANALYSIS_ANSWER
    assert route.patch_localization_allowed is False
    assert route.control_source_snippet_required is False
    assert route.source_grounding == GROUNDING_NONE
    assert route.preflight_validation_required is False
    assert route.repository_indexing_allowed is False
    assert route.change_requested is False
    assert route.change_need_source == CHANGE_NEED_NONE
    assert route.write_authority is False
    assert route.patch_application_authority is False


def test_explicit_feature_route_regression():
    """A feature request is recognised without any failing test."""
    route = route_live_task(FEATURE_FIELD_PROMPT, repository_available=True)

    assert route.task_shape == SHAPE_EXPLICIT_CHANGE
    assert route.selected_workflow == WORKFLOW_EXPLICIT_CHANGE
    assert route.change_requested is True
    assert route.defect_claim_present is False
    assert route.defect_established is False
    assert route.change_need_source == CHANGE_NEED_EXPLICIT_USER_REQUEST
    assert route.patch_localization_allowed is True
    assert route.source_grounding == GROUNDING_ACQUIRED_SOURCE_QUOTE
    # Intent is not authority.
    assert route.write_authority is False
    assert route.patch_application_authority is False


def test_defect_route_regression():
    route = route_live_task(CALC_DEFECT_PROMPT, repository_available=True)

    assert route.task_shape == SHAPE_DEFECT_REPAIR
    assert route.selected_workflow == WORKFLOW_DEFECT_REPAIR
    assert route.change_requested is True
    assert route.defect_claim_present is True
    # A claim is not an establishment.
    assert route.defect_established is False
    assert route.change_need_source == CHANGE_NEED_UNRESOLVED
    assert route.patch_localization_allowed is True
    assert route.preflight_validation_required is True
    assert route.control_source_snippet_required is True
    assert route.source_grounding == GROUNDING_CONTROL_EXACT_SOURCE


def test_false_positive_bug_report_still_routes_to_the_defect_path():
    """A claim selects the road; only evidence may end it in a patch."""
    route = route_live_task(
        "The add function returns the wrong value for 2 and 2.",
        repository_available=True,
    )
    assert route.task_shape == SHAPE_DEFECT_REPAIR
    assert route.change_need_source == CHANGE_NEED_UNRESOLVED
    assert route.defect_established is False


def test_ambiguous_request_never_defaults_to_patching():
    route = route_live_task(AMBIGUOUS_PROMPT, repository_available=True)

    assert route.task_shape == SHAPE_NEEDS_CLARIFICATION
    assert route.selected_workflow == WORKFLOW_CLARIFICATION
    assert route.patch_localization_allowed is False
    assert route.change_requested is False
    assert REASON_NO_DETERMINABLE_OBLIGATION in route.reasons


def test_mixed_request_preserves_both_halves_and_refuses_to_pick_one():
    route = route_live_task(MIXED_PROMPT, repository_available=True)

    assert route.task_shape == SHAPE_NEEDS_CLARIFICATION
    assert REASON_MIXED_OBLIGATIONS in route.reasons
    assert route.patch_localization_allowed is False
    joined = " | ".join(route.obligations).lower()
    assert "explain how validation works" in joined
    assert "fix the pytest detection bug" in joined


def test_route_receipt_carries_the_debugging_fields_and_no_confidence():
    route = route_live_task(FEATURE_FIELD_PROMPT, repository_available=True)
    payload = route.as_dict()

    for key in (
        "task_shape",
        "change_requested",
        "defect_claim_present",
        "change_need_source",
        "selected_workflow",
        "patch_localization_allowed",
        "write_authority",
    ):
        assert key in payload, key
    assert payload["write_authority"] is False
    rendered = render_live_route_json(route)
    assert "confidence" not in rendered
    assert json.loads(rendered)["phase_id"] == "WAITER.LIVE.1"


def test_a_route_receipt_may_never_claim_a_grounded_defect():
    with pytest.raises(ValueError):
        LiveRouteReceipt(
            task_shape=SHAPE_DEFECT_REPAIR,
            change_requested=True,
            defect_claim_present=True,
            change_need_source=CHANGE_NEED_GROUNDED_DEFECT,
            selected_workflow=WORKFLOW_DEFECT_REPAIR,
            patch_localization_allowed=True,
            preflight_validation_required=True,
            repository_indexing_allowed=True,
            source_grounding=GROUNDING_CONTROL_EXACT_SOURCE,
        )


def test_a_no_change_route_may_never_allow_patch_localization():
    with pytest.raises(ValueError):
        LiveRouteReceipt(
            task_shape=SHAPE_ANALYSIS_ONLY,
            change_requested=False,
            defect_claim_present=False,
            change_need_source=CHANGE_NEED_NONE,
            selected_workflow=WORKFLOW_ANALYSIS_ANSWER,
            patch_localization_allowed=True,
            preflight_validation_required=False,
            repository_indexing_allowed=False,
            source_grounding=GROUNDING_NONE,
        )


def test_missing_route_metadata_fails_closed_rather_than_patching():
    assert route_allows_patch_localization(None) is False
    assert route_allows_patch_localization({}) is False
    assert route_allows_patch_localization({"patch_localization_allowed": True}) is False
    assert route_change_need_source(None) == CHANGE_NEED_UNRESOLVED
    assert route_is_explicit_change(None) is False
    assert route_is_read_only(None) is False


def test_safe_route_falls_back_to_clarification_not_to_patching():
    route = safe_route_live_task(None, repository_available=True)
    assert route.selected_workflow == WORKFLOW_CLARIFICATION
    assert route.patch_localization_allowed is False


def test_route_helpers_read_a_serialised_receipt():
    payload = route_live_task(FEATURE_FIELD_PROMPT, repository_available=True).as_dict()
    assert route_allows_patch_localization(payload) is True
    assert route_is_explicit_change(payload) is True
    assert route_is_read_only(payload) is False

    analysis = route_live_task(DEEPSEEK_FIELD_PROMPT, repository_available=True).as_dict()
    assert route_allows_patch_localization(analysis) is False
    assert route_is_read_only(analysis) is True


# ── 4. routing costs nothing ──────────────────────────────────────────────────

def test_routing_makes_no_model_call(monkeypatch):
    import core.router as router

    monkeypatch.setattr(
        router,
        "get_model",
        lambda: pytest.fail("routing must not load an embedding model"),
    )
    monkeypatch.setattr(
        router,
        "classify_task",
        lambda *args, **kwargs: pytest.fail("routing must not classify by model"),
    )
    route = route_live_task(DEEPSEEK_FIELD_PROMPT, repository_available=True)
    assert route.selected_workflow == WORKFLOW_ANALYSIS_ANSWER


def test_routing_makes_no_network_call(monkeypatch):
    import socket

    def _refuse(*args, **kwargs):
        raise AssertionError("routing must not open a socket")

    monkeypatch.setattr(socket, "socket", _refuse)
    monkeypatch.setattr(socket, "create_connection", _refuse)
    assert route_live_task(FEATURE_FIELD_PROMPT, repository_available=True).change_requested


def test_routing_reads_no_files_and_builds_no_index(monkeypatch):
    def _refuse(*args, **kwargs):
        raise AssertionError("routing must not read the repository")

    monkeypatch.setattr(builtins, "open", _refuse)
    route = route_live_task(CALC_DEFECT_PROMPT, repository_available=True)
    assert route.selected_workflow == WORKFLOW_DEFECT_REPAIR


# ── 5. bounded analysis evidence ──────────────────────────────────────────────

def _write_repo(tmp_path):
    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    (repo / "core").mkdir(parents=True)
    (repo / "README.md").write_text("# Demo\nAn agent workspace.\n", encoding="utf-8")
    (repo / "package.json").write_text('{"name": "demo"}\n', encoding="utf-8")
    (repo / "main.py").write_text("print('hi')\n", encoding="utf-8")
    (repo / "docs" / "architecture.md").write_text("## Loop\n", encoding="utf-8")
    (repo / "core" / "retrieval.py").write_text("def search():\n    return []\n", encoding="utf-8")
    return repo


def test_analysis_evidence_prefers_documents_and_manifests_over_symbols(tmp_path):
    repo = _write_repo(tmp_path)
    evidence = collect_analysis_evidence(str(repo))

    roles = {item.path: item.role for item in evidence.items}
    assert roles.get("README.md") == ROLE_PROJECT_DOCUMENT
    assert roles.get("package.json") == ROLE_PACKAGE_MANIFEST
    assert "docs/architecture.md" in roles


def test_analysis_evidence_honours_a_path_the_user_named(tmp_path):
    repo = _write_repo(tmp_path)
    evidence = collect_analysis_evidence(
        str(repo), requested_paths=["core/retrieval.py"]
    )
    assert evidence.items[0].path == "core/retrieval.py"
    assert evidence.items[0].role == ROLE_REQUESTED_PATH


def test_analysis_evidence_is_bounded(tmp_path):
    repo = tmp_path / "big"
    (repo / "docs").mkdir(parents=True)
    for index in range(60):
        (repo / "docs" / f"note-{index:03d}.md").write_text("x" * 20_000, encoding="utf-8")
    evidence = collect_analysis_evidence(str(repo))

    assert len(evidence.items) <= MAX_EVIDENCE_FILES
    assert sum(len(item.text) for item in evidence.items) <= 60_000
    assert evidence.gaps, "a bounded read must report what it did not read"


def test_analysis_evidence_never_escapes_the_repository(tmp_path):
    repo = _write_repo(tmp_path)
    (tmp_path / "outside.md").write_text("secret", encoding="utf-8")
    evidence = collect_analysis_evidence(
        str(repo), requested_paths=["../outside.md", "/etc/passwd"]
    )
    assert all(not item.path.startswith("..") for item in evidence.items)
    assert all("outside.md" not in item.path for item in evidence.items)


def test_analysis_prompt_is_a_readable_answer_not_a_patch_request(tmp_path):
    repo = _write_repo(tmp_path)
    route = route_live_task(ARCHITECTURE_COMPARISON, repository_available=True)
    evidence = collect_analysis_evidence(str(repo))
    prompt = build_analysis_answer_prompt(
        user_query=ARCHITECTURE_COMPARISON,
        evidence=evidence,
        obligations=route.obligations,
        repo_path=str(repo),
    )

    lowered = prompt.lower()
    assert "patch_candidate" not in lowered or "do not propose" in lowered
    assert "source_snippet" not in lowered
    assert "cannot safely generate patch" not in lowered
    assert "return only valid json" not in lowered
    assert "README.md" in prompt
    assert "agent loop" in prompt


def test_clarification_prompt_states_every_obligation_and_asks(tmp_path):
    repo = _write_repo(tmp_path)
    route = route_live_task(MIXED_PROMPT, repository_available=True)
    prompt = build_analysis_answer_prompt(
        user_query=MIXED_PROMPT,
        evidence=collect_analysis_evidence(str(repo)),
        obligations=route.obligations,
        repo_path=str(repo),
        clarification=True,
    )
    assert "Explain how validation works" in prompt
    assert "fix the pytest detection bug" in prompt
    assert "do not propose or apply an edit" in prompt.lower()


def test_selection_is_deterministic_over_the_same_inventory():
    paths = ["README.md", "docs/a.md", "package.json", "main.py", "core/x.py"]
    first = select_analysis_paths(paths, subjects=["core"])
    second = select_analysis_paths(paths, subjects=["core"])
    assert first == second


# ── 6. CONTROL: change-need separation without weakening defect grounding ────

def _control_result(tmp_path, *, route=None, preflight=None, snippet="def add(a, b):\n    return 0\n"):
    repo = tmp_path / "repo"
    repo.mkdir(exist_ok=True)
    (repo / "calc.py").write_text(snippet, encoding="utf-8")
    control = {
        "repo_path": str(repo),
        "query": "calc",
        "top_hypothesis": {"symbol": "calc.py::add", "score": 0.4},
        "hypotheses": [{"symbol": "calc.py::add", "score": 0.4}],
        "patch_intent": {
            "relative_path": "calc.py",
            "file": "calc.py",
            "source_snippet": snippet,
            "target_symbol": "add",
        },
        "related_snippets": [{"file": "calc.py", "symbol": "add", "snippet": snippet}],
    }
    if route is not None:
        control["live_route"] = route
    if preflight is not None:
        control["preflight_validation"] = preflight
    return repo, control


_FAILING_PREFLIGHT = {
    "ran": True,
    "ok": False,
    "category": "test_failure",
    "outcome": "failed",
    "command": "pytest",
    "output": "calc.py:2: AssertionError",
    "locations": [{"file": "calc.py", "line": 2, "kind": "assertion"}],
}

_INCONCLUSIVE_PREFLIGHT = {
    "ran": True,
    "ok": False,
    "category": "no_tests_collected",
    "outcome": "inconclusive",
    "command": "pytest",
    "output": "collected 0 items",
    "locations": [],
}


def _feature_route():
    return route_live_task(FEATURE_FIELD_PROMPT, repository_available=True).as_dict()


def _defect_route():
    return route_live_task(CALC_DEFECT_PROMPT, repository_available=True).as_dict()


def _analysis_route():
    return route_live_task(DEEPSEEK_FIELD_PROMPT, repository_available=True).as_dict()


def test_change_need_source_is_explicit_user_request_for_a_feature(tmp_path):
    from core.control_engine import refresh_control_safety

    _, control = _control_result(tmp_path, route=_feature_route())
    state = refresh_control_safety(control)["patch_candidate_state"]

    assert state["change_need_source"] == CHANGE_NEED_EXPLICIT_USER_REQUEST
    assert state["explicit_change_requested"] is True
    # A requested change is not a defect.
    assert state["defect_established"] is False
    assert state["write_authority"] is False
    assert state["patch_application_authority"] is False


def test_change_need_source_becomes_grounded_defect_only_from_executed_failure(tmp_path):
    from core.control_engine import refresh_control_safety

    _, control = _control_result(
        tmp_path, route=_defect_route(), preflight=_FAILING_PREFLIGHT
    )
    state = refresh_control_safety(control)["patch_candidate_state"]

    assert state["defect_established"] is True
    assert state["change_need_source"] == CHANGE_NEED_GROUNDED_DEFECT
    assert state["eligible_for_patch_safety_handoff"] is True


def test_a_defect_claim_without_evidence_stays_unresolved(tmp_path):
    from core.control_engine import refresh_control_safety

    _, control = _control_result(tmp_path, route=_defect_route())
    state = refresh_control_safety(control)["patch_candidate_state"]

    assert state["defect_established"] is False
    assert state["change_need_source"] == CHANGE_NEED_UNRESOLVED
    assert state["eligible_for_patch_safety_handoff"] is False


def test_inconclusive_validation_still_establishes_no_defect(tmp_path):
    from core.control_engine import refresh_control_safety

    _, control = _control_result(
        tmp_path, route=_defect_route(), preflight=_INCONCLUSIVE_PREFLIGHT
    )
    state = refresh_control_safety(control)["patch_candidate_state"]

    assert state["defect_established"] is False
    assert state["change_need_source"] == CHANGE_NEED_UNRESOLVED


def test_a_failing_baseline_does_not_turn_a_feature_into_a_defect_task(tmp_path):
    """§17 — baseline health is not a task shape."""
    from core.control_engine import refresh_control_safety

    _, control = _control_result(
        tmp_path, route=_feature_route(), preflight=_FAILING_PREFLIGHT
    )
    state = refresh_control_safety(control)["patch_candidate_state"]

    assert state["change_need_source"] == CHANGE_NEED_EXPLICIT_USER_REQUEST
    assert control["live_route"]["task_shape"] == SHAPE_EXPLICIT_CHANGE


def test_an_unrouted_control_result_keeps_control_safety_live_1_behaviour(tmp_path):
    from core.control_engine import refresh_control_safety

    _, control = _control_result(tmp_path)
    state = refresh_control_safety(control)["patch_candidate_state"]

    assert state["defect_established"] is False
    assert state["change_need_source"] == CHANGE_NEED_UNRESOLVED
    assert state["explicit_change_requested"] is False
    assert state["eligible_for_patch_safety_handoff"] is False


# ── 7. the CONTROL prompt by route ────────────────────────────────────────────

def test_explicit_change_reaches_the_change_prompt_not_the_ungrounded_refusal(tmp_path):
    from core.control_engine import build_control_prompt

    repo, control = _control_result(tmp_path, route=_feature_route())
    prompt = build_control_prompt(control, FEATURE_FIELD_PROMPT, repo_path=str(repo))

    assert "explicit_change_request" in prompt
    assert "change_need_source=explicit_user_request" in prompt
    assert "Set patch_candidate=null" not in prompt
    assert "Cannot safely generate patch" not in prompt
    # The change is delivered, not reduced to one symbol.
    assert "do not reduce it to one suspicious symbol" in prompt
    # And it is still grounded in real source.
    assert "target_snippet must be copied verbatim" in prompt


def test_a_defect_without_grounding_still_gets_the_inspection_only_prompt(tmp_path):
    from core.control_engine import build_control_prompt

    repo, control = _control_result(tmp_path, route=_defect_route())
    prompt = build_control_prompt(control, CALC_DEFECT_PROMPT, repo_path=str(repo))

    assert "Set patch_candidate=null" in prompt
    assert "Localization rank is useful for inspection only" in prompt


def test_a_read_only_route_never_reaches_a_patch_prompt(tmp_path):
    from core.control_engine import build_control_prompt

    repo, control = _control_result(tmp_path, route=_analysis_route())
    prompt = build_control_prompt(control, DEEPSEEK_FIELD_PROMPT, repo_path=str(repo))

    assert "No code change was requested" in prompt
    assert "patch_candidate" not in prompt
    assert "Cannot safely generate patch" not in prompt


def test_an_unrouted_prompt_is_unchanged_by_this_phase(tmp_path):
    """Dream and the proposal queue call CONTROL with no route; nothing moved."""
    from core.control_engine import build_control_prompt

    repo, control = _control_result(tmp_path, preflight=_FAILING_PREFLIGHT)
    prompt = build_control_prompt(control, "fix add", repo_path=str(repo))

    assert "[PATCH TARGET]" in prompt
    assert "explicit_change_request" not in prompt


# ── 8. the payload boundary ───────────────────────────────────────────────────

def _feature_plan():
    return {
        "patch_plan": [
            {"file": "calc.py", "op": "replace_snippet"},
        ],
        "confidence": 0.9,
        "needs_escalation": False,
    }


def test_explicit_change_payload_survives_when_targets_were_actually_acquired(tmp_path):
    from core.control_engine import enforce_control_grounding_on_payload

    _, control = _control_result(tmp_path, route=_feature_route())
    # PATCH.BASIS.LIVE.1 preserves a literal ``across model/store/CLI`` scope.
    # This one-file fixture tests the independent explicit-basis rule, so use a
    # one-surface preserved request rather than contradicting that scope.
    control["live_route"] = route_live_task(
        "Add calculator priority support.", repository_available=True
    ).as_dict()
    block = _feature_plan()
    enforce_control_grounding_on_payload(control, block)

    assert block["patch_plan"], "an explicitly requested change must not need a defect"
    assert not block.get("control_patch_candidate_rejected")


def test_explicit_change_payload_is_refused_for_a_file_nobody_opened(tmp_path):
    from core.control_engine import enforce_control_grounding_on_payload

    _, control = _control_result(tmp_path, route=_feature_route())
    block = {
        "patch_plan": [{"file": "unseen/module.py", "op": "replace_snippet"}],
        "confidence": 0.9,
        "needs_escalation": False,
    }
    enforce_control_grounding_on_payload(control, block)

    assert block["patch_plan"] is None
    assert "did not acquire" in block["control_patch_candidate_reject_reason"]


def test_naming_a_file_is_not_permission_to_edit_it(tmp_path):
    """Ranked, or picked by Scout, is not the same as read."""
    from core.control_engine import acquired_source_files, enforce_control_grounding_on_payload

    _, control = _control_result(tmp_path, route=_feature_route())
    control["related_snippets"] = []
    control["scout"] = {"likely_files": ["store.py", "model.py"]}
    control["patch_intent"]["source_snippet"] = ""

    assert acquired_source_files(control) == set()

    block = {
        "patch_plan": [{"file": "store.py", "op": "replace_snippet"}],
        "confidence": 0.9,
        "needs_escalation": False,
    }
    enforce_control_grounding_on_payload(control, block)
    assert block["patch_plan"] is None


def test_a_read_only_route_may_not_carry_a_patch_payload(tmp_path):
    from core.control_engine import enforce_control_grounding_on_payload

    _, control = _control_result(tmp_path, route=_analysis_route())
    block = _feature_plan()
    enforce_control_grounding_on_payload(control, block)

    assert block["patch_plan"] is None
    assert block["needs_escalation"] is True
    assert "read-only" in block["control_patch_candidate_reject_reason"]


def test_an_ungrounded_defect_payload_is_still_refused(tmp_path):
    """CONTROL.SAFETY.LIVE.1, unweakened: rank alone still buys nothing."""
    from core.control_engine import enforce_control_grounding_on_payload

    _, control = _control_result(tmp_path, route=_defect_route())
    block = {
        "patch_candidate": {"file": "calc.py", "target_snippet": "x"},
        "confidence": 0.9,
        "needs_escalation": False,
    }
    enforce_control_grounding_on_payload(control, block)

    assert block["patch_candidate"] is None
    assert "executed failure evidence" in block["control_patch_candidate_reject_reason"]


def test_a_grounded_defect_payload_still_passes(tmp_path):
    from core.control_engine import enforce_control_grounding_on_payload

    _, control = _control_result(
        tmp_path, route=_defect_route(), preflight=_FAILING_PREFLIGHT
    )
    block = {
        "patch_candidate": {"file": "calc.py", "target_snippet": "return 0"},
        "confidence": 0.9,
        "needs_escalation": False,
    }
    enforce_control_grounding_on_payload(control, block)

    assert block["patch_candidate"] is not None


# ── 9. write authority is never widened ───────────────────────────────────────

class _State:
    def __init__(self, **kwargs):
        self.live_route = kwargs.pop("live_route", {})
        self.is_project_input = kwargs.pop("is_project_input", True)
        self.json_block = kwargs.pop("json_block", None)
        self.control_result = kwargs.pop("control_result", None)
        self.mode = kwargs.pop("mode", "reviewer")
        self.final_answer = kwargs.pop("final_answer", "")
        self.human_answer = ""
        self.task_info = kwargs.pop("task_info", {})
        self.patch_style = "safe_minimal"
        self.repo_path = kwargs.pop("repo_path", None)
        for key, value in kwargs.items():
            setattr(self, key, value)


def test_auto_patch_never_runs_on_a_read_only_route(capsys):
    from core import pipeline

    state = _State(live_route=_analysis_route(), json_block={"patch_candidate": {}})
    pipeline.maybe_run_auto_patch(state, interactive=False)

    assert "read-only route" in capsys.readouterr().out


def test_auto_patch_disabled_stays_monotonic_for_an_explicit_change(monkeypatch, capsys):
    from core import pipeline

    monkeypatch.setattr(pipeline, "AUTO_PATCH_ENABLED", False)
    state = _State(live_route=_feature_route(), json_block={"patch_candidate": {}})
    pipeline.maybe_run_auto_patch(state, interactive=False)

    assert "Auto-patch disabled" in capsys.readouterr().out


def test_postprocess_battery_does_not_badger_a_prose_answer_into_a_patch():
    from core.postprocess_gates import run_postprocess_gate_battery

    state = _State(live_route=_analysis_route(), json_block=None, final_answer="prose")
    run_postprocess_gate_battery(
        state,
        reviewed_answer="prose",
        retry_structured_patch_json_fn=lambda *args: pytest.fail(
            "a read-only answer must not be retried into a patch schema"
        ),
        finalize_answer_fn=lambda *args: None,
    )
    assert state.json_block is None


def test_review_pipeline_is_skipped_on_a_read_only_route():
    from core import pipeline

    state = _State(live_route=_analysis_route())
    assert pipeline.run_review_pipeline(state, "the answer") == "the answer"


# ── 10. live production entry points ──────────────────────────────────────────

def _patch_runner(monkeypatch, runner, calls, control_result=None):
    def _record(name, value=None):
        def _inner(*args, **kwargs):
            calls.append(name)
            return value() if callable(value) else value
        return _inner

    monkeypatch.setattr(
        runner,
        "classify_task",
        lambda query, mode, language, audience: {
            "intent": "bug_fix",
            "complexity": "simple",
            "language": language,
        },
    )
    monkeypatch.setattr(runner, "index_repository", _record("index", {}))
    monkeypatch.setattr(runner, "clear_graph_cache", _record("clear_graph_cache"))
    monkeypatch.setattr(
        runner,
        "run_preflight_validation",
        _record("preflight", {"ran": False, "ok": None}),
    )
    monkeypatch.setattr(
        runner,
        "run_control_structured",
        _record("control", lambda: dict(control_result or {})),
    )
    monkeypatch.setattr(runner, "build_related_snippets", lambda control, repo_path, **kw: [])
    monkeypatch.setattr(runner, "get_engineering_memory", lambda **kwargs: [])
    monkeypatch.setattr(
        runner, "maybe_enrich_with_scout", lambda **kwargs: kwargs["control_result"]
    )
    monkeypatch.setattr(runner, "get_or_compute_dna", lambda repo_path, **kwargs: {})
    monkeypatch.setattr(runner, "dna_to_prompt_block", lambda dna, mode="match": "")
    monkeypatch.setattr(runner, "create_session", lambda **kwargs: 123)
    monkeypatch.setattr(runner, "memory_note_exists", lambda *args, **kwargs: True)
    monkeypatch.setattr(runner, "save_message", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "save_engineering_memory", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "run_review_pipeline", lambda state, draft: draft)
    monkeypatch.setattr(runner, "run_postprocess_gate_battery", lambda *a, **k: None)
    monkeypatch.setattr(runner, "maybe_run_auto_patch", _record("auto_patch"))


def test_web_analysis_route_skips_index_preflight_and_control(tmp_path, monkeypatch):
    from web import runner

    repo = _write_repo(tmp_path)
    calls: list[str] = []
    _patch_runner(monkeypatch, runner, calls)

    captured = {}

    def _draft(state):
        calls.append("draft")
        captured["state"] = state
        return "An explanation grounded in README.md."

    monkeypatch.setattr(runner, "run_draft_pipeline", _draft)
    monkeypatch.setattr(runner, "finalize_answer", lambda state, answer: setattr(state, "final_answer", answer))

    result = runner.run_agent_web(
        ARCHITECTURE_COMPARISON, str(repo), runtime_environment="local_linux"
    )

    assert "index" not in calls
    assert "preflight" not in calls
    assert "control" not in calls
    assert "auto_patch" not in calls
    assert result["live_route"]["task_shape"] == SHAPE_ANALYSIS_ONLY
    assert result["live_route"]["patch_localization_allowed"] is False
    assert result["live_route"]["write_authority"] is False
    assert result["patch"] == ""
    assert captured["state"].control_result is None
    assert captured["state"].analysis_evidence is not None
    assert captured["state"].analysis_evidence.items


def test_web_defect_route_still_indexes_validates_and_localizes(tmp_path, monkeypatch):
    from web import runner

    repo = _write_repo(tmp_path)
    calls: list[str] = []
    _patch_runner(
        monkeypatch,
        runner,
        calls,
        control_result={
            "patch_intent": {"file": "main.py", "source_snippet": "print('hi')\n"},
            "top_hypothesis": {"symbol": "main.py::main"},
        },
    )
    monkeypatch.setattr(runner, "run_draft_pipeline", lambda state: "{}")
    monkeypatch.setattr(runner, "finalize_answer", lambda state, answer: None)

    result = runner.run_agent_web(
        CALC_DEFECT_PROMPT, str(repo), runtime_environment="local_linux"
    )

    assert calls.index("index") < calls.index("control")
    assert "preflight" in calls
    assert result["live_route"]["task_shape"] == SHAPE_DEFECT_REPAIR
    assert result["live_route"]["patch_localization_allowed"] is True


def test_web_feature_route_localizes_without_requiring_a_failing_test(tmp_path, monkeypatch):
    from web import runner

    repo = _write_repo(tmp_path)
    calls: list[str] = []
    _patch_runner(
        monkeypatch,
        runner,
        calls,
        control_result={
            "patch_intent": {"file": "main.py", "source_snippet": "print('hi')\n"},
            "top_hypothesis": {"symbol": "main.py::main"},
        },
    )
    monkeypatch.setattr(runner, "run_draft_pipeline", lambda state: "{}")
    monkeypatch.setattr(runner, "finalize_answer", lambda state, answer: None)

    result = runner.run_agent_web(
        FEATURE_FIELD_PROMPT, str(repo), runtime_environment="local_linux"
    )

    assert "control" in calls
    assert result["live_route"]["task_shape"] == SHAPE_EXPLICIT_CHANGE
    assert result["live_route"]["change_need_source"] == CHANGE_NEED_EXPLICIT_USER_REQUEST
    assert result["live_route"]["defect_established"] is False
    assert result["live_route"]["write_authority"] is False


def test_web_route_is_decided_before_any_repository_work(tmp_path, monkeypatch):
    """§36 — classification happens before the graph work it would pay for."""
    from web import runner

    repo = _write_repo(tmp_path)
    calls: list[str] = []
    original = runner.safe_route_live_task

    def _routed(*args, **kwargs):
        calls.append("route")
        return original(*args, **kwargs)

    monkeypatch.setattr(runner, "safe_route_live_task", _routed)
    _patch_runner(
        monkeypatch,
        runner,
        calls,
        control_result={
            "patch_intent": {"file": "main.py", "source_snippet": "print('hi')\n"},
            "top_hypothesis": {"symbol": "main.py::main"},
        },
    )
    monkeypatch.setattr(runner, "run_draft_pipeline", lambda state: "{}")
    monkeypatch.setattr(runner, "finalize_answer", lambda state, answer: None)

    runner.run_agent_web(CALC_DEFECT_PROMPT, str(repo), runtime_environment="local_linux")

    assert calls[0] == "route"
    assert calls.index("route") < calls.index("index")
    assert calls.index("route") < calls.index("control")


def test_cli_analysis_route_skips_index_preflight_and_control(tmp_path, monkeypatch):
    from cli import interactive

    repo = _write_repo(tmp_path)
    answers = iter(
        [
            "agent",
            "reviewer",
            "safe_minimal",
            "n",
            DEEPSEEK_FIELD_PROMPT,
            str(repo),
            "",
        ]
    )
    monkeypatch.setattr(builtins, "input", lambda *args: next(answers))
    calls: list[str] = []
    monkeypatch.setattr(
        interactive,
        "index_repository",
        lambda *a, **k: calls.append("index") or {},
    )
    monkeypatch.setattr(
        interactive,
        "run_preflight_validation",
        lambda **k: calls.append("preflight") or {},
    )
    monkeypatch.setattr(
        interactive,
        "run_control_structured",
        lambda *a, **k: calls.append("control") or {},
    )
    monkeypatch.setattr(interactive, "detect_repo_language", lambda path: "python")
    monkeypatch.setattr(
        interactive,
        "classify_task",
        lambda prompt, mode, language, audience: {
            "intent": "code_explanation",
            "complexity": "simple",
            "language": language,
        },
    )
    monkeypatch.setattr(interactive, "create_session", lambda **k: 7)
    monkeypatch.setattr(interactive, "save_message", lambda *a, **k: None)
    monkeypatch.setattr(interactive, "save_artifact", lambda *a, **k: None)
    monkeypatch.setattr(interactive, "get_recent_messages", lambda *a, **k: [])
    monkeypatch.setattr(interactive, "build_memory_block", lambda *a, **k: "")
    monkeypatch.setattr(interactive, "create_task_run", lambda **k: 11)
    monkeypatch.setattr(interactive, "maybe_retrieve_context", lambda *a, **k: "")

    state = interactive.create_agent_state()

    assert state is not None
    assert calls == []
    assert state.live_route["task_shape"] == SHAPE_ANALYSIS_ONLY
    assert state.control_result is None
    assert state.analysis_evidence is not None
