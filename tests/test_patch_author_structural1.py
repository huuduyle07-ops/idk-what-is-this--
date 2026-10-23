"""Structural drafts tested with synthetic approvals/output, never a live author."""
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import FrozenInstanceError, asdict, replace
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from core.structural_patch_author import (
    StructuralAuthorError, StructuralAuthorInvocation, TIMING_FIELDS,
    normalize_structural_author_output, validate_structural_patch_candidate,
)
from core.structural_scope_admission import acquire_structural_admission_evidence
from scripts.replay_patch_author_structural1 import synthetic_case, synthetic_author_output
from scripts.replay_patch_scope_refresh1 import ANSWERS


@pytest.fixture(scope="module")
def cases():
    result = {name: synthetic_case(name) for name in ANSWERS}
    result["nested"] = synthetic_case(nested=True)
    return result


def normalize(case, output=None, **changes):
    scope, fresh = case
    return normalize_structural_author_output(admitted_scope=scope,
        author_output=synthetic_author_output(scope) if output is None else output, **{**fresh, **changes})


def row(output, kind="draft_new_file"):
    return next(r for r in output["candidate"]["operations"] if r["operation"] == kind)


@pytest.mark.parametrize("name", (*ANSWERS, "nested"))
def test_all_layouts_are_atomic_immutable_bounded_candidates(cases, name):
    case = cases[name]
    scope, fresh = case
    before = (scope.to_json(), fresh["current_source"], fresh["approval_receipt"].as_dict(), fresh["current_scope"])
    timings = {}
    result = normalize_structural_author_output(admitted_scope=scope, author_output=synthetic_author_output(scope),
                                              timings=timings, **fresh)
    assert result.candidate, (result.status, result.reason)
    candidate = result.candidate
    assert validate_structural_patch_candidate(candidate.as_dict(), admitted_scope=scope, **fresh) == candidate
    assert set(timings) == set(TIMING_FIELDS) and all(t >= 0 for t in timings.values())
    assert {(o.operation, o.physical_target, o.owner, o.definition_ids) for o in candidate.operations} == {
        (o.operation, o.physical_target, o.owner, o.definition_ids) for o in scope.permitted_structural_operations}
    for key in ("write_authority", "filesystem_write_authority", "filesystem_file_creation_authority",
                "execution_authorized", "apply_authority"):
        assert getattr(candidate, key) is getattr(result, key) is False
    assert candidate.authority == "candidate_only" and candidate.patch == ""
    assert candidate.repair_scope_delta == candidate.authoring_scope_delta == result.repository_traversals == 0
    assert result.author_calls == result.model_calls == 0
    assert candidate.admission_fingerprint == scope.fingerprint
    assert candidate.implementation_plan_fingerprint == fresh["plan"].fingerprint
    assert candidate.source_bindings == scope.source_bindings
    with pytest.raises(FrozenInstanceError):
        candidate.status = "writable"
    with pytest.raises(StructuralAuthorError, match="mutable"):
        replace(candidate, operations=list(candidate.operations))
    assert before == (scope.to_json(), fresh["current_source"], fresh["approval_receipt"].as_dict(), fresh["current_scope"])
    removes = [o for o in candidate.operations if o.operation == "remove_declaration"]
    assert bool(removes) == (name == "savings_only_on_subclass")
    if removes:
        assert removes[0].existing_declaration == next(o.existing_declaration for o in scope.permitted_structural_operations
                                                      if o.operation == "remove_declaration")
        assert removes[0].source_text is None and removes[0].removal_intent
    if name == "nested":
        assert not candidate.new_path_absence_witnesses
        assert all(o.physical_target == "bank.java" for o in candidate.operations)
        assert any(o.operation == "insert_nested_class" for o in candidate.operations)


def test_normalization_canonicalizes_operation_id_order_and_transport_newlines(cases):
    case = cases["preserve_base_compatibility"]
    original = normalize(case).candidate
    output = synthetic_author_output(case[0])
    output["candidate"]["operations"].reverse()
    output["confidence"] = 0.01
    for operation in output["candidate"]["operations"]:
        operation["definition_ids"].reverse()
        operation["source_text"] = operation["source_text"].replace("\n", "\r\n")
    assert normalize(case, output).candidate.fingerprint == original.fingerprint
    assert normalize(case, json.dumps(output)).candidate == original


