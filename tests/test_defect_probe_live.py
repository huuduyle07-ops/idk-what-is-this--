"""DEFECT.PROBE.LIVE.1 — bounded reproduction and anti-circularity matrix."""

from __future__ import annotations

from dataclasses import replace
import inspect
import os
from pathlib import Path
import py_compile
from types import SimpleNamespace

from core.code_dna import _classify_indent
import core.candidate_defect_probe as candidate_probe
import core.pipeline as pipeline
import core.targeted_repository_validation as targeted_validation
from core.agent_state import AgentState
from core.candidate_defect_probe import (
    CLOSURE_CHANGED_BUT_UNRESOLVED,
    CLOSURE_FIXED,
    CLOSURE_INCONCLUSIVE,
    CLOSURE_INVALID_COMPARISON,
    CLOSURE_STILL_REPRODUCED,
    CLOSURE_UNAVAILABLE,
    candidate_defect_closure_is_current,
    candidate_defect_probe_guardrails,
    evaluate_candidate_defect_closure,
)
from core.check_oracle_assessment import (
    CHECK_FAILED,
    ROLE_DEFECT_PRESERVATION_ORACLE,
    assess_selected_check_oracles,
)
from core.control_engine import (
    attach_preflight_validation,
    build_control_result,
)
from core.defect_probe import (
    EXECUTION_STAGE_POST_PATCH,
    EXPECTATION_BASIS_EXPLICIT_USER,
    EXPECTATION_BASIS_MODEL_AUTHORED,
    EXPECTATION_BASIS_REPOSITORY_CONTRACT,
    INPUT_BASIS_EXPLICIT_USER,
    INPUT_BASIS_MODEL_AUTHORED,
    INPUT_BASIS_REPOSITORY_CONTRACT,
    PROBE_BASIS_EXPLICIT_USER,
    PROBE_BASIS_MODEL_AUTHORED,
    PROBE_BASIS_REPOSITORY_CONTRACT,
    PROBE_BASIS_TASK_FACT_ADAPTER,
    PROBE_INCONCLUSIVE,
    PROBE_INVALID,
    PROBE_NOT_REPRODUCED,
    PROBE_REPRODUCED,
    PROBE_UNAVAILABLE,
    build_existing_pytest_probe,
    build_probe_target_binding,
    build_python_function_probe,
    defect_probe_guardrails,
    derive_control_defect_probe_contract,
    derive_indentation_probe_from_preserved_task,
    execute_defect_probe,
    maybe_execute_control_defect_probe,
    reproduced_probe_target,
)
from core.live_task_routing import safe_route_live_task
from core.execution_eligibility_policy import (
    ELIGIBLE,
    INELIGIBLE,
    PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW,
    PROFILE_FULL_VALIDATION_REQUIRED,
    evaluate_execution_eligibility,
)
from core.patch_safety import evaluate_patch_safety
from core.patch_basis import (
    PATCH_BASIS_EXPLICIT_CHANGE_REQUEST,
    PATCH_BASIS_GROUNDED_DEFECT,
)
from core.validation_execution import SafeValidationResult
from core.validation_outcome import VALIDATION_FAILED, VALIDATION_PASSED
from graph.schema import build_graph


ROOT = Path(__file__).resolve().parents[1]
T6_QUERY = "2-space indentation is classified as 4-space"
T6_DEFECT_TASK = "Fix this bug: 2-space indentation is classified as 4-space"
T6_TARGET = "core/code_dna.py::_classify_indent"


