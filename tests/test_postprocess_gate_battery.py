from __future__ import annotations

import ast
import copy
import importlib
import json
import sys
from pathlib import Path

from core.agent_state import AgentState


ROOT = Path(__file__).resolve().parents[1]

INLINE_GATE_CALLS = {
    "collect_patch_repair_reasons",
    "normalize_patch_plan_schema",
    "promote_go_missing_import_candidate_to_patch_plan",
    "promote_ts_duplicate_import_candidate_to_patch_plan",
    "promote_ts_missing_import_candidate_to_patch_plan",
    "reject_ungrounded_candidate_quotes",
    "reject_ungrounded_patch",
    "retry_structured_patch_json",
}


def _make_state(
    *,
    json_block: dict | None,
    repo_path: str | None = None,
    mode: str = "reviewer",
    language: str = "python",
    control_result: dict | None = None,
) -> AgentState:
    return AgentState(
        interface="cli",
        mode=mode,
        user_input="fix the bug",
        file_paths=[repo_path] if repo_path else [],
        primary_file=None,
        input_mode="repo",
        language=language,
        task_type="patch",
        repo_path=repo_path,
        project_tag="test",
        json_block=json_block,
        control_result=control_result,
    )


def _called_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    calls: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            calls.add(node.func.id)
    return calls


def test_shared_helper_importable_without_flask_web_dependencies():
    sys.modules.pop("core.postprocess_gates", None)
    before = set(sys.modules)

    module = importlib.import_module("core.postprocess_gates")

    imported = set(sys.modules) - before
    assert hasattr(module, "run_postprocess_gate_battery")
    assert "flask" not in imported
    assert "web.app" not in imported
    assert "web.runner" not in imported


def test_helper_ast_import_guard():
    source = (ROOT / "core" / "postprocess_gates.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden_roots = {
        "agents",
        "benchmarks",
        "database",
        "docker",
        "flask",
        "subprocess",
        "web",
    }
    offenders: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root in forbidden_roots:
                    offenders.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = module.split(".", 1)[0]
            if root in forbidden_roots:
                offenders.append(module)

    assert offenders == []


def test_safe_state_passes_through_without_mutation():
    from core.postprocess_gates import run_postprocess_gate_battery

    block = {
        "summary": "no patch needed",
        "issues": [],
        "patch_candidate": None,
        "patch_plan": None,
        "confidence": 0.9,
        "needs_escalation": False,
    }
    original = copy.deepcopy(block)
    state = _make_state(json_block=block)
    state.final_answer = json.dumps(block)

    run_postprocess_gate_battery(
        state,
        reviewed_answer=state.final_answer,
        retry_structured_patch_json_fn=lambda *_args: (_ for _ in ()).throw(
            AssertionError("safe state should not retry")
        ),
    )

    assert state.json_block == original


def test_ungrounded_patch_gets_rejected_by_shared_helper(tmp_path):
    from core.postprocess_gates import run_postprocess_gate_battery

    block = {
        "summary": "fix",
        "issues": [],
        "patch_candidate": {
            "relative_path": "missing.py",
            "target_node_name": "run",
            "target_snippet": "def run():\n    return 1",
            "patched_snippet": "def run():\n    return 2",
        },
        "patch_plan": None,
        "confidence": 0.9,
        "needs_escalation": False,
    }
    state = _make_state(json_block=block, repo_path=str(tmp_path))

    run_postprocess_gate_battery(state)

    patch = state.json_block["patch_candidate"]
    assert patch["rejected"] is True
    assert "does not exist" in patch["reject_reason"]
    assert state.json_block["confidence"] == 0.0
    assert state.json_block["needs_escalation"] is True


def test_ungrounded_candidate_quotes_get_rejected_by_shared_helper():
    from core.postprocess_gates import run_postprocess_gate_battery

    block = {
        "summary": "fix",
        "issues": [],
        "patch_candidate": {
            "relative_path": "report.py",
            "target_node_name": "build_report",
            "target_snippet": "for row in invented_rows:",
            "patched_snippet": "for row in rows:",
        },
        "patch_plan": None,
        "confidence": 0.9,
        "needs_escalation": False,
    }
    control = {
        "patch_intent": {
            "target_file": "report.py",
            "source_snippet": "def build_report(rows):\n    return list(rows)\n",
        }
    }
    state = _make_state(json_block=block, control_result=control)

    run_postprocess_gate_battery(state)

    patch = state.json_block["patch_candidate"]
    assert patch["rejected"] is True
    assert "not found in source" in patch["reject_reason"]
    assert state.json_block["patch_plan"] is None
    assert state.json_block["confidence"] == 0.0
    assert state.json_block["needs_escalation"] is True


def test_patch_plan_schema_normalization_still_occurs():
    from core.postprocess_gates import run_postprocess_gate_battery

    block = {
        "summary": "fix",
        "issues": [],
        "patch_candidate": None,
        "patch_plan": [
            {
                "action": "replace",
                "file": "app.py",
                "target_snippet": "old",
                "patched_snippet": "new",
            }
        ],
        "confidence": 0.8,
        "needs_escalation": False,
    }
    state = _make_state(json_block=block, repo_path=None)

    run_postprocess_gate_battery(state)

    op = state.json_block["patch_plan"][0]
    assert op["op"] == "replace_snippet"
    assert op["relative_path"] == "app.py"
    assert "action" not in op
    assert "file" not in op


