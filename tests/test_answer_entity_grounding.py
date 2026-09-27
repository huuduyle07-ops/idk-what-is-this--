from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

from core.answer_entity_grounding import (
    GROUNDED_EXECUTION_OBSERVED,
    GROUNDED_EXISTING,
    HYPOTHETICAL,
    MAX_RECEIPT_ENTITIES,
    PROPOSED_NEW,
    UNVERIFIED_MODEL_ASSERTION,
    USER_SUPPLIED_UNVERIFIED,
    RepositoryEntityEvidence,
    ground_answer_for_display,
    ground_answer_text,
    ground_state_answer,
)
from core.analysis_evidence import AnalysisEvidence, AnalysisEvidenceItem
from core.agent_state import AgentState


def _evidence(
    *,
    repository_id: str = "cattus-repo",
    name: str = "C.A.T.T.U.S",
    aliases: tuple[str, ...] = ("C.A.T.T.U.S",),
    paths: tuple[str, ...] = (),
    symbols: tuple[str, ...] = (),
    analysis: tuple[str, ...] = (),
    execution: tuple[str, ...] = (),
    current: bool = True,
) -> RepositoryEntityEvidence:
    return RepositoryEntityEvidence(
        repository_id=repository_id,
        display_name=name,
        aliases=frozenset(aliases),
        existing_paths=frozenset(paths),
        source_symbols=frozenset(symbols),
        analysis_paths=frozenset(analysis),
        execution_paths=frozenset(execution),
        current=current,
    )


def _statuses(findings):
    return {finding.reference: finding.status for finding in findings}


def test_nonexistent_file_assertions_are_downgraded_and_reported_as_an_evidence_gap():
    text = (
        "The bug is in patcher/generator.py::PatchGenerator.generate. "
        "config/settings.py::ConfigurationOptions supplies the bad option."
    )

    grounded, findings = ground_answer_text(text, [_evidence(paths=("main.py",))])

    # ANSWER.GROUND.LIVE.3 — the downgrade is span-local.  The claim is
    # retracted at the entity; the prose around it is no longer deleted.
    assert "The bug is in" in grounded
    assert "supplies the bad option" in grounded
    assert grounded.count("(not established in the current evidence)") == 2
    assert "Repository evidence gap" in grounded
    assert "not treating them as a real source location" in grounded
    assert set(_statuses(findings).values()) == {UNVERIFIED_MODEL_ASSERTION}


def test_real_file_does_not_ground_a_fabricated_symbol():
    grounded, findings = ground_answer_text(
        "The resolver is core/code_dna.py::MagicIndentResolver.",
        [_evidence(paths=("core/code_dna.py",))],
    )

    assert "Repository evidence gap" in grounded
    assert findings[0].status == UNVERIFIED_MODEL_ASSERTION


def test_real_source_backed_file_and_symbol_remain_precise():
    evidence = _evidence(
        paths=("core/code_dna.py",),
        symbols=("core/code_dna.py::_classify_indent",),
    )
    text = "Inspect core/code_dna.py::_classify_indent in core/code_dna.py."

    grounded, findings = ground_answer_text(text, [evidence])

    assert grounded == text
    assert set(_statuses(findings).values()) == {GROUNDED_EXISTING}


def test_t1_t2_t3_legacy_repository_symbols_remain_unchanged():
    evidence = _evidence(
        paths=("calc.py", "solution.py"),
        symbols=("calc.py::add", "solution.py::length_of_longest_substring"),
    )
    text = (
        "Use calc.py::add for T1/T2 and "
        "solution.py::length_of_longest_substring for T3."
    )

    grounded, findings = ground_answer_text(text, [evidence])

    assert grounded == text
    assert set(_statuses(findings).values()) == {GROUNDED_EXISTING}


def test_analysis_evidence_path_is_grounded_without_code_index_membership():
    evidence = _evidence(analysis=("docs/architecture.md",))
    text = "The bounded analysis read docs/architecture.md."

    grounded, findings = ground_answer_text(text, [evidence])

    assert grounded == text
    assert findings[0].status == GROUNDED_EXISTING


