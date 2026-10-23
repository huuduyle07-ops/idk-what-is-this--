"""Assemble completion evidence from measured pure validation; import no owners."""
from __future__ import annotations

import ast
from hashlib import sha256
import json
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent
ROOT = OUTPUT.parents[3]


def main():
    safe = json.loads((OUTPUT / "safe_validation_summary.json").read_text(encoding="utf-8"))
    focused = json.loads((OUTPUT / "inert_admission_tests.json").read_text(encoding="utf-8"))
    if (not safe["safe_validation_passed"] or focused["exit_code"] != 0
            or focused["failed"] != 0 or focused["passed"] <= 0
            or focused["guarded_effect_attempts"]
            or not focused["production_store_and_registry_snapshots_unchanged"]):
        raise ValueError("measured safe and isolated validation must pass before completion")
    source = (ROOT / "core/synthetic_reflection_execution_admission_pinned.py").read_bytes()
    tree = ast.parse(source.decode("utf-8"))
    admission = next(node for node in tree.body if isinstance(node, ast.ClassDef)
        and node.name == "PinnedSyntheticReflectionExecutionAdmission")
    fields = [node.target.id for node in admission.body if isinstance(node, ast.AnnAssign)]
    public = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)
        and not node.name.startswith("_")]
    zero_effects = dict.fromkeys(("Docker", "SANDBOX2", "JAVA1C", "provider_issuance",
        "pinned_authorization_issuance", "pinned_runtime_lease_issuance",
        "runtime_lease_consumption", "runtime_lease_invalidation",
        "reflection_request_operational_issuance", "pinned_reflection_admission_operational_issuance",
        "reflection_lease_issuance", "reflection_lease_consumption", "reflection_lease_invalidation",
        "reflection_read", "SyntheticStateBox", "BANK", "EXECUTOR.1R", "Apply", "repository_runtime_writes"), 0)
    contract = json.loads((ROOT / "docs/roadmap/phases/SYNTH_REFLECT_PINNED_CONTRACT_1/contract.json")
        .read_text(encoding="utf-8"))
    report = {
        "status": "SYNTH_REFLECT_ADMIT_PINNED_1A_COMPLETE", "date": "2026-10-13", "timezone": "Asia/Seoul",
        "phase_id": "SYNTH.REFLECT.ADMIT.PINNED.1",
        "module": "core.synthetic_reflection_execution_admission_pinned",
        "exact_type": "PinnedSyntheticReflectionExecutionAdmission",
        "schema_version": "synthetic_reflection_execution_admission_pinned_1_v1",
        "authentication_domain": "CATTUS:SYNTH.REFLECT.ADMIT.PINNED.1:exact-reflection-admission:v1",
        "owner_source_sha256": sha256(source).hexdigest(), "public_APIs": public,
        "authenticated_instance_reads": ["fingerprint", "as_dict"], "projection_fields": fields,
        "request_decision": "A", "request_exact_type": "core.synthetic_read_only_reflection.SyntheticReflectionRequest",
        "request_validator_unchanged": True, "request_roles_unchanged": True,
        "role_mapping": {"BEFORE": "exact_private_state_before", "AFTER": "exact_private_state_after"},
        "old_auth_compatibility_predicate_called": False, "old_registry_insertion": False,
        "pinned_compatibility": {"report_predicate_only": True, "issues_permission": False,
            "same_original_validator_returns_required": True, "runtime_validator_receives_exact_original_auth": True,
            "current_runtime_state_authenticated_publicly": True, "requires_specific_runtime_state": False},
        "one_shot_key": contract["admission_one_shot"],
        "slot_behavior": {"BEFORE_and_AFTER_independent": True, "maximum_each_per_runtime_graph": 1,
            "fresh_same_role_request_reopens": False, "collection_reopens": False},
        "issuance_state_gate": {"BEFORE": "ISSUED", "AFTER": "ISSUED",
            "CONSUMED_or_INVALIDATED": "PINNED_RUNTIME_STATE_MISMATCH", "unresolved": "PROOF_UNRESOLVED"},
        "originals_retained_separately": ["authorization", "runtime", "request"],
        "all_originals_reauthenticated_on_public_reads": True,
        "stable_fingerprint_after_terminal_runtime": True, "validity_implies_readiness": False,
        "renderer_binding": {"identity": contract["renderer_binding"]["renderer_identity"],
            "fixed_helper_UTF8_SHA256": {"BEFORE": "c88aeea914c88ef17a335a184abe6d5b618a9c0c70a7121621ba67edd9919531",
                "AFTER": "4d85951e886bfedabae50c7f64e8e0fa4985e8fa515e4edab9af0a355b10f4ea"},
            "hash_source": "unchanged renderer literal bytes authenticated by source/AST preservation",
            "renderer_invoked": False, "independent_domain_role": "renderer-evidence",
            "text_is_effect_evidence": False, "text_grants_compilation_authority": False},
        "provider_inheritance": {"transitive_original_runtime_auth_provider_graph": True,
            "direct_provider_input": False, "direct_provider_validation": False},
        "authority": contract["authority"], "behavioral_activation_ready": False,
        "behavioral_readiness_reason": "PROOF_UNRESOLVED", "compilation_authority": False,
        "error_categories": ["PINNED_AUTH_UNAUTHENTICATED", "PINNED_RUNTIME_LEASE_UNAUTHENTICATED",
            "PINNED_AUTH_SCOPE_MISMATCH", "PINNED_PROVIDER_PROVENANCE_MISMATCH", "PINNED_RUNTIME_STATE_MISMATCH",
            "REFLECTION_REQUEST_UNAUTHENTICATED", "REFLECTION_SCOPE_MISMATCH", "DUPLICATE_REFLECTION_ADMISSION",
            "REFLECTION_ADMISSION_UNAUTHENTICATED", "REFLECTION_ROLE_MISMATCH", "REFLECTION_WRONG_PROCESS", "PROOF_UNRESOLVED"],
        "upstream_code_reason_preserved": True, "unknown_validator_failure": "PROOF_UNRESOLVED",
        "atomicity": {"independent_owner_lock": True, "wrong_PID_before_lock": True,
            "publication_by_one_complete_store_replacement": True, "failed_signing_publishes_nothing": True,
            "final_runtime_state_change_publishes_nothing": focused["final_runtime_state_race_publishes_nothing"],
            "concurrent_same_role_successes": focused["concurrent_same_role_publications"],
            "concurrent_same_role_duplicates": focused["concurrent_duplicate_rejections"],
            "permanent_slots_survive_collection": focused["collected_admission_does_not_reopen_permanent_role_slot"],
            "cross_owner_transaction": False, "upstream_private_lock_access": False,
            "final_ISSUED_check_is_eligibility_snapshot": True},
        "old_admission_request_sources_changed": False, "pinned_auth_runtime_owner_changed": False,
        "provider_executor_history_changed": False, "registry_reversal_history_changed": False,
        "lifecycle_owner_implemented": False, "admission_consumption_API_implemented": False,
        "operational_admission_issued": False, "production_registries_seeded": False,
        "production_validators_modified": False, "operational_effects": zero_effects,
        "test_local_inert_handles_are_operational_evidence": False,
        "validation": {"focused_isolated_admission": focused,
            "safe_historical_summary": "safe_validation_summary.json",
            "frozen_contract_source_AST": safe["frozen_contract_source_AST_tests"],
            "historical_source_AST_selection": safe["frozen_source_AST_regression_selection"],
            "additional_historical_source_checks": safe["historical_source_AST_checks"],
            "benchmark_cases": safe["benchmark_cases_checked"], "benchmark_errors": safe["benchmark_errors"],
            "registry_picker": safe["registry_picker"], "preservation": safe["preservation"],
            "in_memory_compile_AST_JSON_whitespace": safe["static"]["passed"],
            "git_diff_check_exit_code": safe["git_diff_check"]["exit_code"],
            "full_issuance_dependent_suites_run": False, "independent_contract_review": "no remaining actionable findings"},
        "completion_meaning": "The additive pinned reflection admission owner is implemented and pure-validated. No operational admission, reflection lease or reflection effect exists.",
        "stop_after_admission": True,
    }
    (OUTPUT / "SYNTH_REFLECT_ADMIT_PINNED_1A_REPORT.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(report["status"])


if __name__ == "__main__":
    main()
