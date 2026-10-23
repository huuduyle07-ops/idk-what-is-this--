"""Synthetic ADMIT.1 replay; no live approval, author, Java source or execution."""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import statistics
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.repair_scope import RepairScope
from core.structural_implementation_plan import build_structural_implementation_plan
from core.structural_scope_admission import (
    AdmissionError, TIMING_FIELDS, PathWitness, RepositoryAdmissionEvidence,
    admit_structural_authoring_scope, validate_admitted_structural_authoring_scope,
)
from core.structural_scope_approval import decide_structural_scope_ceiling
from scripts.replay_patch_scope_expand1 import fixture_inputs
from scripts.replay_patch_scope_plan1 import approved_fixture, synthetic_planner_proposal
from scripts.replay_patch_scope_refresh1 import ANSWERS


def synthetic_repository_evidence(inputs, plan, root):
    """Explicit synthetic acquisition facts for the in-memory source fixture.

    Production callers use acquire_structural_admission_evidence. These facts
    describe a synthetic repository and never claim to measure real BANK.2.
    """
    sources = {c.file: raw for c, raw in ((inputs["current_context"], inputs["current_source"]),
                                        *inputs.get("related_contexts", ()))}
    paths = sorted(set(sources) | {m.proposed_physical_target for m in
        (*plan.planner_proposal.logical_creations, *plan.planner_proposal.existing_modifications)})
    witnesses = tuple(PathWitness(path, path, "file" if path in sources else "absent",
        sha256(sources[path]).hexdigest() if path in sources else None,
        tuple(("/".join(PurePosixPath(path).parts[:i]), "/".join(PurePosixPath(path).parts[:i]), "directory")
              for i in range(1, len(PurePosixPath(path).parts)))) for path in paths)
    return RepositoryAdmissionEvidence(str(root), plan.repository_id,
        ((".gitignore", None), (".cattusignore", None)), witnesses)


