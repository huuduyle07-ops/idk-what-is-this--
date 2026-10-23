"""Exactly one gated provider-only live attempt; fixed no-argument operation."""
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PHASE = ROOT / "docs/roadmap/phases/RUNTIME_JAVA_PINNED_1C"
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True


def _check_pure_gates():
    gates = json.loads((PHASE / "pure_preoperational_gates.json").read_text(encoding="utf-8"))
    if (gates.get("phase_id") != "RUNTIME.JAVA.PINNED.1C"
            or gates.get("pure_gates_ready") is not True or not gates.get("checks")
            or not all(value is True for value in gates["checks"].values())):
        raise ValueError("pinned1c_all_pure_gates_required_before_operation")
    for entry in gates["source_bindings"]:
        if sha256((ROOT / entry["path"]).read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError("pinned1c_source_changed_after_gates:" + entry["path"])
    for entry in gates["validation_bindings"]:
        if sha256((PHASE / entry["path"]).read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError("pinned1c_validation_changed_after_gates:" + entry["path"])
    baseline = json.loads((PHASE / "preservation_baseline.json").read_text(encoding="utf-8"))
    for row in baseline["files"]:
        path = ROOT / row["path"]
        if not path.is_file() or sha256(path.read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError("pinned1c_historical_bytes_changed:" + row["path"])
    return {"pure_gates_ready": True, "source_hashes_checked": len(gates["source_bindings"]),
        "validation_artifacts_checked": len(gates["validation_bindings"]),
        "historical_files_checked": len(baseline["files"])}


def main():
    if len(sys.argv) != 1:
        raise ValueError("pinned1c_fixed_no_argument_replay_required")
    gates = _check_pure_gates()
    output = PHASE / "RUNTIME_JAVA_PINNED_1C_LOCAL.json"
    # Reserve before imports/operations. Failure leaves a reservation too; no retry.
    with output.open("x", encoding="utf-8", newline="\n") as handle:
        tempfile.tempdir = str(PHASE)
        from core import runtime_java_pinned_provider as owner
        outcome = owner.issue_pinned_java_exact_provider()
        report = outcome.as_dict()
        report.update(preoperational_gate_summary=gates, single_live_attempt=True,
            exported_json_is_report_only=True, historical_sources_modified_by_operation=False)
        if outcome.receipt is not None:
            matrix = owner.negative_authentication_matrix(outcome)
            report["negative_authentication_matrix"] = matrix
            report["all_negative_controls_rejected"] = bool(matrix) and all(matrix.values())
            report["proof_authentication_after_negative_controls"] = (
                owner.validate_pinned_java_exact_provider(outcome.receipt,
                    *owner._outcome_objects(outcome)) is outcome.receipt)
            if not report["all_negative_controls_rejected"]:
                report.update(status=owner.UNRESOLVED, reason="live_negative_matrix_failed", exact_provider_proven=False)
        else:
            report.update(negative_authentication_matrix={}, all_negative_controls_rejected=False,
                proof_authentication_after_negative_controls=False)
        handle.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": report["status"], "reason": report["reason"], "output": str(output),
        "exact_provider_proven": report["exact_provider_proven"], "runtime_authority": report["runtime_authority"],
        "negative_controls": len(report["negative_authentication_matrix"]),
        "all_negative_controls_rejected": report["all_negative_controls_rejected"]}, indent=2))
    return 0 if report["status"] == owner.COMPLETE else 2


if __name__ == "__main__":
    sys.exit(main())
