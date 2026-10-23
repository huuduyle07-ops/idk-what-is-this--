"""Synthetic structural author proof: no live provider or real BANK.2 authority."""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import asdict, replace
import json
from pathlib import Path
import statistics
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.structural_patch_author import TIMING_FIELDS, _context, normalize_structural_author_output, validate_structural_patch_candidate
from core.structural_scope_admission import admit_structural_authoring_scope
from core.structural_implementation_plan import build_structural_implementation_plan
from scripts.replay_patch_scope_admit1 import synthetic_repository_evidence
from scripts.replay_patch_scope_plan1 import approved_fixture, synthetic_planner_proposal
from scripts.replay_patch_scope_refresh1 import ANSWERS


def synthetic_case(transition="preserve_base_compatibility", *, root=None, nested=False, source=None, path=None):
    root = Path(root or Path(__file__).resolve().parents[1]).resolve()
    if nested:
        from scripts.replay_patch_scope_expand1 import fixture_inputs
        source = fixture_inputs()["current_source"].decode().replace("BankAccount(", "private BankAccount(", 1)
    inputs, action, receipt = approved_fixture(transition, root=root, source=source)
    proposal = synthetic_planner_proposal(inputs, receipt,
        path=path or ("bank.java" if nested else "SavingAccount.java"), nested=nested)
    plan = build_structural_implementation_plan(approval_receipt=receipt, stored_human_action=action,
                                               planner_output=proposal, **inputs)
    evidence = synthetic_repository_evidence(inputs, plan, root)
    fresh = dict(inputs, plan=plan, approval_receipt=receipt, stored_human_action=action, repository_evidence=evidence)
    scope = admit_structural_authoring_scope(**fresh)
    return scope, fresh


def synthetic_author_output(scope):
    """Illustrative implementation text only; no file is created or compiled."""
    definitions = [a.definition for a in scope.definition_allowances]
    debit = next(d for d in definitions if "base_balance_debit" in d.roles)
    interest = next(d for d in definitions if "savings_interest_behavior" in d.roles)
    ctor = next(d for d in definitions if d.kind == "constructor")
    params = ", ".join(t + " " + n for t, n in ctor.parameters)
    inherited = ", ".join(n for _, n in ctor.parameters[:-1])
    interest_params = ", ".join(t + " " + n for t, n in interest.parameters)
    interest_product = " * ".join(n for _, n in interest.parameters[:2])
    nested = any(o.operation == "insert_nested_class" for o in scope.permitted_structural_operations)
    package = next((t.package_name for t in scope.new_file_creation_targets), "")
    cls = (("package " + package + ";\n") if package else "")
    cls += ("public static class " if nested else "public class ") + "SavingAccount extends BankAccount {\n" + f"""
  private double savingBalance;
  private String password;
  public SavingAccount({params}) {{
    super({inherited});
    this.password = password;
  }}
  private boolean verifySavingsPassword(String providedPassword) {{
    return password.equals(providedPassword);
  }}
  public boolean transferToSavings(double amount, String providedPassword) {{
    if (!verifySavingsPassword(providedPassword)) return false;
    if (!{debit.name}(amount)) return false;
    savingBalance += amount;
    return true;
  }}
  public void {interest.name}({interest_params}) {{
    if (!verifySavingsPassword(System.console().readLine())) return;
    savingBalance += savingBalance * {interest_product};
  }}
}}
"""
    member = f"""protected boolean {debit.name}(double amount) {{
  if (amount <= balance) {{ balance -= amount; return true; }}
  return false;
}}"""
    rows = []
    for operation in scope.permitted_structural_operations:
        remove = operation.operation == "remove_declaration"
        rows.append({"operation": operation.operation, "physical_target": operation.physical_target,
            "owner": operation.owner, "definition_ids": list(operation.definition_ids),
            "source_text": None if remove else member if operation.operation == "insert_member" else cls,
            "existing_declaration": json.loads(json.dumps(asdict(operation.existing_declaration))) if remove else None,
            "removal_intent": remove})
    return {"candidate": {"operations": rows}, "confidence": 0.85,
            "needs_escalation": False, "escalation_reason": None}


