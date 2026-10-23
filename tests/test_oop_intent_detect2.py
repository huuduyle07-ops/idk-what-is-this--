"""OOP.INTENT.DETECT.2: missing future-design contract admission."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import io
import json
import os
import socket
import subprocess
import time

import pytest

from tests.test_auth_web1 import web

from core.class_semantic_context import project_class_semantic_context
from core.input_understanding import understand_request
from core.oop_intent_detector import (
    AUTH_DIMENSIONS,
    DISPOSITIONS,
    SAVINGS_DIMENSIONS,
    detect_missing_future_design_contract,
)
from core.oop_intent_session import (
    make_stored_future_design_gap,
    validate_stored_gap,
)
from core.proposed_design_intent import project_proposed_design_intent
from core.repository_identity import derive_repository_id
from core.treesitter_parse import structural_definitions


BANK = """class BankAccount {
  private double balance;
  BankAccount(double opening) { this.balance = opening; }
  void deposit(double amount) { balance += amount; }
  void withdraw(double amount) { balance -= amount; }
  void saving(double rate) { balance += balance * rate; }
}"""

BANK2_TASK = """SavingAccount extends BankAccount.

savingBalance should belong only to SavingAccount,
because not every BankAccount needs savings state.

Using the savings functionality should depend on the user
entering the correct password.

