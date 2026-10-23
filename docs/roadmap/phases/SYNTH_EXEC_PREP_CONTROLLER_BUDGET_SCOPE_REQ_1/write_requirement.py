"""Author additive requirement evidence from frozen JSON, never execute owners."""
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PREFIX = "docs/roadmap/phases/"
CONTROLLER = PREFIX + "SYNTH_EXEC_PREP_CONTROLLER_CONTRACT_1/contract.json"
SCHEMA = PREFIX + "SYNTH_EXEC_PREP_CONTROLLER_CONTRACT_1/message_schema.json"
PREP = PREFIX + "SYNTH_EXEC_PREP_PINNED_CONTRACT_CLOSE_1/contract.json"
WORKSPACE = PREFIX + "SYNTH_EXEC_PREP_WORKSPACE_CONTRACT_1/contract.json"
TRANSPORT = PREFIX + "SYNTH_EXEC_PREP_CONTROLLER_TRANSPORT_1/selection.json"
PROOF = PREFIX + "SYNTH_EXEC_PREP_CONTROLLER_BUDGET_PROOF_1/SYNTH_EXEC_PREP_CONTROLLER_BUDGET_PROOF_1_REPORT.json"
ID = "SYNTH.EXEC.PREP.CONTROLLER.BUDGET.SCOPE.REQ.1"
COMPLETE = "SYNTH_EXEC_PREP_CONTROLLER_BUDGET_SCOPE_REQ_1_COMPLETE"


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def pointer(value, path):
    for part in path.lstrip("/").split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        value = value[int(part)] if type(value) is list else value[part]
    return value


def source(path, key, reason):
    raw = (ROOT / path).read_bytes()
    return {"path": path, "pointer": key, "value": pointer(read(path), key),
            "sha256": sha256(raw).hexdigest(), "size_bytes": len(raw), "reason": reason}


def row(event, owner, mandatory, inside, bound, reason):
    return dict(event_message=event, semantic_lifecycle_owner=owner,
                mandatory=mandatory, inside_8192_preparation_cap=inside,
                other_applicable_bound=bound, reason=reason)


