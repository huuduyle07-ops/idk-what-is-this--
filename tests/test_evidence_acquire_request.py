"""ACQUIRE.1 — bounded evidence acquisition request contract tests.

WAITER.2 said what ingredients the kitchen needs.  ACQUIRE.1 writes the shopping
list — and goes to no shop.

Four things are proved here.

The **request matrix**: an explanation asks only for the material it already
holds; a bounded edit asks for a bounded repository request and carries the
README.md the user wrote as a target anchor rather than a discovery; a broad
investigation and the DeepSeek Harness dogfood ask for implementation,
interfaces, configuration and architecture description first, validation second,
history not at all yet, and generated or snapshot material never.

The **ceiling**: every active request is finite, the ladder from existing
context through bounded to reconnaissance is monotone, deferred material has a
budget of zero, and there is no field anywhere in the schema in which "all
repository files" could be written.  This is the 6,087-file dogfood, made
unrepresentable rather than merely discouraged.

The **closure**: a request may refine an evidence requirement and may not widen
one; every active requirement has exactly one request carrying it at its own
tier; the workflow is copied and never chosen; and a tampered upstream record
produces no requests at all.

The **boundary**: no contract names a discovered path, a query, an address, a
provider or a compute choice; no contract grants any authority, in any status,
including ``ready``.
"""

from __future__ import annotations

import dataclasses
import json

import pytest

from core.acquisition_policy import (
    ACTIVE_TIERS_ORDER,
    EVIDENCE_CLASS_ACQUISITION_CLASSES,
    SOURCE_CLASSES_BY_ROLE,
    AcquisitionPolicy,
    budget_profile_for,
    check_bounded_reconnaissance,
    check_deferred_source_coverage,
    check_request_monotonicity,
    check_requirement_coverage,
    derive_acquisition_policy,
    preserved_target_anchors,
    repository_reach,
    source_classes_for,
    unmappable_roles,
)
from core.acquisition_request import (
    ACQUIRE_EXPLICIT_TARGET_ANCHOR_PRESERVED,
    ACQUIRE_UNRELATED_VALIDATION_DEFERRED,
    ACQUISITION_INCONSISTENCIES,
    ACQUISITION_REASONS,
    ACQUISITION_REASON_DESCRIPTIONS,
    ACQUISITION_SOURCE_CLASSES,
    ACQUISITION_STATUSES,
    BUDGET_BOUNDED,
    BUDGET_EXISTING_CONTEXT,
    BUDGET_EXTERNAL_BOUNDED,
    BUDGET_NONE,
    BUDGET_PROFILES,
    BUDGET_PROFILE_LIMITS,
    BUDGET_RECONNAISSANCE,
    BUDGET_SECONDARY_VERIFICATION,
    FRESHNESS_CURRENT,
    FRESHNESS_HISTORICAL,
    FRESHNESS_NOT_APPLICABLE,
    FRESHNESS_REQUIREMENTS,
    INCONSISTENT_ACQUISITION_WIDENED,
    INCONSISTENT_EVIDENCE_NOT_SPECIFIED,
    INCONSISTENT_REQUIRED_EVIDENCE_DROPPED,
    INCONSISTENT_SOURCE_FINGERPRINT_MISMATCH,
    INCONSISTENT_WORKFLOW_MISMATCH,
    MAX_CANDIDATES_CEILING,
    MAX_INITIAL_SOURCES_CEILING,
    MAX_PER_SOURCE_BYTES_CEILING,
    MAX_TOTAL_BYTES_CEILING,
    NEVER_REQUESTED_SOURCE_CLASSES,
    REQUESTABLE_SOURCE_CLASSES,
    REQUEST_SCOPES,
    REQUEST_SCOPE_BOUNDED_REPOSITORY,
    REQUEST_SCOPE_BROAD_REPOSITORY_RECONNAISSANCE,
    REQUEST_SCOPE_EXISTING_CONTEXT,
    REQUEST_SCOPE_EXTERNAL_INFORMATION,
    SOURCE_CLASS_AUTHORITATIVE_ARCHITECTURE_DOC,
    SOURCE_CLASS_AUTHORITATIVE_EXTERNAL_SOURCE,
    SOURCE_CLASS_CONFIGURATION,
    SOURCE_CLASS_DEPENDENCY_MANIFEST,
    SOURCE_CLASS_DUPLICATE_RENDERING,
    SOURCE_CLASS_GENERATED_ARTIFACT,
    SOURCE_CLASS_HISTORICAL_DESIGN_MATERIAL,
    SOURCE_CLASS_INTERFACE_DEFINITION,
    SOURCE_CLASS_PLUGIN_OR_REGISTRATION_SURFACE,
    SOURCE_CLASS_RUNTIME_IMPLEMENTATION,
    SOURCE_CLASS_SNAPSHOT,
    SOURCE_CLASS_SUPPLIED_CONTEXT,
    SOURCE_CLASS_SURROUNDING_IMPLEMENTATION,
    SOURCE_CLASS_TEMPORARY_ARTIFACT,
    SOURCE_CLASS_VALIDATION_TEST,
    STATUS_INCONSISTENT_INPUT,
    STATUS_NOT_EVIDENCE_READY,
    STATUS_READY,
    AcquisitionBudget,
    AcquisitionRequest,
    AcquisitionRequestContract,
    SourceExclusion,
    TargetAnchor,
    acquisition_authority,
    acquisition_guardrails,
)
from core.evidence_acquire_request import (
    canonical_acquisition_fingerprint,
    canonical_acquisition_shape,
    derive_acquisition_requests,
    render_acquisition_contract_json,
)
from core.evidence_requirements import (
    DOMAIN_DIRECT_CONTEXT,
    DOMAIN_EXTERNAL_INFORMATION,
    DOMAIN_HISTORICAL_CONTEXT,
    DOMAIN_REPOSITORY,
    DOMAIN_VALIDATION_ARTIFACTS,
    EVIDENCE_DIRECT_CONTEXT_FROM_TASK,
    EVIDENCE_DOMAINS,
    EVIDENCE_REPOSITORY_REQUIRED,
    EVIDENCE_ROLES,
    ROLE_ARCHITECTURE_DESCRIPTION,
    ROLE_CONFIGURATION_AUTHORITY,
    ROLE_CURRENT_EXTERNAL_AUTHORITY,
    ROLE_HISTORICAL_CONTEXT,
    ROLE_HYPOTHESIS_SUPPORT,
    ROLE_IMPLEMENTATION_AUTHORITY,
    ROLE_INTERFACE_CONTRACT,
    ROLE_SUPPLIED_MATERIAL,
    ROLE_VALIDATION_EVIDENCE,
    SCOPE_BOUNDED_REPOSITORY,
    SCOPE_BROAD_REPOSITORY_RECONNAISSANCE,
    SCOPE_DIRECT_CONTEXT_ONLY,
    SCOPE_EXTERNAL_ONLY,
    SCOPE_MIXED_SOURCES,
    TIER_DEFERRED,
    TIER_EXCLUDED_INITIALLY,
    TIER_REQUIRED_PRIMARY,
    TIER_REQUIRED_SECONDARY,
    EvidenceRequirement,
    EvidenceRequirementContract,
)
from core.execution_waiter import (
    WORKFLOW_CHAT,
    WORKFLOW_COMMANDER,
    WORKFLOW_INSTANT_RUN,
    WORKFLOW_PROJECT_EVOLUTION,
    route_execution_workflow,
)
from core.input_completion import complete_intake_from_semantic_outcome
from core.intake_completion import STATE_READY
from core.semantic_waiter_adapter import (
    ScriptedSemanticModelClient,
    SemanticWaiterModelAdapter,
)
from core.semantic_waiter_runner import understand_request_semantically
from core.task_shape import (
    DECLARATION_SOURCE_HUMAN_DECLARED_WORKFLOW_INTENT,
    ProjectEvolutionRequest,
)
from core.waiter_evidence import derive_evidence_requirements


# ══ Fixtures ══════════════════════════════════════════════════════════════════

DOGFOOD_PROMPT = """Analyze DeepSeek Harness against C.A.T.T.U.S using the following framework:

- Equivalent
- DeepSeek stronger
- C.A.T.T.U.S stronger
- Orthogonal
- Not worth adopting
"""

BROAD_REPOSITORY = {
    "multi_stage": True,
    "repository_inspection_required": True,
    "local_repository_required": True,
}

BOUNDED_REPOSITORY = {
    "repository_inspection_required": True,
    "local_repository_required": True,
}


def _handoff(prompt: str, payload: dict):
    """A handoff-ready ``(contract, decision)`` pair from INPUT.1 through 3."""
    adapter = SemanticWaiterModelAdapter(
        ScriptedSemanticModelClient([json.dumps(payload)])
    )
    outcome = understand_request_semantically(prompt, adapter=adapter)
    completion = complete_intake_from_semantic_outcome(outcome)
    assert completion.state == STATE_READY, completion.decision.reasons
    return outcome.contract, completion.decision