@pytest.mark.parametrize("extra", ("class Database {}", "private int retryCounter;", "public void lockAccount() {}",
                                    "private class PasswordManager {}", "static {}", "{ savingBalance = 1; }"))
def test_unadmitted_new_file_structure_is_rejected(cases, extra):
    case = cases["preserve_base_compatibility"]
    output = synthetic_author_output(case[0])
    target = row(output)
    target["source_text"] = target["source_text"].rsplit("}", 1)[0] + extra + "\n}"
    result = normalize(case, output)
    assert result.status == "author_output_outside_admitted_scope" and result.candidate is None


@pytest.mark.parametrize("edit", ("private double balance;", "public double balance;",
    "public void deposit(double amount) {}", "public void withdraw(double amount) {}",
    "BankAccount(String n, double b) {}", "public void saving(double rate) {}"))
def test_visible_support_is_never_an_edit_allowance(cases, edit):
    case = cases["preserve_base_compatibility"]
    output = synthetic_author_output(case[0])
    row(output, "insert_member")["source_text"] += "\n" + edit
    assert normalize(case, output).status == "author_output_outside_admitted_scope"


@pytest.mark.parametrize("path", ("src/SavingAccount.java", "SavingAccountBehaviorTest.java", "MainApp.java",
                                  "../SavingAccount.java", "bank.java"))
def test_exact_physical_path_cannot_be_changed(cases, path):
    case = cases["preserve_base_compatibility"]
    output = synthetic_author_output(case[0])
    row(output)["physical_target"] = path
    assert normalize(case, output).status == "author_output_outside_admitted_scope"


@pytest.mark.parametrize("change", ("name", "type", "visibility", "parameters", "owner", "parent", "definition_id"))
def test_claimed_definition_id_cannot_authorize_different_java(cases, change):
    case = cases["preserve_base_compatibility"]
    output = synthetic_author_output(case[0])
    target = row(output, "insert_member")
    old, new = {"name": ("debitForSavings", "otherDebit"), "type": ("boolean", "int"),
        "visibility": ("protected", "public"), "parameters": ("double amount", "int amount")}.get(change, ("", ""))
    if change in {"name", "type", "visibility", "parameters"}:
        target["source_text"] = target["source_text"].replace(old, new)
    elif change == "owner":
        target["owner"] = "SavingAccount"
    elif change == "definition_id":
        target["definition_ids"] = ["BankAccount::withdraw::method"]
    else:
        row(output)["source_text"] = row(output)["source_text"].replace("extends BankAccount", "extends OtherAccount")
    assert normalize(case, output).status == "author_output_outside_admitted_scope"


@pytest.mark.parametrize("name", tuple(ANSWERS))
def test_required_operations_cannot_be_omitted(cases, name):
    case = cases[name]
    output = synthetic_author_output(case[0])
    output["candidate"]["operations"] = [o for o in output["candidate"]["operations"] if o["operation"] != "insert_member"]
    assert normalize(case, output).status == "author_output_incomplete"
    if name == "savings_only_on_subclass":
        output = synthetic_author_output(case[0])
        output["candidate"]["operations"] = [o for o in output["candidate"]["operations"] if o["operation"] != "remove_declaration"]
        assert normalize(case, output).status == "author_output_incomplete"


@pytest.mark.parametrize("name", ("preserve_base_compatibility", "subclass_specialization"))
def test_preserved_base_contract_cannot_be_removed(cases, name):
    output = synthetic_author_output(cases[name][0])
    forbidden = row(synthetic_author_output(cases["savings_only_on_subclass"][0]), "remove_declaration")
    output["candidate"]["operations"].append(forbidden)
    assert normalize(cases[name], output).status == "author_output_outside_admitted_scope"


def test_exact_removal_prohibits_replacement_or_model_chosen_span(cases):
    case = cases["savings_only_on_subclass"]
    for extra in ({"source_text": ""}, {"removal_intent": False}, {"byte_span": [0, 99999]}):
        output = synthetic_author_output(case[0])
        row(output, "remove_declaration").update(extra)
        assert normalize(case, output).status == "author_output_outside_admitted_scope"
    output = synthetic_author_output(case[0])
    row(output, "remove_declaration")["existing_declaration"]["name"] = "withdraw"
    assert normalize(case, output).status == "author_output_outside_admitted_scope"


