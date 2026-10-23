"""Pure frozen-contract proof and mismatches; no live providers are issued."""
import ast
from dataclasses import FrozenInstanceError, asdict, fields, replace
from hashlib import sha256
import inspect
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from tests._preflight_runtime1_guard import no_runtime_effects

with no_runtime_effects(strict=False):
    from core import java_runtime_compatibility as owner
    from core import sandboxed_java_toolchain as java1
    from core import sandboxed_java_positive_continuation as java1c
    from core.runtime.synthetic import synthetic_runtime_authorization as auth


@pytest.fixture(autouse=True)
def effects():
    with no_runtime_effects(strict=True) as evidence:
        with patch("threading.Thread.start", side_effect=evidence.deny("threading.Thread.start")):
            yield
    assert evidence.denied_attempts == {}


@pytest.fixture
def safe_patch(effects):
    with pytest.MonkeyPatch.context() as monkeypatch:
        yield monkeypatch


def test_exact_requirement_and_provider_have_typed_semantic_gap_and_no_bridge():
    result = owner.audit_java_runtime_compatibility()
    assert result.status == owner.SEMANTIC_GAP
    assert result.contract_compatible is result.live_provider_authenticated is False
    assert result.compatibility_relation is None and result.relation_count == 0
    assert result.as_dict()["unproven_dimensions"] == ["runtime_receipt_semantics",
        "complete_local_artifact_discovery", "discovery_backend_binding"]
    assert not hasattr(owner, "java_runtime_provider_satisfies_requirement")
    assert result == owner.audit_java_runtime_compatibility()


def test_requirement_bytes_and_public_schema_defaults_remain_exact():
    spec = auth.executor1r_decrement_3_spec()
    assert asdict(owner.REQUIREMENT) == {key: getattr(spec, key)
        for key in ("java_profile_id", "java_schema_version", "sandbox_profile_id", "sandbox_policy_sha256")}
    for kind, phase, schema in ((java1.SandboxedJavaToolchainDescriptor, "RUNTIME.JAVA.1", "runtime_java_1_v1"),
            (java1c.JavaContinuationDescriptor, "RUNTIME.JAVA.1C", "runtime_java_1c_v1")):
        defaults = {f.name: f.default for f in fields(kind)}
        assert (defaults["phase_id"], defaults["schema_version"]) == (phase, schema)
    assert java1c.POLICY_SHA256 == java1c.sandbox2.POLICY_SHA256 == owner.POLICY_SHA256
    assert java1c.IMAGE == owner.IMAGE


@pytest.mark.parametrize("key,value", [("java_profile_id", "RUNTIME.JAVA.1C"),
    ("java_profile_id", "RUNTIME.JAVA.FUTURE"), ("java_schema_version", "runtime_java_1c_v1"),
    ("sandbox_profile_id", "RUNTIME.SANDBOX.2"), ("sandbox_profile_id", "future_sandbox"),
    ("sandbox_policy_sha256", "0" * 64)])
def test_changed_requirement_and_caller_alias_are_rejected(key, value):
    result = owner.audit_java_runtime_compatibility(replace(owner.REQUIREMENT, **{key: value}))
    assert result.status == owner.UNPROVEN_REQUIREMENT and not result.contract_compatible


@pytest.mark.parametrize("key,value,status", [("phase_id", "RUNTIME.JAVA.1", owner.PROVIDER_AMBIGUITY),
    ("schema_version", "runtime_java_1_v1", owner.PROVIDER_AMBIGUITY),
    ("phase_id", "RUNTIME.JAVA.FUTURE", owner.PROVIDER_AMBIGUITY),
    ("phase_id", "caller-created-alias", owner.PROVIDER_AMBIGUITY),
    ("sandbox_phase_id", "RUNTIME.SANDBOX.1", owner.SANDBOX_BINDING),
    ("sandbox_phase_id", "RUNTIME.SANDBOX.FUTURE", owner.SANDBOX_BINDING),
    ("sandbox_schema_version", "runtime_sandbox_future_v1", owner.SANDBOX_BINDING),
    ("sandbox_policy_sha256", "0" * 64, owner.SANDBOX_BINDING)])
