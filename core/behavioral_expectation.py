"""DEFECT.FACT.LIVE.1 — typed behavioral expectations, extracted once at intake.

A live T6 black-box run localized correctly and then could not probe.  CONTROL
handed :mod:`core.defect_probe` an exact target and the *raw prompt*, and the
probe adapter re-read that prose with one literal sentence regex::

    "<N>-space indentation is classified as <M>-space"

The user's actual words were semantically identical and structurally different::

    "a repository that uses 2-space indentation, the patches it writes come
     back using 4-space indentation instead"

so the adapter returned ``None``, the contract was never built, and the run
reported *no deterministic typed adapter exists for the preserved task facts*.
The behavior fact was in the order the whole time; nothing had ever typed it.

This module is where it gets typed, exactly once:

    raw user prompt
        -> ExplicitEvidence.behavioral_expectations   [core.explicit_evidence]
        -> SemanticInterpretation                     [core.semantic_waiter]
        -> TaskContract                               [core.task_contract]
        -> LiveTaskShape / LiveRouteReceipt           [WAITER.LIVE.1]
        -> CONTROL carries it beside the localized target
        -> probe contract construction                [core.defect_probe]

**Extraction happens here and nowhere else.**  Downstream components consume a
typed record; none of them re-reads the user's sentence.  CONTROL may *carry* a
behavioral fact and may refuse one, but it may never author or rewrite one.

**Not a second natural-language pipeline.**  The old adapter welded three
separate concerns into one sentence template: which values are legal, which
sentence shape the user must write, and which value means what.  They are
factored apart here into

* one *value* scanner per supported subject kind (bounded, normalizing),
* one *pairing* rule (adjacent values, one sentence, bounded gap), and
* one *closed* table of relation connectives that decides direction.

Adding a wording costs one connective in a table capped by a five-label
relation vocabulary.  Adding a subject kind costs one value scanner.  Neither
is a new sentence template, and nothing here grows toward general language
understanding: a pair with no recognised connective produces no fact at all.

**Direction is pinned.**  ``expected`` is what the user says the behavior
should be; ``observed`` is what the user says it does instead.  For the T6
order that is ``expected=2space`` / ``observed=4space``, and the fields never
swap: a probe is built to check the code against the *user's* expectation.

**A claim is not evidence.**  A behavioral expectation records what the user
said.  It establishes no defect, no patch basis, no target and no authority.
Only DEFECT.PROBE.LIVE.1's bounded execution observes what the code does, and
its observation is recorded separately rather than written back over the claim.

The module is stdlib-only and pure.  It reads no files, contacts no service,
calls no model, inspects no repository, ranks nothing, and grants no authority.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any, Iterable, Mapping, Sequence


PHASE_ID = "DEFECT.FACT.LIVE.1"
BEHAVIORAL_EXPECTATION_SCHEMA_VERSION = "defect_fact_live_1_behavioral_expectation_v1"

# ── Subject kinds ─────────────────────────────────────────────────────────────
#: What the expectation is *about*.  A subject kind exists only when its values
#: can be normalized deterministically, so the vocabulary is short on purpose:
#: an un-normalizable value would be prose wearing a typed field's name.

#: Indentation width style, normalized as ``"<n>space"``.
SUBJECT_INDENTATION_STYLE = "indentation_style"

SUBJECT_KINDS: tuple[str, ...] = (SUBJECT_INDENTATION_STYLE,)

# ── Relation vocabulary ───────────────────────────────────────────────────────
#: How the two values relate *in the user's sentence*.  Five labels, closed.
#: This is deliberately not the probe's oracle relation
#: (:data:`core.defect_probe.RELATION_EQUALS`): that one says how a probe
#: compares an observation to an expectation, this one says how the user phrased
#: the mismatch.  Keeping them apart is what stops a wording from leaking into
#: an oracle.

RELATION_EQUALS = "equals"
RELATION_INSTEAD_OF = "instead_of"
RELATION_CHANGES_FROM_TO = "changes_from_to"
RELATION_DIFFERS_FROM = "differs_from"
RELATION_EXPECTED_VS_OBSERVED = "expected_vs_observed"

BEHAVIOR_RELATIONS: tuple[str, ...] = (
    RELATION_EQUALS,
    RELATION_INSTEAD_OF,
    RELATION_CHANGES_FROM_TO,
    RELATION_DIFFERS_FROM,
    RELATION_EXPECTED_VS_OBSERVED,
)

# ── Provenance ────────────────────────────────────────────────────────────────
#: The user literally stated both values.  This is the *only* provenance a
#: behavioral expectation may carry, and the restriction is the point: a value a
#: model proposed, CONTROL guessed, source code implied or a probe observed can
#: never become the expectation a probe is then built to check.
PROVENANCE_EXPLICIT_USER_FACT = "explicit_user_fact"

BEHAVIOR_PROVENANCES: tuple[str, ...] = (PROVENANCE_EXPLICIT_USER_FACT,)

# ── Selection status vocabulary ───────────────────────────────────────────────
#: Exactly one authoritative fact was available for the requested subject kinds.
FACT_STATUS_AVAILABLE = "available"
#: The order states no behavioral expectation this module can type.
FACT_STATUS_UNAVAILABLE = "behavior_fact_unavailable"
#: The order states more than one incompatible expectation for one subject and
#: nothing here may pick between them.
FACT_STATUS_AMBIGUOUS = "behavior_fact_ambiguous"

FACT_STATUSES: tuple[str, ...] = (
    FACT_STATUS_AVAILABLE,
    FACT_STATUS_UNAVAILABLE,
    FACT_STATUS_AMBIGUOUS,
)

# ── Bounds ────────────────────────────────────────────────────────────────────
#: How many typed expectations one order may carry.
MAX_BEHAVIORAL_EXPECTATIONS = 8
#: How far apart two paired values may sit.  A pair is one thing the user said
#: in one breath, not two facts joined across a paragraph.
MAX_PAIR_GAP_CHARS = 200
#: How far past the second value a trailing connective may sit.
MAX_POSTFIX_CHARS = 40
#: How far before the first value a leading connective or the subject noun may
#: sit.  One window, used for both, so "a word or two before the pair" means the
#: same thing everywhere in this grammar.
MAX_PREFIX_CHARS = 24
#: The literal span a fact quotes back as its provenance.
MAX_SOURCE_TEXT_CHARS = 480


# ── Value scanners ────────────────────────────────────────────────────────────
#
# One per subject kind.  A scanner reports *where* a legal value sits and *what*
# it normalizes to; it decides nothing about meaning.  Widths are a single digit
# 1-8, so ``12-space`` matches nothing rather than matching ``2-space`` inside
# it, and no value is ever read out of the middle of a word or a number.

_INDENT_WIDTH_RE = re.compile(
    r"(?<![\w.\-])(?P<width>[1-8])[ \t]*[-‐-―−]?[ \t]*space(?:s)?"
    r"(?P<noun>[ \t]+indent(?:ation|s|ed|ing)?)?",
    re.IGNORECASE,
)

#: The noun that grounds :data:`SUBJECT_INDENTATION_STYLE`.  The pair's own span
#: — or the short run of words leading into it — must name it, so "2 spaces of
#: padding became 4 spaces" is not silently read as an indentation claim.
_INDENT_SUBJECT_RE = re.compile(r"indent", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class _ValueSpan:
    """One normalized value the user typed, and the span it occupies."""

    value: str
    start: int
    end: int


def _scan_indentation_values(text: str) -> list[_ValueSpan]:
    return [
        _ValueSpan(
            value=f"{int(match.group('width'))}space",
            start=match.start(),
            end=match.end(),
        )
        for match in _INDENT_WIDTH_RE.finditer(text)
    ]


#: ``subject kind -> (value scanner, subject-grounding pattern)``.
_SUBJECT_SCANNERS: dict[str, tuple[Any, re.Pattern[str]]] = {
    SUBJECT_INDENTATION_STYLE: (_scan_indentation_values, _INDENT_SUBJECT_RE),
}


# ── Relation connectives ──────────────────────────────────────────────────────
#
# The whole direction grammar, and all of it.  Each entry answers one question:
# given two values the user wrote and the words between them, which one did the
# user say the behavior *should* be?

#: ``Y instead of X`` / ``Y rather than X`` — the second value is the expected
#: one.  Checked first, so a sentence that says "instead of" outright is never
#: read by the weaker trailing-``instead`` rule below.
_REVERSING_GAP_RE = re.compile(r"\b(?:instead\s+of|rather\s+than)\b", re.IGNORECASE)

#: ``... X ... Y instead`` — a trailing ``instead`` refers back to the first
#: value, so the first one is the expected one.  ``instead of`` is excluded
#: because the rule above already owns it.
_TRAILING_INSTEAD_RE = re.compile(r"^[\s,;:]*instead\b(?!\s+of)", re.IGNORECASE)

#: ``from X to Y`` — a stated transition.  ``to`` alone is far too common to be
#: a connective, so the gap must be *only* ``to`` and ``from`` must lead the
#: first value.
_CHANGE_GAP_RE = re.compile(r"^[\s,]*to[\s]*$", re.IGNORECASE)
_CHANGE_PREFIX_RE = re.compile(r"\bfrom\s*$", re.IGNORECASE)

#: Result connectives: the second value is what actually happens.  Every one of
#: them is a word a user writes to introduce an outcome.
_RESULT_GAP_RE = re.compile(
    r"\b(?:"
    r"classified\s+as|detected\s+as|treated\s+as|reported\s+as"
    r"|identified\s+as|recognis(?:ed|es)\s+as|recogniz(?:ed|es)\s+as"
    r"|interpreted\s+as|read\s+as|turns?\s+into|turned\s+into"
    r"|but|becomes?|became|gets?|got|returns?|returned"
    r"|produces?|produced|outputs?|yields?|gives?|gave"
    r"|comes?\s+back|came\s+back|ends?\s+up|ended\s+up"
    r"|observed|actual|actually"
    r")\b",
    re.IGNORECASE,
)

#: A pair may not straddle a sentence the user ended or a line they broke.
_PAIR_BOUNDARY_RE = re.compile(r"[.!?](?=\s|$)|\n")

#: ``rule -> (relation, the first value is the expected one)``.  Four entries,
#: and the whole direction grammar is here.  :func:`_matched_rule` applies them
#: in a fixed order; first match wins, and no match means no fact.
_DIRECTION_RULES: dict[str, tuple[str, bool]] = {
    "reversing": (RELATION_INSTEAD_OF, False),
    "trailing_instead": (RELATION_INSTEAD_OF, True),
    "change": (RELATION_CHANGES_FROM_TO, True),
    "result": (RELATION_EXPECTED_VS_OBSERVED, True),
}


def _matched_rule(text: str, first: _ValueSpan, second: _ValueSpan) -> str | None:
    gap = text[first.end : second.start]
    if len(gap) > MAX_PAIR_GAP_CHARS or _PAIR_BOUNDARY_RE.search(gap):
        return None
    if _REVERSING_GAP_RE.search(gap):
        return "reversing"
    postfix = text[second.end : second.end + MAX_POSTFIX_CHARS]
    if _TRAILING_INSTEAD_RE.match(postfix):
        return "trailing_instead"
    prefix = text[max(0, first.start - MAX_PREFIX_CHARS) : first.start]
    if _CHANGE_GAP_RE.match(gap) and _CHANGE_PREFIX_RE.search(prefix):
        return "change"
    if _RESULT_GAP_RE.search(gap):
        return "result"
    return None


# ── The typed fact ────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class BehavioralExpectation:
    """One explicit behavioral claim the user made, typed and immutable.

    ``expected_value`` is what the user said the behavior should be.
    ``observed_value`` is what the user said it does instead.  They are never
    interchangeable and are never derived from source code, from a model or
    from a probe: see :attr:`provenance`.
    """

    subject_kind: str
    expected_value: str
    observed_value: str
    relation: str
    provenance: str = PROVENANCE_EXPLICIT_USER_FACT
    #: The literal span the user typed that both values were read out of.
    source_text: str = ""
    source_start: int = -1
    source_end: int = -1
    #: Which INPUT.PRESERVE.LIVE.1 obligation unit carries the span, once a
    #: consumer that holds the obligation set has bound it.
    obligation_ordinal: int | None = None
    #: False when another explicit claim contradicts this one.  A contradicted
    #: fact is preserved, never silently resolved, and never used to build a
    #: probe.
    authoritative: bool = True
    schema_version: str = BEHAVIORAL_EXPECTATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.subject_kind not in SUBJECT_KINDS:
            raise ValueError(f"unsupported subject kind: {self.subject_kind!r}")
        if self.relation not in BEHAVIOR_RELATIONS:
            raise ValueError(f"unsupported behavior relation: {self.relation!r}")
        if self.provenance not in BEHAVIOR_PROVENANCES:
            raise ValueError(
                "a behavioral expectation may only carry explicit user provenance, "
                f"not {self.provenance!r}"
            )
        if not str(self.expected_value or "").strip():
            raise ValueError("a behavioral expectation needs an expected value")
        if not str(self.observed_value or "").strip():
            raise ValueError("a behavioral expectation needs an observed value")
        if self.expected_value == self.observed_value:
            raise ValueError(
                "a behavioral expectation states a mismatch; expected and observed "
                "may not be the same value"
            )
        if not str(self.source_text or "").strip():
            raise ValueError(
                "a behavioral expectation must quote the user span it was read from"
            )
        if len(self.source_text) > MAX_SOURCE_TEXT_CHARS:
            raise ValueError("behavioral expectation source text exceeds its bound")
        if self.obligation_ordinal is not None and (
            not isinstance(self.obligation_ordinal, int)
            or isinstance(self.obligation_ordinal, bool)
            or self.obligation_ordinal < 0
        ):
            raise ValueError("an obligation ordinal is a non-negative index")

    @property
    def behavior_key(self) -> str:
        """Identity of the *claim*, ignoring how the user phrased it.

        Two orders that mean the same thing share this key even when their
        wording — and therefore their :attr:`relation` — differ.
        """
        return f"{self.subject_kind}:{self.expected_value}->{self.observed_value}"

    def bind_obligation_ordinal(self, ordinal: int | None) -> "BehavioralExpectation":
        """Record which preserved obligation unit carries this fact.

        The only field a consumer may bind after extraction, and only when it
        is unset or already agrees.  Nothing here can reach the values.
        """
        if ordinal is None or ordinal == self.obligation_ordinal:
            return self
        if self.obligation_ordinal is not None:
            raise ValueError(
                "a behavioral expectation's obligation ordinal is already bound"
            )
        return replace(self, obligation_ordinal=ordinal)

    def contradicted(self) -> "BehavioralExpectation":
        """The same fact, marked as one of several incompatible claims."""
        return self if not self.authoritative else replace(self, authoritative=False)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "subject_kind": self.subject_kind,
            "expected_value": self.expected_value,
            "observed_value": self.observed_value,
            "relation": self.relation,
            "provenance": self.provenance,
            "source_text": self.source_text,
            "source_start": self.source_start,
            "source_end": self.source_end,
            "obligation_ordinal": self.obligation_ordinal,
            "authoritative": self.authoritative,
            "semantics": (
                "explicit user claim about behavior; not defect evidence, not a "
                "probe observation, and not patch or write authority"
            ),
        }


def restore_behavioral_expectation(payload: Any) -> BehavioralExpectation | None:
    """Rebuild one typed fact from its serialized form, or ``None``.

    Serialization is transport, not re-interpretation: every field comes back
    as it was written, and a payload that does not carry a complete, valid fact
    yields nothing rather than a repaired guess.
    """
    if not isinstance(payload, Mapping):
        return None
    ordinal = payload.get("obligation_ordinal")
    if isinstance(ordinal, bool) or not isinstance(ordinal, int):
        ordinal = None
    try:
        return BehavioralExpectation(
            subject_kind=str(payload.get("subject_kind") or ""),
            expected_value=str(payload.get("expected_value") or ""),
            observed_value=str(payload.get("observed_value") or ""),
            relation=str(payload.get("relation") or ""),
            provenance=str(payload.get("provenance") or ""),
            source_text=str(payload.get("source_text") or ""),
            source_start=int(payload.get("source_start", -1) or -1),
            source_end=int(payload.get("source_end", -1) or -1),
            obligation_ordinal=ordinal,
            authoritative=payload.get("authoritative") is not False,
        )
    except (TypeError, ValueError):
        return None


def restore_behavioral_expectations(payload: Any) -> tuple[BehavioralExpectation, ...]:
    """Rebuild a carried tuple, dropping only entries that are not facts."""
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        return ()
    restored = [restore_behavioral_expectation(item) for item in payload]
    return tuple(item for item in restored if item is not None)[
        :MAX_BEHAVIORAL_EXPECTATIONS
    ]


# ── Extraction ────────────────────────────────────────────────────────────────

def _pairs_for_subject(
    text: str,
    subject_kind: str,
) -> list[BehavioralExpectation]:
    scanner, subject_re = _SUBJECT_SCANNERS[subject_kind]
    values: list[_ValueSpan] = scanner(text)
    found: list[BehavioralExpectation] = []

    for first, second in zip(values, values[1:]):
        if first.value == second.value:
            continue
        rule = _matched_rule(text, first, second)
        if rule is None:
            continue
        # The subject may be named inside the pair ("2-space indentation is
        # classified as 4-space") or in the short run of words leading into it
        # ("indentation of 2-space turns into 4-space").  The lead-in window is
        # the same bounded one the ``from ... to`` rule uses, so a subject noun
        # mentioned a sentence earlier still grounds nothing.
        span = text[max(0, first.start - MAX_PREFIX_CHARS) : second.end]
        if not subject_re.search(span):
            continue

        relation, first_is_expected = _DIRECTION_RULES[rule]
        expected = first.value if first_is_expected else second.value
        observed = second.value if first_is_expected else first.value
        # A trailing connective belongs to the span it qualifies.
        end = second.end
        if rule == "trailing_instead":
            postfix = text[second.end : second.end + MAX_POSTFIX_CHARS]
            trailing = _TRAILING_INSTEAD_RE.match(postfix)
            if trailing is not None:
                end = second.end + trailing.end()
        source_text = text[first.start : end]
        if len(source_text) > MAX_SOURCE_TEXT_CHARS:
            continue
        found.append(
            BehavioralExpectation(
                subject_kind=subject_kind,
                expected_value=expected,
                observed_value=observed,
                relation=relation,
                provenance=PROVENANCE_EXPLICIT_USER_FACT,
                source_text=source_text,
                source_start=first.start,
                source_end=end,
            )
        )
    return found


def _mark_contradictions(
    facts: Sequence[BehavioralExpectation],
) -> tuple[BehavioralExpectation, ...]:
    """Preserve every claim; mark incompatible ones instead of choosing.

    Two claims about the same subject that state different value pairs cannot
    both describe the behavior under test.  Nothing here decides which the user
    meant — both survive, both stop being authoritative, and the probe builder
    fails closed.
    """
    keys_by_subject: dict[str, set[str]] = {}
    for fact in facts:
        keys_by_subject.setdefault(fact.subject_kind, set()).add(fact.behavior_key)
    conflicted = {
        subject for subject, keys in keys_by_subject.items() if len(keys) > 1
    }
    return tuple(
        fact.contradicted() if fact.subject_kind in conflicted else fact
        for fact in facts
    )


def extract_behavioral_expectations(
    raw_text: str,
) -> tuple[tuple[BehavioralExpectation, ...], bool]:
    """Read every explicit behavioral claim out of one order.

    Returns ``(facts, truncated)``.  Deterministic and pure: identical input
    always yields identical facts, in the order the user wrote them.  A pair of
    values with no recognised connective produces nothing — silence is the
    correct answer for prose this grammar cannot read, and inventing a fact
    would be exactly the failure this phase exists to prevent.
    """
    if not isinstance(raw_text, str):
        raise TypeError("raw_text must be a string")

    found: list[BehavioralExpectation] = []
    for subject_kind in SUBJECT_KINDS:
        found.extend(_pairs_for_subject(raw_text, subject_kind))
    found.sort(key=lambda fact: (fact.source_start, fact.source_end))

    deduped: list[BehavioralExpectation] = []
    seen: set[tuple[str, int, int]] = set()
    for fact in found:
        key = (fact.behavior_key, fact.source_start, fact.source_end)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(fact)

    # Contradictions are marked across the *whole* order and only then bounded.
    # Doing it the other way round would let the bound hide a conflict, and a
    # hidden conflict is exactly the shape of an invented expectation.
    marked = _mark_contradictions(deduped)
    truncated = len(marked) > MAX_BEHAVIORAL_EXPECTATIONS
    return marked[:MAX_BEHAVIORAL_EXPECTATIONS], truncated


# ── Selection and preservation ────────────────────────────────────────────────

def select_probe_behavior_fact(
    facts: Iterable[BehavioralExpectation],
    *,
    subject_kinds: Sequence[str] | None = None,
) -> tuple[BehavioralExpectation | None, str]:
    """Pick the one fact a probe may be built from, or say why there is none.

    Fails closed twice over: an order that states nothing typed yields
    ``behavior_fact_unavailable``, and one that states two incompatible things
    yields ``behavior_fact_ambiguous``.  Neither ever returns a guess.
    """
    wanted = tuple(subject_kinds) if subject_kinds is not None else SUBJECT_KINDS
    in_scope = [fact for fact in facts if fact.subject_kind in wanted]
    if not in_scope:
        return None, FACT_STATUS_UNAVAILABLE

    authoritative = [fact for fact in in_scope if fact.authoritative]
    if not authoritative:
        return None, FACT_STATUS_AMBIGUOUS
    if len({fact.behavior_key for fact in authoritative}) > 1:
        return None, FACT_STATUS_AMBIGUOUS
    return authoritative[0], FACT_STATUS_AVAILABLE


def _support_key(value: str) -> str:
    return " ".join(str(value or "").split()).casefold()


def behavior_fact_is_supported(
    fact: BehavioralExpectation,
    sources: Iterable[str],
) -> bool:
    """Does preserved user text still carry the span this fact was read from?

    INPUT.PRESERVE.LIVE.1 made explicit commitments survive transport.  This is
    the same invariant one level down: a typed fact whose quoted span no longer
    appears in what was preserved has diverged from the order, and a diverged
    fact may not build a probe.
    """
    quoted = _support_key(fact.source_text)
    if not quoted:
        return False
    return any(quoted in _support_key(source) for source in sources if source)


def supported_behavior_facts(
    facts: Iterable[BehavioralExpectation],
    sources: Iterable[str],
) -> tuple[BehavioralExpectation, ...]:
    """Keep only the facts preserved user text still supports."""
    kept_sources = [source for source in sources if source]
    return tuple(
        fact for fact in facts if behavior_fact_is_supported(fact, kept_sources)
    )


def bind_obligation_ordinals(
    facts: Iterable[BehavioralExpectation],
    obligations: Sequence[str],
) -> tuple[BehavioralExpectation, ...]:
    """Bind each fact to the preserved obligation unit that carries its span."""
    keys = [_support_key(value) for value in obligations]
    bound: list[BehavioralExpectation] = []
    for fact in facts:
        quoted = _support_key(fact.source_text)
        ordinal = next(
            (index for index, key in enumerate(keys) if quoted and quoted in key),
            None,
        )
        bound.append(fact.bind_obligation_ordinal(ordinal))
    return tuple(bound)


def behavioral_expectation_guardrails() -> dict[str, bool]:
    """Every power this module declines to exercise."""
    return {
        "model_call_performed": False,
        "network_call_performed": False,
        "repository_traversal_performed": False,
        "file_read_performed": False,
        "retrieval_changed": False,
        "ranking_changed": False,
        "probe_execution_changed": False,
        "defect_established": False,
        "patch_basis_established": False,
        "write_authority": False,
        "source_derived_expectation_accepted": False,
        "model_authored_expectation_accepted": False,
    }


__all__ = [
    "PHASE_ID",
    "BEHAVIORAL_EXPECTATION_SCHEMA_VERSION",
    "BEHAVIOR_PROVENANCES",
    "BEHAVIOR_RELATIONS",
    "FACT_STATUSES",
    "FACT_STATUS_AMBIGUOUS",
    "FACT_STATUS_AVAILABLE",
    "FACT_STATUS_UNAVAILABLE",
    "MAX_BEHAVIORAL_EXPECTATIONS",
    "PROVENANCE_EXPLICIT_USER_FACT",
    "RELATION_CHANGES_FROM_TO",
    "RELATION_DIFFERS_FROM",
    "RELATION_EQUALS",
    "RELATION_EXPECTED_VS_OBSERVED",
    "RELATION_INSTEAD_OF",
    "SUBJECT_INDENTATION_STYLE",
    "SUBJECT_KINDS",
    "BehavioralExpectation",
    "behavior_fact_is_supported",
    "behavioral_expectation_guardrails",
    "bind_obligation_ordinals",
    "extract_behavioral_expectations",
    "restore_behavioral_expectation",
    "restore_behavioral_expectations",
    "select_probe_behavior_fact",
    "supported_behavior_facts",
]