@pytest.mark.parametrize("old,new", (
    ("password.equals(providedPassword)", "true"),
    ("if (!verifySavingsPassword(providedPassword)) return false;", ""),
    ("if (!debitForSavings(amount)) return false;", ""),
    ("savingBalance += amount;", "savingBalance += amount - 1;"),
    ("savingBalance += savingBalance *", "balance += balance *"),
    ("System.console().readLine()", "password"),
    ("return password.equals(providedPassword);", "while (false) {} return password.equals(providedPassword);"),
    ("private String password;", "private java.io.File password;"),
    ("return password.equals(providedPassword);", "Runtime.getRuntime().exec(\"x\"); return password.equals(providedPassword);"),
    ("return password.equals(providedPassword);", "java.sql.DriverManager.getConnection(\"x\"); return password.equals(providedPassword);"),
    ("savingBalance += amount;", "if (amount > 1000) return false; savingBalance += amount;"),
    ("return password.equals(providedPassword);", "password = \"\"; return password.equals(providedPassword);"),
    ("password.equals(providedPassword)", "password.equals(\"fixed\")"),
    ("System.console().readLine()", "\"fixed\""),
    ("private double savingBalance;", "private double savingBalance = 500;"),
    ("password.equals(providedPassword)", "password.equals(providedPassword) || true"),
    ("debitForSavings(amount)", "debitForSavings(0)"),
    ("!verifySavingsPassword(providedPassword)", "!verifySavingsPassword(providedPassword) || amount > 1000"),
))
def test_semantic_contract_and_infrastructure_drift_fail_closed(cases, old, new):
    case = cases["preserve_base_compatibility"]
    output = synthetic_author_output(case[0])
    row(output)["source_text"] = row(output)["source_text"].replace(old, new)
    result = normalize(case, output)
    assert result.candidate is None and result.status in {"author_output_semantic_drift", "author_output_outside_admitted_scope"}


@pytest.mark.parametrize("kind", ("shell_command", "replace_file", "delete_file", "rename_file", "move_file"))
def test_no_command_or_unbounded_operation_vocabulary(cases, kind):
    case = cases["preserve_base_compatibility"]
    output = synthetic_author_output(case[0])
    row(output)["operation"] = kind
    assert normalize(case, output).status == "author_output_outside_admitted_scope"


@pytest.mark.parametrize("source", ("javac bank.java", "powershell Set-Content bank.java x",
    "// javac bank.java\nprotected boolean debitForSavings(double amount) { return true; }",
    "class BankAccount { private double balance; }", "protected boolean debitForSavings(double amount) {", "\\u007d"))
def test_generated_payload_cannot_be_commands_whole_class_or_invalid_syntax(cases, source):
    case = cases["preserve_base_compatibility"]
    output = synthetic_author_output(case[0])
    row(output, "insert_member")["source_text"] = source
    assert normalize(case, output).candidate is None


@pytest.mark.parametrize("authority", ("write_authority", "filesystem_write_authority", "execution_authorized",
    "apply_authority", "filesystem_file_creation_authority", "file_creation_authority", "apply"))
def test_model_and_serialized_candidate_cannot_claim_authority(cases, authority):
    case = cases["preserve_base_compatibility"]
    output = synthetic_author_output(case[0])
    output["candidate"][authority] = True
    assert normalize(case, output).status == "author_output_authority_escalation"
    candidate = normalize(case).candidate.as_dict()
    candidate[authority] = True
    with pytest.raises(StructuralAuthorError, match="author_output_authority_escalation"):
        validate_structural_patch_candidate(candidate, admitted_scope=case[0], **case[1])


def test_escalation_and_abstention_are_typed_and_do_not_grant_scope(cases):
    case = cases["preserve_base_compatibility"]
    for code in ("missing_context", "admitted_scope_insufficient", "semantic_clarification_required",
                 "unsupported_structural_operation", "author_output_invalid", "other_bounded_reason"):
        output = {"candidate": None, "confidence": 0.1, "needs_escalation": True,
            "escalation_reason": {"code": code, "message": "Additional capability or human answer needed",
                                  "requested_capabilities": ["AnotherDefinition"]}}
        result = normalize(case, output)
        assert result.status == code and result.escalation.requested_capabilities == ("AnotherDefinition",)
        assert result.candidate is None
        output["candidate"] = synthetic_author_output(case[0])["candidate"]
        assert normalize(case, output).status == "author_output_invalid"
    assert normalize(case, {"candidate": None, "confidence": 0, "needs_escalation": False,
                            "escalation_reason": None}).status == "author_abstained"


