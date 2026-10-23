"""Pure symbolic canonical-size proof. No controller, owner, parser or execution.

Unknown identities and digests are width variables, never invented wire values.
The annotated layouts are NOT response payloads or successful execution evidence.
Only an attainable assignment plus justified physical framing could prove fit.
"""
from __future__ import annotations

import ast
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PHASES = HERE.parent
CONTRACT_DIR = PHASES / "SYNTH_EXEC_PREP_CONTROLLER_CONTRACT_1"
SCHEMA = json.loads((CONTRACT_DIR / "message_schema.json").read_text(encoding="utf-8"))
CONTRACT = json.loads((CONTRACT_DIR / "contract.json").read_text(encoding="utf-8"))
DEFS = SCHEMA["definitions"]
CAP = 8192
OPS = ("MATERIALIZE_EXACT_SCENARIO_SOURCE", "COMPILE_EXACT_SCENARIO")
EMPTY_HASH = sha256(b"").hexdigest()
SOURCE_HASH = CONTRACT["materialization"]["source_identity"]["sha256"]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


@dataclass(frozen=True)
class Width:
    name: str
    family: str
    lower: int
    upper: int
    spec: str
    basis: str


def identity(name, family="future_owner"):
    return Width(name, family, 3, 1538, "id",
        "Unresolved semantic encoding. Schema allows 1..256 UTF-8 bytes; canonical quoted width 3..1538. No scalar value selected.")


def container_identity():
    return Width("container_identity", "container", 3, 1538, "id",
        "Full immutable identity required; candidate A fixes 64 hex only within its conditional profile.")


def number(name, family="kernel_numeric", spec="uint"):
    return Width(name, family, 1, 19, spec,
        "Frozen nonnegative/positive 63-bit integer superset; decimal width 1..19. Exact observation/meaning unresolved.")


def digest(name, challenge=False):
    return Width(name, "fixed_digest", 66, 66, "challenge" if challenge else "hash",
        "Actual value unavailable; every truthful SHA256/challenge is exactly 64 lowercase hex plus two quotes. No digest fabricated.")


def resolve(spec):
    return DEFS[spec] if isinstance(spec, str) else spec


def fixed(spec):
    definition = resolve(spec)
    kind = definition["type"]
    if kind == "record":
        return {key: fixed(child) for key, child in definition["fields"].items()}
    if kind in ("enum", "fixed_list"):
        assert len(definition["values"]) == 1 or kind == "fixed_list"
        return definition["values"][0] if kind == "enum" else definition["values"].copy()
    raise AssertionError("Not fixed: " + str(spec))


def namespaces():
    return {name: identity("namespace." + name, "kernel_namespace")
            for name in DEFS["namespaces"]["fields"]}


def manifest(prepared):
    result = []
    paths = ["/work/SyntheticStateBox.java", "/work/classes"]
    if prepared:
        paths.append("/work/classes/SyntheticStateBox.class")
    for path in paths:
        directory, source = path == "/work/classes", path.endswith(".java")
        result.append(dict(path=path, kind="directory" if directory else "file",
            mode=number("mode." + path, "mode"), uid=65534, gid=65534,
            link_count=number("links." + path, "link_count", "positive_int") if directory else 1,
            size_bytes=None if directory else 239 if source else Width(
                "class_size_digits", "class_size", 1, 5, "class_size", "Any valid class in frozen 1..32768 envelope; no one-byte class claimed."),
            sha256=None if directory else SOURCE_HASH if source else digest("class_sha256")))
    return result