def test_traceback_path_is_execution_observed_but_does_not_ground_a_symbol():
    evidence = _evidence(execution=("main.py",))

    file_text, file_findings = ground_answer_text("Validation named main.py:2.", [evidence])
    symbol_text, symbol_findings = ground_answer_text(
        "Validation proves main.py::InventedSymbol.", [evidence]
    )

    assert file_text == "Validation named main.py:2."
    assert file_findings[0].status == GROUNDED_EXECUTION_OBSERVED
    assert "Repository evidence gap" in symbol_text
    assert symbol_findings[0].status == UNVERIFIED_MODEL_ASSERTION


def test_external_library_traceback_path_does_not_become_repository_evidence():
    state = SimpleNamespace(
        repo_path=os.getcwd(),
        project_tag="C.A.T.T.U.S",
        user_input="Explain the failure",
        repository_inventory=SimpleNamespace(
            canonical_root=os.getcwd(),
            entries=(SimpleNamespace(relative_path="main.py"),),
        ),
        analysis_evidence=None,
        repository_graph=None,
        control_result=None,
        validation_output=(
            "C:/Python/Lib/site-packages/example_package/worker.py:41: failure"
        ),
        answer_grounding_evidence_current=True,
    )
    block = {
        "summary": "The bug is in example_package/worker.py.",
        "patch_plan": [],
        "patch_candidate": None,
        "write_authority": False,
    }

    _, _, display, receipt = ground_answer_for_display(state, "", block)

    assert "Repository evidence gap" in display["summary"]
    assert receipt["unverified_entity_count"] == 1
    assert receipt["authority_effect"] == "none"


def test_well_known_external_product_name_is_not_a_repository_file_claim():
    text = (
        "The Node.js front end is unrelated; Vue.js is not used either, "
        "and Socket.io never reaches the Python side."
    )

    grounded, findings = ground_answer_text(text, [_evidence(paths=("main.py",))])

    assert grounded == text
    assert findings == ()


def test_missing_source_files_are_still_downgraded_beside_a_product_name():
    evidence = _evidence(paths=("main.py",))

    nested, nested_findings = ground_answer_text("src/app.js is broken.", [evidence])
    flat, flat_findings = ground_answer_text("app.js is broken.", [evidence])
    stem, stem_findings = ground_answer_text("types.ts is broken.", [evidence])

    for grounded, findings in (
        (nested, nested_findings),
        (flat, flat_findings),
        (stem, stem_findings),
    ):
        assert "Repository evidence gap" in grounded
        # LIVE.3: the file claim is retracted, the surrounding predicate stays.
        assert "is broken" in grounded
        assert "(not established in the current evidence)" in grounded
        assert findings[0].status == UNVERIFIED_MODEL_ASSERTION


def test_repository_evidence_wins_over_the_external_product_name_guard():
    text = "node.js configures the bundler."

    grounded, findings = ground_answer_text(text, [_evidence(paths=("node.js",))])

    assert grounded == text
    assert findings[0].status == GROUNDED_EXISTING


def test_a_file_signal_takes_a_product_name_back_out_of_the_guard():
    evidence = _evidence(paths=("main.py",))

    symbol_text, symbol_findings = ground_answer_text(
        "Node.js::Server handles the socket.", [evidence]
    )
    line_text, line_findings = ground_answer_text(
        "The failure is at Node.js:12.", [evidence]
    )

    assert "Repository evidence gap" in symbol_text
    assert symbol_findings[0].status == UNVERIFIED_MODEL_ASSERTION
    assert "Repository evidence gap" in line_text
    assert line_findings[0].status == UNVERIFIED_MODEL_ASSERTION


def test_user_supplied_missing_path_is_retained_only_as_unverified():
    grounded, findings = ground_answer_text(
        "config/settings.py contains an invalid option.",
        [_evidence()],
        user_input="Why is config/settings.py broken?",
    )

    assert "I could not establish" in grounded
    assert '"config/settings.py"' in grounded
    # LIVE.3: the user's own referent is still discussable in place.
    assert "config/settings.py (not established in the current evidence)" in grounded
    assert "contains an invalid option" in grounded
    assert findings[0].status == USER_SUPPLIED_UNVERIFIED