@pytest.mark.parametrize("bad", (True, [], "bad JSON", {"candidate": None},
    '{"candidate":null,"candidate":null,"confidence":0,"needs_escalation":false,"escalation_reason":null}'))
def test_malformed_envelopes_fail_typed(cases, bad):
    assert normalize(cases["preserve_base_compatibility"], bad).status == "author_output_invalid"


@pytest.mark.parametrize("confidence", (True, float("nan"), float("inf"), -1, 2, "high"))
def test_confidence_cannot_grant_authority(cases, confidence):
    output = synthetic_author_output(cases["preserve_base_compatibility"][0])
    output["confidence"] = confidence
    assert normalize(cases["preserve_base_compatibility"], output).status == "author_output_invalid"


def test_imports_and_package_are_source_bound(cases):
    case = cases["preserve_base_compatibility"]
    output = synthetic_author_output(case[0])
    row(output)["source_text"] = "import java.util.Objects;\n" + row(output)["source_text"].replace(
        "password.equals(providedPassword)", "Objects.equals(password, providedPassword)")
    assert normalize(case, output).candidate
    for prefix in ("package rogue;\n", "import java.sql.Connection;\n", "import java.util.Objects;\n",
                   "import static java.lang.Runtime.*;\n"):
        output = synthetic_author_output(case[0])
        row(output)["source_text"] = prefix + row(output)["source_text"]
        assert normalize(case, output).candidate is None


def test_independent_validator_reconstructs_lineage_and_never_trusts_a_hash(cases):
    case = cases["preserve_base_compatibility"]
    for key in ("admission_fingerprint", "task_fingerprint", "implementation_plan_fingerprint", "repository_id",
                "source_bindings", "new_path_absence_witnesses", "candidate_fingerprint", "authority"):
        payload = normalize(case).candidate.as_dict()
        payload[key] = "forged"
        with pytest.raises(StructuralAuthorError, match="candidate_stale"):
            validate_structural_patch_candidate(payload, admitted_scope=case[0], **case[1])
    scope = case[0].as_dict()
    scope["definition_allowances"][0]["definition"]["visibility"] = "public"
    assert normalize_structural_author_output(admitted_scope=scope,
        author_output=synthetic_author_output(case[0]), **case[1]).candidate is None


def test_changed_source_or_path_witness_rejects_historical_candidate(cases):
    case = cases["preserve_base_compatibility"]
    candidate = normalize(case).candidate
    scope, fresh = case
    evidence = fresh["repository_evidence"]
    stale = replace(evidence, paths=tuple(replace(p, source_fingerprint="changed") if p.path == "bank.java" else p
                                        for p in evidence.paths))
    assert normalize(case, repository_evidence=stale).status == "reacquisition_required"
    collision = replace(evidence, paths=tuple(replace(p, state="file", source_fingerprint=sha256(b"occupied").hexdigest())
                        if p.path == "SavingAccount.java" else p for p in evidence.paths))
    with pytest.raises(StructuralAuthorError, match="admission_conflict_existing_path"):
        validate_structural_patch_candidate(candidate, admitted_scope=scope, **{**fresh, "repository_evidence": collision})
    assert candidate == normalize(case).candidate


class SyntheticAuthor:
    def __init__(self, output, callback=None):
        self.output, self.callback, self.calls, self.context = output, callback, 0, None

    def author(self, context):
        self.calls += 1
        self.context = context
        if self.callback:
            self.callback()
        return self.output


def disk_case(root, transition="preserve_base_compatibility"):
    root.mkdir(parents=True, exist_ok=True)
    scope, fresh = synthetic_case(transition, root=root)
    (root / "bank.java").write_bytes(fresh["current_source"])
    return scope, {k: v for k, v in fresh.items() if k != "repository_evidence"}


