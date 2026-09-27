"""ANSWER.GROUND.LIVE.3 — non-destructive remediation and exact path boundaries.

Two Round-6 defects are pinned here, both reproduced from the live T5 answer.

DEFECT A — remediation deleted the whole containing sentence for one unsupported
entity, and the sentence splitter treated ``vs.`` as a boundary, so removal cut
mid-clause and shipped ``exclusive), and state transitions ...`` to the user.

DEFECT B — the path grammar matched a supported extension as a *prefix* inside a
longer dotted token, so ``args.cmd`` produced a fabrication finding for the file
``args.c``, ``t.json`` for ``t.js``, ``Cordis.plugin`` for ``Cordis.pl`` and
``_pytest.capture.CaptureFixture`` for ``_pytest.capture.C``.

The epistemic distinction this phase protects: *not established by the current
bounded evidence* is not *proven nonexistent*.  A symbol the repository really
has but this run never acquired stays unverified — and the user-visible wording
says so without claiming the repository lacks it.
"""

from __future__ import annotations

import json
import os
import re
from types import SimpleNamespace

from core.answer_entity_grounding import (
    AMBIGUOUS_SYMBOL,
    GROUNDED_EXISTING,
    HYPOTHETICAL,
    LIVE3_PHASE_ID,
    PROPOSED_NEW,
    UNVERIFIED_MODEL_ASSERTION,
    USER_SUPPLIED_UNVERIFIED,
    RepositoryEntityEvidence,
    extract_repository_entities,
    ground_answer_for_display,
    ground_answer_text,
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
        current=current,
    )


def _statuses(findings):
    return {finding.reference: finding.status for finding in findings}


def _body(grounded: str) -> str:
    """The answer text without the appended evidence-gap statement."""

    return grounded.split("Repository evidence gap:")[0].rstrip()


# ── DEFECT A — remediation is span-local, never sentence deletion ─────────────

def test_one_unsupported_symbol_never_deletes_its_sentence():
    text = "The bug is in the PatchGenerator.generate method."

    grounded, findings = ground_answer_text(text, [_evidence(paths=("main.py",))])

    assert "The bug is in" in grounded
    assert "method." in grounded
    assert "Repository evidence gap" in grounded
    assert findings[0].status == UNVERIFIED_MODEL_ASSERTION


def test_round6_t5_abbreviation_clause_is_not_cut_in_half():
    """``parallel vs. exclusive`` — the exact Round-6 mangling, pinned."""

    text = (
        "deepseek-harness uses `Cordis`, where the `AgentLoop` plugin registers "
        "execution modes (parallel vs. exclusive), and state transitions are "
        "recorded in main.py."
    )

    grounded, findings = ground_answer_text(text, [_evidence(paths=("main.py",))])
    body = _body(grounded)

    # The Round-6 output began mid-clause with "exclusive), and state ...".
    assert not body.startswith("exclusive)")
    assert body.startswith("deepseek-harness uses `Cordis`")
    assert "(parallel vs. exclusive)" in body
    assert "and state transitions are recorded in main.py." in body
    assert "`AgentLoop`" in body
    assert set(_statuses(findings).values()) == {
        GROUNDED_EXISTING,
        UNVERIFIED_MODEL_ASSERTION,
    }


def test_eg_and_ie_abbreviations_do_not_control_remediation():
    text = (
        "The registry maps modes (parallel vs. exclusive), i.e. `Cordis` owns "
        "them, e.g. `AgentLoop` records each transition, and calc.py::add stays."
    )
    evidence = _evidence(paths=("calc.py",), symbols=("calc.py::add",))

    grounded, _ = ground_answer_text(text, [evidence])
    body = _body(grounded)

    for fragment in (
        "The registry maps modes (parallel vs. exclusive), i.e. ",
        " owns them, e.g. ",
        " records each transition, and calc.py::add stays.",
    ):
        assert fragment in body


