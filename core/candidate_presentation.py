"""ANSWER.COHERENCE.LIVE.1 — one candidate identity per final answer.

Round 10 is the measurement.  PATCH.AUTHOR.LIVE.1's single verification-guided
revision produced a real second candidate: it parsed, earned its own
fingerprint, went through every gate and was rejected for
``behavior_preservation_regressed``.  The final payload then said:

    summary          Candidate0's explanation of the inert guard
    issues           Candidate0's issue, beside the harness finding on Candidate1
    patch_candidate  Candidate1's branch reorder
    confidence       Candidate1's 1.0

Containment held — nothing was reviewable, approvable or authorized — but the
answer described one patch in another patch's words.  The revision path
installed the new candidate's bytes and confidence and never touched the rest
of the envelope its author had written, so Candidate0's account simply stayed.

This module owns one question and nothing else: **which authoring response a
candidate-authored field on the final payload came from.**

* It records what one authoring response said about its own candidate, at the
  moment that response is parsed and before any gate narrows it.
* It installs a replacement candidate together with its author's account of
  it, as one unit, so there is no half-replaced payload to observe.
* It reads the final candidate identity off the existing lifecycle receipts,
  checks that every presentation field agrees with it, and withholds the
  author-facing fields when that cannot be established.

**What it is not.**  Not a parser: candidate acceptance stays with
``core.candidate_revision``.  Not a judge: verification stays with
``CANDIDATE.VERIFY``.  Not a grounding pass: ANSWER.GROUND still reads the
model-authored prose afterwards.  Not a policy: it never writes
``needs_escalation``, a readiness flag or an authority flag, never clamps a
confidence, and never generates text — a field the final author did not supply
is absent, not borrowed from an earlier author and not composed here.

Stdlib only.  Fingerprints are computed by the caller with the existing exact
candidate fingerprint; nothing here hashes a candidate.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping, MutableMapping


PHASE_ID = "ANSWER.COHERENCE.LIVE.1"
SCHEMA_VERSION = "candidate_presentation_live_1_v1"


# ── Generation vocabulary (§28, closed) ───────────────────────────────────────
#: Which authoring call a candidate came from.  PATCH.AUTHOR.LIVE.1 caps
#: revisions at one per run, so there is no third value and no counter.
GENERATION_INITIAL = "initial"
GENERATION_REVISION = "revision"
CANDIDATE_GENERATIONS: tuple[str, ...] = (GENERATION_INITIAL, GENERATION_REVISION)


# ── Ownership of the authoring envelope (§1/§10/§11) ──────────────────────────
OWNER_CANDIDATE_BYTES = "candidate_bytes"
OWNER_CANDIDATE_NARRATIVE = "candidate_narrative"
OWNER_CANDIDATE_CLAIM = "candidate_claim"

#: Every field of ``PATCH_RESPONSE_SCHEMA`` — the one envelope both authoring
#: calls are held to — and what it is once it reaches the payload.  Mirrored as
#: a literal rather than read out of prompt text; equality with the schema is
#: proved by test, so a field added to the contract fails there first.
AUTHORING_ENVELOPE_OWNERSHIP: Mapping[str, str] = MappingProxyType(
    {
        "summary": OWNER_CANDIDATE_NARRATIVE,
        "issues": OWNER_CANDIDATE_NARRATIVE,
        "patch_candidate": OWNER_CANDIDATE_BYTES,
        "patch_plan": OWNER_CANDIDATE_BYTES,
        "confidence": OWNER_CANDIDATE_CLAIM,
        "needs_escalation": OWNER_CANDIDATE_CLAIM,
    }
)

#: What an author says about its own candidate: the whole envelope except the
#: candidate bytes, which the lifecycle installs and the gates may remove.
AUTHORED_PRESENTATION_FIELDS: tuple[str, ...] = tuple(
    name
    for name, owner in AUTHORING_ENVELOPE_OWNERSHIP.items()
    if owner != OWNER_CANDIDATE_BYTES
)

#: §7 — claims whose payload copy is harness-final once the lifecycle has run.
#: The author's value is recorded as its claim; it is never written back over
#: the harness's decision, in either direction.
HARNESS_FINAL_CLAIM_FIELDS: frozenset[str] = frozenset({"needs_escalation"})

#: The author-facing fields on the payload's primary surface.  ``confidence``
#: is here because its payload copy *is* the author's claim, which existing
#: gates may demote but never replace with another author's.
PRIMARY_PRESENTATION_FIELDS: tuple[str, ...] = tuple(
    name
    for name in AUTHORED_PRESENTATION_FIELDS
    if name not in HARNESS_FINAL_CLAIM_FIELDS
)


# ── Lifecycle receipts that name the candidate they measured (§4/§12) ─────────
#: Read in this order when no revision replaced the first candidate: the
#: verification verdict names the candidate the lifecycle judged, and the two
#: gate receipts are the ones that survive a gate removing the candidate.
IDENTITY_PRECEDENCE: tuple[str, ...] = (
    "candidate_verification_candidate_fingerprint",
    "candidate_effect_candidate_fingerprint",
    "candidate_novelty_candidate_fingerprint",
)
#: Every top-level receipt field naming a candidate.  Each one present must
#: name the final candidate; none of them is a second source of identity.
IDENTITY_RECEIPT_KEYS: tuple[str, ...] = IDENTITY_PRECEDENCE + (
    "candidate_validation_fingerprint",
    "candidate_fingerprint",
    "check_oracle_candidate_fingerprint",
    "execution_eligibility_candidate_fingerprint",
)


# ── Incoherence vocabulary (§41, closed) ──────────────────────────────────────
INCOHERENT_NO_CANDIDATE_IDENTITY = "final_candidate_identity_unavailable"
INCOHERENT_PAYLOAD_CANDIDATE = "payload_candidate_is_not_the_final_candidate"
INCOHERENT_RECEIPT_CANDIDATE = "a_lifecycle_receipt_names_another_candidate"
INCOHERENT_NO_AUTHOR_RECORD = "final_candidate_author_record_unavailable"
INCOHERENT_AUTHOR_GENERATION = "author_record_is_from_another_generation"
INCOHERENT_SUMMARY = "summary_was_not_written_by_the_final_author"
INCOHERENT_SUPERSEDED_ISSUES = "issues_carry_the_superseded_authors_entries"
INCOHERENCE_REASONS: tuple[str, ...] = (
    INCOHERENT_NO_CANDIDATE_IDENTITY,
    INCOHERENT_PAYLOAD_CANDIDATE,
    INCOHERENT_RECEIPT_CANDIDATE,
    INCOHERENT_NO_AUTHOR_RECORD,
    INCOHERENT_AUTHOR_GENERATION,
    INCOHERENT_SUMMARY,
    INCOHERENT_SUPERSEDED_ISSUES,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

#: Distinguishes "take the confidence from the response" from an explicit
#: ``None``, which means the caller established that none was supplied.
_FROM_RESPONSE: Any = object()


class CandidatePresentationError(ValueError):
    """A composition asked to bind one candidate's account to another."""


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


