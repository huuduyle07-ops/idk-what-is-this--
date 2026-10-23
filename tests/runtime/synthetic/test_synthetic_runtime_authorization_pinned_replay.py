"""Pure gate and reservation controls for the pinned authorization replay.

Owner issuance and both negative matrices are stubbed. The outer effect guard
denies runtime processes and network while permitting temporary report files.
"""
from copy import deepcopy
from hashlib import sha256
import json
import sys
import tempfile
from types import SimpleNamespace

import pytest

from tests._preflight_runtime1_guard import no_runtime_effects

with no_runtime_effects(strict=False):
    from core import runtime_java_pinned_provider as provider
    from core.runtime.synthetic import synthetic_runtime_authorization_pinned as owner
    from scripts import replay_synth_auth_pinned1 as replay


_REQUIRED_CHECKS = (
    "focused_authorization_passed", "frozen_semantic_regressions_passed",
    "known_bookkeeping_drift_preserved", "benchmark_check_passed",
    "registry_picker_no_new_failures", "pure_validation_no_operational_effects",
    "in_memory_compilation_passed", "authored_whitespace_and_JSON_passed",
    "git_diff_check_passed", "historical_bytes_preserved",
)


@pytest.fixture(autouse=True)
def denied_live_effects(monkeypatch):
    with no_runtime_effects(strict=False) as effects:
        monkeypatch.setattr(provider, "issue_pinned_java_exact_provider",
            lambda: pytest.fail("replay test attempted live provider issuance"))
        monkeypatch.setattr(owner, "issue_pinned_synthetic_runtime_authorization",
            lambda: pytest.fail("replay test used unstubbed authorization issuance"))
        yield
    assert effects.denied_attempts == {}


@pytest.fixture
def gate_case(tmp_path, monkeypatch):
    root = tmp_path / "repository"
    phase = root / "phase"
    phase.mkdir(parents=True)
    source = root / "new_owner.py"
    validation = phase / "validation.json"
    historical = root / "frozen_owner.py"
    source.write_bytes(b"# additive source\n")
    validation.write_bytes(b'{"passed": true}\n')
    historical.write_bytes(b"# frozen historical source\n")
    gates = {
        "phase_id": "SYNTH.AUTH.PINNED.1", "pure_gates_ready": True,
        "checks": dict.fromkeys(_REQUIRED_CHECKS, True),
        "source_bindings": [{"path": source.name,
            "sha256": sha256(source.read_bytes()).hexdigest()}],
        "validation_bindings": [{"path": validation.name,
            "sha256": sha256(validation.read_bytes()).hexdigest()}],
    }
    baseline = {"files": [{"path": historical.name,
        "sha256": sha256(historical.read_bytes()).hexdigest()}]}
    (phase / "preservation_baseline.json").write_text(json.dumps(baseline), encoding="utf-8")
    gate_path = phase / "pure_preoperational_gates.json"
    gate_path.write_text(json.dumps(gates), encoding="utf-8")
    monkeypatch.setattr(replay, "ROOT", root)
    monkeypatch.setattr(replay, "PHASE", phase)
    monkeypatch.setattr(sys, "argv", ["replay_synth_auth_pinned1.py"])
    return SimpleNamespace(root=root, phase=phase, gates=gates, gate_path=gate_path,
        source=source, validation=validation, historical=historical,
        output=phase / "SYNTH_AUTH_PINNED_1_LOCAL.json")


