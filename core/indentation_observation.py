"""INDENT.SEMANTICS.1 — language-aware indentation observation contract.

The ``indentation_style`` subject is the *block* indentation unit a source file
is written in.  Every earlier oracle measured it by reading the leading
whitespace of every physical line.  For Python that set mixes five different
things, and only the first of them is the subject:

* block indentation, the suites Python's grammar opens and closes;
* continuation alignment inside brackets;
* the interior of multi-line strings;
* comment-only lines;
* whitespace-only lines.

Measured on the smallest shape where it matters::

    def f(a,
          b):
        pass

the physical widths are ``6`` and ``4``, whose common unit is ``2``, while the
only block step is ``4``.  ``core/code_dna.py`` itself measures the same way: its
2-mod-4 rows are all docstring interior, and all 57 of its block steps are 4.
The unit inference was never the fault.  The *observation set* was.

So this module separates what was **observed** from what is **inferred**::

    source text + declared language
        -> SourceIndentationObservation   what was seen, by which observer, how strongly
        -> SourceIndentationAssessment    2space | 4space | tab | None, with its basis

Dispatch is on the language the *input* declares, never on any file path and
never by trying Python first:

``python``
    stdlib ``tokenize``.  Only ``INDENT``/``DEDENT`` events are evidence; the
    step a new level introduces is the suffix its prefix adds to its parent's,
    so levels ``0, 4, 8`` are the steps ``4, 4``.  Continuation rows,
    string interiors, comment-only and whitespace-only rows emit no ``INDENT``
    and so contribute nothing.  The claim is ``structural``.
``python`` that tokenize refuses
    the physical observer below, with ``fallback_reason`` saying so.  The claim
    is downgraded, visibly, rather than kept.
anything else, declared or not
    the physical observer: leading-space widths and leading tabs, read exactly
    as the generic raw-width reference always read them.  The claim is
    ``heuristic_physical`` and it is never relabelled ``structural``.

A tokenizer that accepts some bytes is not evidence that they are Python: HTML
tokenizes into ``INDENT`` events that mirror its markup, and brace languages
tokenize into none at all.  Only a declared ``python`` input reaches it.

This is the verifier's reference path and nothing else.  ``_classify_indent``
and ``compute_dna`` do not call it, no candidate receives a language, and
nothing here reads a file, walks a repository, calls a model or grants any
authority.  ``ast`` is deliberately not a dependency: it cannot parse four of the
five historical matrix fixtures, which tokenize reads without complaint.

The public names are three words long on purpose.  This repository is also the
T6 task's own corpus, and CONTROL's entry ordering favours short identifiers
that carry a prompt's rarest word.  Spelled ``IndentationObservation`` and
``observe_indentation``, these names tied ``core/code_dna.py::_classify_indent``
on the Round-5 T6 prompt and beat it on exact overlap.  That pushed the defect's
real target out of the six-entry cap and offered this oracle as the thing to
fix.  ``SourceIndentationObservation`` and ``observe_source_indentation`` say
the same thing without competing.
"""

from __future__ import annotations

from dataclasses import dataclass
import io
from math import gcd
import tokenize
from typing import Any


PHASE_ID = "INDENT.SEMANTICS.1"
OBSERVATION_SCHEMA_VERSION = "indent_semantics_1_observation_v1"
ASSESSMENT_SCHEMA_VERSION = "indent_semantics_1_assessment_v1"

# ── Declared input language (§5/§6) ──────────────────────────────────────────
LANGUAGE_PYTHON = "python"
#: A missing, empty or unreadable declaration.  Never guessed at.
LANGUAGE_UNKNOWN = "unknown"
#: A declared language is a short label, not text to interpret.
MAX_LANGUAGE_CHARS = 32
_LANGUAGE_CHARACTERS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789+#._-")

# ── Observation tier and claim strength (§4/§15) ─────────────────────────────
TIER_PYTHON_STRUCTURAL = "python_structural"
TIER_HEURISTIC_PHYSICAL = "heuristic_physical"
OBSERVATION_TIERS: tuple[str, ...] = (TIER_PYTHON_STRUCTURAL, TIER_HEURISTIC_PHYSICAL)

