"""INDENT.SEMANTICS.1 — language-aware indentation observation contract.

The ``indentation_style`` subject is the *block* indentation unit a file is
written in.  The raw-width reasoning every earlier oracle used observed
something else: every physical line that starts with a space or a tab.  For
Python that mixes block indentation with continuation alignment, multi-line
string interiors, comment-only lines and whitespace-only lines, and only the
first belongs to the subject.  Measured on two shapes::

    def f(a,
          b):
        pass                 physical widths 6, 4  -> raw unit 2 -> 2space
                             structural step 4     ->              4space

    core/code_dna.py         raw unit 2 (docstring interior rows)
                             57 INDENT events, every step 4 -> 4space

So the observation set was contaminated, not the unit inference.  This phase
separates what was *observed* (typed, with its evidence tier and claim
strength) from what is *inferred* from it, and routes only the verifier's
reference path through the new observer.  ``_classify_indent`` and
``compute_dna`` are untouched: this is an oracle phase, not the T6 fix.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import inspect
import json
import tokenize
from pathlib import Path

import pytest

import core.behavioral_matrix as matrix_module
import core.indentation_observation as observation_module
from core.behavioral_expectation import (
    PROVENANCE_EXPLICIT_USER_FACT,
    SUBJECT_INDENTATION_STYLE,
    extract_behavioral_expectations,
)
from core.behavioral_matrix import (
    BASELINE_REPRODUCED,
    BASELINE_SATISFIED,
    CANDIDATE_FIXED,
    CANDIDATE_PRESERVED,
    DISCRIMINATION_PHASE_IDS,
    MATRIX_PROVENANCE_BEHAVIOR_PRESERVATION,
    MATRIX_PROVENANCE_SUBJECT_INVARIANT,
    RECEIPT_SCHEMA_VERSION,
    ROLE_DEFECT_GENERALIZATION,
    ROLE_PRESERVATION,
    ROLE_PRESERVATION_GENERALIZATION,
    ROLE_PRIMARY_DEFECT,
    ProbeObservation,
    build_behavioral_matrix,
    indentation_depth_fixture,
    indentation_skew_fixture,
    resolve_matrix_case,
)
from core.code_dna import _classify_indent
from core.defect_probe import (
    PROBE_NOT_REPRODUCED,
    PROBE_REPRODUCED,
    _nested_indentation_fixture,
    build_probe_contract_from_behavior_fact,
    build_probe_target_binding,
)
from core.indentation_observation import (
    CLAIM_HEURISTIC_PHYSICAL,
    CLAIM_STRUCTURAL,
    FALLBACK_LANGUAGE_NOT_PYTHON,
    FALLBACK_LANGUAGE_UNDECLARED,
    FALLBACK_PYTHON_TOKENIZE_FAILED,
    TIER_HEURISTIC_PHYSICAL,
    TIER_PYTHON_STRUCTURAL,
    TOKENIZER_COMPLETED,
    TOKENIZER_FAILED,
    TOKENIZER_NOT_ATTEMPTED,
    SourceIndentationAssessment,
    SourceIndentationObservation,
    assess_indentation_observation,
    normalize_input_language,
    observe_source_indentation,
)


ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Hand-written fixtures.  Every expectation below is derived by reading these
# bytes, never by running the code under test.
# ---------------------------------------------------------------------------

#: §10/§24 — the measured minimal continuation shape: one 6-wide alignment
#: row inside brackets, one real 4-wide block step.
PY_CONTINUATION = "def f(a,\n      b):\n    pass\n"
#: §11/§25 — real 4-space block indentation around a docstring whose interior
#: row is 6 wide (2 mod 4).
PY_MULTILINE_STRING = 'def f():\n    """Summary.\n      detail\n    """\n    return 1\n'
#: §12/§41 — a 6-wide comment-only row inside a 4-space suite.
PY_COMMENT_ONLY = "def f():\n    x = 1\n      # aligned comment\n    return x\n"
#: §12/§41 — a 6-wide whitespace-only row inside a 4-space suite.
PY_BLANK_WHITESPACE = "def f():\n    x = 1\n      \n    return x\n"
PY_NESTED_4 = "def f(x):\n    if x:\n        return 1\n    return 2\n"
PY_NESTED_2 = "def f(x):\n  if x:\n    return 1\n  return 2\n"
PY_TABS = "def f(x):\n\tif x:\n\t\treturn 1\n\treturn 2\n"
#: One tab step, then one four-space step nested inside it.
PY_MIXED_LEVELS = "def f(x):\n\tif x:\n\t    return 1\n\treturn 2\n"
#: One step whose own text is two spaces and a tab.
PY_MIXED_STEP = "def f(x):\n  \tif x:\n  \t  return 1\n"
PY_NO_INDENT = "x = 1\ny = 2\n"
#: Indented, dedented to 4, indented again: every transition is one 4-step.
PY_REENTRY = "def f():\n    a\n        b\n    c\n        d\n"
#: tokenize raises IndentationError: dedent to a width that was never a level.
PY_MALFORMED_DEDENT = "def f():\n        x = 1\n    y = 2\n"
#: tokenize raises TokenError: EOF inside an open bracket.
PY_MALFORMED_EOF = "def f(x):\n    return (x,\n"
#: tokenize raises TabError: a tab is deeper than four spaces at tab size 8
#: and shallower at tab size 1, so the two readings disagree.
PY_MALFORMED_TABS = "if x:\n    a = 1\n\tb = 2\n"
GO_TABS = "package main\n\nfunc main() {\n\tif true {\n\t\tprintln(1)\n\t}\n}\n"
JS_4 = "function f(a) {\n    if (a) {\n        return 1;\n    }\n    return 2;\n}\n"
CPP_4 = "int main() {\n    if (x) {\n        return 1;\n    }\n    return 0;\n}\n"
#: Python tokenize accepts this and reports INDENT events mirroring the markup.
HTML_2 = "<html>\n  <body>\n    <p>hi</p>\n  </body>\n</html>\n"

# ---------------------------------------------------------------------------
# The live T6 subject
# ---------------------------------------------------------------------------

T6_QUERY = "2-space indentation is classified as 4-space"
T6_TARGET_FILE = "core/code_dna.py"
T6_TARGET_SYMBOL = "_classify_indent"

CASE_PRIMARY = "indentation_style.primary.2space"
CASE_DEEP_DEFECT = "indentation_style.generalize.2space.deep"
CASE_PRESERVE = "indentation_style.preserve.4space"
CASE_DEEP_PRESERVE = "indentation_style.preserve.4space.deep"
CASE_SKEW = "indentation_style.generalize.2space.skew"
#: §28 — appended after the five historical cases, in this order.
CASE_CONTINUATION = "indentation_style.preserve.4space.continuation"
CASE_MULTILINE_STRING = "indentation_style.preserve.4space.multiline_string"
CASE_GO_TAB = "indentation_style.preserve.tab.go"
LIVE5_CASE_IDS = (
    CASE_PRIMARY,
    CASE_DEEP_DEFECT,
    CASE_PRESERVE,
    CASE_DEEP_PRESERVE,
    CASE_SKEW,
)
CASE_IDS = LIVE5_CASE_IDS + (CASE_CONTINUATION, CASE_MULTILINE_STRING, CASE_GO_TAB)

#: §22 — the five historical contracts, recorded from the production builder
#: *before* this phase changed a byte of it: the sha256 of each contract's
#: identity payload without its target binding, so fixture bytes, expected
#: value, provenance text and execution constraints are all pinned while the
#: repository's own location is not.
#: INDENT.RUNTIME.1 §17 added kwargs={"language": ...} to every case's
#: contract, superseding byte-for-byte contract identity. These are the exact
#: pre-INDENT.RUNTIME.1 values, unchanged, and remain valid once a contract's
#: kwargs is stripped back to {} — see _contract_semantics_without_kwargs and
#: test_the_five_historical_cases_keep_their_contracts_exactly_apart_from_language.
LIVE5_CONTRACT_SEMANTICS_PRE_RUNTIME1 = {
    CASE_PRIMARY: "8aa9fed3361c8ea8e405bb336e81a2f5cc81a26ddcf662c9085fe374f08d2b42",
    CASE_DEEP_DEFECT: "93de85ce66e561644c6eee0684301daa79866dd42b957df342384c9f1073a821",
    CASE_PRESERVE: "025691ee9e55a786587b7222d60498ea77f8a450b2df378fd768fcc070b56f23",
    CASE_DEEP_PRESERVE: "e40642512172a3613a25d411aad552a1d163c97a263c3f35d4b24c53c7ea9d09",
    CASE_SKEW: "e46175250e55767255ef9f50312f6eeadbe60cc3770506570d540c7518843f0b",
}


def _t6_fact():
    (fact,), truncated = extract_behavioral_expectations(T6_QUERY)
    assert truncated is False
    assert fact.subject_kind == SUBJECT_INDENTATION_STYLE
    assert (fact.expected_value, fact.observed_value) == ("2space", "4space")
    return fact


def _t6_contract():
    binding = build_probe_target_binding(
        repo_path=ROOT,
        target_file=T6_TARGET_FILE,
        target_symbol=T6_TARGET_SYMBOL,
        source_snippet=inspect.getsource(_classify_indent),
        candidate_eligible=True,
    )
    assert binding is not None
    contract = build_probe_contract_from_behavior_fact(
        target=binding, behavior_fact=_t6_fact()
    )
    assert contract is not None
    return contract


def _t6_cases():
    return build_behavioral_matrix(probe_contract=_t6_contract(), behavior_fact=_t6_fact())


def _fixture(case) -> str:
    (text,) = case.contract.structured_input["args"]
    return text


def _contract_semantics(contract) -> str:
    payload = contract.identity_payload()
    payload.pop("target")
    return hashlib.sha256(
        json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _python(text: str) -> tuple[SourceIndentationObservation, SourceIndentationAssessment]:
    observed = observe_source_indentation(text, language="python")
    return observed, assess_indentation_observation(observed)


def _declared(text: str, language) -> tuple[SourceIndentationObservation, SourceIndentationAssessment]:
    observed = observe_source_indentation(text, language=language)
    return observed, assess_indentation_observation(observed)


# ═══════════════════════════════════════════════════════════════════════════
# §6/§7/§8 — Python input is observed structurally, by tokenize
# ═══════════════════════════════════════════════════════════════════════════


def test_python_input_is_observed_by_the_structural_tier():
    observed, assessed = _python(PY_NESTED_4)

    assert observed.language == "python"
    assert observed.observation_tier == TIER_PYTHON_STRUCTURAL
    assert observed.claim_strength == CLAIM_STRUCTURAL
    assert observed.tokenizer_status == TOKENIZER_COMPLETED
    assert observed.fallback_reason == ""
    assert observed.structural_space_steps == (4, 4)
    assert observed.structural_tab_steps == ()
    assert observed.structural_mixed_steps == 0
    # §4 — physical evidence exists only on the fallback tier.
    assert observed.physical_space_widths == ()
    assert observed.physical_tab_lines == 0
    assert assessed.value == "4space"
    assert assessed.observation is observed


def test_steps_are_transitions_between_levels_not_absolute_levels():
    """§8/§9 — levels 0, 6, 8 are the steps 6 and 2, never the widths 6 and 8."""

    observed, assessed = _python("level_0\n      level_1\n        level_2\n")

    assert observed.structural_space_steps == (6, 2)
    assert assessed.value == "2space"


def test_a_dedent_returns_to_the_parent_level_before_the_next_step():
    """§8 — the stack is popped on DEDENT, so re-entering a suite is a 4-step."""

    observed, assessed = _python(PY_REENTRY)

    assert observed.structural_space_steps == (4, 4, 4)
    assert observed.structural_mixed_steps == 0
    assert assessed.value == "4space"


@pytest.mark.parametrize(
    "label, text, steps, expected",
    [
        # §23 — the five historical LIVE.5 fixtures, built by the very
        # constructors the matrix uses, keep their prior expectations.
        ("A primary.2space", _nested_indentation_fixture(2), (2, 2, 2), "2space"),
        (
            "B generalize.2space.deep",
            indentation_depth_fixture(2, (0, 3, 4, 4, 3)),
            (6, 2),
            "2space",
        ),
        ("C preserve.4space", _nested_indentation_fixture(4), (4, 4, 4), "4space"),
        (
            "D preserve.4space.deep",
            indentation_depth_fixture(4, (0, 2, 3, 3, 2)),
            (8, 4),
            "4space",
        ),
        ("E generalize.2space.skew", indentation_skew_fixture(2), (2, 2), "2space"),
    ],
)
def test_the_historical_live5_fixtures_keep_their_expectations(
    label, text, steps, expected
):
    observed, assessed = _python(text)

    assert observed.observation_tier == TIER_PYTHON_STRUCTURAL, label
    assert observed.structural_space_steps == steps, label
    assert assessed.value == expected, label


def test_a1_to_a4_are_not_ast_parseable_and_are_still_structurally_observed():
    """§7/§22 — tokenize, not AST, is the minimal primitive that reads them."""

    for text in (
        _nested_indentation_fixture(2),
        indentation_depth_fixture(2, (0, 3, 4, 4, 3)),
        _nested_indentation_fixture(4),
        indentation_depth_fixture(4, (0, 2, 3, 3, 2)),
    ):
        with pytest.raises(IndentationError):
            ast.parse(text)
        assert observe_source_indentation(text, language="python").observation_tier == (
            TIER_PYTHON_STRUCTURAL
        )


# ═══════════════════════════════════════════════════════════════════════════
# §10/§11/§12 — only block structure is indentation evidence
# ═══════════════════════════════════════════════════════════════════════════


def test_continuation_alignment_creates_no_structural_step():
    observed, assessed = _python(PY_CONTINUATION)

    assert observed.structural_space_steps == (4,)
    assert assessed.value == "4space"


def test_multiline_string_interior_creates_no_structural_step():
    ast.parse(PY_MULTILINE_STRING)
    observed, assessed = _python(PY_MULTILINE_STRING)

    assert observed.structural_space_steps == (4,)
    assert assessed.value == "4space"


def test_comment_only_whitespace_creates_no_structural_step():
    observed, assessed = _python(PY_COMMENT_ONLY)

    assert observed.structural_space_steps == (4,)
    assert assessed.value == "4space"


def test_blank_whitespace_creates_no_structural_step():
    observed, assessed = _python(PY_BLANK_WHITESPACE)

    assert observed.structural_space_steps == (4,)
    assert assessed.value == "4space"


@pytest.mark.parametrize(
    "text, physical_widths",
    [
        (PY_CONTINUATION, (6, 4)),
        (PY_MULTILINE_STRING, (4, 6, 4, 4)),
        (PY_COMMENT_ONLY, (4, 6, 4)),
        (PY_BLANK_WHITESPACE, (4, 6, 4)),
    ],
)
def test_red_green_the_raw_width_reference_calls_each_4space_sample_2space(
    text, physical_widths
):
    """§62 — the pre-phase reference model, and the structural one, side by side.

    Same bytes.  Read as undeclared source they reach the physical observer,
    whose unit is 2 because one non-block row is 2 mod 4.  Read as Python they
    reach tokenize, and the only step is 4.
    """

    raw, raw_assessed = _declared(text, None)
    assert raw.observation_tier == TIER_HEURISTIC_PHYSICAL
    assert raw.physical_space_widths == physical_widths
    assert raw_assessed.value == "2space"

    _structural, structural_assessed = _python(text)
    assert structural_assessed.value == "4space"


def test_ordinary_nested_two_space_python():
    observed, assessed = _python(PY_NESTED_2)

    assert observed.structural_space_steps == (2, 2)
    assert assessed.value == "2space"


# ═══════════════════════════════════════════════════════════════════════════
# §9/§17/§18/§19 — step text, unit inference and the closed vocabulary
# ═══════════════════════════════════════════════════════════════════════════


def test_pure_tab_steps_are_a_tab_unit():
    observed, assessed = _python(PY_TABS)

    assert observed.structural_tab_steps == (1, 1)
    assert observed.structural_space_steps == ()
    assert assessed.value == "tab"


def test_a_tab_step_and_a_space_step_are_mixed_evidence_not_a_guess():
    observed, assessed = _python(PY_MIXED_LEVELS)

    assert observed.structural_tab_steps == (1,)
    assert observed.structural_space_steps == (4,)
    assert assessed.value is None


def test_a_step_that_mixes_tabs_and_spaces_is_mixed_evidence_not_a_guess():
    observed, assessed = _python(PY_MIXED_STEP)

    assert observed.structural_mixed_steps == 1
    assert assessed.value is None


def test_no_structural_indentation_is_none():
    observed, assessed = _python(PY_NO_INDENT)

    assert observed.observation_tier == TIER_PYTHON_STRUCTURAL
    assert observed.structural_space_steps == ()
    assert assessed.value is None


@pytest.mark.parametrize(
    "text, steps",
    [
        ("def f():\n return 1\n", (1,)),
        ("def f():\n   return 1\n", (3,)),
        ("def f():\n      return 1\n", (6,)),
        ("def f():\n        return 1\n", (8,)),
        ("def f():\n   if x:\n      return 1\n", (3, 3)),
    ],
)
def test_a_unit_outside_the_vocabulary_is_none_never_rounded(text, steps):
    """§17 — 1, 3, 6 and 8 are not quietly mapped onto 2space or 4space."""

    observed, assessed = _python(text)

    assert observed.structural_space_steps == steps
    assert assessed.value is None


def test_the_physical_fallback_uses_the_same_exact_vocabulary():
    raw, assessed = _declared("x\n   y\n      z\n", None)

    assert raw.physical_space_widths == (3, 6)
    assert assessed.value is None


def test_the_only_values_are_the_subject_vocabulary():
    samples = (
        PY_NESTED_2,
        PY_NESTED_4,
        PY_TABS,
        PY_MIXED_LEVELS,
        PY_NO_INDENT,
        GO_TABS,
        JS_4,
        PY_MALFORMED_EOF,
        "def f():\n   return 1\n",
    )
    values = set()
    for text in samples:
        for language in ("python", "go", None):
            values.add(assess_indentation_observation(
                observe_source_indentation(text, language=language)
            ).value)
    assert values <= {"2space", "4space", "tab", None}


# ═══════════════════════════════════════════════════════════════════════════
# §13/§39 — malformed Python downgrades, visibly, and never crashes
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "text, widths, tabs, expected",
    [
        (PY_MALFORMED_DEDENT, (8, 4), 0, "4space"),
        (PY_MALFORMED_EOF, (4,), 0, "4space"),
        (PY_MALFORMED_TABS, (4,), 1, "4space"),
    ],
)
def test_malformed_python_downgrades_to_the_physical_fallback(
    text, widths, tabs, expected
):
    observed, assessed = _python(text)

    assert observed.language == "python"
    assert observed.observation_tier == TIER_HEURISTIC_PHYSICAL
    assert observed.claim_strength == CLAIM_HEURISTIC_PHYSICAL
    assert observed.tokenizer_status == TOKENIZER_FAILED
    assert observed.fallback_reason == FALLBACK_PYTHON_TOKENIZE_FAILED
    # Steps tokenize reported before it failed are discarded, not kept as a
    # partial structural claim.
    assert observed.structural_space_steps == ()
    assert observed.structural_tab_steps == ()
    assert observed.physical_space_widths == widths
    assert observed.physical_tab_lines == tabs
    assert assessed.value == expected
    assert assessed.claim_strength == CLAIM_HEURISTIC_PHYSICAL


def test_each_malformed_sample_really_fails_stdlib_tokenize():
    import io

    for text, error in (
        (PY_MALFORMED_DEDENT, IndentationError),
        (PY_MALFORMED_EOF, tokenize.TokenError),
        (PY_MALFORMED_TABS, TabError),
    ):
        with pytest.raises(error):
            list(tokenize.generate_tokens(io.StringIO(text).readline))


# ═══════════════════════════════════════════════════════════════════════════
# §5/§6/§14/§38/§40 — language belongs to the input, and nothing is guessed
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "text, language, expected",
    [
        (GO_TABS, "go", "tab"),
        (JS_4, "javascript", "4space"),
        (CPP_4, "cpp", "4space"),
        (HTML_2, "html", "2space"),
    ],
)
def test_declared_non_python_input_is_observed_physically(text, language, expected):
    observed, assessed = _declared(text, language)

    assert observed.language == language
    assert observed.observation_tier == TIER_HEURISTIC_PHYSICAL
    assert observed.claim_strength == CLAIM_HEURISTIC_PHYSICAL
    assert observed.tokenizer_status == TOKENIZER_NOT_ATTEMPTED
    assert observed.fallback_reason == FALLBACK_LANGUAGE_NOT_PYTHON
    assert observed.structural_space_steps == ()
    assert assessed.value == expected


def test_the_go_fallback_keeps_the_generic_tab_evidence():
    observed, assessed = _declared(GO_TABS, "go")

    assert observed.physical_tab_lines == 3
    assert observed.physical_space_widths == ()
    assert assessed.value == "tab"


@pytest.mark.parametrize(
    "text, expected",
    [
        # One tab-led line against one space-led line is not a tab majority.
        ("a\n\tb\n  c\n", "2space"),
        # Two against one is.
        ("a\n\tb\n\tc\n  d\n", "tab"),
    ],
)
def test_the_fallback_keeps_the_generic_strict_tab_majority(text, expected):
    """§14/§20 — the legacy raw-width reading, unchanged, on the weaker tier."""

    _observed, assessed = _declared(text, "go")

    assert assessed.value == expected
    assert assessed.claim_strength == CLAIM_HEURISTIC_PHYSICAL


@pytest.mark.parametrize("language", [None, "", "   ", "unknown", "UNKNOWN"])
def test_missing_or_unknown_language_is_observed_physically(language):
    observed, assessed = _declared(PY_NESTED_4, language)

    assert observed.language == "unknown"
    assert observed.observation_tier == TIER_HEURISTIC_PHYSICAL
    assert observed.fallback_reason == FALLBACK_LANGUAGE_UNDECLARED
    assert observed.tokenizer_status == TOKENIZER_NOT_ATTEMPTED
    assert assessed.value == "4space"


@pytest.mark.parametrize(
    "language, normalized",
    [
        ("python", "python"),
        (" Python ", "python"),
        ("PYTHON", "python"),
        ("Go", "go"),
        ("c++", "c++"),
        (None, "unknown"),
        ("", "unknown"),
        ("unknown", "unknown"),
        ("not a language name", "unknown"),
    ],
)
def test_language_names_are_normalized_not_interpreted(language, normalized):
    assert normalize_input_language(language) == normalized


@pytest.mark.parametrize(
    "text, language",
    [
        (GO_TABS, "go"),
        (JS_4, "javascript"),
        (CPP_4, "cpp"),
        (HTML_2, "html"),
        (PY_NESTED_4, "unknown"),
        (PY_NESTED_4, None),
    ],
)
def test_non_python_input_never_reaches_the_python_tokenizer(
    text, language, monkeypatch
):
    """§6/§40 — no parser guessing: the tokenizer is not even called."""

    calls: list[str] = []
    real = tokenize.generate_tokens

    def spy(readline):
        calls.append("called")
        return real(readline)

    monkeypatch.setattr(tokenize, "generate_tokens", spy)
    observe_source_indentation(text, language=language)

    assert calls == []


def test_python_input_does_reach_the_python_tokenizer(monkeypatch):
    calls: list[str] = []
    real = tokenize.generate_tokens

    def spy(readline):
        calls.append("called")
        return real(readline)

    monkeypatch.setattr(tokenize, "generate_tokens", spy)
    observe_source_indentation(PY_NESTED_4, language="python")

    assert calls == ["called"]


def test_tokenizer_acceptance_is_not_evidence_that_the_input_is_python():
    """§6/§40 — HTML tokenizes into INDENT events; declared HTML ignores them."""

    as_python, _ = _python(HTML_2)
    as_html, _ = _declared(HTML_2, "html")

    # tokenize happily reports two 2-steps for markup nesting ...
    assert as_python.observation_tier == TIER_PYTHON_STRUCTURAL
    assert as_python.structural_space_steps == (2, 2)
    # ... and a declared HTML input never enters that path at all.
    assert as_html.observation_tier == TIER_HEURISTIC_PHYSICAL
    assert as_html.structural_space_steps == ()


def test_brace_languages_tokenize_to_zero_structural_events():
    """§26/§40 — why a Python-only observer would return None for them."""

    for text in (GO_TABS, JS_4, CPP_4):
        observed, assessed = _python(text)
        assert observed.observation_tier == TIER_PYTHON_STRUCTURAL
        assert observed.structural_space_steps == ()
        assert observed.structural_tab_steps == ()
        assert assessed.value is None


def test_the_same_bytes_under_two_declared_languages_may_differ():
    """§38 — expected, and not an inconsistency: language is part of the input."""

    as_python, python_value = _python(PY_CONTINUATION)
    as_unknown, unknown_value = _declared(PY_CONTINUATION, "unknown")

    assert as_python.observation_tier == TIER_PYTHON_STRUCTURAL
    assert as_unknown.observation_tier == TIER_HEURISTIC_PHYSICAL
    assert python_value.value == "4space"
    assert unknown_value.value == "2space"
    # And each is deterministic on its own.
    assert _python(PY_CONTINUATION) == (as_python, python_value)
    assert _declared(PY_CONTINUATION, "unknown") == (as_unknown, unknown_value)


def test_the_observer_takes_text_and_a_declared_language_and_nothing_else():
    """§5 — there is no path, file or target parameter to infer language from."""

    parameters = inspect.signature(observe_source_indentation).parameters

    assert list(parameters) == ["text", "language"]
    assert parameters["language"].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters["language"].default is inspect.Parameter.empty


def test_the_observer_refuses_non_text_input():
    with pytest.raises(TypeError):
        observe_source_indentation(b"def f():\n    pass\n", language="python")


# ═══════════════════════════════════════════════════════════════════════════
# §2/§4/§15/§20 — observation and assessment are typed, separate, and honest
# ═══════════════════════════════════════════════════════════════════════════


def test_equal_values_from_different_tiers_are_not_the_same_evidence():
    structural_obs, structural = _python(PY_NESTED_4)
    heuristic_obs, heuristic = _declared(PY_NESTED_4, "go")

    assert structural.value == heuristic.value == "4space"
    assert structural != heuristic
    assert structural.observation_tier == TIER_PYTHON_STRUCTURAL
    assert heuristic.observation_tier == TIER_HEURISTIC_PHYSICAL
    assert structural.claim_strength == CLAIM_STRUCTURAL
    assert heuristic.claim_strength == CLAIM_HEURISTIC_PHYSICAL
    assert structural.is_structural is True
    assert heuristic.is_structural is False
    assert structural_obs != heuristic_obs


def _heuristic_fields(**overrides):
    fields = {
        "language": "go",
        "observation_tier": TIER_HEURISTIC_PHYSICAL,
        "claim_strength": CLAIM_HEURISTIC_PHYSICAL,
        "tokenizer_status": TOKENIZER_NOT_ATTEMPTED,
        "fallback_reason": FALLBACK_LANGUAGE_NOT_PYTHON,
        "physical_space_widths": (4,),
    }
    fields.update(overrides)
    return fields


def _structural_fields(**overrides):
    fields = {
        "language": "python",
        "observation_tier": TIER_PYTHON_STRUCTURAL,
        "claim_strength": CLAIM_STRUCTURAL,
        "tokenizer_status": TOKENIZER_COMPLETED,
        "structural_space_steps": (4,),
    }
    fields.update(overrides)
    return fields


@pytest.mark.parametrize(
    "fields",
    [
        # heuristic evidence may never claim structural strength
        _heuristic_fields(claim_strength=CLAIM_STRUCTURAL),
        # a structural tier may never carry a heuristic claim
        _structural_fields(claim_strength=CLAIM_HEURISTIC_PHYSICAL),
        # only Python input reaches the structural tier
        _structural_fields(language="go"),
        # a structural observation is one whose tokenization completed
        _structural_fields(tokenizer_status=TOKENIZER_FAILED),
        _structural_fields(fallback_reason=FALLBACK_PYTHON_TOKENIZE_FAILED),
        # physical widths exist only on the fallback tier
        _structural_fields(physical_space_widths=(4,)),
        _structural_fields(physical_tab_lines=1),
        # structural steps exist only on the structural tier
        _heuristic_fields(structural_space_steps=(4,)),
        _heuristic_fields(structural_tab_steps=(1,)),
        # a fallback always says why, in the closed vocabulary
        _heuristic_fields(fallback_reason=""),
        _heuristic_fields(fallback_reason="felt_like_it"),
        # the fallback reason has to describe the declared language
        _heuristic_fields(language="python"),
        _heuristic_fields(language="unknown"),
        _heuristic_fields(fallback_reason=FALLBACK_LANGUAGE_UNDECLARED),
        # a tokenizer failure is only ever Python's
        _heuristic_fields(fallback_reason=FALLBACK_PYTHON_TOKENIZE_FAILED),
        _heuristic_fields(
            language="python",
            fallback_reason=FALLBACK_PYTHON_TOKENIZE_FAILED,
            tokenizer_status=TOKENIZER_NOT_ATTEMPTED,
        ),
        _heuristic_fields(tokenizer_status=TOKENIZER_COMPLETED),
        # closed vocabularies
        _heuristic_fields(observation_tier="vibes"),
        _structural_fields(tokenizer_status="maybe"),
        # evidence is non-negative
        _structural_fields(structural_space_steps=(0,)),
        _heuristic_fields(physical_tab_lines=-1),
    ],
)
def test_the_observation_type_refuses_dishonest_or_mixed_up_fields(fields):
    with pytest.raises(ValueError):
        SourceIndentationObservation(**fields)


def test_the_assessment_type_refuses_a_value_outside_the_vocabulary():
    observed = observe_source_indentation(PY_NESTED_4, language="python")
    with pytest.raises(ValueError):
        SourceIndentationAssessment(
            observation=observed,
            value="8space",
            basis=observation_module.BASIS_STRUCTURAL_SPACE_UNIT,
        )
    with pytest.raises(ValueError):
        SourceIndentationAssessment(observation=observed, value="4space", basis="made_up")


def test_the_assessment_type_refuses_a_basis_its_evidence_cannot_support():
    """§15/§20 — a heuristic reading can never be relabelled as structural."""

    structural = observe_source_indentation(PY_NESTED_4, language="python")
    heuristic = observe_source_indentation(PY_NESTED_4, language="go")

    with pytest.raises(ValueError):
        SourceIndentationAssessment(
            observation=heuristic,
            value="4space",
            basis=observation_module.BASIS_STRUCTURAL_SPACE_UNIT,
        )
    with pytest.raises(ValueError):
        SourceIndentationAssessment(
            observation=structural,
            value="4space",
            basis=observation_module.BASIS_PHYSICAL_SPACE_UNIT,
        )
    # A basis also fixes which values it can produce.
    with pytest.raises(ValueError):
        SourceIndentationAssessment(
            observation=structural,
            value="tab",
            basis=observation_module.BASIS_STRUCTURAL_SPACE_UNIT,
        )
    with pytest.raises(ValueError):
        SourceIndentationAssessment(
            observation=structural,
            value="4space",
            basis=observation_module.BASIS_NO_STRUCTURAL_INDENTATION,
        )


def test_observation_and_assessment_are_immutable():
    observed, assessed = _python(PY_NESTED_4)

    with pytest.raises(dataclasses.FrozenInstanceError):
        observed.observation_tier = TIER_HEURISTIC_PHYSICAL  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        assessed.value = "2space"  # type: ignore[misc]


def test_the_observation_describes_source_evidence_not_candidate_identity():
    """§4 — no fingerprint, candidate or target field on either type."""

    for record in (SourceIndentationObservation, SourceIndentationAssessment):
        for field in dataclasses.fields(record):
            assert "fingerprint" not in field.name
            assert "candidate" not in field.name
            assert "target" not in field.name
            assert "path" not in field.name


def test_the_serialized_forms_are_bounded_and_carry_no_source_text():
    observed, assessed = _python(PY_MULTILINE_STRING)
    rendered = repr(observed.as_dict()) + repr(assessed.as_dict())

    assert "detail" not in rendered
    assert "Summary" not in rendered
    assert assessed.as_dict()["value"] == "4space"
    assert assessed.as_dict()["observation_tier"] == TIER_PYTHON_STRUCTURAL
    assert assessed.as_dict()["claim_strength"] == CLAIM_STRUCTURAL
    assert observed.as_dict()["structural_space_steps"] == [4]


# ═══════════════════════════════════════════════════════════════════════════
# §42 — core/code_dna.py, as one bounded corroboration source
# ═══════════════════════════════════════════════════════════════════════════


def test_core_code_dna_py_is_4space_structurally_and_2space_raw():
    """§42 — semantics from tokenize, not from known line numbers."""

    text = (ROOT / "core" / "code_dna.py").read_text(encoding="utf-8")

    raw, raw_assessed = _declared(text, "unknown")
    structural, structural_assessed = _python(text)

    # The contaminated physical reading: some rows are 2 mod 4 ...
    assert any(width % 4 == 2 for width in raw.physical_space_widths)
    assert raw_assessed.value == "2space"
    # ... and every one of them is invisible to block structure.
    assert structural.observation_tier == TIER_PYTHON_STRUCTURAL
    assert structural.structural_space_steps
    assert set(structural.structural_space_steps) == {4}
    assert structural.structural_tab_steps == ()
    assert structural.structural_mixed_steps == 0
    assert structural_assessed.value == "4space"


# ═══════════════════════════════════════════════════════════════════════════
# §53/§54 — local, stdlib-only, no AST, no traversal
# ═══════════════════════════════════════════════════════════════════════════


def test_the_observation_module_is_stdlib_only_and_never_reads_a_file():
    source = inspect.getsource(observation_module)
    tree = ast.parse(source)
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".")[0])
    # §7 — tokenize is the primitive; AST is deliberately not a dependency.
    assert "ast" not in modules
    assert modules <= {"__future__", "dataclasses", "io", "math", "re", "tokenize", "typing"}
    called = {
        node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, (ast.Name, ast.Attribute))
    }
    for forbidden in (
        "open", "read_text", "read_bytes", "walk", "rglob", "glob", "iterdir",
        "exec", "eval", "compile", "parse", "run_gemini_request",
        "run_deepseek_review", "retrieve_context", "suffix", "endswith",
    ):
        assert forbidden not in called, forbidden


# ═══════════════════════════════════════════════════════════════════════════
# §21/§22/§24–§28 — the matrix: eight fixed cases, language on the input
# ═══════════════════════════════════════════════════════════════════════════


def test_the_production_matrix_is_exactly_eight_fixed_cases_in_order():
    cases = _t6_cases()

    assert tuple(case.case_id for case in cases) == CASE_IDS
    assert tuple(case.role for case in cases) == (
        ROLE_PRIMARY_DEFECT,
        ROLE_DEFECT_GENERALIZATION,
        ROLE_PRESERVATION,
        ROLE_PRESERVATION_GENERALIZATION,
        ROLE_DEFECT_GENERALIZATION,
        ROLE_PRESERVATION_GENERALIZATION,
        ROLE_PRESERVATION_GENERALIZATION,
        ROLE_PRESERVATION_GENERALIZATION,
    )
    # §27 — five historical, three new, and eight is the whole set.
    assert len(cases) == 8


def _contract_semantics_without_kwargs(contract) -> str:
    """INDENT.RUNTIME.1 — identity with kwargs stripped back to {}, so the
    pre-phase pinned digests keep verifying everything the phase did not
    touch: fixture bytes, expected value, provenance text, execution
    constraints. Only ever used for the "what changed" proof below."""

    payload = contract.identity_payload()
    payload.pop("target")
    payload["structured_input"] = {**payload["structured_input"], "kwargs": {}}
    return hashlib.sha256(
        json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def test_the_five_historical_cases_keep_their_contracts_exactly_apart_from_language():
    """§22, superseded by INDENT.RUNTIME.1 §17: ids, fixture bytes, expected
    values, provenance and execution constraints are still exactly
    INDENT.SEMANTICS.1's; the only addition is kwargs={"language": "python"}
    on every one of these five contracts."""

    by_id = {case.case_id: case for case in _t6_cases()}

    for case_id, digest in LIVE5_CONTRACT_SEMANTICS_PRE_RUNTIME1.items():
        assert _contract_semantics_without_kwargs(by_id[case_id].contract) == digest, case_id
        assert by_id[case_id].contract.structured_input["kwargs"] == {
            "language": "python"
        }, case_id
    assert [by_id[case_id].expected for case_id in LIVE5_CASE_IDS] == [
        "2space",
        "2space",
        "4space",
        "4space",
        "2space",
    ]
    assert [by_id[case_id].provenance for case_id in LIVE5_CASE_IDS] == [
        PROVENANCE_EXPLICIT_USER_FACT,
        MATRIX_PROVENANCE_SUBJECT_INVARIANT,
        MATRIX_PROVENANCE_BEHAVIOR_PRESERVATION,
        MATRIX_PROVENANCE_SUBJECT_INVARIANT,
        MATRIX_PROVENANCE_SUBJECT_INVARIANT,
    ]


@pytest.mark.parametrize(
    "case_id, fixture, expected, provenance, language",
    [
        (
            CASE_CONTINUATION,
            PY_CONTINUATION,
            "4space",
            MATRIX_PROVENANCE_SUBJECT_INVARIANT,
            "python",
        ),
        (
            CASE_MULTILINE_STRING,
            PY_MULTILINE_STRING,
            "4space",
            MATRIX_PROVENANCE_SUBJECT_INVARIANT,
            "python",
        ),
        # §26 — a compatibility case: behavior the baseline already produces,
        # in the nearest existing closed vocabulary, and no new role.
        (
            CASE_GO_TAB,
            GO_TABS,
            "tab",
            MATRIX_PROVENANCE_BEHAVIOR_PRESERVATION,
            "go",
        ),
    ],
)
def test_each_new_case_carries_its_declared_contract(
    case_id, fixture, expected, provenance, language
):
    case = {item.case_id: item for item in _t6_cases()}[case_id]

    assert case.role == ROLE_PRESERVATION_GENERALIZATION
    assert case.provenance == provenance
    assert case.provenance != PROVENANCE_EXPLICIT_USER_FACT
    assert case.expected == expected
    assert case.input_language == language
    assert _fixture(case) == fixture
    assert "not a user requirement" in case.contract.provenance_reference


def test_every_case_declares_the_language_of_its_input():
    """§5/§22 — A-G are Python samples; H is Go; the target is a .py file."""

    cases = _t6_cases()

    assert [case.input_language for case in cases] == [
        "python",
        "python",
        "python",
        "python",
        "python",
        "python",
        "python",
        "go",
    ]
    assert {case.contract.target.file for case in cases} == {T6_TARGET_FILE}


def test_every_case_carries_its_reference_observation_and_claim():
    cases = {case.case_id: case for case in _t6_cases()}

    for case_id in CASE_IDS[:-1]:
        reference = cases[case_id].reference
        assert reference.language == "python", case_id
        assert reference.observation_tier == TIER_PYTHON_STRUCTURAL, case_id
        assert reference.claim_strength == CLAIM_STRUCTURAL, case_id
    go = cases[CASE_GO_TAB].reference
    assert go.language == "go"
    assert go.observation_tier == TIER_HEURISTIC_PHYSICAL
    assert go.claim_strength == CLAIM_HEURISTIC_PHYSICAL
    assert go.observation.fallback_reason == FALLBACK_LANGUAGE_NOT_PYTHON


def test_the_language_aware_reference_passes_the_whole_battery():
    """§32 — the new positive reference control, recomputed independently."""

    for case in _t6_cases():
        assessed = assess_indentation_observation(
            observe_source_indentation(_fixture(case), language=case.input_language)
        )
        assert assessed.value == case.expected, case.case_id
        # The reference the case carries is exactly that recomputation.
        assert case.reference == assessed, case.case_id


def test_the_legacy_raw_width_reading_fails_the_continuation_and_string_cases():
    """§31/§62 — the pre-phase reference, run over the same eight fixtures."""

    verdicts = {
        case.case_id: assess_indentation_observation(
            observe_source_indentation(_fixture(case), language=None)
        ).value
        for case in _t6_cases()
    }

    assert verdicts == {
        CASE_PRIMARY: "2space",
        CASE_DEEP_DEFECT: "2space",
        CASE_PRESERVE: "4space",
        CASE_DEEP_PRESERVE: "4space",
        CASE_SKEW: "2space",
        # The two shapes whose physical widths are contaminated.
        CASE_CONTINUATION: "2space",
        CASE_MULTILINE_STRING: "2space",
        CASE_GO_TAB: "tab",
    }


def test_the_baseline_classifier_fails_the_defect_cases_and_holds_the_rest():
    """§36 — each new case is a real preservation oracle: the baseline holds it."""

    observed = {case.case_id: _classify_indent(_fixture(case)) for case in _t6_cases()}

    assert observed == {
        CASE_PRIMARY: "4space",
        CASE_DEEP_DEFECT: "4space",
        CASE_PRESERVE: "4space",
        CASE_DEEP_PRESERVE: "4space",
        CASE_SKEW: "4space",
        CASE_CONTINUATION: "4space",
        CASE_MULTILINE_STRING: "4space",
        CASE_GO_TAB: "tab",
    }


def test_the_input_language_never_comes_from_the_target_path():
    """§5/§38 — a .py target, and a case whose input is declared Go."""

    go = {case.case_id: case for case in _t6_cases()}[CASE_GO_TAB]

    assert go.contract.target.file.endswith(".py")
    assert go.input_language == "go"
    assert go.reference.observation_tier == TIER_HEURISTIC_PHYSICAL
    # Declared Python instead, the same bytes reach tokenize — and produce no
    # structural evidence at all, which is why the language has to be the
    # input's own and not a guess from where the function under test lives.
    as_python = observe_source_indentation(_fixture(go), language="python")
    assert as_python.observation_tier == TIER_PYTHON_STRUCTURAL
    assert assess_indentation_observation(as_python).value is None


def test_candidate_execution_now_receives_the_cases_declared_language():
    """Supersedes §21/§37/§44's pre-INDENT.RUNTIME.1 invariant that the
    candidate was called as ``function(text)`` with nothing else.
    INDENT.RUNTIME.1 gave `_classify_indent` a keyword-only `language`
    parameter its body still ignores (proved in
    tests/test_indent_runtime1.py), and gave every matrix case's candidate
    contract that same language as a generic kwarg — the production
    candidate contract can now express what the reference path always could.
    """

    assert list(inspect.signature(_classify_indent).parameters) == ["text", "language"]
    for case in _t6_cases():
        assert case.contract.structured_input == {
            "args": [_fixture(case)],
            "kwargs": {"language": case.input_language},
        }, case.case_id
        payload = case.contract.worker_payload(ROOT)
        assert payload["structured_input"]["kwargs"] == {
            "language": case.input_language
        }
        assert "input_language" not in payload


def test_the_mirrored_fact_gains_the_same_three_fixed_cases():
    """§27 — fixed cases, appended the same way for every indentation fact."""

    (fact,), _truncated = extract_behavioral_expectations(
        "4-space indentation is classified as 2-space"
    )
    binding = _t6_contract().target
    contract = build_probe_contract_from_behavior_fact(target=binding, behavior_fact=fact)
    cases = build_behavioral_matrix(probe_contract=contract, behavior_fact=fact)

    assert [case.case_id for case in cases] == [
        "indentation_style.primary.4space",
        "indentation_style.generalize.4space.deep",
        "indentation_style.preserve.2space",
        "indentation_style.preserve.2space.deep",
        CASE_CONTINUATION,
        CASE_MULTILINE_STRING,
        CASE_GO_TAB,
    ]
    for case in cases:
        assert case.reference.value == case.expected, case.case_id


def test_each_case_result_reveals_language_tier_claim_and_reference():
    """§29 — and a heuristic compatibility case says so in its own receipt."""

    cases = {case.case_id: case for case in _t6_cases()}
    satisfied = ProbeObservation(result=PROBE_NOT_REPRODUCED, observed="tab")
    continuation = resolve_matrix_case(
        cases[CASE_CONTINUATION],
        ProbeObservation(result=PROBE_NOT_REPRODUCED, observed="4space"),
        ProbeObservation(result=PROBE_NOT_REPRODUCED, observed="4space"),
    ).as_dict()
    go = resolve_matrix_case(cases[CASE_GO_TAB], satisfied, satisfied).as_dict()
    primary = resolve_matrix_case(
        cases[CASE_PRIMARY],
        ProbeObservation(result=PROBE_REPRODUCED, observed="4space"),
        ProbeObservation(result=PROBE_NOT_REPRODUCED, observed="2space"),
    ).as_dict()

    assert continuation["input_language"] == "python"
    assert continuation["observation_tier"] == TIER_PYTHON_STRUCTURAL
    assert continuation["claim_strength"] == CLAIM_STRUCTURAL
    assert continuation["fallback_reason"] == ""
    assert continuation["reference_assessment"] == "4space"
    assert continuation["candidate_status"] == CANDIDATE_PRESERVED
    assert go["input_language"] == "go"
    assert go["observation_tier"] == TIER_HEURISTIC_PHYSICAL
    assert go["claim_strength"] == CLAIM_HEURISTIC_PHYSICAL
    assert go["fallback_reason"] == FALLBACK_LANGUAGE_NOT_PYTHON
    assert go["reference_assessment"] == "tab"
    assert primary["baseline_status"] == BASELINE_REPRODUCED
    assert primary["candidate_status"] == CANDIDATE_FIXED
    assert primary["reference_assessment"] == "2space"
    # §29 — the fixture text itself is not copied into the receipt.
    for rendered in (continuation, go, primary):
        assert "def f(" not in json.dumps(rendered)
        assert "package main" not in json.dumps(rendered)
    assert continuation["baseline_status"] == BASELINE_SATISFIED


def test_the_schema_version_and_phase_visibility_moved_together():
    """§55/§56 — every case record gained fields, so the version says so."""

    assert RECEIPT_SCHEMA_VERSION == "behavioral_matrix_live_4_v2"
    assert DISCRIMINATION_PHASE_IDS == (
        "DEFECT.PROBE.LIVE.4",
        "DEFECT.PROBE.LIVE.5",
        "INDENT.SEMANTICS.1",
    )
    # The structure's owner is unchanged: one canonical matrix receipt.
    assert matrix_module.PHASE_ID == "DEFECT.PROBE.LIVE.4"


# ═══════════════════════════════════════════════════════════════════════════
# §31–§36/§59 — the candidate battery, measured in the real sandbox
# ═══════════════════════════════════════════════════════════════════════════

#: The shipped ``_classify_indent`` body — the text every body below replaces.
T6_CLASSIFIER_BODY = (
    "    counts = Counter()\n"
    "    for line in text.splitlines():\n"
    '        if not line or line[0] not in " \\t":\n'
    "            continue\n"
    '        if line.startswith("\\t"):\n'
    '            counts["tab"] += 1\n'
    '        elif line.startswith("    "):\n'
    '            counts["4space"] += 1\n'
    '        elif line.startswith("  "):\n'
    '            counts["2space"] += 1\n'
    "    return counts.most_common(1)[0][0] if counts else None\n"
)

#: §31 — the legacy raw-width control: the common unit of *every* physical
#: leading-space width.  DEFECT.PROBE.LIVE.4 and .5 used these exact bytes as
#: their positive control.  This phase reclassifies them: continuation rows and
#: docstring interiors are in that observation set, so the control demonstrates
#: earlier behavior and defines no oracle truth for those shapes.  Test-only.
T6_LEGACY_RAW_WIDTH_BODY = (
    "    counts = Counter()\n"
    "    space_widths = []\n"
    "    for line in text.splitlines():\n"
    '        if not line or line[0] not in " \\t":\n'
    "            continue\n"
    '        if line.startswith("\\t"):\n'
    '            counts["tab"] += 1\n'
    "        else:\n"
    '            space_widths.append(len(line) - len(line.lstrip(" ")))\n'
    '    if counts["tab"] > len(space_widths):\n'
    '        return "tab"\n'
    "    if space_widths:\n"
    "        unit = 0\n"
    "        for width in space_widths:\n"
    "            left, right = unit, width\n"
    "            while right:\n"
    "                left, right = right, left % right\n"
    "            unit = left\n"
    '        return "2space" if 0 < unit <= 2 else "4space"\n'
    '    return "tab" if counts["tab"] else None\n'
)

#: §34 — Round 10's any-evidence reference form, byte for byte (the Round-10
#: tooling's ``ref10_any_evidence_body.json`` patched snippet plus the final
#: newline this suite's bodies carry): one line whose width is 2 mod 4 decides
#: 2space.  safe_minimal admits it and the five-case matrix accepted it.
T6_ROUND10_ANY_EVIDENCE_BODY = (
    "    counts = Counter()\n"
    "    for line in text.splitlines():\n"
    '        if not line or line[0] not in " \\t":\n'
    "            continue\n"
    '        if line.startswith("\\t"):\n'
    '            counts["tab"] += 1\n'
    "            continue\n"
    "        width = 0\n"
    "        for char in line:\n"
    '            if char != " ":\n'
    "                break\n"
    "            width += 1\n"
    "        if width % 4 == 2:\n"
    '            counts["2space"] += 1\n'
    "        elif width % 4 == 0:\n"
    '            counts["4space"] += 1\n'
    '    if counts["2space"] and counts["2space"] + counts["4space"] > counts["tab"]:\n'
    '        return "2space"\n'
    "    return counts.most_common(1)[0][0] if counts else None\n"
)

#: Block steps by tokenize, as a function body: the child prefix minus the
#: parent's, with ``?`` for a prefix that does not extend its parent.
_T6_BLOCK_STEPS = (
    "    import io\n"
    "    import tokenize\n"
    "\n"
    '    levels = [""]\n'
    "    steps = []\n"
    "    try:\n"
    "        for token in tokenize.generate_tokens(io.StringIO(text).readline):\n"
    "            if token.type == tokenize.INDENT:\n"
    "                parent = levels[-1]\n"
    "                levels.append(token.string)\n"
    "                if token.string.startswith(parent):\n"
    "                    steps.append(token.string[len(parent):])\n"
    "                else:\n"
    '                    steps.append("?")\n'
    "            elif token.type == tokenize.DEDENT and len(levels) > 1:\n"
    "                levels.pop()\n"
    "    except (tokenize.TokenError, SyntaxError, ValueError):\n"
)

#: §26 — a reading that knows only Python block structure: every input is
#: tokenized, and an input with no block step at all answers None.  Test-only.
T6_PYTHON_ONLY_OBSERVER_BODY = (
    _T6_BLOCK_STEPS
    + "        return None\n"
    "    if not steps:\n"
    "        return None\n"
    '    if all(set(step) == {"\\t"} for step in steps):\n'
    '        return "tab"\n'
    '    if not all(set(step) == {" "} for step in steps):\n'
    "        return None\n"
    "    unit = 0\n"
    "    for step in steps:\n"
    "        left, right = unit, len(step)\n"
    "        while right:\n"
    "            left, right = right, left % right\n"
    "        unit = left\n"
    '    return {2: "2space", 4: "4space"}.get(unit)\n'
)

#: §32 — the test-only structural control.  ``_classify_indent(text)`` has no
#: language, so this body tokenizes every input *as Python* — the guess the
#: observation contract forbids — answers from block steps when tokenize
#: reports any, and otherwise falls back to the legacy raw-width reading.  It
#: closes all eight bounded cases, which shows the oracle can open.  It is not a
#: production fix: it reads HTML nesting as block indentation, and
#: safe_minimal refuses it.  Both are measured below.
T6_STRUCTURAL_CONTROL_BODY = (
    _T6_BLOCK_STEPS
    + "        steps = []\n"
    "    if steps:\n"
    '        if all(set(step) == {"\\t"} for step in steps):\n'
    '            return "tab"\n'
    '        if not all(set(step) == {" "} for step in steps):\n'
    "            return None\n"
    "        unit = 0\n"
    "        for step in steps:\n"
    "            left, right = unit, len(step)\n"
    "            while right:\n"
    "                left, right = right, left % right\n"
    "            unit = left\n"
    '        return {2: "2space", 4: "4space"}.get(unit)\n'
    + T6_LEGACY_RAW_WIDTH_BODY
)

ROUND10_FIXTURE = ROOT / "tests" / "fixtures" / "answer_coherence_live1_round10.json"


def _round10_candidate1() -> tuple[str, str]:
    """§35 — Candidate1 exactly as Round 10's revision returned it."""

    from core.json_utils import extract_json_block

    recorded = json.loads(ROUND10_FIXTURE.read_text(encoding="utf-8"))
    candidate = extract_json_block(recorded["candidate1_response"])["patch_candidate"]
    return candidate["target_snippet"], candidate["patched_snippet"]