def replay(*, repetitions=5):
    if type(repetitions) is not int or repetitions < 1:
        raise ValueError("positive_repetitions_required")
    root = Path(__file__).resolve().parents[1]
    fixtures = {}
    for transition in ANSWERS:
        inputs, action, receipt = approved_fixture(transition)
        proposal = synthetic_planner_proposal(inputs, receipt)
        plan = build_structural_implementation_plan(approval_receipt=receipt, stored_human_action=action,
                                                   planner_output=proposal, **inputs)
        fixtures[transition] = (inputs, action, receipt, plan, synthetic_repository_evidence(inputs, plan, root))
    source = fixture_inputs()["current_source"].decode().replace("BankAccount(", "private BankAccount(", 1)
    inputs, action, receipt = approved_fixture("preserve_base_compatibility", source=source)
    proposal = synthetic_planner_proposal(inputs, receipt, path="bank.java", nested=True)
    plan = build_structural_implementation_plan(approval_receipt=receipt, stored_human_action=action,
                                               planner_output=proposal, **inputs)
    fixtures["unused_MAY_nested_layout"] = (inputs, action, receipt, plan, synthetic_repository_evidence(inputs, plan, root))
    results, negatives = {}, {}
    guards = ("core.pipeline.run_gemini_request", "core.pipeline.run_deepseek_review",
        "core.control_engine.build_control_prompt", "core.control_engine.authoring_context_for_control_result",
        "socket.create_connection", "socket.socket.connect", "subprocess.run", "subprocess.Popen", "os.system",
        "os.walk", "os.scandir", "os.listdir", "pathlib.Path.open", "pathlib.Path.read_bytes",
        "pathlib.Path.read_text", "pathlib.Path.write_bytes", "pathlib.Path.write_text", "builtins.open")
    def forbidden(*args, **kwargs):
        raise AssertionError("ADMIT.1 attempted author, provider, I/O, traversal or execution")
    with ExitStack() as stack:
        for target in guards:
            stack.enter_context(patch(target, forbidden))
        for name, (inputs, action, receipt, plan, evidence) in fixtures.items():
            before = inputs["current_source"], receipt.as_dict(), plan.to_json(), inputs["current_scope"]
            samples, fingerprints = [], []
            for _ in range(repetitions):
                timings = {}
                scope = admit_structural_authoring_scope(plan, approval_receipt=receipt, stored_human_action=action,
                    repository_evidence=evidence, timings=timings, **inputs)
                assert validate_admitted_structural_authoring_scope(scope.as_dict(), plan=plan,
                    approval_receipt=receipt, stored_human_action=action, repository_evidence=evidence, **inputs) == scope
                samples.append(timings)
                fingerprints.append(scope.fingerprint)
            assert len(set(fingerprints)) == 1
            assert before == (inputs["current_source"], receipt.as_dict(), plan.to_json(), inputs["current_scope"])
            results[name] = {"scope": scope.as_dict(), "plan_fingerprint": plan.fingerprint,
                "admitted_physical_edit_targets": [
                    {"path": o.physical_target, "owner": o.owner, "operation": o.operation,
                     "definition_ids": list(o.definition_ids)} for o in scope.permitted_structural_operations],
                "read_only_support_targets": [r.declaration.owner + "::" + r.declaration.name
                                               for r in scope.read_only_supporting_targets],
                "unused_approved_ceiling_targets": [t.target for t in plan.planner_proposal.ceiling_targets_not_used],
                "candidate_authoring_authority": scope.scope_authority, "write_authority": False,
                "deterministic": True, "source_bytes_unchanged": True, "absence_evidence_kind": "synthetic",
                "must_capabilities_covered": len(scope.capability_coverage),
                "performance": {k: {"median_ms": round(statistics.median(x[k] for x in samples)*1000, 6),
                                     "max_ms": round(max(x[k] for x in samples)*1000, 6)} for k in TIMING_FIELDS}}
        inputs, action, receipt, plan, evidence = fixtures["savings_only_on_subclass"]
        scope = admit_structural_authoring_scope(plan, approval_receipt=receipt, stored_human_action=action,
                                                repository_evidence=evidence, **inputs)
        base = dict(inputs, plan=plan, approval_receipt=receipt, stored_human_action=action, repository_evidence=evidence)
        declined = replace(action, decision="decline_scope_expansion")
        revised = replace(action, decision="request_scope_revision")
        changed_plan = build_structural_implementation_plan(approval_receipt=receipt, stored_human_action=action,
            planner_output=synthetic_planner_proposal(inputs, receipt, helper_name="tryDebit"), **inputs)
        collision = replace(evidence, paths=tuple(replace(p, state="file", source_fingerprint=sha256(b"occupied").hexdigest())
                            if p.path == "SavingAccount.java" else p for p in evidence.paths))
        cases = {
            "decline": ({"approval_receipt": decide_structural_scope_ceiling(**inputs, human_action=declined),
                         "stored_human_action": declined}, "admission_unavailable"),
            "revision": ({"approval_receipt": decide_structural_scope_ceiling(**inputs, human_action=revised),
                          "stored_human_action": revised}, "admission_unavailable"),
            "stale_source": ({"current_source": inputs["current_source"] + b"\n// stale"}, "reacquisition_required"),
            "changed_current_scope": ({"current_scope": RepairScope("not_applicable", "bank.java", "saving")}, "admission_stale"),
            "wrong_p1": ({"proposal": fixtures["preserve_base_compatibility"][0]["proposal"]}, "admission_stale"),
            "wrong_plan": ({"plan": changed_plan}, "admission_stale"),
            "forged_plan": ({"plan": {**plan.as_dict(), "status": "authorized"}}, "admission_stale"),
            "path_collision": ({"repository_evidence": collision}, "admission_conflict_existing_path"),
            "outside_repository": ({"repository_evidence": replace(evidence, paths=tuple(
                replace(p, resolved_relative_path="../SavingAccount.java") if p.path == "SavingAccount.java" else p
                for p in evidence.paths))}, "admission_outside_repository_policy"),
            "ignored_path": ({"repository_evidence": replace(evidence,
                policy_sources=((".gitignore", "SavingAccount.java\n"), (".cattusignore", None)))}, "admission_outside_repository_policy"),
            "hard_excluded_physical_path": ({"repository_evidence": replace(evidence, paths=tuple(
                replace(p, resolved_relative_path=".tmp/SavingAccount.java") if p.path == "SavingAccount.java" else p
                for p in evidence.paths))}, "admission_outside_repository_policy"),
        }
        for name, (changes, expected) in cases.items():
            try:
                validate_admitted_structural_authoring_scope(scope, **{**base, **changes})
            except AdmissionError as exc:
                assert exc.code == expected, (name, exc.code)
                negatives[name] = {"status": exc.code, "candidate": None, "patch": ""}
            else:
                raise AssertionError((name, "unsafe admission accepted"))
        corruptions = {}
        payload = scope.as_dict()
        payload["write_authority"] = True
        corruptions["write_authority_escalation"] = (payload, "admission_authority_escalation")
        payload = scope.as_dict()
        extra = json.loads(json.dumps(payload["definition_allowances"][0]))
        extra["definition"].update(owner="Database", name="Database", definition_id="Database")
        payload["definition_allowances"].append(extra)
        corruptions["extra_definition"] = (payload, "admission_outside_validated_plan")
        payload = scope.as_dict()
        payload["existing_file_authoring_targets"][0]["operation"] = "replace_whole_class"
        corruptions["whole_class_over_admission"] = (payload, "admission_scope_nonminimal")
        payload = scope.as_dict()
        payload["permitted_structural_operations"].append({"operation": "draft_new_file",
            "physical_target": "SavingAccountBehaviorTest.java"})
        corruptions["unapproved_test_file"] = (payload, "admission_scope_nonminimal")
        nested_inputs, nested_action, nested_receipt, nested_plan, nested_evidence = fixtures["unused_MAY_nested_layout"]
        nested_scope = admit_structural_authoring_scope(nested_plan, approval_receipt=nested_receipt,
            stored_human_action=nested_action, repository_evidence=nested_evidence, **nested_inputs)
        for name, (payload, expected) in corruptions.items():
            try:
                validate_admitted_structural_authoring_scope(payload, **base)
            except AdmissionError as exc:
                assert exc.code == expected, (name, exc.code)
                negatives[name] = {"status": exc.code, "candidate": None, "patch": ""}
            else:
                raise AssertionError((name, "over-admission accepted"))
        assert all(a.approved_target not in nested_plan.planner_proposal.ceiling_targets_not_used
                   for a in nested_scope.definition_allowances)
    return {"phase_id": "PATCH.SCOPE.ADMIT.1", "fixture_kind": "synthetic_receipts_frozen_PLAN1_outputs_and_path_facts",
        "scenarios": results, "negative_cases": negatives, "repetitions": repetitions,
        "model_calls": 0, "author_calls": 0, "repository_traversals": 0, "source_bytes_unchanged": True,
        "real_BANK2_approval_consumed": False, "MainApp_session_touched": False,
        "candidate": None, "patch": "", "repair_scope_delta": 0, "authoring_scope_delta": 0,
        "write_authority": False, "filesystem_file_creation_authority": False, "apply_authority": False,
        "execution_authorized": False, "auto_apply": False, "provider_latency": "not_applicable_no_provider",
        "first_remaining_blocker": "STRUCTURAL_AUTHOR_INTEGRATION_NOT_IMPLEMENTED"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--repetitions", type=int, default=5)
    options = parser.parse_args()
    result = replay(repetitions=options.repetitions)
    if options.output:
        options.output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"phase_id": result["phase_id"], "negative_cases": result["negative_cases"],
        "scenarios": {k: {"fingerprint": v["scope"]["admission_fingerprint"],
            "edit_targets": v["admitted_physical_edit_targets"], "unused": v["unused_approved_ceiling_targets"],
            "performance": v["performance"]} for k, v in result["scenarios"].items()},
        "first_remaining_blocker": result["first_remaining_blocker"]}, indent=2))
