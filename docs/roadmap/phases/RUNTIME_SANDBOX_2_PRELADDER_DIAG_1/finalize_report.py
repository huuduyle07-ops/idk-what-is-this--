"""Format retained PRELADDER.DIAG.1 evidence without invoking any owner.

Inputs are read-only. The three formatted outputs remain in this new phase;
historical evidence is never repaired, regenerated, or repinned.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PHASE = "RUNTIME.SANDBOX.2.PRELADDER.DIAG.1"
ENDPOINT = "npipe:////./pipe/dockerDesktopLinuxEngine"
IMAGE = "sha256:f6d7dc31a15bb37a618ebed6772beda3de95fdcc3394eb5a1def9b1d20673f7a"
HISTORICAL = ROOT / "docs/roadmap/phases/SYNTH_AUTH_PINNED_1"


def read_json(name, default=None, directory=HERE):
    path = directory / name
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def write_json(name, value):
    (HERE / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8", newline="\n")


def preserved_bytes():
    baseline = read_json("preservation_baseline.json", {})
    files = baseline.get("files", {})
    changes = [name for name, digest in files.items()
               if not (ROOT / name).is_file()
               or hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest]
    return {"passed": bool(files) and not changes, "historical_file_count": len(files),
            "changed_or_missing": changes, "baseline_rewritten": False,
            "method": "SHA256 of every original file named by the exclusive new-phase baseline"}


def is_command(control, *command):
    argv = control.get("argv", [])
    return any(list(argv[i:i + len(command)]) == list(command)
               for i in range(len(argv) - len(command) + 1))


def captured_stream(value):
    if value is None:
        return {"retained": False, "retention_status": "UNAVAILABLE", "bytes": None,
                "sha256": None, "base64": None, "text_utf8_replace": None}
    if isinstance(value, dict):
        return {"retained": value.get("base64") is not None,
                "retention_status": value.get("retention", "retained_original_capture"),
                **value}
    # Older evidence does not retain stdout/stderr; do not fabricate captures.
    return {"retained": False, "retention_status": "UNSUPPORTED_CAPTURE_REPRESENTATION",
            "bytes": None, "sha256": None, "base64": None, "text_utf8_replace": None}


def control_summary(control):
    if control is None:
        return None
    return {"argv": control.get("argv"), "scope": control.get("scope"),
            "status": control.get("status"), "exit_code": control.get("exit_code"),
            "process_created": control.get("process_created"),
            "process_reaped": control.get("process_reaped"),
            "pipes_closed": control.get("pipes_closed"),
            "readers_surviving": control.get("readers_surviving"),
            "stdout": captured_stream(control.get("stdout")),
            "stderr": captured_stream(control.get("stderr")),
            "exceptions": control.get("exceptions", [])}


def historical_facts():
    raw = read_json("SYNTH_AUTH_PINNED_1_LOCAL.json", {}, HISTORICAL)
    proof = raw.get("provider_proof_report", {})
    effects = proof.get("java1c_and_own_sandbox_effects", {})
    controls = proof.get("runtime_docker_controls", [])
    image = next((c for c in controls if c.get("scope") == "JAVA1C_SANDBOX2_infrastructure"
                  and is_command(c, "image", "inspect")), None)
    argv = image.get("argv", []) if image else []
    config = argv[argv.index("--config") + 1] if "--config" in argv else None
    java = proof.get("java1c_report", {})
    pinned = proof.get("pinned1b_report", {})
    endpoint = proof.get("runtime_backend_pre")
    post = read_json("post_attempt_cleanup_observation.json", {}, HISTORICAL)
    return {"source": "docs/roadmap/phases/SYNTH_AUTH_PINNED_1/SYNTH_AUTH_PINNED_1_LOCAL.json",
            "SYNTH_status": raw.get("status"), "provider_proof_status": raw.get("provider_proof_status"),
            "fresh_PINNED1B_invocations": proof.get("fresh_pinned1b_invocations"),
            "PINNED1B_status": pinned.get("status"), "PINNED1B_cleanup": pinned.get("cleanup"),
            "fresh_JAVA1C_invocations": proof.get("fresh_java1c_invocations"),
            "JAVA1C_status": java.get("status"), "JAVA1C_reason": java.get("reason"),
            "JAVA1C_controller_error": java.get("controller_error"),
            "backend_pre": endpoint, "backend_post": proof.get("runtime_backend_post"),
            "exact_image_inspect": {"available": image is not None,
                "successful": bool(image and image.get("completed") and image.get("exit_code") == 0),
                "original_argv": image.get("argv") if image else None,
                "scope": image.get("scope") if image else None,
                "completed": image.get("completed") if image else None,
                "exit_code": image.get("exit_code") if image else None,
                "stdout_retained": bool(image and "stdout" in image),
                "stderr_retained": bool(image and "stderr" in image)},
            "own_SANDBOX2_create_attempts": effects.get("container_create_attempts"),
            "own_SANDBOX2_start_attempts": effects.get("container_start_attempts"),
            "image_metadata": None,
            "private_config_path_in_argv": config,
            "private_config_absence_behavior_measured": None,
            "workspace_preparation_behavior_measured": None,
            "own_SANDBOX2_final_status": None,
            "own_SANDBOX2_eligibility": None,
            "own_SANDBOX2_cleanup_verified": None,
            "own_SANDBOX2_ladder_stage_count": None,
            "original_SANDBOX2_report_and_pair_retained": False,
            "retained_semantic_gate_evidence": "JAVA1C semantic branch rejected after SANDBOX2 pair and policy validation; its generic not_authenticated reason does not demonstrate HMAC failure.",
            "SYNTH_owner_cleanup_verified": raw.get("cleanup_verified"),
            "provider_owner_cleanup_verified": proof.get("cleanup_verified"),
            "JAVA1C_owner_cleanup_verified": java.get("cleanup_verified"),
            "independent_later_cleanup": post,
            "missing_evidence": ["own SANDBOX2 original report", "own SANDBOX2 original descriptor and receipt",
                "image inspection original stdout/stderr and parsed metadata",
                "private config path absence measurements", "workspace preparation result or exception",
                "host socket setup result or exception", "exact first pre-ladder failure"],
            "raw_controls": controls}


def compare_history(live, historical, image_control):
    invoked = live.get("operational_effects", {}).get("SANDBOX2_operational_issuances",
                  live.get("operational_issuances"))
    status = live.get("owner_status")
    create = live.get("first_container_create_attempted")
    inspected = None if image_control is None else (
        image_control.get("status") == "sandbox_completed" and image_control.get("exit_code") == 0)
    if not invoked or image_control is None or historical["own_SANDBOX2_create_attempts"] is None:
        classification = "INSUFFICIENT_HISTORICAL_EVIDENCE"
    elif create or status == "RUNTIME_SANDBOX_2_COMPLETE_WITH_WARNINGS":
        classification = "DIFFERS_FROM_HISTORICAL_FAILURE_SHAPE"
    elif inspected is False and historical["exact_image_inspect"]["successful"]:
        classification = "DIFFERS_FROM_HISTORICAL_FAILURE_SHAPE"
    elif inspected is True and create is False and status == "RUNTIME_SANDBOX_2_BLOCKED_UNRESOLVED":
        classification = "MATCHES_HISTORICAL_FAILURE_SHAPE"
    else:
        classification = "INSUFFICIENT_HISTORICAL_EVIDENCE"
    return {"classification": classification,
            "comparison_scope": "Measured inspection/create/status shape; unretained historical internals remain unknown.",
            "rows": [
                {"fact": "exact image inspection success", "historical": historical["exact_image_inspect"]["successful"] if historical["exact_image_inspect"]["available"] else None, "fresh": inspected},
                {"fact": "parsed image metadata", "historical": None, "fresh": live.get("image_metadata")},
                {"fact": "private config behavior", "historical": "argv path retained; absence not measured", "fresh": live.get("cleanup", {}).get("private_config_paths")},
                {"fact": "workspace behavior", "historical": "not retained", "fresh": live.get("cleanup", {}).get("temporary_workspaces")},
                {"fact": "first create attempted", "historical": False if historical["own_SANDBOX2_create_attempts"] == 0 else None, "fresh": create},
                {"fact": "SANDBOX2 final status", "historical": "blocked pair inferred by frozen context; original report absent", "fresh": status},
                {"fact": "eligibility", "historical": "false per frozen diagnostic context; original descriptor absent", "fresh": live.get("semantic_eligibility")},
                {"fact": "SANDBOX2 owner cleanup", "historical": "not retained", "fresh": live.get("cleanup", {}).get("owner_cleanup_verified")},
                {"fact": "ladder stage count", "historical": "no ladder create; original stage list absent", "fresh": live.get("stage_count")},
            ],
            "historical_nested_root_cause_established": False,
            "restricted_AUTH_DIAG_permission_denial_attributed_to_historical_nested_failure": False,
            "standalone_success_implication": "A successful fresh standalone run supports possible context sensitivity but identifies no causal outer component." if status == "RUNTIME_SANDBOX_2_COMPLETE_WITH_WARNINGS" else None,
            "same_root_cause_claimed": False}


def build_report():
    live = read_json("live_result.json")
    if live is None:
        raise RuntimeError("live_result.json absent; do not format a proposed outcome as measured")
    original = read_json("SANDBOX2_original_report.json")
    pair = read_json("fresh_original_pair.json")
    controls = read_json("observed_controls.json", [])
    independent_controls = read_json("independent_cleanup_controls.json", [])
    cleanup = read_json("independent_cleanup.json", live.get("cleanup", {}))
    static = read_json("static_pre_ladder_audit.json", {})
    preflight = read_json("host_preflight.json", live.get("preflight", {}))
    image_control = next((c for c in controls if is_command(c, "image", "inspect")), None)
    first = live.get("first_failing_step")
    relevant_control = None
    if first:
        if "control_index" in first and isinstance(first["control_index"], int) and 0 <= first["control_index"] < len(controls):
            relevant_control = controls[first["control_index"]]
        elif first.get("step", "").startswith(("image_", "exact_image_", "metadata_")):
            relevant_control = image_control
    historical = historical_facts()
    comparison_input = {**live, "cleanup": cleanup}
    if "operational_effects" not in comparison_input:
        comparison_input["operational_effects"] = {"SANDBOX2_operational_issuances": live.get("operational_issuances", 0)}
    history = compare_history(comparison_input, historical, image_control)
    effects = dict(live.get("operational_effects", {}))
    operational_count = effects.get("SANDBOX2_operational_issuances", live.get("operational_issuances"))
    if operational_count is None:
        operational_count = 1 if (HERE / "LIVE_ATTEMPT_STARTED.json").exists() else 0
    effects.setdefault("SANDBOX2_operational_issuances", operational_count)
    effects.setdefault("Docker_version_preflight", sum(is_command(c, "version") for c in controls))
    effects.setdefault("SANDBOX2_Docker_controls", sum(c.get("scope") != "diagnostic_read_only_control" for c in controls))
    effects.setdefault("independent_cleanup_Docker_controls", len(independent_controls))
    effects.setdefault("SANDBOX2_container_create_attempts", sum(is_command(c, "create") for c in controls))
    effects.setdefault("SANDBOX2_container_start_attempts", sum(is_command(c, "start") for c in controls))
    effects["total_Docker_controls"] = len(controls) + len(independent_controls)
    for name in ("PINNED1A_export", "PINNED1B", "PINNED1C", "BIND1", "JAVA1C", "SYNTH",
                 "Java_compile_outside_frozen_version_probes", "JVM_fixture", "SyntheticStateBox",
                 "reflection", "runtime_lease_consumption", "reflection_lease_consumption", "BANK",
                 "EXECUTOR1R", "Apply", "repository_runtime_writes", "pulls", "builds",
                 "generic_image_inventory", "alternative_provider_inspection", "caller_shell_workload",
                 "host_mounts", "outbound_workload_network"):
        effects.setdefault(name, 0)
    ledger = live.get("ordered_pre_ladder_ledger")
    if ledger is None:
        ledger = [{**row, "state": "NOT_REACHED", "reason": live.get("status")}
                  for row in static.get("ordered_pre_ladder_steps", [])]
    descriptor = pair.get("descriptor") if pair else None
    receipt = pair.get("receipt") if pair else None
    validation = read_json("validation_summary.json", {})
    source_hashes = live.get("source_hashes", static.get("source_hashes", {}))
    hashes_now = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                  for name in source_hashes if (ROOT / name).is_file()}
    preflight_control = next((c for c in controls if is_command(c, "version")), None)
    return {"phase_id": PHASE, "status": live.get("status"),
            "classification": live.get("classification", live.get("status")),
            "generated_utc": datetime.now(timezone.utc).isoformat(), "diagnostic_only": True,
            "operational_issuances": operational_count, "host_preflight": preflight,
            "host_preflight_original_control": control_summary(preflight_control),
            "endpoint": live.get("endpoint", ENDPOINT), "exact_frozen_image": live.get("exact_frozen_image", IMAGE),
            "source_hashes": source_hashes, "source_hashes_current": hashes_now,
            "source_hashes_preserved": bool(source_hashes) and hashes_now == source_hashes,
            "ordered_pre_ladder_ledger": ledger, "first_failing_pre_ladder_step": first,
            "first_failing_source": {key: first.get(key) for key in ("source", "function", "line")} if first else None,
            "first_failure_relevant_original_control": control_summary(relevant_control),
            "first_failure_control_relation": "Control supplied input to failing operation; its own status/code may have passed." if relevant_control else "No relevant original Docker control was retained for this operation, or no pre-ladder failure occurred.",
            "exact_image_inspection_original_control": control_summary(image_control),
            "all_original_controls": controls, "independent_cleanup_controls": independent_controls,
            "image_metadata": live.get("image_metadata"),
            "private_config_path_facts": cleanup.get("private_config_paths"),
            "temporary_workspace_facts": cleanup.get("temporary_workspaces"),
            "first_container_create_attempted": live.get("first_container_create_attempted", False if operational_count == 0 else None),
            "first_ladder_stage_reached": live.get("first_ladder_mode_reached"),
            "SANDBOX2_final_status": live.get("owner_status", original.get("status") if original else None),
            "SANDBOX2_descriptor_status": live.get("descriptor_status", descriptor.get("status") if descriptor else None),
            "SANDBOX2_receipt_status": live.get("receipt_status", receipt.get("status") if receipt else None),
            "original_pair": pair, "receipt_descriptor_HMAC_results": live.get("HMAC_results", pair.get("HMAC_results") if pair else None),
            "semantic_eligibility": live.get("semantic_eligibility", pair.get("semantic_eligibility") if pair else None),
            "stage_count": live.get("stage_count", len(original.get("stages", [])) if original else None),
            "owner_cleanup_result": {"verified": cleanup.get("owner_cleanup_verified", original.get("cleanup_verified") if original else None),
                "remaining_containers": cleanup.get("owner_remaining_container_count", original.get("phase_container_count_after_teardown") if original else None)},
            "independent_cleanup_result": cleanup,
            "remaining_containers": cleanup.get("independent_remaining_containers"),
            "historical_nested_evidence": historical, "historical_comparison": history,
            "historical_shape_classification": history["classification"],
            "historical_nested_root_cause_established": False,
            "restricted_standalone_denial_attributed_to_historical_nested_failure": False,
            "JAVA1C_invoked": live.get("JAVA1C_invoked", False), "SYNTH_retried": live.get("SYNTH_retried", False),
            "runtime_authority_issued": live.get("runtime_authority_issued", False),
            "operational_effects": effects, "forbidden_owner_calls_observed": live.get("forbidden_owner_calls", []),
            "owner_namespace_unchanged": live.get("owner_namespace_unchanged"),
            "escaping_owner_exception": live.get("escaping_owner_exception"),
            "preservation": preserved_bytes(), "pre_live_gates": read_json("validation_pre_live.json"),
            "validation_summary": validation, "registry_picker_baseline_vs_after": read_json("registry_picker_comparison.json"),
            "post_live_artifact_validation": read_json("post_live_validation.json"),
            "pure_authentication_decomposition": read_json("worker_auth-matrix.json"),
            "AUTH_DIAG_artifact_checks": read_json("auth_artifact_check.json"),
            "stop_boundary_observed": True,
            "limitations": ["Exported report fields are report-only; original live objects remain process-local.",
                "The observer reads frozen frame locals and returns; instrumentation timing influence cannot be excluded.",
                "Missing historical SANDBOX2 live evidence prevents an exact historical root-cause determination.",
                "A later independent zero-container observation never changes the original owner cleanup flag."],
            "artifacts": {"original_owner_report": "SANDBOX2_original_report.json" if original else None,
                "original_descriptor_and_receipt": "fresh_original_pair.json" if pair else None,
                "controls": "observed_controls.json" if (HERE / "observed_controls.json").is_file() else None,
                "static_audit": "static_pre_ladder_audit.json", "live_result": "live_result.json",
                "preservation_baseline": "preservation_baseline.json", "validation_summary": "validation_summary.json",
                "post_live_validation": "post_live_validation.json" if (HERE / "post_live_validation.json").is_file() else None}}


def cell(value):
    if value is None:
        return "UNAVAILABLE"
    text = json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else str(value)
    return text.replace("|", "\\|").replace("\r", "").replace("\n", "<br>")


def table(headers, rows):
    return ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |",
            *("| " + " | ".join(cell(value) for value in row) + " |" for row in rows)]


def control_text(control):
    if control is None:
        return ["No relevant original Docker control is available."]
    result = ["```json", json.dumps({k: control.get(k) for k in ("argv", "scope", "status", "exit_code", "process_reaped", "pipes_closed")}, indent=2), "```", ""]
    for name in ("stdout", "stderr"):
        value = control[name]
        result += [f"Original {name} retention: **{cell(value.get('retention_status'))}**; "
                   f"bytes: {cell(value.get('bytes'))}; SHA256: `{cell(value.get('sha256'))}`."]
        if value.get("retained"):
            result += ["", "```text", value.get("text_utf8_replace") or "", "```", ""]
    return result


def markdown(report):
    preflight = report["host_preflight"]
    first = report["first_failing_pre_ladder_step"]
    cleanup = report["independent_cleanup_result"]
    passed = report["preservation"]["passed"]
    lines = [f"# {PHASE}", "", f"**{report['status']}** · **{report['classification']}**", "",
             "This retained diagnostic used the unchanged SANDBOX.2 public owner. No remediation, JAVA.1C continuation, SYNTH retry, or runtime authority was issued.", "",
             "## Outcome", ""]
    if report["operational_issuances"] == 0:
        lines += [f"Stopped with **{report['status']}** before any SANDBOX.2 issuance. Endpoint or observation availability is a diagnostic environment result; no SANDBOX.2 semantic failure was measured.", ""]
    elif first:
        lines += [f"The first failing pre-ladder operation was **{first['step']}**, classified **{report['classification']}**, in `{first['source']}:{first['line']}` (`{first['function']}`).", ""]
    else:
        lines += [f"Pre-ladder result: **{report['classification']}**. First container create attempted: **{cell(report['first_container_create_attempted'])}**. The frozen owner continued naturally; its final status was **{cell(report['SANDBOX2_final_status'])}**.", ""]
    lines += table(["Fact", "Measured result"], [
        ("SANDBOX.2 operational issuances", report["operational_issuances"]),
        ("Linux Server.Version retrieved", preflight.get("linux_server_version_retrieved")),
        ("Endpoint", report["endpoint"]), ("Server.Version", preflight.get("server_version")),
        ("Exact frozen image", report["exact_frozen_image"]),
        ("First create attempted", report["first_container_create_attempted"]),
        ("First ladder mode", report["first_ladder_stage_reached"]),
        ("SANDBOX.2 final / descriptor / receipt status", [report["SANDBOX2_final_status"], report["SANDBOX2_descriptor_status"], report["SANDBOX2_receipt_status"]]),
        ("Receipt / descriptor HMAC results", report["receipt_descriptor_HMAC_results"]),
        ("Semantic eligibility", report["semantic_eligibility"]), ("Ladder stage count", report["stage_count"]),
        ("JAVA.1C invoked", report["JAVA1C_invoked"]), ("SYNTH retried", report["SYNTH_retried"]),
        ("Runtime authority issued", report["runtime_authority_issued"]),
    ])
    lines += ["", "## Source bytes and ordered pre-ladder ledger", ""]
    lines += table(["Source", "SHA256"], report["source_hashes"].items())
    lines += ["", f"Frozen source hashes preserved: **{cell(report['source_hashes_preserved'])}**. Every row below follows the recovered frozen source order. Detailed inputs, possible exceptions/statuses, termination behavior and container effects are retained in the JSON report and [static audit](static_pre_ladder_audit.json).", ""]
    lines += table(["Order", "Step", "State", "Source / function", "Input", "Possible failure", "Creates container"], [
        (row.get("order"), row.get("step"), row.get("state"), f"{row.get('source')}:{row.get('line')} {row.get('function')}", row.get("input"), row.get("possible_exception_status"), row.get("creates_container"))
        for row in report["ordered_pre_ladder_ledger"]])
    lines += ["", "## Original controls and image metadata", "", "### Host preflight", ""]
    lines += control_text(report["host_preflight_original_control"])
    lines += ["", "### Control relevant to the first failure", "", report["first_failure_control_relation"], ""]
    lines += control_text(report["first_failure_relevant_original_control"])
    lines += ["", "### Exact image inspection", ""]
    lines += control_text(report["exact_image_inspection_original_control"])
    lines += ["", "Parsed image metadata:", "", "```json", json.dumps(report["image_metadata"], indent=2, sort_keys=True), "```", "",
              "The full original bounded stdout/stderr bytes are retained as Base64 with byte counts and SHA256 where available in [controls](observed_controls.json). Decoded text is for reading; Base64 preserves the original bytes.", "",
              "## Workspace and private Docker config", "",
              "The frozen Docker prefix constructs a random private config path; it does not create that path or validate its absence. Absence is an independent observed fact. Workspace creation and all inherent frozen owner effects were allowed to continue.", "",
              "```json", json.dumps({"private_config_paths": report["private_config_path_facts"], "temporary_workspaces": report["temporary_workspace_facts"]}, indent=2, sort_keys=True), "```", "",
              "## Authentication, semantic eligibility and cleanup", ""]
    if report["original_pair"] is not None:
        lines += ["Original descriptor and receipt objects were retained at the issuer return and independently checked by unchanged SANDBOX.2 public validators. Exported fields contain no HMAC secret or signature and do not grant authority.", ""]
    else:
        lines += ["No original SANDBOX.2 pair was retained; authentication and eligibility outcomes remain unavailable. No reconstructed pair is substituted.", ""]
    lines += table(["Cleanup fact", "Result"], [
        ("Original owner cleanup", report["owner_cleanup_result"]),
        ("Independent final zero containers", cleanup.get("independent_zero_containers_verified")),
        ("Independent final cleanup verified", cleanup.get("independent_cleanup_verified")),
        ("Remaining phase containers", report["remaining_containers"]),
        ("Control children reaped", cleanup.get("all_control_children_reaped")),
        ("Control pipes closed", cleanup.get("all_control_pipes_closed")),
        ("Control readers stopped", cleanup.get("all_control_readers_stopped")),
        ("Observer restored", cleanup.get("observer_restored")),
        ("Private config paths absent", cleanup.get("all_private_config_paths_absent")),
        ("Created temporary workspaces removed", cleanup.get("temporary_workspaces_removed")),
    ])
    lines += ["", "The original owner cleanup result is preserved exactly. A later zero-container observation does not change that result.", "",
              "## Historical nested comparison", "", f"**{report['historical_shape_classification']}**", ""]
    lines += table(["Fact", "Frozen nested SYNTH attempt", "Fresh standalone diagnostic"], [
        (row["fact"], row["historical"], row["fresh"]) for row in report["historical_comparison"]["rows"]])
    lines += ["", "Historical own SANDBOX.2 inspection succeeded and no container create was attempted. Its original live report, pair and deeper pre-ladder evidence were not retained. Matching blocked outcomes or matching partial failure shapes do not establish the same root cause. **The historical nested root cause remains unresolved.**", "",
              "The restricted standalone AUTH.DIAG Docker permission denial is separate evidence and is never attributed to the older nested failure.", ""]
    if report["historical_comparison"]["standalone_success_implication"]:
        lines += [report["historical_comparison"]["standalone_success_implication"], ""]
    lines += ["## Operational effects", ""]
    lines += table(["Effect", "Count"], report["operational_effects"].items())
    lines += ["", "These counts reflect frozen source and retained original control argv/scope plus owner reports. They do not claim OS-wide event tracing.", "",
              "## Preservation and validation", "", f"Historical byte preservation: **{cell(passed)}**, **{report['preservation']['historical_file_count']}** files checked. No historical baseline was repinned; existing worktree changes were retained.", "",
              "```json", json.dumps({"pre_live_gates_passed": (report["pre_live_gates"] or {}).get("passed"),
                  "validation_passed": report["validation_summary"].get("passed"),
                  "validation_checks": report["validation_summary"].get("checks"),
                  "registry_picker_baseline_vs_after": report["registry_picker_baseline_vs_after"],
                  "preservation": report["preservation"]}, indent=2, sort_keys=True), "```", "",
              "[Full measured report](RUNTIME_SANDBOX_2_PRELADDER_DIAG_1_REPORT.json) · [Live result](live_result.json) · [Validation](validation_summary.json) · [Post-live artifact checks](post_live_validation.json) · [Preservation baseline](preservation_baseline.json)", "",
              "**STOP:** one authorized standalone diagnostic only. No remediation, further issuance, JAVA.1C continuation, SYNTH retry, lease consumption, reflection, SyntheticStateBox, BANK, EXECUTOR or Apply follows."]
    # Captured stderr may contain trailing whitespace. Keep exact bytes in JSON;
    # Markdown is authored presentation and avoids introducing whitespace drift.
    return "\n".join(line.rstrip() for line in lines) + "\n"


def main():
    report = build_report()
    write_json("RUNTIME_SANDBOX_2_PRELADDER_DIAG_1_REPORT.json", report)
    (HERE / "RUNTIME_SANDBOX_2_PRELADDER_DIAG_1.md").write_text(markdown(report), encoding="utf-8", newline="\n")
    (HERE / "README.md").write_text(
        f"# {PHASE}\n\n"
        "[Diagnostic report](RUNTIME_SANDBOX_2_PRELADDER_DIAG_1.md) · [Full measured JSON](RUNTIME_SANDBOX_2_PRELADDER_DIAG_1_REPORT.json)\n\n"
        f"{report['status']}; {report['classification']}. "
        f"SANDBOX.2 issuances: {report['operational_issuances']}. "
        "Historical nested root cause remains unresolved. No remediation or runtime authority issuance.\n",
        encoding="utf-8", newline="\n")
    print(json.dumps({key: report[key] for key in ("phase_id", "status", "classification", "operational_issuances", "historical_shape_classification", "preservation")}))


if __name__ == "__main__":
    main()