def test_surrounding_clause_survives_at_start_middle_and_end_positions():
    evidence = _evidence(paths=("main.py",))

    for text in (
        "`Cordis` is the loop that main.py drives to completion.",
        "The loop `Cordis` is what main.py drives to completion.",
        "main.py drives the loop to completion through `Cordis`.",
    ):
        grounded, findings = ground_answer_text(text, [evidence])
        body = _body(grounded)

        assert "main.py" in body
        assert "`Cordis`" in body
        assert "to completion" in body
        assert findings != ()


def test_several_unsupported_entities_stay_position_stable():
    text = (
        "First `AlphaLoop` runs, then `BetaLoop` runs, and finally `GammaLoop` "
        "reports to main.py."
    )

    grounded, findings = ground_answer_text(text, [_evidence(paths=("main.py",))])
    body = _body(grounded)

    order = [body.index(name) for name in ("`AlphaLoop`", "`BetaLoop`", "`GammaLoop`")]
    assert order == sorted(order)
    assert body.startswith("First `AlphaLoop`")
    assert "then " in body and "and finally " in body
    assert body.endswith("reports to main.py.")
    assert len([item for item in findings if item.status == UNVERIFIED_MODEL_ASSERTION]) == 3


def test_markdown_bullets_headings_and_inline_code_stay_well_formed():
    text = (
        "## Agent loop\n"
        "- **deepseek-harness** uses `Cordis` for scheduling (see main.py).\n"
        "- **C.A.T.T.U.S** uses main.py for the same job.\n"
    )

    grounded, _ = ground_answer_text(text, [_evidence(paths=("main.py",))])
    body = _body(grounded)

    assert body.startswith("## Agent loop\n")
    assert body.count("\n- ") == 2 and body.count("- **") == 2
    assert "**deepseek-harness**" in body and "**C.A.T.T.U.S**" in body
    assert body.count("`") % 2 == 0
    assert body.count("(") == body.count(")")


def test_neighbouring_citations_and_grounded_paths_survive_a_downgrade():
    evidence = _evidence(
        repository_id="harness",
        name="deepseek-harness",
        aliases=("deepseek-harness",),
        paths=("src/loop.ts",),
    )
    text = (
        "As deepseek-harness::src/loop.ts shows, the `Cordis` runtime drives "
        "[the loop](docs/loop.md) end to end."
    )

    grounded, findings = ground_answer_text(text, [evidence])
    body = _body(grounded)

    assert "deepseek-harness::src/loop.ts" in body
    assert "[the loop](docs/loop.md)" in body
    assert _statuses(findings)["deepseek-harness::src/loop.ts"] == GROUNDED_EXISTING


def test_structured_field_remediation_stays_field_local():
    state = SimpleNamespace(repo_path=None, user_input="Fix the bug", project_tag="")
    block = {
        "summary": "Analysis complete.",
        "symbol": "IndentationNormalizer",
        "patch_candidate": None,
        "patch_plan": None,
        "write_authority": False,
        "patch_application_authority": False,
    }

    _, _, display, receipt = ground_answer_for_display(state, "", block)

    assert display["summary"] == "Analysis complete."
    assert display["symbol"].startswith("IndentationNormalizer")
    assert "not established in the current evidence" in display["symbol"]
    assert receipt["unverified_symbol_count"] == 1
    assert display["write_authority"] is False


# ── The epistemic distinction ────────────────────────────────────────────────

def test_unverified_never_reads_as_proven_nonexistent():
    grounded, findings = ground_answer_text(
        "The `AgentLoop` plugin registers modes.", [_evidence(paths=("main.py",))]
    )

    assert findings[0].status == UNVERIFIED_MODEL_ASSERTION
    assert "not established in the current evidence" in grounded
    lowered = grounded.casefold()
    for categorical in (
        "does not exist",
        "do not exist",
        "no such",
        "is not in the repository",
        "nonexistent",
    ):
        assert categorical not in lowered