@pytest.mark.parametrize("stale", ("collision", "source", "forged", "task", "unused_may"))
def test_pre_call_fresh_validation_blocks_author_with_zero_calls(tmp_path, stale):
    scope, fresh = disk_case(tmp_path)
    author = SyntheticAuthor(synthetic_author_output(scope))
    if stale == "collision":
        (tmp_path / "SavingAccount.java").write_text("occupied", encoding="utf-8")
    elif stale == "source":
        (tmp_path / "bank.java").write_bytes(fresh["current_source"] + b"\n// changed")
    elif stale == "task":
        scope = scope.as_dict()
        scope["task_fingerprint"] = "stale"
    else:
        scope = scope.as_dict()
        scope["permitted_structural_operations"][0]["operation"] = "modify_declaration"
    result = StructuralAuthorInvocation().run(admitted_scope=scope, repository_root=tmp_path, author=author,
                                             author_call_authorized=True, **fresh)
    assert result.candidate is None and result.author_calls == author.calls == result.model_calls == 0
    if stale == "collision":
        assert result.status == "admission_conflict_existing_path"
    if stale == "source":
        assert result.status == "reacquisition_required"


@pytest.mark.parametrize("change", ("collision", "source"))
def test_post_call_collision_and_source_changes_reject_without_overwrite(tmp_path, change):
    scope, fresh = disk_case(tmp_path)
    callback = (lambda: (tmp_path / "SavingAccount.java").write_text("occupied", encoding="utf-8")) if change == "collision" else (
        lambda: (tmp_path / "bank.java").write_bytes(fresh["current_source"] + b"\n// changed"))
    author = SyntheticAuthor(synthetic_author_output(scope), callback)
    result = StructuralAuthorInvocation().run(admitted_scope=scope, repository_root=tmp_path, author=author,
                                             author_call_authorized=True, **fresh)
    assert result.candidate is None and result.author_calls == author.calls == 1 and result.model_calls == 0
    assert result.status == ("admission_conflict_existing_path" if change == "collision" else "reacquisition_required")
    if change == "collision":
        assert (tmp_path / "SavingAccount.java").read_text() == "occupied"


def test_one_shot_facade_context_separates_read_from_edit_and_never_writes(tmp_path):
    scope, fresh = disk_case(tmp_path)
    author = SyntheticAuthor(synthetic_author_output(scope))
    invocation = StructuralAuthorInvocation()
    timings = {}
    guards = ("pathlib.Path.write_bytes", "pathlib.Path.write_text", "subprocess.run", "subprocess.Popen",
              "os.system", "os.walk", "os.scandir", "os.listdir", "socket.create_connection")
    with ExitStack() as stack:
        for target in guards:
            stack.enter_context(patch(target, side_effect=AssertionError("unexpected side effect")))
        result = invocation.run(admitted_scope=scope, repository_root=tmp_path, author=author,
                                author_call_authorized=True, timings=timings, **fresh)
        repeated = invocation.run(admitted_scope=scope, repository_root=tmp_path, author=author,
                                  author_call_authorized=True, **fresh)
    assert result.candidate, (result.status, result.reason)
    assert repeated.status == "second_author_call_forbidden" and repeated.author_calls == 0
    assert author.calls == result.author_calls == 1 and result.model_calls == 0
    assert timings["provider_latency_seconds"] >= 0
    assert not (tmp_path / "SavingAccount.java").exists()
    assert (tmp_path / "bank.java").read_bytes() == fresh["current_source"]
    context = author.context.payload
    assert "original_task_meaning" in context
    read = context["[READ-ONLY SUPPORT]"]
    edit = context["[AUTHORABLE STRUCTURE]"]
    assert {r["declaration"]["name"] for r in read["declarations"]} >= {"balance", "deposit", "withdraw", "saving", "BankAccount"}
    assert all("saving::method" not in ref for o in edit["operations"] for ref in o["definition_ids"])
    assert {a["definition"]["definition_id"] for a in edit["definition_allowances"]} == {
        a.definition.identity for a in scope.definition_allowances}
    assert "ceiling_targets_not_used" not in author.context.context_json


def test_provider_failure_never_retries_and_requires_explicit_call_authorization(tmp_path):
    scope, fresh = disk_case(tmp_path)
    author = SyntheticAuthor(None, lambda: (_ for _ in ()).throw(RuntimeError("provider detail")))
    invocation = StructuralAuthorInvocation(model_backed=True)
    result = invocation.run(admitted_scope=scope, repository_root=tmp_path, author=author,
                            author_call_authorized=True, **fresh)
    assert result.status == "author_provider_failure" and result.author_calls == result.model_calls == author.calls == 1
    assert result.reason == "author_provider_failure"
    assert invocation.run(admitted_scope=scope, repository_root=tmp_path, author=author,
                          author_call_authorized=True, **fresh).status == "second_author_call_forbidden"
    unauthorized = StructuralAuthorInvocation().run(admitted_scope=scope, repository_root=tmp_path,
                                                   author=author, **fresh)
    assert unauthorized.status == "author_call_not_authorized" and unauthorized.author_calls == 0