def test_original_java_wrong_schema_policy_and_future_profiles_fail_closed(key, value, status):
    changed = replace(owner.PROVIDER, **{key: value})
    result = owner.audit_java_runtime_compatibility(provider=changed)
    assert result.status == status and not result.contract_compatible
    assert getattr(changed, key) == value  # The audit did not rewrite the input.


def test_original_java1_with_sandbox2_cannot_be_accepted_by_identity_equality():
    original = replace(owner.PROVIDER, phase_id="RUNTIME.JAVA.1", schema_version="runtime_java_1_v1")
    assert original.phase_id == owner.REQUIREMENT.java_profile_id
    assert original.schema_version == owner.REQUIREMENT.java_schema_version
    assert original.sandbox_policy_sha256 == owner.REQUIREMENT.sandbox_policy_sha256
    assert owner.audit_java_runtime_compatibility(provider=original).status == owner.PROVIDER_AMBIGUITY


@pytest.mark.parametrize("row", owner.COMPARISON, ids=lambda row: row.dimension)
def test_same_phase_schema_policy_with_changed_or_weaker_semantics_is_rejected(row):
    changed = tuple((name, "weaker_or_unproven" if name == row.dimension else value)
        for name, value in owner.PROVIDER.semantic_dimensions)
    result = owner.audit_java_runtime_compatibility(provider=replace(owner.PROVIDER, semantic_dimensions=changed))
    assert result.status == owner.SEMANTIC_GAP
    assert result.reason == "caller_metadata_cannot_change_frozen_semantics"
    assert not result.contract_compatible


@pytest.mark.parametrize("value", [asdict(owner.PROVIDER), SimpleNamespace(**asdict(owner.PROVIDER)),
    {"phase_id": owner.PROVIDER.phase_id}, {"schema_version": owner.PROVIDER.schema_version},
    {"sandbox_policy_sha256": owner.POLICY_SHA256}, None])
def test_report_json_profile_only_schema_only_policy_only_and_foreign_objects_are_not_providers(value):
    result = owner.audit_java_runtime_compatibility(provider=value)
    assert result.status == owner.PROVIDER_AMBIGUITY
    assert result.live_provider_authenticated is result.contract_compatible is False


def test_caller_cannot_fill_contract_gaps_or_turn_metadata_into_authority():
    claimed = tuple((name, "proven" if name in {"complete_local_artifact_discovery", "discovery_backend_binding"}
        else value) for name, value in owner.PROVIDER.semantic_dimensions)
    assert owner.audit_java_runtime_compatibility(provider=replace(owner.PROVIDER,
        semantic_dimensions=claimed)).reason == "caller_metadata_cannot_change_frozen_semantics"
    result = owner.audit_java_runtime_compatibility()
    for key in ("compatibility_authority", "runtime_authority", "repository_write_authority",
            "apply_authority", "live_provider_authenticated", "identity_equality_asserted",
            "profile_schema_relabeling", "historical_receipts_rewritten"):
        assert getattr(result, key) is False
        with pytest.raises(FrozenInstanceError):
            setattr(result, key, True)
        with pytest.raises((ValueError, TypeError)):
            replace(result, **{key: True})


@pytest.mark.parametrize("gap", ["inventory", "backend_identity", "backend_version"])
def test_original_java_success_gate_rejects_missing_witness_before_runtime(gap, safe_patch):
    # Pure negative control: stub discovery/adapter data, never sign a positive
    # capability or launch a verifier. These are explicitly fabricated inputs.
    discovery = java1.discovery
    pair = discovery.LocalJavaToolchainPair("/opt/java/bin/java", "a" * 64,
        "/opt/java/bin/javac", "b" * 64, "/usr/local/bin/python", "c" * 64)
    artifact = discovery.LocalJavaArtifact(owner.IMAGE, os="linux", architecture="amd64",
        toolchains=(pair,), status="local_java_toolchain_present")
    inventory = discovery.LocalJavaDiscovery((artifact,), gap != "inventory", True, "test_only",
        "different" if gap == "backend_identity" else "fixed", "different" if gap == "backend_version" else "fixed")
    descriptor = SimpleNamespace(fingerprint="d" * 64, backend_identity="fixed", backend_version="fixed")
    receipt = SimpleNamespace(fingerprint="e" * 64)
    safe_patch.setattr(java1.sandbox, "get_verified_candidate_runtime_sandbox",
        lambda *args: SimpleNamespace(descriptor=descriptor, receipt=receipt))
    safe_patch.setattr(discovery, "discover_local_java_artifacts", lambda: inventory)
    def forbidden(*args, **kwargs):
        pytest.fail("original missing-witness gate reached runtime")
    safe_patch.setattr(java1, "_verify_image_boundary", forbidden)
    safe_patch.setattr(java1, "_invoke_java", forbidden)
    safe_patch.setattr(java1.tempfile, "TemporaryDirectory", forbidden)
    result, evidence = java1.verify_sandboxed_java_toolchain()
    assert evidence.status == java1.INCOMPATIBLE and not result.verified
    assert evidence.reason == ("java_artifact_discovery_incomplete" if gap == "inventory"
        else "java_runtime_boundary_incomplete:backend_binding_changed")
    assert not evidence.java_workload_launch_attempted


