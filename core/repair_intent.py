"""REPAIR.INTENT.1: bounded semantic clarification between repair evidence and authoring.

An author may *report* alternatives. This module alone admits a wait: two
source-grounded alternatives must have different declared semantic effects,
the measured scope must be complete, and no authoritative choice may exist.
No alternative is a patch or an execution authorization.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from core.repository_identity import derive_repository_id
from core.input_understanding import understand_request
from core.repair_intent_evidence_refs import (
    EvidenceRefError, available_repair_intent_refs,
    resolve_repair_intent_evidence_refs,
)


PHASE_ID = "REPAIR.INTENT.1"
SEMANTIC_INTENT_REQUIRED = "semantic_intent_required"
WAITING = "waiting_for_clarification"
RESOLVED = "clarification_supplied"
DECLINED = "clarification_declined"
DIMENSIONS = frozenset({"state_ownership", "value_source", "output_behavior"})
EFFECTS = frozenset({"instance_state", "shared_state", "independent_value",
                     "parameter_value", "different_output", "other"})
MAX_TEXT = 600


def preserved_task_text(control: Mapping[str, Any]) -> str:
    """Read the original task carried by CONTROL for clarification binding."""
    return str(control.get("query") or "")


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _bounded(value: Any, *, max_length: int = MAX_TEXT) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        raise ValueError("malformed_semantic_gap")
    return value.strip()


def _sha(value: Any) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(
        char not in "0123456789abcdef" for char in value
    ):
        raise ValueError("malformed_semantic_gap")
    return value


@dataclass(frozen=True, slots=True)
class SemanticAlternative:
    description: str
    effect: str
    source_quote: str = ""
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _bounded(self.description)
        if self.evidence_refs:
            # Compatibility telemetry: its whitespace is never source authority.
            if not isinstance(self.source_quote, str) or len(self.source_quote) > 300:
                raise ValueError("malformed_semantic_gap")
        else:
            _bounded(self.source_quote, max_length=300)
        if self.effect not in EFFECTS:
            raise ValueError("malformed_semantic_gap")

    def as_dict(self) -> dict[str, Any]:
        return {"description": self.description, "effect": self.effect,
                "source_quote": self.source_quote,
                "evidence_refs": list(self.evidence_refs)}


@dataclass(frozen=True, slots=True)
class RepairIntentGap:
    ambiguity_id: str
    task_fingerprint: str
    control_fingerprint: str
    repository_id: str
    source_fingerprint: str
    evidence_fingerprint: str
    source_path: str
    affected_members: tuple[str, ...]
    dimension: str
    alternatives: tuple[SemanticAlternative, ...]
    question: str
    anchors: tuple[dict[str, Any], ...] = ()
    status: str = WAITING

    def __post_init__(self) -> None:
        for value in (self.ambiguity_id, self.task_fingerprint,
                      self.control_fingerprint, self.source_fingerprint,
                      self.evidence_fingerprint):
            _sha(value)
        _bounded(self.repository_id)
        _bounded(self.source_path, max_length=300)
        _bounded(self.question)
        if self.dimension not in DIMENSIONS or self.status not in {WAITING, RESOLVED, DECLINED}:
            raise ValueError("malformed_semantic_gap")
        if not 1 <= len(self.affected_members) <= 8 or not all(
            isinstance(x, str) and 0 < len(x) <= 100 for x in self.affected_members
        ):
            raise ValueError("malformed_semantic_gap")
        if not 2 <= len(self.alternatives) <= 4 or len({
            item.effect for item in self.alternatives
        }) < 2:
            raise ValueError("malformed_semantic_gap")
        refs = {ref for item in self.alternatives for ref in item.evidence_refs}
        anchor_refs = set()
        total = 0
        for anchor in self.anchors:
            if not isinstance(anchor, Mapping):
                raise ValueError("malformed_semantic_gap")
            body = {key: value for key, value in anchor.items() if key != "anchor_id"}
            if (anchor.get("anchor_id") != _digest(_canonical(body))
                    or anchor.get("repository_id") != self.repository_id
                    or anchor.get("file") != self.source_path
                    or anchor.get("source_fingerprint") != self.source_fingerprint
                    or not isinstance(anchor.get("ref"), str)
                    or not isinstance(anchor.get("exact_text"), str)):
                raise ValueError("malformed_semantic_gap")
            span = anchor.get("span")
            if (not isinstance(span, Mapping)
                    or not isinstance(span.get("start_byte"), int)
                    or not isinstance(span.get("end_byte"), int)
                    or not 0 <= span["start_byte"] < span["end_byte"]):
                raise ValueError("malformed_semantic_gap")
            total += len(anchor["exact_text"].encode("utf-8"))
            if anchor["ref"] in anchor_refs or total > 16_384:
                raise ValueError("malformed_semantic_gap")
            anchor_refs.add(anchor["ref"])
        if refs != anchor_refs:
            raise ValueError("malformed_semantic_gap")

    def as_dict(self) -> dict[str, Any]:
        return {"phase_id": PHASE_ID, "ambiguity_id": self.ambiguity_id,
                "task_fingerprint": self.task_fingerprint,
                "control_fingerprint": self.control_fingerprint,
                "repository_id": self.repository_id,
                "source_fingerprint": self.source_fingerprint,
                "evidence_fingerprint": self.evidence_fingerprint,
                "source_path": self.source_path,
                "affected_members": list(self.affected_members),
                "dimension": self.dimension,
                "alternatives": [x.as_dict() for x in self.alternatives],
                "question": self.question, "anchors": list(self.anchors),
                "status": self.status}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RepairIntentGap":
        if value.get("phase_id") != PHASE_ID:
            raise ValueError("malformed_semantic_gap")
        return cls(value["ambiguity_id"], value["task_fingerprint"],
                   value["control_fingerprint"], value["repository_id"],
                   value["source_fingerprint"], value["evidence_fingerprint"],
                   value["source_path"], tuple(value["affected_members"]),
                   value["dimension"], tuple(SemanticAlternative(
                       description=item["description"], effect=item["effect"],
                       source_quote=item.get("source_quote", ""),
                       evidence_refs=tuple(item.get("evidence_refs") or ()),
                   ) for item in value["alternatives"]), value["question"],
                   tuple(value.get("anchors") or ()), value["status"])


@dataclass(frozen=True, slots=True)
class ClarificationAnswer:
    ambiguity_id: str
    text: str
    provenance: str = "human_provided_semantic_evidence"

    def __post_init__(self) -> None:
        _sha(self.ambiguity_id)
        _bounded(self.text, max_length=4000)
        if self.provenance != "human_provided_semantic_evidence":
            raise ValueError("invalid_answer_provenance")

    def as_dict(self) -> dict[str, str]:
        return {"ambiguity_id": self.ambiguity_id, "text": self.text,
                "provenance": self.provenance}


def author_escalation_directive(scope: Mapping[str, Any] | None = None) -> str:
    """Request bounded observations in the existing author response, no extra call."""
    refs = available_repair_intent_refs(scope or {})
    return """[SEMANTIC INTENT HANDOFF]