# ══════════════════════════════════════════════════════════════════════════════
# §1 — what one author said about its own candidate
# ══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class CandidateAuthoredFields:
    """The account one authoring response gave of the candidate it produced.

    ``values`` holds only the envelope fields that response actually supplied;
    a missing key means "not supplied", never "inherit".  ``supersedes`` is the
    record of the author this one replaced — set only on a revision, because
    the revision is the only thing that replaces a candidate.
    """

    generation: str
    values: Mapping[str, Any] = field(default_factory=dict)
    supersedes: "CandidateAuthoredFields | None" = None

    def __post_init__(self) -> None:
        if self.generation not in CANDIDATE_GENERATIONS:
            raise CandidatePresentationError(
                f"unsupported candidate generation: {self.generation!r}"
            )
        unknown = set(self.values) - set(AUTHORED_PRESENTATION_FIELDS)
        if unknown:
            raise CandidatePresentationError(
                f"not an authored presentation field: {sorted(unknown)!r}"
            )
        if self.generation == GENERATION_INITIAL and self.supersedes is not None:
            raise CandidatePresentationError("a first draft supersedes no author")
        if self.supersedes is not None and self.supersedes.generation != (
            GENERATION_INITIAL
        ):
            raise CandidatePresentationError(
                "a revision can only supersede the initial author"
            )
        # A private deep copy: editing the response after capture, or a payload
        # the fields were installed on, cannot reach back into the record.  A
        # plain dict rather than a proxy keeps the run state copyable.
        object.__setattr__(self, "values", copy.deepcopy(dict(self.values)))

    def supplied(self, name: str) -> bool:
        return name in self.values

    def value(self, name: str) -> Any:
        """A private copy, so no caller can edit the record through it."""

        return copy.deepcopy(self.values[name])

    @property
    def authored_fields(self) -> tuple[str, ...]:
        return tuple(name for name in AUTHORED_PRESENTATION_FIELDS if name in self.values)

    @property
    def model_confidence(self) -> Any:
        return copy.deepcopy(self.values.get("confidence"))

    @property
    def model_needs_escalation(self) -> Any:
        return copy.deepcopy(self.values.get("needs_escalation"))

    @property
    def issue_entries(self) -> list[Any]:
        """The authored issues as entries, whatever shape the author used."""

        if "issues" not in self.values:
            return []
        issues = self.values["issues"]
        if isinstance(issues, list):
            return copy.deepcopy(issues)
        return [copy.deepcopy(issues)]


