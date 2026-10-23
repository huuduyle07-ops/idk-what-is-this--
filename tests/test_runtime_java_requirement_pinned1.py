"""Pure additive requirement freeze; no provider proof or runtime is issued."""
import ast
import builtins
from dataclasses import FrozenInstanceError, asdict, fields, replace
import json
from pathlib import Path
import sys
from types import ModuleType
from unittest.mock import patch

import pytest

from tests._preflight_runtime1_guard import no_runtime_effects

with no_runtime_effects(strict=False):
    from core import java_runtime_compatibility as old_compat
    from core import runtime_java_pinned_requirement as owner
    from core.runtime.synthetic import synthetic_runtime_authorization as auth


@pytest.fixture(autouse=True)
def deny_effects():
    with no_runtime_effects(strict=True) as evidence:
        with patch("threading.Thread.start", side_effect=evidence.deny("thread_start")):
            yield
    assert evidence.denied_attempts == {}


def test_additive_requirement_has_exact_distinct_identity_and_no_alias():
    requirement = owner.REQUIREMENT
    assert owner.PHASE_ID == "RUNTIME.JAVA.REQUIREMENT.PINNED.1"
    assert owner.COMPLETE == "RUNTIME_JAVA_REQUIREMENT_PINNED_1_COMPLETE"
    assert requirement.phase_id == owner.PHASE_ID
    assert requirement.java_profile_id == owner.PROFILE_ID == "RUNTIME.JAVA.PINNED.1"
    assert requirement.java_schema_version == owner.SCHEMA_VERSION == "runtime_java_pinned_1_v1"
    assert requirement.profile_alias is requirement.schema_alias is None
    assert requirement.old_requirement_preserved is True
    assert requirement.old_java1_compatibility_asserted is False
    assert (requirement.java_profile_id, requirement.java_schema_version) != (
        old_compat.REQUIREMENT.java_profile_id, old_compat.REQUIREMENT.java_schema_version)


def test_exact_image_and_binary_pins_are_independent_of_historical_selection():
    requirement = owner.REQUIREMENT
    assert requirement.image_identity == (
        "sha256:f6d7dc31a15bb37a618ebed6772beda3de95fdcc3394eb5a1def9b1d20673f7a")
    assert asdict(requirement.java) == {
        "path": "/opt/temurin-26.0.2.1/bin/java",
        "sha256": "a719fab9108ba87eba82655ba904edbee0a91ff13365579519f44f99100382b2",
    }
    assert asdict(requirement.javac) == {
        "path": "/opt/temurin-26.0.2.1/bin/javac",
        "sha256": "e21c219e342544cbf107d25e86ed1d809eac6cc57bce8f68750a42783f13e023",
    }
    assert requirement.provider_selection == "exact_required_immutable_provider_only_no_selection_step"
    assert requirement.mismatch_action == "BLOCK"
    assert requirement.fallback_allowed is requirement.tag_selection_allowed is False
    assert requirement.provisioning_allowed is False


@pytest.mark.parametrize("value", [owner.REQUIREMENT, owner.REQUIREMENT.java,
    owner.REQUIREMENT.javac, owner.REQUIREMENT.controller, owner.REQUIREMENT.inspection_bounds,
    *owner.EVIDENCE_GRAPH, *owner.NEGATIVE_OUTCOMES])
def test_requirement_metadata_and_nested_records_are_immutable(value):
    field = fields(value)[0]
    with pytest.raises(FrozenInstanceError):
        setattr(value, field.name, "caller replacement")
    assert not hasattr(value, "__dict__")


@pytest.mark.parametrize("name", ["global_inventory_required", "global_inventory_claimed",
    "global_provider_absence_claimed", "global_provider_uniqueness_required",
    "global_provider_uniqueness_claimed", "inventory_boolean_adapter_allowed", "fallback_allowed",
    "tag_selection_allowed", "provisioning_allowed", "chronology_accepted_as_provenance",
    "old_java1_compatibility_asserted", "synth_auth1_modified", "runtime_authority",
    "repository_write_authority", "apply_authority", "provider_proof_issued"])
def test_metadata_cannot_enable_prohibited_claims_or_authority(name):
    assert getattr(owner.REQUIREMENT, name) is False
    with pytest.raises((ValueError, TypeError)):
        replace(owner.REQUIREMENT, **{name: True})


