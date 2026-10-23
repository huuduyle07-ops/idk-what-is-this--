"""Finalize report-only evidence; no owner imports or operational entry points."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
CONTRACT_PATH = ROOT / "docs/roadmap/phases/SYNTH_AUTH_LIFECYCLE_PINNED_CONTRACT_1/contract.json"


def load(name):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def save(name, value):
    (HERE / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main():
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    baseline, focused, implementation = (load(name) for name in (
        "focused_baseline.json", "focused.json", "implementation.json"))
    initial = load("implementation_initial.json")
    registry, benchmark, preservation, static, review = (load(name) for name in (
        "registry_comparison.json", "benchmark.json", "preservation_check.json",
        "static_validation.json", "implementation_review.json"))
    for result in (baseline, focused, implementation, benchmark):
        assert result["exit_code"] == 0 and result["all_operational_effects_zero"], result["mode"]
    assert not implementation["failed"] and not implementation["skipped"]
    assert registry["all_compared_fields_unchanged"] and registry["guard_baseline_zero"] and registry["guard_after_zero"]
    assert preservation["historical_bytes_preserved"] and static["all_checks_passed"]
    git_check = load("git_diff_check.json")
    assert git_check["exit_code"] == 0
    owner = contract["proposed_owner"]
    owner_path = ROOT / (owner["owner_identity"].replace(".", "/") + ".py")
    source_paths = [owner_path, ROOT / "tests/test_synthetic_runtime_authorization_pinned_lifecycle.py",
        CONTRACT_PATH, *[ROOT / name for name in (
            "core/synthetic_runtime_authorization.py", "core/synthetic_runtime_authorization_lifecycle.py",
            "core/synthetic_runtime_authorization_pinned.py", "core/runtime_java_pinned_provider.py",
            "core/runtime_java_pinned_requirement.py", "core/synthetic_read_only_reflection.py",
            "core/synthetic_reflection_execution_admission.py", "core/synthetic_reflection_execution_lifecycle.py")]]
    hashes = {path.relative_to(ROOT).as_posix(): sha256(path.read_bytes()).hexdigest() for path in source_paths}
    assert review["status"] == "NO_CONTRACT_BLOCKER_FOUND"
    assert review["reviewed_source_sha256"] == hashes[owner_path.relative_to(ROOT).as_posix()]
    policy_bytes = json.dumps(contract["activation_policy"], sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    domain = contract["authentication_domain"]["domain"]
    policy_digest = sha256(domain.encode("utf-8") + b"\x00activation-policy\x00" + policy_bytes).hexdigest()
    validation = {
        "typed_status": "SYNTH_AUTH_LIFECYCLE_PINNED_1A_COMPLETE",
        "focused_implementation": {"passed": implementation["passed_count"], "failed": 0, "artifact": "implementation.json"},
        "initial_implementation_run": {"passed": initial["passed_count"], "failed": len(initial["failed"]),
            "reason": "Race-test instrumentation counted record signature verification as terminal commits; corrected to assert actual owner-store publication. No consumer gate or implementation semantics changed.",
            "artifacts": ["implementation_initial.json", "implementation_initial.txt"]},
        "frozen_safe_baseline": {"passed": baseline["passed_count"], "failed": 0, "artifact": "focused_baseline.json"},
        "frozen_safe_after": {"passed": focused["passed_count"], "failed": 0, "artifact": "focused.json",
            "excluded_stage_snapshot": focused["exclusion_reason"]},
        "registry_picker": {"unchanged": True, "baseline_passed": registry["baseline_passed_count"],
            "after_passed": registry["after_passed_count"], "existing_failures": registry["after_failed"],
            "existing_failure_count": len(registry["after_failed"]), "artifact": "registry_comparison.json"},
        "benchmark_check": {"passed": True, "artifact": "benchmark.json"},
        "in_memory_compilation_JSON_whitespace": {"passed": True, "artifact": "static_validation.json"},
        "git_diff_check": git_check,
        "historical_preservation": preservation,
        "all_operational_effects_zero": True,
        "full_suite_claimed": False,
        "issuance_dependent_frozen_suites_run": False,
        "production_validators_patched": False,
        "production_registries_seeded": False,
        "isolated_test_only_owner_calls": implementation["inert_new_owner_calls"],
    }
    save("validation_summary.json", validation)
    report = {
        "typed_status": validation["typed_status"], "phase": "SYNTH.AUTH.LIFECYCLE.PINNED.1A",
        "date_KST": "2026-10-13", "implementation_phase_id": owner["phase_id"],
        "module": owner["owner_identity"], "type": owner["exact_type"], "schema": owner["schema_version"],
        "completion_meaning": "The additive pinned lifecycle owner is implemented and pure-validated against the frozen contract. No operational lease has been issued or consumed.",
        "public_APIs": [item["name"] for item in contract["public_api"]["operations"]],
        "source_sha256": hashes,
        "scenario_source_sha256": contract["scenario"]["source_sha256"],
        "scenario_definition_sha256": contract["scenario"]["definition_sha256"],
        "old_owner_changed": False, "old_consumption_policy_changed": False,
        "pinned_auth_owner_changed": False, "provider_owner_changed": False,
        "reflection_owners_changed": False, "phase_registration_performed": False,
        "state_machine": {"states": contract["state_machine"]["states"],
            "transitions": contract["state_machine"]["transitions"],
            "consumption_transition_operationally_available": False,
            "ISSUED": {"validation": "same original lease", "state_read": "ISSUED",
                "local_ready": True, "behavioral_ready": False, "reason": "PROOF_UNRESOLVED",
                "consume": "PROOF_UNRESOLVED; no mutation", "invalidate": "INVALIDATED"},
            "CONSUMED": {"validation": "same original lease if upstream still authenticates", "state_read": "CONSUMED",
                "local_ready": False, "behavioral_ready": False, "reason": "LEASE_ALREADY_CONSUMED",
                "consume": "LEASE_ALREADY_CONSUMED", "invalidate": "LEASE_ALREADY_CONSUMED"},
            "INVALIDATED": {"validation": "same original lease if upstream still authenticates", "state_read": "INVALIDATED",
                "local_ready": False, "behavioral_ready": False, "reason": "LEASE_INVALIDATED",
                "consume": "LEASE_INVALIDATED", "invalidate": "LEASE_INVALIDATED"},
            "terminal_reissue": "DUPLICATE_LEASE_ISSUANCE", "refund": False,
            "collection_reopens_issuance": False, "tombstone_lifetime": "owner process lifetime"},
        "one_shot_key": {"fields": contract["state_machine"]["one_shot_key_fields"],
            "source": "exact original pinned authorization returned by unchanged public validator",
            "owner_phase_schema_PID_are_upstream_authorization_fields": True,
            "alternate_keys": False},
        "authentication": {"domain": domain, "roles": contract["authentication_domain"]["roles"],
            "record_algorithm": "HMAC-SHA256 with independent private 32-byte secret",
            "public_digest_algorithm": "SHA256, domain and role framed",
            "framing": "domain + NUL + role + NUL + canonical UTF-8 JSON",
            "canonical_types": "exact primitives, string dictionary keys, exact nested lists; no numeric/subclass aliases or nonfinite values",
            "JSON_options": "sort_keys=True; separators=(comma, colon); allow_nan=False",
            "activation_policy_identity": contract["activation_policy"]["identity"],
            "activation_policy_digest": policy_digest,
            "private_signature_or_secret_exported": False,
            "every_operation_revalidates_original_upstream_and_provider": True},
        "provider_decision": "B", "provider_fields_bound": contract["provider_provenance"]["projection_fields"],
        "authority_matrix": {state: dict.fromkeys(contract["authority"]["false_in_all_states"], False)
            for state in contract["state_machine"]["states"]},
        "lease_issued_is_immutable_historical_fact": True,
        "runtime_activation_consumed": "derived only from authenticated current state == CONSUMED",
        "readiness": {"report_only": True, "ISSUED_local_preconditions_satisfied": True,
            "behavioral_activation_ready": False, "reason": "PROOF_UNRESOLVED",
            "is_capability_token_reservation_or_execution_authority": False},
        "consume_behavior": "Reauthenticate under lock, check ISSUED, reject PROOF_UNRESOLVED before signing or replacing state; no caller readiness inputs or bypass.",
        "invalidation_behavior": "Reauthenticate original lease/upstream and scenario/provider/policy/current state under lock; sign INVALIDATED and replace exactly once without consumer readiness; no reissue, consume, refund or reset.",
        "rejection_matrix": {"authorization_copy_deepcopy_replace_manual_JSON_report_ID_fingerprint_wrapper_subclass_old_schema_relabel": "PINNED_AUTH_UNAUTHENTICATED or distinct authenticated scope error",
            "nonoriginal_supplied_authorization": "LEASE_UNAUTHENTICATED",
            "lease_copy_deepcopy_replace_manual_JSON_report_ID_fingerprint_wrapper_subclass_old_type_or_relabel": "LEASE_UNAUTHENTICATED",
            "wrong_PID": "LEASE_WRONG_PROCESS before lock",
            "scenario_or_policy_mismatch": "PINNED_AUTH_SCOPE_MISMATCH",
            "provider_projection_mismatch": "PINNED_PROVIDER_PROVENANCE_MISMATCH",
            "unknown_validator_failure": "PROOF_UNRESOLVED",
            "Boolean_JSON_readiness_override": "TypeError or exact-original typed rejection; never a transition"},
        "error_taxonomy": contract["error_taxonomy"],
        "atomicity": {"independent_lock": True, "read_snapshot_under_same_lock": True,
            "issuance": "construct and sign before one copy-on-write _STORE publication of permanent key plus signed ISSUED record",
            "transition": "authenticate/check/sign before one copy-on-write _STORE publication of target record",
            "failure_publishes_nothing_or_preserves_prior_record": True,
            "race_tests": {"concurrent_duplicate_issuance": "exactly one inert logical commit",
                "consume_vs_invalidate": "one INVALIDATED commit; consume is PROOF_UNRESOLVED or LEASE_INVALIDATED",
                "invalidate_vs_invalidate": "exactly one INVALIDATED commit"},
            "positive_consumption_test_or_fake_consumer_gate": False,
            "CONSUMED_inspection_fixture": "isolated signed historical record only; no successful consume"},
        "old_owner_isolation": "All historical bytes preserved; independent type, secret, lock and owner store; unchanged production validators/registries/policies; no compatibility bridge.",
        "reflection_acceptance_claimed": False, "operational_lease_issued": False,
        "operational_lease_consumed": False, "operational_attempt_performed": False,
        "operational_effects": contract["operational_effects"],
        "isolated_tests": "Source-loaded new owner and pinned upstream copies with an inert exact-original public validator seam. No provider graph, production registry seeding or production validator patching. No fixture capability is exported.",
        "registry_picker_comparison": registry, "validation": validation,
        "historical_preservation": preservation, "independent_review": review,
        "stop_boundary": "Implementation and pure validation complete. No live authorization/provider/lease attempt.",
    }
    save("SYNTH_AUTH_LIFECYCLE_PINNED_1A_REPORT.json", report)
    lines = ["# SYNTH.AUTH.LIFECYCLE.PINNED.1A", "", "2026-10-13 KST.", "",
        "**SYNTH_AUTH_LIFECYCLE_PINNED_1A_COMPLETE**", "", report["completion_meaning"], "",
        "## Identity and API", "", f"Owner: `{report['module']}`. Type: `{report['type']}`. Schema: `{report['schema']}`.", "",
        *["- `" + name + "`" for name in report["public_APIs"]], "",
        "Every operation authenticates the retained original through the unchanged public pinned validator under the independent owner lock. Provider decision B binds all 15 authenticated public provider fields. No caller provider, scenario override, readiness Boolean/JSON, or compatibility bridge is accepted.", "",
        "## State and readiness", "", "| Source state | Validation/state read | Local / behavioral readiness | Consume | Invalidate |", "| --- | --- | --- | --- | --- |",
        "| ISSUED | Original / ISSUED | true / false; PROOF_UNRESOLVED | PROOF_UNRESOLVED; unchanged | INVALIDATED |",
        "| CONSUMED | Original / CONSUMED, if upstream authenticates | false / false; LEASE_ALREADY_CONSUMED | LEASE_ALREADY_CONSUMED | LEASE_ALREADY_CONSUMED |",
        "| INVALIDATED | Original / INVALIDATED, if upstream authenticates | false / false; LEASE_INVALIDATED | LEASE_INVALIDATED | LEASE_INVALIDATED |", "",
        "Only ISSUED -> CONSUMED and ISSUED -> INVALIDATED are defined. Consumption machinery exists but the unresolved consumer/source/compile contract blocks its commit. Invalidation needs no behavioral readiness. Terminal tombstones survive collection for the owner process lifetime; no refund, reissue or reset exists. Readiness is an immutable report, never a capability, token or reservation.", "",
        "## One-shot authentication and atomicity", "",
        "The key is `(authorization.owner_identity, authorization.phase_id, authorization.schema_version, authorization.issuing_pid, authorization.authorization_id)` from the exact public-validator return. Fingerprint, proof context and provider fingerprint are never alternate keys.", "",
        f"Domain: `{domain}`. Roles: `activation-policy`, `lease-evidence`, `lease-fingerprint`, `lease-record-hmac`. Strict canonical JSON uses sorted keys, compact separators, no NaN, UTF-8 and NUL-separated domain/role/payload. Public digests use domain-framed SHA256; private current-state records use independent-secret HMAC-SHA256. No secret or record signature is exported.", "",
        f"Activation policy: `{contract['activation_policy']['identity']}`. Canonical digest: `{policy_digest}`.", "",
        "Issuance constructs/signs before one `_STORE` replacement publishes the permanent key and signed ISSUED record together. A terminal transition reauthenticates and signs before one replacement. Reads use the same lock; wrong PID rejects before the lock. Failure injection preserves the original store. Race tests verify one duplicate-issuance commit, one consume/invalidate terminal commit (invalidation only), and one commit for competing invalidations. Public leases remain immutable and their issuance fingerprints remain stable.", "",
        "## Authority matrix", "", "| Authority | ISSUED | CONSUMED | INVALIDATED |", "| --- | --- | --- | --- |",
        *[f"| {name} | false | false | false |" for name in contract["authority"]["false_in_all_states"]], "",
        "`lease_issued=true` is an immutable issuance fact. `runtime_activation_consumed` is derived only from authenticated current state == CONSUMED. Provider infrastructure compilation grants no scenario compilation authority. Reflection acceptance is not claimed.", "",
        "## Rejection matrix", "", "| Input/failure | Result |", "| --- | --- |",
        "| Auth copy/deepcopy/replace/manual/JSON/report/ID/fingerprint/wrapper/subclass/old epoch | PINNED_AUTH_UNAUTHENTICATED; supplied nonoriginal auth to lease API is LEASE_UNAUTHENTICATED |",
        "| Lease copy/deepcopy/replace/manual/JSON/report/ID/fingerprint/wrapper/subclass/old type/schema relabel | LEASE_UNAUTHENTICATED |",
        "| Wrong process/PID | LEASE_WRONG_PROCESS before lock |",
        "| Scenario/policy mismatch or primitive equality alias | PINNED_AUTH_SCOPE_MISMATCH |",
        "| Provider projection mismatch | PINNED_PROVIDER_PROVENANCE_MISMATCH |",
        "| Unknown public-validator failure | PROOF_UNRESOLVED; no publication/transition |",
        "| Caller Boolean/JSON readiness/override | Rejected by exact input/signature; no transition |", "",
        "Known upstream codes and reasons are retained. Terminal errors retain parent category LEASE_NOT_ISSUED. ACTIVATION_PRECONDITION_UNSATISFIED remains the category for a future defined authenticated false consumer prerequisite; the absent consumer contract currently yields PROOF_UNRESOLVED.", "",
        "## Pure validation and preservation", "",
        f"- Focused implementation: {implementation['passed_count']} passed, zero failed/skipped.",
        f"- Frozen safe baseline: {baseline['passed_count']} passed. After: {focused['passed_count']} passed; one historical test asserting module absence is excluded after implementation, with its bytes unchanged.",
        f"- Registry/picker: {registry['after_passed_count']} passed and the same {len(registry['after_failed'])} existing baseline failures; all compared results, summary and picker output unchanged.",
        "- Benchmark --check, in-memory Python compilation, strict JSON, whitespace and git diff --check passed.",
        f"- All {preservation['baseline_file_count']} baseline historical files are byte-identical. Old lifecycle/auth/pinned auth/provider/reflection owners, registries, consumption policy, historical attempts and frozen artifacts are unchanged. No phase registration occurred.", "",
        "Tests use isolated source-loaded owner/upstream copies and an inert public-validator seam. Production validators are unchanged and production registries are not seeded. The CONSUMED inspection fixture is only a signed isolated historical record; no positive consume or fake consumer-readiness object is tested. All effect-guard counters are zero. Full issuance-dependent suites were not run and are not claimed.", "",
        "Operational lease issued: **false**. Operational lease consumed: **false**. Reflection acceptance claimed: **false**. Docker, SANDBOX2, JAVA1C, pinned provider/auth issuance, operational lease issuance/consumption/invalidation, SyntheticStateBox, reflection, BANK, EXECUTOR.1R, Apply and repository runtime writes: **all zero**.", "",
        "## Source hashes", "", f"Scenario source: `{report['scenario_source_sha256']}`. Definition: `{report['scenario_definition_sha256']}`.", "",
        "| Source | SHA256 |", "| --- | --- |",
        *[f"| {name} | `{digest}` |" for name, digest in hashes.items()], "",
        "Evidence: [machine report](SYNTH_AUTH_LIFECYCLE_PINNED_1A_REPORT.json), [validation summary](validation_summary.json), [implementation tests](implementation.json), [preservation](preservation_check.json), [registry comparison](registry_comparison.json), [source review](implementation_review.json).", "",
        "STOP: implementation and pure validation only; no live authorization/provider/lease attempt.", ""]
    (HERE / "SYNTH_AUTH_LIFECYCLE_PINNED_1A_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"typed_status": report["typed_status"], "focused_implementation_passed": implementation["passed_count"],
        "all_operational_effects_zero": True, "historical_preservation": True}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