def test_pure_normalization_and_validator_have_no_io_models_traversal_or_execution(cases):
    scope, fresh = cases["preserve_base_compatibility"]
    output = synthetic_author_output(scope)
    guards = ("core.pipeline.run_gemini_request", "core.pipeline.run_deepseek_review", "subprocess.run",
        "subprocess.Popen", "os.system", "os.walk", "os.scandir", "os.listdir", "pathlib.Path.read_bytes",
        "pathlib.Path.read_text", "pathlib.Path.write_bytes", "pathlib.Path.write_text", "pathlib.Path.open",
        "builtins.open", "socket.create_connection")
    with ExitStack() as stack:
        for target in guards:
            stack.enter_context(patch(target, side_effect=AssertionError("unexpected side effect")))
        result = normalize_structural_author_output(admitted_scope=scope, author_output=output, **fresh)
        assert result.candidate
        assert validate_structural_patch_candidate(result.candidate, admitted_scope=scope, **fresh) == result.candidate


def test_unused_constructor_may_cannot_be_recovered_from_nested_plan(cases):
    case = cases["nested"]
    unused = case[1]["plan"].planner_proposal.ceiling_targets_not_used
    assert any(t.name == "subclass_initialization_capability" for t in unused)
    output = synthetic_author_output(case[0])
    injected = deepcopy(row(output, "insert_member"))
    injected["definition_ids"] = ["BankAccount::BankAccount::constructor"]
    injected["source_text"] = "public BankAccount(double opening) {}"
    output["candidate"]["operations"].append(injected)
    assert normalize(case, output).status == "author_output_outside_admitted_scope"


def test_bookkeeping_reversal_preserves_exact_dirty_entry_receipts():
    from tests._patch_author_structural1_maintenance import before_patch_author_structural1
    root = Path(__file__).resolve().parents[1]
    receipt = json.loads((root / "tests/fixtures/patch_author_structural1_reversal.json").read_text())
    for record in receipt["reversals"]:
        restored = before_patch_author_structural1(record["path"], (root / record["path"]).read_bytes())
        assert sha256(restored).hexdigest() == record["entry_sha256"]


def test_admitted_package_is_kept_and_wrong_package_rejected(tmp_path):
    import scripts.replay_patch_scope_expand1 as expand_replay
    from scripts.replay_patch_scope_expand1 import fixture_inputs
    original = expand_replay.project_class_semantic_context
    def packaged(**kwargs):
        return original(**{**kwargs, "file": "edu/bank.java"})
    source = "package edu;\n" + fixture_inputs()["current_source"].decode()
    with patch.object(expand_replay, "project_class_semantic_context", packaged):
        case = synthetic_case(root=tmp_path, source=source, path="edu/SavingAccount.java")
    result = normalize(case)
    assert result.candidate, (result.status, result.reason)
    assert row(synthetic_author_output(case[0]))["source_text"].startswith("package edu;")
    assert not (tmp_path / "edu/SavingAccount.java").exists()
    output = synthetic_author_output(case[0])
    row(output)["source_text"] = row(output)["source_text"].replace("package edu;", "package other;")
    assert normalize(case, output).status == "author_output_outside_admitted_scope"


@pytest.mark.parametrize("operation,state", (("insert_member", "balance"), ("draft_new_file", "savingBalance")))
def test_local_shadow_cannot_substitute_for_bound_contract_state(cases, operation, state):
    case = cases["preserve_base_compatibility"]
    output = synthetic_author_output(case[0])
    target = row(output, operation)
    if operation == "insert_member":
        target["source_text"] = target["source_text"].replace("if (amount <= balance)",
            "double balance = 100; if (amount <= balance)")
    else:
        target["source_text"] = target["source_text"].replace("savingBalance += amount;",
            "double savingBalance = 0; savingBalance += amount;")
    assert normalize(case, output).status == "author_output_semantic_drift"