def _upstream(prompt: str, payload: dict, **kwargs):
    """Everything ACQUIRE.1 consumes, for one order."""
    contract, completion = _handoff(prompt, payload)
    decision = route_execution_workflow(contract, completion, **kwargs)
    evidence = derive_evidence_requirements(decision, contract, completion)
    return evidence, decision, contract, completion


def _requests(prompt: str, payload: dict, **kwargs) -> AcquisitionRequestContract:
    return derive_acquisition_requests(*_upstream(prompt, payload, **kwargs))


def _dogfood_interpretation(execution: dict) -> dict:
    return {
        "task": {"type": "comparative_analysis", "provenance": "inferred"},
        "subjects": [
            {"value": "DeepSeek Harness", "provenance": "explicit"},
            {"value": "C.A.T.T.U.S", "provenance": "explicit"},
        ],
        "relationships": [
            {
                "type": "comparison",
                "subjects": ["DeepSeek Harness", "C.A.T.T.U.S"],
                "provenance": "explicit",
            }
        ],
        "user_supplied_framework": {
            "type": "framework",
            "values": [
                "Equivalent",
                "DeepSeek stronger",
                "C.A.T.T.U.S stronger",
                "Orthogonal",
                "Not worth adopting",
            ],
            "provenance": "explicit",
            "ordered": True,
        },
        "constraints": [
            {
                "kind": "framework_reference",
                "text": (
                    "Analyze DeepSeek Harness against C.A.T.T.U.S using the following "
                    "framework:"
                ),
                "provenance": "explicit",
            }
        ],
        "execution_requirements": execution,
    }


def _structure_only(contract) -> str:
    """The record itself, without the English that explains it.

    The prose reason descriptions are part of the contract's explainability and
    are written in ordinary words — one of them says the phrase "no engine, host
    or query is named", which is exactly the sentence a naive token scan would
    trip over.  A boundary test is about the *structure*: the requests, the
    exclusions and the ceilings.
    """
    payload = _without_authority(contract.as_dict())
    payload.pop("reasons", None)
    payload.pop("note", None)
    return json.dumps(payload, ensure_ascii=False).lower()


def _without_authority(value):
    if isinstance(value, dict):
        return {
            key: _without_authority(item)
            for key, item in value.items()
            if key not in ("authority", "guardrails")
        }
    if isinstance(value, list):
        return [_without_authority(item) for item in value]
    return value


_EXPLANATION = (
    "Explain the Bellman equation.",
    {"task": {"type": "question", "provenance": "inferred"}},
)

_PASTED_COMPARISON = (
    "Compare these two pasted functions for readability:\n\n"
    "`def a(x): return x + 1`\n\n"
    "`def b(x): return sum([x, 1])`\n"
)

_PASTED_COMPARISON_INTERPRETATION = {
    "task": {"type": "comparative_analysis", "provenance": "inferred"},
    "subjects": [
        {"value": "def a(x): return x + 1", "provenance": "explicit"},
        {"value": "def b(x): return sum([x, 1])", "provenance": "explicit"},
    ],
    "relationships": [
        {
            "type": "comparison",
            "subjects": ["def a(x): return x + 1", "def b(x): return sum([x, 1])"],
            "provenance": "inferred",
            "confidence": 0.9,
        }
    ],
    "execution_requirements": {},
}

_README_EDIT = (
    "Fix the typo 'teh' to 'the' in README.md.",
    {
        "task": {"type": "implementation", "provenance": "inferred"},
        "subjects": [{"value": "README.md", "provenance": "explicit"}],
        "execution_requirements": BOUNDED_REPOSITORY,
    },
)

_ONE_FILE_IMPLEMENTATION = (
    "Implement a slugify helper in core/text_utils.py.",
    {
        "task": {"type": "implementation", "provenance": "inferred"},
        "subjects": [{"value": "core/text_utils.py", "provenance": "explicit"}],
        "execution_requirements": BOUNDED_REPOSITORY,
    },
)

_BROAD_DEBUGGING = (
    "Investigate why project indexing takes more than an hour, and determine the "
    "causes across core/indexer.py and the rest of the indexing pipeline.",
    {
        "task": {"type": "debugging", "provenance": "inferred"},
        "subjects": [{"value": "core/indexer.py", "provenance": "explicit"}],
        "execution_requirements": BROAD_REPOSITORY,
    },
)

_TEST_FOCUSED_DEBUGGING = (
    "Investigate why tests/test_indexer.py fails after the last indexing change.",
    {
        "task": {"type": "debugging", "provenance": "inferred"},
        "subjects": [{"value": "tests/test_indexer.py", "provenance": "explicit"}],
        "execution_requirements": BOUNDED_REPOSITORY,
    },
)

_REPO_PLUS_EXTERNAL = (
    "Compare our retry policy in core/executor.py against the current published "
    "guidance for exponential backoff.",
    {
        "task": {"type": "comparative_analysis", "provenance": "inferred"},
        "subjects": [
            {"value": "our retry policy in core/executor.py", "provenance": "explicit"},
            {
                "value": "current published guidance for exponential backoff",
                "provenance": "explicit",
            },
        ],
        "relationships": [
            {
                "type": "comparison",
                "subjects": [
                    "our retry policy in core/executor.py",
                    "current published guidance for exponential backoff",
                ],
                "provenance": "explicit",
            }
        ],
        "execution_requirements": {
            "repository_inspection_required": True,
            "local_repository_required": True,
            "external_information_required": True,
        },
    },
)

_EXTERNAL_ONLY = (
    "What is the current stable release of Python?",
    {
        "task": {"type": "question", "provenance": "inferred"},
        "execution_requirements": {"external_information_required": True},
    },
)

_DIRECT_PLUS_EXTERNAL = (
    "Compare this supplied API description with the current official API:\n\n"
    "`GET /v1/items -> {items: []}`\n",
    {
        "task": {"type": "comparative_analysis", "provenance": "inferred"},
        "subjects": [
            {"value": "this supplied API description", "provenance": "explicit"},
            {"value": "current official API", "provenance": "explicit"},
        ],
        "relationships": [
            {
                "type": "comparison",
                "subjects": ["this supplied API description", "current official API"],
                "provenance": "explicit",
            }
        ],
        "execution_requirements": {"external_information_required": True},
    },
)

_EVOLUTION_PROMPT = (
    "Continue evolving this project through the roadmap phases, starting from the "
    "current registry in docs/roadmap/phase_registry.json."
)

_EVOLUTION_INTERPRETATION = {
    "task": {"type": "planning", "provenance": "inferred"},
    "subjects": [{"value": "docs/roadmap/phase_registry.json", "provenance": "explicit"}],
    "execution_requirements": BROAD_REPOSITORY,
}


def _evolution_upstream():
    contract, completion = _handoff(_EVOLUTION_PROMPT, _EVOLUTION_INTERPRETATION)
    declaration = ProjectEvolutionRequest(
        evidence_text="Continue evolving this project through the roadmap phases",
        declared_by=DECLARATION_SOURCE_HUMAN_DECLARED_WORKFLOW_INTENT,
        source_raw_request_sha256=contract.raw_request.sha256,
    )
    decision = route_execution_workflow(
        contract, completion, project_evolution_request=declaration
    )
    evidence = derive_evidence_requirements(decision, contract, completion)
    return evidence, decision, contract, completion


def _evolution_requests() -> AcquisitionRequestContract:
    return derive_acquisition_requests(*_evolution_upstream())


def _dogfood_requests() -> AcquisitionRequestContract:
    return _requests(DOGFOOD_PROMPT, _dogfood_interpretation(BROAD_REPOSITORY))


# ══ A — a simple explanation asks for what it already holds ═══════════════════

def test_case_a_explanation_requests_only_the_context_it_already_has():
    acquisition = _requests(*_EXPLANATION)

    assert acquisition.status == STATUS_READY
    assert acquisition.workflow == WORKFLOW_CHAT
    assert acquisition.evidence_scope == SCOPE_DIRECT_CONTEXT_ONLY
    assert acquisition.domains() == (DOMAIN_DIRECT_CONTEXT,)
    assert acquisition.requests_domain(DOMAIN_REPOSITORY) is False
    assert acquisition.requests_domain(DOMAIN_EXTERNAL_INFORMATION) is False


def test_case_a_a_direct_context_request_fetches_nothing():
    request = _requests(*_EXPLANATION).request_for(
        DOMAIN_DIRECT_CONTEXT, TIER_REQUIRED_PRIMARY
    )

    assert request is not None
    assert request.scope == REQUEST_SCOPE_EXISTING_CONTEXT
    assert request.source_classes == (SOURCE_CLASS_SUPPLIED_CONTEXT,)
    assert request.freshness == FRESHNESS_NOT_APPLICABLE
    assert request.budget.profile == BUDGET_EXISTING_CONTEXT
    assert request.target_anchors == ()


