"""Pure completeness audit: frozen contracts, fabricated records, no verifier run."""
from dataclasses import fields, replace
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tests._preflight_runtime1_guard import no_runtime_effects

with no_runtime_effects(strict=False):
    from core import java_runtime_compatibility as compat
    from core import sandboxed_java_discovery_continuation as continuation
    from core.runtime.synthetic import synthetic_runtime_authorization as auth


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs/roadmap/RUNTIME_JAVA_DISCOVERY_CONTRACT_1_REPORT.json"


@pytest.fixture(autouse=True)
def deny_effects():
    with no_runtime_effects(strict=True) as evidence:
        with patch("threading.Thread.start", side_effect=evidence.deny("thread_start")):
            yield
    assert evidence.denied_attempts == {}


def _inventory():
    d = continuation.discovery
    pair = d.LocalJavaToolchainPair(continuation.JAVA_PATH, continuation.JAVA_SHA256,
        continuation.JAVAC_PATH, continuation.JAVAC_SHA256, "/usr/local/bin/python", "a" * 64)
    target = d.LocalJavaArtifact(continuation.IMAGE, os="linux", architecture="amd64",
        toolchains=(pair,), status="local_java_toolchain_present")
    return d.LocalJavaDiscovery((target,), True, True, "fabricated_contract_control", "route", "version")


def test_downstream_requirement_does_not_pin_historical_selected_image():
    spec = auth.executor1r_decrement_3_spec()
    assert (spec.java_profile_id, spec.java_schema_version) == ("RUNTIME.JAVA.1", "runtime_java_1_v1")
    names = {f.name for f in fields(spec)}
    assert not names & {"image_identity", "java_path", "java_sha256", "javac_path",
        "javac_sha256", "controller_path", "controller_sha256"}
    assert compat.REQUIREMENT.java_profile_id == spec.java_profile_id
    assert compat.REQUIREMENT.java_schema_version == spec.java_schema_version


def test_compat1_independently_requires_discovery_and_receipt_witnesses():
    audit = compat.audit_java_runtime_compatibility()
    assert audit.status == compat.SEMANTIC_GAP
    assert audit.as_dict()["unproven_dimensions"] == ["runtime_receipt_semantics",
        "complete_local_artifact_discovery", "discovery_backend_binding"]
    assert not audit.contract_compatible and audit.compatibility_relation is None


def test_exact_positive_target_does_not_fill_incomplete_global_inventory():
    inv = replace(_inventory(), complete_inventory=False, reason="unrelated_image_unclassified")
    with patch.object(continuation.binding, "sandbox_backend_binding_satisfies_java1_discovery",
            side_effect=AssertionError("incomplete inventory must stop before binding")):
        with pytest.raises(continuation.ContinuationBlocked) as blocked:
            continuation._discovery_gates(None, inv)
    assert blocked.value.status == continuation.DISCOVERY_INCOMPLETE


def test_other_eligible_provider_does_not_violate_global_uniqueness_rule():
    inv = _inventory()
    other = replace(inv.artifacts[0], image_identity="sha256:" + "1" * 64)
    inv = replace(inv, artifacts=(other, *inv.artifacts))
    # This stub is a development predicate control, not live BIND evidence.
    with patch.object(continuation.binding, "sandbox_backend_binding_satisfies_java1_discovery",
            return_value=True):
        artifact, pair = continuation._discovery_gates(None, inv)
    assert artifact is inv.artifacts[1] and pair is artifact.toolchains[0]


@pytest.mark.parametrize("duplicate", ["record", "pair"])
def test_ambiguity_is_scoped_to_exact_target_record_and_pair(duplicate):
    inv = _inventory()
    if duplicate == "record":
        inv = replace(inv, artifacts=inv.artifacts * 2)
    else:
        inv = replace(inv, artifacts=(replace(inv.artifacts[0],
            toolchains=inv.artifacts[0].toolchains * 2),))
    with patch.object(continuation.binding, "sandbox_backend_binding_satisfies_java1_discovery",
            return_value=True):
        with pytest.raises(continuation.ContinuationBlocked) as blocked:
            continuation._discovery_gates(None, inv)
    assert blocked.value.status == continuation.PROVIDER_COHERENCE


def test_full_inventory_receipt_witness_depends_on_unrelated_records():
    inv = _inventory()
    other = replace(inv.artifacts[0], image_identity="sha256:" + "2" * 64,
        status="local_java_toolchain_absent", toolchains=())
    base_records, base_hash = continuation._canonical_inventory(inv)
    records, digest = continuation._canonical_inventory(replace(inv, artifacts=(*inv.artifacts, other)))
    reordered = continuation._canonical_inventory(replace(inv, artifacts=(other, *inv.artifacts)))
    assert len(base_records) == 1 and len(records) == 2
    assert base_hash != digest and (records, digest) == reordered


def test_report_fails_closed_and_defines_no_operational_schema():
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    assert report["semantic_conclusion"] == "REQUIREMENT_EVOLUTION_REQUIRED"
    assert report["report_only"] is True
    for name in ("provider_specific_proof_equivalent", "replacement_without_semantic_weakening",
            "old_contract_rewritten", "compat1_retroactively_changed", "remediation_implemented"):
        assert report[name] is False
    assert all(value == 0 and type(value) is int for value in report["operational_effect_counts"].values())
    assert report["global_uniqueness_required"] is False
    assert report["required_properties_unresolved"]
    assert all(row["classification"] in report["classification_vocabulary"]
        for row in report["named_occurrences"])


def test_occurrence_index_covers_preserved_historical_java_sources():
    import re
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    pattern = re.compile(r"\b(?:complete_inventory|complete_local_artifact_discovery|discovery_complete)\b")
    actual = []
    for filename in report["occurrence_source_files"]:
        for line, text in enumerate((ROOT / filename).read_text(encoding="utf-8").splitlines(), 1):
            for term in pattern.findall(text):
                actual.append((filename, line, term))
    indexed = [(row["file"], row["line"], row["term"]) for row in report["named_occurrences"]]
    assert sorted(actual) == sorted(indexed)
    assert all(row["downstream_decision"] for row in report["named_occurrences"])


def test_every_frozen_compat_dimension_is_accounted_for_without_new_relation():
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    assert {row["dimension"] for row in report["compat_dimension_matrix"]} == {
        row.dimension for row in compat.COMPARISON}
    assert report["global_negative_facts"]["no_other_eligible_provider"] == "not_required_or_proven"
    assert report["global_negative_facts"]["complete_absence_of_eligible_provider"] == "lost_by_exact_only_proof"
    assert any(row["comparison"] == "LOST" for row in report["property_matrix"])
    assert any(row["comparison"] == "CONDITIONAL_UNPROVEN" for row in report["property_matrix"])
