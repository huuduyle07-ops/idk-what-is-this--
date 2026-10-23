"""Assemble the additive report; all writes stay in this phase, under guard."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import runpy

HERE = Path(__file__).resolve().parent
REPORT_NAME = "SYNTH_EXEC_PREP_CONTROLLER_BUDGET_PROOF_1R_REPORT.json"


def read(name):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def write(name, value):
    (HERE / name).write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def assemble(counters, blocked):
    proof, identities, workspace = (read(name) for name in
        ("budget_witness.json", "identity_audit.json", "workspace_audit.json"))
    evidence = {name: read(name + ".json") for name in ("proof", "focused", "benchmark",
        "registry_baseline", "registry_after", "registry_comparison", "static_validation",
        "preservation_comparison", "git_validation")}
    for name in ("proof", "focused", "benchmark"):
        assert evidence[name]["exit_code"] == 0
    assert evidence["focused"]["collected"] == evidence["focused"]["passed_count"]
    assert evidence["benchmark"]["benchmark_errors"] == 0
    assert evidence["registry_comparison"]["unchanged"]
    assert evidence["static_validation"]["passed"]
    assert evidence["preservation_comparison"]["historical_preservation_passed"]
    git = evidence["git_validation"]
    assert git["git_diff_check_exit_code"] == 0 and git["git_cached_diff_check_exit_code"] == 0
    assert git["baseline_vs_after_identical"]
    validator_sha = sha256((HERE / "validate_pure.py").read_bytes()).hexdigest()
    for name in ("proof", "focused", "benchmark", "registry_baseline", "registry_after"):
        value = evidence[name]
        assert value["all_operational_effects_zero"] and not value["blocked_actions"]
        assert not value["imported_capability_owners"] and not any(value["audit_guard"].values())
        assert value["validator_sha256"] == validator_sha
    assert proof["typed_result"] == "BUDGET_WITNESS_UNRESOLVED"
    assert identities["identity_subresult"] == proof["identity_subresult"]
    assert not any(proof["authority_flags"].values()) and not any(proof["operational_effects"].values())
    profiles = [{key: value for key, value in profile.items() if key != "messages"}
                for profile in proof["profiles"]]
    summary = dict(phase_id=proof["phase_id"], typed_result=proof["typed_result"],
        created_at="2026-10-19", all_required_validation_checks_passed=True,
        focused_collected=evidence["focused"]["collected"], focused_passed=evidence["focused"]["passed_count"],
        benchmark_checked=evidence["benchmark"]["benchmark_cases_checked"], benchmark_errors=0,
        registry_baseline_collected=evidence["registry_baseline"]["collected"],
        registry_baseline_passed=evidence["registry_baseline"]["passed_count"],
        registry_existing_failures=len(evidence["registry_baseline"]["failed"]),
        registry_baseline_vs_after_identical=True, historical_preservation=True,
        in_memory_python_compiled=evidence["static_validation"]["compiled_count"],
        git_diff_check_passed=True, all_guarded_effects_zero=True,
        validator_sha256=validator_sha, finalizer_guard=counters, finalizer_blocked_actions=blocked,
        evidence_files=sorted(name + ".json" for name in evidence))
    write("validation_summary.json", summary)
    report = {key: value for key, value in proof.items() if key != "profiles"}
    report.update(profile_byte_totals=profiles, identity_encoding_matrix=identities["identity_encoding_matrix"],
        source_audits=["identity_audit.json", "workspace_audit.json"],
        validation=summary, full_field_and_subtree_ledgers="budget_witness.json")
    write(REPORT_NAME, report)
    lines = ["# SYNTH.EXEC.PREP.CONTROLLER.BUDGET.PROOF.1R", "",
        "**BUDGET_WITNESS_UNRESOLVED**", "",
        "No complete attainable successful preparation witness is established. Identity subresult: "
        "`BUDGET_WITNESS_IDENTITY_ENCODING_UNRESOLVED`. Future-owner/kernel/writer representations "
        "are unresolved; independently, transport framing and physical stream mapping remain unselected. "
        "Because identity is not the only blocker, the overall result is the broader unresolved type. "
        "Neither universal feasibility nor universal impossibility is proved.", "",
        "The budget blocker is not removed. Final transport selection remains blocked; review may continue. "
        "Candidate A remains UNSELECTED. The independent backend-generation cleanup blocker also remains.", "",
        "The historical BUDGET.PROOF.1 result remains `AGGREGATE_BUDGET_SCOPE_UNRESOLVED`. "
        "Scope requirement 1 is frozen and unchanged. This phase changes no contract, schema, cap, pins, "
        "controller, runtime, provider, registry or picker.", "",
        "**Exact effect scope.** The counter origin is the preparation owner's authenticated "
        "single-operation admission record for the already-spent original materialization facet, "
        "immediately before dispatch. The endpoint is the final physical byte of the complete terminal "
        "COMPILE response, including the full embedded state and actual framing.", "",
        "1. MATERIALIZE_EXACT_SCENARIO_SOURCE request.",
        "2. MATERIALIZE_EXACT_SCENARIO_SOURCE COMPLETE response, with full materialized workspace_state once.",
        "3. COMPILE_EXACT_SCENARIO request.",
        "4. COMPILE_EXACT_SCENARIO COMPLETE response, with full post-reap prepared workspace_state once.", "",
        "No additional serialized OBSERVE exchange is explicitly required between these messages. "
        "Fresh owner checks, final local fenced source/readback/manifest validation and mutation-bound "
        "post-observation remain required. If a future implementation invokes an observation inside this "
        "interval, its bytes count. No such exchange is invented here. Mutation envelope challenges are "
        "null; embedded state challenges/sequences are separate single-use references prebound in spent "
        "admissions, and do not substitute for readiness challenges.", "",
        "Initial OBSERVE_EMPTY_WORKSPACE, a fresh post-compile readiness OBSERVE_*, receipt authentication, "
        "handoff, cleanup and outer-custodian evidence are outside this capture under separate bounds. "
        "The fresh readiness observation is mandatory validation before readiness/handoff; its individual "
        "request/response bound is 8192 bytes. No attained readiness record or invented size is reported, "
        "and it contributes zero bytes to this effect ledger.", "",
        "**Attainable versus relaxed.** Exact attained materialization-response size, compile-response "
        "size, aggregate semantic size and physical size are all UNRESOLVED (JSON null), because there "
        "is no justified scalar assignment. The byte counts below are exact for declared symbolic widths, "
        "not successful execution witnesses. Unknown fields are annotated width variables, never one-character "
        "fake IDs, incarnation aliases, fabricated hashes, invented container/kernel identities or class files. "
        "Complete schema layout checking is not authenticity or attainability.", "",
        "Canonical arithmetic uses UTF-8, sort_keys=true, separators=(',', ':'), ensure_ascii=true and "
        "allow_nan=false. Every mandatory nullable key remains. No whitespace, compression, aliases, "
        "renaming, omission, evidence movement or workspace-state deduplication is used.", "",
        "**Exact conditional byte ledger.** Positive margins mean spare bytes; negative margins mean excess. "
        "Every row is symbolic arithmetic, not an established attainable witness. Class-size width is five digits except "
        "universal_lower_relaxation, minimal_writer_layout_lower_widths and the explicit one-digit Candidate-A row. "
        "Those three use one decimal digit. A one-digit width is not a one-byte class claim.", "",
        "| Symbolic profile | Materialize response | Compile response | Response payload | A headers | A framed | Payload margin | A margin | A utilization |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for p in profiles:
        fmt = lambda value: "unselected" if value is None else str(value)
        use = "unselected" if p["candidate_A_utilization_percent"] is None else f'{p["candidate_A_utilization_percent"]:.6f}%'
        lines.append(f'| {p["name"]} | {p["materialization_response_bytes"]} | {p["compile_response_bytes"]} | '
            f'{p["response_aggregate_payload_bytes"]} | {fmt(p["response_frame_overhead_bytes"])} | '
            f'{fmt(p["candidate_A_framed_aggregate_bytes"])} | {p["semantic_margin"]} | {fmt(p["candidate_A_margin"])} | {use} |')
    lines += ["", "The universal lower relaxation is 6450 bytes, below 8192, so it cannot prove impossibility. "
        "It relaxes the container to the universal schema's generic-ID minimum: only Candidate A explicitly "
        "freezes full container identity to 64 hex. The historical 6702-byte relaxation is preserved, not rerun "
        "or rewritten; this new bound is weaker by 252 bytes across four container-identity occurrences.", "",
        "The conditional Candidate-A one-writer/two-root-access lower-width layout has responses 3251 and "
        "4809 bytes at maximum legal class-size width: 8060 payload + 8 framing = 8068, leaving 124 bytes "
        "(98.486328% physical utilization). Its semantic utilization is 98.388672%. This is NOT a semantic "
        "witness fit and does NOT prove that Candidate A could fit: all unresolved identities use length "
        "lower bounds, modes use width lower bounds, and writer completeness is not established.", "",
        "**Directions and fields.** Each request remains host-to-controller input. In Candidate A only, "
        "each response is controller stdout and receives a four-byte u32be header, exactly eight response "
        "header bytes total. Requests receive their own headers in their own direction and are never added "
        "to stdout. Successful Candidate-A stderr is independently zero; no universal stderr mapping or "
        "diagnostic policy is selected. Compiler stdout/stderr are separate captures, each observed_bytes=0, "
        "limit_bytes=2048, exact empty SHA256, eof=true, overflow=false, closed=true. Their metadata is "
        "already counted once inside the compile response.", "",
        "`budget_witness.json` contains exact per-message canonical payload counts, conditional physical "
        "frame counts, stream/direction, inside-interval status, fixed bytes, each scalar-width assignment, "
        "every key/comma contribution and every nested subtree size. Root totals equal the sum of disjoint "
        "own-byte ledger contributions. The symbolic annotated layouts are not canonical wire messages.", "",
        "| Candidate-A lower-width layout, maximum class width | Payload bytes | Physical bytes | Direction | Effect capture / stdout cap |",
        "| --- | ---: | ---: | --- | --- |"]
    selected = next(p for p in proof["profiles"] if p["name"] == "candidate_A_writer_lower_widths_class_5_digits")
    for m in selected["messages"]:
        lines.append(f'| {m["operation"]} {m["direction"]} | {m["canonical_payload_bytes"]} | '
            f'{m["physical_frame_bytes"]} | {m["physical_stream"]} | yes / {"yes" if m["direction"] == "response" else "input direction"} |')
    lines += ["", "**Identity encoding matrix.** Source keys: " + "; ".join(f"{key} = `{value}`" for key, value in identities["sources"].items()) + ".", "",
        "| Required identity | Classification | Source anchors | Justification |",
        "| --- | --- | --- | --- |"]
    for row in identities["identity_encoding_matrix"]:
        lines.append(f'| {row["field"]} | {row["classification"]} | {", ".join(row["anchors"])} | {row["reason"]} |')
    lines += ["", "The actual repository owner primitives use token_hex(32) for their own authorization, "
        "runtime lease, provider and reflection-admission IDs. They do not define future preparation/workspace "
        "owner IDs. HMAC-SHA256 authentication does not make every owner ID 64 hex. Historical seven-namespace "
        "readlink and raw cgroup text conventions are recoverable source evidence; no live kernel observation "
        "was made, and no new composite/kernel mapping is silently inferred.", "",
        "**Writer evidence.** Both snapshots retain controller process/task inventory, all seven namespaces, "
        "cgroup, both exact tmpfs mounts, root metadata, generation/original bindings and exclusivity observation. "
        "A writer-free profile is only a mathematical relaxation. Controller potential access to both 01777 "
        "roots must be accounted. One accounted controller/task with two potential root-access handles is "
        "a structural lower profile, not a proved complete inventory: descendant coverage for classes/source/class, "
        "creation permissions/umask, retained descriptors and potential-access identity projection remain unresolved. "
        "The compiler must be reaped and absent from the postcompile process/task/writer inventory; capture/group "
        "evidence still remains in the compile response.", "",
        "The two-root structural writer layout adds " + str(proof["sensitivity"]["writer_root_layout_increment_payload"]) +
        " payload bytes across the two responses versus the matching writer-free layout, at the same unresolved "
        "lower widths and null markers. That arithmetic does not remove any mandatory actual writer records.", "",
        "**Source, compilation and class envelope.** AST-only recovery confirms the original exact 239-byte "
        "source with SHA256 `" + SOURCE_HASH_PLACEHOLDER(proof) + "`. The full source bytes are retained in "
        "the audit as pure data, with no source file materialization. The frozen wire schema contains its "
        "complete manifest and exact readback size/hash/equality evidence; it has no raw-source field. No such "
        "field is added or mandatory source evidence omitted. `/work/classes` is present in both manifests; "
        "the prepared manifest additionally contains only `/work/classes/SyntheticStateBox.class`. Source "
        "identity is unchanged. Exact compiler path/hash/argv/cwd/environment/image constants remain in full; "
        "capture_and_reap requires exit_code=0, timed_out=false, reaped=true, group_terminated=true and "
        "selectors_closed=true. No target JVM is started or represented.", "",
        "Class size appears twice and its SHA256 appears twice. Across every valid size in 1..32768, only "
        "the two decimal widths vary, by at most eight bytes total. No exact compiled size is needed for "
        "these conditional arithmetic comparisons. The actual class hash remains unknown but fixed at 64 hex; "
        "no fake class hash or one-byte successful class is supplied. Internal class name, inspection kind, "
        "class-loaded=false and path are fixed. Stable fingerprint concerns immutable original identity only, "
        "excludes mutable manifests/liveness, stays equal in both snapshots and has fixed SHA256 width. "
        "There are no additional byte-derived class metadata fields in the frozen schema.", "",
        "| Class decimal width | Response payload | Candidate-A framed total |",
        "| --- | ---: | ---: |"]
    for row in proof["sensitivity"]["class_decimal_width_rows"]:
        lines.append(f'| {row["decimal_width"]} | {row["response_payload_bytes"]} | {row["candidate_A_framed_bytes"]} |')
    lines += ["", "**Width sensitivity.** There are 17 future-owner ID occurrences across responses. Holding "
        "every other unresolved width at its relaxed minimum, each extra shared owner-ID content byte adds "
        "17 bytes. Uniform content width at most eight would fit that conditional layout; this is neither "
        "an attainable encoding nor a recommendation. A hypothetical 32-hex convention produces 8595 framed "
        "bytes (403 excess); actual existing-owner-style 64-hex widths produce 9139 (947 excess) even before "
        "kernel widths grow. No such convention is assigned to the missing owners.", "",
        "Illustrative kernel widths alone produce 8661 framed bytes (469 excess); combining them with 64-hex "
        "owner widths gives 9732 (1540 excess). These are width sensitivities, not fabricated kernel records "
        "or universal lower bounds. The complete family-occurrence and independent-width growth ledger is "
        "in `budget_witness.json` under sensitivity.", "",
        "Mode meaning is unresolved between full st_mode, permission bits or another observation projection. "
        "Mode zero is never asserted as successful metadata. Local source uses both int(st_mode) "
        "(direct_read_receipt.py:94,323; repository_inventory.py:45) and stat.S_IMODE "
        "(undo_backup.py:107; failed_rollback_recovery.py:144 bounds permissions by 0o7777). "
        "Conditionally bounding nine mode occurrences by four decimal digits gives 8095 framed bytes "
        "with 97 margin; an ordinary Linux full-st_mode five-digit ceiling gives 8104 with 88 margin. "
        "Thus these conventional mode alternatives do not independently block the lower-width layout. "
        "The frozen controller does not adopt either serializer or explicitly make those alternatives "
        "exhaustive, so no new convention is selected.", "",
        "Unknown integer fields also have a conservative 19-digit schema superset; controller/artifact "
        "UID/GID65534 and regular-file single-link values retain their exact values. Mode-only growth "
        "to that broad ceiling adds 162 bytes, but this is syntactic superset sensitivity, not a "
        "substantive claim that an actual filesystem mode blocks fit. It does not settle the tighter "
        "semantic width-invariance question. Identity encoding, complete writer inventory and physical "
        "framing remain independent blockers regardless of mode convention.", "",
        "Generic IDs are bounded by 256 UTF-8 bytes, not 256 canonical bytes. With ensure_ascii=true, a legal "
        "one-byte non-NUL control character can require six bytes, so the broad quoted-string ceiling is "
        "1538 bytes. The full schema-superset upper width arithmetic is 142906 response payload bytes for "
        "the same structural topology. This is deliberately a superset, not a possible kernel/owner state. "
        "Its excess neither proves impossibility nor establishes a semantic finite-width fit.", "",
        "**Physical framing.** Semantic response-payload feasibility is UNRESOLVED. Physical transport "
        "feasibility is independently UNRESOLVED: controller contract defers concrete framing and transport "
        "mapping, and schema says transport_byte_prefix_unselected=true. An individual physical-frame cap "
        "does not prove cumulative two-response fit. Only Candidate A defines the four-byte header, stdout "
        "responses and empty successful stderr. No universal framing-overhead bound makes a conditional "
        "payload count into universal physical feasibility. Candidate-A-only excess cannot prove universal "
        "impossibility, and a sub-cap relaxation cannot prove Candidate-A feasibility.", "",
        "**Minimum next semantic contract.** No requirement evolution is performed. The smallest missing "
        "semantic commitments are:", ""]
    lines.extend(str(index) + ". " + text for index, text in enumerate(proof["minimum_next_semantic_contract"], 1))
    lines += ["", "**Independent cleanup blocker.** " + proof["backend_generation_cleanup_blocker"] +
        " Existing sandbox_backend_provenance.py:86-100 has no owner-defined backend continuity mechanism. "
        "Candidate selection.json:450-451 requires an independently authenticated original backend/container "
        "generation relation usable after loss of the inner channel; endpoint/version/full-ID equality "
        "does not discharge that obligation.", "",
        "**Validation.** Focused proof/frozen-contract tests: " + str(summary["focused_passed"]) + "/" + str(summary["focused_collected"]) +
        "; benchmark --check: " + str(summary["benchmark_checked"]) + " cases, zero errors. Registry/picker "
        "baseline versus after is identical: 299 collected, 292 passed, the same seven pre-existing "
        "failures and exact normalized signatures. Python compilation is in memory; JSON/whitespace and "
        "git diff --check pass. Historical preservation covers " + str(evidence["preservation_comparison"]["baseline_file_count"]) +
        " existing non-cache files and detects no outside-phase additions, changes or deletions. "
        "All guarded process/network/owner-import/issuance/transition/execution/outside-phase-write counters "
        "are zero. All authority flags are false and all operational effects are zero. No Docker, javac/java, "
        "live kernel inspection, capability issuance or source materialization occurred. STOP.", ""]
    (HERE / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    (HERE / "README.md").write_text("# Pure preparation-capture witness audit\n\nBUDGET_WITNESS_UNRESOLVED. "
        "Read REPORT.md and the typed report JSON. Full symbolic field/subtree arithmetic is in budget_witness.json; "
        "identity_audit.json and workspace_audit.json retain source anchors. No attainable execution witness or "
        "transport selection is claimed. All additions are confined to this phase.\n", encoding="utf-8")
    checks = dict(python_compiled=[], json_validated=[], whitespace_errors=[])
    for path in HERE.rglob("*"):
        if not path.is_file() or "validation_tmp" in path.parts or path.suffix not in (".py", ".json", ".md"):
            continue
        content = path.read_text(encoding="utf-8")
        if path.suffix == ".py":
            compile(content, str(path), "exec")
            checks["python_compiled"].append(path.relative_to(HERE).as_posix())
        elif path.suffix == ".json":
            json.loads(content)
            checks["json_validated"].append(path.relative_to(HERE).as_posix())
        checks["whitespace_errors"].extend(dict(file=str(path), line=number)
            for number, line in enumerate(content.splitlines(), 1) if line.rstrip() != line)
    assert not checks["whitespace_errors"] and not any(counters.values()) and not blocked
    checks.update(passed=True, finalizer_guard=counters, finalizer_blocked_actions=blocked,
        report_sha256=sha256((HERE / "REPORT.md").read_bytes()).hexdigest())
    write("final_artifact_checks.json", checks)
    print(json.dumps(summary, sort_keys=True))


def SOURCE_HASH_PLACEHOLDER(proof):
    return proof["source_audit"]["sha256"]


if __name__ == "__main__":
    validator = runpy.run_path(str(HERE / "validate_pure.py"))
    with validator["operational_guard"]() as (counters, blocked):
        assemble(counters, blocked)