@pytest.fixture
def stubbed_issuance(gate_case, monkeypatch):
    authorization = SimpleNamespace(authorization_id="authorization-under-test")
    root = SimpleNamespace(receipt_id="provider-under-test")
    proof = SimpleNamespace(receipt=root, consumed=False)
    ledger = {"PINNED1A": {"container_creations": 1},
        "JAVA1C_fixed_controller": {"controller_executions": 1}}
    report = {
        "phase_id": owner.PHASE_ID, "schema_version": owner.SCHEMA_VERSION,
        "status": owner.COMPLETE, "reason": "stubbed_exact_scope_issued",
        "synthetic_scenario_authorized": True, "runtime_execution_authority": False,
        "execution_lease_issued": False, "lifecycle_compatibility_evaluated": False,
        "reflection_admission_issued": False, "SyntheticStateBox_executed": False,
        "provider_proof_consumed": False, "provider_proof_issuance_attempts": 1,
        "provider_proof_infrastructure_effects": ledger,
        "remaining_phase_containers": 0, "cleanup_verified": True,
        "synthetic_authorization": {"authorization_id": authorization.authorization_id,
            "synthetic_scenario_authorized": True, "report_only": True},
    }
    outcome = SimpleNamespace(authorization=authorization, provider_outcome=proof,
        as_dict=lambda: deepcopy(report))
    calls = []
    registry = {}
    provider_registry = {root.receipt_id: {"object": root}}
    monkeypatch.setattr(owner, "_LIVE", registry)
    monkeypatch.setattr(provider, "_LIVE", provider_registry)

    def issue():
        calls.append("issue")
        registry[authorization.authorization_id] = {"object": authorization}
        return outcome

    monkeypatch.setattr(owner, "issue_pinned_synthetic_runtime_authorization", issue)
    monkeypatch.setattr(owner, "negative_authentication_matrix", lambda value: {"auth_control": True})
    monkeypatch.setattr(provider, "negative_authentication_matrix", lambda value: {"provider_control": True})
    monkeypatch.setattr(owner, "validate_pinned_synthetic_runtime_authorization", lambda value: value)
    return SimpleNamespace(authorization=authorization, proof=proof, root=root,
        outcome=outcome, calls=calls, registry=registry,
        provider_registry=provider_registry, ledger=ledger)


def test_replay_rejects_arguments_before_gates_or_issuance(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["replay_synth_auth_pinned1.py", "--caller-provider"])
    monkeypatch.setattr(replay, "_check_pure_gates",
        lambda: pytest.fail("arguments reached pure gate loading"))
    with pytest.raises(ValueError, match="fixed_no_argument_replay_required"):
        replay.main()


def test_all_bound_pure_gates_accept_without_issuance(gate_case):
    summary = replay._check_pure_gates()
    assert summary == {"pure_gates_ready": True, "source_hashes_checked": 1,
        "validation_artifacts_checked": 1, "historical_files_checked": 1}
    assert not gate_case.output.exists()


@pytest.mark.parametrize("check", _REQUIRED_CHECKS)
@pytest.mark.parametrize("change", ("missing", "false", "integer_alias"))
def test_every_named_boolean_gate_is_required(gate_case, check, change):
    if change == "missing":
        gate_case.gates["checks"].pop(check)
    else:
        gate_case.gates["checks"][check] = False if change == "false" else 1
    gate_case.gate_path.write_text(json.dumps(gate_case.gates), encoding="utf-8")
    with pytest.raises(ValueError, match="all_pure_gates_required_before_operation"):
        replay._check_pure_gates()
    assert not gate_case.output.exists()


@pytest.mark.parametrize("field,value", (
    ("phase_id", "SYNTH.AUTH.1"), ("pure_gates_ready", False),
    ("pure_gates_ready", 1), ("source_bindings", []), ("validation_bindings", []),
))
def test_gate_identity_readiness_and_nonempty_bindings_are_required(gate_case, field, value):
    gate_case.gates[field] = value
    gate_case.gate_path.write_text(json.dumps(gate_case.gates), encoding="utf-8")
    with pytest.raises(ValueError, match="all_pure_gates_required_before_operation"):
        replay._check_pure_gates()


@pytest.mark.parametrize("binding,reason", (
    ("source", "source_changed_after_gates"),
    ("validation", "validation_changed_after_gates"),
    ("historical", "historical_bytes_changed"),
))
def test_source_validation_and_preservation_drift_stop_before_reservation(gate_case, binding, reason):
    getattr(gate_case, binding).write_bytes(b"changed after pure gates\n")
    with pytest.raises(ValueError, match=reason):
        replay.main()
    assert not gate_case.output.exists()