def test_case_a_a_direct_context_request_does_not_copy_the_prompt():
    """A reference to preserved material, not a second copy of it."""
    rendered = json.dumps(
        _without_authority(_requests(*_EXPLANATION).as_dict()), ensure_ascii=False
    )

    assert "Bellman" not in rendered


# ══ B — a pasted comparison is the same shape ═════════════════════════════════

def test_case_b_pasted_comparison_requests_direct_context_only():
    acquisition = _requests(_PASTED_COMPARISON, _PASTED_COMPARISON_INTERPRETATION)

    assert acquisition.workflow == WORKFLOW_CHAT
    assert acquisition.domains() == (DOMAIN_DIRECT_CONTEXT,)
    assert acquisition.exclusions == ()
    assert acquisition.deferred_requests == ()


# ══ C — a bounded edit, with the path the user wrote ══════════════════════════

def test_case_c_readme_edit_requests_bounded_repository_evidence():
    acquisition = _requests(*_README_EDIT)
    request = acquisition.request_for(DOMAIN_REPOSITORY, TIER_REQUIRED_PRIMARY)

    assert acquisition.workflow == WORKFLOW_INSTANT_RUN
    assert acquisition.evidence_scope == SCOPE_BOUNDED_REPOSITORY
    assert request is not None
    assert request.scope == REQUEST_SCOPE_BOUNDED_REPOSITORY
    assert request.source_classes == (
        SOURCE_CLASS_RUNTIME_IMPLEMENTATION,
        SOURCE_CLASS_SURROUNDING_IMPLEMENTATION,
    )
    assert request.budget.profile == BUDGET_BOUNDED


def test_case_c_the_path_the_user_wrote_survives_as_an_anchor():
    request = _requests(*_README_EDIT).request_for(
        DOMAIN_REPOSITORY, TIER_REQUIRED_PRIMARY
    )

    assert [anchor.value for anchor in request.target_anchors] == ["README.md"]
    assert ACQUIRE_EXPLICIT_TARGET_ANCHOR_PRESERVED in request.reasons


def test_case_c_an_anchor_asserts_nothing_about_the_thing_it_names():
    """Preserved, not discovered — and not verified, read or opened either."""
    request = _requests(*_README_EDIT).request_for(
        DOMAIN_REPOSITORY, TIER_REQUIRED_PRIMARY
    )
    anchor = request.target_anchors[0].as_dict()

    assert anchor["source"] == "explicit_input_evidence"
    assert anchor["discovered"] is False
    assert anchor["existence_verified"] is False


def test_case_c_a_bounded_edit_asks_for_no_architecture_survey():
    request = _requests(*_README_EDIT).request_for(
        DOMAIN_REPOSITORY, TIER_REQUIRED_PRIMARY
    )

    assert SOURCE_CLASS_AUTHORITATIVE_ARCHITECTURE_DOC not in request.source_classes
    assert SOURCE_CLASS_PLUGIN_OR_REGISTRATION_SURFACE not in request.source_classes
    assert request.scope != REQUEST_SCOPE_BROAD_REPOSITORY_RECONNAISSANCE


# ══ D — a one-file implementation is the same shape ═══════════════════════════

def test_case_d_one_file_implementation_requests_a_bounded_repository():
    acquisition = _requests(*_ONE_FILE_IMPLEMENTATION)
    request = acquisition.request_for(DOMAIN_REPOSITORY, TIER_REQUIRED_PRIMARY)

    assert acquisition.workflow == WORKFLOW_INSTANT_RUN
    assert request.budget.profile == BUDGET_BOUNDED
    assert [anchor.value for anchor in request.target_anchors] == ["core/text_utils.py"]


# ══ E — a broad investigation ═════════════════════════════════════════════════

def test_case_e_broad_investigation_requests_the_seams_as_well_as_the_code():
    request = _requests(*_BROAD_DEBUGGING).request_for(
        DOMAIN_REPOSITORY, TIER_REQUIRED_PRIMARY
    )

    assert request.scope == REQUEST_SCOPE_BROAD_REPOSITORY_RECONNAISSANCE
    for source_class in (
        SOURCE_CLASS_RUNTIME_IMPLEMENTATION,
        SOURCE_CLASS_INTERFACE_DEFINITION,
        SOURCE_CLASS_CONFIGURATION,
        SOURCE_CLASS_DEPENDENCY_MANIFEST,
        SOURCE_CLASS_AUTHORITATIVE_ARCHITECTURE_DOC,
        SOURCE_CLASS_PLUGIN_OR_REGISTRATION_SURFACE,
    ):
        assert source_class in request.source_classes, source_class


def test_case_e_broad_investigation_keeps_validation_secondary():
    acquisition = _requests(*_BROAD_DEBUGGING)

    assert acquisition.request_for(DOMAIN_VALIDATION_ARTIFACTS, TIER_REQUIRED_PRIMARY) is None
    secondary = acquisition.request_for(
        DOMAIN_VALIDATION_ARTIFACTS, TIER_REQUIRED_SECONDARY
    )
    assert secondary is not None
    assert secondary.budget.profile == BUDGET_SECONDARY_VERIFICATION


def test_case_e_broad_investigation_excludes_generated_and_snapshot_material():
    acquisition = _requests(*_BROAD_DEBUGGING)

    assert SOURCE_CLASS_GENERATED_ARTIFACT in acquisition.excluded_classes()
    assert SOURCE_CLASS_SNAPSHOT in acquisition.excluded_classes()
    assert SOURCE_CLASS_TEMPORARY_ARTIFACT in acquisition.excluded_classes()
    assert SOURCE_CLASS_DUPLICATE_RENDERING in acquisition.deferred_classes()


# ══ F — the DeepSeek Harness dogfood ══════════════════════════════════════════

def test_case_f_dogfood_primary_request_is_implementation_interfaces_and_shape():
    acquisition = _dogfood_requests()
    request = acquisition.request_for(DOMAIN_REPOSITORY, TIER_REQUIRED_PRIMARY)

    assert acquisition.workflow == WORKFLOW_COMMANDER
    assert acquisition.evidence_scope == SCOPE_BROAD_REPOSITORY_RECONNAISSANCE
    assert request.required_roles == (
        ROLE_IMPLEMENTATION_AUTHORITY,
        ROLE_INTERFACE_CONTRACT,
        ROLE_CONFIGURATION_AUTHORITY,
        ROLE_ARCHITECTURE_DESCRIPTION,
    )
    assert request.source_classes == (
        SOURCE_CLASS_RUNTIME_IMPLEMENTATION,
        SOURCE_CLASS_SURROUNDING_IMPLEMENTATION,
        SOURCE_CLASS_INTERFACE_DEFINITION,
        SOURCE_CLASS_CONFIGURATION,
        SOURCE_CLASS_DEPENDENCY_MANIFEST,
        SOURCE_CLASS_AUTHORITATIVE_ARCHITECTURE_DOC,
        SOURCE_CLASS_PLUGIN_OR_REGISTRATION_SURFACE,
    )


def test_case_f_dogfood_secondary_request_is_validation_only():
    request = _dogfood_requests().request_for(
        DOMAIN_VALIDATION_ARTIFACTS, TIER_REQUIRED_SECONDARY
    )

    assert request.source_classes == (SOURCE_CLASS_VALIDATION_TEST,)
    assert ACQUIRE_UNRELATED_VALIDATION_DEFERRED in request.reasons


def test_case_f_dogfood_history_is_deferred_with_no_budget_at_all():
    acquisition = _dogfood_requests()
    request = acquisition.request_for(DOMAIN_HISTORICAL_CONTEXT, TIER_DEFERRED)

    assert request in acquisition.deferred_requests
    assert request not in acquisition.requests
    assert request.source_classes == (SOURCE_CLASS_HISTORICAL_DESIGN_MATERIAL,)
    assert request.budget.profile == BUDGET_NONE
    assert request.budget.max_candidates == 0
    assert request.budget.active is False
    assert request.require_current_authority is False
    assert request.freshness == FRESHNESS_HISTORICAL


def test_case_f_dogfood_names_no_file_no_path_and_no_query():
    """A request contract is not a read set."""
    rendered = json.dumps(
        _without_authority(_dogfood_requests().as_dict()), ensure_ascii=False
    ).lower()

    for forbidden in (
        ".py",
        ".json",
        ".md",
        "core/",
        "tests/",
        "docs/",
        "glob",
        "read_set",
        "file_list",
        "search_query",
        "http",
        "www.",
    ):
        assert forbidden not in rendered, forbidden


def test_case_f_dogfood_request_set_is_independent_and_carries_no_plan():
    rendered = _structure_only(_dogfood_requests())

    for forbidden in ("depends_on", "step", "stage", "sequence", "after", "order"):
        assert forbidden not in rendered, forbidden


# ══ G — the same dogfood over supplied context ════════════════════════════════

