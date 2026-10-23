"""Author additive preparation semantics from frozen JSON; import no owners."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

PHASE = Path(__file__).resolve().parent
ROOT = PHASE.parents[3]
PREP = "docs/roadmap/phases/SYNTH_EXEC_PREP_PINNED_CONTRACT_1/contract.json"
REQ = "docs/roadmap/phases/SYNTH_EXEC_ACTIVATION_BOUNDARY_REQ_1/requirement.json"


def read(relative):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def write(name, value):
    (PHASE / name).write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def main():
    if not (PHASE / "preservation_baseline.json").is_file():
        raise AssertionError("Immutable preservation baseline must precede contract authoring")
    previous, requirement = read(PREP), read(REQ)
    assert previous["completion_marker"] == "PREPARATION_REQUIRES_REQUIREMENT_EVOLUTION"
    assert requirement["decision_frozen"] is True
    assert read("docs/roadmap/phases/SYNTH_EXEC_ACTIVATION_BOUNDARY_REQ_1/"
        "SYNTH_EXEC_ACTIVATION_BOUNDARY_REQ_1_REPORT.json")["typed_result"] == (
            "SYNTH_EXEC_ACTIVATION_BOUNDARY_REQ_1_COMPLETE")
    rows = [
        (1, "in_memory_source_projection", "PURE_DERIVATION", "ACCEPTED_UNCHANGED",
         "Exact existing authenticated bytes are projected in memory without synthesis, rewriting or a filesystem effect."),
        (2, "sandbox_materialization", "PREPARATION_EFFECT", "ACCEPTED_UNCHANGED",
         "The exclusive ephemeral source write and full readback change preparation state only; all original path/workspace controls remain binding."),
        (3, "javac_compilation", "PREPARATION_EFFECT", "ACCEPTED_WITH_ADDITIVE_CLARIFICATION",
         "Compiler JVM infrastructure startup is distinct from scenario JVM dispatch. Only the exact closed source/JDK/image/environment inputs are accepted; no target loading, initialization, construction or invocation, processor/plugin/dependency inputs or extra flags are permitted. Source evidence contradicting this premise stops closure."),
        (4, "JVM_startup", "BEHAVIORAL_ACTIVATION_EFFECT", "ACCEPTED_WITH_ADDITIVE_CLARIFICATION",
         "This denotes dispatch of the exact scenario-executing JVM under the completed activation-boundary requirement. It is no longer a proposed requirement revision and makes no universal classification of compiler or inert infrastructure JVM startup."),
        (5, "target_loading_initialization_construction", "AFTER_ACTIVATION_BOUNDARY", "ACCEPTED_UNCHANGED",
         "Target loading/linking and initialization remain behavioral activation effects; ordinary construction is a behavioral effect. All occur after scenario JVM dispatch; inert class metadata inspection never loads the class."),
        (6, "no_preparation_after_runtime_consumption", "ORDERING_INVARIANT", "ACCEPTED_UNCHANGED",
         "All preparation and full harness/consumer readiness evidence precede runtime consumption. Only mandatory authenticated permission checks/commits intervene before dispatch; no materialization, compilation, artifact repair or readiness acquisition after consumption."),
    ]
    retained = ("scenario", "effect_classification", "materialization", "compiler", "sandbox",
        "compile_output", "preparation_receipt", "cleanup", "authority_flags", "operational_effects")
    contract = {key: deepcopy(previous[key]) for key in retained}
    contract.update({
        "phase_id": "SYNTH.EXEC.PREP.PINNED.CONTRACT.CLOSE.1",
        "schema_version": "synthetic_execution_preparation_pinned_contract_close_1_v1",
        "artifact_kind": "additive_frozen_preparation_semantics_contract_only",
        "completion_marker": "SYNTH_EXEC_PREP_PINNED_CONTRACT_CLOSE_1_COMPLETE",
        "decision_frozen": True,
        "preparation_contract_complete": True,
        "harness_contract_complete": False,
        "preparation_contract_complete_implies_harness_contract_complete": False,
        "implementation_authorized": False,
        "owners_implemented": False,
        "capabilities_issued": False,
        "behavioral_activation_ready": False,
        "runtime_consumption_ready": False,
        "reason": "PROOF_UNRESOLVED",
        "stop_after_contract_closure": True,
        "closure_scope": {
            "previous_proposal": PREP,
            "previous_outcome": previous["completion_marker"],
            "revised_requirement": REQ,
            "requirement_outcome": "SYNTH_EXEC_ACTIVATION_BOUNDARY_REQ_1_COMPLETE",
            "preparation_semantics_now_frozen": True,
            "frozen_semantics_are_operational_authority": False,
            "historical_artifacts_rewritten": False,
            "additional_historical_claims_superseded": False,
            "consumer_owner_or_runtime_integration_frozen": False,
            "meaning": "The prior preparation proposals have been reviewed against the revised activation boundary and are now frozen preparation semantics. No owner, authority or operational effect exists.",
        },
        "proposal_review": [dict(item=number, proposal=proposal, classification=classification,
            decision=decision, rationale=rationale) for number, proposal, classification, decision, rationale in rows],
        "activation_boundary": deepcopy(requirement["activation_boundary"]),
        "first_behavioral_effect": {
            "operation": "dispatch exact scenario-executing JVM",
            "classification": "BEHAVIORAL_ACTIVATION_EFFECT",
            "requirement_evolution_required": False,
            "resolved_by": "SYNTH.EXEC.ACTIVATION.BOUNDARY.REQ.1",
            "first_known_source_level_mutable_state_effect": "ordinary construction initializing value = 10",
            "first_exact_executable_harness_instruction": None,
            "source_evidence_contradicts_compilation_classification": False,
            "source_evidence_method": "Read and AST-evaluate the existing _SOURCE literal only; no owner import, executable Java check or source materialization.",
            "contradiction_policy": "STOP; do not compile or run to resolve a contract contradiction; classify REQUIRES_NEW_REQUIREMENT or UNRESOLVED and withhold successful closure.",
        },
        "ordering": {
            "preparation_runtime_state": "ISSUED",
            "both_reflection_admissions_and_leases_prepared_with_runtime": "ISSUED",
            "preparation_requires_runtime_CONSUMED": False,
            "preparation_after_runtime_consumption_allowed": False,
            "sequence": [
                {"id": "capability_gates", "operation": "authenticate original pinned auth/runtime/provider graph and all capability gates"},
                {"id": "prepare_reflection", "operation": "prepare distinct BEFORE and AFTER admissions and leases while runtime ISSUED"},
                {"id": "source_authentication", "operation": "authenticate exact frozen source, future narrow preparation authority and already-authorized live exclusive workspace generation"},
                {"id": "source_projection", "operation": "obtain exact existing source bytes in memory"},
                {"id": "materialization", "operation": "exclusively materialize exact source and authenticate full readback"},
                {"id": "compilation", "operation": "one exact bounded scenario compilation; authenticate source unchanged and bounded inert class output"},
                {"id": "preparation_evidence", "operation": "authenticate original preparation receipt and live workspace/artifact generation"},
                {"id": "future_full_readiness", "operation": "authenticate separately reviewed full harness and consumer readiness; presently unresolved"},
                {"id": "handoff", "operation": "complete all integrity, original graph, freshness and exclusive handoff checks while runtime ISSUED"},
                {"id": "runtime_consume", "operation": "consume runtime lease ISSUED -> CONSUMED"},
                {"id": "before_permission_consume", "operation": "authenticate and consume BEFORE reflection lease"},
                {"id": "scenario_dispatch", "operation": "dispatch exact scenario JVM"},
                {"id": "target_activation", "operation": "load/link/initialize target as required by future reviewed harness"},
                {"id": "ordinary_construction", "operation": "ordinary exact SyntheticStateBox construction"},
                {"id": "before_read", "operation": "BEFORE exact reflection read"},
                {"id": "decrement", "operation": "exact public decrement(3)"},
                {"id": "after_permission_consume", "operation": "authenticate and consume AFTER reflection lease"},
                {"id": "after_read", "operation": "AFTER exact reflection read"},
                {"id": "cleanup", "operation": "finish consumer; tear down entire workspace and independently verify absence"},
            ],
            "between_runtime_consumption_and_dispatch": requirement["activation_boundary"]["between_runtime_consumption_and_dispatch"],
            "launch_before_runtime_and_BEFORE_commits_allowed": False,
            "refund_after_runtime_consumption_allowed": False,
            "launch_failure_or_postcommit_check_failure": "Abort; no launch after failed checks, no refund, reopening, reissue or retry under spent activation.",
            "AFTER_handoff": "AFTER read still requires its separately authenticated consumed permission. Exact staged harness/controller protocol remains unresolved and is not defined here.",
            "future_order_is_current_execution_permission": False,
            "cleanup_is_preparation": False,
            "cleanup_clarification": "Mandatory teardown, child reaping and independent absence verification after completion or abort remain cleanup duties; they do not permit another preparation attempt after runtime consumption.",
        },
        "preparation_authority": {
            "decision": "ACCEPTED_WITH_ADDITIVE_CLARIFICATION",
            "future_owner": "core.synthetic_execution_preparation_pinned",
            "type": "PinnedSyntheticPreparationAuthority",
            "schema": "synthetic_preparation_authority_pinned_1_v1",
            "one_authority_two_noninterchangeable_facets": True,
            "facets": ["exact_sandbox_materialization_authority", "exact_scenario_compilation_authority"],
            "semantics": deepcopy(previous["authority_separation"]),
            "each_facet": {"max_attempts": 1, "reservation": "immediately before its exact effect",
                "failure_spends_attempt": True, "refund_allowed": False, "reissue_allowed": False,
                "exact_original_bindings": ["pinned authorization", "runtime lease", "workspace/container generation", "controller", "provider graph"],
                "runtime_state_required": "ISSUED"},
            "compilation_requires_verified_materialization": True,
            "materialization_facet_can_compile": False,
            "compilation_facet_can_materialize": False,
            "generic_file_or_command_API_allowed": False,
            "sandbox_or_provider_issuance_granted": False,
            "future_implementation_or_lock_integration_preapproved": False,
            "phase_issues_authority": False,
            "clarification": "Freeze only future narrow preparation semantics. Existing auth/runtime/reflection or JAVA.1C evidence is never preparation permission, and this artifact issues no capability.",
        },
        "preparation_evidence_authentication": {
            key: deepcopy(value) for key, value in previous["evidence_authentication"].items()
            if key != "consumer_domain"
        },
        "harness_boundary": {
            "decision": "UNRESOLVED",
            "preparation_closure_requires_harness_completion": False,
            "full_harness": deepcopy(requirement["full_harness"]),
            "historical_renderer_identity": deepcopy(previous["harness_identity"]),
            "helpers_establish_full_harness": False,
            "invented_harness_fields": [],
            "scope": "No harness source, hash, main, JVM argv, loader/controller source or staged permission protocol is fabricated, frozen or implemented. Existing helper metadata is historical evidence only.",
        },
        "consumer_readiness": {
            "review_scope": "DEPENDENCY_SHAPE_ONLY",
            "dependency_decision": "ACCEPTED_WITH_ADDITIVE_CLARIFICATION",
            "final_owner_decision": "UNRESOLVED",
            "preparation_receipt_may_be_one_future_input": True,
            "preparation_receipt_alone_unlocks_runtime_consumption": False,
            "separate_full_harness_and_consumer_review_required": True,
            "final_owner_frozen": False,
            "final_schema_frozen": False,
            "final_public_API_frozen": False,
            "runtime_lock_integration_frozen": False,
            "implemented": False,
            "runtime_consumption": "PROOF_UNRESOLVED",
            "reason": "Full harness and authenticated consumer evidence remain separately unreviewed/unimplemented. Existing unconditional runtime readiness denial is unchanged.",
        },
        "historical_preservation": deepcopy(requirement["historical_preservation"]),
        "completion_rule": {
            "success": "SYNTH_EXEC_PREP_PINNED_CONTRACT_CLOSE_1_COMPLETE",
            "further_evolution": "PREPARATION_CONTRACT_REQUIRES_FURTHER_EVOLUTION",
            "unresolved": "CONTRACT_UNRESOLVED",
            "all_six_proposals_must_be_accepted": True,
            "source_contradiction_stops_closure": True,
            "validation_and_preservation_required": True,
            "stop_after_closure": True,
            "next_action_authorized": None,
        },
    })
    receipt = contract["preparation_receipt"]
    receipt.update({
        "decision": "ACCEPTED_WITH_ADDITIVE_CLARIFICATION",
        "may_prove_only": ["exact source authentication", "materialization and full readback",
            "compiler identity", "exact argv/cwd/environment", "compile result",
            "bounded output manifest with actual class hash", "live workspace generation", "cleanup pending"],
        "context_bindings_are_additional_readiness_claims": False,
        "may_claim_full_harness_readiness": False,
        "may_claim_consumer_readiness": False,
        "may_claim_behavior_success": False,
        "alone_unlocks_runtime_consumption": False,
    })
    contract["authority_flags"].update(preparation_authority=False, consumer_readiness_authority=False)
    contract["effect_counter_scope"] = requirement["effect_counter_scope"]
    write("contract.json", contract)
    index = deepcopy(read("docs/roadmap/phases/SYNTH_EXEC_PREP_PINNED_CONTRACT_1/evidence_index.json"))
    index.update(phase_id=contract["phase_id"], method="raw byte hashes and source/AST/contract inspection only; no owner imports or Java execution")
    for relative in (PREP, REQ,
        "docs/roadmap/phases/SYNTH_EXEC_ACTIVATION_BOUNDARY_REQ_1/SYNTH_EXEC_ACTIVATION_BOUNDARY_REQ_1_REPORT.json",
        "docs/roadmap/phases/SYNTH_EXEC_ACTIVATION_BOUNDARY_REQ_1/compatibility_review.json"):
        data = (ROOT / relative).read_bytes()
        index["files"][relative] = {"bytes": len(data), "sha256": sha256(data).hexdigest(), "anchors": []}
    for relative, row in index["files"].items():
        data = (ROOT / relative).read_bytes()
        assert len(data) == row["bytes"] and sha256(data).hexdigest() == row["sha256"], relative
    write("evidence_index.json", index)
    print(json.dumps({"phase_id": contract["phase_id"], "proposal_decisions": [row["decision"] for row in contract["proposal_review"]], "operational_effects": 0}))


if __name__ == "__main__":
    main()