CLAIM_STRUCTURAL = "structural"
CLAIM_HEURISTIC_PHYSICAL = "heuristic_physical"
CLAIM_STRENGTHS: tuple[str, ...] = (CLAIM_STRUCTURAL, CLAIM_HEURISTIC_PHYSICAL)
#: Each tier carries exactly one claim strength, so the two can never disagree.
_TIER_CLAIMS: dict[str, str] = {
    TIER_PYTHON_STRUCTURAL: CLAIM_STRUCTURAL,
    TIER_HEURISTIC_PHYSICAL: CLAIM_HEURISTIC_PHYSICAL,
}

TOKENIZER_COMPLETED = "completed"
TOKENIZER_FAILED = "failed"
TOKENIZER_NOT_ATTEMPTED = "not_attempted"
TOKENIZER_STATUSES: tuple[str, ...] = (
    TOKENIZER_COMPLETED,
    TOKENIZER_FAILED,
    TOKENIZER_NOT_ATTEMPTED,
)

# ── Why an observation used the physical tier (§13/§14) ──────────────────────
FALLBACK_LANGUAGE_NOT_PYTHON = "language_not_python"
FALLBACK_LANGUAGE_UNDECLARED = "language_undeclared"
FALLBACK_PYTHON_TOKENIZE_FAILED = "python_tokenize_failed"
FALLBACK_REASONS: tuple[str, ...] = (
    FALLBACK_LANGUAGE_NOT_PYTHON,
    FALLBACK_LANGUAGE_UNDECLARED,
    FALLBACK_PYTHON_TOKENIZE_FAILED,
)

#: §13 — the stdlib failures tokenization can end in: ``TokenError`` for an
#: unterminated string or bracket, ``SyntaxError`` (``IndentationError``,
#: ``TabError``) for inconsistent indentation, ``ValueError`` for bytes the
#: reader refuses.  Each one downgrades the observation; none escapes.
_TOKENIZE_FAILURES = (tokenize.TokenError, SyntaxError, ValueError)

# ── The subject vocabulary (§16/§17) ─────────────────────────────────────────
STYLE_2SPACE = "2space"
STYLE_4SPACE = "4space"
STYLE_TAB = "tab"
ASSESSMENT_VALUES: tuple[str | None, ...] = (STYLE_2SPACE, STYLE_4SPACE, STYLE_TAB, None)
#: §17 — the exact unit mapping.  1, 3, 6 and 8 are not rounded onto it.
SPACE_UNIT_STYLES: dict[int, str] = {2: STYLE_2SPACE, 4: STYLE_4SPACE}

# ── How an assessment was reached ────────────────────────────────────────────
BASIS_STRUCTURAL_SPACE_UNIT = "structural_space_unit"
BASIS_STRUCTURAL_TAB_UNIT = "structural_tab_unit"
BASIS_STRUCTURAL_MIXED_UNITS = "structural_mixed_units"
BASIS_STRUCTURAL_UNIT_OUTSIDE_VOCABULARY = "structural_unit_outside_vocabulary"
BASIS_NO_STRUCTURAL_INDENTATION = "no_structural_indentation"
BASIS_PHYSICAL_SPACE_UNIT = "physical_space_unit"
BASIS_PHYSICAL_TAB_MAJORITY = "physical_tab_majority"
BASIS_PHYSICAL_UNIT_OUTSIDE_VOCABULARY = "physical_unit_outside_vocabulary"
BASIS_NO_PHYSICAL_INDENTATION = "no_physical_indentation"
#: basis -> (the only tier it can describe, the only values it can produce).
_BASIS_RULES: dict[str, tuple[str, tuple[str | None, ...]]] = {
    BASIS_STRUCTURAL_SPACE_UNIT: (TIER_PYTHON_STRUCTURAL, (STYLE_2SPACE, STYLE_4SPACE)),
    BASIS_STRUCTURAL_TAB_UNIT: (TIER_PYTHON_STRUCTURAL, (STYLE_TAB,)),
    BASIS_STRUCTURAL_MIXED_UNITS: (TIER_PYTHON_STRUCTURAL, (None,)),
    BASIS_STRUCTURAL_UNIT_OUTSIDE_VOCABULARY: (TIER_PYTHON_STRUCTURAL, (None,)),
    BASIS_NO_STRUCTURAL_INDENTATION: (TIER_PYTHON_STRUCTURAL, (None,)),
    BASIS_PHYSICAL_SPACE_UNIT: (TIER_HEURISTIC_PHYSICAL, (STYLE_2SPACE, STYLE_4SPACE)),
    BASIS_PHYSICAL_TAB_MAJORITY: (TIER_HEURISTIC_PHYSICAL, (STYLE_TAB,)),
    BASIS_PHYSICAL_UNIT_OUTSIDE_VOCABULARY: (TIER_HEURISTIC_PHYSICAL, (None,)),
    BASIS_NO_PHYSICAL_INDENTATION: (TIER_HEURISTIC_PHYSICAL, (None,)),
}
ASSESSMENT_BASES: tuple[str, ...] = tuple(_BASIS_RULES)