def test_true_but_unacquired_symbol_is_an_evidence_gap_not_a_denial():
    """Cordis/AgentLoop really exist in deepseek-harness; this run never read them."""

    acquired_only = _evidence(
        repository_id="harness",
        name="deepseek-harness",
        aliases=("deepseek-harness",),
        analysis=("README.md",),
    )
    text = "Per README.md, `Cordis` schedules the plugins."

    grounded, findings = ground_answer_text(text, [acquired_only])
    body = _body(grounded)

    assert "Per README.md, `Cordis`" in body
    assert _statuses(findings)["Cordis"] == UNVERIFIED_MODEL_ASSERTION
    assert "not a finding about whether deepseek-harness contains it" in grounded


def test_fabricated_qualified_symbol_is_still_downgraded():
    evidence = _evidence(
        paths=("core/code_dna.py",),
        symbols=("core/code_dna.py::_classify_indent",),
    )

    for text in (
        "The bug is in the PatchGenerator.generate method.",
        "`CodeGenerator.format_patch` writes the diff.",
    ):
        grounded, findings = ground_answer_text(text, [evidence])

        assert findings[0].status == UNVERIFIED_MODEL_ASSERTION
        assert "Repository evidence gap" in grounded
        assert "not established in the current evidence" in grounded
        # No substitute entity is ever invented for a rejected claim.
        assert "_classify_indent" not in grounded
        assert "core/code_dna.py" not in grounded


def test_grounded_symbols_and_paths_are_byte_identical():
    evidence = _evidence(
        paths=("core/code_dna.py",),
        symbols=("core/code_dna.py::_classify_indent", "core/code_dna.py::CodeDNA"),
        members=("core/code_dna.py::CodeDNA._classify_indent",),
    )
    text = (
        "Inspect `_classify_indent` in core/code_dna.py, or "
        "core/code_dna.py::CodeDNA._classify_indent for the qualified form."
    )

    grounded, findings = ground_answer_text(text, [evidence])

    assert grounded == text
    assert set(_statuses(findings).values()) == {GROUNDED_EXISTING}


def test_ambiguous_hypothetical_and_proposed_behaviour_is_unchanged():
    ambiguous_evidence = _evidence(
        paths=("alpha.py", "beta.py"),
        symbols=("alpha.py::parse", "beta.py::parse"),
    )
    ambiguous, ambiguous_findings = ground_answer_text(
        "The bug is in `parse`.", [ambiguous_evidence]
    )
    hypothetical, hypothetical_findings = ground_answer_text(
        "For example, a project could put this in src/generator.py.", [_evidence()]
    )

    assert ambiguous_findings[0].status == AMBIGUOUS_SYMBOL
    assert "matches more than one source-backed symbol" in ambiguous
    assert "alpha.py" not in ambiguous and "beta.py" not in ambiguous
    assert "The bug is in `parse`" in ambiguous
    assert hypothetical_findings[0].status == HYPOTHETICAL
    assert hypothetical == "For example, a project could put this in src/generator.py."


def test_multi_root_separation_is_unchanged_by_local_remediation():
    cattus = _evidence(
        repository_id="cattus", name="C.A.T.T.U.S", aliases=("C.A.T.T.U.S",),
        paths=("core/pipeline.py",), symbols=("core/pipeline.py::Pipeline",),
    )
    harness = _evidence(
        repository_id="harness", name="deepseek-harness", aliases=("deepseek-harness",),
        paths=("src/loop.ts",), symbols=("src/loop.ts::AgentLoop",),
    )
    text = (
        "C.A.T.T.U.S::core/pipeline.py holds the pipeline and "
        "deepseek-harness::src/loop.ts::AgentLoop holds the loop, but "
        "C.A.T.T.U.S::core/pipeline.py::AgentLoop does not follow from either."
    )

    grounded, findings = ground_answer_text(text, [cattus, harness])
    statuses = _statuses(findings)

    assert statuses["deepseek-harness::src/loop.ts::AgentLoop"] == GROUNDED_EXISTING
    assert (
        statuses["C.A.T.T.U.S::core/pipeline.py::AgentLoop"]
        == UNVERIFIED_MODEL_ASSERTION
    )
    assert "holds the pipeline" in grounded and "holds the loop" in grounded