def _t6_plan(target: str, patched: str) -> list[dict]:
    source = (ROOT / T6_TARGET_FILE).read_text(encoding="utf-8")
    assert target in source
    return [
        {
            "op": "replace_snippet",
            "relative_path": T6_TARGET_FILE,
            "target_snippet": target,
            "patched_snippet": patched,
        }
    ]


def _t6_matrix(plan: list[dict], **kwargs):
    """One candidate across the whole matrix, guarding the real repository."""

    from core.behavioral_matrix import evaluate_behavioral_closure
    from core.defect_probe import execute_defect_probe
    from core.patch_safety import evaluate_patch_safety

    contract = _t6_contract()
    pre = execute_defect_probe(contract, repo_path=ROOT)
    assert pre.probe_result == PROBE_REPRODUCED
    safety = evaluate_patch_safety([T6_TARGET_FILE], project_root=ROOT)
    assert safety.get("ok") is True
    before = (ROOT / T6_TARGET_FILE).read_bytes()
    receipt = evaluate_behavioral_closure(
        repo_path=ROOT,
        candidate_plan=plan,
        probe_contract=contract,
        pre_probe_receipt=pre,
        patch_safety=safety,
        behavior_fact=_t6_fact(),
        **kwargs,
    )
    # Candidate bytes exist only in the disposable sandbox.  Guarded every run.
    assert (ROOT / T6_TARGET_FILE).read_bytes() == before
    assert receipt.closure.sandbox_only is True
    return contract, pre, receipt