The current code does not yet contain password/authentication support."""


def _context(source: str, repo, *, status: str = "complete"):
    raw = source.encode("utf-8")
    target = next(item for item in structural_definitions(source, "java")["definitions"]
                  if item["kind"] == "class" and item["name"] == "BankAccount")
    context = project_class_semantic_context(
        raw=raw, language="java", file="bank.java", target=target,
        expected_source_fingerprint=hashlib.sha256(raw).hexdigest(),
        repository_id=derive_repository_id(repo))
    if status != "complete":
        context = replace(context, status=status, overflow=("fields",))
    return context, raw


def _inputs(repo, task: str = BANK2_TASK, source: str = BANK):
    contract = understand_request(task)
    design = project_proposed_design_intent(contract)
    context, raw = _context(source, repo)
    return contract, design, context, raw


def _detect(repo, *, task: str = BANK2_TASK, source: str = BANK,
            design=None, context=None, raw=None):
    contract, projected, acquired, source_raw = _inputs(repo, task, source)
    return detect_missing_future_design_contract(
        task_contract=contract,
        design_intent=projected if design is None else design,
        current_context=acquired if context is None else context,
        current_source=source_raw if raw is None else raw,
        repository_id=derive_repository_id(repo)), (contract, projected, acquired, source_raw)


def test_bank2_admits_exactly_one_grouped_future_design_gap(tmp_path):
    result, _ = _detect(tmp_path)
    assert result.status == "clarification_required"
    assert len(result.possible_intent_gaps) == 1
    gap = result.gap
    assert gap is not None and gap.dimension == "future_design_contract"
    assert set(gap.subdimensions) == AUTH_DIMENSIONS | SAVINGS_DIMENSIONS
    assert len(gap.unresolved_dimension_refs) == len(gap.subdimensions)
    assert len(set(gap.unresolved_dimension_refs)) == len(gap.subdimensions)
    assert gap.design_fingerprint == result.design_fingerprint
    assert gap.task_contract_fingerprint == result.task_contract_fingerprint
    assert gap.repository_id == derive_repository_id(tmp_path)
    assert gap.question.startswith("You've already specified that SavingAccount extends BankAccount")
    assert "savingBalance belongs only to SavingAccount" in gap.question
    assert "successful password verification" in gap.question
    assert "source layout" not in gap.question.casefold()
    assert 2 <= len(gap.alternatives) <= 4
    rendered = (gap.question + " " + " ".join(item.description for item in gap.alternatives)).casefold()
    assert not {"sqlite", "csv", "json", "bcrypt", "sha-256", "jwt", "oauth"}.intersection(
        rendered.replace("/", " ").replace("-", " ").split())


def test_bank2_comparison_and_dimension_policy_are_typed(tmp_path):
    result, _ = _detect(tmp_path)
    assert {item.kind for item in result.comparisons} == {
        "inheritance_transition", "state_transition", "authentication_transition"}
    text = " ".join(item.description for item in result.comparisons)
    assert "SavingAccount" in text and "savingBalance" in text
    assert "repository-wide absence" in text
    assert all(item.current_provenance == "current_source_fact" for item in result.comparisons)
    assert all(item.desired_provenance == "explicit_human" for item in result.comparisons)
    assert all(item.is_defect is False for item in result.comparisons)
    dispositions = {item.dimension: item.disposition for item in result.assessments}
    assert all(dispositions[name] == "human_owned_material"
               for name in AUTH_DIMENSIONS | SAVINGS_DIMENSIONS)
    assert dispositions["source_layout"] == "deferred_implementation"
    assert dispositions["subclass_creation_lifecycle"] == "deferred_implementation"
    assert dispositions["verification_failure_behavior"] == "irrelevant_to_current_transition"
    assert dispositions["account_identity"] == "irrelevant_to_current_transition"
    assert set(dispositions.values()) <= DISPOSITIONS


def test_bank2_has_no_author_candidate_scope_or_authority(tmp_path):
    result, _ = _detect(tmp_path)
    assert result.author_calls == result.model_calls == result.repository_traversals == 0
    assert result.patch_candidate is None and result.patch == ""
    assert result.authority == "read_only"
    assert result.write_authority is False
    assert result.execution_authorized is False
    assert result.auto_apply is False
    assert result.repair_scope_authority is False
    assert result.total_seconds >= 0
    assert all(getattr(result, field) >= 0 for field in (
        "projection_validation_seconds", "current_vs_desired_seconds",
        "materiality_classification_seconds", "gap_construction_seconds"))


@pytest.mark.parametrize("suffix", [
    ("Store a password only in memory on SavingAccount for this exercise. No persistence. "
     "Savings transfers amount from inherited balance into savingBalance. "
     "saving() applies interest only to savingBalance."),
    "Store a password only in memory on SavingAccount for this exercise. No persistence.",
    ("Savings transfers amount from inherited balance into savingBalance. "
     "saving() applies interest only to savingBalance."),
])
def test_raw_resolved_and_partial_answers_fail_closed_at_frozen_projection_boundary(tmp_path, suffix):
    task = ("SavingAccount extends BankAccount. savingBalance belongs only to SavingAccount. "
            "Savings functionality requires successful password verification. " + suffix)
    result, (_, design, _, _) = _detect(tmp_path, task=task)
    assert any(item.status == "not_resolved_by_projection"
               for item in design.unresolved_dimensions)
    assert result.status == "projection_bounded" and result.gap is None
    assert result.author_calls == 0 and result.patch_candidate is None


def test_dimension_scoped_question_policy_does_not_reopen_resolved_groups(tmp_path):
    from core.oop_intent_detector import _question_and_alternatives

    _, design, _, _ = _inputs(tmp_path)
    savings_question, savings_options = _question_and_alternatives(
        design, dimensions=SAVINGS_DIMENSIONS)
    assert "remaining savings behavior" in savings_question
    assert "credential" not in savings_question.casefold()
    assert all("credential" not in item.description.casefold() for item in savings_options)
    auth_question, auth_options = _question_and_alternatives(
        design, dimensions=AUTH_DIMENSIONS)
    assert "remaining verification contract" in auth_question
    assert "how savingBalance is funded" not in auth_question
    assert all("fund savingbalance" not in item.description.casefold() for item in auth_options)


def test_persistent_intent_fails_closed_without_selecting_storage_technology(tmp_path):
    task = ("SavingAccount extends BankAccount. savingBalance belongs only to SavingAccount. "
            "Savings functionality requires successful password verification. "
            "Credentials must persist across runs.")
    result, _ = _detect(tmp_path, task=task)
    assert result.status == "projection_bounded" and result.gap is None
    text = result.to_json().casefold()
    assert all(item not in text for item in ("sqlite", "csv", "database", "hash_algorithm", "bcrypt"))


@pytest.mark.parametrize("task", [
    "Review BankAccount logic; is saving correct?",
    "What if SavingAccount extended BankAccount?",
    "Add a comment mentioning password.",
])
def test_current_review_suggestion_and_password_word_do_not_trigger(tmp_path, task):
    result, _ = _detect(tmp_path, task=task)
    assert result.status == "not_applicable"
    assert result.gap is None


def test_conflict_fails_closed_without_question(tmp_path):
    task = "SavingAccount extends BankAccount. Do not use inheritance."
    result, _ = _detect(tmp_path, task=task)
    assert result.status == "design_conflict"
    assert result.gap is None and result.author_calls == 0


def test_stale_source_and_bounded_context_fail_closed(tmp_path):
    result, (_, design, context, raw) = _detect(tmp_path)
    stale, _ = _detect(tmp_path, design=design, context=context, raw=raw + b"\n// stale")
    assert stale.status == "stale_source" and stale.gap is None
    bounded_context = replace(context, status="bounded", overflow=("fields",))
    bounded, _ = _detect(tmp_path, design=design, context=bounded_context, raw=raw)
    assert bounded.status == "source_bounded" and bounded.gap is None


def test_conflicting_binding_and_relevant_projection_omission_fail_closed(tmp_path):
    contract, design, context, raw = _inputs(tmp_path)
    mismatched = replace(design, task_contract_fingerprint="0" * 64)
    result = detect_missing_future_design_contract(
        task_contract=contract, design_intent=mismatched,
        current_context=context, current_source=raw,
        repository_id=derive_repository_id(tmp_path))
    assert result.status == "projection_mismatch" and result.gap is None
    first = design.unresolved_dimensions[0]
    incomplete = replace(design, unresolved_dimensions=(
        replace(first, status="not_resolved_by_projection"),
        *design.unresolved_dimensions[1:]))
    result = detect_missing_future_design_contract(
        task_contract=contract, design_intent=incomplete,
        current_context=context, current_source=raw,
        repository_id=derive_repository_id(tmp_path))
    assert result.status == "projection_mismatch" and result.gap is None


def test_nonhuman_commitment_provenance_is_rejected(tmp_path):
    contract, design, context, raw = _inputs(tmp_path)
    relation = design.relationships[0]
    forged = replace(relation, evidence=replace(
        relation.evidence, provenance="inferred_semantic_interpretation"))
    design = replace(design, relationships=(forged,))
    result = detect_missing_future_design_contract(
        task_contract=contract, design_intent=design,
        current_context=context, current_source=raw,
        repository_id=derive_repository_id(tmp_path))
    assert result.status == "provenance_rejected" and result.gap is None


def test_current_bank_password_field_does_not_settle_future_saving_account_contract(tmp_path):
    source = BANK.replace("private double balance;", "private double balance;\n  private String password;")
    result, _ = _detect(tmp_path, source=source)
    dispositions = {item.dimension: item.disposition for item in result.assessments}
    assert all(dispositions[name] == "human_owned_material" for name in AUTH_DIMENSIONS)
    assert set(result.gap.subdimensions) == AUTH_DIMENSIONS | SAVINGS_DIMENSIONS


def test_current_wrong_owner_state_is_reported_as_current_not_desired(tmp_path):
    source = BANK.replace("private double balance;", "private double balance;\n  private double savingBalance;")
    result, _ = _detect(tmp_path, source=source)
    state = next(item for item in result.comparisons if item.kind == "state_transition")
    assert "declared on the acquired BankAccount context" in state.current
    assert state.desired == "savingBalance belongs only to SavingAccount"
    assert state.is_defect is False


def test_stored_gap_reuses_ui_schema_and_binds_detector_freshness(tmp_path):
    (tmp_path / "bank.java").write_text(BANK, encoding="utf-8")
    result, _ = _detect(tmp_path)
    stored = make_stored_future_design_gap(
        result, task_text=BANK2_TASK, repo_path=str(tmp_path))
    validated = validate_stored_gap(
        stored, task_text=BANK2_TASK, repo_path=str(tmp_path))
    assert validated["gap_id"] == stored["gap_id"]
    assert validated["admission_schema"] == "oop_intent_detect_2_v1"
    assert validated["scope_expansion"] == "deferred"
    assert validated["design_fingerprint"] == result.design_fingerprint
    assert len(validated["current_facts"]) == 3
    assert {item["kind"] for item in validated["interpretations"]} == {
        "future_authentication_contract", "future_savings_contract"}
    auth_refs = set(validated["interpretations"][0]["evidence_refs"])
    savings_refs = set(validated["interpretations"][1]["evidence_refs"])
    assert auth_refs and savings_refs and auth_refs.isdisjoint(savings_refs)
    forged = dict(stored)
    forged.pop("gap_id")
    forged["design_fingerprint"] = "0" * 64
    forged["gap_id"] = hashlib.sha256(json.dumps(
        forged, sort_keys=True, ensure_ascii=False,
        separators=(",", ":")).encode("utf-8")).hexdigest()
    with pytest.raises(ValueError, match="malformed_oop_gap"):
        validate_stored_gap(forged, task_text=BANK2_TASK, repo_path=str(tmp_path))


def test_analysis_adapter_creates_one_durable_wait_without_provider(tmp_path, monkeypatch):
    from core.analysis_evidence import AnalysisEvidence, AnalysisEvidenceItem
    from web import session_store
    from web.oop_intent_adapter import admit_oop_review_wait

    (tmp_path / "bank.java").write_text(BANK, encoding="utf-8")
    monkeypatch.setattr(session_store, "SESSION_FILE", tmp_path / "sessions.json")
    evidence = AnalysisEvidence(items=(AnalysisEvidenceItem(
        path="bank.java", role="requested_path", text=BANK, truncated=False),))
    first = admit_oop_review_wait(
        evidence=evidence, repo_path=str(tmp_path), task_text=BANK2_TASK)
    second = admit_oop_review_wait(
        evidence=evidence, repo_path=str(tmp_path), task_text=BANK2_TASK)
    assert first["status"] == "waiting_for_clarification"
    assert first["clarification_kind"] == "oop_intent"
    assert first["patch_candidate"] is None and first["patch"] == ""
    assert first["patch_author_calls"] == 0
    assert first["clarification_session_id"] == second["clarification_session_id"]
    sessions = session_store.load_sessions()
    assert len(sessions) == 1 and sessions[0]["status"] == "waiting_for_clarification"
    assert sessions[0]["result"]["patch_candidate"] is None


def test_analysis_adapter_reacquires_exact_crlf_bytes_without_traversal(tmp_path, monkeypatch):
    from core.analysis_evidence import AnalysisEvidence, AnalysisEvidenceItem
    from core.oop_intent_session import source_freshness
    from web import session_store
    from web.oop_intent_adapter import admit_oop_review_wait

    raw = BANK.replace("\n", "\r\n").encode("utf-8")
    (tmp_path / "bank.java").write_bytes(raw)
    monkeypatch.setattr(session_store, "SESSION_FILE", tmp_path / "sessions.json")
    evidence = AnalysisEvidence(items=(AnalysisEvidenceItem(
        path="bank.java", role="requested_path", text=BANK, truncated=False),))
    waiting = admit_oop_review_wait(
        evidence=evidence, repo_path=str(tmp_path), task_text=BANK2_TASK)
    session = session_store.find_session(waiting["clarification_session_id"])
    assert session["oop_intent_gap"]["source_fingerprint"] == hashlib.sha256(raw).hexdigest()
    assert source_freshness(session["oop_intent_gap"], repo_path=str(tmp_path)) == "current"


def test_analysis_adapter_skips_unrelated_singleton_java_context(tmp_path, monkeypatch):
    from core.analysis_evidence import AnalysisEvidence, AnalysisEvidenceItem
    from web import session_store
    from web.oop_intent_adapter import admit_oop_review_wait

    helper = "class Helper { void run() {} }"
    (tmp_path / "other.java").write_bytes(helper.encode("utf-8"))
    (tmp_path / "bank.java").write_bytes(BANK.encode("utf-8"))
    repository_id = derive_repository_id(tmp_path)
    monkeypatch.setattr(session_store, "SESSION_FILE", tmp_path / "sessions.json")
    evidence = AnalysisEvidence(items=(
        AnalysisEvidenceItem(
            path="other.java", role="implementation_source", text=helper,
            truncated=False, repository_id=repository_id),
        AnalysisEvidenceItem(
            path="bank.java", role="requested_path", text=BANK, truncated=False,
            repository_id=repository_id),
    ))
    waiting = admit_oop_review_wait(
        evidence=evidence, repo_path=str(tmp_path), task_text=BANK2_TASK)
    detection = waiting["oop_intent_detection"]
    assert detection["source_path"] == "bank.java"
    assert detection["class_identity"] == "BankAccount"


def test_future_no_gap_preserves_independent_current_review(tmp_path, monkeypatch):
    from core.analysis_evidence import AnalysisEvidence, AnalysisEvidenceItem
    from web import session_store
    from web.oop_intent_adapter import (
        admit_future_design_control_wait,
        admit_oop_review_wait,
    )

    task = "SavingAccount extends BankAccount. Review BankAccount logic; is saving correct?"
    (tmp_path / "bank.java").write_bytes(BANK.encode("utf-8"))
    repository_id = derive_repository_id(tmp_path)
    monkeypatch.setattr(session_store, "SESSION_FILE", tmp_path / "sessions.json")
    evidence = AnalysisEvidence(items=(AnalysisEvidenceItem(
        path="bank.java", role="requested_path", text=BANK, truncated=False,
        repository_id=repository_id),))
    waiting = admit_oop_review_wait(
        evidence=evidence, repo_path=str(tmp_path), task_text=task)
    assert waiting["status"] == "waiting_for_clarification"
    assert "oop_intent_detection" not in waiting
    stored = session_store.load_sessions()[0]["oop_intent_gap"]
    assert stored["dimension"] == "domain_state_overlap"

    control = {"patch_intent": {
        "file": "bank.java", "target_symbol": "BankAccount",
    }}
    future, owned = admit_future_design_control_wait(
        control=control, repo_path=str(tmp_path), task_text=task)
    assert future is None and owned is False


def test_control_adapter_waits_before_scope_expansion_and_preserves_source(tmp_path, monkeypatch):
    from web import session_store
    from web.oop_intent_adapter import admit_future_design_control_wait

    source_path = tmp_path / "bank.java"
    source_path.write_text(BANK, encoding="utf-8")
    monkeypatch.setattr(session_store, "SESSION_FILE", tmp_path / "sessions.json")
    control = {
        "patch_intent": {
            "file": "bank.java", "relative_path": "bank.java",
            "target_symbol": "BankAccount", "target_node_kind": "class",
            "language": "java", "source_snippet": BANK,
        },
    }
    before = source_path.read_bytes()
    wait, owned = admit_future_design_control_wait(
        control=control, repo_path=str(tmp_path), task_text=BANK2_TASK)
    assert owned is True and wait["status"] == "waiting_for_clarification"
    assert wait["patch_author_calls"] == 0 and wait["patch_candidate"] is None
    assert "repair_scope" not in control and "repair_scope" not in control["patch_intent"]
    assert source_path.read_bytes() == before
    session = session_store.load_sessions()[0]
    assert session["control"] == control
    assert session["oop_intent_gap"]["scope_expansion"] == "deferred"


def test_non_oop_control_bypasses_detector_and_conflict_fails_closed(tmp_path, monkeypatch):
    from web import session_store
    from web.oop_intent_adapter import admit_future_design_control_wait

    monkeypatch.setattr(session_store, "SESSION_FILE", tmp_path / "sessions.json")
    (tmp_path / "a.py").write_text("def value():\n    return 1\n", encoding="utf-8")
    ordinary, owned = admit_future_design_control_wait(
        control={"patch_intent": {"file": "a.py"}}, repo_path=str(tmp_path),
        task_text="fix a.py: value() must return 2")
    assert ordinary is None and owned is False
    (tmp_path / "bank.java").write_text(BANK, encoding="utf-8")
    conflict, owned = admit_future_design_control_wait(
        control={"patch_intent": {"file": "bank.java", "target_symbol": "BankAccount"}},
        repo_path=str(tmp_path),
        task_text="SavingAccount extends BankAccount. Do not use inheritance.")
    assert owned is True and conflict["status"] == "design_conflict"
    assert conflict["patch_author_calls"] == 0 and conflict["patch_candidate"] is None


def test_future_answer_stops_at_typed_continuation_without_author(web, monkeypatch):
    from web import session_store
    from web.oop_intent_adapter import admit_future_design_control_wait

    (web.repo / "bank.java").write_text(BANK, encoding="utf-8")
    control = {"patch_intent": {"file": "bank.java", "target_symbol": "BankAccount"}}
    waiting, _ = admit_future_design_control_wait(
        control=control, repo_path=str(web.repo), task_text=BANK2_TASK)
    session = session_store.find_session(waiting["clarification_session_id"])

    def forbidden(*args, **kwargs):
        raise AssertionError("future-design free text cannot reach an author")

    monkeypatch.setattr(web.wa, "run_gemini_request", forbidden)
    with web.app.test_request_context("/oop_intent/answer", method="POST", data={
        "session_id": session["id"], "gap_id": session["oop_intent_gap"]["gap_id"],
        "repo_path": session["repo_path"], "answer": "Use an in-memory password.",
    }):
        result = web.wa.answer_oop_intent()
    assert result["status"] == "clarification_projected"
    assert result["oop_intent_detection"]["status"] == "clarification_required"
    assert result["patch"] == "" and result["patch_candidate"] is None
    assert result["usage"]["patch_author_calls"] == 0
    assert session_store.find_session(session["id"])["status"] == result["status"]


def test_generate_candidates_stops_before_all_three_authors(web, monkeypatch):
    (web.repo / "bank.java").write_text(BANK, encoding="utf-8")
    control = {"patch_intent": {"file": "bank.java", "target_symbol": "BankAccount"},
               "query": BANK2_TASK}

    def forbidden(*args, **kwargs):
        raise AssertionError("candidate prompt/provider must not run before clarification")

    monkeypatch.setattr(web.wa, "build_control_prompt", forbidden)
    monkeypatch.setattr(web.wa, "run_gemini_request", forbidden)
    monkeypatch.setattr(web.wa, "run_deepseek_review", forbidden)
    result = web.wa._generate_candidates_from_control(str(web.repo), control)
    assert result["status"] == "waiting_for_clarification"
    assert result["candidates"] == [] and result["patch_candidate"] is None
    assert result["usage"]["patch_author_calls"] == 0


def test_terminal_stops_before_draft_author(web, monkeypatch):
    import main as terminal

    (web.repo / "bank.java").write_text(BANK, encoding="utf-8")
    state = type("TerminalState", (), {
        "interface": "agent", "is_project_input": True,
        "control_result": {"patch_intent": {
            "file": "bank.java", "target_symbol": "BankAccount"}},
        "live_route": {"change_requested": True},
        "repo_path": str(web.repo), "user_input": BANK2_TASK,
    })()

    def forbidden(*args, **kwargs):
        raise AssertionError("terminal draft author must not run before clarification")

    monkeypatch.setattr(terminal, "init_db", lambda: None)
    monkeypatch.setattr(terminal, "create_agent_state", lambda: state)
    monkeypatch.setattr(terminal, "run_draft_pipeline", forbidden)
    monkeypatch.setattr(terminal.sys, "argv", ["cattus", "--terminal"])
    terminal.main()
    from web.session_store import load_sessions
    assert len(load_sessions()) == 1
    assert load_sessions()[0]["status"] == "waiting_for_clarification"


def test_future_detector_is_wired_before_scope_construction():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    app = (root / "web" / "app.py").read_text(encoding="utf-8")
    runner = (root / "web" / "runner.py").read_text(encoding="utf-8")
    main = (root / "main.py").read_text(encoding="utf-8")
    app_start = app.index("def _generate_patch_from_control")
    app_end = app.index("def ", app_start + 4)
    app_block = app[app_start:app_end]
    assert (app_block.index("admit_future_design_control_wait")
            < app_block.index("\n    prompt = build_control_prompt"))
    runner_future = runner.index("admit_future_design_control_wait")
    runner_scope = runner.index("\n            build_control_prompt(", runner_future)
    assert runner_future < runner_scope
    candidate_start = app.index("def _generate_candidates_from_control")
    candidate_end = app.index("def ", candidate_start + 4)
    candidate = app[candidate_start:candidate_end]
    assert candidate.index("admit_future_design_control_wait") < candidate.index("build_control_prompt")
    assert main.index("admit_future_design_control_wait") < main.index("draft = run_draft_pipeline")


def test_detector_is_deterministic_model_free_and_traversal_free(tmp_path, monkeypatch):
    contract, design, context, raw = _inputs(tmp_path)

    def forbidden(*args, **kwargs):
        raise AssertionError("DETECT.2 cannot perform this side effect")

    with monkeypatch.context() as guard:
        guard.setattr("builtins.open", forbidden)
        guard.setattr(io, "open", forbidden)
        guard.setattr(os, "walk", forbidden)
        guard.setattr(os, "scandir", forbidden)
        guard.setattr(socket, "create_connection", forbidden)
        guard.setattr(subprocess, "run", forbidden)
        first = detect_missing_future_design_contract(
            task_contract=contract, design_intent=design,
            current_context=context, current_source=raw,
            repository_id=derive_repository_id(tmp_path))
        second = detect_missing_future_design_contract(
            task_contract=contract, design_intent=design,
            current_context=context, current_source=raw,
            repository_id=derive_repository_id(tmp_path))
    assert first.gap == second.gap
    assert first.comparisons == second.comparisons
    assert first.assessments == second.assessments
    assert first.model_calls == second.model_calls == 0
    assert first.repository_traversals == second.repository_traversals == 0


def test_detector_performance_is_local_and_bounded(tmp_path):
    contract, design, context, raw = _inputs(tmp_path)
    repository_id = derive_repository_id(tmp_path)
    started = time.perf_counter()
    results = [detect_missing_future_design_contract(
        task_contract=contract, design_intent=design,
        current_context=context, current_source=raw,
        repository_id=repository_id) for _ in range(100)]
    elapsed_ms = (time.perf_counter() - started) * 1000
    assert all(item.status == "clarification_required" for item in results)
    assert elapsed_ms < 2000
