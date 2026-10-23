"""One gated, fresh backend-to-target attachment; stop before runtime proof.

The fixed report is exclusively reserved before any upstream operation. No
caller evidence, image selection, retry option or runtime bridge is accepted.
"""
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PHASE = ROOT / "docs/roadmap/phases/RUNTIME_JAVA_PINNED_1B"
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True


def _check_pure_gates():
    gates = json.loads((PHASE / "pure_preoperational_gates.json").read_text(encoding="utf-8"))
    if (gates.get("phase_id") != "RUNTIME.JAVA.PINNED.1B"
            or gates.get("pure_gates_ready") is not True
            or not gates.get("checks")
            or not all(value is True for value in gates["checks"].values())):
        raise ValueError("pinned1b_all_pure_gates_required_before_operation")
    entries = gates["in_memory_compilation"]["files"]
    if not entries:
        raise ValueError("pinned1b_compilation_source_binding_required")
    for entry in entries:
        if sha256((ROOT / entry["path"]).read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError("pinned1b_source_changed_after_pure_gates:" + entry["path"])
    baseline = json.loads((PHASE / "preservation_baseline.json").read_text(encoding="utf-8"))
    for relative, entry in baseline["files"].items():
        expected = entry["sha256"] if isinstance(entry, dict) else entry
        path = ROOT / relative
        if not path.is_file() or sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("pinned1b_historical_bytes_changed:" + relative)
    return {"pure_gates_ready": True, "source_hashes_checked": len(entries),
        "preserved_baseline_files_checked": len(baseline["files"])}


def main():
    if len(sys.argv) != 1:
        raise ValueError("pinned1b_fixed_no_argument_replay_required")
    gates = _check_pure_gates()
    output = PHASE / "RUNTIME_JAVA_PINNED_1B_LOCAL.json"
    with output.open("x", encoding="utf-8", newline="\n") as handle:
        tempfile.tempdir = str(PHASE)
        from core import runtime_java_pinned_backend_target_binding as owner
        outcome = owner.issue_pinned_backend_target_binding()
        report = outcome.as_dict()
        report.update(preoperational_gate_summary=gates, single_live_attempt=True,
            exported_json_is_report_only=True, historical_sources_modified_by_operation=False)
        if outcome.receipt is not None:
            matrix = owner.negative_authentication_matrix(outcome)
            report["negative_authentication_matrix"] = matrix
            report["all_negative_controls_rejected"] = all(matrix.values())
            report["binding_authentication_after_negative_controls"] = (
                owner.validate_pinned_backend_target_binding(outcome.receipt,
                    outcome.bind_attachment, outcome.sandbox_descriptor,
                    outcome.sandbox_receipt, outcome.inspection_receipt) is outcome.receipt)
            if not report["all_negative_controls_rejected"]:
                report.update(status=owner.UNRESOLVED, reason="live_negative_matrix_failed")
        else:
            report.update(negative_authentication_matrix={}, all_negative_controls_rejected=False,
                binding_authentication_after_negative_controls=False)
        handle.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": report["status"], "reason": report["reason"],
        "output": str(output), "negative_controls": len(report["negative_authentication_matrix"]),
        "all_negative_controls_rejected": report["all_negative_controls_rejected"],
        "binding_authentication_after_negative_controls": report["binding_authentication_after_negative_controls"]}, indent=2))
    return 0 if report["status"] == owner.COMPLETE else 2


if __name__ == "__main__":
    sys.exit(main())
