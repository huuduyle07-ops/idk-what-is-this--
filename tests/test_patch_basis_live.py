"""PATCH.BASIS.LIVE.1 typed-basis and failure-relevance regressions."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from core import control_engine, pipeline
from core.agent_state import AgentState
from core.live_task_routing import route_live_task
from core.patch_basis import (
    FAILURE_BINDING_AMBIGUOUS,
    FAILURE_BINDING_DIRECT_EXECUTED_REFERENCE,
    FAILURE_BINDING_DIRECT_LOCATION,
    FAILURE_BINDING_UNAVAILABLE,
    PATCH_BASIS_EXPLICIT_CHANGE_REQUEST,
    PATCH_BASIS_GROUNDED_DEFECT,
    PATCH_BASIS_NONE,
    PATCH_BASIS_UNRESOLVED,
)
from core.postprocess_gates import run_postprocess_gate_battery
from core.preflight import run_preflight_validation
from core.run_lifecycle import run_patch_plan_with_artifacts
from policy.decision_helper import build_patch_policy


def _write(repo: Path, relative: str, text: str) -> None:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _defect_route(text: str = "add returns the wrong value; fix this bug") -> dict:
    return route_live_task(text, repository_available=True).as_dict()


def _feature_route() -> dict:
    return route_live_task(
        "Add task priority support across model/store/CLI.",
        repository_available=True,
    ).as_dict()


def _control(
    repo: Path,
    symbols: list[str],
    *,
    route: dict | None = None,
    preflight: dict | None = None,
    related_files: list[str] | None = None,
    execution_trace: str = "",
) -> dict:
    hypotheses = [
        {
            "symbol": symbol,
            "score": float(100 - index),
            "confidence": 0.99,
            "reasons": ["test navigation fixture"],
            "called_by": ["graph-only-neighbour"],
            "calls": [],
        }
        for index, symbol in enumerate(symbols)
    ]
    control = {
        "repo_path": str(repo),
        "query": "fix the requested behavior",
        "top_hypothesis": hypotheses[0] if hypotheses else None,
        "hypotheses": hypotheses,
        "evidence": hypotheses,
        "execution_trace": execution_trace,
        "related_snippets": [],
    }
    if route is not None:
        control["live_route"] = route
    if preflight is not None:
        control["preflight_validation"] = preflight
    control_engine.refresh_control_safety(control)
    if related_files is not None:
        control["related_snippets"] = [
            {
                "file": relative,
                "symbol": Path(relative).stem,
                "snippet": (repo / relative).read_text(encoding="utf-8"),
            }
            for relative in related_files
        ]
        control_engine.refresh_control_safety(control)
    return control


def _failed_preflight(file: str, line: int, *, output: str = "") -> dict:
    return {
        "ran": True,
        "ok": False,
        "outcome": "failed",
        "category": "assertion_failure",
        "command": "python -m pytest",
        "output": output or f"{file}:{line}: AssertionError",
        "locations": [{"file": file, "line": line, "kind": "assertion"}],
    }


def _state(
    repo: Path,
    control: dict,
    block: dict,
    *,
    user_input: str,
    intent: str = "bug_fix",
    style: str = "safe_minimal",
) -> AgentState:
    return AgentState(
        interface="agent",
        mode="reviewer",
        user_input=user_input,
        file_paths=[str(repo)],
        primary_file=None,
        input_mode="error_log",
        language="python",
        task_type=intent,
        task_info={
            "intent": intent,
            "complexity": "simple",
            "language": "python",
            "patch_style": style,
        },
        is_project_input=True,
        repo_path=str(repo),
        control_result=control,
        live_route=control.get("live_route") or {},
        json_block=block,
    )


def _disable_persistence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pipeline, "get_tooling_profile", lambda *a, **k: {})
    monkeypatch.setattr(pipeline, "upsert_tooling_profile", lambda *a, **k: None)
    monkeypatch.setattr(pipeline, "save_patch_attempt", lambda *a, **k: None)
    monkeypatch.setattr(pipeline, "save_engineering_memory", lambda *a, **k: None)
    monkeypatch.setattr(pipeline, "refresh_memory_block", lambda *a, **k: None)
    monkeypatch.setattr(pipeline, "AUTO_PATCH_ENABLED", True)


def test_direct_failure_location_still_establishes_grounded_defect(tmp_path):
    _write(tmp_path, "calc.py", "def add(a, b):\n    return a - b\n")
    control = _control(
        tmp_path,
        ["calc.py::add"],
        route=_defect_route(),
        preflight=_failed_preflight("calc.py", 2),
    )
    state = control["patch_candidate_state"]
    assert state["patch_basis"] == PATCH_BASIS_GROUNDED_DEFECT
    assert state["failure_binding_kind"] == FAILURE_BINDING_DIRECT_LOCATION
    assert state["target_source_grounded"] is True
    assert state["write_authority"] is False


def test_caller_assertion_binds_to_imported_implementation(tmp_path):
    _write(tmp_path, "calc.py", "def add(a, b):\n    return a - b\n")
    _write(tmp_path, "main.py", "from calc import add\nassert add(2, 2) == 4\n")
    preflight = run_preflight_validation(str(tmp_path), "python", command="python main.py")
    assert preflight["category"] == "assertion_failure"

    control = _control(
        tmp_path,
        ["calc.py::add"],
        route=_defect_route(),
        preflight=preflight,
    )
    state = control["patch_candidate_state"]
    assert state["patch_basis"] == PATCH_BASIS_GROUNDED_DEFECT
    assert state["failure_binding_kind"] == FAILURE_BINDING_DIRECT_EXECUTED_REFERENCE
    assert state["failure_binding_location"]["file"] == "main.py"
    assert state["candidate_binding"]["file"] == "calc.py"
    assert state["candidate_binding"]["symbol"] == "add"
    assert control["grounded_hypothesis"]["needs_escalation"] is False
    assert control["patch_intent"]["target_file"] == "calc.py"


def test_flat_pytest_failure_binds_test_expression_to_implementation(tmp_path):
    _write(
        tmp_path,
        "solution.py",
        "def length_of_longest_substring(value):\n    return len(value)\n",
    )
    _write(
        tmp_path,
        "test_solution.py",
        "from solution import length_of_longest_substring\n\n"
        "def test_abba():\n"
        "    assert length_of_longest_substring('abba') == 2\n",
    )
    preflight = run_preflight_validation(str(tmp_path), "python")
    assert preflight["outcome"] == "failed"
    assert "pytest" in preflight["command"]

    control = _control(
        tmp_path,
        ["solution.py::length_of_longest_substring"],
        route=_defect_route("the sliding-window pytest assertion is wrong; fix the bug"),
        preflight=preflight,
    )
    state = control["patch_candidate_state"]
    assert state["patch_basis"] == PATCH_BASIS_GROUNDED_DEFECT
    assert state["failure_binding_kind"] == FAILURE_BINDING_DIRECT_EXECUTED_REFERENCE
    assert state["failure_binding_location"]["file"] == "test_solution.py"
    assert control["grounded_hypothesis"]["needs_escalation"] is False
    assert control["patch_intent"]["target_file"] == "solution.py"


def test_ambiguous_symbol_resolution_refuses_without_using_rank(tmp_path):
    _write(tmp_path, "calc.py", "def add(a, b):\n    return a - b\n")
    _write(tmp_path, "other.py", "def add(a, b):\n    return a * b\n")
    _write(tmp_path, "main.py", "assert add(2, 2) == 4\n")
    control = _control(
        tmp_path,
        ["calc.py::add", "other.py::add"],
        route=_defect_route(),
        preflight=_failed_preflight("main.py", 1),
    )
    state = control["patch_candidate_state"]
    assert state["patch_basis"] == PATCH_BASIS_UNRESOLVED
    assert state["failure_binding_kind"] == FAILURE_BINDING_AMBIGUOUS
    assert state["defect_established"] is False
    assert state["eligible_for_patch_safety_handoff"] is False


@pytest.mark.parametrize(
    ("failing_source", "execution_trace"),
    [
        ("assert False\n", ""),
        ('message = "add(2, 2)"\nassert False\n', ""),
        ("assert False\n", "calc.py::add appears near this execution trace"),
    ],
    ids=["graph-only", "lexical-only", "trace-proximity-only"],
)
def test_navigation_evidence_alone_cannot_ground(
    tmp_path, failing_source, execution_trace
):
    _write(tmp_path, "calc.py", "def add(a, b):\n    return a - b\n")
    _write(tmp_path, "main.py", failing_source)
    line = len(failing_source.splitlines())
    control = _control(
        tmp_path,
        ["calc.py::add"],
        route=_defect_route(),
        preflight=_failed_preflight("main.py", line),
        execution_trace=execution_trace,
    )
    state = control["patch_candidate_state"]
    assert state["patch_basis"] == PATCH_BASIS_UNRESOLVED
    assert state["failure_binding_kind"] == FAILURE_BINDING_UNAVAILABLE
    assert state["defect_established"] is False


def test_calc_indirect_binding_delivers_end_to_end(tmp_path, monkeypatch):
    _write(tmp_path, "calc.py", "def add(a, b):\n    return a - b\n")
    _write(tmp_path, "main.py", "from calc import add\nassert add(2, 2) == 4\n")
    preflight = run_preflight_validation(str(tmp_path), "python", command="python main.py")
    control = _control(
        tmp_path,
        ["calc.py::add"],
        route=_defect_route(),
        preflight=preflight,
    )
    target = control["patch_intent"]["source_snippet"]
    block = {
        "summary": "Use addition.",
        "issues": [],
        "patch_candidate": {
            "relative_path": "calc.py",
            "file": "calc.py",
            "target_node_name": "add",
            "target_node_kind": "function",
            "target_snippet": target,
            "patched_snippet": target.replace("return a - b", "return a + b"),
        },
        "patch_plan": None,
        "confidence": 0.95,
        "needs_escalation": False,
    }
    state = _state(
        tmp_path,
        control,
        block,
        user_input="add returns the wrong value; fix this bug\nValidation command: python main.py",
    )
    run_postprocess_gate_battery(state)
    _disable_persistence(monkeypatch)
    pipeline.maybe_run_auto_patch(state, interactive=False)
    assert "return a + b" in (tmp_path / "calc.py").read_text(encoding="utf-8")
    assert run_preflight_validation(
        str(tmp_path), "python", command="python main.py"
    )["outcome"] == "passed"


def test_flat_pytest_regression_proceeds_and_validates(tmp_path, monkeypatch):
    _write(
        tmp_path,
        "solution.py",
        "def length_of_longest_substring(value):\n    return len(value)\n",
    )
    _write(
        tmp_path,
        "test_solution.py",
        "from solution import length_of_longest_substring\n\n"
        "def test_abba():\n"
        "    assert length_of_longest_substring('abba') == 2\n",
    )
    preflight = run_preflight_validation(str(tmp_path), "python")
    control = _control(
        tmp_path,
        ["solution.py::length_of_longest_substring"],
        route=_defect_route("the flat pytest sliding window test fails; fix the bug"),
        preflight=preflight,
    )
    target = control["patch_intent"]["source_snippet"]
    block = {
        "patch_candidate": {
            "relative_path": "solution.py",
            "target_node_name": "length_of_longest_substring",
            "target_snippet": target,
            "patched_snippet": target.replace("return len(value)", "return 2"),
        },
        "patch_plan": None,
        "confidence": 0.95,
        "needs_escalation": False,
        "issues": [],
    }
    state = _state(
        tmp_path,
        control,
        block,
        user_input="the flat pytest sliding window test fails; fix the bug",
    )
    run_postprocess_gate_battery(state)
    _disable_persistence(monkeypatch)
    pipeline.maybe_run_auto_patch(state, interactive=False)
    assert "return 2" in (tmp_path / "solution.py").read_text(encoding="utf-8")
    assert run_preflight_validation(str(tmp_path), "python")["outcome"] == "passed"


def test_harmful_test_edit_remains_blocked_before_any_write(tmp_path):
    _write(tmp_path, "solution.py", "def answer():\n    return 5\n")
    original_test = "from solution import answer\nassert answer() == 5\n"
    _write(tmp_path, "test_solution.py", original_test)
    plan = [
        {
            "op": "replace_snippet",
            "file": "solution.py",
            "target_snippet": "return 5",
            "patched_snippet": "return 6",
        },
        {
            "op": "replace_snippet",
            "file": "test_solution.py",
            "target_snippet": "== 5",
            "patched_snippet": "== 6",
        },
    ]
    result = run_patch_plan_with_artifacts(str(tmp_path), plan)
    assert result["success"] is False
    assert result["patch_safety"]["ok"] is False
    assert "test path" in " ".join(result["patch_safety"]["reasons"])
    assert (tmp_path / "solution.py").read_text(encoding="utf-8").endswith(
        "return 5\n"
    )
    assert (tmp_path / "test_solution.py").read_text(encoding="utf-8") == original_test


def _feature_control(repo: Path, preflight: dict | None = None) -> dict:
    _write(repo, "model.py", "PRIORITY = 0\n")
    _write(repo, "store.py", "STORED_PRIORITY = 0\n")
    _write(repo, "cli.py", "CLI_PRIORITY = 0\n")
    return _control(
        repo,
        ["model.py::PRIORITY"],
        route=_feature_route(),
        preflight=preflight,
        related_files=["model.py", "store.py", "cli.py"],
    )


def _feature_plan() -> dict:
    return {
        "patch_plan": [
            {
                "op": "replace_snippet",
                "file": "model.py",
                "target_snippet": "PRIORITY = 0",
                "patched_snippet": "PRIORITY = 1",
            },
            {
                "op": "replace_snippet",
                "file": "store.py",
                "target_snippet": "STORED_PRIORITY = 0",
                "patched_snippet": "STORED_PRIORITY = 1",
            },
            {
                "op": "replace_snippet",
                "file": "cli.py",
                "target_snippet": "CLI_PRIORITY = 0",
                "patched_snippet": "CLI_PRIORITY = 1",
            },
        ],
        "patch_candidate": None,
        "confidence": 1.0,
        "needs_escalation": False,
        "issues": [],
    }


@pytest.mark.parametrize(
    "preflight",
    [
        {
            "ran": True,
            "ok": True,
            "outcome": "passed",
            "category": "passed",
            "command": "python -m pytest",
            "output": "1 passed",
            "locations": [],
        },
        {
            "ran": False,
            "ok": None,
            "outcome": "inconclusive",
            "category": "no_validation_command",
            "command": "",
            "output": "",
            "locations": [],
        },
        {
            "ran": True,
            "ok": False,
            "outcome": "failed",
            "category": "assertion_failure",
            "command": "python -m pytest",
            "output": "model.py:1: AssertionError",
            "locations": [{"file": "model.py", "line": 1, "kind": "assertion"}],
        },
    ],
    ids=["passing-baseline", "inconclusive-baseline", "failing-baseline"],
)
def test_feature_basis_is_not_relabelled_by_baseline_health(tmp_path, preflight):
    control = _feature_control(tmp_path, preflight)
    state = control["patch_candidate_state"]
    assert state["patch_basis"] == PATCH_BASIS_EXPLICIT_CHANGE_REQUEST
    assert state["defect_established"] is False
    assert state["defect_grounded"] is False
    assert state["write_authority"] is False


def test_explicit_feature_reaches_safety_human_handoff_without_auto_write(
    tmp_path, monkeypatch
):
    control = _feature_control(tmp_path)
    block = _feature_plan()
    control_engine.enforce_control_grounding_on_payload(control, block)
    assert block["patch_basis"] == PATCH_BASIS_EXPLICIT_CHANGE_REQUEST
    assert block["target_source_grounded"] is True
    assert block["eligible_for_patch_safety_handoff"] is True

    policy = build_patch_policy(
        "vibe", language="python", patch_confidence=1.0, patch_basis=block["patch_basis"]
    )
    assert policy.patch_basis_accepted is True
    assert policy.auto_apply_allowed is False
    assert policy.human_approval_required is True

    state = _state(
        tmp_path,
        control,
        block,
        user_input="Add task priority support across model/store/CLI.",
        intent="feature_add",
        style="vibe",
    )
    _disable_persistence(monkeypatch)
    pipeline.maybe_run_auto_patch(state, interactive=False)
    assert state.patch_policy["patch_safety"]["ok"] is True
    assert state.patch_policy["write_authority"] is False
    assert state.patch_policy["human_approval_required"] is True
    assert (tmp_path / "model.py").read_text(encoding="utf-8") == "PRIORITY = 0\n"


def test_feature_unrelated_acquired_target_is_rejected_by_preserved_scope(tmp_path):
    control = _feature_control(tmp_path)
    _write(tmp_path, "unrelated.py", "VALUE = 0\n")
    control["related_snippets"].append(
        {"file": "unrelated.py", "symbol": "VALUE", "snippet": "VALUE = 0\n"}
    )
    block = {
        "patch_plan": [
            {
                "op": "replace_snippet",
                "file": "unrelated.py",
                "target_snippet": "VALUE = 0",
                "patched_snippet": "VALUE = 1",
            }
        ],
        "confidence": 1.0,
        "needs_escalation": False,
    }
    control_engine.enforce_control_grounding_on_payload(control, block)
    assert block["patch_basis"] == PATCH_BASIS_EXPLICIT_CHANGE_REQUEST
    assert block["target_source_grounded"] is True
    assert block["change_scope_grounded"] is False
    assert block["patch_plan"] is None


def test_explicit_change_does_not_authorize_arbitrary_new_path(tmp_path):
    control = _feature_control(tmp_path)
    block = {
        "patch_plan": [
            {"op": "create_file", "file": "surprise.py", "content": "VALUE = 1\n"}
        ],
        "confidence": 1.0,
        "needs_escalation": False,
    }
    control_engine.enforce_control_grounding_on_payload(control, block)
    assert block["patch_basis"] == PATCH_BASIS_EXPLICIT_CHANGE_REQUEST
    assert block["target_source_grounded"] is False
    assert block["write_authority"] is False
    assert block["patch_plan"] is None


def test_analysis_and_clarification_routes_have_no_legitimate_patch_basis(tmp_path):
    _write(tmp_path, "calc.py", "def add(a, b):\n    return a + b\n")
    analysis = _control(
        tmp_path,
        ["calc.py::add"],
        route=route_live_task(
            "Explain how validation works.", repository_available=True
        ).as_dict(),
    )["patch_candidate_state"]
    clarification = _control(
        tmp_path,
        ["calc.py::add"],
        route=route_live_task("Improve the agent.", repository_available=True).as_dict(),
    )["patch_candidate_state"]
    assert analysis["patch_basis"] == PATCH_BASIS_NONE
    assert clarification["patch_basis"] == PATCH_BASIS_NONE
    assert analysis["eligible_for_patch_safety_handoff"] is False
    assert clarification["eligible_for_patch_safety_handoff"] is False


def test_defect_claim_with_passing_validation_and_model_confidence_cannot_ground(tmp_path):
    _write(tmp_path, "calc.py", "def add(a, b):\n    return a + b\n")
    control = _control(
        tmp_path,
        ["calc.py::add"],
        route=_defect_route(),
        preflight={
            "ran": True,
            "ok": True,
            "outcome": "passed",
            "category": "passed",
            "command": "python -m pytest",
            "output": "1 passed",
            "locations": [{"file": "calc.py", "line": 2}],
        },
    )
    assert control["top_hypothesis"]["confidence"] == 0.99
    assert control["patch_candidate_state"]["patch_basis"] == PATCH_BASIS_UNRESOLVED
    block = {
        "patch_candidate": {
            "file": "calc.py",
            "target_snippet": "return a + b",
            "patched_snippet": "return a - b",
        },
        "confidence": 1.0,
        "needs_escalation": False,
    }
    control_engine.enforce_control_grounding_on_payload(control, block)
    assert block["patch_candidate"] is None


def test_patch_policy_accepts_both_bases_but_only_defect_basis_can_auto_apply():
    defect = build_patch_policy(
        "safe_minimal",
        language="python",
        patch_confidence=0.9,
        patch_basis=PATCH_BASIS_GROUNDED_DEFECT,
    )
    feature = build_patch_policy(
        "safe_minimal",
        language="python",
        patch_confidence=1.0,
        patch_basis=PATCH_BASIS_EXPLICIT_CHANGE_REQUEST,
    )
    none = build_patch_policy(
        "safe_minimal", language="python", patch_confidence=1.0
    )
    assert defect.patch_basis_accepted is True
    assert defect.auto_apply_allowed is True
    assert feature.patch_basis_accepted is True
    assert feature.auto_apply_allowed is False
    assert none.patch_basis_accepted is False
    assert none.auto_apply_allowed is False


def test_historical_grounding_projects_only_with_retained_exact_failure_proof(
    tmp_path,
):
    _write(tmp_path, "calc.py", "def add(a, b):\n    return a - b\n")
    control = _control(tmp_path, ["calc.py::add"])
    control["patch_candidate_state"].update(
        {
            "defect_grounded": True,
            "exact_source_grounded": True,
            "defect_grounding": [
                {
                    "kind": "executed_validation_failure",
                    "file": "calc.py",
                    "line": 2,
                }
            ],
            "failure_binding_kind": FAILURE_BINDING_DIRECT_LOCATION,
        }
    )
    control_engine.refresh_control_safety(control)
    assert control["patch_candidate_state"]["patch_basis"] == PATCH_BASIS_GROUNDED_DEFECT

    control["preflight_validation"] = None
    control["patch_candidate_state"] = {
        "defect_grounded": True,
        "exact_source_grounded": True,
        "defect_grounding": [],
    }
    control_engine.refresh_control_safety(control)
    assert control["patch_candidate_state"]["patch_basis"] == PATCH_BASIS_NONE


def test_binding_runtime_has_no_model_network_traversal_or_graph_input():
    source = inspect.getsource(__import__("core.patch_basis", fromlist=["*"]))
    tree = ast.parse(source)
    forbidden_calls = {
        "glob",
        "iglob",
        "rglob",
        "urlopen",
        "request",
        "run_gemini_request",
        "run_gemini_request_2",
        "build_graph_from_repo",
        "trace_execution_flow",
    }
    assert not any(
        isinstance(node, ast.Call)
        and (
            isinstance(node.func, ast.Name)
            and node.func.id in forbidden_calls
            or isinstance(node.func, ast.Attribute)
            and node.func.attr in forbidden_calls
        )
        for node in ast.walk(tree)
    )