def test_create_file_plan_path_is_proposed_new_not_existing_source():
    state = SimpleNamespace(
        repo_path=None,
        user_input="Create priority support",
        project_tag="",
    )
    block = {
        "summary": "Create new_priority.py for priority support.",
        "patch_plan": [
            {"op": "create_file", "relative_path": "new_priority.py", "content": "X = 1\n"}
        ],
        "patch_candidate": None,
        "write_authority": False,
    }

    _, _, display, receipt = ground_answer_for_display(state, "", block)

    assert display["summary"] == block["summary"]
    statuses = {item["status"] for item in receipt["entity_statuses"]}
    assert PROPOSED_NEW in statuses
    assert receipt["unverified_entity_count"] == 0
    assert display["write_authority"] is False


def test_clearly_hypothetical_path_is_not_reported_as_fabricated():
    text = "For example, a project could put this in src/generator.py."

    grounded, findings = ground_answer_text(text, [_evidence()])

    assert grounded == text
    assert findings[0].status == HYPOTHETICAL


def test_paths_in_fenced_examples_are_not_treated_as_repository_claims():
    text = "A generic shell example:\n```sh\npython src/generator.py\n```"

    grounded, findings = ground_answer_text(text, [_evidence()])

    assert grounded == text
    assert findings == ()


def test_multi_repository_same_relative_path_requires_subject_binding():
    cattus = _evidence(paths=("README.md",))
    harness = _evidence(
        repository_id="harness-repo",
        name="deepseek-harness",
        aliases=("deepseek-harness",),
        paths=("README.md",),
    )
    qualified = (
        "C.A.T.T.U.S::README.md and deepseek-harness::README.md were both read."
    )

    grounded, findings = ground_answer_text(qualified, [cattus, harness])
    ambiguous, ambiguous_findings = ground_answer_text(
        "README.md establishes both repositories.", [cattus, harness]
    )

    assert grounded == qualified
    assert set(_statuses(findings).values()) == {GROUNDED_EXISTING}
    assert "Repository evidence gap" in ambiguous
    assert ambiguous_findings[0].status == UNVERIFIED_MODEL_ASSERTION


def test_stale_or_mismatched_evidence_fails_conservatively():
    stale = _evidence(paths=("main.py",), current=False)

    grounded, findings = ground_answer_text("The code is in main.py.", [stale])

    assert "Repository evidence gap" in grounded
    assert findings[0].status == UNVERIFIED_MODEL_ASSERTION


def test_unverified_receipt_is_bounded_and_contains_timings_without_confidence():
    block = {
        "summary": " ".join(f"missing_{index}.py is broken." for index in range(20)),
        "patch_candidate": None,
        "write_authority": False,
        "patch_application_authority": False,
    }
    state = SimpleNamespace(repo_path=None, user_input="fix it", project_tag="")

    _, _, display, receipt = ground_answer_for_display(state, "", block)

    assert receipt["unverified_entity_count"] == 20
    assert len(receipt["unverified_entities"]) == MAX_RECEIPT_ENTITIES
    assert receipt["receipt_truncated"] is True
    assert set(receipt["timing_seconds"]) == {
        "extraction",
        "membership_check",
        "total",
    }
    assert "confidence" not in json.dumps(receipt)
    assert display["write_authority"] is False
    assert display["patch_application_authority"] is False


def _inventory(*paths: str):
    return SimpleNamespace(
        canonical_root=os.getcwd(),
        entries=tuple(SimpleNamespace(relative_path=Path(path)) for path in paths),
    )


def test_t6_structured_answer_is_safe_in_every_display_field_and_patch_stays_null():
    state = SimpleNamespace(
        repo_path=os.getcwd(),
        project_tag="fixture",
        repository_inventory=_inventory("main.py"),
        repository_graph=None,
        analysis_evidence=None,
        control_result={"repo_path": os.getcwd(), "preflight_validation": {}},
        validation_output="",
        answer_grounding_evidence_current=True,
        user_input="Fix the failing behavior",
        human_answer="",
        final_answer="",
        json_block={
            "summary": "The bug is in patcher/generator.py::PatchGenerator.generate.",
            "issues": [
                {
                    "reason": (
                        "config/settings.py::ConfigurationOptions supplies the bad value."
                    )
                }
            ],
            "raw_answer": "patcher/generator.py contains the generator.",
            "patch_candidate": None,
            "patch_plan": None,
            "write_authority": False,
            "patch_application_authority": False,
        },
    )

    receipt = ground_state_answer(state)

    assert receipt["unverified_entity_count"] == 3
    assert receipt["action"] == "downgraded_unsupported_specificity"
    assert state.json_block["patch_candidate"] is None
    assert state.json_block["write_authority"] is False
    assert state.json_block["patch_application_authority"] is False
    # LIVE.3: every field keeps its prose; only the entities carry the retraction.
    assert "contains the generator" in state.final_answer
    assert "supplies the bad value" in state.final_answer
    assert state.final_answer.count("(not established in the current evidence)") == 3
    assert "not treating" in state.final_answer
    assert state.final_answer == state.human_answer
    assert json.loads(state.final_answer) == state.json_block