def capture_candidate_authored_fields(
    response: Any,
    *,
    generation: str,
    confidence: Any = _FROM_RESPONSE,
    supersedes: CandidateAuthoredFields | None = None,
) -> CandidateAuthoredFields | None:
    """Record one parsed authoring response's account of its candidate.

    Called where the response is parsed, before any gate narrows the payload:
    a ``safe_minimal`` demotion, a no-op rejection and a verification failure
    all happen afterwards, and none of them is something the author said.

    ``confidence`` lets the revision path pass the value its own parser already
    decided travels with the response (PATCH.AUTHOR.LIVE.1 §42), so there is
    one reading of that rule rather than two.  ``None`` there means the
    response carried none.
    """

    if not isinstance(response, Mapping):
        return None
    values = {
        name: copy.deepcopy(response[name])
        for name in AUTHORED_PRESENTATION_FIELDS
        if name in response
    }
    if confidence is not _FROM_RESPONSE:
        values.pop("confidence", None)
        if confidence is not None:
            values["confidence"] = confidence
    return CandidateAuthoredFields(
        generation=generation, values=values, supersedes=supersedes
    )


# ══════════════════════════════════════════════════════════════════════════════
# §3/§6/§20 — replacing a candidate replaces its whole account
# ══════════════════════════════════════════════════════════════════════════════


def _entries_not_authored_by(
    issues: Any, author: CandidateAuthoredFields | None
) -> list[Any]:
    """The issue entries left after removing one author's own entries.

    Multiset semantics: each authored entry removes one equal entry, so an
    author who wrote the same line twice loses both and a harness finding that
    merely resembles one is not taken with it.  With no record of the author
    nothing can be attributed, so nothing survives the replacement: an entry of
    unknown provenance may not be presented as describing the next candidate.
    """

    if not isinstance(issues, list) or author is None:
        return []
    pending = author.issue_entries
    kept: list[Any] = []
    for entry in issues:
        for index, authored in enumerate(pending):
            if entry == authored:
                del pending[index]
                break
        else:
            kept.append(entry)
    return kept


def superseded_candidate_history(
    block: Mapping[str, Any], author: CandidateAuthoredFields | None
) -> dict[str, Any]:
    """§3/§27 — what the rejected first author said, and what was measured.

    Read before the superseded candidate's receipts are dropped, because its
    verification verdict is one of them.  Only what the record attributes is
    kept: with no authoring record there is no narrative to attribute, and
    ``authored_fields`` says so with ``None`` rather than guessing.
    """

    if author is not None and author.generation != GENERATION_INITIAL:
        raise CandidatePresentationError(
            "only the initial author is ever superseded"
        )
    history: dict[str, Any] = {
        "generation": GENERATION_INITIAL,
        "authored_fields": list(author.authored_fields) if author else None,
    }
    if author is not None:
        for name in ("summary", "issues"):
            if author.supplied(name):
                history[name] = author.value(name)
    history["model_confidence"] = author.model_confidence if author else None
    history["model_needs_escalation"] = (
        author.model_needs_escalation if author else None
    )
    history["verification_status"] = _text(block.get("candidate_verification_status"))
    reasons = block.get("candidate_verification_rejection_reasons")
    history["verification_rejection_reasons"] = (
        list(reasons) if isinstance(reasons, (list, tuple)) else []
    )
    return history