def test_controller_requires_authenticated_measurement_without_an_invented_pin():
    controller = owner.REQUIREMENT.controller
    assert controller.path == "/usr/local/bin/python"
    assert controller.identity_kind == "exact_path_and_owner_authenticated_runtime_measurement"
    assert controller.pinned_sha256 is None
    obligations = " ".join(controller.proof_obligations)
    for required in ("SHA-256", "resolved path", "image identity", "runtime controller",
            "same measured executable", "controller source identity", "runtime evidence digest",
            "JAVA.1C currently lacks", "additive authenticated measurement attachment",
            "No stable fixed controller digest"):
        assert required in obligations


def test_target_inspection_retains_original_bounds_and_local_safety():
    bounds = asdict(owner.REQUIREMENT.inspection_bounds)
    assert bounds == {"export_timeout_ms": 30_000, "max_archive_bytes": 2 * 1024**3,
        "max_archive_entries": 250_000, "max_executable_bytes": 128 * 1024**2,
        "max_link_hops": 40}
    assert all(type(value) is int for value in bounds.values())
    safety = dict(owner.REQUIREMENT.target_local_safety)
    assert len(safety) == len(owner.TARGET_LOCAL_SAFETY)
    assert set(safety) == {"immutable_image", "platform", "java_identity", "javac_identity",
        "toolchain_pair", "controller_identity", "path_normalization", "root_escape_prevention",
        "link_bounds", "nonroot_access", "no_extraction", "no_inspection_execution",
        "bounded_archive", "bounded_executable", "safe_inspection_container",
        "no_declared_volumes", "cleanup", "no_pull", "no_build", "no_tag_substitution",
        "no_fallback"}
    for required in ("linux", "amd64", "ELF64", "little-endian", "machine 62"):
        assert required in safety["platform"]
    assert "same-directory" in safety["toolchain_pair"]
    assert "ambiguous" in safety["toolchain_pair"]
    assert "symlink/hardlink cycles" in safety["link_bounds"]
    assert "uid/gid 65534" in safety["nonroot_access"]
    assert "never extract" in safety["no_extraction"]
    assert "no container start" in safety["no_inspection_execution"]
    assert "image-declared volumes" in safety["no_declared_volumes"]
    assert "independently verify absence" in safety["cleanup"]


def test_exact_sandbox2_and_runtime_constraints_remain_mandatory():
    requirement = owner.REQUIREMENT
    assert requirement.sandbox_profile_id == "runtime_sandbox_2_v1"
    assert requirement.sandbox_policy_sha256 == (
        "5a36bdf1676c4b0d7b4bef489f5e90b5c8fb201b5194be48baf61f4206a81f75")
    runtime = dict(requirement.runtime_safety)
    assert set(runtime) == {"sandbox", "invocation", "versions", "isolation", "identity",
        "containment", "resources", "controller_threads", "capture", "source_class_output",
        "cleanup", "authority"}
    assert "RUNTIME.JAVA.1C/runtime_java_1c_v1" in runtime["invocation"]
    assert "no caller command/flags/source" in runtime["invocation"]
    for required in ("128 PIDs", "134217728", "1000000000", "/work 32 MiB", "/tmp 16 MiB"):
        assert required in runtime["resources"]
    for required in ("10000 ms", "5000 ms", "8192 each", "1024 each", "2048 each"):
        assert required in runtime["capture"]
    assert "zero Thread.start attempts" in runtime["controller_threads"]
    assert "129-byte" in runtime["source_class_output"]
    assert "1..32768 bytes" in runtime["source_class_output"]
    assert "both EOFs" in runtime["cleanup"]


def test_exact_proof_never_becomes_inventory_or_global_absence():
    requirement = owner.REQUIREMENT
    assert requirement.proof_kind == "exact_provider_proven"
    assert set(requirement.forbidden_equivalences) >= {
        "exact_provider_proven != complete_inventory",
        "exact_provider_proven != complete_local_artifact_discovery",
        "target_provider_absent != global_java_provider_absent",
        "event A happened before event B != A and B are authenticated as one provider proof",
        "provider evidence != requirement identity",
    }
    assert dict(requirement.old_new_semantic_differences).keys() == {
        "generic_ordered_provider_selection", "complete_domain_classification",
        "full_authenticated_inventory_witness", "global_absence_reporting"}
    assert "unrelated local images need no inspection/classification" in dict(
        requirement.old_new_semantic_differences)["complete_domain_classification"]


def test_future_receipt_is_explicit_obligation_and_contains_no_inventory_shim():
    requirement = owner.REQUIREMENT
    assert requirement.report_only is requirement.requirement_only is True
    assert requirement.provider_proof_issued is False
    assert requirement.future_receipt_fields == (
        "exact_provider_proven=true", "provider_image_identity", "provider_java_identity",
        "provider_javac_identity", "provider_controller_identity", "target_inspection_evidence",
        "backend_binding_evidence", "sandbox_evidence", "runtime_evidence", "cleanup_evidence")
    assert not any("complete_inventory" in field for field in requirement.future_receipt_fields)
    assert "coherently bound to the required backend and runtime evidence" in (
        requirement.required_future_receipt_statement)
    projection = requirement.as_dict()
    projection["java"]["sha256"] = "0" * 64
    assert requirement.java.sha256 != projection["java"]["sha256"]
    assert "exact_provider_proven" not in {field.name for field in fields(requirement)}