def test_continuation_does_not_prove_original_discovery_witnesses():
    for kind in (java1c.JavaContinuationReceipt, java1c.JavaContinuationDescriptor,
            java1c.sandbox2.ThreadCompatibleSandboxReceipt, java1c.sandbox2.ThreadCompatibleSandboxDescriptor):
        assert not {"discovery_complete", "artifact_inventory", "backend_identity", "backend_version"} & {
            f.name for f in fields(kind)}
    source = inspect.getsource(java1c.verify)
    assert "discover_local_java_artifacts" not in source
    assert "complete_inventory" not in source


def test_comparison_covers_required_dimensions_and_owner_imports_are_pure():
    assert len(owner.COMPARISON) == len({row.dimension for row in owner.COMPARISON}) == 36
    assert all(row.evidence and row.required and row.provider for row in owner.COMPARISON)
    tree = ast.parse(Path(owner.__file__).read_text(encoding="utf-8"))
    imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
    assert len(imports) == 1 and imports[0].module == "dataclasses"
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id in {"open", "exec", "eval", "compile", "__import__"} for node in ast.walk(tree))


def test_exact_frozen_artifact_and_invocation_evidence_is_not_name_inference():
    from scripts.replay_runtime_java_compat1 import ROOT
    original = json.loads((ROOT / "docs/roadmap/RUNTIME_JAVA_1_LOCAL.json").read_text())
    continued = json.loads((ROOT / "docs/roadmap/RUNTIME_JAVA_1C_LOCAL.json").read_text())
    selected = original["explicit_artifact_selection"]
    receipt = continued["verification_receipt"]
    assert selected["image_identity"] == receipt["image_identity"] == owner.IMAGE
    for kind in ("java", "javac"):
        assert selected["toolchain"][kind + "_path"] == receipt[kind + "_path"]
        assert selected["toolchain"][kind + "_sha256"] == receipt[kind + "_sha256"]
    assert java1.JAVA_SOURCE == java1c.probe.JAVA_SOURCE
    assert sha256(java1.JAVA_SOURCE).hexdigest() == receipt["source_sha256"]
    assert tuple(receipt["compile_argv"]) == (receipt["javac_path"], *java1.COMPILE_ARGUMENTS)
    assert tuple(receipt["runtime_argv"]) == (receipt["java_path"], *java1.RUNTIME_ARGUMENTS)
    assert original["descriptor"]["verified"] is False  # Historical failure is preserved.


def test_strict_recorded_audit_has_zero_effects_and_exports_no_live_claim():
    from scripts.replay_runtime_java_compat1 import replay
    report = replay()
    assert report["status"] == owner.SEMANTIC_GAP
    assert report["effect_denial"]["denied_attempts"] == {}
    assert report["source_projection"] is False
    for key in ("docker_calls", "containers_created", "java_executions", "javac_executions",
            "child_processes", "network_calls", "runtime_lease_consumptions", "reflection_lease_consumptions",
            "repository_runtime_writes", "apply_actions", "bank_executions", "executor1r_retries"):
        assert report[key] == 0
    assert report["live_provider_authenticated"] is False
    assert report["report_only"] is True
    assert owner.audit_java_runtime_compatibility(provider=json.loads(json.dumps(report))).status == owner.PROVIDER_AMBIGUITY