def test_case_g_direct_context_dogfood_requests_no_repository_acquisition():
    acquisition = _requests(DOGFOOD_PROMPT, _dogfood_interpretation({}))

    assert acquisition.workflow == WORKFLOW_CHAT
    assert acquisition.evidence_scope == SCOPE_DIRECT_CONTEXT_ONLY
    assert acquisition.domains() == (DOMAIN_DIRECT_CONTEXT,)
    assert acquisition.exclusions == ()
    assert acquisition.budget_summary()["max_candidates_total"] == 1


# ══ H — a simple current external lookup ══════════════════════════════════════

def test_case_h_external_lookup_requests_external_authority_only():
    acquisition = _requests(*_EXTERNAL_ONLY)
    request = acquisition.request_for(DOMAIN_EXTERNAL_INFORMATION, TIER_REQUIRED_PRIMARY)

    assert acquisition.workflow == WORKFLOW_CHAT
    assert acquisition.evidence_scope == SCOPE_EXTERNAL_ONLY
    assert acquisition.requests_domain(DOMAIN_REPOSITORY) is False
    assert request is not None
    assert request.required_roles == (ROLE_CURRENT_EXTERNAL_AUTHORITY,)
    assert request.source_classes == (SOURCE_CLASS_AUTHORITATIVE_EXTERNAL_SOURCE,)
    assert request.scope == REQUEST_SCOPE_EXTERNAL_INFORMATION
    assert request.freshness == FRESHNESS_CURRENT
    assert request.require_current_authority is True
    assert request.budget.profile == BUDGET_EXTERNAL_BOUNDED


def test_case_h_an_external_request_names_no_engine_no_address_and_no_query():
    rendered = _structure_only(_requests(*_EXTERNAL_ONLY))

    for forbidden in (
        "google",
        "bing",
        "duckduckgo",
        "http",
        "www.",
        "url",
        "host",
        "endpoint",
        "query",
        "api",
    ):
        assert forbidden not in rendered, forbidden


# ══ I — supplied material plus a current external fact ════════════════════════

def test_case_i_direct_plus_external_requests_both_and_escalates_nothing():
    acquisition = _requests(*_DIRECT_PLUS_EXTERNAL)

    assert acquisition.workflow == WORKFLOW_CHAT
    assert acquisition.evidence_scope == SCOPE_MIXED_SOURCES
    assert acquisition.domains() == (
        DOMAIN_DIRECT_CONTEXT,
        DOMAIN_EXTERNAL_INFORMATION,
    )
    assert acquisition.requests_domain(DOMAIN_REPOSITORY) is False


def test_case_i_repository_plus_external_requests_both_kinds_of_source():
    acquisition = _requests(*_REPO_PLUS_EXTERNAL)

    assert acquisition.workflow == WORKFLOW_COMMANDER
    assert acquisition.evidence_scope == SCOPE_MIXED_SOURCES
    assert acquisition.requests_domain(DOMAIN_REPOSITORY) is True
    assert acquisition.requests_domain(DOMAIN_EXTERNAL_INFORMATION) is True


# ══ J — validation artifacts follow the task, not a global rule ═══════════════

def test_case_j_a_failing_test_makes_the_validation_request_primary():
    acquisition = _requests(*_TEST_FOCUSED_DEBUGGING)
    request = acquisition.request_for(DOMAIN_VALIDATION_ARTIFACTS, TIER_REQUIRED_PRIMARY)

    assert request is not None
    assert request.source_classes == (SOURCE_CLASS_VALIDATION_TEST,)
    assert request.budget.profile == BUDGET_BOUNDED
    assert acquisition.request_for(
        DOMAIN_VALIDATION_ARTIFACTS, TIER_REQUIRED_SECONDARY
    ) is None


def test_case_j_the_named_test_is_the_anchor_on_the_validation_request():
    request = _requests(*_TEST_FOCUSED_DEBUGGING).request_for(
        DOMAIN_VALIDATION_ARTIFACTS, TIER_REQUIRED_PRIMARY
    )

    assert [anchor.value for anchor in request.target_anchors] == [
        "tests/test_indexer.py"
    ]


def test_case_j_no_request_runs_anything():
    guardrails = acquisition_guardrails()

    assert guardrails["validation_executed"] is False
    assert guardrails["command_executed"] is False


# ══ K — Project Evolution stays bounded per cycle ═════════════════════════════

def test_case_k_project_evolution_requests_stay_finite():
    acquisition = _evolution_requests()
    request = acquisition.request_for(DOMAIN_REPOSITORY, TIER_REQUIRED_PRIMARY)

    assert acquisition.workflow == WORKFLOW_PROJECT_EVOLUTION
    assert request.scope == REQUEST_SCOPE_BROAD_REPOSITORY_RECONNAISSANCE
    assert request.budget.profile == BUDGET_RECONNAISSANCE
    assert 0 < request.budget.max_candidates <= MAX_CANDIDATES_CEILING


def test_case_k_project_evolution_grants_no_project_evolution_authority():
    authority = _evolution_requests().as_dict()["authority"]

    assert authority["project_evolution_authority"] is False
    assert authority["evidence_acquisition_authority"] is False
    assert authority["human_approval_required"] is True


# ══ L — historical material never becomes implementation authority ════════════

def test_case_l_historical_requests_never_expect_current_authority():
    for acquisition in (_dogfood_requests(), _requests(*_BROAD_DEBUGGING)):
        request = acquisition.request_for(DOMAIN_HISTORICAL_CONTEXT, TIER_DEFERRED)

        assert request.require_current_authority is False
        assert request.freshness == FRESHNESS_HISTORICAL
        assert ROLE_IMPLEMENTATION_AUTHORITY not in request.required_roles


# ══ M — restated material is never an active request ══════════════════════════

def test_case_m_no_request_may_name_generated_snapshot_or_temporary_material():
    for acquisition in (
        _dogfood_requests(),
        _requests(*_BROAD_DEBUGGING),
        _requests(*_README_EDIT),
    ):
        for request in acquisition.all_requests():
            assert not set(request.source_classes) & set(NEVER_REQUESTED_SOURCE_CLASSES)


def test_case_m_a_request_for_restated_material_cannot_even_be_built():
    with pytest.raises(ValueError):
        AcquisitionRequest(
            domain=DOMAIN_REPOSITORY,
            required_roles=(ROLE_IMPLEMENTATION_AUTHORITY,),
            tier=TIER_REQUIRED_PRIMARY,
            source_classes=(SOURCE_CLASS_SNAPSHOT,),
            scope=REQUEST_SCOPE_BOUNDED_REPOSITORY,
            budget=AcquisitionBudget(BUDGET_BOUNDED),
            freshness=FRESHNESS_CURRENT,
            require_current_authority=True,
            reasons=(ACQUIRE_EXPLICIT_TARGET_ANCHOR_PRESERVED,),
        )


def test_case_m_an_excluded_class_carries_no_acquisition_budget():
    exclusion = _dogfood_requests().exclusions[0].as_dict()

    assert exclusion["acquisition_budget"]["max_candidates"] == 0
    assert exclusion["acquisition_budget"]["max_total_bytes"] == 0


# ══ N — an unspecified evidence contract produces no requests ═════════════════

def test_case_n_an_unrouted_order_produces_no_acquisition_requests():
    evidence, decision, contract, completion = _upstream(*_EXPLANATION)
    refused = EvidenceRequirementContract(
        status="not_routed",
        reasons=(EVIDENCE_DIRECT_CONTEXT_FROM_TASK,),
        inconsistencies=("waiter_decision_not_routed",),
    )

    acquisition = derive_acquisition_requests(refused, decision, contract, completion)

    assert acquisition.status == STATUS_NOT_EVIDENCE_READY
    assert acquisition.inconsistencies == (INCONSISTENT_EVIDENCE_NOT_SPECIFIED,)
    assert acquisition.requests == ()
    assert acquisition.deferred_requests == ()
    assert acquisition.exclusions == ()
    assert acquisition.workflow is None


def test_case_n_a_refused_contract_still_denies_every_authority():
    evidence, decision, contract, completion = _upstream(*_EXPLANATION)
    refused = EvidenceRequirementContract(
        status="not_routed",
        reasons=(EVIDENCE_DIRECT_CONTEXT_FROM_TASK,),
        inconsistencies=("waiter_decision_not_routed",),
    )
    authority = derive_acquisition_requests(
        refused, decision, contract, completion
    ).as_dict()["authority"]

    assert authority["repository_read_authority"] is False
    assert authority["human_approval_required"] is True


# ══ O — a tampered upstream record ════════════════════════════════════════════

def test_case_o_a_contract_from_another_run_is_refused():
    evidence, decision, _, completion = _upstream(*_README_EDIT)
    other_contract, _ = _handoff(*_ONE_FILE_IMPLEMENTATION)

    acquisition = derive_acquisition_requests(
        evidence, decision, other_contract, completion
    )

    assert acquisition.status == STATUS_INCONSISTENT_INPUT
    assert acquisition.inconsistencies == (INCONSISTENT_SOURCE_FINGERPRINT_MISMATCH,)
    assert acquisition.requests == ()