@pytest.mark.parametrize("code,condition_fragment", [
    ("PINNED_PROVIDER_ABSENT", "conclusively unavailable locally"),
    ("PINNED_PROVIDER_METADATA_MISMATCH", "Image ID/platform/volume/container"),
    ("PINNED_PROVIDER_INSPECTION_INCOMPLETE", "truncated/over-budget"),
    ("PINNED_TOOLCHAIN_MISMATCH", "path/hash/ELF/access/pair"),
    ("PINNED_CONTROLLER_MISMATCH", "authenticity/runtime linkage"),
    ("PINNED_BACKEND_BINDING_MISMATCH", "Route/version/sandbox-pair/owner/target"),
    ("PINNED_RUNTIME_EVIDENCE_MISMATCH", "Fresh JAVA.1C authenticity/identity/digest/constraints/linkage"),
    ("PINNED_CLEANUP_FAILURE", "inspection/backend/sandbox/runtime cleanup"),
    ("PINNED_PROOF_UNRESOLVED", "unknown or unclassified"),
])
def test_every_negative_outcome_blocks_without_fallback_or_global_absence(code, condition_fragment):
    outcomes = {row.code: row for row in owner.NEGATIVE_OUTCOMES}
    assert len(outcomes) == len(owner.NEGATIVE_OUTCOMES) == 9
    row = outcomes[code]
    assert condition_fragment in row.condition
    assert row.blocks_provider_proof is True
    assert row.fallback_allowed is row.global_absence_claimed is False
    for name, value in (("blocks_provider_proof", False), ("fallback_allowed", True),
            ("global_absence_claimed", True)):
        with pytest.raises((ValueError, TypeError)):
            replace(row, **{name: value})


def test_absence_and_incomplete_inspection_remain_different_negative_facts():
    outcomes = {row.code: row for row in owner.NEGATIVE_OUTCOMES}
    assert "never NO_SUITABLE_LOCAL_JAVA_ARTIFACT" in outcomes["PINNED_PROVIDER_ABSENT"].meaning
    assert "global_java_provider_absent" in outcomes["PINNED_PROVIDER_ABSENT"].meaning
    assert "cannot imply target absence" in outcomes["PINNED_PROVIDER_INSPECTION_INCOMPLETE"].meaning
    assert "no provider proof or absence inference" in outcomes["PINNED_PROOF_UNRESOLVED"].meaning