If a compiler-grounded repair is structurally possible but two plausible
interpretations would change state ownership, value source, or observable output,
and the task/source supplies no authoritative choice, return patch_candidate=null,
needs_escalation=true, escalation_reason="semantic_intent_required" and semantic_gap:
{"dimension":"state_ownership|value_source|output_behavior",
 "affected_members":["existing member"],
 "alternatives":[{"description":"behavior only, not patch code",
                  "effect":"instance_state|shared_state|independent_value|parameter_value|different_output|other",
                  "evidence_refs":["member:File.java::member"]}, ...],
 "question":"one concrete behavioral decision for the user"}.
Report at least two materially different effects. Each alternative must select
one to eight IDs from the closed list below. A source_quote may be included as
explanatory text, but it is not grounding authority and need not copy exact
whitespace. Do not invent a file, member, line, offset, or evidence ID. Do not
select a behavior or invent a patch. If no listed evidence supports the
ambiguity, use ordinary escalation.
Allowed evidence_refs: """ + json.dumps(refs, ensure_ascii=False) + "\n"


def admit_gap(*, author: Mapping[str, Any], task_text: str,
              control: Mapping[str, Any], scope: Mapping[str, Any],
              repo_path: str | Path, authoritative_choice: str = "") -> RepairIntentGap | None:
    """Fail closed on unsupported or ungrounded model reports; no repository walk."""
    if (author.get("patch_candidate") is not None or author.get("patch_plan")
            or author.get("needs_escalation") is not True
            or author.get("escalation_reason") != SEMANTIC_INTENT_REQUIRED
            or authoritative_choice.strip()):
        return None
    # INPUT.1 keeps the original task lossless. Existing explicit behavior is
    # authoritative; an author report cannot demote it into an ambiguity.
    contract = understand_request(task_text)
    if not contract.routing_allowed or contract.behavioral_expectations:
        return None
    report = author.get("semantic_gap")
    if not isinstance(report, Mapping) or scope.get("status") != "complete":
        return None
    if not isinstance(report.get("alternatives"), list) or not 2 <= len(report["alternatives"]) <= 4:
        return None
    try:
        path = _bounded(scope["primary_target"]["file"], max_length=300)
        root = Path(repo_path).resolve()
        source_path = (root / path).resolve()
        source_path.relative_to(root)
        if derive_repository_id(root) != scope["repository_id"]:
            return None
        raw = source_path.read_bytes()
        if _digest(raw) != _sha(scope["source_fingerprint"]):
            return None
        preflight = control["preflight_validation"]
        if (scope["evidence_fingerprint"] != preflight["receipt_fingerprint"]
                or scope["control_fingerprint"] != preflight["control_sha256"]
                or scope["repository_id"] != preflight["repository_id"]):
            return None
        members = tuple(_bounded(x, max_length=100) for x in report["affected_members"])
        measured = {x["symbol"] for x in scope["members"]}
        if not members or not set(members) <= measured:
            return None
        source = raw.decode("utf-8", errors="replace")
        alternatives_list = []
        anchor_index: dict[str, dict[str, Any]] = {}
        for item in report["alternatives"]:
            refs = item.get("evidence_refs")
            if refs is None and item.get("source_ref") is not None:
                refs = [item["source_ref"]]
            if refs is not None:
                anchors = resolve_repair_intent_evidence_refs(refs=refs, scope=scope, raw=raw)
                for anchor in anchors:
                    anchor_index.setdefault(anchor["anchor_id"], anchor)
                alternatives_list.append(SemanticAlternative(
                    description=item["description"], effect=item["effect"],
                    source_quote=item.get("source_quote", ""),
                    evidence_refs=tuple(dict.fromkeys(refs))))
            else:
                # Legacy quote-only admission stays exact. A quote alongside a
                # valid ref is telemetry and never determines admission.
                alternative = SemanticAlternative(**item)
                if alternative.source_quote not in source:
                    return None
                alternatives_list.append(alternative)
        alternatives = tuple(alternatives_list)
        if sum(len(a["exact_text"].encode("utf-8")) for a in anchor_index.values()) > 16_384:
            raise EvidenceRefError()
        question = _bounded(report["question"])
        dimension = report["dimension"]
        task_fingerprint = _digest(_canonical(contract.as_dict()))
        body = {"task": task_fingerprint, "control": scope["control_fingerprint"],
                "repo": scope["repository_id"], "source": scope["source_fingerprint"],
                "evidence": scope["evidence_fingerprint"], "members": members,
                "dimension": dimension, "alternatives": [x.as_dict() for x in alternatives],
                "question": question, "anchors": list(anchor_index.values())}
        return RepairIntentGap(_digest(_canonical(body)), task_fingerprint,
                               scope["control_fingerprint"], scope["repository_id"],
                               scope["source_fingerprint"], scope["evidence_fingerprint"],
                               path, members, dimension, alternatives, question,
                               tuple(anchor_index.values()))
    except EvidenceRefError:
        raise
    except (KeyError, TypeError, ValueError, OSError, UnicodeError):
        return None


def render_question(gap: RepairIntentGap) -> str:
    return gap.question + "\n" + "\n".join(
        f"{chr(65 + index)}. {item.description}" for index, item in enumerate(gap.alternatives)
    ) + "\nYou can also describe another intended behavior."


def bind_answer(gap: RepairIntentGap, text: str,
                previous: ClarificationAnswer | None = None) -> ClarificationAnswer:
    answer = ClarificationAnswer(gap.ambiguity_id, text)
    if previous is not None:
        if previous == answer:
            return previous
        raise ValueError("clarification_conflict")
    if gap.status != WAITING:
        raise ValueError("clarification_not_waiting")
    return answer


def validate_resume(gap: RepairIntentGap, answer: ClarificationAnswer, *,
                    task_text: str, control: Mapping[str, Any],
                    repo_path: str | Path) -> str:
    """Return current or a typed refusal; stale evidence must be reacquired."""
    task_contract = understand_request(task_text)
    if (answer.ambiguity_id != gap.ambiguity_id or not task_contract.routing_allowed
            or _digest(_canonical(task_contract.as_dict())) != gap.task_fingerprint):
        return "wrong_task"
    if not understand_request(answer.text).routing_allowed:
        return "answer_contract_conflict"
    try:
        root = Path(repo_path).resolve()
        if derive_repository_id(root) != gap.repository_id:
            return "wrong_repository"
        scope = control["repair_scope"]
        preflight = control["preflight_validation"]
        if (scope["control_fingerprint"] != gap.control_fingerprint
                or scope["evidence_fingerprint"] != gap.evidence_fingerprint
                or preflight["control_sha256"] != gap.control_fingerprint
                or preflight["receipt_fingerprint"] != gap.evidence_fingerprint):
            return "wrong_control"
        target = (root / gap.source_path).resolve()
        target.relative_to(root)
        if _digest(target.read_bytes()) != gap.source_fingerprint:
            return "stale_source"
        return "current"
    except (KeyError, TypeError, ValueError, OSError):
        return "stale_evidence"


def render_human_clarification(answer: ClarificationAnswer) -> str:
    # User input is quoted as data and marked distinctly from source/diagnostics.
    return "[HUMAN CLARIFICATION]\n" + json.dumps(answer.text, ensure_ascii=False) + "\n[/HUMAN CLARIFICATION]"
