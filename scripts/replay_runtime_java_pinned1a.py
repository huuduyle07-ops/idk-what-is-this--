"""One exact-target stopped inspection, only after recorded pure gates.

The fixed output is reserved exclusively before any Docker control. No caller
target or retry path exists. This does not call JAVA.1C or a binding predicate.
"""
from copy import copy, deepcopy
from dataclasses import fields, replace
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
PHASE = ROOT / "docs/roadmap/phases/RUNTIME_JAVA_PINNED_1A"
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True


def _check_pure_gates():
    gates = json.loads((PHASE / "pure_preoperational_gates.json").read_text(encoding="utf-8"))
    if gates.get("phase_id") != "RUNTIME.JAVA.PINNED.1A" or gates.get("pure_gates_ready") is not True:
        raise ValueError("pinned1a_all_pure_gates_required_before_operation")
    if not gates.get("checks") or not all(value is True for value in gates["checks"].values()):
        raise ValueError("pinned1a_incomplete_pure_gates")
    for entry in gates["in_memory_compilation"]["files"]:
        if sha256((ROOT / entry["path"]).read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError("pinned1a_source_changed_after_pure_gates:" + entry["path"])
    return {"pure_gates_ready": True, "source_hashes_checked": len(gates["in_memory_compilation"]["files"])}


def _negative_matrix(owner, receipt):
    """Actual live-object copy/reconstruction controls; no new receipt issued."""
    constructor = {f.name: getattr(receipt, f.name) for f in fields(receipt) if f.init}

    class Subclass(owner.PinnedJavaTargetInspectionReceipt):
        __slots__ = ()

    rows = []
    candidates = {"copy": copy(receipt), "deepcopy": deepcopy(receipt),
        "dataclasses_replace": replace(receipt), "JSON_projection": json.loads(json.dumps(receipt.as_dict())),
        "JSON_reconstruction": owner.PinnedJavaTargetInspectionReceipt(**{
            **constructor, "archive": json.loads(json.dumps(receipt.as_dict()["archive"]))}),
        "subclass": Subclass(**constructor), "wrapper": SimpleNamespace(receipt=receipt)}
    for name, candidate in candidates.items():
        try:
            owner.validate_target_inspection_receipt(candidate)
        except (ValueError, TypeError, AttributeError) as error:
            rows.append({"control": name, "rejected": True, "reason": str(error)})
        else:
            rows.append({"control": name, "rejected": False})
    # Mutations on the original live object are restored immediately. The live
    # registry retains the original bytes, so even a correctly re-signed change
    # cannot authenticate. No invalidation/consumption lifecycle is introduced.
    for name, field, value in (("wrong_process", "issuing_pid", receipt.issuing_pid + 1),
            ("wrong_HMAC", "_signature", "0" * 64),
            ("changed_backend", "backend_server_version", receipt.backend_server_version + "changed"),
            ("changed_evidence_digest", "evidence_digest", "0" * 64)):
        previous = getattr(receipt, field)
        try:
            object.__setattr__(receipt, field, value)
            try:
                owner.validate_target_inspection_receipt(receipt)
            except (ValueError, TypeError, AttributeError) as error:
                rows.append({"control": name, "rejected": True, "reason": str(error)})
            else:
                rows.append({"control": name, "rejected": False})
        finally:
            object.__setattr__(receipt, field, previous)
    owner.validate_target_inspection_receipt(receipt)
    if not all(row["rejected"] for row in rows):
        raise ValueError("pinned1a_live_negative_authentication_control_failed")
    return rows


def main():
    if len(sys.argv) != 1:
        raise ValueError("pinned1a_fixed_no_argument_replay_required")
    gates = _check_pure_gates()
    output = PHASE / "RUNTIME_JAVA_PINNED_1A_LOCAL.json"
    # Exclusive reservation is intentional: this historical operational attempt
    # cannot be silently repeated or overwritten after any outcome.
    with output.open("x", encoding="utf-8") as handle:
        # Use the existing writable phase as the parent for ephemeral policy
        # state. The owner removes its unique workspace/profile before issuance.
        tempfile.tempdir = str(PHASE)
        from core import runtime_java_pinned_target_inspection as owner
        outcome = owner.inspect_target()
        report = outcome.as_dict()
        report["preoperational_gate_summary"] = gates
        report["single_live_attempt"] = True
        report["copy_JSON_negative_matrix"] = (
            _negative_matrix(owner, outcome.receipt) if outcome.receipt is not None else [])
        report["receipt_authentication_after_negative_controls"] = (
            owner.validate_target_inspection_receipt(outcome.receipt) is outcome.receipt
            if outcome.receipt is not None else False)
        report["controller_measurement_is_requirement_constant"] = False
        report["historical_sources_modified_by_operation"] = False
        handle.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "reason": report["reason"],
        "output": str(output), "receipt_authenticated": report["receipt_authentication"],
        "export_elapsed_ms": report["export_elapsed_ms"], "archive_bytes": report["archive_bytes"],
        "archive_entries": report["archive_entries"], "cleanup": report["cleanup"],
        "operational_effect_counts": report["operational_effect_counts"]}, indent=2))
    return 0 if outcome.status == owner.COMPLETE else 2


if __name__ == "__main__":
    sys.exit(main())