def test_state_evidence_reuses_inventory_analysis_control_and_execution():
    state = SimpleNamespace(
        repo_path=os.getcwd(),
        project_tag="calc",
        repository_inventory=_inventory("calc.py"),
        repository_graph=None,
        analysis_evidence=AnalysisEvidence(
            items=(AnalysisEvidenceItem("docs/architecture.md", "project_document", "doc"),)
        ),
        control_result={
            "repo_path": os.getcwd(),
            "top_hypothesis": {"symbol": "calc.py::add"},
            "preflight_validation": {
                "locations": [{"file": "calc.py", "line": 1}],
                "output": "calc.py:1",
            },
        },
        validation_output="calc.py:1",
        answer_grounding_evidence_current=True,
        user_input="Explain add",
    )
    text = "calc.py::add is in calc.py; docs/architecture.md was acquired."

    grounded, _, _, receipt = ground_answer_for_display(state, text)

    assert grounded == text
    assert receipt["grounded_entity_count"] == 3
    assert receipt["unverified_entity_count"] == 0


def test_grounding_never_silently_substitutes_a_real_ranked_file():
    evidence = _evidence(
        paths=("core/code_dna.py",),
        symbols=("core/code_dna.py::_classify_indent",),
    )

    grounded, _ = ground_answer_text(
        "The bug is in patcher/generator.py::PatchGenerator.generate.",
        [evidence],
    )

    assert "core/code_dna.py" not in grounded
    assert "_classify_indent" not in grounded


def test_cli_displays_only_the_grounded_terminal_answer(monkeypatch):
    import main as cli_main

    state = AgentState(
        interface="agent",
        mode="reviewer",
        user_input="Fix the failure",
        file_paths=[],
        primary_file=None,
        input_mode="text",
        language="python",
        task_type="bug_fix",
        live_route={},
    )
    raw = json.dumps(
        {
            "summary": "The bug is in patcher/generator.py::PatchGenerator.generate.",
            "patch_candidate": None,
            "patch_plan": None,
            "confidence": 0.0,
            "needs_escalation": True,
            "write_authority": False,
        }
    )
    displayed = {}
    monkeypatch.setattr(cli_main, "init_db", lambda: None)
    monkeypatch.setattr(cli_main, "create_agent_state", lambda: state)
    monkeypatch.setattr(cli_main, "run_draft_pipeline", lambda current: raw)
    monkeypatch.setattr(cli_main, "run_review_pipeline", lambda current, draft: draft)
    monkeypatch.setattr(cli_main, "run_postprocess_gate_battery", lambda *a, **k: None)
    monkeypatch.setattr(cli_main, "maybe_run_auto_patch", lambda current: None)
    monkeypatch.setattr(cli_main, "finish_task_run", lambda **kwargs: None)
    monkeypatch.setattr(cli_main, "log_session_result", lambda current: None)
    monkeypatch.setattr(cli_main, "save_structured_outputs", lambda current: None)
    monkeypatch.setattr(cli_main, "handle_followups", lambda current: None)
    monkeypatch.setattr(
        cli_main,
        "display_output",
        lambda human, final, block: displayed.update(
            {"human": human, "final": final, "block": block}
        ),
    )
    monkeypatch.setattr(cli_main, "WELCOME", "")
    monkeypatch.setattr(cli_main.sys, "argv", ["main.py", "--terminal"])

    cli_main.main()

    assert "The bug is in" in displayed["final"]
    assert "(not established in the current evidence)" in displayed["final"]
    assert "Repository evidence gap" in displayed["final"]
    assert displayed["final"] == state.final_answer
    assert displayed["block"]["answer_entity_grounding"]["unverified_entity_count"] == 1