def test_user_supplied_referent_is_retained_and_still_only_unverified():
    grounded, findings = ground_answer_text(
        "config/settings.py contains an invalid option.",
        [_evidence()],
        user_input="Why is config/settings.py broken?",
    )

    assert "contains an invalid option" in grounded
    assert "I could not establish" in grounded
    assert findings[0].status == USER_SUPPLIED_UNVERIFIED


# ── DEFECT B — a supported extension may not match a token prefix ─────────────

def _paths(text: str) -> list[str]:
    return [reference.path for reference in extract_repository_entities(text)]


def test_round6_extension_prefix_false_positives_are_gone():
    assert _paths("args.cmd") == []
    assert _paths("_pytest.capture.CaptureFixture") == []
    assert _paths("Cordis.plugin") == []
    # t.json is a genuine file spelling; the defect was truncating it to t.js.
    assert _paths("t.json") == ["t.json"]

    for text, truncated in (
        ("args.cmd", "args.c"),
        ("t.json", "t.js"),
        ("_pytest.capture.CaptureFixture", "_pytest.capture.C"),
        ("Cordis.plugin", "Cordis.pl"),
    ):
        assert truncated not in _paths(text)


def test_dotted_identifiers_do_not_become_partial_file_paths():
    for text in (
        "Cordis.plugin",
        "pytest.main",
        "pathlib.Path",
        "argparse.Namespace",
        "_pytest.capture.CaptureFixture",
        "logging.config",
        "os.path",
    ):
        assert _paths(text) == []


def test_overlapping_extensions_resolve_longest_first():
    assert _paths("config.json") == ["config.json"]
    assert _paths("src/app.js") == ["src/app.js"]
    assert _paths("src/app.jsx") == ["src/app.jsx"]
    assert _paths("src/app.mjs") == ["src/app.mjs"]
    assert _paths("src/app.ts") == ["src/app.ts"]
    assert _paths("src/app.tsx") == ["src/app.tsx"]
    assert _paths("module.c") == ["module.c"]
    assert _paths("module.cc") == ["module.cc"]
    assert _paths("module.cpp") == ["module.cpp"]
    assert _paths("module.cxx") == ["module.cxx"]
    assert _paths("stub.py") == ["stub.py"]
    assert _paths("stub.pyi") == ["stub.pyi"]
    assert _paths("page.htm") == ["page.htm"]
    assert _paths("page.html") == ["page.html"]
    assert _paths("build.yml") == ["build.yml"]
    assert _paths("build.yaml") == ["build.yaml"]


def test_real_file_paths_and_composites_still_match():
    assert _paths("core/code_dna.py") == ["core/code_dna.py"]
    references = extract_repository_entities("core/code_dna.py::_classify_indent")
    assert len(references) == 1
    assert references[0].path == "core/code_dna.py"
    assert references[0].symbol == "_classify_indent"

    composite = extract_repository_entities("file.py::Class.method")
    assert len(composite) == 1
    assert composite[0].identity == "file.py::Class.method"

    lined = extract_repository_entities("main.py:12")
    assert len(lined) == 1
    assert lined[0].path == "main.py" and lined[0].line == 12


def test_path_boundary_keeps_paths_found_next_to_ordinary_punctuation():
    for text, expected in (
        ("See config.json.", ["config.json"]),
        ("See config.json, then main.py;", ["config.json", "main.py"]),
        ("(src/app.tsx)", ["src/app.tsx"]),
        ("`core/code_dna.py`", ["core/code_dna.py"]),
        ("- main.py\n- calc.py", ["main.py", "calc.py"]),
    ):
        assert _paths(text) == expected


def test_node_js_external_product_guard_is_unchanged():
    evidence = _evidence(paths=("main.py",))

    product, product_findings = ground_answer_text(
        "The Node.js front end is unrelated; Vue.js is not used either.", [evidence]
    )
    assert product_findings == ()
    assert product == "The Node.js front end is unrelated; Vue.js is not used either."

    # A stem rule would have exempted these; whole-spelling matching does not.
    for text in ("types.ts is broken.", "path.ts is broken.", "src/app.js is broken."):
        grounded, findings = ground_answer_text(text, [evidence])
        assert findings[0].status == UNVERIFIED_MODEL_ASSERTION
        assert "is broken" in grounded


