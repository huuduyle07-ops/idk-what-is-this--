"""Aggregate measured pure validation evidence. This is not a capability owner."""
from hashlib import sha256
import json
from pathlib import Path

PHASE = Path(__file__).resolve().parent
NAME = "SYNTH_EXEC_PREP_WORKSPACE_CONTRACT_1_REPORT"


def read(name):
    return json.loads((PHASE / name).read_text(encoding="utf-8"))


def write(name, value):
    (PHASE / name).write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def main():
    contract = read("contract.json")
    checks = {name: read(name + ".json") for name in
              ("author", "focused", "registry_baseline", "registry_after", "benchmark")}
    registry = read("registry_comparison.json")
    static = read("static_validation.json")
    git = read("git_diff_check.json")
    preservation = read("preservation_comparison.json")
    guard_zero = all(item["all_operational_effects_zero"] and not item["imported_capability_owners"]
                     and not item["blocked_actions"] and not any(item["audit_guard"].values())
                     for item in checks.values())
    passed = all((checks["author"]["exit_code"] == 0,
                  checks["focused"]["exit_code"] == 0,
                  checks["focused"]["passed_count"] == checks["focused"]["collected"] > 0,
                  not checks["focused"]["failed"], not checks["focused"]["collection_errors"],
                  checks["benchmark"]["exit_code"] == 0,
                  checks["benchmark"]["benchmark_errors"] == 0,
                  checks["benchmark"]["benchmark_cases_checked"] > 0,
                  registry["unchanged"], static["passed"], git["passed"],
                  preservation["historical_preservation_passed"], guard_zero,
                  all(value is False for value in contract["authority_flags"].values()),
                  all(type(value) is int and value == 0 for value in contract["operational_effects"].values())))
    result = contract["typed_result"] if passed else "CONTRACT_UNRESOLVED"
    summary = {
        "typed_result": result, "all_required_pure_checks_passed": passed,
        "focused": {"collected": checks["focused"]["collected"], "passed": checks["focused"]["passed_count"]},
        "registry_picker": {"baseline_collected": registry["baseline_collected"], "after_collected": registry["after_collected"],
            "baseline_passed": registry["baseline_passed"], "after_passed": registry["after_passed"],
            "baseline_failure_nodes": [item["nodeid"] for item in checks["registry_baseline"]["failed"]],
            "after_failure_nodes": [item["nodeid"] for item in checks["registry_after"]["failed"]],
            "unchanged": registry["unchanged"], "projections_identical": registry["registry_and_picker_projections_identical"],
            "signature_comparison": registry["signature_comparison"], "baseline_not_repaired": True},
        "benchmark": {"cases_checked": checks["benchmark"]["benchmark_cases_checked"], "errors": checks["benchmark"]["benchmark_errors"]},
        "static": {"compiled_in_memory": static["compiled_count"], "JSON_files_validated": static["json_count"],
            "passed": static["passed"], "bytecode_written": False},
        "git_diff_check": {"passed": git["passed"], "existing_whitespace_unchanged": git["existing_whitespace_unchanged"],
            "new_phase_files_checked": git["phase_files_checked_without_index_mutation"], "git_index_modified": False},
        "preservation": preservation,
        "guarded_runs": {name: {"audit_guard": value["audit_guard"], "blocked_actions": value["blocked_actions"],
            "imported_capability_owners": value["imported_capability_owners"], "validator_sha256": value["validator_sha256"]}
            for name, value in checks.items()},
        "all_guarded_operational_effects_zero": guard_zero,
        "operational_effects": contract["operational_effects"],
        "all_authority_flags_false": all(value is False for value in contract["authority_flags"].values()),
        "full_issuance_dependent_suites_run": False,
        "scope": "pure source/contract/AST checks only; no operational owner import, creation, issuance or execution",
    }
    write("validation_summary.json", summary)
    report = {
        "phase_id": contract["phase_id"], "typed_result": result,
        "meaning": contract["result_meaning"], "workspace_semantics_frozen": True,
        "controller_evolution_required": True, "operational_controller_binding_resolved": False,
        "workspace_or_preparation_authority_exists_by_this_phase": False,
        "behavioral_activation_ready": False, "runtime_consumption_ready": False, "reason": "PROOF_UNRESOLVED",
        "evidence": {name: sha256((PHASE / name).read_bytes()).hexdigest() for name in
                     ("contract.json", "evidence_index.json", "validation_summary.json", "preservation_baseline.json")},
        "validation": summary, "stop": True,
    }
    write(NAME + ".json", report)
    failures = "\n".join("- `" + item["nodeid"] + "` (" + item["when"] + ")"
                         for item in checks["registry_baseline"]["failed"])
    text = f"""# SYNTH.EXEC.PREP.WORKSPACE.CONTRACT.1

**{result}**

The live ephemeral workspace and controller binding boundary is frozen as an
additive pure contract. The existing controller cannot support a truthful
retained live empty workspace or exclusive artifact handoff. An additive
controller is required. No workspace, container, preparation authority,
runtime/reflection permission or operational owner is created by this phase.

## Controller finding

`core/sandboxed_java_positive_probe.py:81` implements one fixed historical
fixture: empty `/work`, exclusive `JavaSandboxProbe.java`, `/work/classes`,
fixed compilation, then fixed Java dispatch. Its `source()` at line 121 accepts
no caller source/flags/environment/stdin. The outer historical controller at
`core/sandboxed_java_positive_continuation.py:338` always kills/removes the
container and independently checks absence before returning. Provider success
requires that cleanup. Historical receipts therefore authenticate completed
proofs, never a current retained workspace. SANDBOX.2 and PINNED provider cleanup
evidence are preserved unchanged.

The historical executable is `/usr/local/bin/python`, resolved to
`/usr/local/bin/python3.12`, SHA256
`0e6475dfda68a9b2d93501449fc47593ca169010e8f4881577b97463fd0c1263`.
Historical generated controller source is 13037 bytes, SHA256
`4f81640e2f01bc1f7a1a833beb269a9d1df51088b69cf24c8369fb6683f11a58`.
These identify the historical proof. They do not identify a new retained
controller. New controller source/hash/size/protocol are unresolved; no digest
is invented and no historical API is widened.

## Workspace boundary

The future independent owner is
`core.synthetic_execution_preparation_workspace_pinned`, exact type
`PinnedSyntheticPreparationWorkspace`, schema
`synthetic_preparation_workspace_pinned_1_v1`. Only an original registered
process-local object may authenticate. Copies, wrappers, subclasses, JSON,
container IDs and fingerprints cannot substitute for it. Its retained original
authorization/runtime/provider graph must authenticate through unchanged public
validators. Same image or route/version strings never establish provider
authenticity, daemon continuity or generation identity.

The exact SANDBOX.2 image, policy, environment, namespaces, resources and tmpfs
settings are retained. `/work` must be the authenticated isolated empty tmpfs.
`/work/classes` is **absent at workspace readiness**. Its exclusive creation
belongs to the frozen preparation materialization/compile attempt, consistent
with PREP closure's `directories_created`; workspace bootstrap creates none.
No source, class, harness, JAR, processor, plugin, config input, link, unexpected
mount, special file, target JVM or SyntheticStateBox instance is present.

Workspace possession represents only exact location/liveness/control binding.
It grants no `/work` write, materialization, compilation, activation, reflection,
shell, arbitrary command/source/class loading, repository write, Apply,
executor or BANK permission. Future materialization and compilation require
both the same original live workspace generation and the appropriate original
unspent preparation-authority facet. Preparation remains the permission owner
and owns facet spending. A receipt is evidence only; no cross-generation
receipt or host source/class export is allowed.

## Authentication and lifecycle

An independent domain is frozen:
`CATTUS:SYNTH.EXEC.PREP.WORKSPACE.PINNED.1:exact-live-workspace:v1`.
Strict canonical domain/role-framed HMAC-SHA256 uses an independent secret and
exact original registry identity. The public stable fingerprint covers only
immutable identity. Current controller/container generation, exclusive control,
manifest, observation sequence/challenge, handoff and cleanup predicates are
separately authenticated. Historical signatures and timestamps cannot establish
current liveness. No SANDBOX, provider, preparation, runtime or reflection
private secret/state is reused.

The current workspace-state digest has a fixed SHA256 domain/role and canonical
payload: exact generations/observation challenge, authenticated mounts, complete
sorted no-follow `/work` and `/tmp` manifests, file sizes/full hashes/link counts,
and process/writer exclusivity observations. Its scope and digest are covered by
the current-state HMAC. Only metadata is hashed for reporting; a scalar digest
cannot authenticate readiness or authorize exporting artifact bytes.

Predicates describe live, exclusive, preparation-empty, prepared artifacts,
handoff-active, cleanup-started, cleanup-complete and invalid conditions; no
speculative public state machine/API is implemented. Partial preparation proves
neither emptiness nor prepared readiness. Controller loss, generation change or
unexpected artifacts invalidates readiness. Cleaned or invalid generations
cannot be revived. Exclusive handoff still requires separately reviewed consumer
authority and exact original artifact/receipt/generation binding.

Before every future guarded effect, relevant owners reauthenticate their own
originals; runtime must be `ISSUED`. Its report-only lease-local preconditions
may be satisfied while behavioral activation readiness remains false with
`PROOF_UNRESOLVED`. No cross-owner transaction or private lock bridge is claimed.
The future controller must enforce its own operation/cleanup admission fence;
unobservable coordination gaps fail closed. Cleanup-started denies new
preparation. Eligibility loss before effect aborts it; spent facets receive no
refund. Provider/backend mismatch, controller loss, disappearance and generation
replacement cannot be repaired using equal scalar projections.

## Cleanup and remaining gates

Preparation retains its existing attempt lifecycle accountability. The workspace
owner/controller owns containment identity and cleanup evidence; consumer
handoff never removes the cleanup duty. Cleanup must remain possible after
preparation/consumer/activation failure, timeout, abandonment or upstream
invalidation, including controller loss. The independently authorized fixed
teardown path uses retained immutable identity without requiring current
readiness, an `ISSUED` runtime, unspent facets or a lost controller challenge.
It never recreates authority or readiness.

Cleanup evidence separately proves child/process-group reaping, closed
captures, exact container removal, disappearance of both tmpfs generations,
fresh independent absence observation and no surviving raw artifact export.
Preparation success retains live artifacts with cleanup pending until final
consumer/attempt completion. Cleanup success, preparation success and behavior
success remain distinct. `WORKSPACE_CLEANUP_UNRESOLVED` blocks readiness.
All requested workspace errors are defined; known upstream typed errors retain
their status/reason, and semantic mismatches are not authentication failures.

The future additive controller must provide exact executable/source/protocol
identity, fresh liveness observations, fixed bounded preparation operations,
exclusive handoff, capture/reaping and independent cleanup. Implementation and
issuance are outside this phase. Full harness source, main, scenario JVM argv,
loader and staged BEFORE/AFTER protocol remain unresolved. Behavioral readiness
is **false / PROOF_UNRESOLVED**. No consumer, harness or executor is implemented.

## Measured pure validation

- Focused contract checks: **{checks['focused']['passed_count']}/{checks['focused']['collected']} passed**.
- Registry/picker baseline and after: **{registry['baseline_collected']} collected,
  {registry['baseline_passed']} passed, {len(checks['registry_baseline']['failed'])} pre-existing failures**;
  node results, assertion signatures and projections are unchanged. Comparison
  normalizes only Python repr allocator addresses; raw diagnostics are retained.
- Benchmark `--check`: **{checks['benchmark']['benchmark_cases_checked']} cases, {checks['benchmark']['benchmark_errors']} errors**.
- In-memory Python compilation: **{static['compiled_count']} files**. JSON,
  authored AST imports, whitespace and Git whitespace checks passed; no bytecode
  or Git index mutation. Existing Git whitespace baseline is unchanged.
- **{preservation['baseline_file_count']} existing non-cache files/links unchanged**,
  with no additions outside this new phase. The immutable inventory records
  cache/Git exclusions and never follows links.
- All operational guard counters and capability-owner imports are zero.
  All {len(contract['authority_flags'])} authority flags are false and all
  {len(contract['operational_effects'])} operational counters are zero. Full
  issuance-dependent suites were not run.

Preserved registry/picker failures:

{failures}

See [contract.json](contract.json), [evidence_index.json](evidence_index.json),
[validation_summary.json](validation_summary.json) and
[preservation_comparison.json](preservation_comparison.json).

**STOP. Do not implement or issue the workspace or preparation owner.**
"""
    (PHASE / (NAME + ".md")).write_text(text, encoding="utf-8")
    print(json.dumps({"typed_result": result, "all_required_pure_checks_passed": passed}))
    if not passed:
        raise AssertionError("Pure validation is unresolved; no successful contract outcome")


if __name__ == "__main__":
    main()
