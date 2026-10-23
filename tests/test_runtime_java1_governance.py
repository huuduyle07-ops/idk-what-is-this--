"""Current Java phase governance, distinct from explicit frozen snapshot checks."""
from hashlib import sha256
import json
from pathlib import Path

import pytest

from core.phase_picker import pick_phase_candidates, summarize_phase_candidates
from core.phase_registry import load_phase_registry, summarize_phase_registry, validate_phase_registry
from tests._runtime_java1_maintenance import before_runtime_java1


_ROOT = Path(__file__).resolve().parents[1]
_REGISTRY = _ROOT / "docs/roadmap/phase_registry.json"


def _current():
    return load_phase_registry(str(_REGISTRY))


def test_current_registry_adds_one_narrow_runtime_infrastructure_phase():
    data = _current()
    assert validate_phase_registry(data)["is_valid"] is True
    phases = {phase["phase_id"]: phase for phase in data["phases"]}
    phase = phases["RUNTIME.JAVA.1"]
    assert len(data["phases"]) == 225
    assert summarize_phase_registry(data, report_id="java", created_at="fixed")["counts_by_track"]["CONTROL"] == 43
    assert phase["track"] == "CONTROL" and phase["status"] == "active"
    assert phase["budget_tier"] == "blocked"
    assert phase["automation_level"] == "LOCAL_1_PREPARE"
    assert phase["requires_sandbox"] is True
    assert phase["human_approval_required"] is True
    for field in ("network_allowed", "model_calls_allowed", "merge_allowed", "writes_real_repo"):
        assert phase[field] is False
    assert {"RUNTIME.SANDBOX.1", "PREFLIGHT.RUNTIME.1",
        "PATCH.CANDIDATE.BEHAVIOR.REFLECT.1", "PATCH.CANDIDATE.BEHAVIOR.EXEC.PLAN.1",
        "PATCH.CANDIDATE.BEHAVIOR.SPEC.1", "PATCH.CANDIDATE.VALIDATE.1A"} == set(phase["prerequisites"])
    assert phases["RUNTIME.SANDBOX.1"]["status"] == "complete"
    assert phases["PATCH.CANDIDATE.BEHAVIOR.EXECUTOR.1"]["status"] == "active"
    assert phases["PATCH.CANDIDATE.BEHAVIOR.EXECUTOR.1"]["risk_level"] == "blocked"


def test_current_picker_keeps_java_and_executor_blocked_without_authority():
    report = summarize_phase_candidates(pick_phase_candidates(_current()), report_id="java", created_at="fixed")
    assert report["registry_valid"] is True
    assert {phase["phase_id"] for phase in report["blocked"]} == {
        "RUNTIME.JAVA.1", "PATCH.CANDIDATE.BEHAVIOR.EXECUTOR.1"}
    java = next(phase for phase in report["blocked"] if phase["phase_id"] == "RUNTIME.JAVA.1")
    assert "budget_tier is blocked" in java["reasons"]
    assert report["bucket_counts"]["complete_or_history"] == 219
    assert report["bucket_counts"]["blocked"] == 2
    assert report["phase_count"] == 225
    assert report["top_recommendation"]["phase_id"] == "DOGFOOD.1B"
    for bucket in ("safe_to_prepare", "sandbox_required", "complete_or_history"):
        assert "RUNTIME.JAVA.1" not in {phase["phase_id"] for phase in report[bucket]}


def test_java_governance_forbids_frozen_owners_and_historical_receipts():
    phase = next(phase for phase in _current()["phases"] if phase["phase_id"] == "RUNTIME.JAVA.1")
    assert {"core/sandboxed_java_toolchain.py", "core/sandboxed_java_toolchain_probe.py",
        "core/sandboxed_java_toolchain_discovery.py", "tests/test_runtime_java1.py",
        "tests/test_runtime_java1_governance.py", "scripts/replay_runtime_java1.py",
        "docs/roadmap/RUNTIME_JAVA_1.md", "docs/roadmap/RUNTIME_JAVA_1_LOCAL.json"} <= set(phase["allowed_files"])
    for path in ("core/candidate_runtime_sandbox.py", "core/candidate_runtime_sandbox_probe.py",
        "core/behavioral_diagnostic_executor.py", "core/runtime_diagnostic_authorization.py",
        "core/behavioral_validation_specification.py", "core/read_only_reflection.py",
        "bank.java", "SavingAccount.java", "SavingAccountBehaviorTest.java",
        "docs/roadmap/RUNTIME_SANDBOX_1_LOCAL.json",
        "docs/roadmap/PATCH_CANDIDATE_BEHAVIOR_EXECUTOR_1_SYNTHETIC.json",
        "docs/roadmap/PREFLIGHT_RUNTIME_1_SYNTHETIC.json",
        "tests/test_phase_registry.py", "tests/test_phase_picker.py"):
        assert path in phase["forbidden_files"]
        assert path not in phase["allowed_files"]
    notes = " ".join(phase["notes"])
    for text in ("JAVA TOOLCHAIN CAPABILITY != CANDIDATE EXECUTION AUTHORITY",
        "JAVA TOOLCHAIN CAPABILITY != BEHAVIORAL EXECUTOR", "runtime_authority=false",
        "repository_write_authority=false", "apply_authority=false", "BANK execution=0",
        "PREFLIGHT.RUNTIME.1 authorization consumed=0", "no executor owner",
        "RUNTIME_JAVA_1_BLOCKED_TOOLCHAIN_UNAVAILABLE", "no always-on worker/service"):
        assert text in notes


def test_java_reversal_preserves_every_exact_historical_registry_byte():
    raw = _REGISTRY.read_bytes()
    restored = before_runtime_java1("docs/roadmap/phase_registry.json", raw)
    frozen_receipt = json.loads((_ROOT / "tests/fixtures/runtime_sandbox1_reversal.json").read_text(encoding="utf-8"))
    frozen = next(record for record in frozen_receipt["reversals"] if record["path"] == "docs/roadmap/phase_registry.json")
    assert sha256(restored).hexdigest() == frozen["post_sha256"]
    before = json.loads(restored)
    now = _current()
    assert now["phases"][:-1] == before["phases"]
    assert now["phases"][-1]["phase_id"] == "RUNTIME.JAVA.1"
    assert len(before["phases"]) == 224
    assert set(now) == set(before)
    assert now["schema_version"] == before["schema_version"]
    assert now["updated_at"] == before["updated_at"]
    assert before_runtime_java1("core/behavioral_diagnostic_executor.py", b"untouched") == b"untouched"


@pytest.mark.parametrize("mutation", (
    lambda raw: raw + b"\n",
    lambda raw: raw.replace(b'JAVA TOOLCHAIN CAPABILITY', b'FORGED TOOLCHAIN CAPABILITY', 1),
    lambda raw: raw.replace(b'"phase_id": "ROAD.1"', b'"phase_id": "ROAD.FORGED.1"', 1),
))
def test_java_reversal_rejects_any_unattributed_registry_mutation(mutation):
    with pytest.raises(AssertionError):
        before_runtime_java1("docs/roadmap/phase_registry.json", mutation(_REGISTRY.read_bytes()))
