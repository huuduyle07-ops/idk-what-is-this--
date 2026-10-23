"""Author a pure workspace/controller requirement. Never import an operational owner."""
from copy import deepcopy
from hashlib import sha256
import ast
import json
from pathlib import Path

PHASE = Path(__file__).resolve().parent
ROOT = PHASE.parents[3]
PREFIX = "docs/roadmap/phases/"
CLOSE = PREFIX + "SYNTH_EXEC_PREP_PINNED_CONTRACT_CLOSE_1/contract.json"
RESULT = "WORKSPACE_REQUIRES_CONTROLLER_EVOLUTION"


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def write(name, value):
    (PHASE / name).write_text(json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False) + "\n", encoding="utf-8")


def main():
    if not (PHASE / "preservation_baseline.json").is_file():
        raise AssertionError("Capture the immutable historical baseline first")
    close = read(CLOSE)
    assert close["completion_marker"] == "SYNTH_EXEC_PREP_PINNED_CONTRACT_CLOSE_1_COMPLETE"
    assert close["decision_frozen"] and close["preparation_contract_complete"]
    contract = {
        "phase_id": "SYNTH.EXEC.PREP.WORKSPACE.CONTRACT.1",
        "schema_version": "synthetic_execution_preparation_workspace_contract_1_v1",
        "artifact_kind": "pure_additive_workspace_and_controller_binding_contract",
        "typed_result": RESULT,
        "completion_marker": RESULT,
        "workspace_semantics_frozen": True,
        "controller_requirement_frozen": True,
        "existing_controller_satisfies_requirement": False,
        "operational_controller_binding_resolved": False,
        "implementation_authorized": False,
        "owners_implemented": False,
        "workspace_exists_by_this_phase": False,
        "capabilities_issued": False,
        "behavioral_activation_ready": False,
        "runtime_consumption_ready": False,
        "reason": "PROOF_UNRESOLVED",
        "stop_after_contract": True,
        "result_meaning": "Existing controller semantics cannot support truthful retained live workspace handoff without an additive controller requirement. The boundary and that requirement are frozen; no workspace, container or preparation authority is created.",
        "foundation": {
            "preparation_contract": CLOSE,
            "preparation_contract_marker": close["completion_marker"],
            "historical_contracts_modified": False,
            "scenario": deepcopy(close["scenario"]),
            "image_identity": close["compiler"]["image"],
            "sandbox_profile": close["compiler"]["sandbox_profile"],
            "sandbox_policy_sha256": close["compiler"]["sandbox_policy_sha256"],
            "sandbox": deepcopy(close["sandbox"]),
            "dimensions_widened": [],
            "additional_unchanged_inspection_pins": {"privileged": False, "pid_mode": "private default ('', None)", "ipc_mode": "none", "cgroupns_mode": "private", "cap_add": [], "log_driver": "none", "working_directory": "/work", "controller_entrypoint": ["/usr/local/bin/python"]},
            "live_backend_version_is_historical_literal": False,
        },
        "authority_separation": {
            "independent_objects": ["workspace capability", "preparation authority", "preparation receipt", "runtime activation authority"],
            "workspace_answers": "Where may already-authorized exact preparation effects occur, and is that isolated workspace/controller still the same live generation?",
            "workspace_represents_only": "exact live isolated preparation location and control binding",
            "effect_requires_conjunction": ["exact original live eligible workspace and controller binding", "appropriate exact original unspent preparation-authority facet"],
            "possession_allows_work_write": False,
            "workspace_consumes_preparation_facets": False,
            "preparation_permission_owner": "core.synthetic_execution_preparation_pinned",
            "workspace_identity_owner": "core.synthetic_execution_preparation_workspace_pinned",
            "historical_provider_evidence_is_live_readiness": False,
        },
        "exact_live_object": {
            "future_owner": "core.synthetic_execution_preparation_workspace_pinned",
            "type": "PinnedSyntheticPreparationWorkspace",
            "schema": "synthetic_preparation_workspace_pinned_1_v1",
            "phase": "SYNTH.EXEC.PREP.WORKSPACE.PINNED.1",
            "kind": "original process-local live location/control capability",
            "exact_type_required": True,
            "original_registry_object_identity_required": True,
            "issuing_pid_required": True,
            "strong_original_graph_retention_required": True,
            "forbidden_substitutes": ["JSON", "container ID string", "fingerprint", "copied dataclass", "wrapper", "subclass", "historical SANDBOX.2 descriptor", "caller provider JSON"],
            "immutable_signed_bindings": [
                "owner/phase/schema/issuing PID/workspace capability ID",
                "exact original pinned authorization/runtime objects and retained provider graph identities",
                "actual Docker/backend route and exact Server.Version relation to the original provider",
                "immutable image identity/SANDBOX.2 profile/policy digest",
                "actual full container identity and new workspace generation identity",
                "original controller identity and controller incarnation/generation",
                "controller normalized/resolved executable identity, actual byte hash and image provenance",
                "exact controller source bytes identity/hash/size and reviewed fixed protocol identity",
                "exact environment/resources/tmpfs/configuration identity",
                "authenticated creation evidence and initially empty exclusive manifest digest",
                "cleanup responsibility and original attempt identity",
            ],
            "mutable_authenticated_bindings": [
                "current liveness generation and observation sequence/challenge",
                "current controller incarnation and current container/workspace generation",
                "current exclusive-control claim and active operation or handoff binding",
                "current complete no-follow workspace-state digest",
                "cleanup-started/cleanup-complete/invalid predicates and terminal tombstones",
            ],
            "scalar_projection_sufficient": False,
            "stable_fingerprint_scope": "immutable originally signed identity only; it excludes mutable liveness, manifest, exclusive-control, handoff and cleanup observations",
            "current_state_authentication_separate": True,
        },
        "authentication": {
            "domain": "CATTUS:SYNTH.EXEC.PREP.WORKSPACE.PINNED.1:exact-live-workspace:v1",
            "algorithm": "HMAC-SHA256",
            "independent_secret": True,
            "secret_reuse_forbidden": ["SANDBOX.2 private verifier", "provider owners", "preparation owner", "runtime owner", "reflection owners"],
            "registry": "Exact process-local registry retains the original workspace object, immutable signed payload, original graph/controller references, monotonic observations and permanent terminal tombstones; full type and identity checks precede accepting its projection.",
            "canonical_types": "Exact schema-defined str/int/bool/None/list/dict types only; bool is not int. String keys only; reject missing/extra fields, duplicate keys, unsupported types, nonfinite numbers and implicit coercion. No caller JSON restore path exists.",
            "canonical_encoding": "UTF-8 JSON with sort_keys=true, separators=(',', ':'), ensure_ascii=true, allow_nan=false; schema-defined list order, no normalization or default=str",
            "framing": "ASCII domain + NUL + ASCII fixed role + NUL + canonical payload bytes",
            "roles": ["workspace-identity", "workspace-current-state", "workspace-cleanup-evidence"],
            "identity_hmac_payload": "immutable signed bindings; signed payload retains the independently computed stable fingerprint",
            "stable_fingerprint": "SHA256(domain + NUL + 'workspace-identity' + NUL + canonical immutable identity payload excluding signature and fingerprint); public report digest is never authentication",
            "state_hmac_payload": "workspace ID/stable fingerprint/issuing PID + exact original graph/controller binding + generation + owner-monotonic sequence + fresh owner challenge + all current predicates/state digest + operation/handoff ID + cleanup barrier; signs no authority permission",
            "freshness": "Require current owner registry sequence and a current challenge response from the exact retained controller for the guarded operation. Cached HMACs, a timestamp, unchanged digest, container name or route/version equality alone cannot establish current readiness.",
            "validation": "Compare HMAC in constant time and match canonical originally retained bytes. Reauthenticate every retained upstream through its unchanged public validator. Then evaluate current eligibility independently of historical authenticity.",
            "terminal_evidence_may_authenticate": True,
            "terminal_evidence_grants_readiness": False,
            "cleanup_only_exception": "Fresh readiness/challenge and successful current upstream reauthentication are operation admission requirements, not prerequisites for mandatory teardown. After controller loss or upstream invalidity use retained authenticated immutable cleanup identity and the independently authorized fixed teardown/absence path; it never restores readiness.",
        },
        "provider_binding": {
            "original_graph_only": True,
            "public_validators_unchanged": True,
            "private_PINNED_1C_semantics_cloned": False,
            "public_validation_chain": [
                {"module": "core.synthetic_runtime_authorization_pinned", "function": "validate_pinned_synthetic_runtime_authorization", "call_shape": "authorization, provider_outcome=the exact retained original outcome"},
                {"module": "core.synthetic_runtime_authorization_pinned_lifecycle", "function": "validate_pinned_synthetic_runtime_execution_lease", "call_shape": "the exact original lease, the exact original authorization"},
                {"module": "core.synthetic_runtime_authorization_pinned_lifecycle", "function": "pinned_synthetic_runtime_execution_lease_state", "call_shape": "the same originals; independently require ISSUED for preparation"},
                {"module": "core.synthetic_runtime_authorization_pinned_lifecycle", "function": "check_pinned_synthetic_runtime_execution_lease_preconditions", "call_shape": "the same originals; require current_state=ISSUED and lease_local_preconditions_satisfied=true. behavioral_activation_ready stays false with PROOF_UNRESOLVED; report-only, never a reservation"},
                {"module": "core.runtime_java_pinned_provider", "function": "validate_pinned_java_exact_provider", "call_shape": "receipt, pinned_receipt, bind_attachment, bind_sd, bind_sr, inspection, runtime_descriptor, runtime_receipt, runtime_sd, runtime_sr, attachment (all exact retained originals)", "parameter_names": ["receipt", "pinned_receipt", "bind_attachment", "bind_sd", "bind_sr", "inspection", "runtime_descriptor", "runtime_receipt", "runtime_sd", "runtime_sr", "attachment"]},
                {"module": "core.runtime_java_pinned_provider", "function": "validate_runtime_attachment", "call_shape": "attachment, pinned_receipt, bind_attachment, bind_sd, bind_sr, inspection, runtime_descriptor, runtime_receipt, runtime_sd, runtime_sr (all exact originals)", "parameter_names": ["attachment", "pinned_receipt", "bind_attachment", "bind_sd", "bind_sr", "inspection", "runtime_descriptor", "runtime_receipt", "runtime_sd", "runtime_sr"]},
                {"module": "core.sandbox_backend_binding", "function": "validate_sandbox_backend_binding", "call_shape": "original binding attachment and original sandbox descriptor/receipt"},
            ],
            "chain_scope": "The authorization and provider public validators transitively authenticate their retained PINNED.1A/B/C, inspection, BIND and separate runtime/SANDBOX pairs. Do not demand cross-pair fingerprint equality or read any private verifier registry/secret.",
            "live_relation_required": ["current measured route and exact Server.Version match the original retained provider relation", "actual new scenario container has exact image/configuration and exclusive workspace generation", "actual retained controller instance/executable/source belongs to that container and generation", "independently authorized creation and live binding evidence comes from a future reviewed typed adapter, not a caller assertion"],
            "route_version_limit": "BIND route/version equality is no daemon instance identity, continuity proof or ABA resistance. Do not extend that claim. Missing truthful generation/continuity observation invalidates live readiness even if route/version strings match.",
            "same_image_proves_provider_authenticity": False,
            "same_backend_name_proves_generation_continuity": False,
            "historical_backend_version": "29.6.1 (audit evidence only; not a fresh measurement or acceptance default)",
            "new_controller_relation": "Original PINNED.1C authenticates its historical fixed controller source unchanged. The new retained controller requires independently reviewed additive source/protocol/binding evidence. Never pass the new controller off as the old source, alter the old public validator, or claim that historical provider evidence validates its new protocol.",
            "new_live_binding_available_now": False,
        },
        "workspace_state_digest": {
            "algorithm": "SHA256",
            "domain": "CATTUS:SYNTH.EXEC.PREP.WORKSPACE.PINNED.1:exact-live-workspace:v1",
            "role": "workspace-state-digest",
            "framing": "ASCII domain + NUL + ASCII fixed role + NUL + strict canonical payload bytes using authentication.canonical_types and authentication.canonical_encoding",
            "top_level_payload_fields": ["workspace_capability_id", "stable_fingerprint", "issuing_pid", "container_identity", "workspace_generation", "controller_identity", "controller_generation", "observation_sequence", "observation_challenge", "stage", "mounts", "work_manifest", "tmp_manifest", "process_exclusivity_observation"],
            "identity_fields": "Exact retained originals and current generation/sequence/challenge; all must match the enclosing workspace-current-state HMAC and current owner registry.",
            "stage": "preparation-empty, materialized or prepared is derived only from authenticated initial state or the original preparation owner's same-attempt evidence. Partial/failed operations confer no prepared readiness. No harness stage is authorized.",
            "mounts": "Exactly two ordered records /tmp then /work: path, observed mount identity and namespace/generation, filesystem kind=tmpfs, exact frozen options, subordinate_mount_count=0. Include authenticated root identity/metadata; missing or unproved mount relation fails closed.",
            "manifest_entry_fields": ["path", "kind", "mode", "uid", "gid", "link_count", "size_bytes", "sha256"],
            "manifest_scope": "Complete descriptor-relative no-follow recursive entries beneath each authenticated root, including directories; roots are in mounts. Paths are exact absolute POSIX paths, sorted by UTF-8 path bytes, unique, without dot/parent/alias/NUL/backslash components. Each regular file has exact integer byte size, complete content SHA256 and link_count=1. Directory size_bytes and sha256 are null; directories have observed integer metadata and are never followed through links or other mounts. Links/special files are rejected, not omitted or normalized into regular entries.",
            "work_manifest": "Empty at workspace readiness. Thereafter inherit only PREP's stage-appropriate exact /work/SyntheticStateBox.java, /work/classes directory, and /work/classes/SyntheticStateBox.class, with full source/readback and bounded class size/hash checks from the unchanged preparation owner. No predicted class hash or extra artifact is accepted.",
            "tmp_manifest": "Complete no-follow manifest under /tmp with the same entry schema plus its exact mount. Preparation-empty contains no inputs or artifacts; later allowed infrastructure-only entries, if any, require a separately reviewed closed fixed controller operation and never supply compiler inputs. Unknown entries or unproved /tmp closure abort; no generic metadata exception or harness addition is preauthorized.",
            "process_exclusivity_observation": "Authenticate exact controller/process namespace/generation, full bounded process/writer inventory and descendant/operation identities, exclusive owner or exact authorized borrower, absence of shared writers/target JVM/target activation, and no cleanup barrier. Unexpected processes/writers or an incomplete inventory abort readiness. Later consumer observation/activation requires its separate contract; this digest grants none.",
            "metadata_only": True,
            "artifact_bytes_exported": False,
            "digest_alone_authenticates": False,
            "authenticated_by": "workspace-current-state HMAC covers this digest, fixed algorithm/domain/role/scope identity, same observation/generation binding and current predicates; original full observations remain bound in the owner registry. A scalar digest or replayed manifest never establishes readiness.",
        },
        "initial_workspace": {
            "ready_predicate": "live AND exclusive AND preparation-empty AND not invalid AND not cleanup-started; exact current provider/policy/controller/container generation bindings authenticated",
            "work_root": "/work",
            "work_mount": "authenticated expected isolated SANDBOX.2 tmpfs root only",
            "expected_work_entries": [],
            "classes_directory": {"path": "/work/classes", "exists_at_workspace_ready": False, "creation_owner": "preparation materialization/compile attempt", "workspace_bootstrap_may_create": False, "permission": "Only the exact preparation materialization facet may permit exclusive creation of this exact directory as part of its frozen attempt; compilation consumes the resulting same-attempt directory, never repairs/recreates it."},
            "source_file_present": False,
            "class_files_present": False,
            "harness_files_present": False,
            "JAR_processor_plugin_config_inputs_present": False,
            "unexpected_regular_files_present": False,
            "symlinks_hardlinks_subordinate_mounts_special_files_shared_writers_present": False,
            "target_JVM_present": False,
            "target_class_loaded_or_initialized": False,
            "SyntheticStateBox_present": False,
            "tmp_input_closure": "Exact bounded /tmp mount exists, has no compiler input, artifact/config/dependency or unauthorized writer; any permitted controller infrastructure metadata must be independently closed and cannot become compiler input. No target process or artifacts exist in either tmpfs.",
            "observation": "Future controller must authenticate full descriptor-relative no-follow manifest, mount/namespace identity, regular-file link counts and exclusive writers/processes in the same current observation; caller booleans or an empty directory listing alone are insufficient.",
        },
        "historical_workspace_rule": {
            "must_be_new_generation": True,
            "reuse_forbidden_after_cleanup_in": ["SANDBOX.2", "JAVA.1C", "PINNED.1A", "PINNED.1B", "PINNED.1C", "provider verification"],
            "receipts_are": "historical evidence only, never retained live workspace authority",
            "container_ID_or_name_reuse_resurrects_generation": False,
            "creation_authorized_here": False,
            "requires_independent_creation_authorization": True,
        },
        "controller_boundary": {
            "historical_controller": {
                "owner": "core.sandboxed_java_positive_continuation",
                "source_owner": "core.sandboxed_java_positive_probe",
                "source_accessor": "source",
                "phase": "RUNTIME.JAVA.1C",
                "normalized_executable": "/usr/local/bin/python",
                "resolved_executable": "/usr/local/bin/python3.12",
                "executable_sha256": "0e6475dfda68a9b2d93501449fc47593ca169010e8f4881577b97463fd0c1263",
                "source_sha256": "4f81640e2f01bc1f7a1a833beb269a9d1df51088b69cf24c8369fb6683f11a58",
                "source_size_bytes": 13037,
                "identity_kind": "frozen historical provider proof metadata; no current liveness claim",
                "observed_source_semantics": ["one fixed JavaSandboxProbe.java fixture", "requires initially empty /work", "creates /work/classes, compiles fixed fixture and then executes its fixed Java main", "no caller source/flags/environment/stdin", "outer finally kills/removes container and independently observes absence before returning", "successful provider evidence requires verified cleanup"],
                "retains_live_empty_workspace": False,
                "offers_exclusive_live_artifact_handoff": False,
                "may_be_widened_here": False,
            },
            "additive_controller_required": True,
            "additive_controller_implemented": False,
            "future_controller_executable_requirement": "Must bind actual normalized/resolved executable and full bytes to the pinned immutable image and nonroot invocation. Existing interpreter pin above is a foundation, not authentication of new source or a new live instance.",
            "future_controller_source_sha256": None,
            "future_controller_source_size_bytes": None,
            "future_controller_protocol_identity": None,
            "missing_identity_is_accepted": False,
            "responsibilities_required": ["fresh workspace liveness/state/exclusive-control observation", "exclusive integrity-checked artifact handoff in the same live generation", "later bounded preparation child processes with separate exact facet permission", "complete bounded captures, child/process-group supervision and reaping", "unconditional teardown after final attempt/consumer completion, failure or abandonment; preparation success retains live artifacts with cleanup pending", "independent same-backend absence observation"],
            "future_adapter_operations": "Only typed fixed operations required by separately reviewed preparation/harness contracts. This contract freezes responsibilities, not an implemented controller API or a harness protocol.",
            "forbidden_API": ["generic shell", "caller command string", "arbitrary argv", "Docker CLI passthrough", "generic filesystem API", "arbitrary Java", "arbitrary source", "arbitrary class loading"],
            "historical_API_modified": False,
            "unresolved_gate": "Until additive exact controller source/protocol/executable/live-binding evidence is independently reviewed and authorized, every workspace readiness request fails PROOF_UNRESOLVED; this artifact is never a substitute.",
        },
        "lifecycle": {
            "representation": "predicates; no speculative public state enum/API is frozen",
            "predicates": {
                "live": "Exact retained controller/container/workspace incarnation exists now, with current authenticated generation observation and no terminal condition.",
                "exclusive": "One retained controller owns artifact mutation/operation admission; no unaccounted writer, child, concurrent preparation or parallel borrower.",
                "preparation-empty": "Exact initial state above, with /work/classes absent.",
                "prepared-artifacts-present": "Original preparation owner has authenticated materialization and compilation success in this same generation; only exact frozen source/directory/class manifest remains, no running compiler/target JVM, complete captures/reaping, cleanup pending.",
                "handoff-active": "One separately authenticated later consumer borrows the exact original workspace and immutable artifact digest, bound to an operation/handoff identity. It gains no authority from this predicate. No new preparation or alternate borrower while active.",
                "cleanup-started": "Monotonic workspace-local admission barrier set before teardown. Denies new operations/handoffs and revokes readiness immediately; active operations are cancelled/reaped by the fixed controller.",
                "cleanup-complete": "All exact cleanup evidence is verified; terminal, even if a same-named container later exists.",
                "invalid": "Readiness permanently withdrawn for this capability/generation due to lost/changed binding, unexpected state, abandonment or upstream invalidation. Cleanup remains mandatory and possible.",
            },
            "partial_preparation": "Materialization/compile progress and their spent facets belong to the preparation owner. Between source write and verified compile, neither preparation-empty nor prepared-artifacts-present is asserted; partial success never confers readiness.",
            "ordering": ["independently authorized new empty exclusive generation", "exact preparation attempt in that generation", "verified inert artifacts retained live with cleanup pending", "optional exclusive separately authorized consumer handoff", "terminal cleanup and independent absence evidence"],
            "terminal_invariants": ["cleaned workspace can never become live again", "lost controller invalidates readiness and cannot be rebound to resurrect this capability", "generation change invalidates all prior current evidence", "cleanup is terminal and can never recreate preparation authority", "terminal historical evidence remains auditable and never grants readiness"],
            "no_refund_or_generation_rebind": True,
            "handoff": "Requires exact original workspace, original preparation receipt/attempt and artifact digest, retained controller and same generation, plus separately reviewed consumer authority. Pending handoff is not harness completeness. Failure/disconnect rejects handoff and triggers cleanup; no export or copy to another generation.",
        },
        "preparation_interaction": {
            "future_owner": close["preparation_authority"]["future_owner"],
            "authority_type": close["preparation_authority"]["type"],
            "authority_schema": close["preparation_authority"]["schema"],
            "receipt_type": close["preparation_receipt"]["proposed_type"],
            "receipt_schema": close["preparation_receipt"]["schema"],
            "issuance_requires": ["exact original live workspace object", "exact original pinned authorization/runtime graph", "runtime currently ISSUED with authenticated lease-local preconditions satisfied; behavioral readiness stays false/PROOF_UNRESOLVED", "workspace currently live/exclusive/preparation-empty/eligible", "matching original provider/image/policy/controller and workspace generation", "no original attempt tombstone; independently authorized live creation evidence"],
            "facets": deepcopy(close["preparation_authority"]["facets"]),
            "materialization": "All owners reauthenticate their own exact originals immediately before effect. Preparation owner spends its materialization facet; bound fixed controller admits the exact source write and /work/classes exclusive creation only in the original eligible empty generation.",
            "compilation": "Require verified materialization and reauthenticate the SAME workspace generation, exact source/readback/current manifest and ISSUED runtime immediately before effect. Preparation owner spends its distinct compilation facet; fixed controller admits only the frozen bounded compiler operation. Do not require emptiness after authorized materialization or repair altered inputs.",
            "workspace_substitution_allowed": False,
            "source_or_class_export_to_host_allowed": False,
            "cross_generation_receipt_allowed": False,
            "workspace_owner_spends_facets": False,
            "preparation_permission_owner_changed": False,
            "frozen_preparation_details_redefined": False,
            "exact_preparation_contract_reference": CLOSE,
            "runtime_after_consumption": "No new preparation, artifact repair or readiness acquisition after runtime leaves ISSUED. Mandatory cleanup persists regardless of runtime state. Separately reviewed activation/BEFORE checks govern later execution; workspace possession never substitutes for them.",
            "receipt_readiness": "Preparation receipt is evidence, not workspace capability. Require original live workspace and fresh artifact integrity at handoff; after cleanup/invalidity the receipt remains historical only and never crosses generations.",
        },
        "atomicity_and_races": {
            "cross_owner_transaction_claimed": False,
            "private_lock_bridge_allowed": False,
            "before_each_guarded_effect": "Each relevant public owner reauthenticates its own exact originals and state immediately before attempted effect. Workspace controller must enforce its local generation/exclusive-operation/cleanup admission fence across final observation and its fixed operation. Recheck postconditions; never claim that independent owner observations form one atomic transaction.",
            "cross_owner_limit": "Sequential validation cannot prove runtime/provider continuity across an unobservable gap. If an immediate relevant precondition cannot be established at effect admission, abort before effect with PROOF_UNRESOLVED. Do not invent a shared lock or certify raced success. Future implementation must separately prove its coordination without changing existing owners here.",
            "rules": {
                "controller_loss": "Reject admission; mark invalid; cancel/reap outstanding children and invoke independent cleanup path. No controller reconnection resurrects old evidence.",
                "container_disappearance": "Invalidate generation; abort before effect. Disappearance alone does not prove captures/children cleanup; verify exact cleanup evidence independently.",
                "generation_replacement": "Reject even with identical names, image, paths or manifest. No original-to-replacement binding.",
                "unexpected_file_creation": "Reject unexpected entry/link/mount/writer or changed source/class manifest, invalidate and clean. Authorized same-attempt source/class outputs are checked against the appropriate progress manifest.",
                "cleanup_racing_preparation": "Set cleanup-started under workspace-local admission fence before teardown. Admit no new operation. If an operation already started, cancel/reap and publish no preparation readiness until exact cleanup is independently resolved.",
                "runtime_leaving_ISSUED": "Preparation public preconditions fail; deny pending effects and readiness. Already spent facets stay spent. No repair/recompile after runtime consumption.",
                "provider_backend_mismatch": "Preserve upstream typed mismatch if raised; otherwise reject truthful live bridge as WORKSPACE_PROVIDER_MISMATCH. Version equality is insufficient to repair unknown generation continuity.",
            },
            "eligibility_changed_before_effect": "abort before effect",
            "spent_facet_refunded": False,
            "late_loss_after_effect": "No refund, no success/ready receipt from unverified or raced state; invalidate and perform independent cleanup. Record bounded attempt metadata and separately typed cleanup outcome.",
        },
        "cleanup": {
            "attempt_lifecycle_accountability": "Preparation owner retains frozen responsibility for its attempt; later consumer borrows exclusive handoff. It never transfers or cancels the cleanup duty.",
            "location_liveness_cleanup_custodian": "Workspace owner retains original controller/container/generation and monotonic cleanup barrier, coordinates teardown and authenticates cleanup evidence. The bound fixed controller performs containment cleanup; independent control route verifies absence.",
            "historical_PREP_cleanup_ownership_rewritten": False,
            "independent_of_behavior_success": True,
            "required_after": ["preparation failure", "consumer failure", "timeout", "runtime activation failure", "abandonment", "invalidated upstream"],
            "cleanup_requires_ISSUED_runtime_or_unspent_facet": False,
            "cleanup_requires_live_controller_challenge_or_current_upstream_readiness": False,
            "lost_controller_path": "An independently authorized fixed teardown/absence path must remain available with exact backend/container generation identity even when the inner controller is lost. This phase implements or invokes none of it. If absence or process/capture cleanup cannot be proved, report WORKSPACE_CLEANUP_UNRESOLVED and block readiness.",
            "evidence_required": ["all preparation/consumer/controller child processes and process groups terminated and reaped", "all captures/pipes/selectors/supervisors closed or stopped, EOF observed, no retained raw export", "exact actual container removed", "exact /work and /tmp generation gone", "fresh independent same-backend full-container-identity absence observation, not merely removal exit status or controller self-report", "no source/class/harness/raw workspace export survives"],
            "signed_evidence_bindings": ["original workspace ID/stable fingerprint/issuing PID", "original container/workspace/controller generation and backend route/version", "original attempt and handoff identity", "cleanup barrier and terminal observation sequence", "bounded teardown/process/capture results and errors", "independent observer identity/method and absence evidence digest"],
            "successful_cleanup_is_preparation_success": False,
            "successful_cleanup_is_behavior_success": False,
            "cleanup_failure_status": "WORKSPACE_CLEANUP_UNRESOLVED",
            "cleanup_failure_blocks_current_readiness": True,
            "cleanup_retry": "Only bounded fixed teardown/verification duties on the same retained identity may be retried; no new creation, preparation, authority refund or handoff. Invalidity/readiness withdrawal is permanent even if later cleanup succeeds.",
            "retained_audit_only": "Bounded source-free/class-free/harness-free metadata, hashes, manifests, typed errors and cleanup observations; no source/class bytes, raw workspace snapshot or restorable capability.",
        },
        "errors": {
            "WORKSPACE_UNAUTHENTICATED": "Wrong exact type/original registry identity, signature/canonical payload or tampered immutable binding; never use for an authenticated semantic mismatch.",
            "WORKSPACE_WRONG_PROCESS": "Original issuing process differs, including fork/process transfer; no JSON revival.",
            "WORKSPACE_NOT_LIVE": "No current exact live controller/container observation or invalidated readiness.",
            "WORKSPACE_NOT_EMPTY": "Authenticated initial generation has preexisting entries or preparation artifacts, including /work/classes.",
            "WORKSPACE_NOT_EXCLUSIVE": "Unaccounted writer/operation/borrower, lost exclusive control or conflicting handoff.",
            "WORKSPACE_GENERATION_MISMATCH": "Authenticated actual container/workspace/liveness generation differs from retained original.",
            "WORKSPACE_CONTROLLER_MISMATCH": "Authenticated controller instance, executable, source or protocol relation differs.",
            "WORKSPACE_PROVIDER_MISMATCH": "Authenticated original provider graph or actual live backend route/version/provider relation differs.",
            "WORKSPACE_SANDBOX_POLICY_MISMATCH": "Authenticated image/profile/policy/environment/resource/mount/configuration differs from exact pins.",
            "WORKSPACE_UNEXPECTED_ARTIFACT": "Authenticated current no-follow manifest, file kind/link/mount/source/class contents or bounded input closure has unexpected artifacts.",
            "WORKSPACE_HANDOFF_MISMATCH": "Authenticated borrower/receipt/artifact manifest/attempt/handoff binding differs or is not separately authorized.",
            "WORKSPACE_ALREADY_CLEANED": "Permanent cleanup tombstone; no readiness revival.",
            "WORKSPACE_CLEANUP_UNRESOLVED": "Separate cleanup failure or incomplete independent process/capture/container/tmpfs absence proof; blocks readiness.",
            "PROOF_UNRESOLVED": "Required independent creation/controller/live bridge/coordination/harness proof is missing, not forged or authenticated as ready.",
        },
        "error_rules": {
            "known_upstream_typed_errors_preserved": True,
            "semantic_mismatch_relabelled_as_authentication_failure": False,
            "upstream_examples": ["PINNED_BACKEND_BINDING_MISMATCH", "PINNED_CONTROLLER_MISMATCH", "PINNED_RUNTIME_EVIDENCE_MISMATCH", "PINNED_CLEANUP_FAILURE"],
            "selection": "Validate authenticity/process first. Propagate known upstream status/reason unchanged; then report the specific authenticated workspace semantic condition. Terminal cleanup and unresolved cleanup remain distinct from cryptographic authentication. Never suppress cleanup errors behind preparation or behavior success.",
        },
        "harness_boundary": deepcopy(close["harness_boundary"]),
        "authority_flags": {**deepcopy(close["authority_flags"]), "workspace_issuance_authority": False, "container_creation_authority": False, "work_write_authority_from_workspace_possession": False},
        "operational_effects": {**deepcopy(close["operational_effects"]), "workspace_issuance": 0, "container_creation": 0, "container_removal": 0},
        "effect_counter_scope": "This pure contract task and guarded validation only. Documentation/test/evidence file writes and source-control whitespace checks are not scenario workspace effects. Required operational counts are zero; no owner is imported to obtain an observation.",
        "historical_preservation": {"entire_preexisting_noncache_inventory_unchanged": True, "existing_user_changes_preserved": True, "runtime_reflection_owners_unchanged": True, "registry_picker_configuration_unchanged": True, "historical_receipts_reissued_or_reused": False},
        "unresolved": ["additive retained controller exact source/hash/size/protocol and authorized live binding", "independent new live workspace creation authorization and operational owner implementation (outside this task)", "future effect coordination proof without private cross-owner lock integration", "separately reviewed full harness and consumer"],
    }
    write("contract.json", contract)
    sources = {
        CLOSE: ["preparation_authority", "materialization", "cleanup", "harness_boundary"],
        PREFIX + "SYNTH_EXEC_ACTIVATION_BOUNDARY_REQ_1/requirement.json": ["activation_boundary"],
        "core/candidate_runtime_sandbox.py": ["_WORKLOAD_ENVIRONMENT", "_safe_configuration", "_invoke"],
        "core/thread_compatible_runtime_sandbox.py": ["POLICY", "validate_descriptor", "safe_configuration"],
        "core/sandbox_backend_binding.py": ["validate_sandbox_backend_binding", "BINDING_SEMANTICS"],
        "core/runtime_java_pinned_provider.py": ["CONTROLLER_RESOLVED", "CONTROLLER_SHA256", "_bridge", "validate_runtime_attachment", "validate_pinned_java_exact_provider"],
        "core/runtime_java_pinned_requirement.py": ["controller", "daemon", "aba"],
        "core/runtime_java_pinned_backend_target_binding.py": ["validate_"],
        "core/runtime_java_pinned_target_inspection.py": ["validate_"],
        "core/sandboxed_java_positive_probe.py": ["def execute", "def source", "os.mkdir", "run('java'"],
        "core/sandboxed_java_positive_continuation.py": ["def _invoke", "cleanup_control", "def validate_descriptor"],
        "core/synthetic_runtime_authorization_pinned.py": ["_authenticate_provider", "def validate_pinned_synthetic_runtime_authorization"],
        "core/synthetic_runtime_authorization_pinned_lifecycle.py": ["def validate_pinned", "def pinned_synthetic", "def check_pinned", "PROOF_UNRESOLVED"],
        PREFIX + "RUNTIME_JAVA_PINNED_1C_RETRY/RUNTIME_JAVA_PINNED_1C_RETRY_LOCAL.json": ["controller_source_identity", "source_sha256", "source_size_bytes"],
    }
    evidence = []
    for path, needles in sources.items():
        raw = (ROOT / path).read_bytes()
        lines = raw.decode("utf-8").splitlines()
        anchors = [{"line": number, "text": line.strip()[:240]} for number, line in enumerate(lines, 1)
                   if any(needle in line for needle in needles)][:60]
        functions = []
        if path.endswith(".py"):
            tree = ast.parse(raw.decode("utf-8"), filename=path)
            functions = [{"name": node.name, "line": node.lineno, "end_line": node.end_lineno}
                         for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))
                         and (node.name.startswith("validate_") or any(n in node.name for n in ("_invoke", "source", "preconditions", "lease_state")))]
        evidence.append({"path": path, "sha256": sha256(raw).hexdigest(), "bytes": len(raw), "anchors": anchors, "AST_definitions": functions})
    write("evidence_index.json", {"method": "source/JSON/AST only; no operational imports or live remeasurement", "sources": evidence, "historical_metadata_is_current_liveness": False})
    print(json.dumps({"typed_result": RESULT, "source_evidence_files": len(evidence)}))


if __name__ == "__main__":
    main()
