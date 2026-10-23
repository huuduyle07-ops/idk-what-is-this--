"""Aggregate pure evidence; grant no operational authority or implementation."""
from hashlib import sha256
import json
from pathlib import Path

PHASE = Path(__file__).resolve().parent
STEM = "SYNTH_EXEC_ACTIVATION_BOUNDARY_REQ_1_REPORT"


def read(name):
    return json.loads((PHASE / name).read_text(encoding="utf-8"))


def write(name, value):
    (PHASE / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main():
    requirement = read("requirement.json")
    evidence_names = ("focused", "registry_baseline", "registry_after", "benchmark")
    evidence = {name: read(name + ".json") for name in evidence_names}
    comparison = read("registry_comparison.json")
    preservation = read("preservation_comparison.json")
    static = read("static_validation.json")
    git = read("git_diff_check.json")
    validator_hash = sha256((PHASE / "validate_pure.py").read_bytes()).hexdigest()
    guards = {
        name: row["audit_guard"] for name, row in evidence.items()
    }
    focused_passed = len(set(evidence["focused"]["passed_nodes"]))
    checks = {
        "focused_passed": evidence["focused"]["exit_code"] == 0
            and evidence["focused"]["collected"] > 0
            and focused_passed == evidence["focused"]["collected"]
            and not evidence["focused"]["failed"] and not evidence["focused"]["skipped"],
        "benchmark_check_passed": evidence["benchmark"]["exit_code"] == 0
            and evidence["benchmark"]["benchmark_cases_checked"] > 0
            and evidence["benchmark"]["benchmark_errors"] == 0,
        "registry_picker_unchanged": comparison["unchanged"]
            and comparison["registry_and_picker_projections_identical"]
            and comparison["existing_failures_preserved"],
        "registry_pytest_exit_codes_explained_by_node_failures": all(
            evidence[name]["collected"] > 0
            and evidence[name]["exit_code"] == (1 if evidence[name]["failed"] else 0)
            and all(row["when"] == "call" for row in evidence[name]["failed"])
            for name in ("registry_baseline", "registry_after")),
        "historical_preservation_passed": preservation["historical_preservation_passed"],
        "in_memory_compilation_JSON_whitespace_passed": static["passed"],
        "git_diff_check_passed": git["exit_code"] == 0,
        "all_operational_guard_counters_zero": all(
            row["all_operational_effects_zero"] and row["audit_guard"]
            and all(type(value) is int and value == 0 for value in row["audit_guard"].values())
            and not row["blocked_actions"] and not row["imported_capability_owners"]
            for row in evidence.values()),
        "all_evidence_uses_current_validator": all(
            row["validator_sha256"] == validator_hash for row in evidence.values()),
        "one_exact_scoped_supersession": len(requirement["supersessions"]) == 1,
        "all_new_authority_flags_false": all(
            value is False for value in requirement["authority_flags"].values()),
        "all_operational_effects_exact_zero": all(
            type(value) is int and value == 0 for value in requirement["operational_effects"].values()),
        "compatibility_requires_no_changes": all(
            value is False for value in requirement["compatibility_review"]["requires_change"].values()),
        "behavioral_readiness_still_unresolved": requirement["behavioral_activation_ready"] is False
            and requirement["reason"] == "PROOF_UNRESOLVED",
        "full_harness_unresolved": all(requirement["full_harness"][key] is None
            for key in requirement["full_harness"]["unresolved_fields"]),
        "PREP_proposals_remain_non_operational": requirement["preparation_relationship"][
            "automatically_become_operational_requirements"] is False
            and requirement["preparation_relationship"]["closure_review_required"] is True,
    }
    passed = all(checks.values())
    outcome = requirement["completion_rule"]["success" if passed else "unresolved"]
    summary = {
        "requirement_id": requirement["requirement_id"], "typed_result": outcome,
        "validation_passed": passed, "checks": checks,
        "focused": {
            "collected": evidence["focused"]["collected"], "passed_count": focused_passed,
            "passed_report_count_including_subtests": evidence["focused"]["passed_count"],
            "failed": evidence["focused"]["failed"], "skipped": evidence["focused"]["skipped"],
            "counting_method": "unique passed node IDs; raw report count also includes unittest subtests",
        },
        "registry_picker": comparison,
        "benchmark": {key: evidence["benchmark"][key] for key in ("exit_code", "benchmark_cases_checked", "benchmark_errors")},
        "static": {key: static[key] for key in ("compiled_count", "json_count", "errors", "whitespace_errors", "passed")},
        "git_diff_check": git, "historical_preservation": preservation,
        "audit_guards": guards, "all_actual_operational_effects_zero": checks["all_operational_guard_counters_zero"],
        "operational_owner_modules_imported": [], "full_issuance_dependent_suites_run": False,
        "writes_scope": "new additive requirement phase documentation, tests, evidence and validation scratch only",
        "registry_baseline_failure_policy": "Exact existing failed nodes, passed/skipped nodes and registry/picker projections must match. Existing failures are disclosed and never repaired by this phase.",
        "host_tooling_scope": "Python pure validation and git diff --check only; no scenario/runtime shell authority",
    }
    write("validation_summary.json", summary)
    baseline = read("preservation_baseline.json")
    supersession = requirement["supersessions"][0]
    old_path = supersession["superseded_historical_artifact_path"]
    report = {
        "requirement_id": requirement["requirement_id"], "typed_result": outcome,
        "meaning": requirement["completion_rule"]["meaning"] if passed else "Fail closed: pure requirement evolution validation is unresolved.",
        "decision_frozen": requirement["decision_frozen"],
        "supersession": supersession,
        "historical_contract_identity": {"path": old_path, **baseline["files"][old_path]},
        "behavioral_activation_ready": False, "reason": "PROOF_UNRESOLVED",
        "implementation_authorized": False,
        "authority_flags": requirement["authority_flags"],
        "operational_effects": requirement["operational_effects"],
        "validation": summary,
        "compatibility_evidence": "compatibility_review.json",
        "historical_owner_authorities": "Existing narrow permission matrices are preserved byte-for-byte. All false flags in this artifact describe authority newly granted by this requirement phase; no historical narrow permission is removed or widened.",
        "next_step": requirement["preparation_relationship"]["next_review"],
        "stop": True,
        "artifact_sha256": {name: sha256((PHASE / name).read_bytes()).hexdigest() for name in (
            "requirement.json", "test_requirement.py", "validate_pure.py", "finalize_report.py",
            "compatibility_review.json", "preservation_baseline.json", "preservation_after.json",
            "focused.json", "registry_baseline.json", "registry_after.json", "benchmark.json",
            "static_validation.json", "git_diff_check.json", "registry_comparison.json",
            "preservation_comparison.json", "validation_summary.json")},
    }
    write(STEM + ".json", report)
    failures = "\n".join("- `" + row["nodeid"] + "` (" + row["when"] + ")"
        for row in comparison["baseline_failed"]) or "None."
    markdown = f"""# SYNTH.EXEC.ACTIVATION.BOUNDARY.REQ.1

**{outcome}**

This additive requirement evolves exactly the historical
`first_behavior_boundary.first_behavioral_effect = BEFORE exact read` assertion
for `synthetic.EXECUTOR.1R.decrement_3`. The old contract and every pre-existing
file within the preservation scope retain their bytes. The historical assertion
remains a frozen historical requirement, superseded by measured semantic
evidence for this execution epoch. No history is repinned or retroactively
mutated, and no other historical claim is superseded.

The exact source literal in `core/synthetic_runtime_authorization.py` contains
`private int value = 10;`. Ordinary construction initializes mutable scenario
state before a BEFORE read can observe it. The first **known source-level**
mutable-state effect is ordinary construction initializing `value = 10`.
The full harness is unresolved; no earlier exact harness instruction is invented
and construction is not asserted to be its first executable effect.

The conservative activation boundary is **dispatch of the exact scenario-executing
JVM**, after all preparation evidence, full harness readiness, consumer readiness,
runtime consumption and BEFORE permission consumption. This classification is
scoped to the exact scenario consumer and makes no universal assertion about JVM
launches. Target loading/linking and initialization are behavioral activation
effects; ordinary construction and the BEFORE exact reflection read are
behavioral effects.

The revised normative order is:

1. All capability/authentication gates.
2. Source/harness preparation complete, with all preparation, full harness and consumer readiness evidence.
3. Runtime lease `ISSUED -> CONSUMED`.
4. BEFORE reflection lease `ISSUED -> CONSUMED`.
5. Dispatch exact scenario JVM.
6. Load/link/initialize exact target as required by the reviewed harness.
7. Ordinary exact `SyntheticStateBox` construction.
8. BEFORE exact reflection read.
9. Exact public `decrement(3)`.
10. AFTER reflection lease consumption.
11. AFTER exact reflection read.
12. Cleanup.

Only mandatory authenticated permission checks/commits may intervene between
runtime consumption and dispatch. No preparation may occur after runtime
consumption. Launch failure or any later failure does not refund consumption.
Permission consumption remains distinct from evidence of an observed effect.

Compatibility is semantic requirement placement only. Static evidence in
[compatibility_review.json](compatibility_review.json) confirms no changes to
`PinnedSyntheticRuntimeExecutionLease`,
`PinnedSyntheticReflectionExecutionAdmission`,
`PinnedSyntheticReflectionExecutionLease`, their state machines, one-shot
semantics, permanent terminal tombstones, public validators, HMAC domains,
activation policy identities/digests or authority matrices. Existing historical
narrow permissions remain intact; this phase grants none anew. Future owner and
lock integration is not preapproved.

Full executable harness source bytes/hash/size, main class, scenario JVM argv,
loader/controller implementation and staged BEFORE/AFTER protocol remain
**unresolved**. Behavioral activation readiness remains **false** with
`PROOF_UNRESOLVED`. This requirement authorizes no launch or implementation.

PREP's in-memory exact source projection (`PURE_DERIVATION`), sandbox exact source
materialization (`PREPARATION_EFFECT`) and bounded javac scenario compilation
(`PREPARATION_EFFECT`) remain non-operational proposals. This evolution does not
automatically adopt PREP materialization/compile/readiness requirements or grant
preparation authority. A separate small preparation-contract closure review must
confirm their compatibility with the new boundary before any implementation.

All **{len(requirement['authority_flags'])} new authority flags are false**.
All **{len(requirement['operational_effects'])} operational effect counters are zero**.
No preparation owner, receipt, consumer owner, runtime integration, harness or
executor was implemented. No source/class was materialized; no operational
owner was imported, capability issued/consumed, or Java/Docker scenario run.
Writes consist only of this additive requirement and its pure validation support.

Measured validation: **{focused_passed} focused pure tests passed**;
registry/picker baseline and after each collected {comparison['baseline_collected']}
tests, with {comparison['baseline_passed']} passing and
{len(comparison['baseline_failed'])} existing failures; exact node results and
registry/picker projections are identical. Benchmark `--check` checked
**{evidence['benchmark']['benchmark_cases_checked']} cases with zero errors**.
In-memory Python compilation covered **{static['compiled_count']} files**;
JSON/whitespace checks and `git diff --check` passed.
**{preservation['baseline_file_count']} pre-existing non-cache workspace files/links
are unchanged**, with no additions outside this new phase. Preservation excludes
only the recorded cache/runtime directories, Git metadata and this new phase;
links are recorded without traversal. All guarded operational attempt counters
and owner imports are zero. Full issuance-dependent suites were not run.

Existing registry/picker failures, preserved exactly:

{failures}

See [requirement.json](requirement.json) for exact supersession metadata,
[validation_summary.json](validation_summary.json) for measured checks, and
[preservation_comparison.json](preservation_comparison.json) for preservation.

**STOP.** The next phase is the separate preparation-contract closure review.
Do not implement preparation, harness, consumer or runtime integration here.
"""
    if not passed:
        markdown = "# REQUIREMENT_EVOLUTION_UNRESOLVED\n\nFail closed. See validation_summary.json for failed checks. No operational authority is granted. STOP.\n"
    (PHASE / (STEM + ".md")).write_text(markdown, encoding="utf-8")
    print(json.dumps({"typed_result": outcome, "checks": checks, "passed": passed}, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
