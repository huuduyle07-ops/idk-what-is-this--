"""OOP.INTENT.DETECT.2: admit missing future-design contracts.

The detector consumes the preserved DESIGN.1 projection and one already
acquired CTX.OOP.1A source context.  It performs no discovery, source parsing,
provider call, authoring, or scope selection.  A difference between current
and desired structure is recorded as a transition fact, never as a defect.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
import time
from typing import TYPE_CHECKING, Any

from core.class_semantic_context import ClassSemanticContext
from core.oop_semantic_review import OOPIntentAlternative, OOPIntentGap
from core.proposed_design_intent import (
    ProposedDesignIntent,
    UNRESOLVED_DIMENSIONS,
    project_proposed_design_intent,
)
from core.task_contract import TaskContract

if TYPE_CHECKING:
    from core.design_intent_continuation import EffectiveProposedDesignIntent


PHASE_ID = "OOP.INTENT.DETECT.2"
SCHEMA_VERSION = "oop_intent_detect_2_v1"
DISPOSITIONS = frozenset({
    "deferred_implementation",
    "machine_resolvable",
    "human_owned_material",
    "irrelevant_to_current_transition",
})
STATUSES = frozenset({
    "clarification_required",
    "no_gap",
    "not_applicable",
    "design_conflict",
    "projection_bounded",
    "projection_unavailable",
    "projection_mismatch",
    "provenance_rejected",
    "source_bounded",
    "source_unavailable",
    "stale_source",
    "repository_mismatch",
})
AUTH_DIMENSIONS = frozenset({
    "credential_ownership",
    "credential_source",
    "credential_persistence",
    "credential_verification_mechanism",
    "verification_lifecycle",
})
SAVINGS_DIMENSIONS = frozenset({
    "savings_funding_semantics",
    "savings_interest_semantics",
})
SECONDARY_DIMENSIONS = frozenset({
    "verification_failure_behavior",
    "account_identity",
})
DEFERRED_DIMENSIONS = frozenset({
    "source_layout",
    "subclass_creation_lifecycle",
})
_SHA_LENGTH = 64
_AUTH_TOKENS = ("password", "credential", "auth", "verify", "login")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(value: Any) -> str:
    return sha256(_json(value).encode("utf-8")).hexdigest()


def _is_sha(value: Any) -> bool:
    return (isinstance(value, str) and len(value) == _SHA_LENGTH
            and all(char in "0123456789abcdef" for char in value))


def _ref(kind: str, value: Any) -> str:
    return f"{kind}:{_fingerprint(value)}"


@dataclass(frozen=True, slots=True)
class OOPIntentDimensionAssessment:
    dimension: str
    disposition: str
    reason: str
    evidence_refs: tuple[str, ...]
    material_choices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.dimension not in UNRESOLVED_DIMENSIONS:
            raise ValueError("unsupported future-design dimension")
        if self.disposition not in DISPOSITIONS:
            raise ValueError("unsupported future-design disposition")
        if (not isinstance(self.reason, str) or not self.reason
                or not isinstance(self.evidence_refs, tuple)
                or not 1 <= len(self.evidence_refs) <= 8
                or any(not isinstance(item, str) or not item for item in self.evidence_refs)):
            raise ValueError("invalid future-design assessment")
        if self.disposition == "human_owned_material":
            if len(self.material_choices) < 2:
                raise ValueError("material human dimensions require alternatives")
        elif self.material_choices:
            raise ValueError("nonhuman dimensions cannot carry human alternatives")


@dataclass(frozen=True, slots=True)
class OOPCurrentDesiredComparison:
    kind: str
    current: str
    desired: str
    evidence_refs: tuple[str, ...]
    current_provenance: str = "current_source_fact"
    desired_provenance: str = "explicit_human"
    is_defect: bool = False

    def __post_init__(self) -> None:
        if self.kind not in {"inheritance_transition", "state_transition", "authentication_transition"}:
            raise ValueError("unsupported current/desired comparison")
        if (not self.current or not self.desired or not self.evidence_refs
                or self.current_provenance != "current_source_fact"
                or self.desired_provenance != "explicit_human"
                or self.is_defect is not False):
            raise ValueError("invalid current/desired comparison")

    @property
    def description(self) -> str:
        return f"Current: {self.current} Desired: {self.desired}"


@dataclass(frozen=True, slots=True)
class OOPIntentDetection:
    status: str
    task_contract_fingerprint: str
    design_fingerprint: str
    repository_id: str
    source_fingerprint: str = ""
    source_path: str = ""
    class_identity: str = ""
    comparisons: tuple[OOPCurrentDesiredComparison, ...] = ()
    assessments: tuple[OOPIntentDimensionAssessment, ...] = ()
    possible_intent_gaps: tuple[OOPIntentGap, ...] = ()
    reasons: tuple[str, ...] = ()
    projection_validation_seconds: float = 0.0
    current_vs_desired_seconds: float = 0.0
    materiality_classification_seconds: float = 0.0
    gap_construction_seconds: float = 0.0
    total_seconds: float = 0.0
    schema_version: str = field(default=SCHEMA_VERSION, init=False)
    authority: str = field(default="read_only", init=False)
    write_authority: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)
    auto_apply: bool = field(default=False, init=False)
    repair_scope_authority: bool = field(default=False, init=False)
    author_calls: int = field(default=0, init=False)
    model_calls: int = field(default=0, init=False)
    repository_traversals: int = field(default=0, init=False)
    patch_candidate: None = field(default=None, init=False)
    patch: str = field(default="", init=False)

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError("unsupported OOP intent detection status")
        if (not isinstance(self.comparisons, tuple)
                or any(not isinstance(item, OOPCurrentDesiredComparison) for item in self.comparisons)
                or not isinstance(self.assessments, tuple)
                or any(not isinstance(item, OOPIntentDimensionAssessment) for item in self.assessments)
                or not isinstance(self.possible_intent_gaps, tuple)
                or len(self.possible_intent_gaps) > 1
                or any(not isinstance(item, OOPIntentGap) for item in self.possible_intent_gaps)):
            raise ValueError("invalid OOP intent detection collections")
        if ((self.status == "clarification_required") != bool(self.possible_intent_gaps)):
            raise ValueError("clarification status and gap disagree")
        if any(value < 0.0 for value in (
            self.projection_validation_seconds,
            self.current_vs_desired_seconds,
            self.materiality_classification_seconds,
            self.gap_construction_seconds,
            self.total_seconds,
        )):
            raise ValueError("detector timings must be nonnegative")

    @property
    def gap(self) -> OOPIntentGap | None:
        return self.possible_intent_gaps[0] if self.possible_intent_gaps else None

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["phase_id"] = PHASE_ID
        value["disposition_vocabulary"] = sorted(DISPOSITIONS)
        return json.loads(_json(value))

    def to_json(self) -> str:
        return _json(self.as_dict())


def _commitment_provenance_valid(design: ProposedDesignIntent) -> bool:
    explicit = (*design.relationships, *design.state_commitments,
                *design.behavior_gates, *design.explicit_absences)
    if any(item.evidence.provenance != "explicit_human" for item in explicit):
        return False
    if any(item.provenance != "inferred_semantic_interpretation"
           for item in design.unresolved_dimensions):
        return False
    return all(item.base_exclusion_provenance in (None, "inferred_semantic_interpretation")
               for item in design.state_commitments)


def _auth_source_resolution(
    context: ClassSemanticContext, *, desired_owner: str | None,
) -> tuple[bool, frozenset[str]]:
    """Return a narrow surface fact and only dimensions signatures establish.

    A password-shaped field can establish its *current* owner, but it cannot
    establish persistence, verification lifecycle, or every other future
    authentication decision.  Keeping those facts separate prevents one token
    from silently suppressing the whole human contract.
    """
    credential_fields = tuple(item for item in context.fields if any(
        token in f"{item.name} {item.declared_type}".casefold()
        for token in _AUTH_TOKENS))
    credential_parameters = tuple(parameter
        for item in (*context.methods, *context.explicit_constructors)
        for parameter in item.parameters
        if any(token in f"{parameter.name} {parameter.declared_type}".casefold()
               for token in _AUTH_TOKENS))
    verification_methods = tuple(item for item in context.methods if any(
        token in item.name.casefold()
        for token in ("verify", "authenticate", "login", "checkpassword")))
    resolved: set[str] = set()
    owner_matches = bool(context.class_identity and desired_owner
                         and context.class_identity.name == desired_owner)
    if credential_fields and owner_matches:
        resolved.add("credential_ownership")
    if credential_parameters and owner_matches:
        resolved.add("credential_source")
    return bool(credential_fields or credential_parameters or verification_methods), frozenset(resolved)


def _savings_source_resolution(
    context: ClassSemanticContext, state_names: set[str],
) -> tuple[bool, frozenset[str]]:
    """Resolve only funding/interest facts structurally demonstrated here."""
    present = {item.name for item in context.fields} & state_names
    if not present:
        return False, frozenset()
    by_method: dict[str, list[Any]] = {}
    for relation in context.relations:
        by_method.setdefault(relation.method_name, []).append(relation)
    # CTX.OOP relations establish access, not transfer direction or arithmetic.
    # The surface is useful current-state evidence but resolves neither human
    # future contract without a richer already-acquired semantic fact.
    return bool(by_method), frozenset()


def _known_commitment_text(design: ProposedDesignIntent) -> str:
    known: list[str] = []
    if design.relationships:
        item = design.relationships[0]
        known.append(f"{item.child} extends {item.parent}")
    if design.state_commitments:
        item = design.state_commitments[0]
        known.append(f"{item.state} belongs only to {item.owner}")
    if design.behavior_gates:
        item = design.behavior_gates[0]
        condition = item.condition.replace("_", " ")
        known.append(f"{item.gated_behavior} requires {condition}")
    if not known:
        return ""
    if len(known) == 1:
        return known[0]
    return ", ".join(known[:-1]) + ", and " + known[-1]


def _question_and_alternatives(
    design: ProposedDesignIntent,
    *, dimensions: frozenset[str],
) -> tuple[str, tuple[OOPIntentAlternative, ...]]:
    prefix = _known_commitment_text(design)
    opening = f"You've already specified that {prefix}. " if prefix else ""
    auth_dimensions = dimensions & AUTH_DIMENSIONS
    savings_dimensions = dimensions & SAVINGS_DIMENSIONS
    auth = bool(auth_dimensions)
    savings = bool(savings_dimensions)

    def auth_options(limit: int = 3) -> tuple[OOPIntentAlternative, ...]:
        if "credential_persistence" in auth_dimensions:
            values = (
                OOPIntentAlternative(
                    "authentication_in_memory",
                    "Use a simple in-memory credential for this exercise."),
                OOPIntentAlternative(
                    "authentication_persistent",
                    "Use a credential contract that persists across runs without selecting storage technology."),
                OOPIntentAlternative(
                    "other_authentication_contract",
                    "Describe another intended credential persistence and verification contract."),
            )
        elif auth_dimensions & {"credential_ownership", "credential_source"}:
            values = (
                OOPIntentAlternative(
                    "saving_account_credential",
                    "SavingAccount owns or receives the credential for this exercise."),
                OOPIntentAlternative(
                    "identity_owned_credential",
                    "A user or account identity owns and supplies the credential."),
                OOPIntentAlternative(
                    "other_credential_contract",
                    "Describe another intended credential owner or source."),
            )
        elif "verification_lifecycle" in auth_dimensions:
            values = (
                OOPIntentAlternative(
                    "verification_per_operation",
                    "Verify each gated savings operation."),
                OOPIntentAlternative(
                    "verification_for_interaction",
                    "Verify once for a broader authenticated interaction."),
                OOPIntentAlternative(
                    "other_verification_lifecycle",
                    "Describe another intended verification lifecycle."),
            )
        else:
            values = (
                OOPIntentAlternative(
                    "direct_credential_verification",
                    "Verify the supplied credential directly against the intended owner."),
                OOPIntentAlternative(
                    "delegated_credential_verification",
                    "Have the owning identity decide whether the supplied credential is valid."),
                OOPIntentAlternative(
                    "other_verification_contract",
                    "Describe another intended verification mechanism."),
            )
        return values[:limit]

    def savings_options(limit: int = 4) -> tuple[OOPIntentAlternative, ...]:
        if "savings_funding_semantics" in savings_dimensions:
            values = [
                OOPIntentAlternative(
                    "transfer_from_inherited_balance",
                    "Transfer money from inherited balance into savingBalance."),
                OOPIntentAlternative(
                    "independently_funded",
                    "Fund savingBalance independently from inherited balance."),
            ]
            if "savings_interest_semantics" in savings_dimensions:
                values.append(OOPIntentAlternative(
                    "savings_principal_with_interest",
                    "Treat savingBalance as savings principal and apply saving interest to it."))
            values.append(OOPIntentAlternative(
                "other_savings_contract",
                "Describe another intended savings funding behavior."))
        else:
            values = [
                OOPIntentAlternative(
                    "interest_on_saving_balance",
                    "Apply saving interest to savingBalance."),
                OOPIntentAlternative(
                    "no_implicit_interest",
                    "Do not apply interest unless a separate savings operation requests it."),
                OOPIntentAlternative(
                    "other_interest_contract",
                    "Describe another intended interest behavior."),
            ]
        return tuple(values[:limit])

    if auth and savings:
        auth_needs = []
        if auth_dimensions & {"credential_ownership", "credential_source"}:
            auth_needs.append("who owns or supplies the credential")
        if "credential_persistence" in auth_dimensions:
            auth_needs.append("whether it persists")
        if "credential_verification_mechanism" in auth_dimensions:
            auth_needs.append("how it is verified")
        if "verification_lifecycle" in auth_dimensions:
            auth_needs.append("what operation or lifecycle verification gates")
        savings_needs = []
        if "savings_funding_semantics" in savings_dimensions:
            savings_needs.append("how savingBalance is funded")
        if "savings_interest_semantics" in savings_dimensions:
            savings_needs.append("how interest applies")
        question = (
            opening
            + "For this exercise, how should the remaining verification and savings behavior work? "
              + "Please specify " + ", ".join(auth_needs + savings_needs) + "."
        )
        alternatives = auth_options(2) + savings_options(2)
    elif auth:
        needs = []
        if auth_dimensions & {"credential_ownership", "credential_source"}:
            needs.append("the credential owner/source")
        if "credential_persistence" in auth_dimensions:
            needs.append("whether it persists")
        if "credential_verification_mechanism" in auth_dimensions:
            needs.append("how it is verified")
        if "verification_lifecycle" in auth_dimensions:
            needs.append("whether verification gates each savings operation or a broader lifecycle")
        question = (
            opening
            + "For this exercise, how should the remaining verification contract work? Please specify "
              + ", ".join(needs) + "."
        )
        alternatives = auth_options()
    else:
        needs = []
        if "savings_funding_semantics" in savings_dimensions:
            needs.append("how savingBalance is funded")
        if "savings_interest_semantics" in savings_dimensions:
            needs.append("whether saving behavior applies interest to it")
        question = (
            opening
            + "For this exercise, how should the remaining savings behavior work? Please specify "
              + " and ".join(needs) + "."
        )
        alternatives = savings_options()
    return question, alternatives


def detect_missing_future_design_contract(
    *,
    task_contract: TaskContract,
    design_intent: ProposedDesignIntent | EffectiveProposedDesignIntent,
    current_context: ClassSemanticContext | None,
    current_source: bytes,
    repository_id: str,
    stored_gap: Any = None,
    stored_answer: Any = None,
    repo_path: str = "",
) -> OOPIntentDetection:
    """Return one typed future-design gap only when material intent is human-owned."""
    from core.design_intent_continuation import (
        EffectiveProposedDesignIntent,
        validate_effective_design,
    )

    started = time.perf_counter()
    projection_started = time.perf_counter()
    task_fp = ""
    design_fp = ""
    source_fp = getattr(current_context, "source_fingerprint", "") if current_context else ""
    source_path = getattr(current_context, "file", "") if current_context else ""
    class_identity = ""
    if current_context and current_context.class_identity:
        class_identity = current_context.class_identity.qualified_name

    def outcome(
        status: str,
        *,
        reasons: tuple[str, ...] = (),
        comparisons: tuple[OOPCurrentDesiredComparison, ...] = (),
        assessments: tuple[OOPIntentDimensionAssessment, ...] = (),
        gaps: tuple[OOPIntentGap, ...] = (),
        projection_seconds: float | None = None,
        comparison_seconds: float = 0.0,
        classification_seconds: float = 0.0,
        gap_seconds: float = 0.0,
    ) -> OOPIntentDetection:
        return OOPIntentDetection(
            status=status,
            task_contract_fingerprint=task_fp,
            design_fingerprint=design_fp,
            repository_id=repository_id if isinstance(repository_id, str) else "",
            source_fingerprint=source_fp,
            source_path=source_path,
            class_identity=class_identity,
            comparisons=comparisons,
            assessments=assessments,
            possible_intent_gaps=gaps,
            reasons=reasons,
            projection_validation_seconds=(time.perf_counter() - projection_started
                if projection_seconds is None else projection_seconds),
            current_vs_desired_seconds=comparison_seconds,
            materiality_classification_seconds=classification_seconds,
            gap_construction_seconds=gap_seconds,
            total_seconds=time.perf_counter() - started,
        )

    effective = isinstance(design_intent, EffectiveProposedDesignIntent)
    base_design = design_intent.base if effective else design_intent
    if not isinstance(task_contract, TaskContract) or not isinstance(base_design, ProposedDesignIntent):
        return outcome("projection_unavailable", reasons=("typed_projection_required",))
    task_fp = _fingerprint(task_contract.as_dict())
    design_fp = design_intent.fingerprint
    baseline = project_proposed_design_intent(task_contract)
    bindings_match = (
        base_design.task_contract_fingerprint == task_fp
        and base_design.raw_request_fingerprint == task_contract.raw_request.sha256
        and base_design.semantic_interpretation_fingerprint
            == baseline.semantic_interpretation_fingerprint
    )
    if not task_contract.preservation.passed or not task_contract.routing_allowed:
        return outcome("projection_unavailable", reasons=("requirement_preservation_failed",))
    if not bindings_match:
        return outcome("projection_mismatch", reasons=("projection_fingerprint_mismatch",))
    if not _commitment_provenance_valid(base_design):
        return outcome("provenance_rejected", reasons=("invalid_design_provenance",))
    if base_design.as_dict() != baseline.as_dict():
        return outcome("projection_mismatch", reasons=("projection_payload_mismatch",))
    if effective:
        if stored_gap is None or stored_answer is None or not repo_path:
            return outcome("projection_mismatch", reasons=("continuation_external_bindings_required",))
        try:
            validate_effective_design(
                task_contract=task_contract,
                design_intent=design_intent,
                current_context=current_context,
                current_source=current_source,
                repo_path=repo_path,
                stored_gap=stored_gap,
                stored_answer=stored_answer,
            )
        except ValueError as exc:
            reason = str(exc)
            status = ("stale_source" if reason in {"reacquisition_required", "stale_source"}
                      else "design_conflict" if reason == "continuation_conflict"
                      else "projection_mismatch")
            return outcome(status, reasons=(reason,))
    if design_intent.status == "conflict":
        return outcome("design_conflict", reasons=("design_commitments_conflict",))
    if design_intent.status == "bounded":
        return outcome("projection_bounded", reasons=("design_projection_bounded",))
    if design_intent.status == "unavailable":
        no_design = (not design_intent.relationships and not design_intent.state_commitments
                     and not design_intent.behavior_gates and not design_intent.unresolved_dimensions)
        return outcome("not_applicable" if no_design else "projection_unavailable",
                       reasons=("no_future_design_commitment" if no_design
                                else "design_projection_unavailable",))
    if design_intent.status == "unresolved":
        return outcome("not_applicable", reasons=("suggestion_is_not_a_commitment",))
    projection_seconds = time.perf_counter() - projection_started

    comparison_started = time.perf_counter()
    if current_context is None or current_context.status not in {"complete", "bounded"}:
        return outcome("source_unavailable", reasons=("exact_current_context_required",),
                       projection_seconds=projection_seconds)
    if current_context.status == "bounded" or current_context.overflow:
        return outcome("source_bounded", reasons=("current_context_bounded",),
                       projection_seconds=projection_seconds)
    if (not isinstance(current_source, bytes)
            or sha256(current_source).hexdigest() != current_context.source_fingerprint):
        return outcome("stale_source", reasons=("source_fingerprint_mismatch",),
                       projection_seconds=projection_seconds)
    if (not isinstance(repository_id, str) or not repository_id
            or current_context.repository_id != repository_id):
        return outcome("repository_mismatch", reasons=("repository_identity_mismatch",),
                       projection_seconds=projection_seconds)
    if current_context.class_identity is None or current_context.target is None:
        return outcome("source_unavailable", reasons=("current_class_identity_unavailable",),
                       projection_seconds=projection_seconds)

    source_ref = _ref("current_source_fact", current_context.as_dict())
    relationship_refs = {
        id(item): _ref("design_commitment", item.as_dict()) for item in design_intent.relationships
    }
    state_refs = {
        id(item): _ref("design_commitment", item.as_dict()) for item in design_intent.state_commitments
    }
    gate_refs = {
        id(item): _ref("design_commitment", item.as_dict()) for item in design_intent.behavior_gates
    }
    comparisons: list[OOPCurrentDesiredComparison] = []
    current_class = current_context.class_identity
    relevant_relationships = [item for item in design_intent.relationships
                              if current_class.name in {item.child, item.parent}]
    for item in relevant_relationships[:1]:
        already_present = (current_class.name == item.child and current_class.extends == item.parent)
        comparisons.append(OOPCurrentDesiredComparison(
            kind="inheritance_transition",
            current=(f"the acquired {current_class.name} declaration already extends {item.parent}"
                     if already_present else
                     f"the acquired context is {current_class.name}; it does not establish a repository-wide "
                     f"absence for {item.child}"),
            desired=f"{item.child} extends {item.parent}",
            evidence_refs=(source_ref, relationship_refs[id(item)]),
        ))
    current_fields = {item.name for item in current_context.fields}
    savings_states = [item for item in design_intent.state_commitments
                      if item.state_role == "savings_state"]
    for item in savings_states[:1]:
        present = item.state in current_fields
        comparisons.append(OOPCurrentDesiredComparison(
            kind="state_transition",
            current=(f"{item.state} is declared on the acquired {current_class.name} context"
                     if present else
                     f"{item.state} is not declared on the acquired {current_class.name} context"),
            desired=f"{item.state} belongs only to {item.owner}",
            evidence_refs=(source_ref, state_refs[id(item)]),
        ))
    auth_gates = [item for item in design_intent.behavior_gates
                  if item.condition in {"successful_password_verification",
                                        "successful_credential_verification"}]
    desired_auth_owner = savings_states[0].owner if savings_states else (
        relevant_relationships[0].child if relevant_relationships else None)
    auth_present, auth_source_dimensions = _auth_source_resolution(
        current_context, desired_owner=desired_auth_owner)
    for item in auth_gates[:1]:
        comparisons.append(OOPCurrentDesiredComparison(
            kind="authentication_transition",
            current=("the acquired class has authentication-shaped fields, parameters, or callables that "
                     "must be resolved from exact source" if auth_present else
                     "the acquired class has no password-, credential-, authentication-, verification-, "
                     "or login-named field, parameter, or callable"),
            desired=f"{item.gated_behavior} requires {item.condition.replace('_', ' ')}",
            evidence_refs=(source_ref, gate_refs[id(item)]),
        ))
    comparison_seconds = time.perf_counter() - comparison_started

    classification_started = time.perf_counter()
    dimension_ref = _ref("unresolved_dimensions",
                         [item.as_dict() for item in design_intent.unresolved_dimensions])
    _savings_present, savings_source_dimensions = _savings_source_resolution(
        current_context, {item.state for item in savings_states})
    assessments: list[OOPIntentDimensionAssessment] = []
    relevant_projection_omission = False
    for item in design_intent.unresolved_dimensions:
        refs = tuple(dict.fromkeys((*item.basis, dimension_ref)))[:8]
        if item.dimension in DEFERRED_DIMENSIONS:
            disposition = "deferred_implementation"
            reason = ("source_layout_is_later_implementation_planning"
                      if item.dimension == "source_layout"
                      else "subclass_creation_is_later_implementation_planning")
            choices: tuple[str, ...] = ()
        elif item.dimension in SECONDARY_DIMENSIONS:
            disposition = "irrelevant_to_current_transition"
            reason = "secondary_behavior_does_not_independently_block_this_transition"
            choices = ()
        elif item.status == "not_resolved_by_projection":
            disposition = "machine_resolvable"
            reason = "projection_must_type_preserved_evidence_before_human_admission"
            choices = ()
            if item.dimension in AUTH_DIMENSIONS | SAVINGS_DIMENSIONS:
                relevant_projection_omission = True
        elif item.dimension in AUTH_DIMENSIONS:
            if not auth_gates:
                disposition = "irrelevant_to_current_transition"
                reason = "no_explicit_authentication_behavior_gate"
                choices = ()
            elif item.dimension in auth_source_dimensions:
                disposition = "machine_resolvable"
                reason = "exact_current_authentication_signature_resolves_this_dimension"
                choices = ()
            else:
                disposition = "human_owned_material"
                reason = "credential_model_changes_owned_state_persistence_and_gate_lifecycle"
                choices = ("SavingAccount-owned in-memory credential",
                           "persistent user/account-owned credential")
        elif item.dimension in SAVINGS_DIMENSIONS:
            if not savings_states or not auth_gates:
                disposition = "irrelevant_to_current_transition"
                reason = "no_explicit_savings_state_and_behavior_commitment"
                choices = ()
            elif item.dimension in savings_source_dimensions:
                disposition = "machine_resolvable"
                reason = "exact_current_field_relations_resolve_this_dimension"
                choices = ()
            else:
                disposition = "human_owned_material"
                reason = "savings_choices_change_balance_mutation_and_interest_state"
                choices = ("transfer from inherited balance",
                           "independent funding of savingBalance",
                           "interest applied to savingBalance")
        else:
            disposition = "irrelevant_to_current_transition"
            reason = "dimension_is_not_required_for_current_transition"
            choices = ()
        assessments.append(OOPIntentDimensionAssessment(
            item.dimension, disposition, reason, refs, choices))
    classification_seconds = time.perf_counter() - classification_started
    frozen_assessments = tuple(assessments)
    frozen_comparisons = tuple(comparisons)
    if relevant_projection_omission:
        return outcome(
            "projection_bounded",
            reasons=("relevant_design_evidence_not_resolved_by_projection",),
            comparisons=frozen_comparisons,
            assessments=frozen_assessments,
            projection_seconds=projection_seconds,
            comparison_seconds=comparison_seconds,
            classification_seconds=classification_seconds,
        )

    gap_started = time.perf_counter()
    human = [item for item in assessments if item.disposition == "human_owned_material"]
    if not human:
        gap_seconds = time.perf_counter() - gap_started
        return outcome(
            "no_gap",
            reasons=("no_material_human_owned_dimension",),
            comparisons=frozen_comparisons,
            assessments=frozen_assessments,
            projection_seconds=projection_seconds,
            comparison_seconds=comparison_seconds,
            classification_seconds=classification_seconds,
            gap_seconds=gap_seconds,
        )
    question, alternatives = _question_and_alternatives(
        design_intent, dimensions=frozenset(item.dimension for item in human))
    commitment_refs = [*relationship_refs.values(), *state_refs.values(), *gate_refs.values()]
    evidence_refs = tuple(dict.fromkeys((
        _ref("task_contract", task_contract.as_dict()),
        _ref("design_projection", design_intent.as_dict()),
        source_ref,
        _ref("repository_identity", repository_id),
        *commitment_refs,
        dimension_ref,
    )))[:8]
    gap = OOPIntentGap(
        dimension="future_design_contract",
        question=question,
        alternatives=alternatives,
        evidence_refs=evidence_refs,
        source_fingerprint=current_context.source_fingerprint,
        task_fingerprint=task_contract.raw_request.sha256,
        subdimensions=tuple(item.dimension for item in human),
        unresolved_dimension_refs=tuple(
            _ref("unresolved_dimension", next(
                dimension.as_dict() for dimension in design_intent.unresolved_dimensions
                if dimension.dimension == item.dimension))
            for item in human
        ),
        design_fingerprint=design_intent.fingerprint,
        task_contract_fingerprint=task_fp,
        repository_id=repository_id,
    )
    gap_seconds = time.perf_counter() - gap_started
    return outcome(
        "clarification_required",
        comparisons=frozen_comparisons,
        assessments=frozen_assessments,
        gaps=(gap,),
        projection_seconds=projection_seconds,
        comparison_seconds=comparison_seconds,
        classification_seconds=classification_seconds,
        gap_seconds=gap_seconds,
    )