def test_case_o_an_edited_evidence_contract_no_longer_fingerprints():
    evidence, decision, contract, completion = _upstream(*_README_EDIT)
    tampered = dataclasses.replace(evidence, source_contract_fingerprint="0" * 64)

    acquisition = derive_acquisition_requests(tampered, decision, contract, completion)

    assert acquisition.status == STATUS_INCONSISTENT_INPUT
    assert acquisition.inconsistencies == (INCONSISTENT_SOURCE_FINGERPRINT_MISMATCH,)


# ══ P — the capability envelope, in both directions ═══════════════════════════

def test_case_p_an_evidence_contract_outside_the_envelope_is_refused():
    evidence, decision, contract, completion = _upstream(*_EXPLANATION)
    widened = dataclasses.replace(
        evidence,
        scope=SCOPE_BOUNDED_REPOSITORY,
        requirements=evidence.requirements
        + (
            EvidenceRequirement(
                domain=DOMAIN_REPOSITORY,
                role=ROLE_IMPLEMENTATION_AUTHORITY,
                tier=TIER_REQUIRED_PRIMARY,
                reasons=(EVIDENCE_REPOSITORY_REQUIRED,),
            ),
        ),
    )

    acquisition = derive_acquisition_requests(widened, decision, contract, completion)

    assert acquisition.status == STATUS_INCONSISTENT_INPUT
    assert acquisition.requests == ()


def test_case_q_an_evidence_contract_missing_a_required_capability_is_refused():
    evidence, decision, contract, completion = _upstream(*_EXTERNAL_ONLY)
    narrowed = dataclasses.replace(
        evidence,
        scope=SCOPE_DIRECT_CONTEXT_ONLY,
        requirements=tuple(
            item
            for item in evidence.requirements
            if item.domain != DOMAIN_EXTERNAL_INFORMATION
        ),
        verification_requirements=(),
    )

    acquisition = derive_acquisition_requests(narrowed, decision, contract, completion)

    assert acquisition.status == STATUS_INCONSISTENT_INPUT
    assert acquisition.requests == ()


# ══ R — the workflow is copied, never chosen ══════════════════════════════════

def test_case_r_the_workflow_is_copied_from_the_evidence_contract():
    for prompt, payload in (
        _EXPLANATION,
        _README_EDIT,
        _BROAD_DEBUGGING,
        _EXTERNAL_ONLY,
    ):
        evidence, decision, contract, completion = _upstream(prompt, payload)
        acquisition = derive_acquisition_requests(
            evidence, decision, contract, completion
        )

        assert acquisition.workflow == evidence.workflow == decision.recommended_workflow


def test_case_r_a_workflow_that_disagrees_with_the_route_is_refused():
    evidence, decision, contract, completion = _upstream(*_EXPLANATION)
    mutated = dataclasses.replace(evidence, workflow=WORKFLOW_COMMANDER)

    acquisition = derive_acquisition_requests(mutated, decision, contract, completion)

    assert acquisition.status == STATUS_INCONSISTENT_INPUT
    assert acquisition.inconsistencies == (INCONSISTENT_WORKFLOW_MISMATCH,)


def test_case_r_no_acquisition_module_contains_a_router_symbol():
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1] / "core"
    for name in ("acquisition_request.py", "acquisition_policy.py"):
        source = (root / name).read_text(encoding="utf-8")

        for forbidden in ("route_execution_workflow", "select_workflow"):
            assert forbidden not in source, f"{name}: {forbidden}"


# ══ S — no compute choice of any kind ═════════════════════════════════════════

_COMPUTE_TOKENS: tuple[str, ...] = (
    "gemini",
    "gemma",
    "qwen",
    "ornith",
    "claude",
    "gpt",
    "ollama",
    "cloud",
    "provider",
    "model",
    "context window",
    "num_ctx",
    "temperature",
    "api key",
    "endpoint",
    "fallback",
)


@pytest.mark.parametrize(
    "prompt, payload",
    [
        _EXPLANATION,
        (_PASTED_COMPARISON, _PASTED_COMPARISON_INTERPRETATION),
        _README_EDIT,
        _BROAD_DEBUGGING,
        _REPO_PLUS_EXTERNAL,
        _EXTERNAL_ONLY,
        (DOGFOOD_PROMPT, _dogfood_interpretation(BROAD_REPOSITORY)),
    ],
)
def test_case_s_no_request_names_a_model_or_a_provider(prompt, payload):
    rendered = json.dumps(
        _without_authority(_requests(prompt, payload).as_dict()), ensure_ascii=False
    ).lower()

    for token in _COMPUTE_TOKENS:
        assert token not in rendered, token


def test_case_s_local_and_cloud_are_not_request_concepts():
    rendered = json.dumps(
        _without_authority(_dogfood_requests().as_dict()), ensure_ascii=False
    ).lower()

    assert "local" not in rendered
    assert "remote" not in rendered


# ══ T — the contract is structural, not linguistic ════════════════════════════

def test_case_t_english_and_vietnamese_orders_request_identical_acquisition():
    english = _requests(
        "Analyse the whole indexing architecture in core/indexer.py and graph/builder.py.",
        {
            "task": {"type": "analysis", "provenance": "inferred"},
            "subjects": [
                {"value": "core/indexer.py", "provenance": "explicit"},
                {"value": "graph/builder.py", "provenance": "explicit"},
            ],
            "execution_requirements": BROAD_REPOSITORY,
        },
    )
    vietnamese = _requests(
        "Phân tích toàn bộ kiến trúc lập chỉ mục trong core/indexer.py và graph/builder.py.",
        {
            "task": {"type": "analysis", "provenance": "inferred"},
            "subjects": [
                {"value": "core/indexer.py", "provenance": "explicit"},
                {"value": "graph/builder.py", "provenance": "explicit"},
            ],
            "execution_requirements": BROAD_REPOSITORY,
        },
    )

    assert canonical_acquisition_shape(english) == canonical_acquisition_shape(vietnamese)


def test_case_t_a_vietnamese_explanation_requests_only_its_own_context():
    acquisition = _requests(
        "Giải thích phương trình Bellman.",
        {"task": {"type": "question", "provenance": "inferred"}},
    )

    assert acquisition.domains() == (DOMAIN_DIRECT_CONTEXT,)


# ══ Budgets ═══════════════════════════════════════════════════════════════════

def _candidates(profile: str) -> int:
    return BUDGET_PROFILE_LIMITS[profile][0]


def test_a_direct_context_request_carries_the_smallest_active_budget():
    request = _requests(*_EXPLANATION).request_for(
        DOMAIN_DIRECT_CONTEXT, TIER_REQUIRED_PRIMARY
    )

    assert request.budget.max_candidates == 1
    assert request.budget.max_initial_sources == 1
    assert request.budget.active is True


def test_a_bounded_repository_budget_is_smaller_than_reconnaissance():
    bounded = _requests(*_README_EDIT).request_for(
        DOMAIN_REPOSITORY, TIER_REQUIRED_PRIMARY
    )
    broad = _dogfood_requests().request_for(DOMAIN_REPOSITORY, TIER_REQUIRED_PRIMARY)

    assert bounded.budget.max_candidates < broad.budget.max_candidates
    assert bounded.budget.max_initial_sources < broad.budget.max_initial_sources


def test_a_reconnaissance_budget_is_larger_than_bounded_and_still_finite():
    broad = _dogfood_requests().request_for(DOMAIN_REPOSITORY, TIER_REQUIRED_PRIMARY)

    assert broad.budget.max_candidates == _candidates(BUDGET_RECONNAISSANCE)
    assert 0 < broad.budget.max_candidates <= MAX_CANDIDATES_CEILING
    assert 0 < broad.budget.max_initial_sources <= MAX_INITIAL_SOURCES_CEILING


def test_a_secondary_validation_budget_never_exceeds_the_evidence_it_checks():
    acquisition = _dogfood_requests()
    primary = acquisition.request_for(DOMAIN_REPOSITORY, TIER_REQUIRED_PRIMARY)
    secondary = acquisition.request_for(
        DOMAIN_VALIDATION_ARTIFACTS, TIER_REQUIRED_SECONDARY
    )

    assert secondary.budget.max_candidates <= primary.budget.max_candidates
    assert secondary.budget.max_initial_sources <= primary.budget.max_initial_sources


def test_deferred_history_has_no_acquisition_budget():
    request = _dogfood_requests().request_for(DOMAIN_HISTORICAL_CONTEXT, TIER_DEFERRED)

    assert request.budget.max_candidates == 0
    assert request.budget.max_initial_sources == 0
    assert request.budget.max_total_bytes == 0


def test_an_excluded_source_class_has_no_acquisition_budget():
    summary = _dogfood_requests().budget_summary()

    assert summary["excluded_candidate_budget"] == 0
    assert summary["deferred_candidate_budget"] == 0


def test_project_evolution_budgets_are_finite_per_cycle():
    summary = _evolution_requests().budget_summary()

    assert summary["bounded"] is True
    assert summary["unbounded_request_present"] is False
    assert 0 < summary["max_candidates_total"] < MAX_CANDIDATES_CEILING * len(
        EVIDENCE_DOMAINS
    )


