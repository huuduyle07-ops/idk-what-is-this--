"""Aggregate measured contract evidence; no operational owner imports/calls."""
from hashlib import sha256
import json
from pathlib import Path
import re

PHASE = Path(__file__).resolve().parent
STEM = "SYNTH_EXEC_PREP_PINNED_CONTRACT_1_REPORT"


def read(name):
    return json.loads((PHASE / name).read_text(encoding="utf-8"))


def main():
    contract, validation, evidence = (read(name) for name in
        ("contract.json", "validation_summary.json", "evidence_index.json"))
    assert contract["completion_marker"] == "PREPARATION_REQUIRES_REQUIREMENT_EVOLUTION"
    assert contract["requirement_evolution"]["required"] is True
    assert validation["validation_passed"] is True
    assert validation["all_actual_operational_effects_zero"] is True
    assert all(value is False for value in contract["authority_flags"].values())
    assert all(type(value) is int and value == 0 for value in contract["operational_effects"].values())
    markdown = (PHASE / (STEM + ".md")).read_text(encoding="utf-8")
    # Counts are derived from the machine contract, never guessed in prose.
    markdown = markdown.replace("All **31 authority flags**", "All **" + str(len(contract["authority_flags"])) + " authority flags**")
    markdown = markdown.replace("All **21 operational effect counters**", "All **" + str(len(contract["operational_effects"])) + " operational effect counters**")
    counts = ("Measured final results: contract/source **" + str(validation["focused"]["passed"]) +
        " passed**; frozen AST **" + str(validation["frozen"]["passed"]) + " passed**; " +
        str(validation["historical_preservation"]["baseline_file_count"]) +
        " pre-existing scoped files unchanged; in-memory Python compilation **" +
        str(read("static_validation.json")["compiled_count"]) + " files**; no syntax/JSON/whitespace errors; " +
        "git diff --check exit 0. Guarded operational attempts and owner imports: **zero**.\n")
    marker = "Measured counts and exact failed nodes are in [validation_summary.json](validation_summary.json).\n"
    if "Measured final results:" not in markdown:
        assert marker in markdown
        markdown = markdown.replace(marker, marker + "\n" + counts)
    else:
        markdown = re.sub(r"Measured final results:.*?\*\*zero\*\*\.\n", lambda match: counts,
            markdown, count=1, flags=re.DOTALL)
    (PHASE / (STEM + ".md")).write_text(markdown, encoding="utf-8")
    keys = ("effect_classification", "first_behavioral_effect", "authority_separation", "materialization",
        "compiler", "sandbox", "compile_output", "preparation_receipt", "harness_identity", "consumer_readiness",
        "runtime_consumption_gate", "ordering", "cleanup", "error_taxonomy", "authority_flags",
        "operational_effects", "requirement_evolution", "remaining_implementation_prerequisites",
        "recommended_implementation_slice")
    report = {"phase_id": contract["phase_id"], "typed_result": contract["completion_marker"],
        "decision_frozen": True, "owners_implemented": False, "implementation_authorized": False,
        "behavioral_activation_ready": False, "reason": "PROOF_UNRESOLVED",
        "scenario": contract["scenario"], **{key: contract[key] for key in keys},
        "historical_preservation": validation["historical_preservation"],
        "validation": validation, "evidence_source_file_count": len(evidence["files"]),
        "validation_scope": "Pure source/AST/JSON and report-only baseline comparison; no operational/issuance-dependent test suites",
        "writes_scope": "Only this new phase directory: documentation, tests, evidence and validator scratch; no source/class/runtime materialization",
        "authority_flag_count": len(contract["authority_flags"]),
        "operational_effect_counter_count": len(contract["operational_effects"]),
        "artifact_hashes": {name: sha256((PHASE / name).read_bytes()).hexdigest() for name in
            ("contract.json", "test_contract.py", "capture_evidence.py", "validate_pure.py", "evidence_index.json", STEM + ".md")}}
    (PHASE / (STEM + ".json")).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    consistency = {
        "contract_digest_current": report["artifact_hashes"]["contract.json"] == validation["artifact_hashes"]["contract.json"],
        "test_digest_current": report["artifact_hashes"]["test_contract.py"] == validation["artifact_hashes"]["test_contract.py"],
        "harness_digest_current": report["artifact_hashes"]["validate_pure.py"] == validation["artifact_hashes"]["validate_pure.py"],
        "typed_result_in_markdown": report["typed_result"] in markdown,
        "all_flags_false": all(value is False for value in report["authority_flags"].values()),
        "all_effects_exact_zero": all(type(value) is int and value == 0 for value in report["operational_effects"].values()),
        "historical_bytes_preserved": report["historical_preservation"]["historical_preservation_passed"],
        "registry_picker_unchanged": validation["registry_picker"]["unchanged"],
        "validation_passed": validation["validation_passed"],
        "chosen_outcome_is_evolution": report["requirement_evolution"]["required"] and report["typed_result"] == "PREPARATION_REQUIRES_REQUIREMENT_EVOLUTION",
    }
    result = {"checks": consistency, "passed": all(consistency.values()), "owner_modules_imported": False}
    (PHASE / "report_consistency.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"typed_result": report["typed_result"], "report_consistent": result["passed"],
        "authority_flags": len(contract["authority_flags"]), "operational_counters": len(contract["operational_effects"])}))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
