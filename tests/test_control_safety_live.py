"""CONTROL.SAFETY.LIVE.1 production localization/authority regressions."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from core import control_engine, pipeline
from core.agent_state import AgentState
from core.postprocess_gates import run_postprocess_gate_battery
from core.preflight import run_preflight_validation
from graph.schema import ProgramGraph
from policy.decision_helper import build_patch_policy


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _evidence(
    symbol: str,
    score: float,
    *,
    query_bonus: float = 1.0,
    called_by: list[str] | None = None,
    calls: list[str] | None = None,
    depth: int = 0,
) -> dict:
    return {
        "symbol": symbol,
        "score": score,
        "query_bonus": query_bonus,
        "called_by": called_by or [],
        "calls": calls or [],
        "impact": [],
        "risk": {"risk_level": "low", "risk_score": 0},
        "graph_weight": max(0.0, score - 1.0),
        "depth": depth,
    }


def _production_control(
    monkeypatch: pytest.MonkeyPatch,
    repo: Path,
    query: str,
    evidence: list[dict],
    *,
    execution_trace: str = "",
) -> dict:
    """Exercise run_control_structured while fixing only retrieval inputs."""
    graph = ProgramGraph()
    for item in evidence:
        graph.add_node(item["symbol"], "function")
    monkeypatch.setattr(control_engine, "get_cached_graph", lambda *a, **k: graph)
    monkeypatch.setattr(
        control_engine,
        "select_entry_nodes",
        lambda **kwargs: [item["symbol"] for item in evidence[:6]],
    )
    monkeypatch.setattr(
        control_engine,
        "control_dfs_v2",
        lambda **kwargs: [dict(item) for item in evidence],
    )
    monkeypatch.setattr(
        control_engine,
        "trace_execution_flow",
        lambda **kwargs: execution_trace,
    )
    monkeypatch.setattr(
        control_engine, "load_phantom_limb_report", lambda repo_path: {}
    )
    return control_engine.run_control_structured(query, str(repo), graph=graph)


def _failed_preflight(
    relative_file: str,
    *,
    category: str = "assertion_failure",
    locations: list[dict] | None = None,
) -> dict:
    return {
        "ran": True,
        "ok": False,
        "outcome": "failed",
        "category": category,
        "command": "python -m pytest",
        "output": f'failure at "{relative_file}":12',
        "locations": locations
        if locations is not None
        else [{"kind": "stack_frame", "file": relative_file, "line": 12}],
    }


def _state(repo: Path, control: dict, block: dict) -> AgentState:
    return AgentState(
        interface="agent",
        mode="reviewer",
        user_input="Fix the grounded failure.\nValidation command: python calc.py",
        file_paths=[str(repo)],
        primary_file=None,
        input_mode="error_log",
        language="python",
        task_type="bug_fix",
        task_info={
            "intent": "bug_fix",
            "complexity": "simple",
            "language": "python",
            "patch_style": "safe_minimal",
        },
        is_project_input=True,
        repo_path=str(repo),
        control_result=control,
        json_block=block,
    )


def test_real_control_high_rank_without_grounding_is_localization_only(
    tmp_path, monkeypatch
):
    _write(
        tmp_path,
        "tests/produced-files.client.spec.tsx",
        "export function at() { return 1; }\n",
    )
    result = _production_control(
        monkeypatch,
        tmp_path,
        "Compare the client architecture and produced files",
        [
            _evidence(
                "tests/produced-files.client.spec.tsx::at",
                279.23,
                called_by=["client.ts::run"],
                calls=["state.ts::read"],
            )
        ],
        execution_trace="at appears in execution/state trace",
    )

    top = result["top_hypothesis"]
    assert top["symbol"].endswith("::at")
    assert top["localization_score"] > 250
    assert top["confidence"] == 0.95
    assert top["confidence_kind"] == "localization_rank_legacy"
    assert top["legacy_control_confidence_deprecated"] is True
    assert top["defect_established"] is False
    assert top["recommended_action"] == "inspect_candidate"
    assert top["needs_escalation"] is True
    state = result["patch_candidate_state"]
    assert state["defect_established"] is False
    assert state["patch_eligibility_granted"] is False
    assert state["auto_patch_candidate_allowed"] is False
    assert state["write_authority"] is False

    prompt = control_engine.build_control_prompt(result, result["query"])
    assert "highest_ranked_candidate=" in prompt
    assert "relative navigation heuristic" in prompt
    assert "defect_established=False" in prompt
    assert "Set patch_candidate=null" in prompt
    assert "confidence=0.95" not in prompt


def test_cattus_self_bug_wrong_topology_target_cannot_mint_authority(
    tmp_path, monkeypatch
):
    _write(
        tmp_path,
        "core/code_dna.py",
        "def _classify_indent(lines):\n    return 4\n",
    )
    _write(
        tmp_path,
        "tests/test_index_completion.py",
        "def write_text(path, text):\n    return path.write_text(text)\n",
    )
    result = _production_control(
        monkeypatch,
        tmp_path,
        "Two-space repositories receive four-space patches",
        [
            _evidence(
                "tests/test_index_completion.py::write_text",
                1279.78,
                called_by=[f"caller_{index}" for index in range(30)],
            ),
            _evidence("core/code_dna.py::_classify_indent", 14.0),
        ],
    )

    assert result["top_hypothesis"]["symbol"].endswith("::write_text")
    assert result["top_hypothesis"]["localization_score"] > 1000
    assert result["patch_candidate_state"]["defect_established"] is False
    assert result["decision"]["auto_patch_candidate_allowed"] is False

    wrong_patch = {
        "patch_candidate": {
            "relative_path": "tests/test_index_completion.py",
            "target_node_name": "write_text",
            "target_snippet": "def write_text(path, text):\n    return path.write_text(text)",
            "patched_snippet": "def write_text(path, text):\n  return path.write_text(text)",
        },
        "confidence": 0.99,
        "needs_escalation": False,
    }
    control_engine.enforce_control_grounding_on_payload(result, wrong_patch)
    assert wrong_patch["patch_candidate"] is None
    assert wrong_patch["confidence"] == 0.0
    assert wrong_patch["needs_escalation"] is True


def test_lower_ranked_exact_failure_target_becomes_grounded_candidate_not_authority(
    tmp_path, monkeypatch
):
    _write(tmp_path, "central.py", "def central():\n    return 'ok'\n")
    _write(tmp_path, "calc.py", "def add(a, b):\n    return a - b\n")
    result = _production_control(
        monkeypatch,
        tmp_path,
        "Fix the failing add assertion",
        [
            _evidence("central.py::central", 500.0, called_by=["a", "b", "c"]),
            _evidence("calc.py::add", 8.0, query_bonus=1),
        ],
    )
    control_engine.attach_preflight_validation(
        result, _failed_preflight("calc.py")
    )

    assert result["top_hypothesis"]["symbol"] == "central.py::central"
    assert result["grounded_hypothesis"]["symbol"] == "calc.py::add"
    assert result["patch_intent"]["target_file"] == "calc.py"
    assert result["patch_intent"]["source_snippet"].startswith("def add")
    state = result["patch_candidate_state"]
    assert state["defect_established"] is True
    assert state["exact_source_grounded"] is True
    assert state["eligible_for_patch_safety_handoff"] is True
    assert state["patch_eligibility_granted"] is False
    assert state["auto_patch_candidate_allowed"] is False
    assert state["write_authority"] is False


def test_test_file_can_be_legitimately_grounded_without_test_file_authority_rule(
    tmp_path, monkeypatch
):
    _write(
        tmp_path,
        "tests/test_contract.py",
        "def broken_contract():\n    assert False\n",
    )
    result = _production_control(
        monkeypatch,
        tmp_path,
        "Fix the failing contract assertion",
        [_evidence("tests/test_contract.py::broken_contract", 9.0)],
    )
    control_engine.attach_preflight_validation(
        result, _failed_preflight("tests/test_contract.py")
    )

    assert result["patch_candidate_state"]["defect_established"] is True
    assert result["patch_intent"]["target_file"] == "tests/test_contract.py"
    assert result["patch_candidate_state"]["write_authority"] is False


@pytest.mark.parametrize(
    "preflight",
    [
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
            "outcome": "inconclusive",
            "category": "no_tests_collected",
            "command": "python -m pytest",
            "output": "calc.py: no tests ran",
            "locations": [],
        },
        {
            "ran": True,
            "ok": False,
            "outcome": "inconclusive",
            "category": "validation_tool_unavailable",
            "command": "npm run test",
            "output": "calc.py: npm unavailable",
            "locations": [],
        },
        {
            "ran": True,
            "ok": True,
            "outcome": "passed",
            "category": "passed",
            "command": "python calc.py",
            "output": "calc.py: passed",
            "locations": [{"file": "calc.py", "line": 1}],
        },
    ],
)
def test_command_pass_or_inconclusive_validation_never_grounds(
    tmp_path, monkeypatch, preflight
):
    _write(tmp_path, "calc.py", "def add(a, b):\n    return a + b\n")
    result = _production_control(
        monkeypatch,
        tmp_path,
        "Inspect add",
        [_evidence("calc.py::add", 999.0)],
    )
    control_engine.attach_preflight_validation(result, preflight)
    assert result["patch_candidate_state"]["defect_established"] is False
    assert result["patch_candidate_state"]["eligible_for_patch_safety_handoff"] is False


def test_historical_artifact_remains_readable_but_unsafe_action_is_legacy_only(
    tmp_path,
):
    _write(tmp_path, "old.py", "def old():\n    return 1\n")
    historical = {
        "query": "old run",
        "repo_path": str(tmp_path),
        "top_hypothesis": {
            "symbol": "old.py::old",
            "score": 100.0,
            "confidence": 0.95,
            "recommended_action": "auto_patch_candidate_allowed",
            "reasons": ["has upstream callers"],
            "likely_issue": "unknown_logic_issue",
        },
        # Persisted JSON does not retain object identity between the repeated
        # top_hypothesis projection and hypotheses list.
        "hypotheses": [
            {
                "symbol": "old.py::old",
                "score": 100.0,
                "confidence": 0.95,
                "recommended_action": "auto_patch_candidate_allowed",
                "reasons": ["has upstream callers"],
                "likely_issue": "unknown_logic_issue",
            }
        ],
        "evidence": [],
    }
    control_engine.refresh_control_safety(historical)
    assert len(historical["hypotheses"]) == 1
    top = historical["top_hypothesis"]
    assert top["confidence"] == 0.95
    assert top["confidence_kind"] == "localization_rank_legacy"
    assert top["legacy_recommended_action"] == "auto_patch_candidate_allowed"
    assert top["recommended_action"] == "inspect_candidate"
    assert historical["decision"]["auto_patch_candidate_allowed"] is False


def test_human_prompt_does_not_claim_ranked_candidate_is_a_bug_without_grounding(
    tmp_path, monkeypatch
):
    _write(tmp_path, "candidate.py", "def candidate():\n    return 1\n")
    control = _production_control(
        monkeypatch,
        tmp_path,
        "Explain the suspicious behavior",
        [_evidence("candidate.py::candidate", 999.0)],
    )
    prompt = control_engine.build_control_prompt_human(control, control["query"])
    assert "no defect has been established" in prompt
    assert "Do not claim an exact problematic line" in prompt


def test_postprocess_removes_model_patch_when_control_has_no_grounding(
    tmp_path, monkeypatch
):
    _write(tmp_path, "wrong.py", "def wrong():\n    return 1\n")
    control = _production_control(
        monkeypatch,
        tmp_path,
        "Explain the architecture",
        [_evidence("wrong.py::wrong", 999.0)],
    )
    block = {
        "patch_candidate": {
            "relative_path": "wrong.py",
            "target_node_name": "wrong",
            "target_node_kind": "function",
            "target_snippet": "def wrong():\n    return 1",
            "patched_snippet": "def wrong():\n    return 2",
        },
        "patch_plan": None,
        "confidence": 0.99,
        "needs_escalation": False,
        "issues": [],
    }
    state = _state(tmp_path, control, block)
    run_postprocess_gate_battery(state)
    assert state.json_block["patch_candidate"] is None
    assert state.json_block["control_patch_candidate_rejected"] is True
    assert state.json_block["needs_escalation"] is True


def test_auto_patch_disabled_is_monotonic_even_for_high_rank(
    tmp_path, monkeypatch, capsys
):
    _write(tmp_path, "wrong.py", "def wrong():\n    return 1\n")
    control = _production_control(
        monkeypatch,
        tmp_path,
        "Fix wrong",
        [_evidence("wrong.py::wrong", 999.0)],
    )
    block = {
        "patch_candidate": {
            "relative_path": "wrong.py",
            "target_node_name": "wrong",
            "target_snippet": "def wrong():\n    return 1",
            "patched_snippet": "def wrong():\n    return 2",
        },
        "confidence": 0.99,
        "needs_escalation": False,
    }
    monkeypatch.setattr(pipeline, "AUTO_PATCH_ENABLED", False)
    pipeline.maybe_run_auto_patch(_state(tmp_path, control, block), interactive=False)
    assert "AUTO_PATCH_ENABLED=false" in capsys.readouterr().out
    assert (tmp_path / "wrong.py").read_text(encoding="utf-8").endswith(
        "return 1\n"
    )


def test_patch_policy_ignores_legacy_control_localization_confidence():
    legacy_only = build_patch_policy(
        "safe_minimal",
        language="python",
        control_confidence=0.99,
    )
    grounded_writer = build_patch_policy(
        "safe_minimal",
        language="python",
        control_confidence=0.01,
        patch_confidence=0.9,
        defect_grounded=True,
    )
    command_only = build_patch_policy(
        "balanced",
        language="typescript",
        has_validation_command=True,
        patch_confidence=0.99,
        defect_grounded=False,
    )
    assert legacy_only.auto_apply_allowed is False
    assert grounded_writer.auto_apply_allowed is True
    assert command_only.auto_apply_allowed is False


def test_static_boundary_has_no_localization_to_patch_authority_edge():
    pipeline_source = inspect.getsource(pipeline)
    policy_source = inspect.getsource(__import__("policy.decision_helper", fromlist=["*"]))
    infer_source = inspect.getsource(control_engine.infer_hypotheses)
    prompt_source = inspect.getsource(control_engine.build_control_prompt)

    assert 'top.get("confidence"' not in pipeline_source
    assert "combined_confidence" not in pipeline_source
    assert "control_confidence >=" not in policy_source
    assert "auto_patch_candidate_allowed" not in infer_source
    assert "confidence={top.get" not in prompt_source

    pipeline_tree = ast.parse(pipeline_source)
    policy_tree = ast.parse(policy_source)
    assert not any(
        isinstance(node, ast.Compare)
        and any(
            isinstance(name, ast.Name) and name.id == "localization"
            for name in ast.walk(node)
        )
        for node in ast.walk(pipeline_tree)
    )
    assert not any(
        isinstance(node, ast.Compare)
        and any(
            isinstance(name, ast.Name) and name.id == "control_confidence"
            for name in ast.walk(node)
        )
        for node in ast.walk(policy_tree)
    )

    control_tree = ast.parse(inspect.getsource(control_engine))
    assert not any(
        isinstance(node, ast.Dict)
        and any(
            isinstance(key, ast.Constant)
            and key.value == "auto_patch_candidate_allowed"
            and isinstance(value, ast.Constant)
            and value.value is True
            for key, value in zip(node.keys, node.values)
        )
        for node in ast.walk(control_tree)
    )

    safety_source = "\n".join(
        inspect.getsource(function)
        for function in (
            control_engine._validation_binding,
            control_engine._source_is_exactly_grounded,
            control_engine.refresh_control_safety,
            control_engine.enforce_control_grounding_on_payload,
        )
    )
    safety_tree = ast.parse(safety_source)
    forbidden_calls = {
        "glob",
        "iglob",
        "rglob",
        "walk",
        "urlopen",
        "request",
        "run_gemini_request",
        "run_gemini_request_2",
    }
    assert not any(
        isinstance(node, ast.Call)
        and (
            isinstance(node.func, ast.Name)
            and node.func.id in forbidden_calls
            or isinstance(node.func, ast.Attribute)
            and node.func.attr in forbidden_calls
        )
        for node in ast.walk(safety_tree)
    )


def test_calc_real_failure_control_patch_safety_apply_and_validation(
    tmp_path, monkeypatch
):
    original = (
        "def add(a, b):\n"
        "    return a - b\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    assert add(2, 3) == 5\n"
    )
    _write(tmp_path, "calc.py", original)
    control = _production_control(
        monkeypatch,
        tmp_path,
        "Fix calc.py add; its real assertion fails",
        [_evidence("calc.py::add", 8.0)],
    )
    preflight = run_preflight_validation(
        str(tmp_path), "python", command="python calc.py"
    )
    assert preflight["category"] == "assertion_failure"
    control_engine.attach_preflight_validation(control, preflight)
    assert control["patch_candidate_state"]["defect_established"] is True
    assert control["patch_candidate_state"]["exact_source_grounded"] is True

    target = control["patch_intent"]["source_snippet"]
    patched = target.replace("return a - b", "return a + b")
    block = {
        "summary": "Use addition for add.",
        "issues": [],
        "patch_candidate": {
            "relative_path": "calc.py",
            "file": "calc.py",
            "target_node_name": "add",
            "target_node_kind": "function",
            "target_snippet": target,
            "patched_snippet": patched,
        },
        "patch_plan": None,
        # Model patch confidence is separate from CONTROL localization.
        "confidence": 0.95,
        "needs_escalation": False,
    }
    state = _state(tmp_path, control, block)
    run_postprocess_gate_battery(state)
    assert isinstance(state.json_block["patch_candidate"], dict)

    monkeypatch.setattr(pipeline, "get_tooling_profile", lambda *a, **k: {})
    monkeypatch.setattr(pipeline, "upsert_tooling_profile", lambda *a, **k: None)
    monkeypatch.setattr(pipeline, "save_patch_attempt", lambda *a, **k: None)
    monkeypatch.setattr(pipeline, "save_engineering_memory", lambda *a, **k: None)
    monkeypatch.setattr(pipeline, "refresh_memory_block", lambda *a, **k: None)
    monkeypatch.setattr(pipeline, "AUTO_PATCH_ENABLED", True)
    pipeline.maybe_run_auto_patch(state, interactive=False)

    assert "return a + b" in (tmp_path / "calc.py").read_text(encoding="utf-8")
    final_validation = run_preflight_validation(
        str(tmp_path), "python", command="python calc.py"
    )
    assert final_validation["outcome"] == "passed"
