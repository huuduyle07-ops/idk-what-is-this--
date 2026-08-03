"""Deterministic, permission-independent file actionability scoring.

Scores answer only how strongly supplied evidence suggests that inspecting or
eventually modifying a file may help the current task.  They never authorize a
read or a write.  Capability/editability states are evaluated separately as
hard action gates.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import islice
from typing import Any, Iterable, Iterator, Mapping

from core.file_capabilities import FileCapability


SCORING_STAGES = ("inventory", "filename_match", "lexical_search")
MAX_SUPPLIED_ACTIONABILITY_EVIDENCE = 512
MAX_SUPPLIED_RISK_ADJUSTMENTS = 128

EVIDENCE_WEIGHTS: dict[str, int] = {
    "user_named_file": 35,
    "user_named_symbol": 22,
    "exact_filename_match": 26,
    "filename_token_match": 12,
    "path_token_match": 8,
    "likely_entrypoint": 10,
    "configuration_file": 8,
    "test_pair": 15,
    "direct_import_reference": 18,
    "direct_symbol_reference": 25,
    "lexical_match": 20,
    "task_term_match": 20,
    "recent_change_hint": 8,
    "single_readable_file": 40,
    "unsupported_but_readable_text": 6,
}

EVIDENCE_STAGE: dict[str, str] = {
    "likely_entrypoint": "inventory",
    "configuration_file": "inventory",
    "single_readable_file": "inventory",
    "unsupported_but_readable_text": "inventory",
    "user_named_file": "filename_match",
    "user_named_symbol": "filename_match",
    "exact_filename_match": "filename_match",
    "filename_token_match": "filename_match",
    "path_token_match": "filename_match",
    "test_pair": "filename_match",
    "direct_import_reference": "filename_match",
    "direct_symbol_reference": "filename_match",
    "recent_change_hint": "filename_match",
    "lexical_match": "lexical_search",
    "task_term_match": "lexical_search",
}

# Repeated matches may add useful corroboration, but no evidence kind can grow
# without bound.  Most binary facts are intentionally capped at one weight.
EVIDENCE_KIND_CAPS: dict[str, int] = {
    **{kind: weight for kind, weight in EVIDENCE_WEIGHTS.items()},
    "filename_token_match": 24,
    "path_token_match": 16,
    "lexical_match": 30,
    "task_term_match": 30,
    "direct_import_reference": 36,
    "direct_symbol_reference": 50,
}

RISK_WEIGHTS: dict[str, int] = {
    "high_dependency_centrality": -12,
    "high_blast_radius": -15,
    "file_class_risk": -10,
    "parser_partial": -4,
    "parser_unsupported": -8,
    "generated_or_vendor": -20,
    "validation_gap": -6,
}

SCORE_BANDS = (
    (80, 100, "primary_patch_candidate"),
    (60, 79, "inspect_before_patch"),
    (35, 59, "supporting_context"),
    (1, 34, "low_priority_context"),
    (0, 0, "forbidden_or_no_evidence"),
)

FILENAME_ONLY_EVIDENCE = frozenset(
    {
        "exact_filename_match",
        "filename_token_match",
        "path_token_match",
        "likely_entrypoint",
        "configuration_file",
        "single_readable_file",
        "unsupported_but_readable_text",
    }
)

PATCH_GROUNDING_EVIDENCE = frozenset(
    {
        "user_named_file",
        "user_named_symbol",
        "test_pair",
        "direct_import_reference",
        "direct_symbol_reference",
        "lexical_match",
        "task_term_match",
        "recent_change_hint",
    }
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
class ActionabilityEvidence(_RecordMapping):
    kind: str
    detail: str
    stage: str
    weight: int
    related_path: str | None = None
    evidence_id: str | None = None

    def __post_init__(self) -> None:
        if self.stage not in SCORING_STAGES:
            raise ValueError(f"unsupported scoring stage: {self.stage}")
        if isinstance(self.weight, bool) or not isinstance(self.weight, int):
            raise TypeError("evidence weight must be an integer")
        if self.weight < 0:
            raise ValueError("positive evidence weight must be non-negative")

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "kind": self.kind,
            "weight": self.weight,
            "detail": self.detail,
            "stage": self.stage,
        }
        if self.related_path is not None:
            result["related_path"] = self.related_path
        if self.evidence_id is not None:
            result["evidence_id"] = self.evidence_id
        return result


@dataclass(frozen=True, slots=True)
class RiskAdjustment(_RecordMapping):
    kind: str
    weight: int
    detail: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.weight, bool) or not isinstance(self.weight, int):
            raise TypeError("risk weight must be an integer")
        if self.weight > 0:
            raise ValueError("risk adjustment weight must be non-positive")

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"kind": self.kind, "weight": self.weight}
        if self.detail:
            result["detail"] = self.detail
        return result


@dataclass(frozen=True, slots=True)
class ScoreHistoryEntry(_RecordMapping):
    stage: str
    score: int

    def as_dict(self) -> dict[str, Any]:
        return {"stage": self.stage, "score": self.score}


@dataclass(frozen=True, slots=True)
class ActionabilityScore(_RecordMapping):
    path: str
    actionability_score: int
    score_band: str
    positive_evidence: tuple[ActionabilityEvidence, ...]
    risk_adjustments: tuple[RiskAdjustment, ...]
    score_history: tuple[ScoreHistoryEntry, ...]
    filename_only: bool
    forbidden_override: bool = False

    def __post_init__(self) -> None:
        if not 0 <= self.actionability_score <= 100:
            raise ValueError("actionability score must be bounded from 0 through 100")
        if self.score_band != score_band(self.actionability_score):
            raise ValueError("score band must match actionability score")
        if tuple(item.stage for item in self.score_history) != SCORING_STAGES:
            raise ValueError("score history must use the stable scoring-stage order")
        if any(item.weight <= 0 for item in self.positive_evidence):
            raise ValueError("positive evidence must contain only contributing records")
        if len(self.risk_adjustments) > len(RISK_WEIGHTS):
            raise ValueError("risk adjustments must be bounded by known risk kinds")

    @property
    def score(self) -> int:
        return self.actionability_score

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "actionability_score": self.actionability_score,
            "score_band": self.score_band,
            "positive_evidence": [item.as_dict() for item in self.positive_evidence],
            "risk_adjustments": [item.as_dict() for item in self.risk_adjustments],
            "score_history": [item.as_dict() for item in self.score_history],
            "filename_only": self.filename_only,
            "forbidden_override": self.forbidden_override,
        }


@dataclass(frozen=True, slots=True)
class CandidateActionDecision(_RecordMapping):
    action: str
    recommended_action: str
    can_propose_read: bool
    can_propose_patch: bool
    write_authority: bool
    reason: str
    warnings: tuple[str, ...] = ()
    authoritative_source: str | None = None

    def __post_init__(self) -> None:
        if self.write_authority is not False:
            raise ValueError("candidate decisions can never carry write authority")

    def as_dict(self) -> dict[str, Any]:
        result = {
            "action": self.action,
            "recommended_action": self.recommended_action,
            "can_propose_read": self.can_propose_read,
            "can_propose_patch": self.can_propose_patch,
            "write_authority": False,
            "reason": self.reason,
            "warnings": list(self.warnings),
        }
        if self.authoritative_source is not None:
            result["authoritative_source"] = self.authoritative_source
        return result


def _coerce_evidence(
    value: ActionabilityEvidence | Mapping[str, Any],
) -> ActionabilityEvidence:
    if isinstance(value, ActionabilityEvidence):
        return value
    if not isinstance(value, Mapping):
        raise TypeError("evidence must be ActionabilityEvidence or a mapping")
    kind = str(value.get("kind", "")).strip()
    if not kind:
        raise ValueError("evidence kind must be nonblank")
    raw_weight = value.get("weight", EVIDENCE_WEIGHTS.get(kind, 0))
    if isinstance(raw_weight, bool) or not isinstance(raw_weight, int):
        raise TypeError("evidence weight must be an integer")
    return ActionabilityEvidence(
        kind=kind,
        detail=str(value.get("detail", "")),
        stage=str(value.get("stage", EVIDENCE_STAGE.get(kind, "filename_match"))),
        weight=raw_weight,
        related_path=(
            str(value["related_path"]) if value.get("related_path") else None
        ),
        evidence_id=(str(value["evidence_id"]) if value.get("evidence_id") else None),
    )


def _coerce_risk(value: RiskAdjustment | Mapping[str, Any] | str) -> RiskAdjustment:
    if isinstance(value, RiskAdjustment):
        return value
    if isinstance(value, str):
        return RiskAdjustment(kind=value, weight=RISK_WEIGHTS.get(value, 0))
    if not isinstance(value, Mapping):
        raise TypeError("risk must be RiskAdjustment, mapping, or string")
    kind = str(value.get("kind", "")).strip()
    if not kind:
        raise ValueError("risk kind must be nonblank")
    raw_weight = value.get("weight", RISK_WEIGHTS.get(kind, 0))
    if isinstance(raw_weight, bool) or not isinstance(raw_weight, int):
        raise TypeError("risk weight must be an integer")
    return RiskAdjustment(
        kind=kind,
        weight=raw_weight,
        detail=str(value.get("detail", "")),
    )


def _evidence_key(item: ActionabilityEvidence) -> tuple[str, ...]:
    if item.evidence_id:
        return ("id", item.evidence_id)
    return (
        "value",
        item.kind,
        item.detail,
        item.related_path or "",
    )


def _risk_key(item: RiskAdjustment) -> str:
    return item.kind


def score_band(score: int) -> str:
    bounded = max(0, min(100, int(score)))
    for low, high, label in SCORE_BANDS:
        if low <= bounded <= high:
            return label
    raise AssertionError("score bands do not cover the bounded range")


def _capability_value(capability: FileCapability | Mapping[str, Any] | None, key: str) -> Any:
    if capability is None:
        return None
    if isinstance(capability, Mapping):
        return capability.get(key)
    return getattr(capability, key, None)


def calculate_actionability_score(
    path: str,
    evidence: Iterable[ActionabilityEvidence | Mapping[str, Any]],
    *,
    risks: Iterable[RiskAdjustment | Mapping[str, Any] | str] = (),
    capability: FileCapability | Mapping[str, Any] | None = None,
) -> ActionabilityScore:
    """Return an explainable, stable integer score in the inclusive 0-100 range."""

    if isinstance(evidence, (str, bytes)):
        raise TypeError("evidence must be an iterable of evidence records")
    supplied_evidence = tuple(
        islice(iter(evidence), MAX_SUPPLIED_ACTIONABILITY_EVIDENCE + 1)
    )
    if len(supplied_evidence) > MAX_SUPPLIED_ACTIONABILITY_EVIDENCE:
        raise ValueError(
            "evidence exceeds the defensive input limit of "
            f"{MAX_SUPPLIED_ACTIONABILITY_EVIDENCE}"
        )
    unique_evidence: dict[tuple[str, ...], ActionabilityEvidence] = {}
    for raw in supplied_evidence:
        item = _coerce_evidence(raw)
        key = _evidence_key(item)
        current = unique_evidence.get(key)
        item_rank = (
            item.weight,
            -SCORING_STAGES.index(item.stage),
            item.kind,
            item.detail,
            item.related_path or "",
        )
        current_rank = (
            current.weight,
            -SCORING_STAGES.index(current.stage),
            current.kind,
            current.detail,
            current.related_path or "",
        ) if current is not None else None
        if current is None or item_rank > current_rank:
            unique_evidence[key] = item

    stage_rank = {stage: index for index, stage in enumerate(SCORING_STAGES)}
    ordered_raw = sorted(
        unique_evidence.values(),
        key=lambda item: (
            stage_rank[item.stage],
            item.kind,
            item.detail,
            item.related_path or "",
            item.evidence_id or "",
        ),
    )

    used_by_kind: dict[str, int] = {}
    applied: list[ActionabilityEvidence] = []
    for item in ordered_raw:
        configured_weight = EVIDENCE_WEIGHTS.get(item.kind, 0)
        cap = EVIDENCE_KIND_CAPS.get(item.kind, configured_weight)
        remaining = max(0, cap - used_by_kind.get(item.kind, 0))
        applied_weight = min(configured_weight, remaining)
        used_by_kind[item.kind] = used_by_kind.get(item.kind, 0) + applied_weight
        if applied_weight <= 0:
            continue
        applied.append(
            ActionabilityEvidence(
                kind=item.kind,
                detail=item.detail,
                stage=item.stage,
                weight=applied_weight,
                related_path=item.related_path,
                evidence_id=item.evidence_id,
            )
        )

    if isinstance(risks, (str, bytes)):
        raise TypeError("risks must be an iterable of risk records")
    supplied_risks = tuple(
        islice(iter(risks), MAX_SUPPLIED_RISK_ADJUSTMENTS + 1)
    )
    if len(supplied_risks) > MAX_SUPPLIED_RISK_ADJUSTMENTS:
        raise ValueError(
            "risks exceeds the defensive input limit of "
            f"{MAX_SUPPLIED_RISK_ADJUSTMENTS}"
        )
    unique_risks: dict[str, RiskAdjustment] = {}
    for raw in supplied_risks:
        supplied_item = _coerce_risk(raw)
        configured_weight = RISK_WEIGHTS.get(supplied_item.kind, 0)
        if configured_weight == 0:
            continue
        item = RiskAdjustment(
            kind=supplied_item.kind,
            weight=configured_weight,
            detail=supplied_item.detail,
        )
        key = _risk_key(item)
        current = unique_risks.get(key)
        if current is None or (item.detail, item.kind) < (
            current.detail,
            current.kind,
        ):
            unique_risks[key] = item

    parser = _capability_value(capability, "parser_support")
    if parser == "partial":
        item = RiskAdjustment("parser_partial", RISK_WEIGHTS["parser_partial"])
        unique_risks.setdefault(_risk_key(item), item)
    elif parser == "unsupported":
        item = RiskAdjustment("parser_unsupported", RISK_WEIGHTS["parser_unsupported"])
        unique_risks.setdefault(_risk_key(item), item)
    if _capability_value(capability, "generated") or _capability_value(capability, "vendor"):
        item = RiskAdjustment(
            "generated_or_vendor", RISK_WEIGHTS["generated_or_vendor"]
        )
        unique_risks.setdefault(_risk_key(item), item)

    ordered_risks = tuple(
        sorted(unique_risks.values(), key=lambda item: (item.kind, item.detail))
    )
    risk_total = sum(item.weight for item in ordered_risks)

    forbidden = _capability_value(capability, "editability") in {
        "forbidden",
        "outside_scope",
    }
    history: list[ScoreHistoryEntry] = []
    running = 0
    for stage in SCORING_STAGES:
        running += sum(item.weight for item in applied if item.stage == stage)
        stage_score = 0 if forbidden else max(0, min(100, running + risk_total))
        history.append(ScoreHistoryEntry(stage=stage, score=stage_score))

    final_score = history[-1].score if history else 0
    positive_kinds = {item.kind for item in applied if item.weight > 0}
    filename_only = bool(positive_kinds) and positive_kinds <= FILENAME_ONLY_EVIDENCE

    return ActionabilityScore(
        path=str(path),
        actionability_score=final_score,
        score_band=score_band(final_score),
        positive_evidence=tuple(applied),
        risk_adjustments=ordered_risks,
        score_history=tuple(history),
        filename_only=filename_only,
        forbidden_override=forbidden,
    )


def score_file_actionability(
    capability_or_path: FileCapability | Mapping[str, Any] | str,
    evidence: Iterable[ActionabilityEvidence | Mapping[str, Any]],
    *,
    risks: Iterable[RiskAdjustment | Mapping[str, Any] | str] = (),
) -> ActionabilityScore:
    """Convenience wrapper accepting either a capability record or a path."""

    if isinstance(capability_or_path, str):
        return calculate_actionability_score(
            capability_or_path,
            evidence,
            risks=risks,
        )
    path = (
        str(capability_or_path.get("path", ""))
        if isinstance(capability_or_path, Mapping)
        else capability_or_path.path
    )
    return calculate_actionability_score(
        path,
        evidence,
        risks=risks,
        capability=capability_or_path,
    )


def _evidence_kinds(evidence: Iterable[Any]) -> frozenset[str]:
    kinds: set[str] = set()
    for item in evidence:
        if isinstance(item, ActionabilityEvidence):
            kinds.add(item.kind)
        elif isinstance(item, Mapping) and item.get("kind"):
            kinds.add(str(item["kind"]))
        elif isinstance(item, str):
            kinds.add(item)
    return frozenset(kinds)


def derive_candidate_action(
    *,
    actionability_score: int,
    editability: str,
    readability: str,
    evidence: Iterable[Any],
    read_policy: str = "auto_read_allowed",
    parser_support: str = "supported",
    authoritative_source: str | None = None,
) -> CandidateActionDecision:
    """Apply hard capability gates over relevance without granting authority."""

    score = max(0, min(100, int(actionability_score)))
    kinds = _evidence_kinds(evidence)
    grounded_for_patch = bool(kinds & PATCH_GROUNDING_EVIDENCE)
    warnings: list[str] = []

    if editability in {"forbidden", "outside_scope"}:
        return CandidateActionDecision(
            "exclude",
            "exclude",
            False,
            False,
            False,
            "hard repository or security policy excludes the file",
        )
    if read_policy == "hard_no_auto_read" or editability == "opaque" or readability in {
        "opaque_binary",
        "unreadable",
    }:
        return CandidateActionDecision(
            "exclude",
            "exclude",
            False,
            False,
            False,
            "the file is not eligible for direct textual inspection",
        )
    if (
        read_policy == "explicit_human_approval_required"
        or editability == "sensitive_requires_approval"
        or readability == "sensitive"
    ):
        return CandidateActionDecision(
            "requires_human_approval",
            "requires_human_approval",
            False,
            False,
            False,
            "explicit human approval is required before any direct read",
        )
    if editability == "generated_do_not_edit":
        reason = "generated or vendor output cannot be proposed as a direct patch target"
        if authoritative_source:
            reason += "; inspect the authoritative source instead"
        return CandidateActionDecision(
            "redirect_to_authoritative_source",
            "redirect_to_authoritative_source",
            True,
            False,
            False,
            reason,
            authoritative_source=authoritative_source,
        )

    if parser_support == "unsupported":
        warnings.append(
            "raw textual understanding only; AST and dependency completeness are unavailable"
        )
    elif parser_support == "partial":
        warnings.append("parser understanding is partial")

    if score >= 80 and editability in {"editable", "editable_with_review"} and grounded_for_patch:
        if editability == "editable_with_review":
            warnings.append("editability requires review")
        return CandidateActionDecision(
            "propose_patch_candidate",
            "inspect_then_patch",
            True,
            True,
            False,
            "strong multi-source evidence supports patch consideration after inspection",
            tuple(sorted(set(warnings))),
        )
    if score >= 60 and editability in {"editable", "editable_with_review"} and grounded_for_patch:
        if editability == "editable_with_review":
            warnings.append("editability requires review")
        return CandidateActionDecision(
            "propose_inspect_then_patch",
            "inspect_then_patch",
            True,
            True,
            False,
            "grounded evidence supports inspection before patch consideration",
            tuple(sorted(set(warnings))),
        )
    if score >= 35 or (score > 0 and editability == "read_only"):
        if not grounded_for_patch and score >= 60:
            warnings.append("filename-only evidence cannot create a patch candidate")
        return CandidateActionDecision(
            "propose_read",
            "inspect",
            True,
            False,
            False,
            "the file is relevant supporting context but is not patch-authorized",
            tuple(sorted(set(warnings))),
        )
    return CandidateActionDecision(
        "supporting_context_only",
        "supporting_context_only",
        score > 0,
        False,
        False,
        "evidence is low priority or absent",
        tuple(sorted(set(warnings))),
    )