def test_evidence_graph_binds_explicit_cross_owner_identities_and_cleanup():
    edges = {(row.source, row.target): row for row in owner.EVIDENCE_GRAPH}
    assert len(edges) == len(owner.EVIDENCE_GRAPH) == 11
    required_equalities = {
        ("backend_binding", "target_inspection"): {
            ("canonical_backend_identity", "backend_route_identity"),
            ("canonical_backend_version", "backend_server_version"),
            ("target_image_identity", "target_image_identity"),
            ("target_inspection_evidence_fingerprint", "evidence_fingerprint"),
            ("target_inspection_owner_identity", "owner_identity")},
        ("target_inspection", "provider_identity"): {
            ("evidence_fingerprint", "target_inspection_evidence_fingerprint"),
            ("target_image_identity", "provider_image_identity"),
            ("java_path", "java_path"), ("java_sha256", "java_sha256"),
            ("javac_path", "javac_path"), ("javac_sha256", "javac_sha256"),
            ("controller_path", "controller_path"),
            ("controller_resolved_path", "controller_resolved_path"),
            ("controller_measured_sha256", "controller_measured_sha256")},
        ("backend_binding", "backend_binding_sandbox"): {
            ("sandbox_descriptor_fingerprint", "descriptor_fingerprint"),
            ("sandbox_receipt_fingerprint", "receipt_fingerprint"),
            ("sandbox_receipt_evidence_digest", "receipt_evidence_digest"),
            ("target_image_identity", "image_identity"),
            ("canonical_backend_identity", "backend_route_identity"),
            ("canonical_backend_version", "backend_server_version")},
        ("backend_binding_sandbox", "java1c_sandbox"): {
            ("image_identity", "image_identity"),
            ("backend_route_identity", "backend_route_identity"),
            ("backend_server_version", "backend_server_version")},
        ("java1c_sandbox", "runtime"): {
            ("descriptor_fingerprint", "sandbox_descriptor_fingerprint"),
            ("receipt_fingerprint", "sandbox_receipt_fingerprint"),
            ("receipt_evidence_digest", "sandbox_receipt_evidence_digest"),
            ("image_identity", "java1c_image_identity"),
            ("backend_route_identity", "backend_route_identity"),
            ("backend_server_version", "backend_server_version")},
        ("provider_identity", "runtime"): {
            ("provider_image_identity", "java1c_image_identity"),
            ("java_path", "java_path"), ("java_sha256", "java_sha256"),
            ("javac_path", "javac_path"), ("javac_sha256", "javac_sha256"),
            ("controller_path", "controller_path"),
            ("controller_resolved_path", "controller_resolved_path"),
            ("controller_measured_sha256", "controller_measured_sha256")},
        ("target_inspection", "cleanup"): {
            ("evidence_fingerprint", "target_inspection_evidence_fingerprint"),
            ("cleanup_result", "target_inspection_cleanup_result")},
        ("runtime", "cleanup"): {
            ("java1c_receipt_fingerprint", "java1c_receipt_fingerprint"),
            ("cleanup_result", "runtime_cleanup_result")},
        ("backend_binding", "cleanup"): {
            ("evidence_fingerprint", "backend_binding_evidence_fingerprint"),
            ("cleanup_result", "backend_binding_cleanup_result")},
        ("backend_binding_sandbox", "cleanup"): {
            ("receipt_fingerprint", "backend_binding_sandbox_receipt_fingerprint"),
            ("cleanup_result", "backend_binding_sandbox_cleanup_result")},
        ("java1c_sandbox", "cleanup"): {
            ("receipt_fingerprint", "sandbox_receipt_fingerprint"),
            ("cleanup_result", "sandbox_cleanup_result")},
    }
    assert set(edges) == set(required_equalities)
    for endpoints, equalities in required_equalities.items():
        assert set(edges[endpoints].equalities) >= equalities
        assert edges[endpoints].obligation


def test_graph_names_every_required_fingerprint_and_authenticates_final_proof_root():
    assert set(owner.EVIDENCE_FIELDS) >= {
        "proof_owner_identity", "proof_context_identity", "requirement_profile", "requirement_schema",
        "target_inspection_owner_identity", "target_image_identity", "backend_route_identity",
        "backend_server_version", "target_inspection_evidence_fingerprint",
        "backend_binding_evidence_fingerprint", "backend_binding_sandbox_descriptor_fingerprint",
        "backend_binding_sandbox_receipt_fingerprint", "backend_binding_sandbox_receipt_evidence_digest",
        "sandbox_pair_bridge_evidence_fingerprint",
        "sandbox_descriptor_fingerprint", "sandbox_receipt_fingerprint", "sandbox_receipt_evidence_digest",
        "java1c_descriptor_fingerprint", "java1c_receipt_fingerprint", "java1c_receipt_evidence_digest",
        "java1c_image_identity", "java_path", "java_sha256", "javac_path", "javac_sha256",
        "controller_path", "controller_resolved_path", "controller_measured_sha256",
        "controller_runtime_identity_evidence_fingerprint", "controller_source_identity",
        "cleanup_result", "cleanup_evidence_fingerprint",
    }
    assert len(set(owner.EVIDENCE_FIELDS)) == len(owner.EVIDENCE_FIELDS)
    authentication = " ".join(owner.EVIDENCE_AUTHENTICATION)
    for required in ("authenticate every node and edge", "one final proof root",
            "new requirement profile/schema", "issuer/owner", "fresh owner-established proof context",
            "original typed evidence", "canonical full-payload SHA-256", "domain-separated",
            "report JSON", "copied objects", "caller-supplied strings", "Hash equality",
            "Common process, endpoint or time order supplies no binding",
            "Missing, conflicting, stale, fabricated, incomplete or unauthenticated evidence blocks"):
        assert required in authentication