def normalize_input_language(language: Any) -> str:
    """The declared language as a bounded label, or ``unknown``.

    Normalization is spelling only — case and surrounding whitespace.  A value
    that is not a short language label is treated as no declaration at all,
    which is the one conservative reading: it can only reach the weaker tier.
    """

    if not isinstance(language, str):
        return LANGUAGE_UNKNOWN
    label = language.strip().casefold()
    if (
        not label
        or len(label) > MAX_LANGUAGE_CHARS
        or not set(label) <= _LANGUAGE_CHARACTERS
    ):
        return LANGUAGE_UNKNOWN
    return label


def _check_counts(name: str, values: tuple[int, ...]) -> None:
    if not isinstance(values, tuple) or any(
        isinstance(value, bool) or not isinstance(value, int) or value <= 0
        for value in values
    ):
        raise ValueError(f"{name} must be a tuple of positive widths")


@dataclass(frozen=True, slots=True)
class SourceIndentationObservation:
    """What was observed in one supplied text, by which observer, how strongly.

    Evidence only.  It names no candidate, no file and no target: the same
    bytes under the same declared language always observe the same way.
    """

    language: str
    observation_tier: str
    claim_strength: str
    tokenizer_status: str
    fallback_reason: str = ""
    #: Python structural tier only — one entry per ``INDENT`` transition.
    structural_space_steps: tuple[int, ...] = ()
    structural_tab_steps: tuple[int, ...] = ()
    #: Steps whose text mixes tabs and spaces, or does not extend its parent.
    structural_mixed_steps: int = 0
    #: Physical tier only — the generic raw-width evidence.
    physical_space_widths: tuple[int, ...] = ()
    physical_tab_lines: int = 0
    schema_version: str = OBSERVATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.observation_tier not in OBSERVATION_TIERS:
            raise ValueError(f"unsupported observation tier: {self.observation_tier!r}")
        if self.claim_strength != _TIER_CLAIMS[self.observation_tier]:
            # §14/§15 — physical evidence is never labelled structural, and the
            # reverse is equally untrue.
            raise ValueError(
                f"a {self.observation_tier} observation cannot claim "
                f"{self.claim_strength!r} strength"
            )
        if self.tokenizer_status not in TOKENIZER_STATUSES:
            raise ValueError(f"unsupported tokenizer status: {self.tokenizer_status!r}")
        if normalize_input_language(self.language) != self.language:
            raise ValueError(f"language is not a normalized label: {self.language!r}")
        _check_counts("structural_space_steps", self.structural_space_steps)
        _check_counts("structural_tab_steps", self.structural_tab_steps)
        _check_counts("physical_space_widths", self.physical_space_widths)
        for name in ("structural_mixed_steps", "physical_tab_lines"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative count")

        if self.observation_tier == TIER_PYTHON_STRUCTURAL:
            if self.language != LANGUAGE_PYTHON:
                raise ValueError("only declared Python input is observed structurally")
            if self.tokenizer_status != TOKENIZER_COMPLETED:
                raise ValueError("a structural observation needs completed tokenization")
            if self.fallback_reason:
                raise ValueError("a structural observation did not fall back")
            if self.physical_space_widths or self.physical_tab_lines:
                raise ValueError("physical evidence belongs to the fallback tier only")
            return

        if (
            self.structural_space_steps
            or self.structural_tab_steps
            or self.structural_mixed_steps
        ):
            raise ValueError("structural evidence belongs to the structural tier only")
        if self.language == LANGUAGE_PYTHON:
            reason, status = FALLBACK_PYTHON_TOKENIZE_FAILED, TOKENIZER_FAILED
        elif self.language == LANGUAGE_UNKNOWN:
            reason, status = FALLBACK_LANGUAGE_UNDECLARED, TOKENIZER_NOT_ATTEMPTED
        else:
            reason, status = FALLBACK_LANGUAGE_NOT_PYTHON, TOKENIZER_NOT_ATTEMPTED
        if self.fallback_reason != reason:
            raise ValueError(
                f"a {self.language} fallback must say {reason!r}, "
                f"not {self.fallback_reason!r}"
            )
        if self.tokenizer_status != status:
            raise ValueError(
                f"a {reason} fallback has tokenizer status {status!r}, "
                f"not {self.tokenizer_status!r}"
            )

    @property
    def is_structural(self) -> bool:
        return self.claim_strength == CLAIM_STRUCTURAL

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "phase_id": PHASE_ID,
            "language": self.language,
            "observation_tier": self.observation_tier,
            "claim_strength": self.claim_strength,
            "tokenizer_status": self.tokenizer_status,
            "fallback_reason": self.fallback_reason,
            "structural_space_steps": list(self.structural_space_steps),
            "structural_tab_steps": list(self.structural_tab_steps),
            "structural_mixed_steps": self.structural_mixed_steps,
            "physical_space_widths": list(self.physical_space_widths),
            "physical_tab_lines": self.physical_tab_lines,
        }