def state(prepared, writers, nullable_relaxation):
    mounts = []
    for path, options in (("/tmp", "rw,nosuid,nodev,noexec,size=16m,mode=1777"),
                          ("/work", "rw,nosuid,nodev,size=32m,mode=1777")):
        mounts.append(dict(path=path, mount_identity=identity("mount." + path, "kernel_mount"),
            namespace_generation=identity("mount_namespace_generation", "kernel_namespace"),
            filesystem_kind="tmpfs", options=options, subordinate_mount_count=0,
            root_identity=identity("root." + path, "kernel_root"),
            root_metadata=dict(mode=number("root_mode." + path, "mode"),
                uid=number("root_uid." + path, "root_uid_gid"),
                gid=number("root_gid." + path, "root_uid_gid"),
                link_count=number("root_links." + path, "link_count", "positive_int"))))
    process_identity = identity("controller_process_identity", "kernel_process")
    process = dict(pid=number("controller_pid", "pid", "positive_int"),
        parent_pid=number("controller_parent_pid", "pid"),
        start_identity=identity("controller_start", "kernel_start"), role="controller",
        namespaces=namespaces(), cgroup_identity=identity("cgroup", "kernel_cgroup"),
        uid=65534, gid=65534,
        tasks=[dict(tid=number("controller_tid", "pid", "positive_int"),
                    start_identity=identity("task_start", "kernel_start"))],
        admitted_operation_id=None)
    exclusive = dict(controller_process_identity=process_identity,
        controller_generation=identity("controller_generation", "generation"),
        namespace_identity=identity("process_namespace_identity", "kernel_namespace"),
        processes=[process], writers=[],
        exclusive_owner_relation_id=identity("exclusive_owner_relation_id"),
        authorized_borrower_relation_id=None, inventory_method="complete_readonly_kernel_inventory",
        cleanup_barrier_sequence=0, active_operation_id=None, handoff_identity=None)
    if writers:
        exclusive["writers"] = [dict(process_identity=process_identity,
            task_identity=identity("writer_task_identity", "kernel_process"),
            accounted_original_relation_id=identity("exclusive_owner_relation_id"),
            handles=[dict(descriptor_identity=identity("access." + path, "kernel_descriptor"),
                path=path, mount_identity=mount["mount_identity"],
                access_kind="potential_write_access", admitted_operation_id=None)
                for path, mount in zip(("/tmp", "/work"), mounts)])]
    if nullable_relaxation:
        for key in ("active_operation_id", "authorized_borrower_relation_id", "handoff_identity"):
            exclusive[key] = Width("nullable." + key, "nullable_relaxation", 3, 1538,
                "nullable_id", "Minimum of null and unresolved nonempty id; strict lower relaxation only.")
        process["admitted_operation_id"] = Width("nullable.admitted_operation_id",
            "nullable_relaxation", 3, 1538, "nullable_id", "Strict lower relaxation only.")
    return dict(workspace_capability_id=identity("workspace_capability_id"),
        stable_fingerprint=digest("stable_fingerprint"),
        issuing_pid=number("issuing_pid", "issuing_pid", "positive_int"),
        container_identity=container_identity(),
        workspace_generation=identity("workspace_generation", "generation"),
        controller_identity=identity("controller_identity"),
        controller_generation=identity("controller_generation", "generation"),
        observation_sequence=number("post_sequence.prepared" if prepared else "post_sequence.materialized", "sequence", "positive_int"),
        observation_challenge=digest("post_challenge.prepared" if prepared else "post_challenge.materialized", True),
        stage="prepared" if prepared else "materialized", mounts=mounts,
        work_manifest=manifest(prepared), tmp_manifest=[], process_exclusivity_observation=exclusive)