def _write(root: Path, relative: str, text: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _binding(
    root: Path,
    *,
    relative: str = "calc.py",
    symbol: str = "add",
    source: str = "def add(a, b):\n    return a + b\n",
):
    path = root / relative
    if not path.exists():
        _write(root, relative, source)
    return build_probe_target_binding(
        repo_path=root,
        target_file=relative,
        target_symbol=symbol,
        source_snippet=source.strip(),
        candidate_eligible=True,
    )


def _contract(root: Path, *, expected=4, expectation_source_paths=()):
    binding = _binding(root)
    assert binding is not None
    return build_python_function_probe(
        target=binding,
        args=(2, 2),
        expected=expected,
        probe_basis=PROBE_BASIS_REPOSITORY_CONTRACT,
        input_basis=INPUT_BASIS_REPOSITORY_CONTRACT,
        expected_behavior_basis=EXPECTATION_BASIS_REPOSITORY_CONTRACT,
        provenance_reference="repository contract: add returns the arithmetic sum",
        expectation_source_paths=expectation_source_paths,
    )


def _inconclusive_preflight(category: str = "validation_budget_exhausted") -> dict:
    return {
        "ran": True,
        "ok": False,
        "outcome": "inconclusive",
        "category": category,
        "command": "python -m pytest",
        "output": "validation budget exhausted after 30s",
        "locations": [],
        "timed_out": category == "validation_budget_exhausted",
        "timeout_seconds": 30,
        "validation_budget_exhausted": category == "validation_budget_exhausted",
    }


def _failed_preflight(relative: str) -> dict:
    return {
        "ran": True,
        "ok": False,
        "outcome": "failed",
        "category": "assertion_failure",
        "command": "python -m pytest",
        "output": f"{relative}:1: assertion failed",
        "locations": [
            {"kind": "pytest_failure", "file": relative, "line": 1, "col": 1}
        ],
    }


def _control(query: str, root: Path, target: str) -> dict:
    evidence = [
        {
            "symbol": target,
            "score": 14.0,
            "query_bonus": 1.0,
            "called_by": [],
            "calls": [],
            "impact": [],
            "risk": {"risk_level": "low", "risk_score": 0},
            "graph_weight": 13.0,
            "depth": 0,
        }
    ]
    result = build_control_result(
        query,
        str(root),
        [target],
        evidence,
        "",
        entry_resolution={"resolved_entry_nodes": [target]},
    )
    result["live_route"] = safe_route_live_task(
        query, repository_available=True
    ).as_dict()
    return result


def test_deterministic_typed_pure_function_probe_reproduces_behavior(tmp_path):
    _write(tmp_path, "calc.py", "def add(a, b):\n    return a - b\n")
    binding = _binding(
        tmp_path,
        source="def add(a, b):\n    return a - b\n",
    )
    assert binding is not None
    contract = build_python_function_probe(
        target=binding,
        args=(2, 2),
        expected=4,
        probe_basis=PROBE_BASIS_REPOSITORY_CONTRACT,
        input_basis=INPUT_BASIS_REPOSITORY_CONTRACT,
        expected_behavior_basis=EXPECTATION_BASIS_REPOSITORY_CONTRACT,
        provenance_reference="repository specification: add returns a+b",
    )

    receipt = execute_defect_probe(contract, repo_path=tmp_path)

    assert receipt.probe_result == PROBE_REPRODUCED, receipt.as_dict()
    assert receipt.observed == 0
    assert receipt.expected == 4
    assert receipt.freshness == "current_source_isolated_bytecode_cache"
    assert reproduced_probe_target(receipt.as_dict()) == {
        "file": "calc.py",
        "symbol": "add",
        "relation": "bounded_reproduction_bound",
    }


def test_explicit_user_reproducer_is_labeled_as_user_requirement_not_objective_truth(
    tmp_path,
):
    contract = _contract(tmp_path, expected=5)
    contract = replace(
        contract,
        probe_basis=PROBE_BASIS_EXPLICIT_USER,
        input_basis=INPUT_BASIS_EXPLICIT_USER,
        expected_behavior_basis=EXPECTATION_BASIS_EXPLICIT_USER,
        provenance_reference="literal user reproducer: add(2, 2) should return 5",
    )

    receipt = execute_defect_probe(contract, repo_path=tmp_path)

    assert receipt.probe_result == PROBE_REPRODUCED
    assert receipt.observed == 4
    assert receipt.expected == 5
    assert receipt.expected_behavior_basis == EXPECTATION_BASIS_EXPLICIT_USER
    assert "objective" not in receipt.reason


def test_model_authored_expectation_and_both_sides_are_refused(tmp_path):
    contract = replace(
        _contract(tmp_path, expected=5),
        probe_basis=PROBE_BASIS_MODEL_AUTHORED,
        input_basis=INPUT_BASIS_MODEL_AUTHORED,
        expected_behavior_basis=EXPECTATION_BASIS_MODEL_AUTHORED,
        provenance_reference="same patch model response",
    )

    receipt = execute_defect_probe(contract, repo_path=tmp_path)

    assert receipt.probe_result == PROBE_INVALID
    assert receipt.attempted is False
    assert reproduced_probe_target(receipt.as_dict()) is None


def test_ambiguous_or_unavailable_provenance_is_refused(tmp_path):
    contract = replace(_contract(tmp_path), provenance_reference="")

    receipt = execute_defect_probe(contract, repo_path=tmp_path)

    assert receipt.probe_result == PROBE_INVALID
    assert receipt.attempted is False


def test_existing_repository_test_is_a_narrow_probe(tmp_path):
    source = "def add(a, b):\n    return a - b\n"
    _write(tmp_path, "calc.py", source)
    _write(
        tmp_path,
        "tests/test_calc.py",
        "from calc import add\n\ndef test_add_contract():\n    assert add(2, 2) == 4\n",
    )
    binding = _binding(tmp_path, source=source)
    assert binding is not None
    contract = build_existing_pytest_probe(
        target=binding,
        test_selector="tests/test_calc.py::test_add_contract",
        provenance_reference="pre-existing repository test assertion",
    )

    receipt = execute_defect_probe(contract, repo_path=tmp_path)

    assert receipt.probe_result == PROBE_REPRODUCED, receipt.reason
    assert receipt.observed == "test_failed"
    assert not (tmp_path / ".pytest_cache").exists()
    assert not list(tmp_path.rglob("*.pyc"))


def test_unbound_existing_test_is_invalid_not_evidence(tmp_path):
    binding = _binding(tmp_path)
    assert binding is not None
    _write(
        tmp_path,
        "tests/test_other.py",
        "def test_other():\n    assert 2 + 2 == 5\n",
    )
    contract = build_existing_pytest_probe(
        target=binding,
        test_selector="tests/test_other.py::test_other",
        provenance_reference="existing repository test",
    )

    assert execute_defect_probe(contract, repo_path=tmp_path).probe_result == PROBE_INVALID


def test_probe_timeout_is_inconclusive(monkeypatch, tmp_path):
    contract = _contract(tmp_path)

    def timed_out(command):
        return SafeValidationResult(
            ok=False,
            blocked=False,
            block_reason="",
            exit_code=None,
            stdout="",
            stderr="validation budget exhausted",
            timed_out=True,
            command=command.command,
            cwd=str(command.cwd),
            timeout_sec=command.timeout_sec,
            python_bytecode_cache_isolated=True,
        )

    monkeypatch.setattr("core.defect_probe.run_safe_validation_command", timed_out)
    receipt = execute_defect_probe(contract, repo_path=tmp_path)

    assert receipt.probe_result == PROBE_INCONCLUSIVE
    assert receipt.attempted is True


def test_probe_import_failure_is_inconclusive(tmp_path):
    source = "raise RuntimeError('import refused')\n\ndef add(a, b):\n    return a + b\n"
    _write(tmp_path, "calc.py", source)
    binding = _binding(tmp_path, source=source)
    assert binding is not None
    contract = build_python_function_probe(
        target=binding,
        args=(2, 2),
        expected=4,
        probe_basis=PROBE_BASIS_REPOSITORY_CONTRACT,
        input_basis=INPUT_BASIS_REPOSITORY_CONTRACT,
        expected_behavior_basis=EXPECTATION_BASIS_REPOSITORY_CONTRACT,
        provenance_reference="repository contract",
    )

    receipt = execute_defect_probe(contract, repo_path=tmp_path)

    assert receipt.probe_result == PROBE_INCONCLUSIVE
    assert receipt.observed == "tool_failure:RuntimeError"


def test_probe_refuses_repository_mutation_and_leaves_bytes_unchanged(tmp_path):
    source = (
        "from pathlib import Path\n\n"
        "def touch_repo(value):\n"
        "    Path('changed.txt').write_text(value)\n"
        "    return value\n"
    )
    _write(tmp_path, "mutator.py", source)
    binding = _binding(
        tmp_path,
        relative="mutator.py",
        symbol="touch_repo",
        source=source,
    )
    assert binding is not None
    contract = build_python_function_probe(
        target=binding,
        args=("x",),
        expected="x",
        probe_basis=PROBE_BASIS_REPOSITORY_CONTRACT,
        input_basis=INPUT_BASIS_REPOSITORY_CONTRACT,
        expected_behavior_basis=EXPECTATION_BASIS_REPOSITORY_CONTRACT,
        provenance_reference="repository contract",
    )

    receipt = execute_defect_probe(contract, repo_path=tmp_path)

    assert receipt.probe_result == PROBE_INCONCLUSIVE
    assert receipt.observed == "side_effect_refused"
    assert not (tmp_path / "changed.txt").exists()
    assert (tmp_path / "mutator.py").read_text(encoding="utf-8") == source


def test_probe_refuses_network_access(tmp_path):
    source = (
        "import socket\n\n"
        "def fetch(host):\n"
        "    socket.create_connection((host, 80))\n"
        "    return 'connected'\n"
    )
    _write(tmp_path, "networker.py", source)
    binding = _binding(
        tmp_path,
        relative="networker.py",
        symbol="fetch",
        source=source,
    )
    assert binding is not None
    contract = build_python_function_probe(
        target=binding,
        args=("example.com",),
        expected="connected",
        probe_basis=PROBE_BASIS_REPOSITORY_CONTRACT,
        input_basis=INPUT_BASIS_REPOSITORY_CONTRACT,
        expected_behavior_basis=EXPECTATION_BASIS_REPOSITORY_CONTRACT,
        provenance_reference="repository contract",
    )

    receipt = execute_defect_probe(contract, repo_path=tmp_path)

    assert receipt.probe_result == PROBE_INCONCLUSIVE
    assert receipt.observed == "side_effect_refused"


def test_same_immutable_probe_reuses_current_source_post_patch(tmp_path):
    source = "def value():\n    return 'A'\n"
    path = _write(tmp_path, "value.py", source)
    binding = _binding(
        tmp_path,
        relative="value.py",
        symbol="value",
        source=source,
    )
    assert binding is not None
    contract = build_python_function_probe(
        target=binding,
        args=(),
        expected="B",
        probe_basis=PROBE_BASIS_REPOSITORY_CONTRACT,
        input_basis=INPUT_BASIS_REPOSITORY_CONTRACT,
        expected_behavior_basis=EXPECTATION_BASIS_REPOSITORY_CONTRACT,
        provenance_reference="repository contract: value returns B",
    )
    before = execute_defect_probe(contract, repo_path=tmp_path)
    stat = path.stat()
    path.write_text("def value():\n    return 'B'\n", encoding="utf-8")
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    after = execute_defect_probe(
        contract,
        repo_path=tmp_path,
        execution_stage=EXECUTION_STAGE_POST_PATCH,
    )

    assert before.probe_result == PROBE_REPRODUCED
    assert after.probe_result == PROBE_NOT_REPRODUCED
    assert before.expected == after.expected == "B"
    assert before.target_binding is after.target_binding
    assert before.source_sha256 != after.source_sha256
    assert reproduced_probe_target(after.as_dict()) is None


def test_pre_patch_source_change_invalidates_freshness_binding(tmp_path):
    contract = _contract(tmp_path)
    (tmp_path / "calc.py").write_text(
        "def add(a, b):\n    return a - b\n", encoding="utf-8"
    )

    receipt = execute_defect_probe(contract, repo_path=tmp_path)

    assert receipt.probe_result == PROBE_INVALID
    assert receipt.attempted is False


def test_current_source_probe_ignores_same_size_same_mtime_repository_pyc(tmp_path):
    path = _write(tmp_path, "value.py", "def value():\n    return 'A'\n")
    pyc_path = Path(py_compile.compile(str(path), doraise=True))
    stat = path.stat()
    path.write_text("def value():\n    return 'B'\n", encoding="utf-8")
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    source = path.read_text(encoding="utf-8")
    binding = _binding(
        tmp_path,
        relative="value.py",
        symbol="value",
        source=source,
    )
    assert binding is not None
    contract = build_python_function_probe(
        target=binding,
        args=(),
        expected="B",
        probe_basis=PROBE_BASIS_REPOSITORY_CONTRACT,
        input_basis=INPUT_BASIS_REPOSITORY_CONTRACT,
        expected_behavior_basis=EXPECTATION_BASIS_REPOSITORY_CONTRACT,
        provenance_reference="repository contract: value returns B",
    )

    receipt = execute_defect_probe(contract, repo_path=tmp_path)

    assert pyc_path.is_file()
    assert receipt.probe_result == PROBE_NOT_REPRODUCED
    assert receipt.observed == "B"
    assert receipt.freshness == "current_source_isolated_bytecode_cache"


def test_t6_adapter_reproduces_current_indent_classifier_without_fixing_it():
    source = inspect.getsource(_classify_indent)
    binding = build_probe_target_binding(
        repo_path=ROOT,
        target_file="core/code_dna.py",
        target_symbol="_classify_indent",
        source_snippet=source,
        candidate_eligible=True,
    )
    assert binding is not None
    contract = derive_indentation_probe_from_preserved_task(
        raw_task=T6_QUERY,
        target=binding,
    )
    assert contract is not None

    receipt = execute_defect_probe(contract, repo_path=ROOT)

    assert contract.probe_basis == PROBE_BASIS_TASK_FACT_ADAPTER
    assert receipt.probe_result == PROBE_REPRODUCED
    assert receipt.observed == "4space"
    assert receipt.expected == "2space"
    assert 'counts["4space"] += 1' in inspect.getsource(_classify_indent)


def test_production_t6_timeout_probe_feeds_existing_patch_basis_boundary():
    control = _control(T6_DEFECT_TASK, ROOT, T6_TARGET)

    attach_preflight_validation(control, _inconclusive_preflight())

    probe = control["defect_probe"]
    state = control["patch_candidate_state"]
    assert probe["probe_result"] == PROBE_REPRODUCED
    assert probe["probe_observed"] == "4space"
    assert control["defect_probe_result"] == PROBE_REPRODUCED
    assert state["defect_grounded"] is True
    assert state["patch_basis"] == "grounded_defect"
    assert state["patch_basis_source"] == "bounded_defect_reproduction"
    assert state["candidate_binding"] == {
        "file": "core/code_dna.py",
        "symbol": "_classify_indent",
        "relation": "bounded_reproduction_bound",
    }
    assert state["write_authority"] is False
    assert state["patch_application_authority"] is False
    assert control["preflight_validation"]["outcome"] == "inconclusive"
    assert control["preflight_validation"]["validation_budget_exhausted"] is True


def test_genuine_fast_validation_failure_does_not_force_a_probe(tmp_path):
    source = "def add(a, b):\n    return a - b\n"
    _write(tmp_path, "calc.py", source)
    control = _control("Fix the failing add assertion", tmp_path, "calc.py::add")

    attach_preflight_validation(control, _failed_preflight("calc.py"))

    # A conclusive baseline no longer hides reproduction diagnostics. This
    # task has no independent typed behavior contract, so no probe executes.
    assert control["defect_probe"]["probe_result"] == PROBE_UNAVAILABLE
    assert control["defect_probe"]["defect_probe_attempted"] is False
    assert control["patch_candidate_state"]["patch_basis"] == "grounded_defect"
    assert control["patch_candidate_state"]["patch_basis_source"] == (
        "executed_validation_failure"
    )


def test_analysis_and_explicit_change_routes_do_not_probe(tmp_path):
    base = {
        "query": "Explain the architecture",
        "repo_path": str(tmp_path),
        "preflight_validation": _inconclusive_preflight(),
        "live_route": safe_route_live_task(
            "Explain the architecture", repository_available=True
        ).as_dict(),
    }
    feature = dict(base)
    feature["query"] = "Add a priority field"
    feature["live_route"] = safe_route_live_task(
        feature["query"], repository_available=True
    ).as_dict()

    assert maybe_execute_control_defect_probe(base) is None
    assert maybe_execute_control_defect_probe(feature) is None


def test_no_adapter_is_unavailable_without_repository_search(tmp_path):
    source = "def add(a, b):\n    return a - b\n"
    _write(tmp_path, "calc.py", source)
    control = _control("The add result is wrong; fix it", tmp_path, "calc.py::add")
    control["preflight_validation"] = _inconclusive_preflight()

    receipt = maybe_execute_control_defect_probe(control)

    assert receipt is not None
    assert receipt.probe_result == PROBE_UNAVAILABLE
    assert receipt.attempted is False


def test_probe_surface_contains_no_arbitrary_code_or_traversal_primitives():
    source = (ROOT / "core/defect_probe.py").read_text(encoding="utf-8")
    worker = (ROOT / "core/defect_probe_worker.py").read_text(encoding="utf-8")
    for forbidden in ("eval(", "exec(", "python -c", ".rglob(", "os.walk("):
        assert forbidden not in source
        assert forbidden not in worker

    guardrails = defect_probe_guardrails()
    assert guardrails["arbitrary_code_accepted"] is False
    assert guardrails["network_allowed"] is False
    assert guardrails["repository_traversal_added"] is False
    assert guardrails["write_authority_granted"] is False
    assert guardrails["repository_validation_replaced"] is False


# ---------------------------------------------------------------------------
# DEFECT.PROBE.LIVE.2 — immutable candidate closure
# ---------------------------------------------------------------------------


def _closure_fixture(tmp_path: Path, *, user_basis: bool = False):
    broken_source = "def add(a, b):\n    return a - b\n"
    _write(tmp_path, "calc.py", broken_source)
    source_paths = ()
    if not user_basis:
        _write(tmp_path, "contract.md", "add(a, b) returns the arithmetic sum\n")
        source_paths = ("contract.md",)
    binding = _binding(tmp_path, source=broken_source)
    assert binding is not None
    contract = build_python_function_probe(
        target=binding,
        args=(2, 2),
        expected=4,
        probe_basis=PROBE_BASIS_REPOSITORY_CONTRACT,
        input_basis=INPUT_BASIS_REPOSITORY_CONTRACT,
        expected_behavior_basis=EXPECTATION_BASIS_REPOSITORY_CONTRACT,
        provenance_reference="repository contract: add returns the arithmetic sum",
        expectation_source_paths=source_paths,
    )
    if user_basis:
        contract = replace(
            contract,
            probe_basis=PROBE_BASIS_EXPLICIT_USER,
            input_basis=INPUT_BASIS_EXPLICIT_USER,
            expected_behavior_basis=EXPECTATION_BASIS_EXPLICIT_USER,
            provenance_reference="preserved user requirement: add(2, 2) returns 4",
            expectation_source_paths=(),
        )
    pre = execute_defect_probe(contract, repo_path=tmp_path)
    assert pre.probe_result == PROBE_REPRODUCED
    plan = [
        {
            "op": "replace_snippet",
            "relative_path": "calc.py",
            "target_snippet": "    return a - b\n",
            "patched_snippet": "    return a + b\n",
        }
    ]
    return contract, pre, plan


def test_immutable_probe_fingerprint_covers_oracle_and_excludes_run_metadata(tmp_path):
    contract, pre, _plan = _closure_fixture(tmp_path)

    assert len(contract.fingerprint) == 64
    assert pre.probe_fingerprint == contract.fingerprint
    assert pre.as_dict()["probe_fingerprint"] == contract.fingerprint
    assert replace(contract, timeout_seconds=contract.timeout_seconds + 1).fingerprint != contract.fingerprint
    assert replace(contract, expected_json="5").fingerprint != contract.fingerprint


def test_pre_reproduced_post_fixed_is_bound_to_exact_candidate_and_cleans_sandbox(tmp_path):
    contract, pre, plan = _closure_fixture(tmp_path)
    before = (tmp_path / "calc.py").read_bytes()
    sandbox_parent = tmp_path.parent / f"{tmp_path.name}-sandboxes"
    sandbox_parent.mkdir()

    result = evaluate_candidate_defect_closure(
        repo_path=tmp_path,
        candidate_plan=plan,
        probe_contract=contract,
        pre_probe_receipt=pre,
        patch_safety={"ok": True},
        expected_candidate_fingerprint=candidate_probe.patch_plan_fingerprint(plan),
        sandbox_parent=sandbox_parent,
    )

    assert result.defect_closure_status == CLOSURE_FIXED, result.as_telemetry()
    assert result.pre_probe_result == PROBE_REPRODUCED
    assert result.pre_probe_observed == 0
    assert result.post_probe_result == PROBE_NOT_REPRODUCED
    assert result.post_probe_observed == 4
    assert result.sandbox_only is True
    assert result.sandbox_cleanup_ok is True
    assert not list(sandbox_parent.iterdir())
    assert (tmp_path / "calc.py").read_bytes() == before
    assert set(result.timings) == {
        "sandbox_creation_sec",
        "patch_apply_sec",
        "post_probe_execution_sec",
        "cleanup_sec",
        "total_sec",
    }


def test_same_wrong_and_different_wrong_outputs_remain_distinct(tmp_path):
    contract, pre, _plan = _closure_fixture(tmp_path)
    same_plan = [
        {
            "op": "replace_snippet",
            "relative_path": "calc.py",
            "target_snippet": "    return a - b\n",
            "patched_snippet": "    return a - b  # still wrong\n",
        }
    ]
    changed_plan = [
        {
            "op": "replace_snippet",
            "relative_path": "calc.py",
            "target_snippet": "    return a - b\n",
            "patched_snippet": "    return a + b + 1\n",
        }
    ]

    same = evaluate_candidate_defect_closure(
        repo_path=tmp_path,
        candidate_plan=same_plan,
        probe_contract=contract,
        pre_probe_receipt=pre,
        patch_safety={"ok": True},
    )
    changed = evaluate_candidate_defect_closure(
        repo_path=tmp_path,
        candidate_plan=changed_plan,
        probe_contract=contract,
        pre_probe_receipt=pre,
        patch_safety={"ok": True},
    )

    assert same.defect_closure_status == CLOSURE_STILL_REPRODUCED
    assert same.post_probe_observed == 0
    assert changed.defect_closure_status == CLOSURE_CHANGED_BUT_UNRESOLVED
    assert changed.post_probe_observed == 5


def test_changed_probe_and_candidate_refinement_invalidate_comparison(tmp_path):
    contract, pre, plan = _closure_fixture(tmp_path)
    changed_probe = replace(contract, expected_json="5")

    comparison = evaluate_candidate_defect_closure(
        repo_path=tmp_path,
        candidate_plan=plan,
        probe_contract=changed_probe,
        pre_probe_receipt=pre,
        patch_safety={"ok": True},
    )
    changed_candidate = [dict(plan[0])]
    changed_candidate[0]["patched_snippet"] = "    return a + b + 0\n"
    stale_binding = evaluate_candidate_defect_closure(
        repo_path=tmp_path,
        candidate_plan=changed_candidate,
        probe_contract=contract,
        pre_probe_receipt=pre,
        patch_safety={"ok": True},
        expected_candidate_fingerprint=candidate_probe.patch_plan_fingerprint(plan),
    )

    assert comparison.defect_closure_status == CLOSURE_INVALID_COMPARISON
    assert stale_binding.defect_closure_status == CLOSURE_INVALID_COMPARISON


def test_candidate_refinement_makes_stored_post_probe_stale(tmp_path):
    contract, pre, plan = _closure_fixture(tmp_path)
    result = evaluate_candidate_defect_closure(
        repo_path=tmp_path,
        candidate_plan=plan,
        probe_contract=contract,
        pre_probe_receipt=pre,
        patch_safety={"ok": True},
    )
    telemetry = result.as_telemetry()
    refined = [dict(plan[0], patched_snippet="    return a + b + 0\n")]

    assert candidate_defect_closure_is_current(telemetry, plan) is True
    assert candidate_defect_closure_is_current(telemetry, refined) is False


def test_candidate_cannot_modify_repository_backed_probe_oracle(tmp_path):
    contract, pre, plan = _closure_fixture(tmp_path)
    plan.append(
        {
            "op": "replace_snippet",
            "relative_path": "contract.md",
            "target_snippet": "arithmetic sum",
            "patched_snippet": "subtraction",
        }
    )

    result = evaluate_candidate_defect_closure(
        repo_path=tmp_path,
        candidate_plan=plan,
        probe_contract=contract,
        pre_probe_receipt=pre,
        patch_safety={"ok": True},
    )

    assert result.defect_closure_status == CLOSURE_INVALID_COMPARISON
    assert result.candidate_apply_status == "not_attempted"
    assert (tmp_path / "contract.md").read_text(encoding="utf-8").endswith("sum\n")


def test_false_model_oracle_cannot_become_fixed_even_if_candidate_matches(tmp_path):
    contract, pre, _plan = _closure_fixture(tmp_path)
    model_contract = replace(
        contract,
        expected_json="5",
        probe_basis=PROBE_BASIS_MODEL_AUTHORED,
        input_basis=INPUT_BASIS_MODEL_AUTHORED,
        expected_behavior_basis=EXPECTATION_BASIS_MODEL_AUTHORED,
        provenance_reference="model invented add(2, 2) == 5",
        expectation_source_paths=(),
    )
    forged_pre = replace(
        pre,
        expected=5,
        probe_basis=PROBE_BASIS_MODEL_AUTHORED,
        input_basis=INPUT_BASIS_MODEL_AUTHORED,
        expected_behavior_basis=EXPECTATION_BASIS_MODEL_AUTHORED,
        probe_fingerprint=model_contract.fingerprint,
    )
    plan = [
        {
            "op": "replace_snippet",
            "relative_path": "calc.py",
            "target_snippet": "    return a - b\n",
            "patched_snippet": "    return 5\n",
        }
    ]

    result = evaluate_candidate_defect_closure(
        repo_path=tmp_path,
        candidate_plan=plan,
        probe_contract=model_contract,
        pre_probe_receipt=forged_pre,
        patch_safety={"ok": True},
    )

    assert result.defect_closure_status == CLOSURE_INVALID_COMPARISON
    assert result.candidate_apply_status == "not_attempted"


def test_user_and_source_bound_repository_expectations_may_support_closure(tmp_path):
    repository_contract, repository_pre, repository_plan = _closure_fixture(
        tmp_path / "repository"
    )
    user_contract, user_pre, user_plan = _closure_fixture(
        tmp_path / "user", user_basis=True
    )

    repository_result = evaluate_candidate_defect_closure(
        repo_path=tmp_path / "repository",
        candidate_plan=repository_plan,
        probe_contract=repository_contract,
        pre_probe_receipt=repository_pre,
        patch_safety={"ok": True},
    )
    user_result = evaluate_candidate_defect_closure(
        repo_path=tmp_path / "user",
        candidate_plan=user_plan,
        probe_contract=user_contract,
        pre_probe_receipt=user_pre,
        patch_safety={"ok": True},
    )

    assert repository_result.defect_closure_status == CLOSURE_FIXED
    assert user_result.defect_closure_status == CLOSURE_FIXED


def test_unsafe_or_unmaterializable_candidate_is_never_probed(tmp_path, monkeypatch):
    contract, pre, plan = _closure_fixture(tmp_path)
    called = False

    def fail_if_called(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("probe execution must remain unreachable")

    monkeypatch.setattr(candidate_probe, "execute_defect_probe", fail_if_called)
    denied = evaluate_candidate_defect_closure(
        repo_path=tmp_path,
        candidate_plan=plan,
        probe_contract=contract,
        pre_probe_receipt=pre,
        patch_safety={"ok": False},
    )
    invalid_plan = [dict(plan[0], target_snippet="not in source")]
    unavailable = evaluate_candidate_defect_closure(
        repo_path=tmp_path,
        candidate_plan=invalid_plan,
        probe_contract=contract,
        pre_probe_receipt=pre,
        patch_safety={"ok": True},
    )

    assert denied.defect_closure_status == CLOSURE_UNAVAILABLE
    assert denied.candidate_apply_status == "not_attempted"
    assert unavailable.defect_closure_status == CLOSURE_UNAVAILABLE
    assert unavailable.candidate_apply_status == "failed"
    assert called is False


def test_post_probe_timeout_and_tool_failure_are_inconclusive(tmp_path, monkeypatch):
    contract, pre, plan = _closure_fixture(tmp_path)

    for reason in ("probe timeout exhausted", "tool/import unavailable"):
        monkeypatch.setattr(
            candidate_probe,
            "execute_defect_probe",
            lambda *_args, _reason=reason, **_kwargs: replace(
                pre,
                probe_result=PROBE_INCONCLUSIVE,
                execution_stage=EXECUTION_STAGE_POST_PATCH,
                observed=_reason,
                reason=_reason,
            ),
        )
        result = evaluate_candidate_defect_closure(
            repo_path=tmp_path,
            candidate_plan=plan,
            probe_contract=contract,
            pre_probe_receipt=pre,
            patch_safety={"ok": True},
        )
        assert result.defect_closure_status == CLOSURE_INCONCLUSIVE
        assert result.post_probe_result == PROBE_INCONCLUSIVE


def test_sandbox_execution_unavailable_is_inconclusive(tmp_path, monkeypatch):
    contract, pre, plan = _closure_fixture(tmp_path)
    monkeypatch.setattr(
        candidate_probe,
        "create_managed_sandbox",
        lambda *_args, **_kwargs: {"ok": False, "error": "copy unavailable"},
    )

    result = evaluate_candidate_defect_closure(
        repo_path=tmp_path,
        candidate_plan=plan,
        probe_contract=contract,
        pre_probe_receipt=pre,
        patch_safety={"ok": True},
    )

    assert result.defect_closure_status == CLOSURE_INCONCLUSIVE
    assert result.candidate_apply_status == "unavailable"


def test_candidate_probe_uses_current_sandbox_source_despite_stale_repository_pyc(tmp_path):
    contract, pre, plan = _closure_fixture(tmp_path)
    cache = tmp_path / "stale.pyc"
    py_compile.compile(str(tmp_path / "calc.py"), cfile=str(cache), doraise=True)

    result = evaluate_candidate_defect_closure(
        repo_path=tmp_path,
        candidate_plan=plan,
        probe_contract=contract,
        pre_probe_receipt=pre,
        patch_safety={"ok": True},
    )

    assert result.defect_closure_status == CLOSURE_FIXED
    assert result.post_probe_observed == 4


def test_candidate_probe_guardrails_preserve_validation_and_authority_boundaries():
    guardrails = candidate_defect_probe_guardrails()

    assert guardrails["same_probe_required"] is True
    assert guardrails["same_expectation_provenance_required"] is True
    assert guardrails["patch_safety_required_before_sandbox"] is True
    assert guardrails["real_patch_plan_primitive_used"] is True
    assert guardrails["full_validation_rewritten"] is False
    assert guardrails["targeted_validation_rewritten"] is False
    assert guardrails["patch_basis_created"] is False
    assert guardrails["execution_authority_granted"] is False
    assert guardrails["auto_apply_granted"] is False
    assert guardrails["model_called"] is False
    assert guardrails["network_called"] is False


def _candidate_probe_state(repo: Path, control: dict, plan: list[dict]) -> AgentState:
    state = AgentState(
        interface="agent",
        mode="control",
        user_input=T6_DEFECT_TASK,
        file_paths=[str(repo)],
        primary_file=None,
        input_mode="project",
        language="python",
        task_type="bug_fix",
        repo_path=str(repo),
        is_project_input=True,
        live_route=control["live_route"],
    )
    state.control_result = control
    state.json_block = {
        "patch_basis": PATCH_BASIS_GROUNDED_DEFECT,
        "patch_plan": plan,
        "targeted_validation_status": "failed",
        "full_validation_outcome": "inconclusive",
        "full_validation_category": "validation_budget_exhausted",
        "execution_authorized": False,
        "write_authority": False,
    }
    return state


def test_live_adapter_records_closure_without_rewriting_other_facts(tmp_path):
    broken = (
        "def _classify_indent(text):\n"
        "    for line in text.splitlines():\n"
        "        if line.startswith('    '):\n"
        "            return '4space'\n"
        "    return '2space'\n"
    )
    _write(tmp_path, "indent.py", broken)
    binding = build_probe_target_binding(
        repo_path=tmp_path,
        target_file="indent.py",
        target_symbol="_classify_indent",
        source_snippet=broken.strip(),
        candidate_eligible=True,
    )
    assert binding is not None
    contract = derive_indentation_probe_from_preserved_task(
        raw_task=T6_QUERY,
        target=binding,
    )
    assert contract is not None
    pre = execute_defect_probe(contract, repo_path=tmp_path)
    control = {
        "query": T6_QUERY,
        "repo_path": str(tmp_path),
        "live_route": {
            "selected_workflow": "defect_repair_patch",
            "preservation_passed": True,
        },
        "preflight_validation": {
            "outcome": "inconclusive",
            "category": "validation_budget_exhausted",
        },
        "patch_intent": {
            "target_file": "indent.py",
            "target_symbol": "_classify_indent",
            "target_symbol_full": "indent.py::_classify_indent",
            "source_snippet": broken.strip(),
        },
        "entry_resolution": {
            "resolved_entry_nodes": ["indent.py::_classify_indent"]
        },
        "defect_probe": pre.as_dict(),
    }
    plan = [
        {
            "op": "replace_snippet",
            "relative_path": "indent.py",
            "target_snippet": "            return '4space'\n",
            "patched_snippet": "            return '2space'\n",
        }
    ]
    state = _candidate_probe_state(tmp_path, control, plan)

    result = pipeline._record_candidate_defect_closure(
        state,
        SimpleNamespace(patch_basis=PATCH_BASIS_GROUNDED_DEFECT),
        tmp_path,
        patch_safety={"ok": True},
    )

    assert result is not None
    assert state.json_block["defect_closure_status"] == CLOSURE_FIXED
    assert state.json_block["targeted_validation_status"] == "failed"
    assert state.json_block["full_validation_outcome"] == "inconclusive"
    assert state.json_block["full_validation_category"] == "validation_budget_exhausted"
    assert state.json_block["patch_basis"] == PATCH_BASIS_GROUNDED_DEFECT
    assert state.json_block["execution_authorized"] is False
    assert state.json_block["write_authority"] is False
    assert state.json_block["candidate_probe_authority_effect"] == "none"


def test_t1_t2_t3_and_explicit_change_routes_do_not_trigger_candidate_probe(
    tmp_path, monkeypatch
):
    called = False

    def fail_if_called(**_kwargs):
        nonlocal called
        called = True
        raise AssertionError("candidate closure must not run")

    monkeypatch.setattr(candidate_probe, "evaluate_candidate_defect_closure", fail_if_called)
    monkeypatch.setattr(pipeline, "evaluate_candidate_defect_closure", fail_if_called)
    cases = (
        (PATCH_BASIS_EXPLICIT_CHANGE_REQUEST, "inconclusive", "validation_budget_exhausted"),
        (PATCH_BASIS_GROUNDED_DEFECT, "passed", "passed"),
        (PATCH_BASIS_GROUNDED_DEFECT, "failed", "assertion_failure"),
    )
    for basis, outcome, category in cases:
        control = {
            "live_route": {
                "selected_workflow": "defect_repair_patch",
                "preservation_passed": True,
            },
            "preflight_validation": {"outcome": outcome, "category": category},
        }
        state = _candidate_probe_state(
            tmp_path,
            control,
            [{"op": "create_file", "relative_path": "x.py", "content": ""}],
        )
        result = pipeline._record_candidate_defect_closure(
            state,
            SimpleNamespace(patch_basis=basis),
            tmp_path,
            patch_safety={"ok": True},
        )
        assert result is None
    assert called is False


def _t6_candidate_plan() -> list[dict]:
    target = (
        "    counts = Counter()\n"
        "    for line in text.splitlines():\n"
        "        if not line or line[0] not in \" \\t\":\n"
        "            continue\n"
        "        if line.startswith(\"\\t\"):\n"
        "            counts[\"tab\"] += 1\n"
        "        elif line.startswith(\"    \"):\n"
        "            counts[\"4space\"] += 1\n"
        "        elif line.startswith(\"  \"):\n"
        "            counts[\"2space\"] += 1\n"
        "    return counts.most_common(1)[0][0] if counts else None\n"
    )
    patched = (
        "    counts = Counter()\n"
        "    space_widths = []\n"
        "    for line in text.splitlines():\n"
        "        if not line or line[0] not in \" \\t\":\n"
        "            continue\n"
        "        if line.startswith(\"\\t\"):\n"
        "            counts[\"tab\"] += 1\n"
        "        else:\n"
        "            space_widths.append(len(line) - len(line.lstrip(\" \")))\n"
        "    if counts[\"tab\"] > len(space_widths):\n"
        "        return \"tab\"\n"
        "    if space_widths:\n"
        "        return \"2space\" if min(space_widths) <= 2 else \"4space\"\n"
        "    return \"tab\" if counts[\"tab\"] else None\n"
    )
    return [
        {
            "op": "replace_snippet",
            "relative_path": "core/code_dna.py",
            "target_snippet": target,
            "patched_snippet": patched,
        }
    ]


def test_t6_sandbox_closure_and_defect_preservation_failure_coexist():
    source_before = (ROOT / "core/code_dna.py").read_bytes()
    source_text = inspect.getsource(_classify_indent)
    binding = build_probe_target_binding(
        repo_path=ROOT,
        target_file="core/code_dna.py",
        target_symbol="_classify_indent",
        source_snippet=source_text,
        candidate_eligible=True,
    )
    assert binding is not None
    contract = derive_indentation_probe_from_preserved_task(
        raw_task=T6_QUERY,
        target=binding,
    )
    assert contract is not None
    pre = execute_defect_probe(contract, repo_path=ROOT)
    plan = _t6_candidate_plan()
    safety = evaluate_patch_safety(["core/code_dna.py"], project_root=ROOT)

    closure = evaluate_candidate_defect_closure(
        repo_path=ROOT,
        candidate_plan=plan,
        probe_contract=contract,
        pre_probe_receipt=pre,
        patch_safety=safety,
    )

    target = "core/code_dna.py::_classify_indent"
    selected = (
        "tests/test_localization_candidate_population.py::"
        "test_classify_indent_defect_remains_reproducible",
        "tests/test_query_symbol_entry_recall.py::"
        "test_classify_indent_remains_intentionally_broken_and_untouched",
    )
    graph = build_graph(
        [
            {"id": "core/code_dna.py", "type": "file"},
            {"id": target, "type": "function", "file": "core/code_dna.py"},
            *[
                {
                    "id": selector,
                    "type": "function",
                    "file": selector.split("::", 1)[0],
                }
                for selector in selected
            ],
        ],
        [
            {"source": selector, "target": target, "type": "resolved_call"}
            for selector in selected
        ],
    )
    request = targeted_validation.build_targeted_validation_request(
        repo_path=ROOT,
        candidate_plan=plan,
        graph=graph,
        changed_symbols=(target,),
    )
    targeted = targeted_validation.validate_targeted_candidate(
        repo_path=ROOT,
        candidate_plan=plan,
        request=request,
        pre_patch_probe_result=pre.probe_result,
    )
    oracle_receipt = assess_selected_check_oracles(
        repo_path=ROOT,
        probe_contract=contract,
        targeted_validation=targeted,
        defect_closure=closure.as_telemetry(),
        full_validation={
            "outcome": "inconclusive",
            "category": "validation_budget_exhausted",
        },
    )
    eligibility = evaluate_execution_eligibility(
        {
            "task_route": "defect_repair",
            "patch_basis": PATCH_BASIS_GROUNDED_DEFECT,
            "source_target_grounded": True,
            "candidate_fingerprint": request.candidate_fingerprint,
            "patch_safety": {
                **safety,
                "candidate_fingerprint": request.candidate_fingerprint,
            },
            "full_validation": {
                "outcome": "inconclusive",
                "category": "validation_budget_exhausted",
            },
            "pre_probe": pre.as_dict(),
            "candidate_defect_closure": closure.as_telemetry(),
            "targeted_validation": targeted.as_telemetry(),
            "oracle_assessment": oracle_receipt.as_telemetry(),
            "execution_authorization": {
                "execution_authorized": False,
                "execution_authority_source": "none",
                "execution_authorization_denied_reason": "human_approval_required",
                "human_approval_required_for_execution": True,
                "execution_attempted": False,
                "patch_applied": False,
                "final_repository_changed": False,
            },
        }
    )

    full_validation = {
        "outcome": "inconclusive",
        "category": "validation_budget_exhausted",
    }
    authority = {"execution_authorized": False, "write_authority": False}
    assert pre.probe_result == PROBE_REPRODUCED
    assert pre.observed == "4space"
    assert closure.defect_closure_status == CLOSURE_FIXED, closure.as_telemetry()
    assert closure.post_probe_observed == "2space"
    assert targeted.baseline_outcome == VALIDATION_PASSED
    assert targeted.candidate_outcome == VALIDATION_FAILED
    assert targeted.status == VALIDATION_FAILED
    assert len(oracle_receipt.assessments) == 2
    assert {
        item.oracle_role for item in oracle_receipt.assessments
    } == {ROLE_DEFECT_PRESERVATION_ORACLE}
    assert {
        item.check_execution_outcome for item in oracle_receipt.assessments
    } == {CHECK_FAILED}
    assert oracle_receipt.evidence_matrix["post_probe"] == {
        "result": "not_reproduced",
        "observed": "2space",
        "defect_closure_status": CLOSURE_FIXED,
    }
    assert oracle_receipt.evidence_matrix["targeted_validation"]["outcome"] == (
        VALIDATION_FAILED
    )
    assert full_validation == {
        "outcome": "inconclusive",
        "category": "validation_budget_exhausted",
    }
    assert authority == {"execution_authorized": False, "write_authority": False}
    assert eligibility.assessment_for(
        PROFILE_FULL_VALIDATION_REQUIRED
    ).eligibility_status == INELIGIBLE
    assert eligibility.assessment_for(
        PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW
    ).eligibility_status == ELIGIBLE
    assert eligibility.human_review_eligible is True
    assert (ROOT / "core/code_dna.py").read_bytes() == source_before
    assert _classify_indent(
        "root\n  one\n    two\n      three\n      four\n    five\n  six\n"
    ) == "4space"