def test_a_dotted_identifier_beside_a_real_path_downgrades_only_the_symbol():
    evidence = _evidence(paths=("core/executor.py",))
    text = "core/executor.py reads args.cmd before `Cordis.plugin` dispatches."

    grounded, findings = ground_answer_text(text, [evidence])
    statuses = _statuses(findings)

    assert statuses["core/executor.py"] == GROUNDED_EXISTING
    assert "args.c" not in statuses and "Cordis.pl" not in statuses
    assert "core/executor.py reads args.cmd before" in grounded


# ── Receipt, boundaries and compatibility ────────────────────────────────────

def test_receipt_reports_the_remediation_scope_without_confidence_or_authority():
    state = SimpleNamespace(repo_path=None, user_input="fix it", project_tag="")
    block = {
        "summary": "The bug is in the PatchGenerator.generate method.",
        "patch_candidate": None,
        "write_authority": False,
        "patch_application_authority": False,
    }

    _, _, display, receipt = ground_answer_for_display(state, "", block)

    assert receipt["remediation_scope"] == "entity_span"
    assert receipt["surrounding_text_preserved"] is True
    assert LIVE3_PHASE_ID in receipt["phase_ids"]
    assert receipt["authority_effect"] == "none"
    assert receipt["retrieval_effect"] == "none"
    assert "confidence" not in json.dumps(receipt)
    assert display["write_authority"] is False
    assert display["patch_application_authority"] is False


def test_no_repository_scan_model_call_or_network_is_introduced():
    source = open(
        os.path.join(os.path.dirname(__file__), "..", "core", "answer_entity_grounding.py"),
        encoding="utf-8",
    ).read()

    for forbidden in (
        "os.walk",
        "rglob",
        "glob(",
        "import requests",
        "import httpx",
        "import urllib",
        "import socket",
        "import subprocess",
        "openai",
        "anthropic",
        "google.generativeai",
        "import ollama",
        "from agents",
        "import agents",
        "core.retriever",
        "core.indexer",
        "write_authority =",
        "patch_application_authority =",
    ):
        assert forbidden not in source, forbidden

    # No T5-specific allowlist may be smuggled in as a "fix".
    for smuggled in ("Cordis", "AgentLoop", "ReactLoopAgent", "AbortController"):
        assert smuggled not in source, smuggled


def test_extension_alternation_is_constructed_longest_first():
    from core.answer_entity_grounding import _COMMON_REPOSITORY_EXTENSIONS

    lengths = [len(item) for item in _COMMON_REPOSITORY_EXTENSIONS.split("|")]
    assert lengths == sorted(lengths, reverse=True)


def test_path_grammar_pins_the_post_extension_boundary():
    from core.answer_entity_grounding import _EXTENSION_BOUNDARY, _ENTITY_RE

    assert _EXTENSION_BOUNDARY == r"(?![A-Za-z0-9_])"
    assert _EXTENSION_BOUNDARY in _ENTITY_RE.pattern
    # The boundary must sit inside the path group, right after the extension.
    assert re.search(
        r"\)\)" + re.escape(_EXTENSION_BOUNDARY), _ENTITY_RE.pattern
    ) is not None


def test_proposed_new_paths_and_symbols_still_escape_the_downgrade():
    state = SimpleNamespace(repo_path=None, user_input="add priority", project_tag="")
    block = {
        "summary": "Create new_priority.py and introduce `PriorityFilter` there.",
        "patch_plan": [
            {
                "op": "create_file",
                "relative_path": "new_priority.py",
                "content": "class PriorityFilter:\n    pass\n",
            }
        ],
        "patch_candidate": None,
        "write_authority": False,
    }

    _, _, display, receipt = ground_answer_for_display(state, "", block)

    assert display["summary"] == block["summary"]
    assert PROPOSED_NEW in {item["status"] for item in receipt["entity_statuses"]}
    assert receipt["unverified_entity_count"] == 0