def install_candidate_presentation(
    block: MutableMapping[str, Any],
    *,
    candidate: Mapping[str, Any],
    authored: CandidateAuthoredFields,
) -> None:
    """Put one candidate and its author's account of it on the payload, together.

    Everything the superseded author wrote leaves the primary surface first:
    its summary, its confidence and its own issue entries.  Then the candidate
    bytes and this author's account go on, field by field, and only where this
    author supplied one — a missing summary stays missing (§9/§26).  Harness
    findings the superseded candidate's receipts did not take with them are
    left where they are; they are not an author's words.
    """

    if authored.generation != GENERATION_REVISION:
        raise CandidatePresentationError(
            "only a revision replaces the candidate on the payload"
        )
    findings = _entries_not_authored_by(block.get("issues"), authored.supersedes)

    block["patch_candidate"] = dict(candidate)
    block["patch_plan"] = None

    # Values are replaced where they stand, so the new author's account keeps
    # the envelope's position at the head of the payload instead of trailing
    # the history record that quotes the rejected one.
    if authored.supplied("summary"):
        block["summary"] = authored.value("summary")
    else:
        block.pop("summary", None)
    if authored.supplied("confidence"):
        block["confidence"] = authored.value("confidence")
    else:
        block.pop("confidence", None)
    if authored.supplied("issues"):
        issues = authored.value("issues")
        block["issues"] = (
            findings + (issues if isinstance(issues, list) else [issues])
            if findings or isinstance(issues, list)
            else issues
        )
    elif findings:
        block["issues"] = findings
    else:
        block.pop("issues", None)


# ══════════════════════════════════════════════════════════════════════════════
# §4/§12/§21/§41 — the one final identity, and whether the answer is bound to it
# ══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class CandidatePresentation:
    """Which candidate the final answer presents, and whether that holds.

    Harness-owned telemetry.  It names a candidate; it does not describe one,
    judge one or authorize one.
    """

    coherent: bool
    candidate_fingerprint: str
    generation: str
    authored_fields: tuple[str, ...] | None = None
    model_confidence: Any = None
    model_needs_escalation: Any = None
    incoherence_reasons: tuple[str, ...] = ()
    phase_id: str = PHASE_ID
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        unknown = set(self.incoherence_reasons) - set(INCOHERENCE_REASONS)
        if unknown:
            raise CandidatePresentationError(
                f"unknown incoherence reasons: {sorted(unknown)!r}"
            )
        if self.coherent:
            if self.incoherence_reasons:
                raise CandidatePresentationError("a coherent binding has no reasons")
            if not _SHA256_RE.match(self.candidate_fingerprint):
                raise CandidatePresentationError(
                    "a coherent binding names an exact candidate fingerprint"
                )
            if self.generation not in CANDIDATE_GENERATIONS:
                raise CandidatePresentationError(
                    f"unsupported candidate generation: {self.generation!r}"
                )
        else:
            if not self.incoherence_reasons:
                raise CandidatePresentationError("a withheld binding says why")
            if self.candidate_fingerprint or self.generation:
                raise CandidatePresentationError(
                    "a withheld binding claims no candidate identity"
                )

    def as_telemetry(self) -> dict[str, Any]:
        return {
            "candidate_presentation_phase_id": self.phase_id,
            "candidate_presentation_schema_version": self.schema_version,
            "final_candidate_fingerprint": self.candidate_fingerprint,
            "final_candidate_generation": self.generation,
            "candidate_presentation_coherent": self.coherent,
            "candidate_presentation_authored_fields": (
                list(self.authored_fields)
                if self.authored_fields is not None
                else None
            ),
            "candidate_presentation_model_confidence": copy.deepcopy(
                self.model_confidence
            ),
            "candidate_presentation_model_needs_escalation": copy.deepcopy(
                self.model_needs_escalation
            ),
            "candidate_presentation_incoherence_reasons": list(
                self.incoherence_reasons
            ),
        }


def select_final_candidate(
    block: Mapping[str, Any],
    *,
    revised_candidate_present: bool,
    revised_candidate_fingerprint: str,
) -> tuple[str, str]:
    """§4/§21 — the final candidate, read off existing lifecycle truth.

    The revision receipt decides the generation: Candidate1 is the final
    candidate exactly when the revision actually produced one.  Otherwise the
    first candidate is, and its identity is whatever the lifecycle receipts
    recorded for it.  The payload's own bytes are never the source — a patch
    being present says nothing about which author it belongs to.
    """

    if revised_candidate_present:
        return GENERATION_REVISION, _text(revised_candidate_fingerprint)
    for key in IDENTITY_PRECEDENCE:
        fingerprint = _text(block.get(key))
        if fingerprint:
            return GENERATION_INITIAL, fingerprint
    return GENERATION_INITIAL, ""


def _withhold_author_presentation(
    block: MutableMapping[str, Any], author: CandidateAuthoredFields | None
) -> None:
    """§41 — fail closed: take the author-facing account off the payload.

    Removes, never rewrites.  Harness findings stay; so do the candidate bytes
    and every receipt, which each name their own candidate.
    """

    for name in PRIMARY_PRESENTATION_FIELDS:
        if name != "issues":
            block.pop(name, None)
    if author is None or "issues" not in block:
        return
    kept = _entries_not_authored_by(block.get("issues"), author)
    if author.supersedes is not None:
        kept = _entries_not_authored_by(kept, author.supersedes)
    if kept:
        block["issues"] = kept
    else:
        block.pop("issues", None)