def build():
    controller, schema, prep, transport, proof = map(read, (CONTROLLER, SCHEMA, PREP, TRANSPORT, PROOF))
    observation = controller["bounds"]["observation"]
    cleanup = controller["bounds"]["cleanup"]
    observe_bound = "observation profile: 5000ms, outer 10000ms, request/response frame <=8192; full inventory bounds; reviewed retained policy required"
    cleanup_bound = "cleanup profile: outer 10000ms, response <=8192, request frame <=8192, automatic retries 0; guaranteed separate cleanup capacity"
    effect_bound = "one shared 5000ms deadline, hard 10000ms; each frame <=8192; outer stdout and stderr each cumulatively <=8192"
    rows = [
        row("OBSERVE_EMPTY_WORKSPACE request / response", "workspace initial eligibility", "YES before materialization admission", "NO", observe_bound,
            "Establishes the independently authorized empty workspace required before an effect facet can be admitted. Its bytes are outside this effect capture; no unlimited observation or retained lifetime is authorized."),
        row("MATERIALIZE_EXACT_SCENARIO_SOURCE request / response", "preparation effect attempt", "YES", "YES", effect_bound,
            "Originating fixed effect exchange of the original spent materialization facet. Request belongs to the interval but stdin is not stdout/stderr."),
        row("materialize response.result.workspace_state", "preparation materialization evidence", "YES complete embedded record", "YES_IN_PARENT_ONCE", "parent frame and effect bounds",
            "Full poststate remains part of the response. It is neither another frame nor current readiness."),
        row("OBSERVE_CURRENT_WORKSPACE request / response between materialization admission and compile response completion", "workspace observation within active preparation effect attempt", "IF required by the existing admission checks or explicitly invoked", "YES", observe_bound + "; also original remaining effect bounds",
            "An observation inside the still-open effect interval consumes that same cumulative capture; an observation profile never resets or exempts an in-attempt frame."),
        row("COMPILE_EXACT_SCENARIO request / response", "preparation effect attempt", "YES on successful preparation path", "YES", effect_bound + "; compiler child pipes each <=2048",
            "Distinct compilation facet in the same fixed attempt. Complete terminal response is the successful counter endpoint, including all metadata and poststate."),
        row("compile response.result.workspace_state", "preparation compilation evidence", "YES complete post-reap embedded record", "YES_IN_PARENT_ONCE", "parent frame and effect bounds",
            "Full duplicated source/class/mount/process/writer evidence stays unchanged and is counted once in this response."),
        row("fresh prepared-current-state OBSERVE_* request / response after compile response", "workspace current-liveness/readiness evidence", "YES before readiness or handoff", "NO", observe_bound,
            "Re-establishes current workspace eligibility after completed effects, rather than performing another preparation effect. No mutation poststate substitution. CURRENT may precede the initial receipt; PREPARED requires the original receipt."),
        row("additional OBSERVE_CURRENT_WORKSPACE or OBSERVE_PREPARED_ARTIFACTS request / response after effect endpoint", "workspace current-liveness/readiness evidence", "IF invoked; new challenge for each use", "NO", observe_bound,
            "Readiness revalidation cannot reopen or reset the spent effect attempt. PREPARED is legal only with its original receipt and all existing predicates."),
        row("preparation receipt authentication", "preparation owner authenticated effect evidence", "YES for a success receipt", "NO_CONTROLLER_WIRE_BYTES", "exact frozen owner authentication, original graph/generation and lifetime rules; no new wire envelope",
            "Host in-process receipt authentication follows exact preparation evidence. Its data already serialized in effect responses is not counted again; this does not make the receipt current readiness or consumer permission."),
        row("PREPARE_EXCLUSIVE_HANDOFF request / response", "workspace retained-session/handoff lifecycle", "NO for preparation eligibility; only with separately reviewed consumer", "NO", observe_bound + "; conditional candidate session ceilings",
            "Optional exclusive reservation follows the effect interval. Activation remains PROOF_UNRESOLVED. A consumer execution/capture budget is unresolved future consumer scope, not supplied here."),
        row("BEGIN_CLEANUP request / response", "monotonic cleanup duty", "YES barrier duty; inner exchange if channel available", "NO", cleanup_bound,
            "cleanup_is_preparation=false even when cleanup preempts the attempt. Ordinary pending response bytes remain charged to the failed attempt, never relabeled as this control exchange."),
        row("CLEANUP_AND_REPORT request / response", "monotonic cleanup duty", "YES evidence duty; inner exchange if channel available", "NO", cleanup_bound,
            "Separate bounded teardown/reap/EOF evidence; no readiness requirement and no dependence on remaining normal effect budget. Lost inner evidence stays unresolved."),
        row("outer TERMINATE_REMOVE_EXACT_RETAINED_GENERATION", "independent outer cleanup custodian", "YES cleanup duty, including after inner loss", "NO", "fixed 10000ms invocation and <=8192-byte response; original immutable cleanup relation; no automatic retry",
            "Independent channel with fixed exact-generation authority; normal capture exhaustion cannot prevent teardown. No generic command or authority is created."),
        row("outer OBSERVE_EXACT_RETAINED_GENERATION_ABSENCE", "independent outer cleanup custodian", "YES independent absence evidence", "NO", "fixed 10000ms invocation and <=8192-byte response; exact same-backend full-ID absence; no automatic retry",
            "Fresh outer absence is separate from removal and cannot replace lost child wait or capture EOF evidence."),
        row("outer cleanup evidence composed with retained inner cleanup result", "workspace owner host in-process cleanup evidence", "YES for truthful composite cleanup completion", "NO_CONTROLLER_WIRE_BYTES", "bounded existing component schemas/inventories and invocation bounds; no extra inner response",
            "Keep provenance. Composition is not an inner process reporting its own removal and is not preparation success."),
    ]
    evidence = {
        "fixed_attempt": source(PREP, "/preparation_authority/semantics/preparation_authority_design", "The semantic effect unit is exactly materialize then compile."),
        "facets": source(PREP, "/preparation_authority/facets", "Two distinct effect facets in one attempt, not readiness authority."),
        "ordering": source(PREP, "/ordering/sequence", "Preparation evidence, full readiness and handoff are distinct lifecycle positions."),
        "cleanup_not_preparation": source(PREP, "/ordering/cleanup_is_preparation", "Cleanup cannot consume the successful effect allowance as a prerequisite."),
        "receipt": source(PREP, "/preparation_receipt", "Authenticated evidence, no current/consumer authority from receipt alone."),
        "owner_admission": source(CONTROLLER, "/authority_separation/admission", "Owning boundary spends/admit before dispatch; controller final checks do not restart attempt."),
        "old_scope": source(CONTROLLER, "/bounds/attempt_budget_scope", "Old ambiguous interval wording remains historically unchanged."),
        "operations": source(CONTROLLER, "/operations", "Mutation, observation and cleanup profiles and owners are distinct."),
        "observation_bounds": source(CONTROLLER, "/bounds/observation", "Independent bounded observation evidence, no first-N truncation."),
        "cleanup_bounds": source(CONTROLLER, "/bounds/cleanup", "Independent bounded cleanup, zero automatic retries."),
        "outer_bounds": source(CONTROLLER, "/cleanup/outer", "Outer custodian bound and independence survive inner loss."),
        "retention_gate": source(CONTROLLER, "/bounds/retention", "No unbounded retained workspace is preauthorized."),
        "fresh_challenge": source(SCHEMA, "/cross_field_rules/1", "Fresh observation mandatory, never mutation poststate."),
        "frame_and_capture": source(SCHEMA, "/cross_field_rules/10", "Frame and cumulative cap, full evidence and persistent cleanup duty."),
        "workspace_order": source(WORKSPACE, "/lifecycle/ordering", "Empty generation precedes attempt; consumer handoff is optional."),
        "workspace_receipt": source(WORKSPACE, "/preparation_interaction/receipt_readiness", "Fresh workspace integrity at handoff is distinct from receipt authenticity."),
        "candidate_budget": source(TRANSPORT, "/wire/stream_budgets", "Reviewed conditional session limits/reserves do not select a transport."),
        "candidate_lifetime": source(TRANSPORT, "/retained_lifetime", "Candidate-only finite retained lifetime/reserve; not a universal policy."),
        "old_proof": source(PROOF, "/typed_result", "Frozen old proof stays AGGREGATE_BUDGET_SCOPE_UNRESOLVED; no rerun."),
    }
    start = "Preparation owning boundary records the authenticated single-operation admission for this attempt's already-spent original materialization facet, before dispatching the MATERIALIZE_EXACT_SCENARIO_SOURCE request. That admission record is the single counter-origin event: open both counters at zero there, before any request or response byte of this exchange. Facet spending precedes the record; no cross-owner atomic transaction is claimed."
    end = "The final physical byte of the complete terminal COMPILE_EXACT_SCENARIO response frame is captured by the owning boundary, including all actual framing and its entire mandatory workspace_state, compiler_identity, capture_and_reap and class_metadata. A successful attempt requires the complete valid COMPLETE response; child exit, payload parsing before frame completion, receipt authentication, new readiness OBSERVE request/response, handoff admission and cleanup completion are not this endpoint."
    interpretation = "A: the one fixed materialize-then-compile preparation EFFECT attempt; successful outer capture begins at owning materialization admission and ends at complete compilation response. In-attempt observations remain inside; independent initial/current-readiness/handoff/cleanup lifecycle exchanges remain separately bounded."
    clarifications = []
    for path, key in [(CONTROLLER, "/bounds/attempt_budget_scope"), (SCHEMA, "/cross_field_rules/10"),
                      (TRANSPORT, "/wire/stream_budgets"), (PREP, "/compiler")]:
        clarifications.append({"new_requirement_id": ID, "historical_artifact": path, "historical_key": key,
            "old_ambiguous_wording": pointer(read(path), key), "new_exact_interpretation": interpretation,
            "scope": "Only byte-accounting membership of the existing cumulative preparation capture; transport candidate wording remains conditional.",
            "reason": "Historical wording was underspecified for this newly measured budget question. The fixed effect attempt, independent workspace readiness and mandatory non-preparation cleanup supply the semantic basis; numeric fit is not the selection criterion.",
            "historical_bytes_preserved": True})
    return {
        "phase_id": ID, "new_requirement_id": ID, "artifact_kind": "PURE_ADDITIVE_REQUIREMENT_CLARIFICATION",
        "typed_result": COMPLETE, "completion_marker": COMPLETE, "requirement_frozen": True,
        "historical_bytes_preserved": True, "historical_contract_globally_wrong": False,
        "prior_text_uniquely_defined_endpoint": False,
        "semantic_selection": {"choice": "A", "effect_attempt_semantics": True,
            "wider_readiness_lifecycle_semantics": False, "selection_based_on_budget_fit": False,
            "reason": "PREP admits exactly two non-interchangeable effect facets in one fixed attempt. Initial workspace eligibility precedes admission; fresh current readiness and optional handoff revalidate retained workspace after effects; cleanup is explicitly not preparation. This additive requirement supplies the previously missing exact byte events without changing those effect meanings.",
            "not_claimed": "The historical proof did not already entail these exact byte events. This is the authorized new normative scope interpretation, not a reinterpretation of the old proof outcome."},
        "counter_interval": {"start_event_id": "OWNER_MATERIALIZATION_ADMISSION_BEFORE_DISPATCH",
            "start": start, "successful_end_event_id": "COMPLETE_COMPILE_RESPONSE_FINAL_BYTE", "successful_end": end,
            "origin_derived_from_deadline_alone": False,
            "origin_basis": "The materialization facet admission opens the one-shot effect attempt; independently, the existing shared deadline also begins there. Initial empty observation/request/response precede this effect boundary. Inner final local admission and first response byte are not new origins.",
            "earlier_events_outside": ["before empty observation", "OBSERVE_EMPTY_WORKSPACE request", "OBSERVE_EMPTY_WORKSPACE response"],
            "failure_end_event_id": "ORDINARY_RESPONSE_DRAIN_TERMINATION",
            "failure_end_cases": {
                "no_response_pending": "Recorded irrevocable terminal attempt-abort event when no admitted ordinary operation response remains pending.",
                "response_pending": "First of: final byte of the last terminal ordinary response already admitted to this attempt; observed terminal channel closure/loss; original 10000ms hard preparation deadline. Count every observed partial/invalid ordinary byte until that event.",
                "early_failure": "A materialization failure/rejection or a later admission/compilation failure cannot wait for a nonexistent successful compile response. Apply the no-pending or pending-response case to the failed admitted operation; no second attempt or new counter is allowed.",
                "cleanup_preemption": "The cleanup barrier suppresses success immediately but does not close a pending ordinary response ledger. Its complete response suffix still belongs to the failed effect attempt, even if physically delivered after the barrier. Cleanup exchanges have their own ledger.",
                "overflow": "Overflow fails the attempt, never resets or forgives observed bytes; retain an exceeded/incomplete result and bounded partial/drain evidence. It never authorizes unbounded buffering, a late successful receipt or denial of mandatory independent cleanup.",
                "loss_or_deadline": "No terminal response is fabricated. Any still-unobserved ordinary suffix is unresolved, not an outside-budget exemption; the failed epoch cannot reopen or publish success. Mandatory cleanup remains independently bounded."
            },
            "no_deadline_extension": "The shared 5000ms attempt deadline is never renewed. Cancellation/reaping/capture closure and terminal drain remain clamped to original 10000ms hard bound; a failed result never appends a new preparation interval.",
            "no_resets": ["compile admission", "observation", "receipt authentication", "cleanup barrier", "lost response", "generation or retained lifetime"],
            "membership_rule": "All ordinary effect request/response frames and any current observation invoked after origin but before the effect endpoint are members. Include actual framing in its own physical stream. Separately identifiable cleanup control/results retain cleanup membership even during preemption; pending ordinary bytes cannot be relabeled.",
            "no_evidence_deferral": "Every mandatory materialization/compile record must be complete in its own response before the endpoint. No chunking, delayed suffix, post-end receipt, observation or handoff may carry deferred effect response evidence to evade the unchanged cap."
        },
        "caps": {"outer_stdout_max_bytes": 8192, "outer_stderr_max_bytes": 8192,
            "individual_frame_max_bytes": 8192, "shared_attempt_deadline_ms": 5000, "hard_preparation_bound_ms": 10000,
            "compiler_child_stdout_max_bytes": 2048, "compiler_child_stderr_max_bytes": 2048,
            "controller_stdin_cumulative_8192_cap_frozen": False},
        "fresh_readiness_observation": {"classification": "OUTSIDE_PREPARATION_CAPTURE_WITH_SEPARATE_BOUND",
            "mandatory_before_readiness_or_handoff": True, "mutation_poststate_substitutes": False,
            "lifecycle_class": "workspace current-liveness/readiness evidence", "bounds_ref": "independent_bounds.observation",
            "reason": "Current eligibility is a fresh challenged observation of retained prepared workspace after completed effects; it is not a third preparation effect facet. Earlier in-attempt observations still count.",
            "required_tag": "new complete challenged OBSERVE_* of prepared current state",
            "CURRENT_before_initial_receipt_allowed": True, "PREPARED_before_original_receipt_allowed": False,
            "PREPARED_with_original_receipt_allowed": True,
            "no_new_receipt_ordering_rule": "Preserve all existing owner evidence/authentication checks. The byte endpoint does not require a receipt to precede CURRENT or force PREPARED to create the receipt it already requires."},
        "initial_empty_observation": {"classification": "OUTSIDE_PREPARATION_CAPTURE_WITH_SEPARATE_BOUND",
            "mandatory": True, "lifecycle_class": "workspace initial eligibility before effect admission",
            "bounds_ref": "independent_bounds.observation", "request_and_response_both_classified": True},
        "independent_bounds": {"observation": observation, "cleanup": cleanup,
            "all_frames_max_bytes": 8192, "outer_custodian": controller["cleanup"]["outer"]["bounds"],
            "retained_lifetime_gate": controller["bounds"]["retention"],
            "no_unbounded_exemption": "Every outside observation/handoff uses existing per-operation time/frame/record/byte bounds and a separately reviewed finite retained lifetime policy before readiness. No universal numeric session/lifetime ceiling is invented or authorized here. Missing reviewed retained bounds denies readiness, not an unlimited channel.",
            "outside_diagnostics": "Observation request/response ceilings do not independently bound arbitrary controller stderr or unsolicited output. Outside lifecycle traffic has no free diagnostic channel: unexpected/nonprotocol output fails closed; any future transport must prove finite capture bounds for all outer channels under its separately reviewed retained policy before operational eligibility. No new universal stderr number is invented. Candidate A retains empty successful controller stderr and its conditional session ceilings only.",
            "conditional_candidate_A_only": {"accepted": False, "session_bytes_each_direction": 65536,
                "session_request_count_including_cleanup": 64, "reserved_cleanup_request_slots": 2,
                "retained_total_ms": 30000, "work_cutoff_ms": 20000, "cleanup_reserve_ms": 10000,
                "framing_header_bytes": 4, "whole_frame_max_bytes": 8192,
                "reason": "These are preserved reviewed candidate profile limits, not final transport or architecture selection; they never enlarge the 8192 effect cap."}},
        "cleanup": {"cleanup_is_preparation": False, "membership": "OUTSIDE_PREPARATION_CAPTURE_WITH_SEPARATE_BOUND",
            "preemption_allowed": True, "duty_mandatory": True, "requires_remaining_effect_budget": False,
            "safety_capacity": "Before ordinary admission the future transport must guarantee bounded independent/reserved cleanup capacity, including both cleanup exchanges and outer fallback. Normal effect capture may consume all 8192 bytes without spending cleanup capacity. If the channel cannot preserve this, deny ordinary admission; this requirement selects no transport.",
            "shared_channel": "Separately identified cleanup frames are charged to cleanup and to any applicable retained-session ceiling once per ledger, not the ordinary effect ledger. Finishing an already-started ordinary response cannot convert its bytes to cleanup. Channel/normal-quota failure still invokes independent exact-generation outer teardown.",
            "reserves": "For conditional candidate A, preserve two cleanup slots plus bounded cleanup/error response capacity within the 65536/session/64-request ceiling and the 10000ms cleanup time reserve. Ordinary admission cannot spend them. Existing independent cleanup and outer invocation bounds remain; reserves do not enlarge preparation capture.",
            "lost_inner_evidence": "Removal and absence do not prove missing child reaping/EOF. Preserve unresolved components; no fabricated cleanup success."},
        "stream_accounting": {
            "controller_stdin_requests": "Report request payload/framing in its own direction. Semantic attempt membership does not turn stdin into captured outer stdout or stderr; no bidirectional sum or new cumulative stdin cap.",
            "controller_stdout_responses": "Count each member response byte, including full embedded poststate and actual transport framing, once if mapped to outer stdout by a future transport. All partial/malformed/unframed/unexpected captured bytes during the effect epoch also count and deny success; missing labels do not exempt them. No omission, compression, alias or removal of duplicated evidence.",
            "controller_stderr": "All bytes observed during the effect capture epoch count toward its separate 8192 stderr cap unless independently attributable to a separately bounded lifecycle channel. No untagged/shared stderr may be favorably relabeled as cleanup or observation. Empty successful candidate stderr is conditional precedent, not a new encoding shortcut.",
            "compiler_child_stdout": "Separate <=2048 child capture; exact successful observed bytes=0. Metadata is already counted in compile response; do not add it twice.",
            "compiler_child_stderr": "Separate <=2048 child capture; exact successful observed bytes=0. Metadata is already counted in compile response; do not add it twice.",
            "outer_custodian_channel": "Separate fixed bounded cleanup invocation, no invented four-byte prefix and no charge to normal effect allowance.",
            "host_in_process_composed_evidence": "Receipt authentication and provenance-preserving cleanup composition are not extra controller wire responses. A future serialization would require its actual bounded channel accounting, not a free exemption.",
            "payload_vs_physical": "Freeze lifecycle membership here. Canonical semantic payload and actual physical framing are distinct; bytes on a capped physical stream include its real headers. No transport mapping is selected. Candidate A alone would put request+4 on stdin and response+4 on stdout.",
            "attempt_vs_session": "Preparation attempt budget != retained controller session budget != workspace lifetime. One physical byte may be checked against nested applicable ceilings but is never added twice within one ledger. A larger session ceiling neither expands the effect allowance nor makes it a lifetime allowance.",
            "unattributed_or_late_bytes": "A future channel must prove attribution and preserve bounded capture/closure; it cannot publish success by moving ordinary response suffixes past the endpoint. Unknown/lost/invalid bytes remain failure evidence, never an unlimited uncharged channel."},
        "handoff": {"required_for_preparation_eligibility": False, "frame_budget_class": "retained-session/handoff budget",
            "inside_preparation_capture": False, "existing_operation_bounds_profile": "observation",
            "activation_status": "PROOF_UNRESOLVED", "future_consumer_capture_scope": "UNRESOLVED_FUTURE_CONSUMER_SCOPE",
            "consumer_authority_invented": False},
        "normative_table": rows, "clarifications": clarifications, "evidence": evidence,
        "budget_arithmetic_consequence": {"historical_proof_outcome_unchanged": proof["typed_result"],
            "old_proof_rerun": False, "next_phase": "SYNTH.EXEC.PREP.CONTROLLER.BUDGET.PROOF.1R",
            "next_phase_requirement": "TRUTHFUL_ATTAINABLE_WITNESS_REQUIRED",
            "reason": "Fresh readiness observation is outside this effect capture. The already-known 6702-byte relaxed materialize+compile payload is only a lower relaxation; it does not prove an attainable semantic identity encoding or complete framed exchange can fit.",
            "known_relaxations_read_only": {"materialize_compile_payload": 6702, "with_fresh_CURRENT_payload": 9423},
            "inside_branch_not_selected": "Had fresh observation been inside, 1R would seek impossibility confirmation using the already-known universal relaxed excess. That branch is not selected or proved here.",
            "feasibility_decision": "NOT_MADE_IN_SCOPE_PHASE", "budget_blocker_removed": False},
        "non_changes": {"cap_changed": False, "schema_changed": False, "operation_changed": False,
            "transport_selected": False, "candidate_A_selected": False, "historical_proof_modified": False,
            "pins_changed": False, "owners_implemented": False, "capabilities_issued": False,
            "evidence_compressed_or_deduplicated": False, "id_widths_changed": False,
            "stash_reset_clean_used": False, "registry_modified": False},
        "authority_flags": dict(controller["authority_flags"], controller_authority=False, workspace_authority=False,
            preparation_authority=False, runtime_authority=False, reflection_authority=False),
        "operational_effects": dict(controller["operational_effects"], network=0, process=0, controller_execution=0),
        "effect_counter_scope": "Domain operational effects are zero. Local Python source/JSON analysis and explicitly required in-process tests/benchmark checks are validation, not preparation/controller execution; guards measure child process/network/owner-import/issuance/outside-phase writes separately.",
        "stop": True,
    }


def main():
    value = build()
    (HERE / "requirement.json").write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    table = ["| Event/message | Semantic lifecycle owner | Mandatory? | Inside 8192 preparation cap? | Other applicable bound | Reason |",
             "| --- | --- | --- | --- | --- | --- |"]
    for item in value["normative_table"]:
        table.append("| " + " | ".join(str(field).replace("|", "\\|") for field in item.values()) + " |")
    (HERE / "normative_table.md").write_text("# Normative lifecycle membership\n\n" + "\n".join(table) + "\n", encoding="utf-8")
    print(json.dumps({"phase_id": ID, "typed_result": COMPLETE, "table_rows": len(value["normative_table"]), "old_proof_rerun": False}))


if __name__ == "__main__":
    main()