def pair(operation, writers=True, nullable_relaxation=False):
    prepared = operation == OPS[1]
    label = "compile" if prepared else "materialize"
    envelope = dict(protocol_id=fixed("protocol"), version=1, operation=operation,
        request_id=identity("request_id." + label), operation_id=identity("operation_id." + label),
        workspace_capability_id=identity("workspace_capability_id"),
        container_identity=container_identity(),
        workspace_generation=identity("workspace_generation", "generation"),
        controller_generation=identity("controller_generation", "generation"),
        sequence=number("sequence." + label, "sequence", "positive_int"),
        challenge=None, purpose=operation)
    attempt = identity("preparation_attempt_id")
    request = dict(envelope, admission_relation_id=identity("admission_relation_id." + label),
                   payload=dict(preparation_attempt_id=attempt))
    result = dict(workspace_state=state(prepared, writers, nullable_relaxation), preparation_attempt_id=attempt)
    if not prepared:
        result.update(source_readback_size=239, source_readback_sha256=SOURCE_HASH, source_readback_exact=True)
    else:
        compiler = fixed({"type": "record", "fields": {key: spec for key, spec in
            DEFS["compiler_identity"]["fields"].items() if key not in ("namespaces", "cgroup_identity")}})
        compiler.update(namespaces=namespaces(), cgroup_identity=identity("cgroup", "kernel_cgroup"))
        stream = dict(observed_bytes=0, limit_bytes=2048, sha256=EMPTY_HASH,
                      eof=True, overflow=False, closed=True)
        result.update(compiler_identity=compiler,
            capture_and_reap=dict(child_pid=number("compiler_child_pid", "pid", "positive_int"),
                process_group_identity=identity("compiler_group", "kernel_group"), exit_code=0,
                timed_out=False, reaped=True, group_terminated=True, stdout=stream.copy(),
                stderr=stream.copy(), selectors_closed=True, deadline_identity=identity("deadline_identity")),
            class_metadata=dict(path="/work/classes/SyntheticStateBox.class",
                size_bytes=result["workspace_state"]["work_manifest"][2]["size_bytes"],
                sha256=digest("class_sha256"), internal_class_name="SyntheticStateBox",
                inspection_kind="inert_bounded_classfile_metadata", class_loaded=False))
    return request, dict(envelope, status="COMPLETE", result=result, error=None)


def shape_check(value, spec, operation):
    """Check complete schema layout and fixed values without instantiating unknowns."""
    definition = resolve(spec)
    kind = definition["type"]
    if isinstance(value, Width):
        if kind == "nullable" and value.spec != "nullable_id":
            shape_check(value, definition["item"], operation)
            return
        if value.spec == "nullable_id":
            assert kind == "nullable" and definition["item"] == "id"
        elif value.spec == "class_size":
            assert definition["type"] == "int" and definition["maximum"] >= 32768
        else:
            assert definition == resolve(value.spec)
        return
    if kind == "record":
        assert type(value) is dict and set(value) == set(definition["fields"])
        for key, child in definition["fields"].items():
            shape_check(value[key], child, operation)
    elif kind == "nullable":
        if value is not None:
            shape_check(value, definition["item"], operation)
    elif kind == "operation_selected_record":
        shape_check(value, definition["by_operation"][operation], operation)
    elif kind == "list":
        assert type(value) is list and len(value) <= definition["max_items"]
        for item in value:
            shape_check(item, definition["items"], operation)
    elif kind in ("enum", "fixed_list"):
        assert value == definition["values"] if kind == "fixed_list" else value in definition["values"]
    elif kind == "int":
        assert type(value) is int and definition["minimum"] <= value <= definition["maximum"]
    elif kind == "bool":
        assert type(value) is bool
    elif kind == "str":
        assert type(value) is str
        assert len(value.encode("utf-8")) <= definition["max_utf8_bytes"]
        if "pattern" in definition:
            import re
            assert re.fullmatch(definition["pattern"], value)
    else:
        raise AssertionError(kind)


def expression(value):
    if isinstance(value, Width):
        return 0, Counter({value.name: 1})
    if isinstance(value, (dict, list)):
        base, variables = 2 + max(0, len(value) - 1), Counter()
        children = value.values() if isinstance(value, dict) else value
        if isinstance(value, dict):
            base += sum(len(canonical(key)) + 1 for key in value)
        for child in children:
            fixed_bytes, terms = expression(child)
            base += fixed_bytes
            variables.update(terms)
        return base, variables
    return len(canonical(value)), Counter()


def widths(value):
    if isinstance(value, Width):
        return {value.name: value}
    result = {}
    if isinstance(value, (dict, list)):
        for child in value.values() if isinstance(value, dict) else value:
            for name, bound in widths(child).items():
                assert name not in result or result[name] == bound
                result[name] = bound
    return result


def size(value, assignment):
    base, terms = expression(value)
    return base + sum(count * assignment[name] for name, count in terms.items())