def replay(*, repetitions=5):
    results, negative_results = {}, {}
    for name in (*ANSWERS, "nested"):
        scope, fresh = synthetic_case("preserve_base_compatibility" if name == "nested" else name, nested=name == "nested")
        output = synthetic_author_output(scope)
        samples, fingerprints = [], []
        for _ in range(repetitions):
            timings = {}
            with ExitStack() as guards:
                for target in ("subprocess.run", "subprocess.Popen", "os.system", "os.walk", "os.scandir", "os.listdir",
                               "pathlib.Path.open", "pathlib.Path.read_bytes", "pathlib.Path.read_text",
                               "pathlib.Path.write_bytes", "pathlib.Path.write_text", "builtins.open"):
                    guards.enter_context(patch(target, side_effect=AssertionError("unexpected author-phase side effect")))
                result = normalize_structural_author_output(admitted_scope=scope, author_output=output, timings=timings, **fresh)
                assert result.candidate is not None, (result.status, result.reason)
                _context(scope, fresh, timings)
                timings["total_deterministic_seconds"] += timings["author_context_projection_seconds"]
                assert validate_structural_patch_candidate(result.candidate.as_dict(), admitted_scope=scope, **fresh) == result.candidate
            samples.append(timings)
            fingerprints.append(result.candidate.fingerprint)
        assert len(set(fingerprints)) == 1
        results[name] = {"candidate": result.candidate.as_dict(), "deterministic": True,
            "performance": {k: {"median_ms": round(statistics.median(s[k] for s in samples)*1000, 6),
                                 "max_ms": round(max(s[k] for s in samples)*1000, 6)} for k in TIMING_FIELDS}}
    scope, fresh = synthetic_case()
    output = synthetic_author_output(scope)
    negatives = {}
    wrong = deepcopy(output)
    next(r for r in wrong["candidate"]["operations"] if r["operation"] == "draft_new_file")["physical_target"] = "src/SavingAccount.java"
    negatives["wrong_path"] = (wrong, {}, "author_output_outside_admitted_scope")
    for name, suffix in (("extra_class", "class Database {}"), ("extra_field", "private int retryCounter;"),
                         ("extra_method", "public void lockAccount() {}")):
        wrong = deepcopy(output)
        target = next(r for r in wrong["candidate"]["operations"] if r["operation"] == "draft_new_file")
        target["source_text"] = target["source_text"].rsplit("}", 1)[0] + suffix + "\n}"
        negatives[name] = (wrong, {}, "author_output_outside_admitted_scope")
    wrong = deepcopy(output)
    wrong["candidate"]["operations"] = [r for r in wrong["candidate"]["operations"] if r["operation"] != "insert_member"]
    negatives["missing_debit"] = (wrong, {}, "author_output_incomplete")
    wrong = deepcopy(output)
    wrong["candidate"]["apply_authority"] = True
    negatives["authority_escalation"] = (wrong, {}, "author_output_authority_escalation")
    wrong = deepcopy(output)
    wrong["needs_escalation"] = True
    negatives["candidate_plus_escalation"] = (wrong, {}, "author_output_invalid")
    wrong = deepcopy(output)
    next(r for r in wrong["candidate"]["operations"] if r["operation"] == "insert_member")["source_text"] = "javac bank.java"
    negatives["command_payload"] = (wrong, {}, "author_output_invalid")
    wrong = deepcopy(output)
    target = next(r for r in wrong["candidate"]["operations"] if r["operation"] == "draft_new_file")
    target["source_text"] = target["source_text"].replace("savingBalance += amount;", "savingBalance += amount - 1;")
    negatives["semantic_drift_fee"] = (wrong, {}, "author_output_semantic_drift")
    evidence = fresh["repository_evidence"]
    collision = replace(evidence, paths=tuple(replace(p, state="occupied") if p.state == "absent" else p for p in evidence.paths))
    negatives["occupied_new_path"] = (output, {"repository_evidence": collision}, "admission_conflict_existing_path")
    negatives["stale_source"] = (output, {"current_source": fresh["current_source"] + b"\n// stale"}, "reacquisition_required")
    for name, (response, changes, expected) in negatives.items():
        result = normalize_structural_author_output(admitted_scope=scope, author_output=response, **{**fresh, **changes})
        assert result.status == expected and result.candidate is None, (name, result.status)
        negative_results[name] = {"status": result.status, "candidate": None, "author_calls": 0, "model_calls": 0}
    return {"phase_id": "PATCH.AUTHOR.STRUCTURAL.1", "fixture_kind": "synthetic_admissions_and_author_outputs",
        "scenarios": results, "negative_cases": negative_results, "repetitions": repetitions, "model_calls": 0, "author_calls": 0,
        "repository_traversals": 0, "source_mutation": False, "real_BANK2_approval_consumed": False,
        "MainApp_session_touched": False, "write_authority": False, "execution_authorized": False,
        "apply_authority": False, "filesystem_file_creation_authority": False,
        "first_remaining_blocker": "STRUCTURAL_CANDIDATE_MATERIALIZATION_NOT_IMPLEMENTED"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error("positive repetitions required")
    result = replay(repetitions=args.repetitions)
    if args.output:
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"phase_id": result["phase_id"], "scenarios": {name: {
        "fingerprint": scenario["candidate"]["candidate_fingerprint"], "performance": scenario["performance"]}
        for name, scenario in result["scenarios"].items()}, "first_remaining_blocker": result["first_remaining_blocker"]}, indent=2))