def bind_final_candidate_presentation(
    block: MutableMapping[str, Any],
    *,
    author: CandidateAuthoredFields | None,
    revised_candidate_present: bool,
    revised_candidate_fingerprint: str,
    payload_candidate_fingerprint: str | None,
) -> CandidatePresentation | None:
    """Check that the final answer presents one candidate, and say which.

    ``payload_candidate_fingerprint`` is the existing exact fingerprint of the
    candidate bytes still on the payload, or ``None`` when a gate removed them.
    Returns ``None`` when no candidate ever entered the lifecycle, because a
    payload that never carried a candidate is not annotated with a binding to
    nothing.  Nothing is written to ``block`` except, on failure, the removal
    of the author-facing fields that could not be vouched for.
    """

    generation, fingerprint = select_final_candidate(
        block,
        revised_candidate_present=revised_candidate_present,
        revised_candidate_fingerprint=revised_candidate_fingerprint,
    )
    if (
        generation == GENERATION_INITIAL
        and not fingerprint
        and payload_candidate_fingerprint is None
    ):
        return None

    reasons: list[str] = []
    if not _SHA256_RE.match(fingerprint):
        reasons.append(INCOHERENT_NO_CANDIDATE_IDENTITY)
    if (
        payload_candidate_fingerprint is not None
        and payload_candidate_fingerprint != fingerprint
    ):
        reasons.append(INCOHERENT_PAYLOAD_CANDIDATE)
    if any(
        _text(block.get(key)) and _text(block.get(key)) != fingerprint
        for key in IDENTITY_RECEIPT_KEYS
    ):
        reasons.append(INCOHERENT_RECEIPT_CANDIDATE)

    if author is None:
        # A single authoring generation needs no record to be coherent: there
        # is no other author its fields could have come from.  A revision
        # always leaves one, so its absence there is a broken lifecycle.
        if generation == GENERATION_REVISION:
            reasons.append(INCOHERENT_NO_AUTHOR_RECORD)
    elif author.generation != generation:
        reasons.append(INCOHERENT_AUTHOR_GENERATION)
    else:
        if "summary" in block and (
            not author.supplied("summary")
            or block["summary"] != author.values["summary"]
        ):
            reasons.append(INCOHERENT_SUMMARY)
        if author.supersedes is not None:
            issues = block.get("issues")
            own = _entries_not_authored_by(
                author.supersedes.issue_entries, author
            )
            if isinstance(issues, list) and any(entry in issues for entry in own):
                reasons.append(INCOHERENT_SUPERSEDED_ISSUES)

    if reasons:
        _withhold_author_presentation(block, author)
        return CandidatePresentation(
            coherent=False,
            candidate_fingerprint="",
            generation="",
            incoherence_reasons=tuple(dict.fromkeys(reasons)),
        )
    return CandidatePresentation(
        coherent=True,
        candidate_fingerprint=fingerprint,
        generation=generation,
        authored_fields=author.authored_fields if author is not None else None,
        model_confidence=author.model_confidence if author is not None else None,
        model_needs_escalation=(
            author.model_needs_escalation if author is not None else None
        ),
    )


def describe_candidate_presentation(presentation: CandidatePresentation) -> str:
    """One operator-facing line that never reads as review or approval."""

    if not presentation.coherent:
        return (
            "the author-facing account was withheld — "
            + "; ".join(presentation.incoherence_reasons)
        )
    return (
        f"{presentation.generation} candidate "
        f"{presentation.candidate_fingerprint[:12]}; every author-facing field "
        "shown is that candidate's own author's, and verification and authority "
        "remain the harness's"
    )


def candidate_presentation_guardrails() -> dict[str, Any]:
    """The boundaries this phase asserts about itself."""

    return {
        "presentation_fields_follow_one_candidate": True,
        "missing_fields_inherit_from_a_superseded_author": False,
        "superseded_author_kept_as_rejected_history": True,
        "presentation_generates_text": False,
        "presentation_clamps_confidence": False,
        "presentation_writes_needs_escalation": False,
        "presentation_grants_review_or_approval": False,
        "presentation_grants_execution_authority": False,
        "presentation_changes_verification": False,
        "presentation_makes_model_calls": False,
        "presentation_traverses_the_repository": False,
    }