def test_exclusive_report_reservation_prevents_second_issuance(gate_case, stubbed_issuance):
    assert replay.main() == 0
    first_report = gate_case.output.read_bytes()
    assert stubbed_issuance.calls == ["issue"]
    with pytest.raises(FileExistsError):
        replay.main()
    assert stubbed_issuance.calls == ["issue"]
    assert gate_case.output.read_bytes() == first_report


def test_exception_after_reservation_records_blocker_and_restores_tempdir(gate_case, monkeypatch):
    previous_tempdir = str(gate_case.root / "previous-tempdir")
    monkeypatch.setattr(tempfile, "tempdir", previous_tempdir)
    calls = []

    def interrupted_issue():
        assert gate_case.output.exists()
        assert tempfile.tempdir == str(gate_case.phase)
        calls.append("issue")
        raise RuntimeError("interrupted public issuer")

    monkeypatch.setattr(owner, "issue_pinned_synthetic_runtime_authorization", interrupted_issue)
    assert replay.main() == 2
    report = json.loads(gate_case.output.read_text(encoding="utf-8"))
    assert report["status"] == owner.BLOCKED
    assert report["reason"] == "single_attempt_failed:RuntimeError:interrupted public issuer"
    assert report["synthetic_scenario_authorized"] is False
    assert report["provider_proof_issuance_attempts"] == 1
    assert report["provider_effect_accounting_complete"] is False
    assert report["provider_proof_consumed"] is False
    assert tempfile.tempdir == previous_tempdir
    with pytest.raises(FileExistsError):
        replay.main()
    assert calls == ["issue"]


def test_exception_in_negative_controls_preserves_effect_ledger_and_withdraws_authorization(
        gate_case, stubbed_issuance, monkeypatch):
    previous_tempdir = tempfile.tempdir

    def interrupted_matrix(outcome):
        raise RuntimeError("interrupted rejection controls")

    monkeypatch.setattr(owner, "negative_authentication_matrix", interrupted_matrix)
    assert replay.main() == 2
    report = json.loads(gate_case.output.read_text(encoding="utf-8"))
    assert report["status"] == owner.BLOCKED
    assert report["provider_effect_accounting_complete"] is True
    assert report["provider_proof_infrastructure_effects"] == stubbed_issuance.ledger
    assert report["cleanup_verified"] is True and report["remaining_phase_containers"] == 0
    assert report["authorization_withdrawn_after_failed_checks"] is True
    assert "synthetic_authorization" not in report
    assert stubbed_issuance.authorization.authorization_id not in stubbed_issuance.registry
    assert stubbed_issuance.provider_registry[stubbed_issuance.root.receipt_id]["object"] is stubbed_issuance.root
    assert stubbed_issuance.proof.consumed is False
    assert tempfile.tempdir == previous_tempdir


@pytest.mark.parametrize("matrix_owner", ("authorization", "provider"))
def test_failed_negative_matrix_withdraws_scope_without_consuming_provider(
        gate_case, stubbed_issuance, monkeypatch, matrix_owner):
    target = owner if matrix_owner == "authorization" else provider
    monkeypatch.setattr(target, "negative_authentication_matrix", lambda value: {"failed_control": False})
    provider_registry_before = dict(stubbed_issuance.provider_registry)
    assert replay.main() == 2
    report = json.loads(gate_case.output.read_text(encoding="utf-8"))
    assert report["status"] == owner.BLOCKED
    assert report["reason"] == "live_negative_matrix_failed"
    assert report["synthetic_scenario_authorized"] is False
    assert report["all_negative_controls_rejected"] is False
    assert report["authorization_withdrawn_after_failed_checks"] is True
    assert "synthetic_authorization" not in report
    assert report["withdrawn_authorization_report"]["authorization_id"] == stubbed_issuance.authorization.authorization_id
    assert stubbed_issuance.authorization.authorization_id not in stubbed_issuance.registry
    assert stubbed_issuance.provider_registry == provider_registry_before
    assert stubbed_issuance.proof.consumed is False
    assert report["provider_proof_consumed"] is False
    assert stubbed_issuance.calls == ["issue"]