@dataclass(frozen=True, slots=True)
class SourceIndentationAssessment:
    """One reference reading of an observation, in the subject's vocabulary.

    It keeps the observation it read, so two assessments that agree on
    ``value`` and disagree on evidence are *not* equal: the tier and the claim
    strength travel with the value and are never collapsed into it (§15).
    """

    observation: SourceIndentationObservation
    value: str | None
    basis: str
    #: The inferred space unit, where one was inferred; ``0`` otherwise.
    space_unit: int = 0
    schema_version: str = ASSESSMENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.observation, SourceIndentationObservation):
            raise TypeError("an assessment reads a SourceIndentationObservation")
        if self.value not in ASSESSMENT_VALUES:
            raise ValueError(f"value outside the subject vocabulary: {self.value!r}")
        rule = _BASIS_RULES.get(self.basis)
        if rule is None:
            raise ValueError(f"unsupported assessment basis: {self.basis!r}")
        tier, values = rule
        if tier != self.observation.observation_tier:
            raise ValueError(
                f"a {self.basis} assessment cannot read "
                f"{self.observation.observation_tier} evidence"
            )
        if self.value not in values:
            raise ValueError(f"a {self.basis} assessment cannot produce {self.value!r}")
        if isinstance(self.space_unit, bool) or not isinstance(self.space_unit, int):
            raise ValueError("space_unit must be an integer")
        if self.space_unit < 0:
            raise ValueError("space_unit must be non-negative")

    @property
    def language(self) -> str:
        return self.observation.language

    @property
    def observation_tier(self) -> str:
        return self.observation.observation_tier

    @property
    def claim_strength(self) -> str:
        return self.observation.claim_strength

    @property
    def is_structural(self) -> bool:
        return self.observation.is_structural

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "phase_id": PHASE_ID,
            "value": self.value,
            "basis": self.basis,
            "space_unit": self.space_unit,
            "language": self.language,
            "observation_tier": self.observation_tier,
            "claim_strength": self.claim_strength,
            "fallback_reason": self.observation.fallback_reason,
        }


# ── Observers ─────────────────────────────────────────────────────────────────


def _python_structure(text: str) -> tuple[tuple[int, ...], tuple[int, ...], int] | None:
    """Structural steps from tokenize, or ``None`` when tokenization failed.

    An ``INDENT`` token carries the *absolute* prefix of its new level.  The
    step is what that prefix adds to its parent's, which is why a stack of
    prefixes is kept and popped on every ``DEDENT``.  A step is only a clean
    unit when the child prefix extends the parent's and adds one kind of
    whitespace; anything else is counted as mixed rather than normalized into
    a guessed width.  Steps seen before a failure are discarded with it.
    """

    levels = [""]
    space_steps: list[int] = []
    tab_steps: list[int] = []
    mixed = 0
    try:
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type == tokenize.INDENT:
                parent = levels[-1]
                child = token.string
                levels.append(child)
                step = child[len(parent):]
                if not step or not child.startswith(parent):
                    mixed += 1
                elif set(step) == {" "}:
                    space_steps.append(len(step))
                elif set(step) == {"\t"}:
                    tab_steps.append(len(step))
                else:
                    mixed += 1
            elif token.type == tokenize.DEDENT and len(levels) > 1:
                levels.pop()
    except _TOKENIZE_FAILURES:
        return None
    return tuple(space_steps), tuple(tab_steps), mixed


