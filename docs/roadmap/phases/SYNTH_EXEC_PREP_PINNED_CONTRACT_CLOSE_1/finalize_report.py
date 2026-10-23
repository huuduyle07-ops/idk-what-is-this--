"""Aggregate measured pure closure evidence. Never create runtime authority."""
from hashlib import sha256
import json
from pathlib import Path

PHASE = Path(__file__).resolve().parent
STEM = "SYNTH_EXEC_PREP_PINNED_CONTRACT_CLOSE_1_REPORT"


def read(name):
    return json.loads((PHASE / name).read_text(encoding="utf-8"))


def write(name, value):
    (PHASE / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main():
    contract = read("contract.json")
    evidence = {name: read(name + ".json") for name in (
        "focused", "registry_baseline", "registry_after", "benchmark")}
    comparison = read("registry_comparison.json")
    preservation = read("preservation_comparison.json")
    static = read("static_validation.json")
    git = read("git_diff_check.json")
    validator_hash = sha256((PHASE / "validate_pure.py").read_bytes()).hexdigest()
    focused_passed = len(set(evidence["focused"]["passed_nodes"]))
    checks = {
        "focused_closure_tests_passed": evidence["focused"]["exit_code"] == 0
            and evidence["focused"]["collected"] > 0
            and focused_passed == evidence["focused"]["collected"]
            and not evidence["focused"]["failed"] and not evidence["focused"]["skipped"],
        "benchmark_check_passed": evidence["benchmark"]["exit_code"] == 0
            and evidence["benchmark"]["benchmark_cases_checked"] > 0
            and evidence["benchmark"]["benchmark_errors"] == 0,
        "registry_picker_baseline_unchanged": comparison["unchanged"]
            and comparison["registry_and_picker_projections_identical"]
            and comparison["existing_failures_preserved"],
        "registry_exit_codes_explained_by_existing_test_failures": all(
            evidence[name]["collected"] > 0
            and evidence[name]["exit_code"] == (1 if evidence[name]["failed"] else 0)
            and all(row["when"] == "call" for row in evidence[name]["failed"])
            for name in ("registry_baseline", "registry_after")),
        "historical_preservation_passed": preservation["historical_preservation_passed"],
        "in_memory_compilation_JSON_whitespace_passed": static["passed"],
        "git_diff_check_passed": git["exit_code"] == 0,
        "operational_guards_zero": all(
            row["all_operational_effects_zero"] and row["audit_guard"]
            and all(type(value) is int and value == 0 for value in row["audit_guard"].values())
            and not row["blocked_actions"] and not row["imported_capability_owners"]
            for row in evidence.values()),
        "evidence_uses_current_validator": all(
            row["validator_sha256"] == validator_hash for row in evidence.values()),
        "all_six_proposals_accepted": len(contract["proposal_review"]) == 6 and all(
            row["decision"] in {"ACCEPTED_UNCHANGED", "ACCEPTED_WITH_ADDITIVE_CLARIFICATION"}
            for row in contract["proposal_review"]),
        "source_does_not_contradict_preparation": contract["first_behavioral_effect"][
            "source_evidence_contradicts_compilation_classification"] is False,
        "no_authority_or_operations": all(value is False for value in contract["authority_flags"].values())
            and all(type(value) is int and value == 0 for value in contract["operational_effects"].values()),
        "harness_and_consumer_stay_unresolved": contract["harness_contract_complete"] is False
            and all(contract["harness_boundary"]["full_harness"][key] is None
                for key in contract["harness_boundary"]["full_harness"]["unresolved_fields"])
            and contract["consumer_readiness"]["final_owner_frozen"] is False
            and contract["consumer_readiness"]["runtime_consumption"] == "PROOF_UNRESOLVED",
        "implementation_not_authorized": contract["implementation_authorized"] is False
            and contract["owners_implemented"] is False and contract["capabilities_issued"] is False,
    }
    passed = all(checks.values())
    evolution = any(row["decision"] in {"REQUIRES_NEW_REQUIREMENT", "REJECTED"}
        for row in contract["proposal_review"])
    outcome = contract["completion_rule"]["success" if passed else "further_evolution" if evolution else "unresolved"]
    summary = {
        "phase_id": contract["phase_id"], "typed_result": outcome,
        "validation_passed": passed, "checks": checks,
        "focused": {"collected": evidence["focused"]["collected"], "passed": focused_passed,
            "failed": evidence["focused"]["failed"], "skipped": evidence["focused"]["skipped"]},
        "registry_picker": comparison,
        "benchmark": {key: evidence["benchmark"][key] for key in (
            "exit_code", "benchmark_cases_checked", "benchmark_errors")},
        "static": {key: static[key] for key in ("compiled_count", "json_count", "errors", "whitespace_errors", "passed")},
        "historical_preservation": preservation, "git_diff_check": git,
        "audit_guards": {name: value["audit_guard"] for name, value in evidence.items()},
        "all_actual_operational_effects_zero": checks["operational_guards_zero"],
        "operational_owner_modules_imported": [], "full_issuance_dependent_suites_run": False,
        "writes_scope": "new additive closure phase documentation, pure tests, validation evidence and scratch only",
        "baseline_failure_policy": "Disclose and preserve identical existing failed nodes and registry/picker projections; never repair prior files in this phase.",
    }
    write("validation_summary.json", summary)
    report = {
        "phase_id": contract["phase_id"], "typed_result": outcome,
        "meaning": contract["closure_scope"]["meaning"] if passed else "Closure withheld; inspect failed validation checks. Zero operational authority.",
        "decision_frozen": passed,
        "proposal_review": contract["proposal_review"],
        "preparation_contract_complete": passed,
        "harness_contract_complete": False,
        "runtime_consumption": "PROOF_UNRESOLVED",
        "behavioral_activation_ready": False,
        "implementation_authorized": False,
        "authority_flags": contract["authority_flags"],
        "operational_effects": contract["operational_effects"],
        "validation": summary,
        "stop": True,
        "artifact_sha256": {name: sha256((PHASE / name).read_bytes()).hexdigest() for name in (
            "contract.json", "evidence_index.json", "write_contract.py", "test_contract.py", "validate_pure.py",
            "finalize_report.py", "preservation_baseline.json", "preservation_after.json", "focused.json",
            "registry_baseline.json", "registry_after.json", "registry_comparison.json", "benchmark.json",
            "preservation_comparison.json", "static_validation.json", "git_diff_check.json", "validation_summary.json")},
    }
    write(STEM + ".json", report)
    rows = "\n".join(f"| {row['item']}. `{row['proposal']}` | `{row['classification']}` | `{row['decision']}` |"
        for row in contract["proposal_review"])
    failures = "\n".join("- `" + row["nodeid"] + "` (" + row["when"] + ")"
        for row in comparison["baseline_failed"]) or "None."
    markdown = f"""# SYNTH.EXEC.PREP.PINNED.CONTRACT.CLOSE.1

**{outcome}**

The prior preparation proposals have been reviewed against the revised activation
boundary and are now frozen preparation semantics. No owner, authority or
operational effect exists. This closure is additive; the prior PREP outcome
`PREPARATION_REQUIRES_REQUIREMENT_EVOLUTION` remains unchanged in history.
`SYNTH.EXEC.ACTIVATION.BOUNDARY.REQ.1` already resolved its named first-effect
conflict for this exact scenario. No additional historical claim is superseded.

| Prior proposal | Effect/constraint | Closure classification |
| --- | --- | --- |
{rows}

Items 3 and 4 add scope clarification: the compiler's infrastructure JVM is
distinct from dispatch of the exact scenario-executing JVM. The latter boundary
is now an adopted requirement. No compiler arguments, source bytes, workspace
controls, preparation limits or runtime/reflection permissions are widened.

The exact scenario is `synthetic.EXECUTOR.1R.decrement_3`: existing 239-byte source
SHA256 `813a17fd33e9c3d5a9bdc5bb6f8158e97ad7b021c3a0d2915ef68e45b0f09302`,
definition SHA256 `e9466adfd5ab3e881b96deab9ac5bdac6907da17a9014f457bb20d7fdc2a941d`,
`SyntheticStateBox`, `boolean SyntheticStateBox.decrement(int)`, argument `3`,
field `SyntheticStateBox.value:int`. Source/AST inspection authenticates the
existing literal only. The instance initializer `value = 10` occurs on ordinary
construction before observation. Source evidence contains one class and no
imports, annotations, explicit constructor or static initialization. There is no
source contradiction with the closed inert compilation contract.

Materialization retains the exact exclusive ephemeral `/work` tmpfs and binary
exclusive creation at `/work/SyntheticStateBox.java`: no overwrite, shared writer,
symlink, hardlink, special file, traversal or unexpected mount crossing; full
239-byte readback. No host repository mutation or persistent source/class export
is permitted. The original path and workspace controls are retained verbatim.

Compilation retains `/opt/temurin-26.0.2.1/bin/javac`, SHA256
`e21c219e342544cbf107d25e86ed1d809eac6cc57bce8f68750a42783f13e023`, image
`sha256:f6d7dc31a15bb37a618ebed6772beda3de95fdcc3394eb5a1def9b1d20673f7a`,
`runtime_sandbox_2_v1` and policy SHA256
`5a36bdf1676c4b0d7b4bef489f5e90b5c8fb201b5194be48baf61f4206a81f75`.
Exact argv:

```json
{json.dumps(contract['compiler']['exact_scenario_argv'], indent=2)}
```

`shell=false`, `cwd=/work`; exact eight-variable environment only, one attempt,
no Maven/Gradle, network, arbitrary classpath, caller flags, argument files,
processors, plugins or dependency inputs. Compilation may only transform the
exact source into inert bytes; no target loading, initialization, construction
or invocation. Any contradictory source evidence stops closure.

Output remains exactly `/work/classes/SyntheticStateBox.class`, one class file
of 1..32768 bytes, no extra outputs, unchanged source, full no-follow workspace
manifest, actual class-byte hashing and bounded inert class metadata inspection.
Never load the class for validation. No predicted class hash or successful
compilation is claimed. Full capture, resource, timeout and reaping bounds remain
the prior contract's acceptance conditions.

The future narrow owner `core.synthetic_execution_preparation_pinned`, type
`PinnedSyntheticPreparationAuthority`, schema
`synthetic_preparation_authority_pinned_1_v1` retains two non-interchangeable
facets: `exact_sandbox_materialization_authority` and
`exact_scenario_compilation_authority`. Each has one attempt, reserved immediately
before its effect; failure spends it, with no refund or reissue. Both bind exact
original runtime/auth/workspace generation and controller/provider graph.
Compilation requires verified materialization. No generic file/command API or
sandbox issuance is defined. This phase implements or issues none of them.

`PinnedSyntheticPreparationReceipt`, schema
`synthetic_preparation_receipt_pinned_1_v1`, remains authenticated evidence with
false runtime and execution permission. It may prove only exact source
authentication, materialization/readback, compiler identity, exact
argv/environment, compile result, bounded output manifest, live workspace
generation and cleanup pending. Its original graph/signature/context bindings
authenticate those claims; they add no harness, consumer or behavior claim.
It cannot alone unlock runtime consumption.

**Preparation contract complete != harness contract complete.** Full harness
source/hash/size, main class, scenario JVM argv, loader/controller source and
staged permission protocol remain null/unresolved. Existing reflection helper
hashes are insufficient. Consumer review is dependency shape only: the receipt
may later be one input. No final consumer owner, schema, API, authentication
domain or runtime-lock integration is frozen or implemented. Runtime consumption
remains **PROOF_UNRESOLVED** until full harness and consumer evidence are
separately reviewed; the existing unconditional owner gate is unchanged.

The revised sequence is:

1. Authenticate all gates; prepare BEFORE/AFTER admissions and leases while runtime is ISSUED.
2. Authenticate/project exact source, exclusively materialize/read back, compile, and authenticate bounded preparation evidence.
3. Authenticate separately reviewed full harness and consumer readiness and complete live integrity/handoff checks.
4. Consume runtime lease, then consume BEFORE reflection permission.
5. Dispatch exact scenario JVM; only then target loading/linking/initialization/construction, BEFORE read and exact decrement(3).
6. Consume AFTER permission before AFTER read; finish/abort and independently verify cleanup.

No preparation occurs after runtime consumption; only mandatory authenticated
permission checks/commits may precede dispatch. No launch before both runtime
and BEFORE commits, and no refund after runtime consumption, including launch
failure. Required teardown/reaping/absence verification are cleanup duties and
do not authorize a new preparation attempt. Permission consumption proves no
observed effect.

Measured validation: **{focused_passed} focused closure tests passed**;
registry/picker baseline and after each collected {comparison['baseline_collected']}
tests, with {comparison['baseline_passed']} passing and
{len(comparison['baseline_failed'])} identical existing failures. Exact node results
and registry/picker projections are unchanged. Benchmark `--check`: **{evidence['benchmark']['benchmark_cases_checked']}
cases, zero errors**. In-memory Python compilation: **{static['compiled_count']}
files**. JSON/whitespace and `git diff --check` passed.
**{preservation['baseline_file_count']} pre-existing non-cache files/links are
unchanged**, with no additions outside this phase. Snapshot records exclusions
and never follows links. All operational guard counters and capability-owner
imports are zero. No full issuance-dependent suite was run.

Existing registry/picker failures, preserved exactly:

{failures}

All {len(contract['authority_flags'])} authority flags are false; all
{len(contract['operational_effects'])} operational effect counters are zero.
No owner implementation, capability issuance/consumption, source/class
materialization, javac/java/Docker invocation or runtime/reflection modification
occurred. Only additive documentation and pure validation support were written.

See [contract.json](contract.json), [evidence_index.json](evidence_index.json),
[validation_summary.json](validation_summary.json) and
[preservation_comparison.json](preservation_comparison.json).

**STOP after closure. No preparation owner implementation is authorized.**
"""
    if not passed:
        markdown = f"# {outcome}\n\nClosure withheld. See validation_summary.json. No operational authority. STOP.\n"
    (PHASE / (STEM + ".md")).write_text(markdown, encoding="utf-8")
    print(json.dumps({"typed_result": outcome, "checks": checks, "passed": passed}, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