def _statuses(receipt) -> dict[str, str]:
    return {item.case_id: item.candidate_status for item in receipt.cases}


def _observed(receipt) -> dict[str, object]:
    return {item.case_id: item.candidate_observed for item in receipt.cases}


def _regressed(receipt) -> list[str]:
    return [
        item.case_id
        for item in receipt.cases
        if item.candidate_status == matrix_module.CANDIDATE_REGRESSED
    ]


def _cases_without(*case_ids: str):
    return tuple(case for case in _t6_cases() if case.case_id not in case_ids)


@pytest.fixture(scope="module")
def t6_legacy_raw_width():
    return _t6_matrix(_t6_plan(T6_CLASSIFIER_BODY, T6_LEGACY_RAW_WIDTH_BODY))


@pytest.fixture(scope="module")
def t6_any_evidence():
    return _t6_matrix(_t6_plan(T6_CLASSIFIER_BODY, T6_ROUND10_ANY_EVIDENCE_BODY))


@pytest.fixture(scope="module")
def t6_round10_reorder():
    return _t6_matrix(_t6_plan(*_round10_candidate1()))


@pytest.fixture(scope="module")
def t6_python_only():
    return _t6_matrix(_t6_plan(T6_CLASSIFIER_BODY, T6_PYTHON_ONLY_OBSERVER_BODY))