def test_no_budget_depends_on_anything_measured():
    """Every ceiling is a constant, so nothing about the machine can move one."""
    for profile in BUDGET_PROFILES:
        limits = BUDGET_PROFILE_LIMITS[profile]

        assert all(isinstance(value, int) for value in limits)
        assert limits[0] <= MAX_CANDIDATES_CEILING
        assert limits[1] <= MAX_INITIAL_SOURCES_CEILING
        assert limits[2] <= MAX_TOTAL_BYTES_CEILING
        assert limits[3] <= MAX_PER_SOURCE_BYTES_CEILING


def test_the_same_order_always_produces_the_same_budgets():
    first = _dogfood_requests()
    second = _dogfood_requests()

    assert canonical_acquisition_fingerprint(first) == canonical_acquisition_fingerprint(
        second
    )
    assert first.budget_summary() == second.budget_summary()


def test_a_budget_is_not_derived_from_the_workflow():
    """A Commander order whose evidence is direct context asks for no repository."""
    commander = _dogfood_requests()
    chat = _requests(DOGFOOD_PROMPT, _dogfood_interpretation({}))

    assert commander.workflow == WORKFLOW_COMMANDER
    assert chat.workflow == WORKFLOW_CHAT
    assert chat.requests_domain(DOGFOOD_REPOSITORY := DOMAIN_REPOSITORY) is False
    assert chat.budget_summary()["max_candidates_total"] == 1


# ══ The DeepSeek anti-6,087 regression ════════════════════════════════════════

def test_no_request_can_express_the_whole_repository():
    """The failure this phase exists to make unrepresentable."""
    acquisition = _dogfood_requests()

    for request in acquisition.all_requests():
        assert isinstance(request.budget.max_candidates, int)
        assert request.budget.max_candidates <= MAX_CANDIDATES_CEILING
        assert request.budget.max_candidates != 6087
        assert request.budget.max_total_bytes <= MAX_TOTAL_BYTES_CEILING


def test_a_broad_request_still_names_which_classes_it_may_reach():
    request = _dogfood_requests().request_for(DOMAIN_REPOSITORY, TIER_REQUIRED_PRIMARY)

    assert request.scope == REQUEST_SCOPE_BROAD_REPOSITORY_RECONNAISSANCE
    assert set(request.source_classes) < set(REQUESTABLE_SOURCE_CLASSES)
    assert SOURCE_CLASS_VALIDATION_TEST not in request.source_classes
    assert SOURCE_CLASS_HISTORICAL_DESIGN_MATERIAL not in request.source_classes


def test_a_broad_request_never_travels_without_its_exclusions():
    acquisition = _dogfood_requests()

    assert acquisition.exclusions != ()
    assert check_bounded_reconnaissance(
        AcquisitionPolicy(
            requests=acquisition.requests,
            deferred_requests=acquisition.deferred_requests,
            exclusions=(),
        )
    ) == (INCONSISTENT_ACQUISITION_WIDENED,)


def test_an_unbounded_budget_cannot_be_constructed():
    for bad in ("unlimited", "all", "", "everything"):
        with pytest.raises(ValueError):
            AcquisitionBudget(bad)


def test_a_budget_has_no_field_in_which_a_number_could_be_supplied():
    fields = {field.name for field in dataclasses.fields(AcquisitionBudget)}

    assert fields == {"profile"}


def test_the_rendered_contract_never_says_unlimited():
    rendered = render_acquisition_contract_json(_dogfood_requests()).lower()

    for forbidden in ("unlimited", "unbounded_request_present\": true", "all_files", "-1"):
        assert forbidden not in rendered, forbidden


# ══ Monotonicity: refine, never widen ═════════════════════════════════════════

def _policy_for(prompt: str, payload: dict, **kwargs):
    evidence, _, contract, _ = _upstream(prompt, payload, **kwargs)
    return derive_acquisition_policy(evidence, contract), evidence


def test_every_derived_request_set_stays_inside_its_evidence_contract():
    for prompt, payload in (
        _EXPLANATION,
        (_PASTED_COMPARISON, _PASTED_COMPARISON_INTERPRETATION),
        _README_EDIT,
        _ONE_FILE_IMPLEMENTATION,
        _BROAD_DEBUGGING,
        _TEST_FOCUSED_DEBUGGING,
        _REPO_PLUS_EXTERNAL,
        _EXTERNAL_ONLY,
        _DIRECT_PLUS_EXTERNAL,
        (DOGFOOD_PROMPT, _dogfood_interpretation(BROAD_REPOSITORY)),
        (DOGFOOD_PROMPT, _dogfood_interpretation({})),
    ):
        policy, evidence = _policy_for(prompt, payload)

        assert check_request_monotonicity(policy, evidence) == (), prompt
        assert check_requirement_coverage(policy, evidence) == (), prompt
        assert check_deferred_source_coverage(policy, evidence) == (), prompt
        assert check_bounded_reconnaissance(policy) == (), prompt


