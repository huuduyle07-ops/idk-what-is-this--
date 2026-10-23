"""CONTINUE.1 owns bounded, gap-scoped clarification typing; no intake/provider.

Only whole clauses in the closed grammar below have semantic authority. Unknown
clauses are retained and prevent readiness, including qualifications/negations
outside this grammar. Spans refer to the stored answer, never current source.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re

from core.explicit_design_evidence import EvidenceSpan


VALUES = {
    "credential_ownership": {"SavingAccount", "BankAccount", "user/account identity", "application/session"},
    "credential_source": {"simple_password"},
    "credential_persistence": {"in_memory_only", "persists_across_runs"},
    "credential_verification_mechanism": {"semantic_password_check"},
    "verification_lifecycle": {"operation_gated", "creation_gated", "both"},
    "savings_funding_semantics": {"transfer_from_inherited_balance", "independently_funded"},
    "savings_interest_semantics": {"interest_applies_to_saving_balance", "no_interest_behavior"},
    "exercise_hashing_constraint": {"hashing_out_of_scope_for_this_exercise"},
}


@dataclass(frozen=True, slots=True)
class AnswerCommitment:
    dimension: str
    value: str
    evidence: EvidenceSpan
    answer_fingerprint: str
    provenance: str = "explicit_human"

    def __post_init__(self):
        allowed = VALUES.get(self.dimension, set())
        if (self.value not in allowed and not (
                self.dimension == "credential_ownership"
                and re.fullmatch(r"explicit_other:[A-Za-z][A-Za-z0-9_]{0,79}", self.value))):
            raise ValueError("unsupported_answer_commitment")
        if (not isinstance(self.evidence, EvidenceSpan) or self.provenance != "explicit_human"
                or self.evidence.provenance != "explicit_human"):
            raise ValueError("invalid_answer_provenance")
        if (not isinstance(self.answer_fingerprint, str) or len(self.answer_fingerprint) != 64
                or any(c not in "0123456789abcdef" for c in self.answer_fingerprint)):
            raise ValueError("invalid_answer_fingerprint")

    def as_dict(self):
        return asdict(self)


@dataclass(frozen=True, slots=True)
class AnswerConflict:
    kind: str
    evidence: tuple[EvidenceSpan, ...]
    inherited_commitment_refs: tuple[str, ...] = ()

    def __post_init__(self):
        if (not isinstance(self.evidence, tuple) or not self.evidence
                or any(not isinstance(item, EvidenceSpan) or item.provenance != "explicit_human"
                       for item in self.evidence)
                or not isinstance(self.inherited_commitment_refs, tuple)
                or any(not isinstance(item, str) for item in self.inherited_commitment_refs)):
            raise ValueError("invalid_conflict_evidence")


@dataclass(frozen=True, slots=True)
class AnswerEvidence:
    commitments: tuple[AnswerCommitment, ...]
    conflicts: tuple[AnswerConflict, ...]
    not_resolved_by_continuation: tuple[EvidenceSpan, ...]


def extract_clarification_answer(answer, dimensions, base) -> AnswerEvidence:
    """Use active subdimensions as the sole context for pronouns like 'it'."""
    text = answer.text
    active = frozenset(dimensions)
    commitments, conflicts, unknown = [], [], []
    # Bounds match the answer record; individual evidence spans remain <=600.
    clauses = list(re.finditer(r"[^.;\n]+", text))
    if len(clauses) > 48:
        return AnswerEvidence((), (), (EvidenceSpan(text[:600], 0, min(600, len(text))),))
    pieces = []
    for clause in clauses:
        # Split coordinated assertions, but keep 'both creation and each ...'
        # and 'stores and checks' intact. Never discard a leading unknown word.
        separators = list(re.finditer(r"\s+and\s+(?=(?:do not|don't|interest|savingBalance)\b)", clause.group(), re.I))
        edges = [(0, separators[0].start())] if separators else [(0, len(clause.group()))]
        edges += [(item.end(), separators[index+1].start() if index+1 < len(separators) else len(clause.group()))
                  for index, item in enumerate(separators)]
        for part_start, part_end in edges:
            start, end = clause.start() + part_start, clause.start() + part_end
            while start < end and text[start] in " ,\t\r":
                start += 1
            while end > start and text[end-1] in " ,\t\r":
                end -= 1
            if end > start:
                pieces.append((start, end))
    for start, end in pieces:
        if end - start > 600:
            unknown.append(EvidenceSpan(text[start:start+600], start, start+600))
            continue
        span = EvidenceSpan(text[start:end], start, end)
        clause = re.sub(r"\s+", " ", span.source_text).strip()
        clause = re.sub(r"^and (?=(?:interest|savingBalance)\b)", "", clause, flags=re.I)
        clause = re.sub(r"^(?:for this exercise,? |actually |please )", "", clause, flags=re.I)
        found = []
        recognized = False

        def match(pattern):
            return re.fullmatch(pattern, clause, re.I)

        # Reversal is never implicit supersession. Check inherited commitments
        # before gap extraction, even though their dimensions are already fixed.
        for state in base.state_commitments:
            m = match(rf"(?:put {re.escape(state.state)} on|{re.escape(state.state)} (?:belongs|should belong)(?: only)? to) ([A-Za-z][A-Za-z0-9_]*)")
            if m:
                recognized = True
                if m[1] != state.owner:
                    conflicts.append(AnswerConflict("base_state_owner_conflict", (span,), (f"state:{state.state}:{state.owner}",)))
        for rel in base.relationships:
            m = match(rf"{re.escape(rel.child)} (?:extends|should extend) ([A-Za-z][A-Za-z0-9_]*)")
            prohibited = match(r"(?:do not|don't) use inheritance")
            if m or prohibited:
                recognized = True
                if prohibited or m[1] != rel.parent:
                    conflicts.append(AnswerConflict("base_inheritance_conflict", (span,), (f"extends:{rel.child}:{rel.parent}",)))
        if base.behavior_gates and match(r"(?:skip|bypass|disable) (?:password |credential )?verification|(?:savings (?:operations|behavior|functionality) (?:do not|does not|must not) require (?:password )?verification)"):
            recognized = True
            conflicts.append(AnswerConflict("base_behavior_gate_conflict", (span,), ("successful_password_verification",)))

        owner = r"(SavingAccount|BankAccount|user/account identity|application/session)"
        m = match(rf"(?:let )?{owner} (?:own|owns|stores/checks|stores and checks) (?:a )?(?:simple )?password(?: (?:only )?in memory)?")
        if not m:
            m = match(rf"(?:use )?(?:an? )?(?:in-memory |simple )?password (?:owned by|on) {owner}(?: (?:only )?in memory)?")
        if m:
            canonical_owner = next(item for item in VALUES["credential_ownership"] if item.casefold() == m[1].casefold())
            found += [("credential_ownership", canonical_owner), ("credential_source", "simple_password")]
            # The exercise-level password contract is semantic verification,
            # never a hashing, storage, visibility, or security-quality policy.
            if re.search(r"simple|memory|checks", clause, re.I):
                found += [("credential_verification_mechanism", "semantic_password_check")]
            if re.search(r"memory", clause, re.I):
                found += [("credential_persistence", "in_memory_only")]
        if match(r"(?:use )?(?:an? )?(?:simple )?in-memory password"):
            found += [("credential_source", "simple_password"), ("credential_persistence", "in_memory_only"), ("credential_verification_mechanism", "semantic_password_check")]
        m = match(r"credential owner: ([A-Za-z][A-Za-z0-9_]{0,79})")
        if m:
            found.append(("credential_ownership", m[1] if m[1] in VALUES["credential_ownership"] else "explicit_other:" + m[1]))
        if match(r"(?:keep it only in memory(?: for this exercise)?|in memory|no persistence|(?:do not|don't) persist (?:it|the password|credentials)|it does not need to persist across runs)"):
            found.append(("credential_persistence", "in_memory_only"))
        if match(r"(?:credentials|the password|it) (?:must |should )?persist(?:s)? across runs"):
            found.append(("credential_persistence", "persists_across_runs"))
        if match(r"(?:verify (?:it|the password) when a savings operation is requested|verify (?:the password )?(?:before|for) (?:each|every) savings operation|operation-gated)"):
            found += [("verification_lifecycle", "operation_gated"), ("credential_verification_mechanism", "semantic_password_check")]
        if match(r"(?:verify (?:it|the password) (?:only )?(?:at|on) (?:account )?creation|creation-gated)"):
            found += [("verification_lifecycle", "creation_gated"), ("credential_verification_mechanism", "semantic_password_check")]
        if match(r"verify (?:it|the password) at both creation and each savings operation"):
            found += [("verification_lifecycle", "both"), ("credential_verification_mechanism", "semantic_password_check")]
        if match(r"(?:savingBalance should receive money transferred from (?:the )?inherited balance|transfer (?:money )?from (?:the )?inherited balance(?: (?:to|into) savingBalance)?)"):
            found.append(("savings_funding_semantics", "transfer_from_inherited_balance"))
        if match(r"savingBalance (?:is|should be) independently funded"):
            found.append(("savings_funding_semantics", "independently_funded"))
        if match(r"interest (?:should apply|applies)(?: only)? to savingBalance"):
            found.append(("savings_interest_semantics", "interest_applies_to_saving_balance"))
        if match(r"(?:no interest behavior|(?:do not|don't) apply interest to savingBalance)"):
            found.append(("savings_interest_semantics", "no_interest_behavior"))
        if match(r"(?:don't|do not) worry about hashing") and re.search(r"(?:only a practice|this) exercise", text, re.I):
            found.append(("exercise_hashing_constraint", "hashing_out_of_scope_for_this_exercise"))
        if match(r"this is only a practice exercise"):
            recognized = True
        for dimension, value in found:
            if dimension in active or (dimension == "exercise_hashing_constraint" and active & set(VALUES) - {"savings_funding_semantics", "savings_interest_semantics"}):
                recognized = True
                commitments.append(AnswerCommitment(dimension, value, span, answer.answer_fingerprint))
        if not recognized:
            unknown.append(span)
    for dimension in VALUES:
        items = [item for item in commitments if item.dimension == dimension]
        if len({item.value for item in items}) > 1:
            conflicts.append(AnswerConflict("incompatible_answer_values", tuple(item.evidence for item in items)))
    # Repeated declarations of the same value do not create duplicate evidence.
    # Preserve the first exact supporting span; the complete answer stays bound.
    unique = {}
    for item in commitments:
        unique.setdefault((item.dimension, item.value), item)
    return AnswerEvidence(tuple(unique.values()), tuple(conflicts), tuple(unknown))