@pytest.fixture(scope="module")
def t6_structural_control():
    return _t6_matrix(_t6_plan(T6_CLASSIFIER_BODY, T6_STRUCTURAL_CONTROL_BODY))


@pytest.fixture(scope="module")
def t6_round9():
    from tests.test_defect_probe_matrix_live5 import (
        T6_ROUND9_ABSOLUTE_WIDTH_VOTING_BODY,
    )

    return _t6_matrix(
        _t6_plan(T6_CLASSIFIER_BODY, T6_ROUND9_ABSOLUTE_WIDTH_VOTING_BODY)
    )


def test_the_battery_replays_the_measured_bytes():
    """§34/§35 — the same bytes the earlier phases and Round 10 measured."""

    from tests.test_defect_probe_matrix_live import (
        T6_UNIT_INFERRING_BODY as live4_control,
    )
    from tests.test_defect_probe_matrix_live5 import (
        T6_CLASSIFIER_BODY as live5_classifier,
        T6_REORDERED_BRANCHES,
        T6_UNIT_INFERRING_BODY as live5_control,
    )

    assert T6_CLASSIFIER_BODY == live5_classifier
    assert T6_CLASSIFIER_BODY in (ROOT / T6_TARGET_FILE).read_text(encoding="utf-8")
    assert T6_LEGACY_RAW_WIDTH_BODY == live5_control == live4_control
    target, patched = _round10_candidate1()
    assert patched == T6_REORDERED_BRANCHES.rstrip("\n")
    assert target in T6_CLASSIFIER_BODY