def annotated(value):
    if isinstance(value, Width):
        return {"$unresolved_scalar_width": value.name, "family": value.family,
            "canonical_width_interval": [value.lower, value.upper], "basis": value.basis}
    if isinstance(value, dict):
        return {key: annotated(child) for key, child in value.items()}
    if isinstance(value, list):
        return [annotated(child) for child in value]
    return value


def ledger(value, assignment, path="", key_bytes=0, comma_bytes=0):
    container = isinstance(value, (dict, list))
    base, terms = expression(value)
    own = 2 if container else size(value, assignment)
    rows = [dict(path=path or "/", canonical_subtree_bytes=size(value, assignment),
        fixed_subtree_bytes=base, width_terms=dict(sorted(terms.items())),
        key_and_colon_bytes=key_bytes, preceding_comma_bytes=comma_bytes,
        own_bytes=own + key_bytes + comma_bytes,
        evidence_kind="SYMBOLIC_WIDTH_CALCULATION_NOT_EXECUTION_WITNESS")]
    if container:
        items = sorted(value.items()) if isinstance(value, dict) else enumerate(value)
        for index, (key, child) in enumerate(items):
            rows.extend(ledger(child, assignment, path + "/" + str(key),
                len(canonical(key)) + 1 if isinstance(value, dict) else 0, int(index > 0)))
    return rows


def source_audit():
    path = ROOT / "core/synthetic_runtime_authorization.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    source = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "_SOURCE" for target in node.targets))
    assert type(source) is bytes and len(source) == 239 and sha256(source).hexdigest() == SOURCE_HASH
    return dict(owner_source_path=path.relative_to(ROOT).as_posix(), bytes=len(source),
        sha256=SOURCE_HASH, exact_source_ascii=source.decode("ascii"), recovery="AST literal only; owner never imported",
        wire_source_bytes=0, wire_source_reason="Frozen schema has exact readback/manifest evidence; no raw source field. No mandatory field omitted.")


def profile(name, *, writers=True, candidate=False, owner_width=3, kernel=False,
            class_digits=5, envelope=False, nullable_relaxation=False):
    messages = []
    for operation in OPS:
        for direction, value in zip(("request", "response"), pair(operation, writers, nullable_relaxation)):
            shape_check(value, direction, operation)
            assignment = {}
            for key, bound in widths(value).items():
                width = bound.upper if envelope else bound.lower
                if not envelope:
                    if bound.family == "future_owner":
                        width = owner_width
                    if bound.family in ("container", "generation"):
                        width = 66 if candidate else bound.lower
                    if bound.family == "class_size":
                        width = class_digits
                    if kernel:
                        content_widths = {"kernel_mount": 2, "kernel_namespace": 16,
                            "kernel_root": 6, "kernel_process": 8, "kernel_start": 6,
                            "kernel_cgroup": 4, "kernel_descriptor": 11, "kernel_group": 8}
                        if bound.family in content_widths:
                            width = content_widths[bound.family] + 2
                        if bound.family == "issuing_pid":
                            width = 4
                        if bound.family == "mode":
                            width = 5
                assert bound.lower <= width <= bound.upper
                assignment[key] = width
            parts = ledger(value, assignment)
            payload = size(value, assignment)
            assert sum(row["own_bytes"] for row in parts) == payload
            base, terms = expression(value)
            messages.append(dict(operation=operation, direction=direction,
                canonical_payload_bytes=payload, canonical_payload_kind="EXACT_FOR_DECLARED_WIDTH_ASSIGNMENT_ONLY",
                physical_frame_bytes=payload + 4 if candidate else None,
                physical_stream="controller_stdout" if candidate and direction == "response" else
                    "controller_stdin" if candidate else "UNSELECTED",
                inside_effect_interval=True, inside_stdout_cap=candidate and direction == "response",
                stdout_mapping_universally_frozen=False, fixed_bytes=base,
                width_terms=dict(sorted(terms.items())), width_assignment=assignment,
                field_and_subtree_contributions=parts,
                annotated_symbolic_layout=annotated(value),
                attainable_execution_witness=False))
    responses = [row for row in messages if row["direction"] == "response"]
    total = sum(row["canonical_payload_bytes"] for row in responses)
    framed = total + 8 if candidate else None
    return dict(name=name, kind="SYMBOLIC_RELAXATION_OR_CONDITIONAL_SENSITIVITY_NOT_WITNESS",
        controller_writers=1 if writers else 0, potential_write_handles_per_writer=2 if writers else 0,
        writer_free_is_relaxation_only=not writers, owner_id_content_width=owner_width - 2,
        kernel_widths_illustrative_not_frozen=kernel, candidate_A_UNSELECTED=True,
        class_size_decimal_width=class_digits, schema_superset_upper_envelope=envelope,
        attainable_execution_witness=False, messages=messages,
        materialization_response_bytes=responses[0]["canonical_payload_bytes"],
        compile_response_bytes=responses[1]["canonical_payload_bytes"],
        response_aggregate_payload_bytes=total, response_frame_overhead_bytes=8 if candidate else None,
        candidate_A_framed_aggregate_bytes=framed,
        semantic_margin=CAP-total, semantic_utilization_percent=100*total/CAP,
        candidate_A_margin=None if framed is None else CAP-framed,
        candidate_A_utilization_percent=None if framed is None else 100*framed/CAP,
        request_payload_total=sum(row["canonical_payload_bytes"] for row in messages if row["direction"] == "request"),
        request_bytes_added_to_stdout=0, candidate_A_stderr_success_bytes=0 if candidate else None,
        stderr_basis="Candidate A success emits no controller stderr; compiler captures are separate and empty. Universal mapping/diagnostics unresolved.")