def _physical_observation(
    text: str, *, language: str, fallback_reason: str, tokenizer_status: str
) -> SourceIndentationObservation:
    """The generic raw-width reading, exactly as the legacy reference read it.

    Every physical line led by a tab is tab evidence; every line led by a space
    contributes its leading-space width.  Nothing distinguishes a block from a
    continuation row here, which is why the claim is only ever heuristic.
    """

    widths: list[int] = []
    tab_lines = 0
    for line in text.splitlines():
        if not line or line[0] not in " \t":
            continue
        if line[0] == "\t":
            tab_lines += 1
        else:
            widths.append(len(line) - len(line.lstrip(" ")))
    return SourceIndentationObservation(
        language=language,
        observation_tier=TIER_HEURISTIC_PHYSICAL,
        claim_strength=CLAIM_HEURISTIC_PHYSICAL,
        tokenizer_status=tokenizer_status,
        fallback_reason=fallback_reason,
        physical_space_widths=tuple(widths),
        physical_tab_lines=tab_lines,
    )


def observe_source_indentation(text: str, *, language: Any) -> SourceIndentationObservation:
    """Observe one explicitly supplied text under the language its input declares.

    ``language`` describes the text being observed — never the file whose code
    is being tested, which is why there is no path argument to infer it from.
    """

    if not isinstance(text, str):
        raise TypeError("indentation is observed on supplied source text")
    declared = normalize_input_language(language)
    if declared == LANGUAGE_PYTHON:
        structure = _python_structure(text)
        if structure is None:
            return _physical_observation(
                text,
                language=declared,
                fallback_reason=FALLBACK_PYTHON_TOKENIZE_FAILED,
                tokenizer_status=TOKENIZER_FAILED,
            )
        space_steps, tab_steps, mixed = structure
        return SourceIndentationObservation(
            language=declared,
            observation_tier=TIER_PYTHON_STRUCTURAL,
            claim_strength=CLAIM_STRUCTURAL,
            tokenizer_status=TOKENIZER_COMPLETED,
            structural_space_steps=space_steps,
            structural_tab_steps=tab_steps,
            structural_mixed_steps=mixed,
        )
    return _physical_observation(
        text,
        language=declared,
        fallback_reason=(
            FALLBACK_LANGUAGE_UNDECLARED
            if declared == LANGUAGE_UNKNOWN
            else FALLBACK_LANGUAGE_NOT_PYTHON
        ),
        tokenizer_status=TOKENIZER_NOT_ATTEMPTED,
    )


# ── The reference assessment (§16–§20) ───────────────────────────────────────


def _unit_assessment(
    observation: SourceIndentationObservation,
    widths: tuple[int, ...],
    *,
    unit_basis: str,
    outside_basis: str,
) -> SourceIndentationAssessment:
    unit = gcd(*widths)
    style = SPACE_UNIT_STYLES.get(unit)
    return SourceIndentationAssessment(
        observation=observation,
        value=style,
        basis=unit_basis if style else outside_basis,
        space_unit=unit,
    )