# ── §36 — the production baseline, unchanged and still broken ───────────────


def test_the_baseline_reproduces_the_defect_cases_and_holds_every_other(
    t6_any_evidence,
):
    _contract, _pre, receipt = t6_any_evidence
    baseline = {item.case_id: item.baseline_status for item in receipt.cases}
    observed = {item.case_id: item.baseline_observed for item in receipt.cases}

    assert baseline == {
        CASE_PRIMARY: BASELINE_REPRODUCED,
        CASE_DEEP_DEFECT: BASELINE_REPRODUCED,
        CASE_PRESERVE: BASELINE_SATISFIED,
        CASE_DEEP_PRESERVE: BASELINE_SATISFIED,
        CASE_SKEW: BASELINE_REPRODUCED,
        CASE_CONTINUATION: BASELINE_SATISFIED,
        CASE_MULTILINE_STRING: BASELINE_SATISFIED,
        CASE_GO_TAB: BASELINE_SATISFIED,
    }
    assert observed == {
        CASE_PRIMARY: "4space",
        CASE_DEEP_DEFECT: "4space",
        CASE_PRESERVE: "4space",
        CASE_DEEP_PRESERVE: "4space",
        CASE_SKEW: "4space",
        CASE_CONTINUATION: "4space",
        CASE_MULTILINE_STRING: "4space",
        CASE_GO_TAB: "tab",
    }


# ── §31/§59 — the legacy raw-width control ───────────────────────────────────


def test_the_legacy_control_still_passes_the_historical_cases(t6_legacy_raw_width):
    _contract, _pre, receipt = t6_legacy_raw_width
    statuses = _statuses(receipt)

    assert [statuses[case_id] for case_id in LIVE5_CASE_IDS] == [
        CANDIDATE_FIXED,
        CANDIDATE_FIXED,
        CANDIDATE_PRESERVED,
        CANDIDATE_PRESERVED,
        CANDIDATE_FIXED,
    ]


def test_the_legacy_control_fails_both_python_structural_cases(t6_legacy_raw_width):
    _contract, _pre, receipt = t6_legacy_raw_width

    assert _regressed(receipt) == [CASE_CONTINUATION, CASE_MULTILINE_STRING]
    assert _observed(receipt)[CASE_CONTINUATION] == "2space"
    assert _observed(receipt)[CASE_MULTILINE_STRING] == "2space"
    assert _statuses(receipt)[CASE_GO_TAB] == CANDIDATE_PRESERVED
    assert receipt.matrix_status == matrix_module.MATRIX_FIXED_BUT_REGRESSIVE
    assert receipt.closure_ready is False


# ── §34/§62 — the Round-10 any-evidence false positive ──────────────────────


def test_round10_any_evidence_passes_all_five_historical_cases(t6_any_evidence):
    _contract, _pre, receipt = t6_any_evidence
    statuses = _statuses(receipt)

    assert [statuses[case_id] for case_id in LIVE5_CASE_IDS] == [
        CANDIDATE_FIXED,
        CANDIDATE_FIXED,
        CANDIDATE_PRESERVED,
        CANDIDATE_PRESERVED,
        CANDIDATE_FIXED,
    ]


def test_round10_any_evidence_fails_the_continuation_and_multiline_cases(
    t6_any_evidence,
):
    _contract, _pre, receipt = t6_any_evidence

    assert _regressed(receipt) == [CASE_CONTINUATION, CASE_MULTILINE_STRING]
    assert _observed(receipt)[CASE_CONTINUATION] == "2space"
    assert _observed(receipt)[CASE_MULTILINE_STRING] == "2space"
    assert _statuses(receipt)[CASE_GO_TAB] == CANDIDATE_PRESERVED


def test_round10_any_evidence_is_not_fixed_and_preserved(t6_any_evidence):
    _contract, _pre, receipt = t6_any_evidence

    assert receipt.matrix_status == matrix_module.MATRIX_FIXED_BUT_REGRESSIVE
    assert receipt.matrix_status != matrix_module.MATRIX_FIXED_AND_PRESERVED
    assert receipt.closure_ready is False
    assert receipt.rejection_reasons == (
        matrix_module.REASON_PRESERVATION_REGRESSED,
        f"{matrix_module.REASON_PRESERVATION_REGRESSED}:{CASE_CONTINUATION}",
        f"{matrix_module.REASON_PRESERVATION_REGRESSED}:{CASE_MULTILINE_STRING}",
    )
    # A legacy LIVE.3 reader is narrowed with it, never told the pair closed.
    from core.candidate_defect_probe import CLOSURE_FIXED_BUT_REGRESSIVE
    from core.paired_defect_probe import PAIRED_FIXED_BUT_REGRESSIVE

    assert receipt.paired_status == PAIRED_FIXED_BUT_REGRESSIVE
    assert receipt.defect_closure_status == CLOSURE_FIXED_BUT_REGRESSIVE


def test_red_green_the_five_case_oracle_accepted_the_any_evidence_candidate():
    """§34/§62 — the primary proof: the same bytes, the same sandbox rules.

    Under the five historical cases the candidate closes.  With the two Python
    structural cases appended it does not, and nothing else about the run
    changed: the five historical verdicts are identical in both.
    """

    plan = _t6_plan(T6_CLASSIFIER_BODY, T6_ROUND10_ANY_EVIDENCE_BODY)
    live5_only = _cases_without(CASE_CONTINUATION, CASE_MULTILINE_STRING, CASE_GO_TAB)
    assert tuple(case.case_id for case in live5_only) == LIVE5_CASE_IDS

    # RED: the pre-phase oracle is satisfied by the measured false positive.
    _contract, _pre, old = _t6_matrix(plan, matrix_cases=live5_only)
    assert len(old.cases) == 5
    assert old.matrix_status == matrix_module.MATRIX_FIXED_AND_PRESERVED
    assert old.closure_ready is True

    # GREEN: all five still pass; the structural cases refuse closure.
    _contract, _pre, new = _t6_matrix(plan)
    assert len(new.cases) == 8
    for case_id in LIVE5_CASE_IDS:
        assert _statuses(new)[case_id] == _statuses(old)[case_id], case_id
    assert new.matrix_status == matrix_module.MATRIX_FIXED_BUT_REGRESSIVE
    assert new.closure_ready is False


def _safe_minimal_admits(target: str, patched: str) -> tuple[bool, dict]:
    """The real safe_minimal gate on a throwaway stand-in state (no writes)."""

    import contextlib
    import io
    from types import SimpleNamespace

    import patching.patch_gates as gates

    state = SimpleNamespace(
        task_info={"patch_style": "safe_minimal"},
        patch_style="safe_minimal",
        language="python",
        json_block={
            "summary": "",
            "issues": [],
            "patch_candidate": {
                "file": T6_TARGET_FILE,
                "relative_path": T6_TARGET_FILE,
                "target_node_name": T6_TARGET_SYMBOL,
                "target_node_kind": "function",
                "target_snippet": target,
                "patched_snippet": patched,
            },
            "confidence": 0.9,
            "needs_escalation": False,
        },
        final_answer="",
        human_answer="",
    )
    with contextlib.redirect_stdout(io.StringIO()):
        gates._enforce_safe_minimal(state)
    block = state.json_block
    return isinstance(block.get("patch_candidate"), dict), block


def test_safe_minimal_admits_the_any_evidence_candidate_so_the_oracle_must_stop_it():
    """§34/§51 — safe_minimal is unchanged; the matrix is what now refuses it."""

    admitted, block = _safe_minimal_admits(
        T6_CLASSIFIER_BODY.rstrip("\n"), T6_ROUND10_ANY_EVIDENCE_BODY.rstrip("\n")
    )

    assert admitted is True
    assert block["candidate_novelty_admitted"] is True
    assert block["candidate_novelty_reason"] == "bounded_local_identifier_novelty"
    assert block["candidate_novelty_local_binding_names"] == ["width"]


# ── §35 — the Round-10 branch reorder ───────────────────────────────────────