def sensitivity(profiles):
    base = next(row for row in profiles if row["name"] == "candidate_A_writer_lower_widths_class_5_digits")
    counts, growth = Counter(), Counter()
    for row in base["messages"]:
        if row["direction"] != "response":
            continue
        atoms = widths(pair(row["operation"])[1])
        for name, count in row["width_terms"].items():
            bound = atoms[name]
            counts[bound.family] += count
            growth[bound.family] += count * (bound.upper - row["width_assignment"][name])
    writer_free = profile("matching_writer_free_sensitivity", candidate=True, writers=False)
    return dict(reference_profile=base["name"], reference_framed_bytes=base["candidate_A_framed_aggregate_bytes"],
        family_occurrences_in_responses=dict(sorted(counts.items())),
        extra_bytes_at_broad_schema_width_ceiling_by_family=dict(sorted(growth.items())),
        effect_of_one_more_canonical_byte_at_every_future_owner_id=counts["future_owner"],
        all_equal_owner_content_width_fit_threshold_with_every_other_lower_width_held=1 + base["candidate_A_margin"] // counts["future_owner"],
        owner_width_threshold_is_attainable_or_recommended=False,
        writer_root_layout_increment_payload=base["response_aggregate_payload_bytes"] - writer_free["response_aggregate_payload_bytes"],
        writer_increment_scope="One accounted writer/two potential root handle records in EACH response, with unknown identity widths at lower relaxation. Exhaustiveness unresolved.",
        class_decimal_width_rows=[dict(decimal_width=digits,
            response_payload_bytes=base["response_aggregate_payload_bytes"] - 2 * (5-digits),
            candidate_A_framed_bytes=base["candidate_A_framed_aggregate_bytes"] - 2 * (5-digits)) for digits in range(1,6)],
        conventional_mode_width_sensitivity=[dict(convention=label, maximum_decimal_width=digits,
            mode_occurrences=counts["mode"],
            candidate_A_framed_bytes=base["candidate_A_framed_aggregate_bytes"] + counts["mode"] * (digits-1),
            remaining_margin=base["candidate_A_margin"] - counts["mode"] * (digits-1),
            frozen_exhaustive_semantic_envelope=False)
            for label, digits in (("permission bits", 4), ("ordinary Linux full st_mode", 5))],
        mode_convention_sources=["core/direct_read_receipt.py:94,323 and core/repository_inventory.py:45 use int(st_mode)",
            "core/undo_backup.py:107 uses stat.S_IMODE; core/failed_rollback_recovery.py:144 bounds permission mode by 0o7777"],
        frozen_kernel_max_width_fit=False,
        conclusion="The 4/5-digit conventional mode ceilings both fit the lower-width layout; mode is not independently shown to block fit. The 19-digit schema-superset excess cannot settle a tighter semantic width theorem. Broad upper excess and illustrative-width excess are not universal lower bounds.")


