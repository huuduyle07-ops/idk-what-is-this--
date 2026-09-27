"""ANSWER.GROUND.LIVE.2 — bare symbol and qualified member claim grounding.

The Round-5 regression at the top of this file is the reason the phase exists:
a fabricated ``Class.method`` with no path in it escaped the LIVE.1 boundary.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

from core.analysis_evidence import AnalysisEvidence, AnalysisEvidenceItem
from core.answer_entity_grounding import (
    AMBIGUOUS_SYMBOL,
    GROUNDED_EXECUTION_OBSERVED,
    GROUNDED_EXISTING,
    HYPOTHETICAL,
    KIND_PATH,
    KIND_SYMBOL,
    PROPOSED_NEW,
    UNVERIFIED_MODEL_ASSERTION,
    USER_SUPPLIED_UNVERIFIED,
    RepositoryEntityEvidence,
    ground_answer_for_display,
    ground_answer_text,
    ground_state_answer,
)
from core.repository_symbol_membership import (
    SymbolClaim,
    SymbolMembership,
    declared_symbols,
    extract_symbol_claims,
    member_relations_from_spans,
    parse_symbol_text,
)


def _evidence(
    *,
    repository_id: str = "fixture-repo",
    name: str = "fixture",
    aliases: tuple[str, ...] = ("fixture",),
    paths: tuple[str, ...] = (),
    symbols: tuple[str, ...] = (),
    members: tuple[str, ...] = (),
    analysis: tuple[str, ...] = (),
    execution: tuple[str, ...] = (),
    execution_symbols: tuple[str, ...] = (),
    current: bool = True,
) -> RepositoryEntityEvidence:
    return RepositoryEntityEvidence(
        repository_id=repository_id,
        display_name=name,
        aliases=frozenset(aliases),
        existing_paths=frozenset(paths),
        source_symbols=frozenset(symbols),
        symbol_members=frozenset(members),
        analysis_paths=frozenset(analysis),
        execution_paths=frozenset(execution),
        execution_symbols=frozenset(execution_symbols),
        current=current,
    )


def _statuses(findings):
    return {finding.reference: finding.status for finding in findings}


def _code_dna() -> RepositoryEntityEvidence:
    return _evidence(
        paths=("core/code_dna.py",),
        symbols=("core/code_dna.py::_classify_indent", "core/code_dna.py::CodeDNA"),
        members=("core/code_dna.py::CodeDNA._classify_indent",),
    )


# ── Round-5 reproduced failures ───────────────────────────────────────────────

def test_round5_prose_class_method_with_no_path_is_no_longer_established_fact():
    text = "The bug is in the PatchGenerator.generate method."

    grounded, findings = ground_answer_text(text, [_code_dna()])

    # ANSWER.GROUND.LIVE.3 — the claim is retracted at the symbol, not by
    # deleting the sentence that carries it.
    assert "The bug is in the PatchGenerator.generate" in grounded
    assert "(not established in the current evidence) method." in grounded
    assert "Repository evidence gap" in grounded
    assert '"PatchGenerator.generate"' in grounded
    assert "not treating it as a real source location" in grounded
    assert _statuses(findings) == {
        "PatchGenerator.generate": UNVERIFIED_MODEL_ASSERTION
    }
    assert findings[0].kind == KIND_SYMBOL


def test_round5_structured_symbol_field_with_no_path_is_validated_directly():
    state = SimpleNamespace(repo_path=None, user_input="Fix the bug", project_tag="")
    block = {
        "summary": "Analysis complete.",
        "symbol": "CodeGenerator.format_patch",
        "patch_candidate": None,
        "patch_plan": None,
        "write_authority": False,
        "patch_application_authority": False,
    }

    _, _, display, receipt = ground_answer_for_display(state, "", block)

    assert "Repository evidence gap" in display["symbol"]
    assert receipt["asserted_symbol_count"] == 1
    assert receipt["unverified_symbol_count"] == 1
    assert receipt["grounded_symbol_count"] == 0
    assert receipt["action"] == "downgraded_unsupported_specificity"
    assert display["patch_candidate"] is None
    assert display["write_authority"] is False
    assert display["patch_application_authority"] is False


def test_round5_both_fabricated_symbols_are_caught_in_one_boundary_pass():
    state = SimpleNamespace(repo_path=None, user_input="Fix it", project_tag="")
    block = {
        "summary": "The bug is in the PatchGenerator.generate method.",
        "symbol": "CodeGenerator.format_patch",
        "patch_candidate": None,
        "write_authority": False,
    }

    _, _, display, receipt = ground_answer_for_display(state, "", block)

    entities = {item["entity"] for item in receipt["unverified_entities"]}
    assert entities == {"PatchGenerator.generate", "CodeGenerator.format_patch"}
    assert receipt["unverified_symbol_count"] == 2
    assert receipt["asserted_path_count"] == 0
    assert display["summary"].startswith("The bug is in the PatchGenerator.generate")
    assert "(not established in the current evidence)" in display["summary"]
    assert "(not established in the current evidence)" in display["symbol"]
    assert receipt["authority_effect"] == "none"
    assert receipt["retrieval_effect"] == "none"


def test_no_substitute_symbol_is_invented_for_a_rejected_claim():
    grounded, _ = ground_answer_text(
        "The bug is in the PatchGenerator.generate method.", [_code_dna()]
    )

    assert "_classify_indent" not in grounded
    assert "CodeDNA" not in grounded
    assert "code_dna" not in grounded


# ── Grounded symbol cases ─────────────────────────────────────────────────────

def test_real_unique_bare_function_may_stay_precise_without_a_path():
    text = "Inspect `_classify_indent` for the indentation defect."

    grounded, findings = ground_answer_text(text, [_code_dna()])

    assert grounded == text
    assert _statuses(findings) == {"_classify_indent": GROUNDED_EXISTING}


def test_real_qualified_member_is_grounded_from_recorded_spans():
    grounded, findings = ground_answer_text(
        "Inspect `CodeDNA._classify_indent` and core/code_dna.py::CodeDNA._classify_indent.",
        [_code_dna()],
    )

    assert "Repository evidence gap" not in grounded
    assert set(_statuses(findings).values()) == {GROUNDED_EXISTING}
    assert {finding.kind for finding in findings} == {KIND_SYMBOL, KIND_PATH}


def test_module_qualified_symbol_binds_through_the_module_relation():
    grounded, findings = ground_answer_text(
        "`code_dna._classify_indent` handles the indent case.", [_code_dna()]
    )

    assert grounded.startswith("`code_dna._classify_indent` handles")
    assert findings[0].status == GROUNDED_EXISTING


def test_analysis_acquired_typescript_symbol_grounds_without_the_code_index():
    state = SimpleNamespace(
        repo_path=os.getcwd(),
        project_tag="fixture",
        user_input="Explain the service",
        repository_inventory=None,
        repository_graph=None,
        analysis_evidence=AnalysisEvidence(
            items=(
                AnalysisEvidenceItem(
                    "src/service.ts",
                    "requested_path",
                    "export class TaskService {\n  runQueue() {\n    return 1;\n  }\n}\n",
                ),
            )
        ),
        control_result=None,
        validation_output="",
        answer_grounding_evidence_current=True,
    )
    text = "`TaskService.runQueue` drives the queue in src/service.ts."

    grounded, _, _, receipt = ground_answer_for_display(state, text)

    assert grounded == text
    assert receipt["grounded_symbol_count"] == 1
    assert receipt["unverified_symbol_count"] == 0


def test_execution_observed_frame_grounds_the_symbol_it_actually_ran():
    evidence = _evidence(
        paths=("main.py",),
        execution=("main.py",),
        execution_symbols=("main.py::add",),
    )

    grounded, findings = ground_answer_text("The frame named `add`.", [evidence])

    assert grounded == "The frame named `add`."
    assert findings[0].status == GROUNDED_EXECUTION_OBSERVED


def test_traceback_frames_only_promote_symbols_for_known_repository_files():
    state = SimpleNamespace(
        repo_path=os.getcwd(),
        project_tag="fixture",
        user_input="Why did it fail?",
        repository_inventory=SimpleNamespace(
            canonical_root=os.getcwd(),
            entries=(SimpleNamespace(relative_path="main.py"),),
        ),
        repository_graph=None,
        analysis_evidence=None,
        control_result=None,
        validation_output=(
            'File "main.py", line 2, in add\n'
            'File "C:/Python/Lib/site-packages/pkg/worker.py", line 41, in dispatch\n'
        ),
        answer_grounding_evidence_current=True,
    )

    grounded, _, _, receipt = ground_answer_for_display(
        state, "The frame named `add`. The library frame named `dispatch`."
    )

    assert "The frame named `add`." in grounded
    # LIVE.3: the library frame's symbol is retracted where it stands; the
    # sentence reporting it survives.
    assert "The library frame named `dispatch`" in grounded
    assert "`dispatch` (not established in the current evidence)" in grounded
    assert "Repository evidence gap" in grounded
    assert receipt["grounded_symbol_count"] == 1
    assert receipt["unverified_symbol_count"] == 1


# ── False grounding must not happen ───────────────────────────────────────────

def test_real_file_never_grounds_an_invented_member():
    grounded, findings = ground_answer_text(
        "Look at core/code_dna.py::IndentClassifier.resolve.", [_code_dna()]
    )

    assert "Repository evidence gap" in grounded
    assert findings[0].status == UNVERIFIED_MODEL_ASSERTION


def test_real_class_never_grounds_a_method_it_does_not_own():
    evidence = _evidence(
        paths=("gen.py",),
        symbols=("gen.py::PatchGenerator",),
    )

    grounded, findings = ground_answer_text(
        "The bug is in `PatchGenerator.generate`.", [evidence]
    )

    assert "Repository evidence gap" in grounded
    assert findings[0].status == UNVERIFIED_MODEL_ASSERTION


def test_real_method_in_the_wrong_class_is_not_grounded():
    evidence = _evidence(
        paths=("a.py",),
        symbols=("a.py::Foo", "a.py::generate"),
        members=("a.py::Foo.generate",),
    )

    good, good_findings = ground_answer_text("`Foo.generate` is fine.", [evidence])
    bad, bad_findings = ground_answer_text("`Bar.generate` is the bug.", [evidence])

    assert good == "`Foo.generate` is fine."
    assert good_findings[0].status == GROUNDED_EXISTING
    assert "Repository evidence gap" in bad
    assert bad_findings[0].status == UNVERIFIED_MODEL_ASSERTION


def test_ambiguous_bare_symbol_is_never_guessed_at():
    evidence = _evidence(
        paths=("alpha.py", "beta.py"),
        symbols=("alpha.py::parse", "beta.py::parse"),
    )

    grounded, findings = ground_answer_text("The bug is in `parse`.", [evidence])

    assert "matches more than one source-backed symbol" in grounded
    assert "alpha.py" not in grounded
    assert "beta.py" not in grounded
    assert findings[0].status == AMBIGUOUS_SYMBOL


def test_ambiguity_resolves_when_the_same_sentence_names_a_grounded_file():
    evidence = _evidence(
        paths=("alpha.py", "beta.py"),
        symbols=("alpha.py::parse", "beta.py::parse"),
    )
    text = "In alpha.py, `parse` drops the final token."

    grounded, findings = ground_answer_text(text, [evidence])

    assert grounded == text
    assert _statuses(findings) == {
        "alpha.py": GROUNDED_EXISTING,
        "parse": GROUNDED_EXISTING,
    }


def test_ambiguity_resolves_from_a_sibling_structured_path_field():
    state = SimpleNamespace(repo_path=None, user_input="fix", project_tag="")
    evidence = _evidence(
        paths=("alpha.py", "beta.py"),
        symbols=("alpha.py::parse", "beta.py::parse"),
    )

    grounded, findings = ground_answer_text(
        "parse",
        [evidence],
        structured_field="symbol",
        context_path="beta.py",
    )

    assert grounded == "parse"
    assert findings[0].status == GROUNDED_EXISTING
    assert findings[0].reference == "beta.py::parse"
    assert state.repo_path is None


def test_symbol_tail_collision_permanent_regression():
    evidence = _evidence(
        paths=("a.py", "b.py"),
        symbols=("a.py::Alpha", "a.py::generate", "b.py::Beta", "b.py::generate"),
        members=("a.py::Alpha.generate", "b.py::Beta.generate"),
    )

    bare, bare_findings = ground_answer_text("Check `generate`.", [evidence])
    exact, exact_findings = ground_answer_text("Check `Alpha.generate`.", [evidence])

    assert bare_findings[0].status == AMBIGUOUS_SYMBOL
    assert "Repository evidence gap" in bare
    assert exact == "Check `Alpha.generate`."
    assert exact_findings[0].status == GROUNDED_EXISTING


def test_stale_symbol_evidence_fails_conservatively():
    stale = _evidence(
        paths=("core/code_dna.py",),
        symbols=("core/code_dna.py::_classify_indent",),
        current=False,
    )

    grounded, findings = ground_answer_text("Inspect `_classify_indent`.", [stale])

    assert "Repository evidence gap" in grounded
    assert findings[0].status == UNVERIFIED_MODEL_ASSERTION


def test_one_repository_symbol_never_grounds_another_repository_claim():
    owner = _evidence(
        repository_id="repo-a",
        name="repo-a",
        aliases=("repo-a",),
        paths=("a.py",),
        symbols=("a.py::Foo", "a.py::run"),
        members=("a.py::Foo.run",),
    )
    other = _evidence(
        repository_id="repo-b",
        name="repo-b",
        aliases=("repo-b",),
        paths=("b.py",),
        symbols=("b.py::unrelated",),
    )

    grounded, findings = ground_answer_text("`Foo.run` is the entry.", [owner, other])
    assert grounded == "`Foo.run` is the entry."
    assert findings[0].status == GROUNDED_EXISTING
    assert findings[0].repository_id == "repo-a"

    only_b, only_b_findings = ground_answer_text("`Foo.run` is the entry.", [other])
    assert "Repository evidence gap" in only_b
    assert only_b_findings[0].status == UNVERIFIED_MODEL_ASSERTION


# ── Non-existing forms that must remain sayable ───────────────────────────────

def test_user_supplied_missing_symbol_is_discussable_as_unverified():
    grounded, findings = ground_answer_text(
        "`PatchGenerator.generate` drives the patch.",
        [_code_dna()],
        user_input="Why is PatchGenerator.generate broken?",
    )

    assert "I could not establish" in grounded
    assert '"PatchGenerator.generate"' in grounded
    # LIVE.3: the user's referent stays sayable in place, only unverified.
    assert grounded.startswith("`PatchGenerator.generate`")
    assert "drives the patch" in grounded
    assert findings[0].status == USER_SUPPLIED_UNVERIFIED


def test_proposed_new_class_from_a_create_file_plan_is_not_a_fabrication():
    state = SimpleNamespace(repo_path=None, user_input="add priority", project_tag="")
    block = {
        "summary": "The plan introduces `PriorityFilter` in filters.py.",
        "patch_plan": [
            {
                "op": "create_file",
                "relative_path": "filters.py",
                "content": "class PriorityFilter:\n    def apply(self):\n        pass\n",
            }
        ],
        "patch_candidate": None,
        "write_authority": False,
    }

    _, _, display, receipt = ground_answer_for_display(state, "", block)

    assert display["summary"] == block["summary"]
    statuses = {item["entity"]: item["status"] for item in receipt["entity_statuses"]}
    assert statuses["PriorityFilter"] == PROPOSED_NEW
    assert statuses["filters.py"] == PROPOSED_NEW
    assert receipt["unverified_symbol_count"] == 0
    assert display["write_authority"] is False


def test_proposed_new_method_needs_an_existing_owner_and_stays_unapplied():
    evidence = _evidence(paths=("store.py",), symbols=("store.py::TaskStore",))
    from core.answer_entity_grounding import _proposed_new_symbols

    legitimate = _proposed_new_symbols(
        {
            "patch_plan": [
                {
                    "op": "replace_snippet",
                    "relative_path": "store.py",
                    "patched_snippet": (
                        "class TaskStore:\n"
                        "    def filter_by_priority(self):\n        pass\n"
                    ),
                }
            ]
        },
        [evidence],
    )
    laundered = _proposed_new_symbols(
        {
            "patch_candidate": {
                "patched_snippet": (
                    "class CodeGenerator:\n"
                    "    def format_patch(self):\n        pass\n"
                )
            }
        },
        [evidence],
    )

    good, good_findings = ground_answer_text(
        "The plan adds `TaskStore.filter_by_priority`.",
        [evidence],
        proposed_new_symbols=legitimate,
    )
    bad, bad_findings = ground_answer_text(
        "The bug is in `CodeGenerator.format_patch`.",
        [evidence],
        proposed_new_symbols=laundered,
    )

    assert good_findings[0].status == PROPOSED_NEW
    assert "Repository evidence gap" not in good
    assert bad_findings[0].status == UNVERIFIED_MODEL_ASSERTION
    assert "Repository evidence gap" in bad


def test_hypothetical_symbol_example_is_not_reported_as_fabricated():
    illustration, illustration_findings = ground_answer_text(
        "A system could expose `Formatter.render()` for that.", [_code_dna()]
    )
    claim, claim_findings = ground_answer_text(
        "The repository uses `Formatter.render()` here.", [_code_dna()]
    )

    assert illustration == "A system could expose `Formatter.render()` for that."
    assert illustration_findings[0].status == HYPOTHETICAL
    assert "Repository evidence gap" in claim
    assert claim_findings[0].status == UNVERIFIED_MODEL_ASSERTION


def test_identifiers_inside_a_generated_code_block_are_not_repository_claims():
    text = (
        "An illustrative shape:\n"
        "```python\n"
        "class Example:\n"
        "    def run(self):\n"
        "        return PatchGenerator.generate()\n"
        "```"
    )

    grounded, findings = ground_answer_text(text, [_code_dna()])

    assert grounded == text
    assert findings == ()


def test_external_library_symbols_are_not_forced_to_exist_in_the_repository():
    text = (
        "Run it with pytest.main, build the path with pathlib.Path, "
        "reuse requests.Session, and call len() on the result."
    )

    grounded, findings = ground_answer_text(text, [_code_dna()])

    assert grounded == text
    assert findings == ()


def test_ordinary_prose_words_are_not_turned_into_repository_entities():
    text = (
        "The bug is in production, the result data is fine, and the generator "
        "keeps running while values are collected."
    )

    grounded, findings = ground_answer_text(text, [_code_dna()])

    assert grounded == text
    assert findings == ()


# ── Compatibility with the frozen path boundary and the coding routes ─────────

def test_t1_t2_t3_style_answers_keep_both_path_and_symbol_precision():
    evidence = _evidence(
        paths=("calc.py", "solution.py"),
        symbols=(
            "calc.py::add",
            "solution.py::length_of_longest_substring",
        ),
    )
    text = (
        "calc.py::add returns the sum; the `length_of_longest_substring` "
        "function in solution.py scans once."
    )

    grounded, findings = ground_answer_text(text, [evidence])

    assert grounded == text
    assert set(_statuses(findings).values()) == {GROUNDED_EXISTING}


def test_t1_auto_patch_payload_keeps_its_typed_symbol_fields_intact():
    state = SimpleNamespace(
        repo_path=os.getcwd(),
        project_tag="calc",
        repository_inventory=None,
        repository_graph=None,
        analysis_evidence=None,
        control_result={
            "repo_path": os.getcwd(),
            "patch_intent": {
                "file": "calc.py",
                "relative_path": "calc.py",
                "target_node_name": "add",
                "target_symbol": "add",
                "target_symbol_full": "calc.py::add",
                "source_snippet": "def add(a, b):\n    return a - b\n",
            },
            "top_hypothesis": {"symbol": "calc.py::add"},
            "preflight_validation": {},
        },
        validation_output="",
        answer_grounding_evidence_current=True,
        user_input="calc.py add is wrong",
        human_answer="",
        final_answer="",
        json_block={
            "relative_path": "calc.py",
            "target_node_name": "add",
            "target_snippet": "def add(a, b):\n    return a - b\n",
            "patched_snippet": "def add(a, b):\n    return a + b\n",
            "issue": "The `add` function subtracts instead of adding.",
            "patch_candidate": {
                "relative_path": "calc.py",
                "target_node_name": "add",
                "target_snippet": "def add(a, b):\n    return a - b\n",
                "patched_snippet": "def add(a, b):\n    return a + b\n",
            },
        },
    )

    receipt = ground_state_answer(state)

    assert state.json_block["target_node_name"] == "add"
    assert state.json_block["patch_candidate"]["target_node_name"] == "add"
    assert state.json_block["patch_candidate"]["relative_path"] == "calc.py"
    assert state.json_block["issue"] == "The `add` function subtracts instead of adding."
    assert receipt["action"] == "unchanged"
    # The typed field resolves inside its sibling file; the prose mention keeps
    # its own bare identity.  Both are grounded, neither is downgraded.
    assert {
        item["entity"]
        for item in receipt["entity_statuses"]
        if item["kind"] == KIND_SYMBOL
    } == {"calc.py::add", "add"}
    assert receipt["grounded_symbol_count"] == 2
    assert receipt["unverified_symbol_count"] == 0


def test_path_grounding_behaviour_from_live_1_is_unchanged_by_symbol_grounding():
    evidence = _evidence(paths=("main.py",))

    grounded, findings = ground_answer_text(
        "The bug is in patcher/generator.py::PatchGenerator.generate.", [evidence]
    )

    assert "Repository evidence gap" in grounded
    assert len(findings) == 1
    assert findings[0].kind == KIND_PATH
    assert findings[0].status == UNVERIFIED_MODEL_ASSERTION


def test_symbol_receipt_is_bounded_and_carries_no_confidence_or_source_text():
    evidence = _evidence(paths=("a.py",))
    block = {
        "summary": " ".join(
            f"The bug is in `Fake{index}.method`." for index in range(20)
        ),
        "patch_candidate": None,
        "write_authority": False,
    }
    state = SimpleNamespace(repo_path=None, user_input="fix", project_tag="")

    _, _, _, receipt = ground_answer_for_display(state, "", block)

    assert receipt["asserted_symbol_count"] == 20
    assert receipt["unverified_symbol_count"] == 20
    assert len(receipt["unverified_entities"]) <= 12
    assert receipt["receipt_truncated"] is True
    assert set(receipt["timing_seconds"]) == {"extraction", "membership_check", "total"}
    serialized = json.dumps(receipt)
    assert "confidence" not in serialized
    assert "localization_score" not in serialized
    assert receipt["phase_ids"] == [
        "ANSWER.GROUND.LIVE.1",
        "ANSWER.GROUND.LIVE.2",
        "ANSWER.GROUND.LIVE.3",
    ]
    assert evidence.current is True


def test_every_display_surface_shares_one_grounded_symbol_copy():
    state = SimpleNamespace(
        repo_path=os.getcwd(),
        project_tag="fixture",
        repository_inventory=SimpleNamespace(
            canonical_root=os.getcwd(),
            entries=(SimpleNamespace(relative_path=Path("main.py")),),
        ),
        repository_graph=None,
        analysis_evidence=None,
        control_result={"repo_path": os.getcwd(), "preflight_validation": {}},
        validation_output="",
        answer_grounding_evidence_current=True,
        user_input="Fix the failing behavior",
        human_answer="",
        final_answer="",
        json_block={
            "summary": "The bug is in the PatchGenerator.generate method.",
            "symbol": "CodeGenerator.format_patch",
            "issues": [{"reason": "`PatchGenerator.generate` mangles the diff."}],
            "patch_candidate": None,
            "patch_plan": None,
            "write_authority": False,
            "patch_application_authority": False,
        },
    )

    receipt = ground_state_answer(state)

    rendered = state.final_answer
    assert rendered == state.human_answer
    assert json.loads(rendered) == state.json_block
    # LIVE.3: every surface shares one copy, and that copy now retracts each
    # entity in place instead of dropping the fields' prose.
    assert "mangles the diff" in rendered
    assert "The bug is in the PatchGenerator" in rendered
    assert rendered.count("(not established in the current evidence)") == 3
    assert receipt["unverified_symbol_count"] == 2
    assert state.json_block["patch_candidate"] is None
    assert state.json_block["write_authority"] is False
    assert state.json_block["patch_application_authority"] is False


def test_symbol_grounding_touches_no_retrieval_or_authority_state():
    control = {"repo_path": os.getcwd(), "entry_nodes": ["main.py::main"]}
    state = SimpleNamespace(
        repo_path=os.getcwd(),
        project_tag="fixture",
        repository_inventory=None,
        repository_graph=None,
        analysis_evidence=None,
        control_result=control,
        validation_output="",
        answer_grounding_evidence_current=True,
        user_input="fix",
        human_answer="The bug is in `PatchGenerator.generate`.",
        final_answer="",
        json_block=None,
    )
    before = json.dumps(control, sort_keys=True)

    receipt = ground_state_answer(state)

    assert json.dumps(control, sort_keys=True) == before
    assert receipt["authority_effect"] == "none"
    assert receipt["retrieval_effect"] == "none"
    assert not hasattr(state, "patch_candidate")


# ── Grammar and membership units ──────────────────────────────────────────────

def test_symbol_grammar_rejects_paths_and_accepts_qualified_identifiers():
    assert parse_symbol_text("PatchGenerator.generate") == (
        "PatchGenerator",
        "generate",
        False,
    )
    assert parse_symbol_text("Foo::bar") == ("Foo", "bar", False)
    assert parse_symbol_text("parse()") == ("", "parse", True)
    assert parse_symbol_text("main.py::main") is None
    assert parse_symbol_text("settings.py") is None
    assert parse_symbol_text("core/code_dna.py") is None
    assert parse_symbol_text("two words") is None
    assert parse_symbol_text("") is None


def test_claims_never_overlap_spans_the_path_grammar_already_owns():
    text = "See core/code_dna.py::CodeDNA._classify_indent for the detail."

    claims = extract_symbol_claims(text, exclude_spans=[(4, 49)])

    assert claims == ()


def test_member_relations_come_from_recorded_spans_without_a_reparse():
    relations = member_relations_from_spans(
        [
            ("a.py", "Alpha", "class", 0, 100),
            ("a.py", "generate", "function", 10, 50),
            ("a.py", "free_function", "function", 200, 260),
        ]
    )

    assert relations == frozenset({"a.py::alpha.generate"})


def test_declaration_scan_reports_owners_by_indentation():
    assert declared_symbols(
        "class TaskStore:\n"
        "    def filter_by_priority(self):\n"
        "        pass\n"
        "\n"
        "def helper():\n"
        "    pass\n"
    ) == (
        ("", "TaskStore"),
        ("TaskStore", "filter_by_priority"),
        ("", "helper"),
    )


def test_membership_never_reports_a_claim_for_builtins_or_plain_words():
    membership = SymbolMembership(
        source_symbols=frozenset({"a.py::run"}), known_paths=frozenset({"a.py"})
    )

    def _claim(owner: str, member: str, **kwargs) -> SymbolClaim:
        return SymbolClaim(raw=member, owner=owner, member=member, **kwargs)

    assert membership.is_repository_claim(_claim("", "run")) is True
    assert membership.is_repository_claim(_claim("", "len", call_form=True)) is False
    assert membership.is_repository_claim(_claim("", "production")) is False
    assert membership.is_repository_claim(_claim("pytest", "main")) is False
    assert membership.is_repository_claim(_claim("PatchGenerator", "generate")) is True


def test_symbol_boundary_has_no_model_network_traversal_or_authority_dependency():
    for module in ("answer_entity_grounding", "repository_symbol_membership"):
        source = (
            Path(__file__).parent.parent / "core" / f"{module}.py"
        ).read_text(encoding="utf-8")

        for forbidden in (
            "os.walk(",
            ".rglob(",
            ".glob(",
            ".iterdir(",
            ".read_text(",
            ".read_bytes(",
            "open(",
            "import requests",
            "import httpx",
            "import urllib",
            "import socket",
            "import subprocess",
            "run_gemini",
            "run_deepseek",
            "run_ollama",
            "embed_text",
            "retrieve_context",
            "index_repository",
            "build_graph_from_repo",
            "build_graph(",
            "maybe_run_auto_patch",
            "human_review_eligible = True",
            "write_authority = True",
            "patch_application_authority = True",
            "execution_authorized = True",
        ):
            assert forbidden not in source, f"{module}: {forbidden}"