def test_round10_branch_reorder_still_regresses_4space_preservation(
    t6_round10_reorder,
):
    _contract, _pre, receipt = t6_round10_reorder
    statuses = _statuses(receipt)

    assert statuses[CASE_PRIMARY] == CANDIDATE_FIXED
    assert statuses[CASE_DEEP_DEFECT] == CANDIDATE_FIXED
    assert statuses[CASE_SKEW] == CANDIDATE_FIXED
    # The existing 4-space preservation is what it breaks first ...
    assert _regressed(receipt)[0] == CASE_PRESERVE
    assert receipt.rejection_reasons[1] == (
        f"{matrix_module.REASON_PRESERVATION_REGRESSED}:{CASE_PRESERVE}"
    )
    # ... and the structural cases do not make it look any better.
    assert _regressed(receipt) == [
        CASE_PRESERVE,
        CASE_DEEP_PRESERVE,
        CASE_CONTINUATION,
        CASE_MULTILINE_STRING,
    ]
    assert statuses[CASE_GO_TAB] == CANDIDATE_PRESERVED
    assert receipt.matrix_status == matrix_module.MATRIX_FIXED_BUT_REGRESSIVE


# ── §26 — the Go case exists so a Python-only reading is not rewarded ───────


def test_a_python_only_reading_passes_every_python_case_and_fails_the_go_case(
    t6_python_only,
):
    _contract, _pre, receipt = t6_python_only
    statuses = _statuses(receipt)

    for case_id in CASE_IDS[:-1]:
        assert statuses[case_id] in {CANDIDATE_FIXED, CANDIDATE_PRESERVED}, case_id
    assert _regressed(receipt) == [CASE_GO_TAB]
    assert _observed(receipt)[CASE_GO_TAB] is None
    assert receipt.matrix_status == matrix_module.MATRIX_FIXED_BUT_REGRESSIVE


def test_red_green_without_the_go_case_a_python_only_reading_would_close():
    plan = _t6_plan(T6_CLASSIFIER_BODY, T6_PYTHON_ONLY_OBSERVER_BODY)

    _contract, _pre, without_go = _t6_matrix(
        plan, matrix_cases=_cases_without(CASE_GO_TAB)
    )
    assert without_go.matrix_status == matrix_module.MATRIX_FIXED_AND_PRESERVED

    _contract, _pre, with_go = _t6_matrix(plan)
    assert with_go.matrix_status == matrix_module.MATRIX_FIXED_BUT_REGRESSIVE


# ── §32 — the structural control: the oracle opens, and T6 is not won ──────


def test_the_structural_control_closes_all_eight_cases(t6_structural_control):
    _contract, _pre, receipt = t6_structural_control

    assert [item.case_id for item in receipt.cases] == list(CASE_IDS)
    assert list(_statuses(receipt).values()) == [
        CANDIDATE_FIXED,
        CANDIDATE_FIXED,
        CANDIDATE_PRESERVED,
        CANDIDATE_PRESERVED,
        CANDIDATE_FIXED,
        CANDIDATE_PRESERVED,
        CANDIDATE_PRESERVED,
        CANDIDATE_PRESERVED,
    ]
    assert receipt.matrix_status == matrix_module.MATRIX_FIXED_AND_PRESERVED
    assert receipt.rejection_reasons == ()
    assert receipt.closure_ready is True


def _run_body(body: str, text: str):
    source = inspect.getsource(_classify_indent).replace(T6_CLASSIFIER_BODY, body)
    assert body in source
    namespace: dict = {}
    exec(
        "from collections import Counter\nfrom typing import Optional\n" + source,
        namespace,
    )
    return namespace["_classify_indent"](text)


def test_the_structural_control_guesses_python_for_input_it_cannot_know():
    """§33 — why closing the battery is not the production fix.

    A plain-text outline is not Python, yet tokenize accepts it, and reads its
    parenthesis as a Python bracket.  So a body with no language answers from
    structure the text does not have.  The reference path never does, because
    the input declares what it is — and it keeps the weaker claim for it.
    """

    outline = "Title\n    - item (see\n          notes)\n    - item two\n"

    assert _run_body(T6_STRUCTURAL_CONTROL_BODY, outline) == "4space"
    declared = assess_indentation_observation(observe_source_indentation(outline, language="text"))
    assert declared.observation_tier == TIER_HEURISTIC_PHYSICAL
    assert declared.value == "2space"
    assert observe_source_indentation(outline, language="python").structural_space_steps == (4,)


@pytest.mark.parametrize(
    "body",
    [T6_STRUCTURAL_CONTROL_BODY, T6_PYTHON_ONLY_OBSERVER_BODY],
)
def test_safe_minimal_refuses_every_body_known_to_read_block_structure(body):
    """§33/§49/§51 — the oracle can represent the semantics; the current
    candidate search space cannot express them, and this phase widens nothing.
    """

    admitted, block = _safe_minimal_admits(
        T6_CLASSIFIER_BODY.rstrip("\n"), body.rstrip("\n")
    )

    assert admitted is False
    assert block["candidate_novelty_admitted"] is False
    assert block["candidate_novelty_reason"] == "novel_import"


def test_safe_minimal_also_refused_the_legacy_raw_width_control():
    """The legacy control was only ever measured by placing it directly."""

    admitted, block = _safe_minimal_admits(
        T6_CLASSIFIER_BODY.rstrip("\n"), T6_LEGACY_RAW_WIDTH_BODY.rstrip("\n")
    )

    assert admitted is False
    assert block["candidate_novelty_reason"] == "novel_external_reference"


# ── Round 9, recorded under the wider oracle ────────────────────────────────


def test_the_round9_candidate_now_also_regresses_the_continuation_case(t6_round9):
    """What became of LIVE.5's measured candidate.

    Its skew verdict is unchanged.  On the continuation sample it counts one
    6-wide row as 2space and one 4-wide row as 4space, and the tie resolves to
    the vote it counted first.
    """

    _contract, _pre, receipt = t6_round9

    assert _statuses(receipt)[CASE_SKEW] == matrix_module.CANDIDATE_STILL_REPRODUCED
    assert _regressed(receipt) == [CASE_CONTINUATION]
    assert _observed(receipt)[CASE_CONTINUATION] == "2space"
    assert receipt.matrix_status == matrix_module.MATRIX_FIXED_BUT_REGRESSIVE


# ═══════════════════════════════════════════════════════════════════════════
# §46 — CANDIDATE.VERIFY consumes the enlarged matrix through its reducer
# ═══════════════════════════════════════════════════════════════════════════


def _matrix_verdict(bundle):
    import core.candidate_verification as verification

    contract, _pre, receipt = bundle
    return verification._matrix_verdict(
        receipt.as_telemetry()["behavioral_matrix"],
        candidate=receipt.closure.candidate_fingerprint,
        probe=contract.fingerprint,
    )


def _verification_evidence(bundle) -> dict:
    """The evidence mapping the pipeline assembles, with this run's receipts."""

    import core.candidate_verification as verification
    from core.patch_basis import PATCH_BASIS_GROUNDED_DEFECT

    _contract, pre, receipt = bundle
    block = dict(receipt.as_telemetry())
    block.update(
        {
            "targeted_validation_status": "verified",
            "targeted_validation_category": "candidate_verified",
            "targeted_validation_candidate_fingerprint": (
                receipt.closure.candidate_fingerprint
            ),
            "check_oracle_assessment_status": "current",
            "sandbox_apply_status": "applied",
        }
    )
    return {
        "policy_profile": verification.PROFILE_GROUNDED_DEFECT_BOUNDED_EVIDENCE,
        "patch_basis": PATCH_BASIS_GROUNDED_DEFECT,
        "candidate_fingerprint": receipt.closure.candidate_fingerprint,
        "candidate_target_paths": [T6_TARGET_FILE],
        "patch_safety": {
            "ok": True,
            "candidate_fingerprint": receipt.closure.candidate_fingerprint,
        },
        "pre_probe": pre.as_dict(),
        "candidate_defect_closure": block,
        "targeted_validation": block,
        "oracle_assessment": block,
        "candidate_sandbox_validation": block,
    }


def test_verification_rejects_the_any_evidence_candidate(t6_any_evidence):
    import core.candidate_verification as verification

    verdict, _limits = _matrix_verdict(t6_any_evidence)

    assert verdict.component == verification.COMPONENT_PAIRED_PROBE
    assert verdict.verdict == verification.CONTRADICTING
    assert verdict.reason == verification.REASON_PRESERVATION_REGRESSED
    # The existing reducer names the first regressed case in matrix order.
    assert CASE_CONTINUATION in verdict.detail
    result = verification.evaluate_candidate_verification(
        _verification_evidence(t6_any_evidence)
    )
    assert result.status == verification.REJECTED
    assert result.verified is False
    assert result.review_ready is False
    assert verification.REASON_PRESERVATION_REGRESSED in result.rejection_reasons


def test_verification_rejects_the_branch_reorder_for_4space_preservation(
    t6_round10_reorder,
):
    import core.candidate_verification as verification

    verdict, _limits = _matrix_verdict(t6_round10_reorder)

    assert verdict.verdict == verification.CONTRADICTING
    assert verdict.reason == verification.REASON_PRESERVATION_REGRESSED
    assert CASE_PRESERVE in verdict.detail
    result = verification.evaluate_candidate_verification(
        _verification_evidence(t6_round10_reorder)
    )
    assert result.status == verification.REJECTED


def test_verification_supports_the_structural_control(t6_structural_control):
    import core.candidate_verification as verification

    verdict, limits = _matrix_verdict(t6_structural_control)

    assert verdict.verdict == verification.SUPPORTING
    assert limits == ()


# ═══════════════════════════════════════════════════════════════════════════
# §29/§56/§61 — the one canonical receipt, its cost, and phase visibility
# ═══════════════════════════════════════════════════════════════════════════


def test_the_receipt_reveals_the_phase_and_every_case_semantics(t6_any_evidence):
    _contract, _pre, receipt = t6_any_evidence
    telemetry = receipt.as_telemetry()
    block = telemetry["behavioral_matrix"]

    assert block["discrimination_phase_ids"] == [
        "DEFECT.PROBE.LIVE.4",
        "DEFECT.PROBE.LIVE.5",
        "INDENT.SEMANTICS.1",
    ]
    assert block["schema_version"] == "behavioral_matrix_live_4_v2"
    assert telemetry["behavioral_matrix_schema_version"] == "behavioral_matrix_live_4_v2"
    assert block["case_count"] == telemetry["behavioral_matrix_case_count"] == 8
    semantics = {
        case["case_id"]: (
            case["input_language"],
            case["observation_tier"],
            case["claim_strength"],
            case["fallback_reason"],
            case["reference_assessment"],
        )
        for case in block["cases"]
    }
    structural = (TIER_PYTHON_STRUCTURAL, CLAIM_STRUCTURAL, "")
    assert semantics == {
        CASE_PRIMARY: ("python", *structural, "2space"),
        CASE_DEEP_DEFECT: ("python", *structural, "2space"),
        CASE_PRESERVE: ("python", *structural, "4space"),
        CASE_DEEP_PRESERVE: ("python", *structural, "4space"),
        CASE_SKEW: ("python", *structural, "2space"),
        CASE_CONTINUATION: ("python", *structural, "4space"),
        CASE_MULTILINE_STRING: ("python", *structural, "4space"),
        CASE_GO_TAB: (
            "go",
            TIER_HEURISTIC_PHYSICAL,
            CLAIM_HEURISTIC_PHYSICAL,
            FALLBACK_LANGUAGE_NOT_PYTHON,
            "tab",
        ),
    }
    # The flat and nested copies agree, and there is no second subtree.
    assert telemetry["behavioral_matrix_cases"] == block["cases"]
    assert not any("indent_semantics" in key for key in telemetry)
    # PATCH.AUTHOR.LIVE.3 carries exact bounded inputs from the executed
    # receipt; the semantic oracle and its metadata remain unchanged.
    for case in block["cases"]:
        assert isinstance(case["input_text"], str)
        assert len(case["input_text"].encode("utf-8")) <= 16_384
        assert len(case["case_probe_fingerprint"]) == 64
    rendered = json.dumps(telemetry, ensure_ascii=False)
    for forbidden in ("confidence", "def _classify_indent", "verifier_source"):
        assert forbidden not in rendered, forbidden


def test_eight_cases_still_use_exactly_one_candidate_sandbox(t6_any_evidence):
    _contract, _pre, receipt = t6_any_evidence

    assert receipt.closure.candidate_apply_status == "applied"
    # Seven companion probes in that one sandbox; the primary is never re-run.
    assert len(receipt.closure.preservation_probe_receipts) == 7
    assert set(dict(receipt.closure.preservation_probe_receipts)) == set(CASE_IDS[1:])


def test_matrix_cost_stays_bounded_and_is_reported_by_stage(t6_any_evidence):
    """§61 — three more probes each side; the observation itself is noise."""

    _contract, _pre, receipt = t6_any_evidence

    assert set(receipt.timings) >= {
        "matrix_construction_sec",
        "matrix_baseline_sec",
        "matrix_candidate_probe_sec",
        "matrix_reduction_sec",
        "matrix_total_sec",
    }
    assert receipt.timings["matrix_construction_sec"] < 0.5
    assert receipt.timings["matrix_reduction_sec"] < 0.1