def build():
    profiles = [profile("universal_lower_relaxation", writers=False, nullable_relaxation=True, class_digits=1),
        profile("minimal_writer_layout_lower_widths", class_digits=1),
        profile("candidate_A_writer_lower_widths_class_1_digit", candidate=True, class_digits=1),
        profile("candidate_A_writer_lower_widths_class_5_digits", candidate=True),
        profile("candidate_A_owner_32_hex_width_sensitivity", candidate=True, owner_width=34),
        profile("candidate_A_owner_64_hex_width_sensitivity", candidate=True, owner_width=66),
        profile("candidate_A_illustrative_kernel_width_sensitivity", candidate=True, kernel=True),
        profile("candidate_A_64_hex_and_kernel_width_sensitivity", candidate=True, owner_width=66, kernel=True),
        profile("schema_superset_upper_envelope", envelope=True)]
    return dict(phase_id="SYNTH.EXEC.PREP.CONTROLLER.BUDGET.PROOF.1R",
        typed_result="BUDGET_WITNESS_UNRESOLVED",
        identity_subresult="BUDGET_WITNESS_IDENTITY_ENCODING_UNRESOLVED",
        typed_result_reason="Identity/kernel/writer representation prevents an attainable witness; independently, unselected physical framing/mapping prevents universal physical feasibility. Identity is not the only blocker.",
        historical_BUDGET_PROOF_1_result="AGGREGATE_BUDGET_SCOPE_UNRESOLVED",
        scope_requirement_result="SYNTH_EXEC_PREP_CONTROLLER_BUDGET_SCOPE_REQ_1_COMPLETE",
        effect_sequence=[operation + " " + direction for operation in OPS for direction in ("request", "COMPLETE response")],
        intervening_observation_required=False,
        observation_basis="Final local fenced current snapshots/readbacks are mandatory; frozen contract does not require an additional serialized OBSERVE exchange between the two effects. Mutation post-observation challenges/sequence remain embedded and distinct.",
        excluded_separately_bounded=["initial OBSERVE_EMPTY_WORKSPACE", "fresh post-compile readiness OBSERVE_*", "receipt authentication", "handoff", "cleanup", "outer custodian evidence"],
        canonical_encoding=dict(encoding="UTF-8", sort_keys=True, separators=[",", ":"], ensure_ascii=True, allow_nan=False),
        source_audit=source_audit(), profiles=profiles, sensitivity=sensitivity(profiles),
        attainable_witness_produced=False, schema_layout_check_is_attainability_proof=False,
        symbolic_relation_constraints=["Same original workspace/controller/container/generations/attempt/exclusive-owner bindings throughout.",
            "Same immutable stable_fingerprint in both states; it excludes mutable manifests and liveness.",
            "Distinct single-use request/operation/admission identities per exchange; exact encodings unresolved.",
            "Fresh mutation-bound post-observation references/sequences prebound in each spent admission; no readiness challenge reused.",
            "Source unchanged; same eventual actual class digest/size in output manifest and class_metadata.",
            "Width assignments alone cannot authenticate any original relation or kernel observation."],
        exact_attainable_materialization_response_bytes=None,
        exact_attainable_compile_response_bytes=None,
        exact_attainable_aggregate_payload_bytes=None,
        exact_attainable_physical_bytes=None,
        semantic_response_payload_feasibility="UNRESOLVED",
        physical_transport_feasibility="UNRESOLVED",
        candidate_A_could_fit_proved=False, candidate_A_impossible_proved=False,
        universal_impossibility_proved=False, budget_blocker_removed=False,
        transport_selection_may_continue=False,
        transport_selection_reason="Review can continue; final selection gate remains blocked by truthful aggregate proof and independent backend-generation cleanup continuity.",
        exact_class_size_required_for_width_arithmetic=False,
        class_size_analysis=dict(legal_envelope=[1,32768], legal_decimal_widths=[1,2,3,4,5],
            occurrences=2, worst_minus_best_response_bytes=8,
            bound_is_valid_class_conditional=True, one_byte_class_claimed=False,
            sha256_occurrences=2, sha256_canonical_width_each=66,
            dependencies=["exact class SHA256 in manifest and class_metadata; value unknown but fixed width",
                "exact class size in manifest and class_metadata; 1..32768 controls only decimal width",
                "stable_fingerprint covers immutable original identity only, excludes mutable manifests/liveness; SHA256 always fixed width and not a class-byte dependency",
                "internal_class_name/inspection_kind/class_loaded fixed success predicates; no other byte-derived schema metadata"],
            class_existence_proved_by_width_arithmetic=False),
        writer_analysis=dict(structural_lower_profile="One accounted controller task with potential write access to both /work and /tmp; two root-access records per snapshot. Compiler reaped before prepared snapshot. These records are not proved exhaustive.",
            exact_representation_frozen=False, closed_transient_handles_assumed_for_minimal_shape=True,
            no_writer_free_attainability_claim=True,
            unresolved=["process/task incarnation encoding", "potential-access descriptor identity", "accounted original owner relation encoding", "active/admitted operation marker observation instant", "descendant access grouping for classes/source/class", "creation modes/umask and retained descriptor inventory"]),
        frozen_envelope_strategy=dict(class_size="all five decimal widths evaluated; exact compiled size unnecessary for conditional fit conclusion",
            modes_uid_gid_links_pid="Full schema 63-bit integer superset assessed; mode meaning not selected. UID/GID65534 fixed for controller and artifacts.",
            kernel_and_owner_text="Only broad schema superset yields finite canonical widths; it does not fit and is not a semantic execution profile. No shorter encoding inferred.",
            worst_case_fit_proved=False),
        minimum_next_semantic_contract=["Freeze owner-backed encodings and equality/binding rules for workspace, controller, exclusive-owner, admission, attempt, request, operation and deadline identities; identify any reuse of existing owner primitives explicitly.",
            "Freeze kernel observation serialization for mount/root/generation/process/task/namespaces/cgroup/start/group and potential-writer handles, snapshot active-operation semantics, creation permissions/umask and descriptor lifecycle. Define numeric mode/ownership/link/PID/TID projections and finite semantic widths, or prove the fit result invariant across their legitimate representations.",
            "Freeze applicable physical response/diagnostic stream mapping and an upper bound on actual framing. A transport-independent framing envelope would suffice; this phase selects none."],
        backend_generation_cleanup_blocker="Independent same-backend immutable-generation continuity and exact retained full-ID teardown/absence provenance remain unresolved; pinning a container ID or runtime fingerprint does not freeze backend incarnation.",
        cap_per_outer_stream=CAP, transport_selected=False, candidate_A_selected=False,
        schema_changed=False, cap_changed=False, pins_changed=False,
        authority_flags={key: False for key in CONTRACT["authority_flags"]},
        operational_effects={key: 0 for key in CONTRACT["operational_effects"]}, stop=True)


def write_json(name, value):
    (HERE / name).write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def main():
    result = build()
    write_json("budget_witness.json", result)
    write_json("byte_totals.json", [{key: value for key, value in profile.items() if key != "messages"}
                                  for profile in result["profiles"]])
    print(json.dumps({"typed_result": result["typed_result"], "profiles": {
        profile["name"]: [profile["materialization_response_bytes"], profile["compile_response_bytes"],
            profile["response_aggregate_payload_bytes"], profile["candidate_A_framed_aggregate_bytes"]]
        for profile in result["profiles"]}}, sort_keys=True))


if __name__ == "__main__":
    main()