def test_frozen_bind_and_java1c_are_components_with_explicit_additive_bridges():
    authentication = " ".join(owner.EVIDENCE_AUTHENTICATION)
    assert "sandbox_backend_binding_satisfies_java1_discovery requires original discovery-owner evidence" in authentication
    assert "must not be repurposed for target inspection" in authentication
    assert "A fresh BIND alone is insufficient" in authentication
    assert "daemon instance identity, continuity and ABA resistance are not established or claimed" in authentication
    assert "Fresh JAVA.1C is one runtime component" in authentication
    edges = {(row.source, row.target): row.obligation for row in owner.EVIDENCE_GRAPH}
    bridge = edges["backend_binding_sandbox", "java1c_sandbox"]
    for required in ("both exact sandbox pairs", "target inspection fingerprint/owner",
            "distinct fingerprints/digests", "owner-authenticated route/version bridge",
            "never equate pair fingerprints", "Never assume pairs are identical"):
        assert required in bridge
    bridge_edge = next(row for row in owner.EVIDENCE_GRAPH
        if (row.source, row.target) == ("backend_binding_sandbox", "java1c_sandbox"))
    assert all("fingerprint" not in field and "digest" not in field
        for equality in bridge_edge.equalities for field in equality)
    assert "Frozen JAVA.1C lacks these cross-owner/controller fields" in edges["provider_identity", "runtime"]
    assert "exact JAVA.1C receipt fingerprint" in edges["java1c_sandbox", "runtime"]


def test_old_authorization_projection_does_not_migrate_to_the_new_epoch():
    spec = auth.executor1r_decrement_3_spec()
    assert (spec.java_profile_id, spec.java_schema_version) == ("RUNTIME.JAVA.1", "runtime_java_1_v1")
    assert asdict(old_compat.REQUIREMENT) == {name: getattr(spec, name) for name in (
        "java_profile_id", "java_schema_version", "sandbox_profile_id", "sandbox_policy_sha256")}
    assert not {"image_identity", "java", "javac", "controller"} & {field.name for field in fields(spec)}
    requirement = owner.REQUIREMENT
    assert requirement.synth_auth1_modified is False
    assert requirement.future_synth_authorization_epoch_required is True
    assert "SYNTH.AUTH.PINNED.1" in requirement.future_authorization_epoch
    assert "SYNTH.AUTH.LIFECYCLE.1 acceptance" in requirement.lifecycle_boundary
    assert "cannot be assumed or migrated" in requirement.lifecycle_boundary
    assert requirement.proposed_future_chain == (owner.PHASE_ID,
        "target-specific provider proof implementation", "provider proof validation",
        "new SYNTH authorization epoch", "lifecycle compatibility review", "operational EXECUTOR retry")


def test_report_projects_exact_requirement_without_operational_or_inventory_claims():
    report_path = Path(__file__).resolve().parents[1] / (
        "docs/roadmap/phases/RUNTIME_JAVA_REQUIREMENT_PINNED_1/"
        "RUNTIME_JAVA_REQUIREMENT_PINNED_1_REPORT.json")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["phase_id"] == owner.PHASE_ID
    assert report["status"] == owner.COMPLETE
    assert report["requirement"] == json.loads(json.dumps(owner.REQUIREMENT.as_dict()))
    assert report["report_only"] is report["requirement_only"] is True
    assert all(type(value) is int and value == 0 for value in report["operational_effect_counts"].values())
    for name in ("future_receipt_issued", "runtime_capability_issued", "provider_implementation_added",
            "compat2_created", "java1d_retried", "executor1r_retried",
            "old_java1_satisfied_new_requirement_claimed", "existing_auth_handles_migrated",
            "existing_lifecycle_semantics_modified", "runtime_consumers_modified", "registry_modified",
            "historical_drift_repinned", "resource_bounds_changed",
            "unrelated_image_diagnostic_justifies_target_timeout_change"):
        assert report[name] is False


def test_owner_import_and_projection_are_pure_without_loading_runtime_owners():
    source_path = Path(owner.__file__)
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source_path))
    imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
    assert all(isinstance(node, ast.ImportFrom) and node.module == "dataclasses" for node in imports)
    assert not any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) for node in tree.body)
    for name in ("verify", "replay", "issue", "validate_descriptor", "validate_provider_proof",
            "java_runtime_provider_satisfies_requirement", "discover_local_java_artifacts",
            "get_verified_candidate_runtime_java_toolchain", "execute", "run"):
        assert not hasattr(owner, name)
    imported = []
    original_import = builtins.__import__

    def track_import(name, *args, **kwargs):
        imported.append(name)
        return original_import(name, *args, **kwargs)

    probe_name = "_runtime_java_pinned_requirement_purity_probe"
    probe = ModuleType(probe_name)
    with patch.dict(sys.modules, {probe_name: probe}), patch("builtins.__import__", track_import):
        exec(compile(source, str(source_path), "exec"), probe.__dict__)
        assert probe.REQUIREMENT.as_dict() == owner.REQUIREMENT.as_dict()
    assert "dataclasses" in imported
    assert not {name.split(".")[0] for name in imported} & {
        "core", "scripts", "subprocess", "socket", "threading", "multiprocessing"}