def test_no_json_repair_uses_injected_retry_and_finalize_callbacks():
    from core.postprocess_gates import run_postprocess_gate_battery

    state = _make_state(json_block=None, mode="reviewer")
    state.final_answer = "not json"
    calls: list[str] = []

    def retry(_state: AgentState, bad_answer: str) -> str:
        calls.append(bad_answer)
        return json.dumps({
            "summary": "repaired",
            "patch_candidate": None,
            "patch_plan": None,
        })

    def finalize(target: AgentState, answer: str) -> None:
        target.final_answer = answer
        target.json_block = json.loads(answer)
        target.human_answer = answer

    run_postprocess_gate_battery(
        state,
        reviewed_answer="raw reviewed answer",
        retry_structured_patch_json_fn=retry,
        finalize_answer_fn=finalize,
    )

    assert calls == ["raw reviewed answer"]
    assert state.json_block["summary"] == "repaired"


def test_patch_issue_retry_runs_only_when_repair_reasons_exist():
    from core.postprocess_gates import run_postprocess_gate_battery

    broken = {
        "summary": "fix",
        "issues": [],
        "patch_candidate": {
            "relative_path": "main.go",
            "target_snippet": "func main() {}",
            "patched_snippet": "func main() {",
        },
        "patch_plan": None,
        "confidence": 0.9,
        "needs_escalation": False,
    }
    repaired = {
        "summary": "repaired",
        "issues": [],
        "patch_candidate": None,
        "patch_plan": None,
        "confidence": 0.8,
        "needs_escalation": False,
    }
    calls: list[str] = []

    def retry(_state: AgentState, bad_answer: str) -> str:
        calls.append(bad_answer)
        return json.dumps(repaired)

    def finalize(target: AgentState, answer: str) -> None:
        target.final_answer = answer
        target.json_block = json.loads(answer)
        target.human_answer = answer

    state = _make_state(json_block=broken, mode="planner", language="go")
    state.final_answer = json.dumps(broken)
    run_postprocess_gate_battery(
        state,
        retry_structured_patch_json_fn=retry,
        finalize_answer_fn=finalize,
    )

    assert len(calls) == 1
    assert "STRUCTURAL ERROR" in calls[0]
    assert state.json_block["summary"] == "repaired"

    safe_state = _make_state(json_block=copy.deepcopy(repaired), mode="planner")
    safe_state.final_answer = json.dumps(repaired)
    run_postprocess_gate_battery(
        safe_state,
        retry_structured_patch_json_fn=lambda *_args: (_ for _ in ()).throw(
            AssertionError("safe state should not retry")
        ),
    )


def test_import_promotion_gates_still_run_in_existing_order(monkeypatch):
    from core.postprocess_gates import run_postprocess_gate_battery
    import patching.patch_gates as gates

    calls: list[str] = []
    monkeypatch.setattr(
        gates,
        "promote_go_missing_import_candidate_to_patch_plan",
        lambda _state: calls.append("go"),
    )
    monkeypatch.setattr(
        gates,
        "promote_ts_duplicate_import_candidate_to_patch_plan",
        lambda _state: calls.append("ts_duplicate"),
    )
    monkeypatch.setattr(
        gates,
        "promote_ts_missing_import_candidate_to_patch_plan",
        lambda _state: calls.append("ts_missing"),
    )
    monkeypatch.setattr(
        gates,
        "collect_patch_repair_reasons",
        lambda _state: calls.append("collect_repair_reasons") or [],
    )
    monkeypatch.setattr(
        gates,
        "normalize_patch_plan_schema",
        lambda _state: calls.append("normalize"),
    )
    monkeypatch.setattr(
        gates,
        "reject_ungrounded_patch",
        lambda _state: calls.append("reject_patch"),
    )
    monkeypatch.setattr(
        gates,
        "reject_ungrounded_candidate_quotes",
        lambda _state: calls.append("reject_quotes"),
    )

    state = _make_state(json_block={"summary": "safe", "patch_plan": None})

    run_postprocess_gate_battery(state)

    assert calls == [
        "go",
        "ts_duplicate",
        "ts_missing",
        "collect_repair_reasons",
        "ts_duplicate",
        "ts_missing",
        "ts_duplicate",
        "ts_missing",
        "normalize",
        "reject_patch",
        "reject_quotes",
    ]


def test_cli_path_uses_shared_helper():
    calls = _called_names(ROOT / "main.py")

    assert "run_postprocess_gate_battery" in calls
    assert calls.isdisjoint(INLINE_GATE_CALLS)


def test_web_runner_path_uses_shared_helper():
    calls = _called_names(ROOT / "web" / "runner.py")

    assert "run_postprocess_gate_battery" in calls
    assert calls.isdisjoint(INLINE_GATE_CALLS)