def test_observing_one_supplied_text_is_linear_and_cheap():
    """§61 — O(text) per fixture: a ten-times input costs about ten times."""

    import time

    text = (ROOT / "core" / "code_dna.py").read_text(encoding="utf-8")

    def cost(sample: str) -> float:
        best = float("inf")
        for _ in range(5):
            started = time.perf_counter()
            assess_indentation_observation(observe_source_indentation(sample, language="python"))
            best = min(best, time.perf_counter() - started)
        return best

    single = cost(text)
    tenfold = cost(text * 10)
    assert single < 0.25
    # Linear, with generous headroom for a loaded machine.
    assert tenfold < single * 40


# ═══════════════════════════════════════════════════════════════════════════
# §47/§48/§49/§50 — revision evidence, answer coherence, grounding, authority
# ═══════════════════════════════════════════════════════════════════════════


def test_revision_evidence_carries_the_new_cases_and_none_of_their_metadata(
    t6_any_evidence,
):
    """§47 — canonical semantics survive LIVE.3's executed-input transport."""

    from core.candidate_revision import _counterexample_from_case

    _contract, _pre, receipt = t6_any_evidence
    cases = receipt.as_telemetry()["behavioral_matrix_cases"]
    counterexamples = [_counterexample_from_case(case) for case in cases]

    assert [item.case_id for item in counterexamples] == list(CASE_IDS)
    failed = [item.case_id for item in counterexamples if item.is_failure]
    assert failed == [CASE_CONTINUATION, CASE_MULTILINE_STRING]
    for item, case in zip(counterexamples, cases):
        assert set(item.as_dict()) == {
            "case_id",
            "role",
            "provenance",
            "expected",
            "candidate_observed",
            "status",
            "input_language",
            "input_text",
            "case_probe_fingerprint",
        }
        assert item.input_text == case["input_text"]
        assert item.input_language == case["input_language"]
        assert item.case_probe_fingerprint == case["case_probe_fingerprint"]


def test_round10_under_eight_cases_changes_only_three_preserved_case_lines():
    """§47/§48 — Round 10 replayed through the real lifecycle, as it now runs.

    The revision request differs from the recorded one by exactly the three
    appended preserved cases Candidate0 keeps; removing them rebuilds the
    recorded request byte for byte.  Candidate identities, generation and the
    harness verdict are Round 10's own.
    """

    from core.candidate_presentation import GENERATION_REVISION
    from core.defect_probe import maybe_execute_control_defect_probe
    from core.candidate_sandbox_validation import candidate_fingerprint_from_payload
    from tests.test_answer_coherence_live1 import (
        FP0,
        FP1,
        ROUND10,
        SUMMARY1,
        _control,
        _route,
        _scenario,
    )

    pre = maybe_execute_control_defect_probe(_control(_route()))
    assert pre is not None
    if pre.probe_result != PROBE_REPRODUCED:
        pytest.skip(f"baseline probe was {pre.probe_result}, not reproduced")
    _state, block, requests, recorder = _scenario(
        pre, ROUND10["candidate0_response"], ROUND10["candidate1_response"]
    )

    assert recorder.calls == []
    (request,) = requests
    from _harness_maintenance import before_author_live3_prompt
    request = before_author_live3_prompt(request, ROUND10["control_source_snippet"])
    new_lines = [
        line
        for line in request.split("\n")
        if line.startswith("- case_id=")
        and any(
            f"case_id={case_id} " in line
            for case_id in (CASE_CONTINUATION, CASE_MULTILINE_STRING, CASE_GO_TAB)
        )
    ]
    assert len(new_lines) == 3
    assert all(line.endswith("status=preserved") for line in new_lines)
    historical = "\n".join(line for line in request.split("\n") if line not in new_lines)
    assert len(historical) == ROUND10["candidate1_request_chars"]
    assert hashlib.sha256(historical.encode("utf-8")).hexdigest() == (
        ROUND10["candidate1_request_sha256"]
    )
    # No fixture text reached the author (§47).
    for fixture in (PY_CONTINUATION, PY_MULTILINE_STRING, GO_TABS):
        assert fixture not in request
    # ANSWER.COHERENCE.LIVE.1's bindings are Round 10's own.
    assert block["candidate_revision_previous_candidate_fingerprint"] == FP0
    assert candidate_fingerprint_from_payload(block) == FP1
    assert block["final_candidate_fingerprint"] == FP1
    assert block["final_candidate_generation"] == GENERATION_REVISION
    assert block["candidate_presentation_coherent"] is True
    assert block["summary"] == SUMMARY1
    assert block["candidate_verification_status"] == "rejected"
    assert block["candidate_verification_rejection_reasons"] == [
        "behavior_preservation_regressed"
    ]
    assert block["candidate_revision_preserved_case_count"] == 5
    assert block["candidate_revision_counterexample_count"] == 3


def test_answer_ground_leaves_the_declared_input_metadata_identical(t6_any_evidence):
    """§49 — harness-authored observation fields are immutable through grounding."""

    import copy

    from core.answer_entity_grounding import ground_state_answer

    _contract, _pre, receipt = t6_any_evidence
    payload = receipt.as_telemetry()
    before = copy.deepcopy(payload)

    class _Terminal:
        repo_path = str(ROOT)
        user_input = T6_QUERY
        final_answer = json.dumps(payload, ensure_ascii=False)
        human_answer = T6_QUERY
        json_block = payload

    state = _Terminal()
    ground_state_answer(state)

    assert state.json_block["behavioral_matrix"] == before["behavioral_matrix"]
    assert state.json_block["behavioral_matrix_cases"] == before["behavioral_matrix_cases"]
    go = {case["case_id"]: case for case in state.json_block["behavioral_matrix_cases"]}[
        CASE_GO_TAB
    ]
    assert go["claim_strength"] == CLAIM_HEURISTIC_PHYSICAL
    assert go["input_language"] == "go"


def test_passing_all_eight_cases_authorizes_nothing(t6_structural_control):
    """§50 — verification evidence is not execution authority."""

    _contract, _pre, receipt = t6_structural_control
    telemetry = receipt.as_telemetry()

    assert receipt.matrix_status == matrix_module.MATRIX_FIXED_AND_PRESERVED
    for key in (
        "write_authority",
        "execution_authorized",
        "approval_ready",
        "human_review_eligible",
        "final_repository_changed",
        "auto_apply_allowed",
    ):
        assert key not in telemetry, key
    assert telemetry["behavioral_matrix_authority_effect"] == "none"
    guardrails = matrix_module.behavioral_matrix_guardrails()
    for flag in (
        "write_authority_granted",
        "execution_authorized",
        "auto_apply_granted",
        "human_review_eligibility_granted",
        "model_called",
        "network_called",
        "repository_traversal_added",
        "safe_minimal_changed",
        "targeted_validation_budget_changed",
        "production_classifier_fixed",
        "input_language_inferred_from_target_path",
        "heuristic_reference_labelled_structural",
    ):
        assert guardrails[flag] is False, flag
    # INDENT.RUNTIME.1 §17 — superseded: the candidate now does receive the
    # case's declared language (see test_indent_runtime1.py), and that alone
    # authorizes nothing either — every flag above stays False regardless.
    assert guardrails["candidate_receives_input_language"] is True
    observation_guardrails = observation_module.indentation_observation_guardrails()
    for flag in (
        "authority_granted",
        "model_called",
        "network_called",
        "source_file_read",
        "ast_used",
        "production_classifier_changed",
        "compute_dna_changed",
    ):
        assert observation_guardrails[flag] is False, flag


# ═══════════════════════════════════════════════════════════════════════════
# §46/§50 — the product path, with mutation off and no provider reachable
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def product_run(monkeypatch):
    """Drive the real ``maybe_run_auto_patch`` read-only, exactly as the
    CANDIDATE.VERIFY.LIVE.1 suite does, with every provider entry refused."""

    import core.pipeline as live_pipeline
    from core.defect_probe import execute_defect_probe
    from tests.test_candidate_verification import _t6_candidate, _t6_state

    revision_requests: list[str] = []

    def refuse(*_args, **_kwargs):
        raise AssertionError("a deterministic test reached a provider")

    def no_revision(_state, prompt):
        revision_requests.append(prompt)
        return ""

    monkeypatch.setattr(live_pipeline, "run_gemini_request", refuse)
    monkeypatch.setattr(live_pipeline, "run_deepseek_review", refuse)
    monkeypatch.setattr(live_pipeline, "_call_revision_provider", no_revision)
    monkeypatch.setattr(live_pipeline, "AUTO_PATCH_ENABLED", False)

    def run(target: str, patched: str) -> dict:
        contract = _t6_contract()
        pre = execute_defect_probe(contract, repo_path=ROOT)
        assert pre.probe_result == PROBE_REPRODUCED
        state = _t6_state(_t6_candidate(target, patched), (contract, pre))
        before = (ROOT / T6_TARGET_FILE).read_bytes()
        live_pipeline.maybe_run_auto_patch(state, interactive=False)
        assert (ROOT / T6_TARGET_FILE).read_bytes() == before
        return state.json_block

    run.revision_requests = revision_requests
    return run


def test_product_path_rejects_the_any_evidence_candidate(product_run):
    block = product_run(T6_CLASSIFIER_BODY, T6_ROUND10_ANY_EVIDENCE_BODY)

    assert block["behavioral_matrix_case_count"] == 8
    assert block["behavioral_matrix_status"] == matrix_module.MATRIX_FIXED_BUT_REGRESSIVE
    assert [
        case["case_id"]
        for case in block["behavioral_matrix_cases"]
        if case["candidate_status"] == matrix_module.CANDIDATE_REGRESSED
    ] == [CASE_CONTINUATION, CASE_MULTILINE_STRING]
    assert block["candidate_verification_status"] == "rejected"
    assert "behavior_preservation_regressed" in (
        block["candidate_verification_rejection_reasons"]
    )
    assert block["human_review_eligible"] is False
    assert block["execution_authorized"] is False
    assert block["final_repository_changed"] is False
    # LIVE.3 now carries the exact executed samples as well as their IDs.
    (request,) = product_run.revision_requests
    assert CASE_CONTINUATION in request and CASE_MULTILINE_STRING in request
    assert PY_CONTINUATION in request
    assert PY_MULTILINE_STRING in request


def test_product_path_verifies_the_structural_control_and_authorizes_nothing(
    product_run,
):
    block = product_run(T6_CLASSIFIER_BODY, T6_STRUCTURAL_CONTROL_BODY)

    assert block["behavioral_matrix_case_count"] == 8
    assert block["behavioral_matrix_status"] == matrix_module.MATRIX_FIXED_AND_PRESERVED
    assert block["candidate_verification_status"] == "verified"
    assert block["candidate_verification_rejection_reasons"] == []
    assert block["execution_authorized"] is False
    assert block["final_repository_changed"] is False
    assert block["auto_apply_allowed"] is False
    assert block["write_authority"] is False
    assert block["patch_application_authority"] is False
    assert "human_apply_review" not in block
    assert product_run.revision_requests == []


def test_product_path_rejects_the_round10_branch_reorder(product_run):
    block = product_run(*_round10_candidate1())

    assert block["behavioral_matrix_case_count"] == 8
    assert block["behavioral_matrix_status"] == matrix_module.MATRIX_FIXED_BUT_REGRESSIVE
    regressed = [
        case["case_id"]
        for case in block["behavioral_matrix_cases"]
        if case["candidate_status"] == matrix_module.CANDIDATE_REGRESSED
    ]
    assert regressed[0] == CASE_PRESERVE
    assert block["candidate_verification_status"] == "rejected"
    assert block["execution_authorized"] is False


# ═══════════════════════════════════════════════════════════════════════════
# §3/§43/§60/§63 — one authority, the product frozen, the change reversible
# ═══════════════════════════════════════════════════════════════════════════

FIXTURES = ROOT / "tests" / "fixtures"
REVERSAL_FIXTURE = FIXTURES / "indent_semantics1_reversal.json"
FROZEN_FIXTURE = FIXTURES / "indent_semantics1_frozen_boundaries.json"


def _module_names(relative: str) -> set[str]:
    tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names


def test_there_is_exactly_one_observation_authority():
    """§3 — the observer lives in one module; the matrix only calls it."""

    assert "tokenize" in _module_names("core/indentation_observation.py")
    for relative in (
        "core/behavioral_matrix.py",
        "core/defect_probe.py",
        "core/code_dna.py",
        "core/candidate_verification.py",
    ):
        names = _module_names(relative)
        assert "tokenize" not in names, relative
        assert "gcd" not in names, relative
    matrix_names = _module_names("core/behavioral_matrix.py")
    assert "core.indentation_observation" in matrix_names
    assert {"observe_source_indentation", "assess_indentation_observation"} <= matrix_names


#: RETRIEVE.LIVE.4's verbatim Round-5 T6 prompt.
ROUND5_T6_PROMPT = (
    "When I point the agent at a repository that uses 2-space indentation, the "
    "patches it writes come back using 4-space indentation instead. Something "
    "looks wrong with the way repo style gets detected. Please find the root "
    "cause and fix it."
)