def test_web_result_answer_patch_and_receipt_share_the_grounded_copy(
    tmp_path,
    monkeypatch,
):
    from web import runner

    repo = tmp_path / "fixture"
    repo.mkdir()
    (repo / "main.py").write_text("print('ok')\n", encoding="utf-8")
    control = {
        "repo_path": str(repo),
        "patch_intent": {"file": "main.py", "source_snippet": "print('ok')\n"},
        "top_hypothesis": {"symbol": "main.py::main"},
        "preflight_validation": {"ran": False, "ok": None},
    }
    raw = json.dumps(
        {
            "summary": "The bug is in patcher/generator.py::PatchGenerator.generate.",
            "issues": [
                {"reason": "config/settings.py::ConfigurationOptions is invalid."}
            ],
            "patch_candidate": None,
            "patch_plan": None,
            "confidence": 0.0,
            "needs_escalation": True,
            "write_authority": False,
            "patch_application_authority": False,
        }
    )
    ordering = []
    monkeypatch.setattr(
        runner,
        "classify_task",
        lambda query, mode, language, audience: {
            "intent": "bug_fix",
            "complexity": "simple",
            "language": language,
        },
    )
    monkeypatch.setattr(runner, "index_repository", lambda *a, **k: {})
    monkeypatch.setattr(runner, "clear_graph_cache", lambda *a, **k: None)
    monkeypatch.setattr(
        runner,
        "run_preflight_validation",
        lambda *a, **k: {"ran": False, "ok": None},
    )
    monkeypatch.setattr(runner, "run_control_structured", lambda *a, **k: dict(control))
    monkeypatch.setattr(runner, "build_related_snippets", lambda *a, **k: [])
    monkeypatch.setattr(runner, "get_engineering_memory", lambda **kwargs: [])
    monkeypatch.setattr(
        runner, "maybe_enrich_with_scout", lambda **kwargs: kwargs["control_result"]
    )
    monkeypatch.setattr(runner, "get_or_compute_dna", lambda *a, **k: {})
    monkeypatch.setattr(runner, "dna_to_prompt_block", lambda *a, **k: "")
    monkeypatch.setattr(runner, "create_session", lambda **kwargs: 123)
    monkeypatch.setattr(runner, "memory_note_exists", lambda *a, **k: True)
    monkeypatch.setattr(runner, "save_message", lambda *a, **k: None)
    monkeypatch.setattr(runner, "save_engineering_memory", lambda *a, **k: None)
    monkeypatch.setattr(runner, "run_draft_pipeline", lambda current: raw)
    monkeypatch.setattr(runner, "run_review_pipeline", lambda current, draft: draft)
    monkeypatch.setattr(runner, "run_postprocess_gate_battery", lambda *a, **k: None)

    def _terminal_authority(current, interactive=False):
        assert "answer_entity_grounding" not in current.json_block
        ordering.append("authority_terminal")

    monkeypatch.setattr(runner, "maybe_run_auto_patch", _terminal_authority)

    result = runner.run_agent_web(
        "Fix the failing behavior",
        str(repo),
        runtime_environment="local_windows",
    )

    assert ordering == ["authority_terminal"]
    assert "The bug is in" in result["answer"]
    assert "is invalid" in result["answer"]
    assert result["answer"].count("(not established in the current evidence)") == 2
    assert "Repository evidence gap" in result["answer"]
    assert json.loads(result["answer"]) == json.loads(result["patch"])
    assert result["answer_entity_grounding"]["unverified_entity_count"] == 2
    assert result["answer_entity_grounding"]["authority_effect"] == "none"


def test_grounding_boundary_has_no_model_network_traversal_or_authority_dependency():
    source = (
        Path(__file__).parent.parent / "core" / "answer_entity_grounding.py"
    ).read_text(encoding="utf-8")

    for forbidden in (
        "os.walk(",
        ".rglob(",
        "requests",
        "httpx",
        "urllib",
        # Not a bare "socket": the boundary now names Socket.io as a product an
        # answer may mention.  Both real forms of the module stay forbidden.
        "import socket",
        "socket.socket",
        "subprocess",
        "run_gemini",
        "run_deepseek",
        "run_ollama",
        "retrieve_context",
        "index_repository",
        "build_graph_from_repo",
        "maybe_run_auto_patch",
        "write_authority = True",
        "patch_application_authority = True",
    ):
        assert forbidden not in source, forbidden
