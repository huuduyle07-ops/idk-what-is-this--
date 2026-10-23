"""Aggregate measured source-only checks; never an operational evidence owner."""
from hashlib import sha256
import json
from pathlib import Path

PHASE = Path(__file__).resolve().parent
NAME = "SYNTH_EXEC_PREP_CONTROLLER_CONTRACT_1_REPORT"


def read(name):
    return json.loads((PHASE / name).read_text(encoding="utf-8"))


def write(name, value):
    (PHASE / name).write_text(json.dumps(value, indent=2, sort_keys=True,
        ensure_ascii=True, allow_nan=False) + "\n", encoding="utf-8")


def main():
    contract = read("contract.json")
    checks = {name: read(name + ".json") for name in
        ("author", "focused", "registry_baseline", "registry_after", "benchmark")}
    registry = read("registry_comparison.json")
    static, git, preservation = (read(name + ".json") for name in
        ("static_validation", "git_diff_check", "preservation_comparison"))
    guarded = all(item["all_operational_effects_zero"] and not item["imported_capability_owners"]
        and not item["blocked_actions"] and not any(item["audit_guard"].values()) for item in checks.values())
    passed = all((checks["author"]["exit_code"] == 0, checks["focused"]["exit_code"] == 0,
        checks["focused"]["collected"] == checks["focused"]["passed_count"] > 0,
        not checks["focused"]["failed"], not checks["focused"]["collection_errors"],
        checks["benchmark"]["exit_code"] == 0, checks["benchmark"]["benchmark_cases_checked"] > 0,
        checks["benchmark"]["benchmark_errors"] == 0, registry["unchanged"], static["passed"],
        git["passed"], preservation["historical_preservation_passed"], guarded,
        all(value is False for value in contract["authority_flags"].values()),
        all(type(value) is int and value == 0 for value in contract["operational_effects"].values())))
    result = contract["typed_result"] if passed else "CONTRACT_UNRESOLVED"
    summary = {
        "typed_result": result, "all_required_pure_checks_passed": passed,
        "focused": {"collected": checks["focused"]["collected"], "passed": checks["focused"]["passed_count"]},
        "registry_picker": {"baseline_collected": registry["baseline_collected"],
            "after_collected": registry["after_collected"], "baseline_passed": registry["baseline_passed"],
            "after_passed": registry["after_passed"], "unchanged": registry["unchanged"],
            "projections_identical": registry["registry_and_picker_projections_identical"],
            "existing_failure_nodes": [item["nodeid"] for item in checks["registry_baseline"]["failed"]],
            "signature_comparison": registry["signature_comparison"], "baseline_not_repaired": True},
        "benchmark": {"cases_checked": checks["benchmark"]["benchmark_cases_checked"],
            "errors": checks["benchmark"]["benchmark_errors"]},
        "static": {"compiled_in_memory": static["compiled_count"], "JSON_files_validated": static["json_count"],
            "passed": static["passed"], "bytecode_written": False},
        "git_diff_check": {"passed": git["passed"], "existing_whitespace_unchanged": git["existing_whitespace_unchanged"],
            "new_phase_files_checked": git["phase_files_checked_without_index_mutation"], "index_modified": False},
        "preservation": preservation,
        "guarded_runs": {name: {key: value[key] for key in ("audit_guard", "blocked_actions",
            "imported_capability_owners", "validator_sha256")} for name, value in checks.items()},
        "all_guarded_operational_effects_zero": guarded, "operational_effects": contract["operational_effects"],
        "all_authority_flags_false": all(value is False for value in contract["authority_flags"].values()),
        "scope": "pure source/AST/contract checks only; no operational owner import, issuance or execution",
    }
    write("validation_summary.json", summary)
    evidence_names = ("contract.json", "message_schema.json", "evidence_index.json", "validation_summary.json",
        "preservation_baseline.json", "write_contract.py", "test_contract.py", "validate_pure.py", "finalize_report.py")
    report = {"phase_id": contract["phase_id"], "typed_result": result,
        "meaning": contract["result_meaning"], "protocol_frozen": True,
        "controller_source_identity_resolved": False, "concrete_transport_selected": False,
        "controller_workspace_or_operational_capability_exists_by_this_phase": False,
        "behavioral_activation_ready": False, "runtime_consumption_ready": False, "reason": "PROOF_UNRESOLVED",
        "evidence_sha256": {name: sha256((PHASE / name).read_bytes()).hexdigest() for name in evidence_names},
        "validation": summary, "stop": True}
    write(NAME + ".json", report)
    failures = "\n".join("- `" + node + "`" for node in summary["registry_picker"]["existing_failure_nodes"])
    markdown = f"""# SYNTH.EXEC.PREP.CONTROLLER.CONTRACT.1

**{result}**

The additive retained live preparation controller protocol is frozen. No
controller implementation, workspace or operational capability exists.
Behavioral activation and runtime consumption remain false / PROOF_UNRESOLVED.

## Scope and preserved foundation

The conceptual additive owner is
`core.synthetic_execution_preparation_controller_pinned`, protocol
`synthetic_preparation_controller_pinned_1_v1`. No Python class or owner module
is created. Source bytes, source SHA256 and source size are null until actual
implementation. No hash is invented.

The immutable foundation remains image
`sha256:f6d7dc31a15bb37a618ebed6772beda3de95fdcc3394eb5a1def9b1d20673f7a`,
SANDBOX.2 profile `runtime_sandbox_2_v1`, policy
`5a36bdf1676c4b0d7b4bef489f5e90b5c8fb201b5194be48baf61f4206a81f75`.
Interpreter `/usr/local/bin/python` resolves to `/usr/local/bin/python3.12`,
SHA256 `0e6475dfda68a9b2d93501449fc47593ca169010e8f4881577b97463fd0c1263`.
The interpreter pin authenticates infrastructure only. Future exact identity
must also bind reviewed source bytes/hash/size, protocol/schema, host process,
full container and workspace/controller generations, bootstrap, environment,
channel endpoints/framing, resource bounds and cleanup responsibility.

Historical JAVA.1C remains a fixed `JavaSandboxProbe` compile/runtime proof.
Its outer `finally` kills/removes the container and checks absence before
return. Its provider validates that historical source and cleanup. Those
receipts cannot authenticate a live scenario workspace or the new controller.
No historical source, cleanup, API, source pin, receipt, provider or contract
was changed. The existing workspace contract retains its historical
`WORKSPACE_REQUIRES_CONTROLLER_EVOLUTION` result.

## Closed operations

| Operation | Exact purpose and admission boundary |
|---|---|
| OBSERVE_EMPTY_WORKSPACE | Workspace owner; full current empty/exclusive predicate, classes absent. |
| OBSERVE_CURRENT_WORKSPACE | Workspace owner; full stage-appropriate current state, no cached manifest shortcut. |
| OBSERVE_PREPARED_ARTIFACTS | Workspace owner; fresh original receipt/artifact integrity before handoff. |
| MATERIALIZE_EXACT_SCENARIO_SOURCE | Preparation owner has spent exact materialization facet; exclusive classes directory and exact 239-byte source/readback. |
| COMPILE_EXACT_SCENARIO | Preparation owner has spent distinct compile facet; verified same-attempt source and exact bounded javac. |
| PREPARE_EXCLUSIVE_HANDOFF | Workspace plus future consumer boundary; exclusive reservation only, activation unresolved. |
| BEGIN_CLEANUP | Independent cleanup custodian; monotonic barrier preempts active work. |
| CLEANUP_AND_REPORT | Same custodian; bounded reaping/capture closure, outer removal and independent absence evidence. |

The three observation tags verify different frozen downstream predicates using
one complete snapshot schema. Cleanup start must preempt immediately; cleanup
completion gathers the later composite evidence. Each operation's owner,
predicates, closed inputs, paths, child process, bounds, postconditions, failure
and cleanup behavior are enumerated in [contract.json](contract.json).

Controller protocol, workspace capability, preparation authority, preparation
receipt, runtime activation authority and consumer authority stay independent.
The owning boundary decides policy permission and spends its own facet.
Controller admission only checks a separately authenticated exact operation
relation and its local generation/fence predicates. It spends no authority.
Scalar IDs, booleans, digests and receipts confer no permission.

## Observations, freshness and framing

Every successful observation covers one bounded same-generation snapshot:
exact container/controller identity, `/work` and `/tmp` mount identities, full
descriptor-relative no-follow manifests with kinds/link counts/sizes/hashes,
mount crossings, complete process/task/writer inventory, cleanup barrier and
active operation/handoff identities. No directory-listing or caller-boolean
substitute is accepted. This protocol permits no `/tmp` infrastructure files.
Limits include three work entries, zero tmp entries, 33007 regular-file bytes,
128 total process tasks/writers/handles, two mounts and an 8192-byte response.
An incomplete or oversized snapshot fails closed without truncating success.

Workspace owner issues a fresh unpredictable 32-byte challenge with monotonic
sequence, exact operation/purpose and original workspace/controller generations.
It independently authenticates complete source observations and the original
live object relation. Controller digest, workspace HMAC and readiness remain
distinct. Timestamps, replay, unchanged manifests or container names are
insufficient. Challenge freshness does not prove daemon continuity.

[message_schema.json](message_schema.json) freezes exact nested semantic
request/response records, operation-specific payloads/results, types, enums,
size/count limits and cross-field predicates. Canonical UTF-8 JSON follows the
workspace contract; duplicate/unknown/missing fields, coercion and bool-as-int
are rejected. Wire prefix and concrete transport remain unselected. Requests
and responses bind version/tag, IDs, generations, sequence, purpose and required
challenge. Mutation poststate is bound to a separate single-use owner reference
in the spent admission, and requires a new OBSERVE challenge before readiness.
Typed errors preserve authenticated originating layer/status/code/reason.

## Preparation and handoff

Materialization alone exclusively creates `/work/classes` and
`/work/SyntheticStateBox.java`, writes the frozen 239 bytes, verifies full
no-follow size/hash/byte readback and observes the exact manifest. No caller
source, overwrite, regeneration, second source or compile is admitted. Existing
source bytes are only a future authenticated in-memory projection; no source
is materialized by this contract. Repository conventions establish no fsync
requirement for this ephemeral tmpfs preparation.

Compilation uses only `/opt/temurin-26.0.2.1/bin/javac` and PREP's exact argv,
cwd and eight-variable environment, copied verbatim. No new flags, classpath,
processor/plugin/dependency inputs or network are added. Compiler captures are
2048 bytes per stream and empty on success; outer captures total 8192 per
stream across the entire attempt. A shared monotonic 5000ms preparation
deadline never resets between materialization and compilation; outer hard
timeout is 10000ms. Retained lifetime is separate and needs a future reviewed
bounded policy. Successful compile requires full reaping/EOF, unchanged source,
exact one-class 1..32768-byte envelope, actual hash and inert metadata identity.
No target class is loaded and no behavior success is claimed.

Handoff reservation binds original workspace/controller generation, preparation
attempt/receipt, exact manifest and separately authenticated future borrower.
Artifacts stay in the same generation. No export, consumer type/schema,
scenario JVM dispatch, behavioral loader, main class or BEFORE/AFTER protocol
is defined. With no consumer contract, reservation activation and borrower
authentication remain PROOF_UNRESOLVED.

## Fences, races and cleanup

At most one mutation or exclusive handoff exists. Observations cannot race
mutations. Cleanup-started is monotonic and preempts busy work: withdraw
readiness, cancel/terminate/reap, close captures and continue teardown. No
materialization, compile, new handoff or ready observation follows the barrier.

Workspace owner authenticates current location; preparation owner authenticates
and spends the exact facet; controller admits only the same-generation fixed
operation under its local fence. Runtime remains separately owned and ISSUED
for preparation. Its report-only check is no reservation. An unobservable
precondition gap aborts with PROOF_UNRESOLVED; no private cross-owner locks or
atomic transaction are claimed. Lost/changed generation, late invalidity or
lost responses cannot refund a facet, repeat an effect or resurrect readiness.

Normal cleanup covers failure, activation/consumer failure, timeout, abandonment
and upstream invalidation. The inner controller cannot remove itself and then
prove absence. A separate host/control-plane custodian therefore exposes only
`TERMINATE_REMOVE_EXACT_RETAINED_GENERATION` and
`OBSERVE_EXACT_RETAINED_GENERATION_ABSENCE`, with their own closed typed
envelopes. They target retained authenticated full container/backend/generation
identity. No ready workspace, ISSUED runtime, unspent facet or inner challenge
is required. No container creation, preparation, controller/handoff restoration
or generic Docker command is allowed. Unsafe identity targeting is
WORKSPACE_CLEANUP_UNRESOLVED.

Composite cleanup evidence binds original generations, barrier, child/group
results, captures/EOF, removal and fresh independent full-ID absence, observer
method/identity and no surviving artifact export. Failed/unresolved cleanup
may return bounded partial evidence with unresolved components. Container
absence alone never fabricates lost-child reaping or EOF. Cleanup evidence is
neither preparation/behavior success nor future authority.

## Validation

- Focused contract/source/AST tests: {checks['focused']['passed_count']}/{checks['focused']['collected']} passed.
- Registry/picker: {registry['baseline_passed']}/{registry['baseline_collected']} before and after; identical projections and seven existing failures preserved.
- Benchmark check: {checks['benchmark']['benchmark_cases_checked']} cases, {checks['benchmark']['benchmark_errors']} errors.
- In-memory compilation, strict contract checks, JSON, whitespace and Git checks passed.
- Whole prior non-cache workspace: {preservation['baseline_file_count']} files unchanged; no additions outside this phase.
- Guarded author/focused/registry/benchmark runs: zero operational counters, no owner imports or blocked effects.

Existing registry/picker failures retained exactly (only allocator addresses in
Python reprs normalized for comparison; raw diagnostics are preserved):

{failures}

See [validation_summary.json](validation_summary.json),
[evidence_index.json](evidence_index.json) and the report JSON for measured
checks and hashes. Required operational effects are all zero. No Docker,
container operation, SANDBOX.2/JAVA.1C verification, issuance, materialization,
javac/java, class loading, reflection, SyntheticStateBox, BANK, executor or Apply
was performed.

STOP after this freeze. Exact new source, concrete retained transport/bootstrap,
live binding/coordination, bounded lifetime, workspace/preparation owners and
full harness/consumer remain future work.
"""
    (PHASE / (NAME + ".md")).write_text(markdown, encoding="utf-8")
    (PHASE / "README.md").write_text("""# Retained live preparation controller protocol

Pure contract only. Read [the report](SYNTH_EXEC_PREP_CONTROLLER_CONTRACT_1_REPORT.md),
[contract.json](contract.json), [message_schema.json](message_schema.json) and
[validation_summary.json](validation_summary.json).

No controller source or workspace owner exists. Source identity and concrete
transport remain unresolved. Behavioral readiness is false / PROOF_UNRESOLVED.

Validation from repository root:

```powershell
python -B docs/roadmap/phases/SYNTH_EXEC_PREP_CONTROLLER_CONTRACT_1/validate_pure.py --mode MODE
```

Modes: snapshot, git_baseline and registry_baseline are immutable and run once
before authoring. Then author, focused, registry_after, compare, benchmark,
static, git_diff, preservation and report. All generated evidence/scratch stays
in this phase. Guarded modes deny owner imports, operational processes,
network and writes outside this phase. Git modes perform source-control
whitespace checks only and never mutate the index. Existing baseline failures
are compared rather than repaired. Historical files are hashed before/after.

The schema is declarative contract data; no parser/controller is implemented.
STOP after contract freeze; no live operations or capabilities are issued.
""", encoding="utf-8")
    if not passed:
        raise AssertionError("Required pure checks did not pass; see validation_summary.json")


if __name__ == "__main__":
    main()
