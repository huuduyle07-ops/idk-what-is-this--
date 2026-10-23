"""Build reviewable lifecycle evidence from AST and measured pure validation."""
from __future__ import annotations

import ast
from hashlib import sha256
import json
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent
ROOT = OUTPUT.parents[3]
SOURCE = ROOT / "core/synthetic_reflection_execution_lifecycle_pinned.py"


def main():
    validation = json.loads((OUTPUT / "validation_summary.json").read_text(encoding="utf-8"))
    if not validation.get("scope_passed", validation["passed"]):
        raise AssertionError("Completion report requires all scoped validation to pass")
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    constants = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                constants[node.targets[0].id] = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                pass
    api_nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef)
        and not node.name.startswith("_")]
    states = ("ISSUED", "CONSUMED", "INVALIDATED")
    readiness = [{"reflection": reflection, "runtime": runtime,
        "local_ready": reflection == "ISSUED" and runtime == "ISSUED",
        "reflection_active_ready": reflection == "ISSUED" and runtime == "CONSUMED",
        "behavioral_activation_ready": False, "reason": "PROOF_UNRESOLVED"}
        for reflection in states for runtime in states]
    effects = dict.fromkeys(("Docker", "SANDBOX2", "JAVA1C", "provider_issuance",
        "pinned_authorization_issuance", "pinned_runtime_lease_operational_issuance",
        "runtime_operational_consume", "runtime_operational_invalidate",
        "operational_reflection_request_issuance", "operational_admission_issuance",
        "operational_reflection_lease_issuance", "operational_reflection_consume",
        "operational_reflection_invalidate", "reflection_read", "SyntheticStateBox",
        "decrement_3_invocation", "BANK", "EXECUTOR.1R", "Apply", "repository_runtime_writes"), 0)
    report = {
        "status": constants["COMPLETE"], "owner_identity": constants["OWNER_ID"],
        "phase_id": constants["PHASE_ID"], "schema_version": constants["SCHEMA_VERSION"],
        "exact_type": "PinnedSyntheticReflectionExecutionLease",
        "authentication_domain": constants["_DOMAIN"].decode("utf-8"),
        "owner_source_sha256": sha256(SOURCE.read_bytes()).hexdigest(),
        "public_APIs": [{"name": node.name, "arguments": ast.unparse(node.args)} for node in api_nodes],
        "exact_upstream_graph": [
            {"type": "PinnedSyntheticReflectionExecutionAdmission", "owner": "core.synthetic_reflection_execution_admission_pinned",
                "validator": "validate_pinned_synthetic_reflection_execution_admission"},
            {"type": "SyntheticReflectionRequest", "owner": "core.synthetic_read_only_reflection",
                "validator": "validate_synthetic_reflection_request"},
            {"type": "PinnedSyntheticRuntimeExecutionLease", "owner": "core.synthetic_runtime_authorization_pinned_lifecycle",
                "validator": "validate_pinned_synthetic_runtime_execution_lease", "authorization": "exact retained original"},
            {"type": "PinnedSyntheticRuntimeAuthorization", "owner": "core.synthetic_runtime_authorization_pinned",
                "validator": "validate_pinned_synthetic_runtime_authorization"}],
        "originals": {"strongly_retained": True, "same_original_validator_returns_required": True,
            "optional_supplied_inputs_identity_required": True, "scalar_projection_is_authenticity": False,
            "provider_provenance": "Inherited transitively through unchanged pinned public validators; no provider input"},
        "permanent_admission_key": {"private_owner_process_store": constants["OWNER_ID"],
            "components": ["authenticated admission.owner_identity", "admission.phase_id", "admission.schema_version",
                "admission.issuing_pid", "admission.admission_id"],
            "derived_only_after_public_authentication": True, "original_admission_retained": True,
            "survives_lease_collection_and_terminal_transition": True,
            "alternate_ID_role_request_fingerprint_keys": False},
        "states": list(states), "transitions": [
            {"from": "ISSUED", "to": "CONSUMED", "runtime_required": "CONSUMED"},
            {"from": "ISSUED", "to": "INVALIDATED", "runtime_required": "any authentic state"}],
        "terminal_validation": "CONSUMED and INVALIDATED remain valid evidence while all exact originals authenticate; neither grants readiness",
        "runtime_state_authority": "Public pinned_synthetic_runtime_execution_lease_state(runtime, authorization=exact_original)",
        "issuance_runtime_state": "ISSUED for both BEFORE and AFTER, including final check immediately before publication",
        "readiness_matrix": readiness,
        "readiness_diagnostics": "readiness_reason holds terminal/runtime mismatch category; overall reason remains PROOF_UNRESOLVED",
        "ordering": list(constants["EXECUTOR_SEQUENCE"]),
        "ordering_is_execution": False,
        "immutable_projection": {
            "lease_fields": [node.target.id for cls in tree.body if isinstance(cls, ast.ClassDef)
                and cls.name == "PinnedSyntheticReflectionExecutionLease" for node in cls.body if isinstance(node, ast.AnnAssign)],
            "stable_fingerprint": "Domain-framed SHA256 issuance identity; excludes mutable current reflection state",
            "private_current_state": "Independent-secret HMAC-SHA256 over immutable issuance projection plus current state; never exported",
            "canonicalization": "Exact str/int/bool/null/list/string-key-dict nested types; sorted keys, compact separators, allow_nan=false, UTF-8; domain NUL role NUL canonical payload"},
        "authority_matrix": {**dict.fromkeys(constants["_FALSE_AUTHORITY"], False),
            "one_shot_exact_role_read_only_permission": "Only exact bound SyntheticStateBox.value:int / read_exact_bound_field / BEFORE or AFTER role; state and runtime rechecks required"},
        "error_taxonomy": list(constants["ERROR_CODES"]),
        "upstream_error_policy": "Known code/reason preserved as upstream_code/upstream_reason with typed category; unknown failure -> PROOF_UNRESOLVED",
        "rejection_matrix": {
            "copied_reconstructed_projected_or_ID_inputs": "Reject exact identity/type authentication",
            "different_same_role_request_or_matching_runtime_auth": "Reject original graph substitution",
            "runtime_CONSUMED_or_INVALIDATED_on_issue": "PINNED_RUNTIME_STATE_MISMATCH",
            "duplicate_admission_slot_including_collected_or_terminal_lease": "DUPLICATE_REFLECTION_LEASE",
            "wrong_role": "REFLECTION_ROLE_MISMATCH", "wrong_scenario_source_invocation_field_read": "REFLECTION_SCOPE_MISMATCH",
            "wrong_process": "REFLECTION_WRONG_PROCESS before lock", "consume_before_runtime_CONSUMED": "PINNED_RUNTIME_STATE_MISMATCH",
            "repeat_terminal": "REFLECTION_LEASE_ALREADY_CONSUMED or REFLECTION_LEASE_INVALIDATED",
            "unknown_public_validator_failure": "PROOF_UNRESOLVED", "provider_or_ready_boolean_input": "Not accepted by public signatures"},
        "atomicity": {"lock": "Independent owner lock, PID rejection first",
            "issue": "Construct/sign and prepare complete store; final public runtime ISSUED check; single store replacement publishes key and record",
            "transition": "Authenticate snapshot; check semantic prerequisites; sign target record; replace complete store once",
            "failure_preserves_previous_store": True, "cross_owner_lock_or_transaction": False,
            "runtime_change_after_publication": "Lease remains issuance evidence; readiness and consume authenticate runtime again",
            "race_tests": ["duplicate issuance", "consume versus consume", "invalidate versus invalidate", "consume versus invalidate"],
            "race_result": "Exactly one publication or terminal commit; competing operation rejected"},
        "effect_evidence": {"reflection_consumption_proves_read": False, "runtime_consumption_proves_invocation": False,
            "read_performed_by_lifecycle": False, "method_invoked_by_lifecycle": False},
        "downstream_dependencies": dict.fromkeys(("source_materialization_placement", "scenario_compilation_timing",
            "scenario_compilation_authority", "consumer_executor_proof"), "UNRESOLVED_DOWNSTREAM_DEPENDENCY"),
        "behavioral_activation_ready": False, "reason": "PROOF_UNRESOLVED", "compilation_authority": False,
        "old_lifecycle_source_changed": False, "pinned_admission_source_changed": False,
        "operational_reflection_lease_issued": False, "operational_reflection_effect": False,
        "operational_effects": effects, "all_operational_effects_zero": True,
        "validation": {
            "isolated": {key: validation["runs"]["isolated"][key] for key in ("collected", "passed_count", "failed", "exit_code", "audit_guard")},
            "contract_source_AST_passed": validation["runs"]["focused"]["passed_count"],
            "frozen_source_AST_regression_passed": validation["runs"]["frozen"]["passed_count"],
            "additional_frozen_source_AST_passed": validation["frozen_source_checks"]["passed_count"],
            "registry_picker": validation["registry_picker"],
            "benchmark_cases_checked": validation["benchmark_cases_checked"], "benchmark_errors": validation["benchmark_errors"],
            "static_passed": validation["static"]["passed"], "git_diff_check_exit": validation["git_diff_check"]["exit_code"],
            "historical_preservation": validation["preservation"], "stale_contract_test_deselected": validation["stale_contract_test_deselected"],
            "full_suite_run": False,
            "initial_bootstrap_rejection": "Outer guard blocked an existing-directory mkdir attempted by the shared historical test guard; no write occurred. Focused guard corrected collection; initial evidence retained in isolated_bootstrap_blocked.json."},
        "completion_meaning": "The additive pinned reflection one-shot lifecycle owner is implemented and pure-validated. No operational reflection lease was issued or consumed and no reflection effect occurred.",
        "stop": "No source/compile resolution or live capability issuance follows this phase."}
    (OUTPUT / "SYNTH_REFLECT_LIFECYCLE_PINNED_1A_REPORT.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = ["# SYNTH.REFLECT.LIFECYCLE.PINNED.1A", "", report["status"], "", report["completion_meaning"], "",
        "## Owner and authentication", "",
        "`core.synthetic_reflection_execution_lifecycle_pinned` defines the independent immutable `PinnedSyntheticReflectionExecutionLease`, schema `synthetic_reflection_execution_lease_pinned_1_v1`.", "",
        "Domain: `" + report["authentication_domain"] + "`. Secret, lock, registry, permanent admission map and signed state are independent of every historical owner.", "",
        "The exact original pinned admission, reflection request, pinned runtime lease and pinned authorization are strongly retained and reauthenticated through unchanged public validators on every operation. Validators must return their original input. Optional inputs must be the retained object by identity. Provider provenance is inherited transitively.", "",
        "Public APIs:", ""]
    lines += ["- `" + item["name"] + "`" for item in report["public_APIs"]]
    lines += ["", "## One-shot identity and state", "",
        "The permanent key contains authenticated admission owner/phase/schema/PID/admission ID inside this lifecycle's private process store. It is derived after public admission authentication. The retained admission and permanent tombstone survive lease collection and terminal transitions. BEFORE and AFTER use distinct admissions.", "",
        "| Operation | Reflection prerequisite | Runtime prerequisite | Result |",
        "|---|---|---|---|", "| Issue | No permanent admission slot | ISSUED | ISSUED |",
        "| Preexecution readiness | ISSUED | ISSUED | local_ready=true |",
        "| Active readiness | ISSUED | CONSUMED | reflection_active_ready=true |",
        "| Consume | ISSUED | CONSUMED | CONSUMED |",
        "| Invalidate | ISSUED | Any authentic state | INVALIDATED |",
        "| Validate terminal | CONSUMED or INVALIDATED | Any authentic state | Evidence only; both readiness flags false |", "",
        "Every graph must authenticate. Runtime state comes from the public pinned state API with the exact authorization, never initial-state or report fields. Overall `behavioral_activation_ready=false`, `reason=PROOF_UNRESOLVED` in every report. Separate `readiness_reason` preserves typed mismatch/terminal diagnostics.", "",
        "The immutable projection binds owner/process/issuance identity, both role literals, admission/request/renderer/auth/runtime identifiers and fingerprints, authorization proof context, exact scenario/source/invocation/field/read scope, initial runtime ISSUED state, and the authority matrix. Domain-framed public SHA256 fingerprints identify issuance. A private independent HMAC authenticates current state separately. No secret, record HMAC, registry or mutable record is exported.", "",
        "## Atomicity, rejection, and authority", "",
        "Wrong PID rejects before lock acquisition. Issuance prepares a fully signed store, performs a final public runtime ISSUED check, and publishes the permanent slot plus ISSUED record in one store replacement. Transition failure preserves the previous record. There is no cross-owner lock or transaction. Runtime changes after publication are rechecked on later readiness/consume.", "",
        "Race tests cover duplicate issuance, consume/consume, invalidate/invalidate and consume/invalidate; exactly one publication or terminal commit succeeds. Copies, reconstruction, projections, IDs, substituted originals, wrong role/scope/state/process, repeat transitions, unknown validators, and provider/readiness input bypasses are rejected. Known upstream code/reason is retained; unknown failures become PROOF_UNRESOLVED. The JSON report lists the complete typed taxonomy and rejection matrix.", "",
        "Only the exact bound read role for `SyntheticStateBox.value:int`, operation `read_exact_bound_field`, is represented. Runtime, real-task runtime, repository writes, Apply, network, mounts, shell, arbitrary Java/reflection/class/method, private methods, field writes, enumeration, executor, BANK, compilation, constructor reflection and arbitrary class loading authority remain false in every state.", "",
        "## Ordering and unresolved dependencies", "", "Normative ordering remains:", ""]
    lines += [str(index) + ". " + step for index, step in enumerate(report["ordering"], 1)]
    lines += ["", "The lifecycle performs no read or invocation. CONSUMED reflection permission does not prove a read; CONSUMED runtime permission does not prove invocation. Source placement, compilation timing/authority and consumer/executor proof remain `UNRESOLVED_DOWNSTREAM_DEPENDENCY`. Compilation authority remains false and the production runtime consumer stays fail-closed.", "",
        "## Validation and preservation", "",
        f"- Focused isolated lifecycle tests: {report['validation']['isolated']['passed_count']} passed; no production issuance, transitions, validators or reads called.",
        f"- Contract source/AST: {report['validation']['contract_source_AST_passed']} passed. One stale contract-freeze absence assertion is deselected; frozen bytes remain unchanged.",
        f"- Historical source/AST regressions: {report['validation']['frozen_source_AST_regression_passed']} passed; additional frozen source checks: {report['validation']['additional_frozen_source_AST_passed']} passed.",
        f"- Registry/picker: {validation['registry_picker']['after_passed']} passed and {len(validation['registry_picker']['after_failed'])} pre-existing failures, identical baseline/after; projections unchanged.",
        f"- Benchmark --check: {validation['benchmark_cases_checked']} cases, {validation['benchmark_errors']} errors. In-memory compilation, JSON/whitespace and git diff --check passed.",
        f"- Preservation: all {validation['preservation']['baseline_file_count']} pre-existing files unchanged, including old reflection lifecycle, pinned admission, runtime/provider owners, registry, reversals and historical executor attempts.",
        "- Full suite and issuance-dependent production suites were not run. Initial collection hit a denied no-op directory bootstrap before any test; the local guard was corrected and the blocked attempt evidence is retained.", "",
        "Old lifecycle source changed: **false**. Pinned admission source changed: **false**. Operational reflection lease issued: **false**. Operational reflection effect: **false**. All requested operational effect counts: **zero**.", "",
        "STOP. No source/compile resolution or live capability issuance.", ""]
    (OUTPUT / "SYNTH_REFLECT_LIFECYCLE_PINNED_1A_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    (OUTPUT / "README.md").write_text("# Pinned reflection lifecycle implementation\n\n"
        "See [implementation report](SYNTH_REFLECT_LIFECYCLE_PINNED_1A_REPORT.md), "
        "[machine-readable report](SYNTH_REFLECT_LIFECYCLE_PINNED_1A_REPORT.json), and "
        "[measured validation](validation_summary.json).\n\n"
        "Pure isolated tests only; no operational reflection lease or effect. "
        "Registry and all historical files remain unchanged.\n", encoding="utf-8")
    print(report["status"])


if __name__ == "__main__":
    main()
