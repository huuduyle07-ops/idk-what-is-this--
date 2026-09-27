"""REPAIR.INTENT.DETECT.1: bounded, harness-owned ambiguity admission.

The Java adapter supplies syntax facts.  This owner binds them to the current
PREFLIGHT receipt, deduplicates them, and creates one existing RepairIntentGap.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import time
from typing import Any, Mapping

from core.input_understanding import understand_request
from core.java_repair_intent_ambiguity import JavaDeclaration, project_java_ownership_evidence
from core.repair_intent import RepairIntentGap, SemanticAlternative
from core.repair_intent_evidence_refs import EvidenceRefError, resolve_repair_intent_evidence_refs
from core.repository_identity import derive_repository_id


PHASE_ID = "REPAIR.INTENT.DETECT.1"
DIMENSION = "state_ownership"


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


@dataclass(frozen=True, slots=True)
class SemanticAmbiguityFact:
    ambiguity_kind: str
    affected_members: tuple[str, ...]
    diagnostic_refs: tuple[str, ...]
    declaration_ref: str
    declaration: JavaDeclaration
    semantic_dimension: str
    source_fingerprint: str
    evidence_fingerprint: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "ambiguity_kind": self.ambiguity_kind,
            "affected_members": list(self.affected_members),
            "diagnostic_refs": list(self.diagnostic_refs),
            "declaration_ref": self.declaration_ref,
            "declaration": {
                "file": self.declaration.file, "name": self.declaration.name,
                "owner": self.declaration.owner, "kind": self.declaration.kind,
                "lexical_scope": self.declaration.lexical_scope,
                "source_fingerprint": self.declaration.source_fingerprint,
                "start_byte": self.declaration.start_byte,
                "end_byte": self.declaration.end_byte,
                "is_static": self.declaration.is_static,
            },
            "semantic_dimension": self.semantic_dimension,
            "source_fingerprint": self.source_fingerprint,
            "evidence_fingerprint": self.evidence_fingerprint,
        }


@dataclass(frozen=True, slots=True)
class AmbiguityDetection:
    facts: tuple[SemanticAmbiguityFact, ...] = ()
    gap: RepairIntentGap | None = None
    timings_ms: tuple[tuple[str, float], ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {"phase_id": PHASE_ID,
                "status": "waiting_for_clarification" if self.gap else "not_detected",
                "facts": [fact.as_dict() for fact in self.facts],
                "timings_ms": dict(self.timings_ms),
                "model_calls": 0, "network_calls": 0,
                "repository_traversals": 0}


def _explicitly_resolved(fact: SemanticAmbiguityFact, contract: Any) -> bool:
    """Recognize only explicit, preserved ownership commitments for V1."""
    if not contract.routing_allowed or not contract.preservation.passed:
        return False
    text = contract.raw_request.text
    clauses = re.split(r"[.!?;\n]", text)
    for clause in clauses:
        words = clause.casefold()
        if fact.ambiguity_kind == "cross_member_local_reference":
            if (re.search(r"\b(?:method[- ]local|local)\b", words)
                    and re.search(r"\b(?:pass|passed|passing|parameter|parameters)\b", words)
                    and re.search(r"(?<![\w$])" + re.escape(fact.declaration.name.casefold())
                                  + r"(?![\w$])", words)):
                return True
        elif fact.ambiguity_kind == "static_instance_state_ambiguity":
            if (re.search(r"(?<![\w$])" + re.escape(fact.affected_members[0].casefold())
                          + r"(?![\w$])", words)
                    and re.search(r"\b(?:remain|keep|stays?|must)\b", words)
                    and re.search(r"\bstatic\b", words)
                    and re.search(r"\b(?:shared|class)\b", words)
                    and re.search(r"\bstate\b", words)):
                return True
    return False


def detect_repair_intent_ambiguity(*, task_text: str, control: Mapping[str, Any],
                                   repo_path: str | Path,
                                   language: str = "java") -> AmbiguityDetection:
    """Read one exact source file; admit one gap before patch authoring if proven."""
    started = time.perf_counter()
    if language.lower() != "java":
        return AmbiguityDetection()
    scope = control.get("repair_scope") or {}
    preflight = control.get("preflight_validation") or {}
    if (scope.get("status") != "complete" or preflight.get("measured") is not True
            or preflight.get("evidence_source") != "PREFLIGHT.REQUEST.1"
            or preflight.get("evidence_kind") != "compile_evidence"
            or scope.get("evidence_fingerprint") != preflight.get("receipt_fingerprint")
            or scope.get("control_fingerprint") != preflight.get("control_sha256")
            or scope.get("repository_id") != preflight.get("repository_id")):
        return AmbiguityDetection()
    file = (scope.get("primary_target") or {}).get("file")
    if not isinstance(file, str) or not file.lower().endswith(".java"):
        return AmbiguityDetection()
    try:
        root = Path(repo_path).resolve()
        target = (root / file).resolve()
        target.relative_to(root)
        if derive_repository_id(root) != scope["repository_id"]:
            return AmbiguityDetection()
        raw = target.read_bytes()
        source_fingerprint = _digest(raw)
        if source_fingerprint != scope["source_fingerprint"]:
            return AmbiguityDetection()
        fingerprints = {item["path"]: item["sha256"]
                        for item in preflight.get("source_fingerprints") or ()}
        if fingerprints.get(file) != source_fingerprint:
            return AmbiguityDetection()
        locations = preflight.get("locations") or ()
        if (any(item.get("language") != "java" or item.get("file") != file
                for item in locations)
                or sorted(_canonical({key: value for key, value in item.items()
                                       if key != "language"})
                          for item in locations)
                   != sorted(_canonical(item)
                             for member in scope.get("members") or ()
                             for item in member.get("diagnostics") or ())):
            return AmbiguityDetection()
        projected = project_java_ownership_evidence(
            raw=raw, file=file, source_fingerprint=source_fingerprint, scope=scope)
        projection_done = time.perf_counter()
        grouped: dict[tuple[str, str, str, int], list[Any]] = {}
        for item in projected:
            declaration = item.declaration
            key = (item.kind, declaration.name, declaration.owner, declaration.start_byte)
            grouped.setdefault(key, []).append(item)
        measured = {member.get("symbol") for member in scope.get("members") or ()}
        facts = []
        for key, items in sorted(grouped.items()):
            declaration = items[0].declaration
            members = tuple(sorted({item.diagnostic_owner for item in items}
                                   | ({declaration.owner} if declaration.owner in measured else set())))
            refs = tuple(sorted({f"diagnostic:{file}::{item.diagnostic_owner}::"
                                 f"{item.diagnostic_ordinal}" for item in items}))
            fact = SemanticAmbiguityFact(
                key[0], members, refs,
                f"declaration:{file}::{declaration.owner}::{declaration.name}::"
                f"{declaration.start_byte}:{declaration.end_byte}",
                declaration, DIMENSION, source_fingerprint, scope["evidence_fingerprint"])
            facts.append(fact)
        contract = understand_request(task_text)
        facts = [fact for fact in facts if not _explicitly_resolved(fact, contract)]
        dedup_done = time.perf_counter()
        if not facts or len(facts) > 8 or not contract.routing_allowed:
            return AmbiguityDetection(tuple(facts), timings_ms=(
                ("projection", (projection_done - started) * 1000),
                ("deduplication", (dedup_done - projection_done) * 1000)))
        refs: list[str] = []
        for fact in facts:
            refs.append(fact.diagnostic_refs[0])
        for fact in facts:
            refs.extend(f"member:{file}::{member}" for member in fact.affected_members)
        for fact in facts:
            refs.extend(fact.diagnostic_refs[1:])
        refs = list(dict.fromkeys(refs))[:8]
        anchors = resolve_repair_intent_evidence_refs(refs=refs, scope=scope, raw=raw)
        refs_done = time.perf_counter()
        cross = any(fact.ambiguity_kind == "cross_member_local_reference" for fact in facts)
        static = any(fact.ambiguity_kind == "static_instance_state_ambiguity" for fact in facts)
        question = "These values are referenced across different Java scopes. What state or value ownership did you intend?"
        if cross:
            question += " Should method-local values be supplied explicitly, or represent shared state?"
        if static:
            question += " Should the static method use per-instance state, shared class state, or another intended source?"
        alternatives = []
        if cross:
            alternatives.extend((
                SemanticAlternative("Values remain local and are supplied explicitly", "parameter_value",
                                    evidence_refs=tuple(refs)),
                SemanticAlternative("Values represent shared state", "shared_state",
                                    evidence_refs=tuple(refs))))
        if static:
            alternatives.extend((
                SemanticAlternative("The static method uses per-instance state", "instance_state",
                                    evidence_refs=tuple(refs)),
                SemanticAlternative("The static method uses shared class state", "shared_state",
                                    evidence_refs=tuple(refs))))
        # Combined evidence still yields one bounded set of semantic effects.
        alternatives = list(dict.fromkeys((item.effect, item) for item in alternatives))
        alternatives = [item for _, item in alternatives]
        members = tuple(member.get("symbol") for member in scope.get("members") or ()
                        if member.get("symbol") in {name for fact in facts for name in fact.affected_members})
        task_fingerprint = _digest(_canonical(contract.as_dict()))
        body = {"task": task_fingerprint, "control": scope["control_fingerprint"],
                "repo": scope["repository_id"], "source": source_fingerprint,
                "evidence": scope["evidence_fingerprint"], "members": members,
                "dimension": DIMENSION, "alternatives": [item.as_dict() for item in alternatives],
                "question": question, "anchors": list(anchors)}
        gap = RepairIntentGap(_digest(_canonical(body)), task_fingerprint,
                              scope["control_fingerprint"], scope["repository_id"],
                              source_fingerprint, scope["evidence_fingerprint"], file,
                              members, DIMENSION, tuple(alternatives), question, anchors)
        finished = time.perf_counter()
        return AmbiguityDetection(tuple(facts), gap, (
            ("projection", (projection_done - started) * 1000),
            ("deduplication", (dedup_done - projection_done) * 1000),
            ("evidence_refs", (refs_done - dedup_done) * 1000),
            ("gap_admission", (finished - refs_done) * 1000)))
    except (EvidenceRefError, KeyError, TypeError, ValueError, OSError, UnicodeError):
        return AmbiguityDetection()