def test_the_oracle_module_never_outcompetes_the_t6_target_for_an_entry_slot():
    """§60 — CONTROL routing and retrieval stay where they were.

    This repository is the T6 task's own corpus.  CONTROL orders entry
    candidates by repository specificity times the share of an identifier the
    prompt explains, then by exact overlap.  Measured on the real 20,952-node
    population, the first names for this module — ``IndentationObservation``,
    ``IndentationAssessment``, ``observe_indentation`` — explained half of
    themselves exactly, as much as ``_classify_indent`` does through a
    morphology bridge, and won the tie.  The T6 target fell to rank 7, outside
    the six-entry cap, and the oracle stood where the defect should.  Every
    matching name now has to explain a smaller share than the target does.
    """

    from core.identifier_recall import (
        extract_query_symbol_candidates,
        match_identifier_entry,
        prepare_identifier_query,
    )

    prepared = prepare_identifier_query(extract_query_symbol_candidates(ROUND5_T6_PROMPT))

    def share(node_id: str) -> float | None:
        match = match_identifier_entry(node_id, prepared)
        if match is None:
            return None
        return len(match.matched_query_tokens) / len(match.identifier_tokens)

    target_share = share(f"{T6_TARGET_FILE}::{T6_TARGET_SYMBOL}")
    assert target_share == 0.5

    tree = ast.parse((ROOT / "core" / "indentation_observation.py").read_text(encoding="utf-8"))
    names = sorted(
        {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.ClassDef))
        }
    )
    shares = {name: share(f"core/indentation_observation.py::{name}") for name in names}
    matching = {name: value for name, value in shares.items() if value is not None}
    assert matching, "the module still says what it is about"
    assert all(value < target_share for value in matching.values()), matching
    # Red: the two-word spellings would have tied the target and won.
    for rejected in ("IndentationObservation", "IndentationAssessment", "observe_indentation"):
        assert share(f"core/indentation_observation.py::{rejected}") == target_share


def test_classify_indent_and_compute_dna_are_still_broken_after_language_transport():
    """§34/§36/§43/§63 — the oracle did not move again.

    indent_semantics1_frozen_boundaries.json's ``definitions`` entries are
    INDENT.SEMANTICS.1's historical pin and are never re-pinned (its own
    ``files`` note says so explicitly); INDENT.RUNTIME.1's own reversal
    receipt (tests/fixtures/indent_runtime1_reversal.json) is what proves
    exactly how the live source now differs from that history, so the digest
    check below reads the *reconstructed historical* source, the same way
    test_every_frozen_boundary_is_byte_identical already does for whole
    files. What still must be true regardless of which phase last touched the
    signature: the known T6 defect reproduces, and it reproduces on a
    classifier that received a language kwarg and ignored it, not only on one
    that never received it at all.
    """

    from _harness_maintenance import before_later_receipts

    frozen = json.loads(FROZEN_FIXTURE.read_text(encoding="utf-8"))
    live_source = (ROOT / T6_TARGET_FILE).read_text(encoding="utf-8")
    historical_source = before_later_receipts(
        T6_TARGET_FILE,
        (ROOT / T6_TARGET_FILE).read_bytes(),
        newer_than=REVERSAL_FIXTURE,
    ).decode("utf-8")

    def digest(source: str, name: str) -> str:
        (node,) = [
            item
            for item in ast.parse(source).body
            if isinstance(item, ast.FunctionDef) and item.name == name
        ]
        return hashlib.sha256(ast.dump(node).encode("utf-8")).hexdigest()

    assert digest(historical_source, "_classify_indent") == (
        frozen["definitions"]["core/code_dna.py::_classify_indent"]
    )
    assert digest(historical_source, "compute_dna") == (
        frozen["definitions"]["core/code_dna.py::compute_dna"]
    )
    # The measured T6 defect is still present, on purpose — and still present
    # when a language is explicitly supplied and ignored (INDENT.RUNTIME.1 §45).
    assert _classify_indent(_nested_indentation_fixture(2)) == "4space"
    assert _classify_indent(_nested_indentation_fixture(2), language="python") == "4space"
    assert _classify_indent(indentation_skew_fixture(2)) == "4space"
    # compute_dna now transports each file's own language (INDENT.RUNTIME.1
    # §7), and the repair-seam import is source-visible but unused by the
    # current (still buggy) body (INDENT.RUNTIME.1 §9/§26) — both checked on
    # the live source, not the reconstructed history.
    assert (
        "ind = _classify_indent(text, language=_language_for_suffix(p.suffix))"
        in live_source
    )
    assert "observe_source_indentation" in live_source
    assert "assess_indentation_observation(" not in live_source


def test_every_frozen_boundary_is_byte_identical():
    """§60 — evaluated through the receipt chain, never re-pinned."""

    from _harness_maintenance import before_later_receipts

    frozen = json.loads(FROZEN_FIXTURE.read_text(encoding="utf-8"))
    assert frozen["phase_id"] == "INDENT.SEMANTICS.1"
    drifted = [
        relative
        for relative, pinned in frozen["files"].items()
        if hashlib.sha256(
            before_later_receipts(
                relative,
                (ROOT / relative).read_bytes(),
                newer_than=REVERSAL_FIXTURE,
            )
        ).hexdigest()
        != pinned
    ]
    assert not drifted, drifted
    for required in (
        "core/code_dna.py",
        "core/defect_probe.py",
        "core/candidate_verification.py",
        "core/candidate_revision.py",
        "core/local_binding_novelty.py",
        "patching/patch_gates.py",
        "core/targeted_repository_validation.py",
        "core/execution_eligibility_policy.py",
        "core/live_execution_authorization.py",
        "core/human_apply_authorization.py",
        "core/candidate_presentation.py",
        "core/answer_entity_grounding.py",
        "core/control_engine.py",
        "core/pipeline.py",
    ):
        assert required in frozen["files"], required
    assert "core/behavioral_matrix.py" not in frozen["files"]
    assert "core/indentation_observation.py" not in frozen["files"]


def _reversal() -> dict:
    return json.loads(REVERSAL_FIXTURE.read_text(encoding="utf-8"))


def test_the_production_change_is_a_reversible_containment_proof():
    """§60 — the shipped bytes rebuild the pre-phase bytes, hunk by hunk.

    INDENT.RUNTIME.1 note: ``core/behavioral_matrix.py`` is not in this
    fixture's own file list, so its "shipped" bytes here are read through
    ``before_later_receipts(..., newer_than=REVERSAL_FIXTURE)`` — the same
    idiom test_every_frozen_boundary_is_byte_identical already uses — so a
    later phase's own edits to that file are undone first and this receipt
    keeps proving exactly what *it* changed, not what changed after it.
    """

    from _harness_maintenance import LATER_RECEIPTS, before_later_receipts

    fixture = _reversal()
    assert [item["path"] for item in fixture["reversals"]] == [
        "core/behavioral_matrix.py",
        "core/phase_registry.py",
    ]
    for reversal in fixture["reversals"]:
        shipped = before_later_receipts(
            reversal["path"],
            (ROOT / reversal["path"]).read_bytes(),
            newer_than=REVERSAL_FIXTURE,
        )
        assert hashlib.sha256(shipped).hexdigest() == reversal["post_sha256"]
        text = shipped.decode("utf-8")
        for hunk in reversal["hunks"]:
            assert text.count(hunk["post"]) == 1
            text = text.replace(hunk["post"], hunk["pre"], 1)
        assert hashlib.sha256(text.encode("utf-8")).hexdigest() == reversal["pre_sha256"]

    # The chain: this phase's preimage is exactly the history already pinned.
    live5 = json.loads(
        (FIXTURES / "defect_probe_live5_frozen_boundaries.json").read_text(
            encoding="utf-8"
        )
    )
    matrix_reversal = fixture["reversals"][0]
    assert matrix_reversal["pre_sha256"] == live5["behavioral_matrix"]["post_sha256"]
    # Newest first: this receipt is undone before any receipt older than it
    # (ANSWER.COHERENCE.LIVE.1's), regardless of what a later phase — such as
    # INDENT.RUNTIME.1 — prepends in front of both.
    assert LATER_RECEIPTS.index(REVERSAL_FIXTURE) < LATER_RECEIPTS.index(
        FIXTURES / "answer_coherence_live1_reversal.json"
    )


def test_the_matrix_change_is_three_helpers_and_five_touched_definitions():
    """INDENT.RUNTIME.1 note: ``post`` here must be the file exactly as
    INDENT.SEMANTICS.1 left it, so a later phase's own edits (this receipt's
    ``newer_than=REVERSAL_FIXTURE`` undoes only receipts strictly newer than
    this one) must not change what this test measures about that transition.
    """

    from _harness_maintenance import before_later_receipts

    def definitions(source: str) -> dict[str, str]:
        return {
            node.name: hashlib.sha256(ast.dump(node).encode("utf-8")).hexdigest()
            for node in ast.parse(source).body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        }

    matrix_reversal, registry_reversal = _reversal()["reversals"]
    for reversal in (matrix_reversal, registry_reversal):
        post = before_later_receipts(
            reversal["path"],
            (ROOT / reversal["path"]).read_bytes(),
            newer_than=REVERSAL_FIXTURE,
        ).decode("utf-8")
        pre = post
        for hunk in reversal["hunks"]:
            pre = pre.replace(hunk["post"], hunk["pre"], 1)
        before, after = definitions(pre), definitions(post)
        assert sorted(set(before) - set(after)) == reversal["removed_definitions"] == []
        assert sorted(set(after) - set(before)) == reversal["added_definitions"]
        assert sorted(
            name for name in before if name in after and before[name] != after[name]
        ) == reversal["changed_definitions"]

    assert matrix_reversal["added_definitions"] == [
        "_declared",
        "_declared_input_cases",
        "_declared_input_fields",
    ]
    assert matrix_reversal["changed_definitions"] == [
        # the declared input language and reference, carried and rendered
        "BehavioralMatrixCase",
        "MatrixCaseResult",
        # the five cases declared, three appended
        "_indentation_matrix_cases",
        # the new guardrail flags
        "behavioral_matrix_guardrails",
        # the two new fields copied from the case
        "resolve_matrix_case",
    ]
    assert matrix_reversal["changed_assignments"] == [
        "DISCRIMINATION_PHASE_IDS",
        "RECEIPT_SCHEMA_VERSION",
        "__all__",
    ]
    assert matrix_reversal["added_assignments"] == [
        "CONTINUATION_FIXTURE",
        "GO_TAB_FIXTURE",
        "INPUT_LANGUAGE_GO",
        "INPUT_LANGUAGE_PYTHON",
        "MULTILINE_STRING_FIXTURE",
    ]
    # The registry module gained one namespace entry and nothing else.
    assert registry_reversal["added_definitions"] == []
    assert registry_reversal["changed_definitions"] == []
    assert registry_reversal["changed_assignments"] == ["PHASE_ID_PREFIXES"]
    from core.phase_registry import PHASE_ID_PREFIXES

    assert "INDENT" in PHASE_ID_PREFIXES
    assert PHASE_ID_PREFIXES.count("INDENT") == 1


# ═══════════════════════════════════════════════════════════════════════════
# Registry
# ═══════════════════════════════════════════════════════════════════════════


def test_the_phase_is_registered_with_its_measured_claim():
    from core.phase_registry import load_phase_registry, validate_phase_registry

    data = load_phase_registry(str(ROOT / "docs" / "roadmap" / "phase_registry.json"))
    by_id = {item["phase_id"]: item for item in data["phases"]}
    phase = by_id[observation_module.PHASE_ID]

    assert phase["track"] == "OPS"
    assert phase["status"] == "complete"
    assert phase["model_calls_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["budget_tier"] == "local_only"
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    for prerequisite in (
        "DEFECT.PROBE.LIVE.5",
        "DEFECT.FACT.LIVE.1",
        "CANDIDATE.VERIFY.LIVE.1",
        "PATCH.MINIMAL.LIVE.2",
        "PATCH.AUTHOR.LIVE.2",
        "ANSWER.COHERENCE.LIVE.1",
        "CONTROL.LOCALIZE.LIVE.2",
        "EXEC.POLICY.LIVE.1",
        "EXEC.APPROVAL.LIVE.1",
        "EXEC.AUTH.LIVE.1",
    ):
        assert prerequisite in phase["prerequisites"], prerequisite
    for artifact in phase["expected_artifacts"]:
        assert (ROOT / artifact).exists(), artifact
    for frozen in ("core/code_dna.py", "patching/patch_gates.py", "core/pipeline.py"):
        assert frozen in phase["forbidden_files"], frozen
    text = " ".join(phase["notes"] + [phase["summary"]]).lower()
    for term in (
        "tokenize",
        "heuristic_physical",
        "structural",
        "continuation",
        "multi-line string",
        "preserve.tab.go",
        "_classify_indent",
        "safe_minimal",
        "no execution authority",
        "no model call",
        "no network call",
    ):
        assert term in text, term
    # The registry validator knows the namespace, so it raises no warning.
    report = validate_phase_registry(data)
    assert not [
        warning for warning in report.get("warnings", []) if "INDENT." in warning
    ]
    ids = {item["phase_id"] for item in data["phases"]}
    # LIVE.3 has shipped; the next unused phase IDs remain absent.
    # This historical phase still did not fix the production target.
    for forbidden_phase in (
        "DEFECT.PROBE.LIVE.6",
        "PATCH.AUTHOR.LIVE.4",
        "INDENT.SEMANTICS.2",
    ):
        assert forbidden_phase not in ids
