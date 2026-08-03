"""Pure, explainable CTX.PATCH.1 file patchability scoring.

Patchability answers whether supplied direct-context evidence supports a
bounded, testable change to one file.  It is deliberately separate from
CTX.SELECT actionability (task relevance), and it never grants write or patch
application authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import islice
from typing import Any, Iterable, Iterator, Mapping


MAX_SUPPLIED_PATCHABILITY_EVIDENCE = 256
MAX_SUPPLIED_PATCHABILITY_RISKS = 128

PATCHABILITY_EVIDENCE_WEIGHTS: dict[str, int] = {
    "direct_read_target_confirmation": 25,
    "diagnosis_confidence": 20,
    "change_locality": 15,
    "symbol_or_branch_specificity": 12,
    "validation_coverage": 15,
    "reversibility": 8,
    "matching_test_or_linter": 18,
    "authoritative_source_confidence": 18,
    "direct_symbol_reference_confirmation": 20,
    "localized_defect_evidence": 20,
    "bounded_manual_verification": 10,
}

PATCHABILITY_EVIDENCE_ALIASES: dict[str, str] = {
    "direct_read_confirmation": "direct_read_target_confirmation",
    "direct_target_confirmation": "direct_read_target_confirmation",
    "direct_symbol_confirmation": "direct_symbol_reference_confirmation",
    "direct_reference_confirmation": "direct_symbol_reference_confirmation",
    "direct_symbol_or_reference_confirmation": (
        "direct_symbol_reference_confirmation"
    ),
    "localized_change": "change_locality",
    "localized_defect": "localized_defect_evidence",
    "matching_test": "matching_test_or_linter",
    "matching_linter": "matching_test_or_linter",
    "known_validation_command": "validation_coverage",
    "linter_or_type_check": "matching_test_or_linter",
    "manual_verification_plan": "bounded_manual_verification",
    "authoritative_configuration_source_ownership": (
        "authoritative_source_confidence"
    ),
    "authoritative_configuration": "authoritative_source_confidence",
}

PATCHABILITY_RISK_WEIGHTS: dict[str, int] = {
    "high_blast_radius": -20,
    "critical_blast_radius": -30,
    "unknown_blast_radius": -10,
    "medium_blast_radius": -5,
    "high_dependency_centrality": -12,
    "shared_public_api": -15,
    "weak_parser_or_raw_text_only": -12,
    "ambiguous_ownership": -12,
    "validation_gap": -18,
    "generated_or_derived_file": -25,
    "configuration_security_risk": -10,
    "cross_language_boundary": -12,
    "stale_or_partial_read": -15,
}

PATCHABILITY_RISK_ALIASES: dict[str, str] = {
    "parser_unsupported": "weak_parser_or_raw_text_only",
    "raw_text_only": "weak_parser_or_raw_text_only",
    "generated_file": "generated_or_derived_file",
    "derived_file": "generated_or_derived_file",
    "generated_or_derived_semantics": "generated_or_derived_file",
    "configuration_risk": "configuration_security_risk",
    "partial_read": "stale_or_partial_read",
    "stale_read": "stale_or_partial_read",
}

PATCHABILITY_BANDS = (
    (80, 100, "primary_patch_candidate"),
    (65, 79, "patch_candidate_with_review"),
    (40, 64, "inspect_or_supporting_context"),
    (1, 39, "insufficient_patch_evidence"),
    (0, 0, "blocked_or_forbidden"),
)


class _RecordMapping(Mapping[str, Any]):
    def as_dict(self) -> dict[str, Any]:  # pragma: no cover - abstract helper
        raise NotImplementedError

    def __getitem__(self, key: str) -> Any:
        return self.as_dict()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.as_dict())

    def __len__(self) -> int:
        return len(self.as_dict())


@dataclass(frozen=True, slots=True)
class PatchabilityEvidence(_RecordMapping):
    kind: str
    weight: int
    detail: str
    origin: str = "ctx_patch"
    related_path: str | None = None
    evidence_id: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in PATCHABILITY_EVIDENCE_WEIGHTS:
            raise ValueError(f"unknown patchability evidence kind: {self.kind}")
        if self.weight != PATCHABILITY_EVIDENCE_WEIGHTS[self.kind]:
            raise ValueError("patchability evidence must use its canonical weight")
        if not self.detail.strip():
            raise ValueError("patchability evidence detail must be nonblank")

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "kind": self.kind,
            "weight": self.weight,
            "detail": self.detail,
            "origin": self.origin,
        }
        if self.related_path is not None:
            result["related_path"] = self.related_path
        if self.evidence_id is not None:
            result["evidence_id"] = self.evidence_id
        return result


@dataclass(frozen=True, slots=True)
class PatchabilityRiskAdjustment(_RecordMapping):
    kind: str
    weight: int
    detail: str = ""

    def __post_init__(self) -> None:
        if self.kind not in PATCHABILITY_RISK_WEIGHTS:
            raise ValueError(f"unknown patchability risk kind: {self.kind}")
        if self.weight != PATCHABILITY_RISK_WEIGHTS[self.kind]:
            raise ValueError("patchability risk must use its canonical weight")

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"kind": self.kind, "weight": self.weight}
        if self.detail:
            result["detail"] = self.detail
        return result


@dataclass(frozen=True, slots=True)
class PatchabilityScore(_RecordMapping):
    path: str
    patchability_score: int
    patchability_band: str
    positive_evidence: tuple[PatchabilityEvidence, ...]
    risk_adjustments: tuple[PatchabilityRiskAdjustment, ...]
    ignored_evidence_kinds: tuple[str, ...] = ()
    hard_blocked: bool = False

    def __post_init__(self) -> None:
        if not 0 <= self.patchability_score <= 100:
            raise ValueError("patchability score must be bounded from 0 through 100")
        if self.patchability_band != patchability_band(self.patchability_score):
            raise ValueError("patchability band must match the bounded score")
        if self.hard_blocked and self.patchability_score != 0:
            raise ValueError("a hard-blocked patchability score must be zero")
        if tuple(sorted(set(self.ignored_evidence_kinds))) != (
            self.ignored_evidence_kinds
        ):
            raise ValueError("ignored evidence kinds must be deterministic")

    @property
    def score(self) -> int:
        return self.patchability_score

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "patchability_score": self.patchability_score,
            "patchability_band": self.patchability_band,
            "positive_evidence": [item.as_dict() for item in self.positive_evidence],
            "risk_adjustments": [item.as_dict() for item in self.risk_adjustments],
            "ignored_evidence_kinds": list(self.ignored_evidence_kinds),
            "hard_blocked": self.hard_blocked,
            "write_authority": False,
            "patch_application_authority": False,
            "human_approval_required": True,
        }


def patchability_band(score: int) -> str:
    bounded = max(0, min(100, int(score)))
    for low, high, label in PATCHABILITY_BANDS:
        if low <= bounded <= high:
            return label
    raise AssertionError("patchability bands do not cover the bounded range")


def _canonical_evidence_kind(kind: str) -> str:
    return PATCHABILITY_EVIDENCE_ALIASES.get(kind, kind)


def _canonical_risk_kind(kind: str) -> str:
    return PATCHABILITY_RISK_ALIASES.get(kind, kind)


def _coerce_evidence(
    value: PatchabilityEvidence | Mapping[str, Any],
) -> PatchabilityEvidence | None:
    if isinstance(value, PatchabilityEvidence):
        return value
    if not isinstance(value, Mapping):
        raise TypeError("patchability evidence must be a record mapping")
    supplied_kind = str(value.get("kind", "")).strip()
    if not supplied_kind:
        raise ValueError("patchability evidence kind must be nonblank")
    kind = _canonical_evidence_kind(supplied_kind)
    if kind not in PATCHABILITY_EVIDENCE_WEIGHTS:
        return None
    detail = str(value.get("detail", "")).strip()
    if not detail:
        raise ValueError("patchability evidence detail must be nonblank")
    return PatchabilityEvidence(
        kind=kind,
        weight=PATCHABILITY_EVIDENCE_WEIGHTS[kind],
        detail=detail,
        origin=str(value.get("origin", value.get("stage", "ctx_patch"))),
        related_path=(
            str(value["related_path"]) if value.get("related_path") else None
        ),
        evidence_id=(
            str(value["evidence_id"]) if value.get("evidence_id") else None
        ),
    )


def _coerce_risk(
    value: PatchabilityRiskAdjustment | Mapping[str, Any] | str,
) -> PatchabilityRiskAdjustment | None:
    if isinstance(value, PatchabilityRiskAdjustment):
        return value
    if isinstance(value, str):
        supplied_kind = value.strip()
        detail = ""
    elif isinstance(value, Mapping):
        supplied_kind = str(value.get("kind", "")).strip()
        detail = str(value.get("detail", "")).strip()
    else:
        raise TypeError("patchability risk must be a mapping or string")
    if not supplied_kind:
        raise ValueError("patchability risk kind must be nonblank")
    kind = _canonical_risk_kind(supplied_kind)
    if kind not in PATCHABILITY_RISK_WEIGHTS:
        return None
    return PatchabilityRiskAdjustment(
        kind=kind,
        weight=PATCHABILITY_RISK_WEIGHTS[kind],
        detail=detail,
    )


def _evidence_identity(item: PatchabilityEvidence) -> tuple[str, ...]:
    if item.evidence_id:
        # An upstream fact may be projected through SELECT, SEARCH, and READ.
        # One stable id therefore wins only once across every origin.
        return ("evidence_id", item.evidence_id)
    return (
        "semantic",
        item.kind,
        item.detail.casefold(),
        (item.related_path or "").casefold(),
    )


def calculate_patchability_score(
    path: str,
    evidence: Iterable[PatchabilityEvidence | Mapping[str, Any]],
    *,
    risks: Iterable[
        PatchabilityRiskAdjustment | Mapping[str, Any] | str
    ] = (),
    hard_blocked: bool = False,
) -> PatchabilityScore:
    """Return a deterministic 0-100 score from already-supplied evidence.

    Unknown evidence kinds (including CTX.SELECT actionability evidence) are
    recorded but contribute zero.  This prevents relevance evidence from being
    silently counted a second time as modification suitability.
    """

    if isinstance(evidence, (str, bytes)):
        raise TypeError("evidence must be an iterable of evidence records")
    supplied = tuple(
        islice(iter(evidence), MAX_SUPPLIED_PATCHABILITY_EVIDENCE + 1)
    )
    if len(supplied) > MAX_SUPPLIED_PATCHABILITY_EVIDENCE:
        raise ValueError(
            "patchability evidence exceeds the defensive input limit of "
            f"{MAX_SUPPLIED_PATCHABILITY_EVIDENCE}"
        )

    ignored: set[str] = set()
    by_identity: dict[tuple[str, ...], PatchabilityEvidence] = {}
    for raw in supplied:
        supplied_kind = (
            raw.kind
            if isinstance(raw, PatchabilityEvidence)
            else str(raw.get("kind", "")).strip()
            if isinstance(raw, Mapping)
            else ""
        )
        item = _coerce_evidence(raw)
        if item is None:
            if supplied_kind:
                ignored.add(supplied_kind)
            continue
        key = _evidence_identity(item)
        current = by_identity.get(key)
        rank = (item.weight, item.kind, item.detail, item.origin)
        current_rank = (
            (current.weight, current.kind, current.detail, current.origin)
            if current is not None
            else None
        )
        if current is None or rank > current_rank:
            by_identity[key] = item

    # Each dimension is a bounded question, not a match counter.  Multiple
    # confirmations of the same dimension therefore contribute once.
    by_kind: dict[str, PatchabilityEvidence] = {}
    for item in by_identity.values():
        current = by_kind.get(item.kind)
        rank = (item.weight, item.detail, item.origin, item.evidence_id or "")
        current_rank = (
            (
                current.weight,
                current.detail,
                current.origin,
                current.evidence_id or "",
            )
            if current is not None
            else None
        )
        if current is None or rank > current_rank:
            by_kind[item.kind] = item
    positives = tuple(
        sorted(by_kind.values(), key=lambda item: (item.kind, item.detail))
    )

    if isinstance(risks, (str, bytes)):
        raise TypeError("risks must be an iterable of risk records")
    supplied_risks = tuple(
        islice(iter(risks), MAX_SUPPLIED_PATCHABILITY_RISKS + 1)
    )
    if len(supplied_risks) > MAX_SUPPLIED_PATCHABILITY_RISKS:
        raise ValueError(
            "patchability risks exceed the defensive input limit of "
            f"{MAX_SUPPLIED_PATCHABILITY_RISKS}"
        )
    by_risk_kind: dict[str, PatchabilityRiskAdjustment] = {}
    for raw in supplied_risks:
        item = _coerce_risk(raw)
        if item is None:
            continue
        current = by_risk_kind.get(item.kind)
        if current is None or item.detail < current.detail:
            by_risk_kind[item.kind] = item
    adjustments = tuple(
        sorted(by_risk_kind.values(), key=lambda item: (item.kind, item.detail))
    )

    raw_score = sum(item.weight for item in positives) + sum(
        item.weight for item in adjustments
    )
    bounded_score = 0 if hard_blocked else max(0, min(100, raw_score))
    return PatchabilityScore(
        path=str(path),
        patchability_score=bounded_score,
        patchability_band=patchability_band(bounded_score),
        positive_evidence=positives,
        risk_adjustments=adjustments,
        ignored_evidence_kinds=tuple(sorted(ignored)),
        hard_blocked=bool(hard_blocked),
    )


def score_file_patchability(
    path_or_candidate: str | Mapping[str, Any],
    evidence: Iterable[PatchabilityEvidence | Mapping[str, Any]] | None = None,
    *,
    risks: Iterable[
        PatchabilityRiskAdjustment | Mapping[str, Any] | str
    ] = (),
    hard_blocked: bool = False,
) -> PatchabilityScore:
    """Convenience wrapper for a path or candidate mapping."""

    if isinstance(path_or_candidate, str):
        path = path_or_candidate
        supplied_evidence = () if evidence is None else evidence
    elif isinstance(path_or_candidate, Mapping):
        path = str(path_or_candidate.get("path", ""))
        supplied_evidence = (
            path_or_candidate.get("patchability_evidence", ())
            if evidence is None
            else evidence
        )
    else:
        raise TypeError("path_or_candidate must be a path or mapping")
    return calculate_patchability_score(
        path,
        supplied_evidence,
        risks=risks,
        hard_blocked=hard_blocked,
    )


# Stable short aliases for callers and contract examples.
calculate_file_patchability = calculate_patchability_score
score_patchability = calculate_patchability_score