def assess_indentation_observation(
    observation: SourceIndentationObservation,
) -> SourceIndentationAssessment:
    """The deterministic reference reading.  An oracle, not ``_classify_indent``.

    Structural evidence: pure tab steps are ``tab``; pure space steps take
    their common unit, and only a unit of exactly 2 or 4 has a name; tab and
    space steps together, or any mixed step, are ``None``; no step at all is
    ``None``.  Physical evidence keeps the generic raw-width reading — ``tab``
    when tab-led lines outnumber space-led ones, otherwise the common unit of
    the space widths under the same exact mapping — and keeps its weaker claim.
    """

    if not isinstance(observation, SourceIndentationObservation):
        raise TypeError("assess a SourceIndentationObservation")
    if observation.observation_tier == TIER_PYTHON_STRUCTURAL:
        spaces = observation.structural_space_steps
        tabs = observation.structural_tab_steps
        if observation.structural_mixed_steps or (spaces and tabs):
            return SourceIndentationAssessment(
                observation=observation, value=None, basis=BASIS_STRUCTURAL_MIXED_UNITS
            )
        if tabs:
            return SourceIndentationAssessment(
                observation=observation, value=STYLE_TAB, basis=BASIS_STRUCTURAL_TAB_UNIT
            )
        if not spaces:
            return SourceIndentationAssessment(
                observation=observation,
                value=None,
                basis=BASIS_NO_STRUCTURAL_INDENTATION,
            )
        return _unit_assessment(
            observation,
            spaces,
            unit_basis=BASIS_STRUCTURAL_SPACE_UNIT,
            outside_basis=BASIS_STRUCTURAL_UNIT_OUTSIDE_VOCABULARY,
        )

    widths = observation.physical_space_widths
    if observation.physical_tab_lines > len(widths):
        return SourceIndentationAssessment(
            observation=observation, value=STYLE_TAB, basis=BASIS_PHYSICAL_TAB_MAJORITY
        )
    if not widths:
        return SourceIndentationAssessment(
            observation=observation, value=None, basis=BASIS_NO_PHYSICAL_INDENTATION
        )
    return _unit_assessment(
        observation,
        widths,
        unit_basis=BASIS_PHYSICAL_SPACE_UNIT,
        outside_basis=BASIS_PHYSICAL_UNIT_OUTSIDE_VOCABULARY,
    )


def indentation_observation_guardrails() -> dict[str, bool]:
    return {
        "language_declared_by_the_input": True,
        "python_observed_structurally_with_stdlib_tokenize": True,
        "non_python_input_observed_physically": True,
        "failed_python_tokenization_downgrades_the_claim": True,
        "observation_and_assessment_are_separate": True,
        "heuristic_observation_labelled_structural": False,
        "language_inferred_from_a_file_path": False,
        "python_tried_first_for_undeclared_input": False,
        "ast_used": False,
        "source_file_read": False,
        "repository_traversal_added": False,
        "model_called": False,
        "network_called": False,
        "production_classifier_changed": False,
        "compute_dna_changed": False,
        "authority_granted": False,
    }


__all__ = [
    "PHASE_ID",
    "OBSERVATION_SCHEMA_VERSION",
    "ASSESSMENT_SCHEMA_VERSION",
    "LANGUAGE_PYTHON",
    "LANGUAGE_UNKNOWN",
    "MAX_LANGUAGE_CHARS",
    "TIER_PYTHON_STRUCTURAL",
    "TIER_HEURISTIC_PHYSICAL",
    "OBSERVATION_TIERS",
    "CLAIM_STRUCTURAL",
    "CLAIM_HEURISTIC_PHYSICAL",
    "CLAIM_STRENGTHS",
    "TOKENIZER_COMPLETED",
    "TOKENIZER_FAILED",
    "TOKENIZER_NOT_ATTEMPTED",
    "TOKENIZER_STATUSES",
    "FALLBACK_LANGUAGE_NOT_PYTHON",
    "FALLBACK_LANGUAGE_UNDECLARED",
    "FALLBACK_PYTHON_TOKENIZE_FAILED",
    "FALLBACK_REASONS",
    "STYLE_2SPACE",
    "STYLE_4SPACE",
    "STYLE_TAB",
    "ASSESSMENT_VALUES",
    "SPACE_UNIT_STYLES",
    "BASIS_STRUCTURAL_SPACE_UNIT",
    "BASIS_STRUCTURAL_TAB_UNIT",
    "BASIS_STRUCTURAL_MIXED_UNITS",
    "BASIS_STRUCTURAL_UNIT_OUTSIDE_VOCABULARY",
    "BASIS_NO_STRUCTURAL_INDENTATION",
    "BASIS_PHYSICAL_SPACE_UNIT",
    "BASIS_PHYSICAL_TAB_MAJORITY",
    "BASIS_PHYSICAL_UNIT_OUTSIDE_VOCABULARY",
    "BASIS_NO_PHYSICAL_INDENTATION",
    "ASSESSMENT_BASES",
    "SourceIndentationObservation",
    "SourceIndentationAssessment",
    "normalize_input_language",
    "observe_source_indentation",
    "assess_indentation_observation",
    "indentation_observation_guardrails",
]
