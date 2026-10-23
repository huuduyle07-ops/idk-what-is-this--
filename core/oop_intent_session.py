"""Durable, read-only OOP intent evidence bound to one task and source.

This is an adapter for CTX.OOP.1C, not a repair gap or patch authorization.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from core.oop_semantic_review import OOPSemanticReview
from core.repository_identity import derive_repository_id


KIND = "oop_intent"
PROVENANCE = "human_provided_semantic_evidence"


def _hash(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                             separators=(",", ":")).encode("utf-8")).hexdigest()


def _sha(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _text(value: Any, limit: int = 600) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= limit


def make_stored_gap(review: OOPSemanticReview, *, task_text: str,
                    repo_path: str) -> dict[str, Any] | None:
    """Admit only a validated 1C clarification; informational reviews pass through."""
    if review.status != "clarification_required":
        return None
    if len(review.possible_intent_gaps) != 1:
        raise ValueError("malformed_oop_gap")
    gap = review.possible_intent_gaps[0]
    if (gap.status != "clarification_required" or gap.owner != "human"
            or gap.source_fingerprint != review.source_fingerprint
            or gap.task_fingerprint != sha256(task_text.encode("utf-8")).hexdigest()
            or not _text(review.file, 300) or not _text(review.class_identity, 300)
            or not _sha(review.source_fingerprint)):
        raise ValueError("malformed_oop_gap")
    allowed = set(review.evidence_refs)
    if (not set(gap.evidence_refs) <= allowed
            or any(not set(x.evidence_refs) <= allowed for x in review.structural_facts)
            or any(not set(x.evidence_refs) <= allowed for x in review.semantic_observations)):
        raise ValueError("malformed_oop_gap")
    body = {
        "gap_kind": KIND, "dimension": gap.dimension, "question": gap.question,
        "alternatives": [asdict(x) for x in gap.alternatives],
        "evidence_refs": list(gap.evidence_refs),
        "current_facts": [{**asdict(x), "evidence_refs": list(x.evidence_refs)}
                          for x in review.structural_facts],
        "interpretations": [{**asdict(x), "evidence_refs": list(x.evidence_refs)}
                            for x in review.semantic_observations],
        "task_fingerprint": gap.task_fingerprint,
        "repository_id": derive_repository_id(repo_path),
        "source_fingerprint": gap.source_fingerprint,
        "source_path": review.file, "class_identity": review.class_identity,
        "evidence_fingerprint": _hash(sorted(gap.evidence_refs)),
    }
    body["gap_id"] = _hash(body)
    return body


def make_stored_future_design_gap(
    detection: Any, *, task_text: str, repo_path: str,
) -> dict[str, Any] | None:
    """Adapt one validated DETECT.2 result to the frozen OOP UI lifecycle."""
    from core.oop_intent_detector import (
        DISPOSITIONS, OOPIntentDetection, SCHEMA_VERSION as DETECTOR_SCHEMA_VERSION,
    )

    if not isinstance(detection, OOPIntentDetection):
        raise TypeError("an OOPIntentDetection is required")
    if detection.status != "clarification_required":
        return None
    gap = detection.gap
    if gap is None or len(detection.possible_intent_gaps) != 1:
        raise ValueError("malformed_oop_gap")
    repository_id = derive_repository_id(repo_path)
    if (gap.dimension != "future_design_contract"
            or gap.status != "clarification_required" or gap.owner != "human"
            or gap.task_fingerprint != sha256(task_text.encode("utf-8")).hexdigest()
            or gap.repository_id != repository_id
            or detection.repository_id != repository_id
            or gap.source_fingerprint != detection.source_fingerprint
            or gap.design_fingerprint != detection.design_fingerprint
            or gap.task_contract_fingerprint != detection.task_contract_fingerprint
            or not gap.subdimensions or not gap.unresolved_dimension_refs
            or not _sha(gap.source_fingerprint)
            or not _text(detection.source_path, 300)
            or not _text(detection.class_identity, 300)):
        raise ValueError("malformed_oop_gap")
    evidence = set(gap.evidence_refs)
    if any(not set(item.evidence_refs) <= evidence for item in detection.comparisons):
        raise ValueError("malformed_oop_gap")
    material = tuple(item for item in detection.assessments
                     if item.disposition == "human_owned_material")
    if ({item.dimension for item in material} != set(gap.subdimensions)
            or any(item.disposition not in DISPOSITIONS for item in detection.assessments)):
        raise ValueError("malformed_oop_gap")

    dimension_refs = dict(zip(gap.subdimensions, gap.unresolved_dimension_refs, strict=True))
    interpretations = []
    auth_dimensions = tuple(item.dimension for item in material
        if item.dimension.startswith("credential_") or item.dimension == "verification_lifecycle")
    if auth_dimensions:
        interpretations.append({
            "kind": "future_authentication_contract",
            "description": ("Credential ownership, persistence, and verification lifecycle choices "
                            "produce materially different state and gating behavior."),
            "evidence_refs": [dimension_refs[item] for item in auth_dimensions],
            "provenance": "inferred_semantic_interpretation",
        })
    savings_dimensions = tuple(item.dimension for item in material
        if item.dimension.startswith("savings_"))
    if savings_dimensions:
        interpretations.append({
            "kind": "future_savings_contract",
            "description": ("Funding and interest choices produce materially different mutations of "
                            "the inherited balance and savingBalance."),
            "evidence_refs": [dimension_refs[item] for item in savings_dimensions],
            "provenance": "inferred_semantic_interpretation",
        })
    body = {
        "gap_kind": KIND,
        "admission_schema": DETECTOR_SCHEMA_VERSION,
        "dimension": gap.dimension,
        "subdimensions": list(gap.subdimensions),
        "unresolved_dimension_refs": list(gap.unresolved_dimension_refs),
        "question": gap.question,
        "alternatives": [asdict(item) for item in gap.alternatives],
        "evidence_refs": list(gap.evidence_refs),
        "current_facts": [
            {
                "kind": item.kind,
                "description": item.description,
                "evidence_refs": list(item.evidence_refs),
                "current_provenance": item.current_provenance,
                "desired_provenance": item.desired_provenance,
                "is_defect": False,
            }
            for item in detection.comparisons
        ],
        "interpretations": interpretations,
        "dimension_assessments": [asdict(item) for item in detection.assessments],
        "task_fingerprint": gap.task_fingerprint,
        "task_contract_fingerprint": gap.task_contract_fingerprint,
        "design_fingerprint": gap.design_fingerprint,
        "repository_id": repository_id,
        "source_fingerprint": gap.source_fingerprint,
        "source_path": detection.source_path,
        "class_identity": detection.class_identity,
        "evidence_fingerprint": _hash(sorted(gap.evidence_refs)),
        "scope_expansion": "deferred",
    }
    body["gap_id"] = _hash(body)
    return body


def validate_stored_gap(value: Mapping[str, Any], *, task_text: str,
                        repo_path: str) -> dict[str, Any]:
    """Validate immutable content before presentation or answer binding."""
    try:
        gap = dict(value)
        identity = gap.pop("gap_id")
        if (gap.get("gap_kind") != KIND or not _sha(identity) or identity != _hash(gap)
                or gap.get("task_fingerprint") != sha256(task_text.encode("utf-8")).hexdigest()
                or gap.get("repository_id") != derive_repository_id(repo_path)
                or not _sha(gap.get("source_fingerprint"))
                or not _text(gap.get("source_path"), 300)
                or not _text(gap.get("class_identity"), 300)
                or not _text(gap.get("dimension"), 100)
                or not _text(gap.get("question"))):
            raise ValueError
        refs = gap["evidence_refs"]
        if (not isinstance(refs, list) or not 1 <= len(refs) <= 8
                or not all(_text(ref, 300) for ref in refs)
                or gap["evidence_fingerprint"] != _hash(sorted(refs))):
            raise ValueError
        alternatives = gap["alternatives"]
        if (not isinstance(alternatives, list) or not 2 <= len(alternatives) <= 4
                or not all(isinstance(a, dict) and _text(a.get("effect"), 100)
                           and _text(a.get("description")) for a in alternatives)
                or len({a["effect"] for a in alternatives}) < 2):
            raise ValueError
        for key in ("current_facts", "interpretations"):
            if not isinstance(gap[key], list) or len(gap[key]) > 48:
                raise ValueError
            for item in gap[key]:
                if (not isinstance(item, dict) or not _text(item.get("kind"), 100)
                        or not _text(item.get("description"), 500)
                        or not isinstance(item.get("evidence_refs"), list)):
                    raise ValueError
        if gap.get("admission_schema") is not None:
            from core.oop_intent_detector import DISPOSITIONS, SCHEMA_VERSION as detector_schema
            from core.input_understanding import understand_request
            from core.proposed_design_intent import project_proposed_design_intent

            current_contract = understand_request(task_text)
            current_design = project_proposed_design_intent(current_contract)

            if (gap.get("admission_schema") != detector_schema
                    or gap.get("dimension") != "future_design_contract"
                    or not _sha(gap.get("design_fingerprint"))
                    or not _sha(gap.get("task_contract_fingerprint"))
                    or gap.get("task_contract_fingerprint") != _hash(current_contract.as_dict())
                    or gap.get("design_fingerprint") != current_design.fingerprint
                    or gap.get("scope_expansion") != "deferred"):
                raise ValueError
            subdimensions = gap.get("subdimensions")
            dimension_refs = gap.get("unresolved_dimension_refs")
            if (not isinstance(subdimensions, list) or not 1 <= len(subdimensions) <= 7
                    or len(subdimensions) != len(set(subdimensions))
                    or not isinstance(dimension_refs, list)
                    or len(dimension_refs) != len(subdimensions)
                    or len(dimension_refs) != len(set(dimension_refs))
                    or any(not _text(item, 100) for item in subdimensions)
                    or any(not isinstance(item, str)
                           or not item.startswith("unresolved_dimension:")
                           or len(item) != len("unresolved_dimension:") + 64
                           for item in dimension_refs)):
                raise ValueError
            assessments = gap.get("dimension_assessments")
            if (not isinstance(assessments, list) or len(assessments) > 11
                    or any(not isinstance(item, dict)
                           or item.get("disposition") not in DISPOSITIONS
                           or not _text(item.get("dimension"), 100)
                           or not _text(item.get("reason"), 300)
                           for item in assessments)):
                raise ValueError
            material_dimensions = {
                item["dimension"] for item in assessments
                if item["disposition"] == "human_owned_material"
            }
            if material_dimensions != set(subdimensions):
                raise ValueError
        gap["gap_id"] = identity
        return gap
    except (KeyError, TypeError, ValueError, OSError) as exc:
        raise ValueError("malformed_oop_gap") from exc


def source_freshness(gap: Mapping[str, Any], *, repo_path: str) -> str:
    """Conservative exact-source check. No walk, index, or partial rebase."""
    try:
        root = Path(repo_path).resolve()
        target = (root / gap["source_path"]).resolve()
        target.relative_to(root)
        return "current" if sha256(target.read_bytes()).hexdigest() == gap["source_fingerprint"] else "stale_source"
    except (KeyError, TypeError, ValueError, OSError):
        return "stale_source"


@dataclass(frozen=True, slots=True)
class OOPHumanAnswer:
    gap_id: str
    task_fingerprint: str
    repository_id: str
    class_identity: str
    source_fingerprint: str
    evidence_fingerprint: str
    text: str
    answer_fingerprint: str
    provenance: str = PROVENANCE

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def bind_human_answer(gap: Mapping[str, Any], text: str,
                      previous: Mapping[str, Any] | None = None) -> OOPHumanAnswer:
    if not _text(text, 4000):
        raise ValueError("invalid_clarification_answer")
    answer = OOPHumanAnswer(
        gap["gap_id"], gap["task_fingerprint"], gap["repository_id"],
        gap["class_identity"], gap["source_fingerprint"],
        gap["evidence_fingerprint"], text.strip(), _hash(text.strip()))
    if previous is not None:
        if dict(previous) == answer.as_dict():
            return answer
        raise ValueError("clarification_conflict")
    return answer