def test_a_repository_request_the_contract_never_licensed_is_widening():
    policy, evidence = _policy_for(*_EXPLANATION)
    widened = AcquisitionPolicy(
        requests=policy.requests
        + (
            AcquisitionRequest(
                domain=DOMAIN_REPOSITORY,
                required_roles=(ROLE_IMPLEMENTATION_AUTHORITY,),
                tier=TIER_REQUIRED_PRIMARY,
                source_classes=(SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
                scope=REQUEST_SCOPE_BOUNDED_REPOSITORY,
                budget=AcquisitionBudget(BUDGET_BOUNDED),
                freshness=FRESHNESS_CURRENT,
                require_current_authority=True,
                reasons=(ACQUIRE_EXPLICIT_TARGET_ANCHOR_PRESERVED,),
            ),
        )
    )

    assert check_request_monotonicity(widened, evidence) == (
        INCONSISTENT_ACQUISITION_WIDENED,
    )


def test_promoting_deferred_history_to_primary_is_widening():
    policy, evidence = _policy_for(DOGFOOD_PROMPT, _dogfood_interpretation(BROAD_REPOSITORY))
    promoted = AcquisitionPolicy(
        requests=policy.requests
        + (
            AcquisitionRequest(
                domain=DOMAIN_HISTORICAL_CONTEXT,
                required_roles=(ROLE_HISTORICAL_CONTEXT,),
                tier=TIER_REQUIRED_PRIMARY,
                source_classes=(SOURCE_CLASS_HISTORICAL_DESIGN_MATERIAL,),
                scope=REQUEST_SCOPE_BOUNDED_REPOSITORY,
                budget=AcquisitionBudget(BUDGET_BOUNDED),
                freshness=FRESHNESS_HISTORICAL,
                require_current_authority=False,
                reasons=(ACQUIRE_EXPLICIT_TARGET_ANCHOR_PRESERVED,),
            ),
        ),
        deferred_requests=(),
        exclusions=policy.exclusions,
    )

    assert check_request_monotonicity(promoted, evidence) == (
        INCONSISTENT_ACQUISITION_WIDENED,
    )


def test_an_external_request_the_contract_never_licensed_is_widening():
    policy, evidence = _policy_for(*_README_EDIT)
    widened = AcquisitionPolicy(
        requests=policy.requests
        + (
            AcquisitionRequest(
                domain=DOMAIN_EXTERNAL_INFORMATION,
                required_roles=(ROLE_CURRENT_EXTERNAL_AUTHORITY,),
                tier=TIER_REQUIRED_PRIMARY,
                source_classes=(SOURCE_CLASS_AUTHORITATIVE_EXTERNAL_SOURCE,),
                scope=REQUEST_SCOPE_EXTERNAL_INFORMATION,
                budget=AcquisitionBudget(BUDGET_EXTERNAL_BOUNDED),
                freshness=FRESHNESS_CURRENT,
                require_current_authority=True,
                reasons=(ACQUIRE_EXPLICIT_TARGET_ANCHOR_PRESERVED,),
            ),
        ),
        deferred_requests=policy.deferred_requests,
        exclusions=policy.exclusions,
    )

    assert check_request_monotonicity(widened, evidence) == (
        INCONSISTENT_ACQUISITION_WIDENED,
    )


# ══ No required evidence may be lost ══════════════════════════════════════════

def test_dropping_the_external_request_loses_required_evidence():
    policy, evidence = _policy_for(*_EXTERNAL_ONLY)
    narrowed = AcquisitionPolicy(
        requests=tuple(
            item for item in policy.requests if item.domain != DOMAIN_EXTERNAL_INFORMATION
        ),
        deferred_requests=policy.deferred_requests,
        exclusions=policy.exclusions,
    )

    assert check_requirement_coverage(narrowed, evidence) == (
        INCONSISTENT_REQUIRED_EVIDENCE_DROPPED,
    )


def test_dropping_a_required_role_loses_required_evidence():
    policy, evidence = _policy_for(DOGFOOD_PROMPT, _dogfood_interpretation(BROAD_REPOSITORY))
    repository = policy.requests[1]
    thinned = dataclasses.replace(
        repository,
        required_roles=(ROLE_IMPLEMENTATION_AUTHORITY,),
        source_classes=source_classes_for((ROLE_IMPLEMENTATION_AUTHORITY,)),
    )
    narrowed = AcquisitionPolicy(
        requests=(policy.requests[0], thinned) + policy.requests[2:],
        deferred_requests=policy.deferred_requests,
        exclusions=policy.exclusions,
    )

    assert check_requirement_coverage(narrowed, evidence) == (
        INCONSISTENT_REQUIRED_EVIDENCE_DROPPED,
    )


def test_dropping_an_exclusion_loses_a_deferred_source_class():
    policy, evidence = _policy_for(DOGFOOD_PROMPT, _dogfood_interpretation(BROAD_REPOSITORY))
    narrowed = AcquisitionPolicy(
        requests=policy.requests,
        deferred_requests=policy.deferred_requests,
        exclusions=policy.exclusions[1:],
    )

    assert check_deferred_source_coverage(narrowed, evidence) == (
        INCONSISTENT_REQUIRED_EVIDENCE_DROPPED,
    )


def test_every_deferred_evidence_class_is_accounted_for_somewhere():
    """Including the one with no acquisition counterpart of its own."""
    policy, evidence = _policy_for(DOGFOOD_PROMPT, _dogfood_interpretation(BROAD_REPOSITORY))
    carried = {
        reason
        for request in policy.requests + policy.deferred_requests
        for reason in request.reasons
    }
    stated = {item.source_class for item in policy.exclusions}

    for source in evidence.deferred_sources:
        counterpart = EVIDENCE_CLASS_ACQUISITION_CLASSES[source.source_class]
        if counterpart is None:
            assert ACQUIRE_UNRELATED_VALIDATION_DEFERRED in carried, source.source_class
        else:
            assert counterpart in stated, source.source_class


# ══ Tier preservation ═════════════════════════════════════════════════════════

def test_every_request_keeps_the_tier_its_requirement_had():
    for prompt, payload in (
        _README_EDIT,
        _TEST_FOCUSED_DEBUGGING,
        _BROAD_DEBUGGING,
        (DOGFOOD_PROMPT, _dogfood_interpretation(BROAD_REPOSITORY)),
    ):
        evidence, decision, contract, completion = _upstream(prompt, payload)
        acquisition = derive_acquisition_requests(evidence, decision, contract, completion)

        for requirement in evidence.requirements:
            carriers = [
                request
                for request in acquisition.all_requests()
                if request.satisfies(requirement.domain, requirement.role)
            ]
            assert len(carriers) == 1, (prompt, requirement)
            assert carriers[0].tier == requirement.tier, (prompt, requirement)


def test_an_excluded_tier_is_never_a_request():
    with pytest.raises(ValueError):
        AcquisitionRequest(
            domain=DOMAIN_REPOSITORY,
            required_roles=(ROLE_IMPLEMENTATION_AUTHORITY,),
            tier=TIER_EXCLUDED_INITIALLY,
            source_classes=(SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
            scope=REQUEST_SCOPE_BOUNDED_REPOSITORY,
            budget=AcquisitionBudget(BUDGET_NONE),
            freshness=FRESHNESS_CURRENT,
            require_current_authority=True,
            reasons=(ACQUIRE_EXPLICIT_TARGET_ANCHOR_PRESERVED,),
        )


def test_a_deferred_request_may_not_carry_an_active_budget():
    with pytest.raises(ValueError):
        AcquisitionRequest(
            domain=DOMAIN_HISTORICAL_CONTEXT,
            required_roles=(ROLE_HISTORICAL_CONTEXT,),
            tier=TIER_DEFERRED,
            source_classes=(SOURCE_CLASS_HISTORICAL_DESIGN_MATERIAL,),
            scope=REQUEST_SCOPE_BOUNDED_REPOSITORY,
            budget=AcquisitionBudget(BUDGET_BOUNDED),
            freshness=FRESHNESS_HISTORICAL,
            require_current_authority=False,
            reasons=(ACQUIRE_EXPLICIT_TARGET_ANCHOR_PRESERVED,),
        )


def test_a_required_request_may_not_carry_an_empty_budget():
    with pytest.raises(ValueError):
        AcquisitionRequest(
            domain=DOMAIN_REPOSITORY,
            required_roles=(ROLE_IMPLEMENTATION_AUTHORITY,),
            tier=TIER_REQUIRED_PRIMARY,
            source_classes=(SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
            scope=REQUEST_SCOPE_BOUNDED_REPOSITORY,
            budget=AcquisitionBudget(BUDGET_NONE),
            freshness=FRESHNESS_CURRENT,
            require_current_authority=True,
            reasons=(ACQUIRE_EXPLICIT_TARGET_ANCHOR_PRESERVED,),
        )


# ══ Role mapping ══════════════════════════════════════════════════════════════

def test_every_role_states_the_source_classes_that_satisfy_it():
    assert tuple(SOURCE_CLASSES_BY_ROLE) == EVIDENCE_ROLES
    for role, classes in SOURCE_CLASSES_BY_ROLE.items():
        for source_class in classes:
            assert source_class in REQUESTABLE_SOURCE_CLASSES, role


def test_the_role_mapping_is_the_one_the_design_states():
    assert SOURCE_CLASSES_BY_ROLE[ROLE_IMPLEMENTATION_AUTHORITY] == (
        SOURCE_CLASS_RUNTIME_IMPLEMENTATION,
        SOURCE_CLASS_SURROUNDING_IMPLEMENTATION,
    )
    assert SOURCE_CLASSES_BY_ROLE[ROLE_INTERFACE_CONTRACT] == (
        SOURCE_CLASS_INTERFACE_DEFINITION,
    )
    assert SOURCE_CLASSES_BY_ROLE[ROLE_CONFIGURATION_AUTHORITY] == (
        SOURCE_CLASS_CONFIGURATION,
        SOURCE_CLASS_DEPENDENCY_MANIFEST,
    )
    assert SOURCE_CLASSES_BY_ROLE[ROLE_ARCHITECTURE_DESCRIPTION] == (
        SOURCE_CLASS_AUTHORITATIVE_ARCHITECTURE_DOC,
        SOURCE_CLASS_PLUGIN_OR_REGISTRATION_SURFACE,
    )
    assert SOURCE_CLASSES_BY_ROLE[ROLE_VALIDATION_EVIDENCE] == (
        SOURCE_CLASS_VALIDATION_TEST,
    )
    assert SOURCE_CLASSES_BY_ROLE[ROLE_HISTORICAL_CONTEXT] == (
        SOURCE_CLASS_HISTORICAL_DESIGN_MATERIAL,
    )


def test_a_role_with_no_source_class_fails_the_contract_closed():
    evidence, decision, contract, completion = _upstream(*_EXPLANATION)
    unmappable = dataclasses.replace(
        evidence,
        requirements=evidence.requirements
        + (
            EvidenceRequirement(
                domain=DOMAIN_DIRECT_CONTEXT,
                role=ROLE_HYPOTHESIS_SUPPORT,
                tier=TIER_REQUIRED_SECONDARY,
                reasons=(EVIDENCE_DIRECT_CONTEXT_FROM_TASK,),
            ),
        ),
    )

    assert unmappable_roles(unmappable) == (ROLE_HYPOTHESIS_SUPPORT,)
    acquisition = derive_acquisition_requests(
        unmappable, decision, contract, completion
    )
    assert acquisition.status == STATUS_INCONSISTENT_INPUT
    assert acquisition.requests == ()


# ══ Authority ═════════════════════════════════════════════════════════════════

def test_the_acquisition_phase_holds_no_authority_of_any_kind():
    authority = acquisition_authority()

    for power in (
        "evidence_acquisition_authority",
        "repository_read_authority",
        "repository_traversal_authority",
        "external_search_authority",
        "web_fetch_authority",
        "context_selection_authority",
        "indexing_authority",
        "graph_authority",
        "validation_authority",
        "command_execution_authority",
        "work" + "er_launch_authority",
        "repository_write_authority",
        "patch_authority",
        "planning_authority",
        "routing_authority",
        "provider_selection_authority",
        "model_selection_authority",
        "project_evolution_authority",
    ):
        assert authority[power] is False, power
    assert authority["human_approval_required"] is True


def test_a_ready_status_grants_no_acquisition_authority():
    acquisition = _dogfood_requests()
    authority = acquisition.as_dict()["authority"]

    assert acquisition.status == STATUS_READY
    assert authority["evidence_acquisition_authority"] is False
    assert authority["repository_read_authority"] is False
    assert acquisition.human_approval_required is True


def test_the_guardrails_record_every_action_not_performed():
    guardrails = acquisition_guardrails()

    for action in (
        "repository_files_read",
        "repository_traversal_performed",
        "repository_membership_inspected",
        "manifest_consulted",
        "graph_consulted",
        "index_consulted",
        "ctx_select_called",
        "network_called",
        "web_search_performed",
        "search_query_generated",
        "files_generated",
        "validation_executed",
        "planning_performed",
        "language_system_called",
        "provider_selected",
    ):
        assert guardrails[action] is False, action


def test_no_acquisition_module_can_reach_a_file_a_process_or_a_network():
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1] / "core"
    for name in (
        "acquisition_request.py",
        "acquisition_policy.py",
        "evidence_acquire_request.py",
    ):
        source = (root / name).read_text(encoding="utf-8")
        for forbidden in (
            "import os",
            "import subprocess",
            "import socket",
            "import requests",
            "import urllib",
            "import random",
            "import time",
            "from pathlib",
            "import pathlib",
            "open(",
        ):
            assert forbidden not in source, f"{name}: {forbidden}"


def test_no_acquisition_module_imports_a_selector_an_index_or_a_graph():
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1] / "core"
    for name in (
        "acquisition_request.py",
        "acquisition_policy.py",
        "evidence_acquire_request.py",
    ):
        source = (root / name).read_text(encoding="utf-8")
        for forbidden in (
            "from core.context_selection",
            "from core.retriever",
            "from core.indexer",
            "from core.index_execution",
            "from core.repository_inventory",
            "from core.repo_inventory",
            "from core.graph_walker",
            "from core.index_manifest",
            "from core.file_candidate_selector",
            "from core.direct_file_reader",
            "import core.context_selection",
            "import core.indexer",
        ):
            assert forbidden not in source, f"{name}: {forbidden}"


# ══ Determinism ═══════════════════════════════════════════════════════════════

def test_the_same_order_always_requests_the_same_acquisition():
    first = _dogfood_requests()
    second = _dogfood_requests()

    assert canonical_acquisition_fingerprint(first) == canonical_acquisition_fingerprint(
        second
    )
    assert render_acquisition_contract_json(first) == render_acquisition_contract_json(
        second
    )


def test_an_acquisition_contract_renders_as_deterministic_json():
    payload = json.loads(render_acquisition_contract_json(_dogfood_requests()))

    assert payload["phase_id"] == "ACQUIRE.1"
    assert payload["status"] == STATUS_READY
    assert payload["evidence_scope"] == SCOPE_BROAD_REPOSITORY_RECONNAISSANCE
    assert payload["budget_summary"]["bounded"] is True


def test_the_fingerprint_binds_every_upstream_record():
    acquisition = _dogfood_requests()

    assert acquisition.source_evidence_fingerprint is not None
    assert acquisition.source_decision_fingerprint is not None
    assert acquisition.source_contract_fingerprint is not None
    assert acquisition.source_completion_fingerprint is not None
    assert len(set(
        (
            acquisition.source_evidence_fingerprint,
            acquisition.source_decision_fingerprint,
            acquisition.source_contract_fingerprint,
            acquisition.source_completion_fingerprint,
        )
    )) == 4


# ══ Vocabulary and record invariants ══════════════════════════════════════════

def test_every_vocabulary_is_bounded_and_distinct():
    for vocabulary in (
        ACQUISITION_SOURCE_CLASSES,
        REQUESTABLE_SOURCE_CLASSES,
        NEVER_REQUESTED_SOURCE_CLASSES,
        REQUEST_SCOPES,
        FRESHNESS_REQUIREMENTS,
        BUDGET_PROFILES,
        ACQUISITION_REASONS,
        ACQUISITION_STATUSES,
        ACQUISITION_INCONSISTENCIES,
        ACTIVE_TIERS_ORDER,
    ):
        assert len(set(vocabulary)) == len(vocabulary)
        assert all(isinstance(item, str) and item for item in vocabulary)


def test_every_reason_code_has_a_sentence():
    for reason in ACQUISITION_REASONS:
        assert ACQUISITION_REASON_DESCRIPTIONS[reason].strip()


def test_every_budget_profile_states_its_limits():
    assert tuple(BUDGET_PROFILE_LIMITS) == BUDGET_PROFILES


def test_a_request_must_name_the_fact_it_came_from():
    with pytest.raises(ValueError):
        AcquisitionRequest(
            domain=DOMAIN_REPOSITORY,
            required_roles=(ROLE_IMPLEMENTATION_AUTHORITY,),
            tier=TIER_REQUIRED_PRIMARY,
            source_classes=(SOURCE_CLASS_RUNTIME_IMPLEMENTATION,),
            scope=REQUEST_SCOPE_BOUNDED_REPOSITORY,
            budget=AcquisitionBudget(BUDGET_BOUNDED),
            freshness=FRESHNESS_CURRENT,
            require_current_authority=True,
            reasons=(),
        )


def test_a_request_must_name_at_least_one_source_class():
    with pytest.raises(ValueError):
        AcquisitionRequest(
            domain=DOMAIN_REPOSITORY,
            required_roles=(ROLE_IMPLEMENTATION_AUTHORITY,),
            tier=TIER_REQUIRED_PRIMARY,
            source_classes=(),
            scope=REQUEST_SCOPE_BOUNDED_REPOSITORY,
            budget=AcquisitionBudget(BUDGET_BOUNDED),
            freshness=FRESHNESS_CURRENT,
            require_current_authority=True,
            reasons=(ACQUIRE_EXPLICIT_TARGET_ANCHOR_PRESERVED,),
        )


def test_a_ready_contract_must_carry_a_workflow_and_a_scope():
    with pytest.raises(ValueError):
        AcquisitionRequestContract(
            status=STATUS_READY,
            reasons=(ACQUIRE_EXPLICIT_TARGET_ANCHOR_PRESERVED,),
        )


def test_a_refused_contract_may_not_carry_requests():
    with pytest.raises(ValueError):
        AcquisitionRequestContract(
            status=STATUS_NOT_EVIDENCE_READY,
            requests=(
                AcquisitionRequest(
                    domain=DOMAIN_DIRECT_CONTEXT,
                    required_roles=(ROLE_SUPPLIED_MATERIAL,),
                    tier=TIER_REQUIRED_PRIMARY,
                    source_classes=(SOURCE_CLASS_SUPPLIED_CONTEXT,),
                    scope=REQUEST_SCOPE_EXISTING_CONTEXT,
                    budget=AcquisitionBudget(BUDGET_EXISTING_CONTEXT),
                    freshness=FRESHNESS_NOT_APPLICABLE,
                    require_current_authority=False,
                    reasons=(ACQUIRE_EXPLICIT_TARGET_ANCHOR_PRESERVED,),
                ),
            ),
            reasons=(ACQUIRE_EXPLICIT_TARGET_ANCHOR_PRESERVED,),
            inconsistencies=(INCONSISTENT_EVIDENCE_NOT_SPECIFIED,),
        )


def test_a_requested_class_and_an_excluded_class_can_never_be_the_same_thing():
    """Not a rule enforced at contract level: a disjointness nothing can breach."""
    assert not set(REQUESTABLE_SOURCE_CLASSES) & set(NEVER_REQUESTED_SOURCE_CLASSES)
    assert set(REQUESTABLE_SOURCE_CLASSES) | set(NEVER_REQUESTED_SOURCE_CLASSES) == set(
        ACQUISITION_SOURCE_CLASSES
    )

    with pytest.raises(ValueError):
        SourceExclusion(
            source_class=SOURCE_CLASS_RUNTIME_IMPLEMENTATION,
            disposition=TIER_EXCLUDED_INITIALLY,
            reasons=(ACQUIRE_EXPLICIT_TARGET_ANCHOR_PRESERVED,),
        )


def test_an_anchor_may_only_come_from_explicit_input_evidence():
    with pytest.raises(ValueError):
        TargetAnchor(value="core/router.py", source="repository_scan")


def test_an_anchor_must_carry_something():
    with pytest.raises(ValueError):
        TargetAnchor(value="   ")


def test_anchors_come_only_from_what_input_preserved():
    contract, _ = _handoff(*_EXPLANATION)

    assert preserved_target_anchors(contract) == ()


def test_the_helper_functions_reject_the_wrong_record():
    with pytest.raises(TypeError):
        repository_reach("not a contract")
    with pytest.raises(TypeError):
        preserved_target_anchors("not a contract")
    with pytest.raises(KeyError):
        budget_profile_for("nowhere", TIER_REQUIRED_PRIMARY, REQUEST_SCOPE_EXISTING_CONTEXT)


# ══ Not wired ═════════════════════════════════════════════════════════════════

def test_acquire_1_is_not_reachable_from_any_live_path():
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1]
    callers = []
    for path in root.rglob("*.py"):
        parts = set(path.parts)
        if parts & {"__pycache__", "tmp_tests", ".agent", ".venv", "tests"}:
            continue
        if path.name in (
            "acquisition_request.py",
            "acquisition_policy.py",
            "evidence_acquire_request.py",
        ):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "evidence_acquire_request" in text or "derive_acquisition_requests" in text:
            callers.append(str(path.relative_to(root)))

    assert callers == [], callers
