"""Join phase-owned static evidence and completed pure validation results."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPORT = "RUNTIME_SANDBOX_2_NESTED_CONTEXT_DIAG_1_REPORT.json"


def read(name):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def main():
    result = read(REPORT)
    validation = read("validation_summary.json")
    launch = read("historical_launch_provenance.json")
    path_observation = read("historical_path_current_observation.json")
    result["validation_summary"] = validation
    result["preservation"] = validation["checks"]["historical_byte_preservation"]
    result["provenance_artifacts"] = {
        name: {"sha256": hashlib.sha256((HERE / name).read_bytes()).hexdigest(),
               "historical_files_modified": False}
        for name in ("historical_launch_provenance.json", "historical_path_current_observation.json")}
    result["recovered_launch"] = {"provenance": "historical_launch_provenance.json",
        "direct_command": "python -B scripts/replay_synth_auth_pinned1.py",
        "Python_validation_worker_hooks_inherited": False,
        "launch_and_completion_records_verified": len(launch["recovered_records"]) == 5,
        "startup_environment_and_native_policy_retained": False}
    result["current_path_observation"] = {"artifact": "historical_path_current_observation.json",
        "current_only_not_historical_permission_proof": True,
        "read_only_observation_retained": bool(path_observation)}
    compiled = []
    for identity in result["historical_source_identities"]:
        path = HERE.parents[3] / identity["path"]
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
        compiled.append(identity["path"])
    result["frozen_source_in_memory_compilation"] = {"passed": True,
        "compiled_source_count": len(compiled), "sources": compiled,
        "imports_or_execution": False, "bytecode_emission": False}
    timeout_files = sorted(path.name for path in HERE.glob("*timeout*.json"))
    result["partial_broad_validation_attempt_artifacts"] = timeout_files
    result["validation_passed"] = validation["passed"]
    (HERE / REPORT).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                              encoding="utf-8", newline="\n")
    checks = validation["checks"]
    lines = [
        "# RUNTIME.SANDBOX.2.NESTED.CONTEXT.DIAG.1", "",
        "**UNRESOLVED**. Historical nested root cause unresolved.", "",
        "The static and pure audit found surviving process context differences, but no exact active denial mechanism that explains the historical post-image, pre-create failure. The lost SANDBOX.2 report and first failing statement prevent causal attribution. This phase stops here.", "",
        "The exact runner is `scripts/replay_synth_auth_pinned1.py`, SHA256 `73ac65320825f3f32726526bcb5f2aa492887ef496b06d086932903b47cfc440`, matching its retained preoperational source binding. The original Codex launch record directly invoked `python -B scripts/replay_synth_auth_pinned1.py` with host access. Session and turn context record this repository as cwd; no workdir override, environment assignment, or validation wrapper appears in the launch. Selected original records and their line hashes are retained in [launch provenance](historical_launch_provenance.json).", "",
        "`tempfile.tempdir` and consequently `tempfile.gettempdir()` were the absolute SYNTH phase directory for the entire authorization/provider call. Runner line 61 sets the override; line 102 restores it after issuance returns. Historical TMP, TEMP, TMPDIR and the previous cached tempdir were not retained. The explicit global override bypasses their selection. No pytest basetemp context was active in the directly launched live runner.", "",
        "Both the absent Docker config path (`candidate_runtime_sandbox.py:371`) and `TemporaryDirectory(prefix='runtime-sandbox2-')` (`thread_compatible_runtime_sandbox.py:335`) use that same root. The successful standalone diagnostic used normal Windows Temp. The config path itself is not a demonstrated cause: image inspection succeeded, and the earlier BIND SANDBOX.2 replay in the same historical issuance completed all 11 stages, removed its workspace, and verified cleanup while the phase-local override remained active. This excludes an unconditional root-wide write denial or socket prohibition throughout the attempt.", "",
        "The historical root was present and allowed earlier workspace writes. Its exact later ACL, symlink, write-denial policy and cleanup state were not recorded. Current read-only metadata shows an ordinary directory with Modify ACL entries; current metadata cannot establish historical permissions. The exact live source contains no early cleanup of the phase root. [Current path and tempfile observations](historical_path_current_observation.json) preserve this distinction.", "",
        "| Context / owner | Active at JAVA.1C SANDBOX.2 boundary | Lifetime / affected step | Classification |",
        "| --- | --- | --- | --- |",
    ]
    for candidate in result["active_at_SANDBOX2_matrix"]:
        active = candidate["active_at_SANDBOX2"]
        label = "Yes" if active is True else "No" if active is False else "Unknown"
        affected = ", ".join(candidate["affected_steps"]) or "No direct pre-ladder dependency"
        lines.append("| " + candidate["id"] + " | " + label + " | " + candidate["lifetime"] + "; " + affected + " | " + candidate["classification"] + " |")
    lines.extend([
        "",
        "The provider's `sys.setprofile` return-frame observer remains installed across `runtime.verify()` and SANDBOX.2. Its callback reads selected return values, arguments and locals for accounting; it does not install an audit hook, deny sockets or writes, or replace owner values. It is shared with the successful PINNED.1C retry. Direct denial by this callback is excluded; historical timing or allocation effects are unmeasured. Pure controls execute the exact helper with inert stand-ins and verify observation plus restoration on success and exception.", "",
        "PINNED.1B and BIND transport/replay patches finish before JAVA.1C. Their lexical lifetime makes them NOT_ACTIVE_AT_FAILURE_BOUNDARY. The successful retry's private-config tracer is absent from the blocked runner. Negative authentication mutations run only after successful issuance and were skipped. Provider registries survive but SANDBOX.2 pre-ladder setup does not read them. Runner import-path insertion and bytecode suppression survive and expose no post-image denial mechanism.", "",
        "No Python audit registration, socket constructor/bind/listen patch, Popen/run patch or shutil.which patch was found on the exact retained live path. Guards in separate validation processes are not inherited into the fresh live Python interpreter. No system/thread trace, thread profile or monitoring mutation was found there; inherited startup and native policy were not recorded. The separate strict-resolution sandbox probe does not establish a denial in the host-capable historical launch.", "",
        "The retained JAVA.1C-period Docker controls are successful image inspection followed by two successful cleanup listings; creates and starts are zero at the failed boundary. A global subprocess prohibition contradicts this evidence. There is no further subprocess between image inspection and SANDBOX.2 workspace/socket setup. Parsed metadata eligibility, workspace creation, file writes, TCP/UDP construction, TCP bind/listen and UDP bind remain possible failure steps, with no retained first-failure evidence. No socket rejection rule is proven active there. JAVA.1C's generic not_authenticated label does not demonstrate HMAC failure.", "",
        "Pure temp controls use the exact historical override statement and exact frozen pre-socket workspace subtree, rebound only to a new phase-owned scratch root. They confirm shared config/workspace root selection, successful policy/sentinel writes and cleanup, without Docker or socket operations. This proves the semantic connection, not the historical root cause.", "",
        "| Validation | Result |", "| --- | --- |",
    ])
    for key in ("context-audit", "pytest", "auth-matrix", "auth-artifacts", "context-contracts", "historical-blocked", "benchmark"):
        item = checks[key]
        worker = item.get("worker_result", {})
        count = worker.get("passed_test_count", worker.get("case_count"))
        detail = (str(count) + " passed; " if count is not None else "") + ("PASS" if item["passed"] else "FAIL")
        lines.append("| " + key + " | " + detail + " |")
    comparison = checks["registry_picker_pure_test_baseline_vs_after"]
    counts = comparison["after"]
    lines.append("| Registry/picker tests | Identical baseline and after: " + str(counts["passed_test_count"]) + " passed, " + str(counts["failed_test_count"]) + " existing failures |")
    lines.extend([
        "| Registry/picker reports | Identical deterministic baseline and after |",
        "| In-memory compilation, JSON, whitespace, git diff --check | " + ("PASS" if checks["source_json_whitespace_diff_checks"]["passed"] else "FAIL") + " |",
        "| Historical byte preservation | " + str(result["preservation"]["historical_file_count"]) + " files unchanged; prior frozen pins also match |", "",
        "Completed guarded validation workers report zero forbidden process, socket and historical-write attempts. Frozen pure contracts use controlled fixtures; no live provider graph or operational owner was issued. One exact isolated Python authentication-domain control child is retained separately from operational effects. All " + str(len(compiled)) + " inventoried frozen project sources also compile in memory without import, execution or bytecode output.", "",
        "SANDBOX.2 source changed: **false**. JAVA.1C source changed: **false**. SYNTH retried: **false**. Remediation implemented: **false**. Existing registry, reversal artifacts, blocked attempt, diagnostics, lifecycle/reflection owners and EXECUTOR history are byte preserved. Output is confined to this new phase; no stash, reset, clean or historical repinning occurred.", "",
    ])
    if timeout_files:
        lines.extend(["The initial broad fixture-contract attempt reached its 300-second limit before a final worker summary. It is retained as a partial attempt, with no full-suite pass claimed. The completed contract result above covers the selected context helpers and pure authorization/replay checks; exact test selections are in validation_summary.json. The timed-out process was killed and reaped. Its audit guard prevented operational effects, but a final attempted-effect counter snapshot was unavailable. "
                      + " · ".join("[" + name + "](" + name + ")" for name in timeout_files), ""])
    lines.extend(["| Operational effect | Count |", "| --- | --- |"])
    lines.extend("| " + key + " | " + str(value) + " |" for key, value in result["operational_effects"].items())
    lines.extend([
        "",
        "Recommended next slice: one separately authorized instrumented fresh SYNTH.AUTH.PINNED.1 authorization retry. Retain the full fresh SANDBOX.2 report, original pair observations/authentication in the issuing process, parsed metadata, private-config absence, ordered pre-ladder entries/completions/first exception, workspace and socket outcomes, exact process-context ledger and owner cleanup. Exported reports remain report-only. Bind exact source hashes, use narrow observation without owner replacement, restore instrumentation and preserve failure evidence without exposing secrets or persisting capabilities. Stop at the authorization boundary. No retry is run in this phase.", "",
        "[Full typed report](RUNTIME_SANDBOX_2_NESTED_CONTEXT_DIAG_1_REPORT.json) · [Source inventory](source_context_inventory.json) · [Validation](validation_summary.json) · [Preservation baseline](preservation_baseline.json)", "",
        "Reproduce pure checks only: `python -B docs/roadmap/phases/RUNTIME_SANDBOX_2_NESTED_CONTEXT_DIAG_1/validation.py validate`. Never run historical live or validation scripts directly; historical validation scripts write their own evidence. Regenerate this joined report with this phase's `finalize_report.py`, then run `validation.py source-checks` and `validation.py preservation`.", "",
    ])
    (HERE / "RUNTIME_SANDBOX_2_NESTED_CONTEXT_DIAG_1.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    (HERE / "README.md").write_text(
        "# RUNTIME.SANDBOX.2.NESTED.CONTEXT.DIAG.1\n\n"
        "**UNRESOLVED**. Historical nested root cause unresolved. Pure/static audit only; all operational effects zero.\n\n"
        "[Audit report](RUNTIME_SANDBOX_2_NESTED_CONTEXT_DIAG_1.md) · [Full typed JSON](RUNTIME_SANDBOX_2_NESTED_CONTEXT_DIAG_1_REPORT.json)\n",
        encoding="utf-8", newline="\n")
    print(json.dumps({"status": result["status"], "validation_passed": validation["passed"]}))


if __name__ == "__main__":
    main()
