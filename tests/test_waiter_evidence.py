"""WAITER.2 — deterministic evidence requirement contract tests.

WAITER.1 said which kitchen receives the order.  WAITER.2 says what ingredients
that kitchen should ask for — and asks for none of them.

Three things are proved here.

The **requirement matrix**: an explanation and a pasted-snippet comparison need
only what the order carried with it; a bounded edit needs a bounded repository
requirement; a broad investigation and the DeepSeek Harness dogfood need a
prioritised repository requirement in which implementation, interfaces,
configuration and architecture description come first, validation artifacts come
second, historical material is deferred, and generated or snapshot material is
excluded from the initial set.

The **task sensitivity**: "tests are secondary" is a consequence of the task, not
a global rule.  When the order is about a failing test, validation artifacts are
primary.

The **boundary**: no contract names a file, a path, a query, a provider or a
model; no contract can widen the capability envelope WAITER.1 established; no
contract can change the workflow WAITER.1 selected; and an order WAITER.1 did
not route produces no requirements at all.
"""

from __future__ import annotations

import dataclasses
import json

import pytest

from core.capability_requirements import (
    CAPABILITY_BROAD_REPOSITORY_RECONNAISSANCE,
    CAPABILITY_EXTERNAL_INFORMATION,
    CAPABILITY_NAMES,
    CAPABILITY_PERSISTENT_PROJECT_CONTEXT,
    CAPABILITY_REPOSITORY_READ,
    CAPABILITY_VALIDATION,
    CapabilityRequirement,
    CapabilityRequirements,
    derive_capability_requirements,
)
from core.evidence_requirements import (
    ACTIVE_TIERS,
    CAPABILITY_EVIDENCE_OBLIGATIONS,
    DEFERRED_SOURCE_CLASSES,
    DOMAIN_CAPABILITY_LICENCES,
    DOMAIN_DIRECT_CONTEXT,
    DOMAIN_EXTERNAL_INFORMATION,
    DOMAIN_HISTORICAL_CONTEXT,
    DOMAIN_REPOSITORY,
    DOMAIN_VALIDATION_ARTIFACTS,
    EVIDENCE_ARCHITECTURE_RECON_REQUIRED,
    EVIDENCE_CONTRACT_STATUSES,
    EVIDENCE_DIRECT_CONTEXT_FROM_TASK,
    EVIDENCE_DOMAINS,
    EVIDENCE_EXTERNAL_CURRENT_INFO_REQUIRED,
    EVIDENCE_HISTORY_NON_AUTHORITATIVE,
    EVIDENCE_REASONS,
    EVIDENCE_REASON_DESCRIPTIONS,
    EVIDENCE_REPOSITORY_REQUIRED,
    EVIDENCE_REQUIRED_CAPABILITY_LOST,
    EVIDENCE_ROLES,
    EVIDENCE_SCOPES,
    EVIDENCE_TESTS_ARE_THE_SUBJECT,
    EVIDENCE_TESTS_FOR_VERIFICATION,
    EVIDENCE_TIERS,
    INCONSISTENT_CAPABILITY_ENVELOPE_WIDENED,
    INCONSISTENT_REQUIRED_CAPABILITY_DROPPED,
    INCONSISTENT_SOURCE_FINGERPRINT_MISMATCH,
    INCONSISTENT_WAITER_NOT_ROUTED,
    ROLE_ARCHITECTURE_DESCRIPTION,
    ROLE_CONFIGURATION_AUTHORITY,
    ROLE_CURRENT_EXTERNAL_AUTHORITY,
    ROLE_HISTORICAL_CONTEXT,
    ROLE_IMPLEMENTATION_AUTHORITY,
    ROLE_INTERFACE_CONTRACT,
    ROLE_SUPPLIED_MATERIAL,
    ROLE_VALIDATION_EVIDENCE,
    SCOPE_BOUNDED_REPOSITORY,
    SCOPE_BROAD_REPOSITORY_RECONNAISSANCE,
    SCOPE_DIRECT_CONTEXT_ONLY,
    SCOPE_EXTERNAL_ONLY,
    SCOPE_MIXED_SOURCES,
    SOURCE_CLASS_GENERATED_ARTIFACTS,
    SOURCE_CLASS_SNAPSHOTS,
    STATUS_INCONSISTENT_INPUT,
    STATUS_NOT_ROUTED,
    STATUS_SPECIFIED,
    TIER_DEFERRED,
    TIER_EXCLUDED_INITIALLY,
    TIER_REQUIRED_PRIMARY,
    TIER_REQUIRED_SECONDARY,
    VERIFY_CURRENT_IMPLEMENTATION_OVER_HISTORY,
    VERIFY_EXTERNAL_INFORMATION_CURRENCY,
    VERIFY_SUPPLIED_MATERIAL_IS_THE_WHOLE_SET,
    EvidenceRequirement,
    EvidenceRequirementContract,
    check_capability_envelope,
    check_required_capability_coverage,
    evidence_authority,
)
from core.execution_waiter import (
    STATUS_ROUTED,
    WORKFLOW_CHAT,
    WORKFLOW_COMMANDER,
    WORKFLOW_INSTANT_RUN,
    WORKFLOW_PROJECT_EVOLUTION,
    WaiterDecision,
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
from core.evidence_policy import EvidencePolicy, carries_direct_context_material
from core.waiter_evidence import (
    canonical_evidence_fingerprint,
    canonical_evidence_shape,
    derive_evidence_requirements,
    render_evidence_contract_json,
)


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


def _evidence(prompt: str, payload: dict, **kwargs):
    """Route one order, then specify what its workflow will need."""
    contract, completion = _handoff(prompt, payload)
    decision = route_execution_workflow(contract, completion, **kwargs)
    return decision, derive_evidence_requirements(decision, contract, completion)


def _contract_for(prompt: str, payload: dict, **kwargs) -> EvidenceRequirementContract:
    return _evidence(prompt, payload, **kwargs)[1]


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


_EXPLANATION = ("Explain the Bellman equation.", {"task": {"type": "question", "provenance": "inferred"}})

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

_SIMPLE_EXTERNAL_LOOKUP = (
    "What changed in the latest release of the requests library?",
    {
        "task": {"type": "question", "provenance": "inferred"},
        "execution_requirements": {"external_information_required": True},
    },
)

#: The order pastes the material it wants checked *and* needs a current external
#: fact to check it against.  WAITER.1 answers external first when it picks a
#: single scope, so the direct-context half is invisible in the shape and has to
#: survive in WAITER.2's requirement set instead.
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


def _evolution_declaration(contract) -> ProjectEvolutionRequest:
    return ProjectEvolutionRequest(
        evidence_text="Continue evolving this project through the roadmap phases",
        declared_by=DECLARATION_SOURCE_HUMAN_DECLARED_WORKFLOW_INTENT,
        source_raw_request_sha256=contract.raw_request.sha256,
    )


def _evolution_evidence():
    contract, completion = _handoff(_EVOLUTION_PROMPT, _EVOLUTION_INTERPRETATION)
    decision = route_execution_workflow(
        contract,
        completion,
        project_evolution_request=_evolution_declaration(contract),
    )
    return decision, derive_evidence_requirements(decision, contract, completion)


# ══ A — a chat explanation needs nothing but the order ════════════════════════

def test_case_a_explanation_requires_direct_context_and_no_repository():
    evidence = _contract_for(*_EXPLANATION)

    assert evidence.status == STATUS_SPECIFIED
    assert evidence.workflow == WORKFLOW_CHAT
    assert evidence.scope == SCOPE_DIRECT_CONTEXT_ONLY
    assert evidence.domains() == (DOMAIN_DIRECT_CONTEXT,)
    assert evidence.requires_domain(DOMAIN_REPOSITORY) is False
    assert evidence.requires_domain(DOMAIN_EXTERNAL_INFORMATION) is False
    assert evidence.requires_domain(DOMAIN_VALIDATION_ARTIFACTS) is False
    assert EVIDENCE_DIRECT_CONTEXT_FROM_TASK in evidence.reasons


# ══ B — a pasted comparison needs only what was pasted ════════════════════════

def test_case_b_pasted_comparison_requires_direct_context_only():
    evidence = _contract_for(_PASTED_COMPARISON, _PASTED_COMPARISON_INTERPRETATION)

    assert evidence.workflow == WORKFLOW_CHAT
    assert evidence.scope == SCOPE_DIRECT_CONTEXT_ONLY
    assert evidence.domains() == (DOMAIN_DIRECT_CONTEXT,)
    assert evidence.roles() == (ROLE_SUPPLIED_MATERIAL,)


def test_case_b_a_direct_context_order_defers_nothing_and_excludes_nothing():
    """Nothing is deferred when nothing outside the order was ever in scope."""
    evidence = _contract_for(_PASTED_COMPARISON, _PASTED_COMPARISON_INTERPRETATION)

    assert evidence.deferred_sources == ()


# ══ C — a bounded edit needs a bounded repository requirement ═════════════════

def test_case_c_readme_edit_requires_bounded_repository_evidence():
    evidence = _contract_for(*_README_EDIT)

    assert evidence.workflow == WORKFLOW_INSTANT_RUN
    assert evidence.scope == SCOPE_BOUNDED_REPOSITORY
    assert evidence.requires_domain(DOMAIN_REPOSITORY) is True
    assert (
        evidence.tier_of(DOMAIN_REPOSITORY, ROLE_IMPLEMENTATION_AUTHORITY)
        == TIER_REQUIRED_PRIMARY
    )
    assert EVIDENCE_REPOSITORY_REQUIRED in evidence.reasons


def test_case_c_a_bounded_edit_asks_for_no_architecture_survey():
    evidence = _contract_for(*_README_EDIT)

    assert EVIDENCE_ARCHITECTURE_RECON_REQUIRED not in evidence.reasons
    assert ROLE_ARCHITECTURE_DESCRIPTION not in evidence.roles()
    assert ROLE_HISTORICAL_CONTEXT not in evidence.roles()


def test_case_c_a_change_carries_its_validation_requirement():
    evidence = _contract_for(*_README_EDIT)

    assert (
        evidence.tier_of(DOMAIN_VALIDATION_ARTIFACTS, ROLE_VALIDATION_EVIDENCE)
        == TIER_REQUIRED_SECONDARY
    )
    assert EVIDENCE_TESTS_FOR_VERIFICATION in evidence.reasons


# ══ D — a one-file implementation is the same shape ═══════════════════════════

def test_case_d_one_file_implementation_requires_bounded_repository_evidence():
    evidence = _contract_for(*_ONE_FILE_IMPLEMENTATION)

    assert evidence.workflow == WORKFLOW_INSTANT_RUN
    assert evidence.scope == SCOPE_BOUNDED_REPOSITORY
    assert (
        evidence.tier_of(DOMAIN_REPOSITORY, ROLE_IMPLEMENTATION_AUTHORITY)
        == TIER_REQUIRED_PRIMARY
    )


# ══ E — a broad investigation needs a prioritised repository requirement ══════

def test_case_e_broad_investigation_requires_reconnaissance_evidence():
    evidence = _contract_for(*_BROAD_DEBUGGING)

    assert evidence.workflow == WORKFLOW_COMMANDER
    assert evidence.scope == SCOPE_BROAD_REPOSITORY_RECONNAISSANCE
    assert ROLE_IMPLEMENTATION_AUTHORITY in evidence.roles_at(TIER_REQUIRED_PRIMARY)
    assert ROLE_CONFIGURATION_AUTHORITY in evidence.roles_at(TIER_REQUIRED_PRIMARY)
    assert EVIDENCE_ARCHITECTURE_RECON_REQUIRED in evidence.reasons


def test_case_e_validation_evidence_is_secondary_for_a_broad_investigation():
    evidence = _contract_for(*_BROAD_DEBUGGING)

    assert evidence.requires_domain(DOMAIN_VALIDATION_ARTIFACTS) is True
    assert ROLE_VALIDATION_EVIDENCE not in evidence.roles_at(TIER_REQUIRED_PRIMARY)


# ══ F — the DeepSeek Harness dogfood ══════════════════════════════════════════

def _dogfood_evidence() -> EvidenceRequirementContract:
    return _contract_for(DOGFOOD_PROMPT, _dogfood_interpretation(BROAD_REPOSITORY))


def test_case_f_dogfood_scope_is_broad_repository_reconnaissance():
    evidence = _dogfood_evidence()

    assert evidence.workflow == WORKFLOW_COMMANDER
    assert evidence.scope == SCOPE_BROAD_REPOSITORY_RECONNAISSANCE


def test_case_f_dogfood_primary_evidence_is_implementation_not_tests():
    """The failure this phase exists to fix: 6,087 files, no priority."""
    evidence = _dogfood_evidence()
    primary = evidence.roles_at(TIER_REQUIRED_PRIMARY)

    assert ROLE_IMPLEMENTATION_AUTHORITY in primary
    assert ROLE_INTERFACE_CONTRACT in primary
    assert ROLE_CONFIGURATION_AUTHORITY in primary
    assert ROLE_ARCHITECTURE_DESCRIPTION in primary
    assert ROLE_VALIDATION_EVIDENCE not in primary


def test_case_f_dogfood_validation_evidence_is_secondary():
    evidence = _dogfood_evidence()

    assert (
        evidence.tier_of(DOMAIN_VALIDATION_ARTIFACTS, ROLE_VALIDATION_EVIDENCE)
        == TIER_REQUIRED_SECONDARY
    )
    assert EVIDENCE_TESTS_FOR_VERIFICATION in evidence.reasons


def test_case_f_dogfood_history_is_deferred_and_never_current_authority():
    evidence = _dogfood_evidence()

    assert (
        evidence.tier_of(DOMAIN_HISTORICAL_CONTEXT, ROLE_HISTORICAL_CONTEXT)
        == TIER_DEFERRED
    )
    assert ROLE_HISTORICAL_CONTEXT not in evidence.roles_at(TIER_REQUIRED_PRIMARY)
    assert ROLE_IMPLEMENTATION_AUTHORITY not in evidence.roles_at(TIER_DEFERRED)
    assert EVIDENCE_HISTORY_NON_AUTHORITATIVE in evidence.reasons
    assert VERIFY_CURRENT_IMPLEMENTATION_OVER_HISTORY in evidence.verification_requirements


def test_case_f_dogfood_excludes_generated_and_snapshot_material_initially():
    evidence = _dogfood_evidence()

    assert SOURCE_CLASS_GENERATED_ARTIFACTS in evidence.excluded_classes()
    assert SOURCE_CLASS_SNAPSHOTS in evidence.excluded_classes()


def test_case_f_dogfood_names_no_file_no_path_and_no_query():
    """A requirement contract is not a read set."""
    rendered = json.dumps(
        _without_authority(_dogfood_evidence().as_dict()), ensure_ascii=False
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
        "candidates",
        "search_query",
        "http",
    ):
        assert forbidden not in rendered, forbidden


# ══ G — the same comparison over supplied context needs nothing else ══════════

def test_case_g_direct_context_dogfood_requires_direct_context_only():
    evidence = _contract_for(DOGFOOD_PROMPT, _dogfood_interpretation({}))

    assert evidence.workflow == WORKFLOW_CHAT
    assert evidence.scope == SCOPE_DIRECT_CONTEXT_ONLY
    assert evidence.domains() == (DOMAIN_DIRECT_CONTEXT,)
    assert evidence.requires_domain(DOMAIN_REPOSITORY) is False
    assert evidence.requires_domain(DOMAIN_VALIDATION_ARTIFACTS) is False
    assert evidence.requires_domain(DOMAIN_HISTORICAL_CONTEXT) is False


# ══ H — repository plus current external information ══════════════════════════

def test_case_h_repository_and_external_evidence_is_mixed_sources():
    evidence = _contract_for(*_REPO_PLUS_EXTERNAL)

    assert evidence.workflow == WORKFLOW_COMMANDER
    assert evidence.scope == SCOPE_MIXED_SOURCES
    assert evidence.requires_domain(DOMAIN_REPOSITORY) is True
    assert evidence.requires_domain(DOMAIN_EXTERNAL_INFORMATION) is True
    assert (
        evidence.tier_of(DOMAIN_EXTERNAL_INFORMATION, ROLE_CURRENT_EXTERNAL_AUTHORITY)
        == TIER_REQUIRED_PRIMARY
    )
    assert EVIDENCE_EXTERNAL_CURRENT_INFO_REQUIRED in evidence.reasons


def test_case_h_external_only_asks_for_no_repository_evidence():
    evidence = _contract_for(*_EXTERNAL_ONLY)

    assert evidence.workflow == WORKFLOW_CHAT
    assert evidence.scope == SCOPE_EXTERNAL_ONLY
    assert evidence.requires_domain(DOMAIN_EXTERNAL_INFORMATION) is True
    assert evidence.requires_domain(DOMAIN_REPOSITORY) is False


def test_case_h_no_contract_chooses_a_search_engine_or_a_url():
    rendered = json.dumps(
        _without_authority(_contract_for(*_REPO_PLUS_EXTERNAL).as_dict()),
        ensure_ascii=False,
    ).lower()

    for forbidden in ("google", "bing", "duckduckgo", "http", "www.", "api", "url"):
        assert forbidden not in rendered, forbidden


# == H2 - the closure case: external evidence is never quietly dropped =========
#
# WAITER.1 deliberately leaves a simple current-fact lookup on the CHAT route:
# needing something from outside the repository is not, by itself, a reason to
# wake Commander.  The risk that creates is downstream.  A layer that answered
# "chat, therefore whatever the user pasted is the whole evidence set" would
# silently turn a question about the world into a question about the prompt, and
# nothing in the record would say a smaller question had been substituted.


def test_case_h2_a_simple_external_lookup_stays_chat_and_keeps_its_external_domain():
    decision, evidence = _evidence(*_SIMPLE_EXTERNAL_LOOKUP)

    assert decision.recommended_workflow == WORKFLOW_CHAT
    assert decision.requires(CAPABILITY_EXTERNAL_INFORMATION) is True
    assert evidence.workflow == WORKFLOW_CHAT
    assert evidence.requires_domain(DOMAIN_EXTERNAL_INFORMATION) is True
    assert (
        evidence.tier_of(DOMAIN_EXTERNAL_INFORMATION, ROLE_CURRENT_EXTERNAL_AUTHORITY)
        == TIER_REQUIRED_PRIMARY
    )


def test_case_h2_a_simple_external_lookup_is_never_reduced_to_direct_context():
    """The exact reduction this closure check exists to forbid."""
    evidence = _contract_for(*_SIMPLE_EXTERNAL_LOOKUP)

    assert evidence.scope != SCOPE_DIRECT_CONTEXT_ONLY
    assert evidence.scope == SCOPE_EXTERNAL_ONLY
    assert VERIFY_EXTERNAL_INFORMATION_CURRENCY in evidence.verification_requirements
    assert (
        VERIFY_SUPPLIED_MATERIAL_IS_THE_WHOLE_SET
        not in evidence.verification_requirements
    )


def test_case_h2_supplied_material_plus_external_reaches_both_kinds_of_source():
    contract, _ = _handoff(*_DIRECT_PLUS_EXTERNAL)
    evidence = _contract_for(*_DIRECT_PLUS_EXTERNAL)

    assert carries_direct_context_material(contract) is True
    assert evidence.scope == SCOPE_MIXED_SOURCES
    assert evidence.domains() == (DOMAIN_DIRECT_CONTEXT, DOMAIN_EXTERNAL_INFORMATION)
    assert (
        evidence.tier_of(DOMAIN_DIRECT_CONTEXT, ROLE_SUPPLIED_MATERIAL)
        == TIER_REQUIRED_PRIMARY
    )
    assert (
        evidence.tier_of(DOMAIN_EXTERNAL_INFORMATION, ROLE_CURRENT_EXTERNAL_AUTHORITY)
        == TIER_REQUIRED_PRIMARY
    )


def test_case_h2_an_order_that_carries_nothing_stays_external_only():
    """The refinement moves one case and no other."""
    contract, _ = _handoff(*_SIMPLE_EXTERNAL_LOOKUP)

    assert carries_direct_context_material(contract) is False
    assert _contract_for(*_SIMPLE_EXTERNAL_LOOKUP).scope == SCOPE_EXTERNAL_ONLY


def test_case_h2_external_evidence_does_not_by_itself_summon_commander():
    """External evidence is a source, not a workflow class."""
    for prompt, payload in (
        _SIMPLE_EXTERNAL_LOOKUP,
        _EXTERNAL_ONLY,
        _DIRECT_PLUS_EXTERNAL,
    ):
        decision, evidence = _evidence(prompt, payload)

        assert decision.recommended_workflow == WORKFLOW_CHAT, prompt
        assert evidence.workflow == WORKFLOW_CHAT, prompt
        assert evidence.requires_domain(DOMAIN_REPOSITORY) is False, prompt


def test_case_h2_a_chat_external_contract_still_names_no_engine_and_no_query():
    for prompt, payload in (_SIMPLE_EXTERNAL_LOOKUP, _DIRECT_PLUS_EXTERNAL):
        rendered = json.dumps(
            _without_authority(_contract_for(prompt, payload).as_dict()),
            ensure_ascii=False,
        ).lower()

        for forbidden in ("google", "bing", "duckduckgo", "http", "www.", "search_query"):
            assert forbidden not in rendered, forbidden


# == H3 - no required capability may be lost ==================================
#
# The licence table refuses to widen the envelope.  Read the other way it is a
# closure rule, and the two together are what "faithful" means: not wider, and
# not narrower where evidence is required.


def _capabilities_requiring(*names: str) -> CapabilityRequirements:
    """A hand-built envelope, to exercise a policy that lost something."""
    return CapabilityRequirements(
        requirements=tuple(
            CapabilityRequirement(
                name=name,
                value=name in names,
                reasons=(("task_shape.evidence_scope=hand_built",) if name in names else ()),
            )
            for name in CAPABILITY_NAMES
        )
    )


def _all_fixtures():
    return (
        _EXPLANATION,
        (_PASTED_COMPARISON, _PASTED_COMPARISON_INTERPRETATION),
        _README_EDIT,
        _ONE_FILE_IMPLEMENTATION,
        _BROAD_DEBUGGING,
        _TEST_FOCUSED_DEBUGGING,
        _REPO_PLUS_EXTERNAL,
        _EXTERNAL_ONLY,
        _SIMPLE_EXTERNAL_LOOKUP,
        _DIRECT_PLUS_EXTERNAL,
        (DOGFOOD_PROMPT, _dogfood_interpretation(BROAD_REPOSITORY)),
        (DOGFOOD_PROMPT, _dogfood_interpretation({})),
    )


def test_every_capability_states_what_evidence_it_obliges():
    """A capability added upstream cannot slip through by never being considered."""
    assert tuple(CAPABILITY_EVIDENCE_OBLIGATIONS) == CAPABILITY_NAMES
    for name, obligations in CAPABILITY_EVIDENCE_OBLIGATIONS.items():
        for domain, role in obligations:
            assert domain in EVIDENCE_DOMAINS, name
            assert role in EVIDENCE_ROLES, name


def test_no_derived_contract_drops_a_required_evidence_capability():
    for prompt, payload in _all_fixtures():
        decision, evidence = _evidence(prompt, payload)

        assert (
            check_required_capability_coverage(
                evidence.requirements, decision.capability_requirements
            )
            == ()
        ), prompt


def test_the_project_evolution_contract_drops_no_required_capability():
    decision, evidence = _evolution_evidence()

    assert (
        check_required_capability_coverage(
            evidence.requirements, decision.capability_requirements
        )
        == ()
    )


def test_a_missing_external_requirement_is_a_dropped_capability():
    """The failure the precheck names: external required upstream, absent here."""
    only_direct = (
        EvidenceRequirement(
            domain=DOMAIN_DIRECT_CONTEXT,
            role=ROLE_SUPPLIED_MATERIAL,
            tier=TIER_REQUIRED_PRIMARY,
            reasons=(EVIDENCE_DIRECT_CONTEXT_FROM_TASK,),
        ),
    )
    capabilities = _capabilities_requiring(CAPABILITY_EXTERNAL_INFORMATION)

    assert check_required_capability_coverage(only_direct, capabilities) == (
        INCONSISTENT_REQUIRED_CAPABILITY_DROPPED,
    )


def test_a_deferred_requirement_does_not_discharge_a_required_capability():
    """Deferred material is on the record and out of the work."""
    deferred_external = (
        EvidenceRequirement(
            domain=DOMAIN_EXTERNAL_INFORMATION,
            role=ROLE_CURRENT_EXTERNAL_AUTHORITY,
            tier=TIER_DEFERRED,
            reasons=(EVIDENCE_EXTERNAL_CURRENT_INFO_REQUIRED,),
        ),
    )
    capabilities = _capabilities_requiring(CAPABILITY_EXTERNAL_INFORMATION)

    assert check_required_capability_coverage(deferred_external, capabilities) == (
        INCONSISTENT_REQUIRED_CAPABILITY_DROPPED,
    )
    assert TIER_DEFERRED not in ACTIVE_TIERS


def test_broad_reconnaissance_obliges_the_seams_and_not_only_the_code():
    implementation_only = (
        EvidenceRequirement(
            domain=DOMAIN_REPOSITORY,
            role=ROLE_IMPLEMENTATION_AUTHORITY,
            tier=TIER_REQUIRED_PRIMARY,
            reasons=(EVIDENCE_ARCHITECTURE_RECON_REQUIRED,),
        ),
    )
    capabilities = _capabilities_requiring(
        CAPABILITY_REPOSITORY_READ, CAPABILITY_BROAD_REPOSITORY_RECONNAISSANCE
    )

    assert check_required_capability_coverage(implementation_only, capabilities) == (
        INCONSISTENT_REQUIRED_CAPABILITY_DROPPED,
    )


def test_a_required_validation_capability_is_not_answered_with_code_alone():
    capabilities = _capabilities_requiring(
        CAPABILITY_REPOSITORY_READ, CAPABILITY_VALIDATION
    )
    code_only = (
        EvidenceRequirement(
            domain=DOMAIN_REPOSITORY,
            role=ROLE_IMPLEMENTATION_AUTHORITY,
            tier=TIER_REQUIRED_PRIMARY,
            reasons=(EVIDENCE_REPOSITORY_REQUIRED,),
        ),
    )

    assert check_required_capability_coverage(code_only, capabilities) == (
        INCONSISTENT_REQUIRED_CAPABILITY_DROPPED,
    )


def test_a_dropped_capability_fails_the_whole_contract_closed(monkeypatch):
    """End to end: the orchestrator refuses rather than shipping a smaller order."""
    import core.waiter_evidence as waiter_evidence

    contract, completion = _handoff(*_SIMPLE_EXTERNAL_LOOKUP)
    decision = route_execution_workflow(contract, completion)

    def _narrowed(shape, capabilities, task_contract):
        return EvidencePolicy(
            scope=SCOPE_DIRECT_CONTEXT_ONLY,
            requirements=(
                EvidenceRequirement(
                    domain=DOMAIN_DIRECT_CONTEXT,
                    role=ROLE_SUPPLIED_MATERIAL,
                    tier=TIER_REQUIRED_PRIMARY,
                    reasons=(EVIDENCE_DIRECT_CONTEXT_FROM_TASK,),
                ),
            ),
        )

    monkeypatch.setattr(waiter_evidence, "derive_evidence_policy", _narrowed)
    evidence = waiter_evidence.derive_evidence_requirements(decision, contract, completion)

    assert evidence.status == STATUS_INCONSISTENT_INPUT
    assert evidence.inconsistencies == (INCONSISTENT_REQUIRED_CAPABILITY_DROPPED,)
    assert evidence.reasons == (EVIDENCE_REQUIRED_CAPABILITY_LOST,)
    assert evidence.requirements == ()
    assert evidence.workflow is None


# ══ I — explicit project evolution ════════════════════════════════════════════

def test_case_i_project_evolution_evidence_reflects_persistent_context():
    decision, evidence = _evolution_evidence()

    assert decision.recommended_workflow == WORKFLOW_PROJECT_EVOLUTION
    assert decision.requires(CAPABILITY_PERSISTENT_PROJECT_CONTEXT) is True
    assert evidence.workflow == WORKFLOW_PROJECT_EVOLUTION
    assert evidence.scope == SCOPE_BROAD_REPOSITORY_RECONNAISSANCE
    assert evidence.requires_domain(DOMAIN_REPOSITORY) is True


def test_case_i_project_evolution_evidence_starts_no_project_execution():
    _, evidence = _evolution_evidence()
    authority = evidence.as_dict()["authority"]

    assert authority["execution_authority"] is False
    assert authority["project_evolution_authority"] is False
    assert authority["repository_read_authority"] is False
    assert authority["human_approval_required"] is True


# ══ J — tests are secondary only when the task is not about tests ═════════════

def test_case_j_a_failing_test_investigation_makes_validation_evidence_primary():
    evidence = _contract_for(*_TEST_FOCUSED_DEBUGGING)

    assert (
        evidence.tier_of(DOMAIN_VALIDATION_ARTIFACTS, ROLE_VALIDATION_EVIDENCE)
        == TIER_REQUIRED_PRIMARY
    )
    assert EVIDENCE_TESTS_ARE_THE_SUBJECT in evidence.reasons


def test_case_j_tests_are_not_globally_secondary():
    """The differential that proves the rule is task-aware, not a constant."""
    subject = _contract_for(*_TEST_FOCUSED_DEBUGGING)
    instrument = _dogfood_evidence()

    assert (
        subject.tier_of(DOMAIN_VALIDATION_ARTIFACTS, ROLE_VALIDATION_EVIDENCE)
        == TIER_REQUIRED_PRIMARY
    )
    assert (
        instrument.tier_of(DOMAIN_VALIDATION_ARTIFACTS, ROLE_VALIDATION_EVIDENCE)
        == TIER_REQUIRED_SECONDARY
    )


# ══ K — an unrouted order produces no evidence contract ═══════════════════════

def test_case_k_an_unrouted_order_specifies_no_evidence():
    contract, completion = _handoff(*_EXPLANATION)
    blocked = dataclasses.replace(
        route_execution_workflow(contract, completion),
        status="uncertain",
        recommended_workflow=None,
        reasons=("ROUTE_UNCERTAIN_TASK_SHAPE_UNDETERMINED",),
        disqualifiers=("task_shape_unknown",),
    )
    evidence = derive_evidence_requirements(blocked, contract, completion)

    assert evidence.status == STATUS_NOT_ROUTED
    assert evidence.workflow is None
    assert evidence.scope is None
    assert evidence.requirements == ()
    assert INCONSISTENT_WAITER_NOT_ROUTED in evidence.inconsistencies


def test_case_k_a_blocked_handoff_specifies_no_evidence():
    contract, completion = _handoff(*_EXPLANATION)
    decision = route_execution_workflow(None, completion)
    evidence = derive_evidence_requirements(decision, None, completion)

    assert evidence.status == STATUS_NOT_ROUTED
    assert evidence.requirements == ()


# ══ L — tampered source integrity is refused ══════════════════════════════════

def test_case_l_a_tampered_source_fingerprint_is_refused():
    contract, completion = _handoff(*_README_EDIT)
    decision = route_execution_workflow(contract, completion)
    tampered = dataclasses.replace(
        decision,
        receipt=dataclasses.replace(
            decision.receipt, source_contract_fingerprint="0" * 64
        ),
    )
    evidence = derive_evidence_requirements(tampered, contract, completion)

    assert evidence.status == STATUS_INCONSISTENT_INPUT
    assert INCONSISTENT_SOURCE_FINGERPRINT_MISMATCH in evidence.inconsistencies
    assert evidence.requirements == ()


def test_case_l_a_contract_from_another_order_is_refused():
    contract, completion = _handoff(*_README_EDIT)
    other_contract, other_completion = _handoff(*_EXPLANATION)
    decision = route_execution_workflow(contract, completion)
    evidence = derive_evidence_requirements(decision, other_contract, other_completion)

    assert evidence.status == STATUS_INCONSISTENT_INPUT
    assert INCONSISTENT_SOURCE_FINGERPRINT_MISMATCH in evidence.inconsistencies


# ══ M — no capability escalation ══════════════════════════════════════════════

def _capabilities_without_repository() -> CapabilityRequirements:
    contract, completion = _handoff(*_EXPLANATION)
    decision = route_execution_workflow(contract, completion)
    return decision.capability_requirements


def test_case_m_a_repository_requirement_outside_the_envelope_is_rejected():
    widened = (
        EvidenceRequirement(
            domain=DOMAIN_REPOSITORY,
            role=ROLE_IMPLEMENTATION_AUTHORITY,
            tier=TIER_REQUIRED_PRIMARY,
            reasons=(EVIDENCE_REPOSITORY_REQUIRED,),
        ),
    )
    violations = check_capability_envelope(widened, _capabilities_without_repository())

    assert INCONSISTENT_CAPABILITY_ENVELOPE_WIDENED in violations


def test_case_m_an_external_requirement_outside_the_envelope_is_rejected():
    widened = (
        EvidenceRequirement(
            domain=DOMAIN_EXTERNAL_INFORMATION,
            role=ROLE_CURRENT_EXTERNAL_AUTHORITY,
            tier=TIER_REQUIRED_PRIMARY,
            reasons=(EVIDENCE_EXTERNAL_CURRENT_INFO_REQUIRED,),
        ),
    )
    violations = check_capability_envelope(widened, _capabilities_without_repository())

    assert INCONSISTENT_CAPABILITY_ENVELOPE_WIDENED in violations


def test_case_m_direct_context_is_always_inside_the_envelope():
    inside = (
        EvidenceRequirement(
            domain=DOMAIN_DIRECT_CONTEXT,
            role=ROLE_SUPPLIED_MATERIAL,
            tier=TIER_REQUIRED_PRIMARY,
            reasons=(EVIDENCE_DIRECT_CONTEXT_FROM_TASK,),
        ),
    )

    assert check_capability_envelope(inside, _capabilities_without_repository()) == ()


def test_case_m_every_derived_contract_stays_inside_its_envelope():
    for prompt, payload in (
        _EXPLANATION,
        _README_EDIT,
        _ONE_FILE_IMPLEMENTATION,
        _BROAD_DEBUGGING,
        _TEST_FOCUSED_DEBUGGING,
        _REPO_PLUS_EXTERNAL,
        _EXTERNAL_ONLY,
        (DOGFOOD_PROMPT, _dogfood_interpretation(BROAD_REPOSITORY)),
        (DOGFOOD_PROMPT, _dogfood_interpretation({})),
    ):
        decision, evidence = _evidence(prompt, payload)
        assert evidence.status == STATUS_SPECIFIED, prompt
        assert (
            check_capability_envelope(
                evidence.requirements, decision.capability_requirements
            )
            == ()
        ), prompt


def test_case_m_repository_evidence_never_appears_without_the_upstream_capability():
    for prompt, payload in (
        _EXPLANATION,
        (_PASTED_COMPARISON, _PASTED_COMPARISON_INTERPRETATION),
        _EXTERNAL_ONLY,
    ):
        decision, evidence = _evidence(prompt, payload)
        assert decision.requires(CAPABILITY_REPOSITORY_READ) is False, prompt
        assert evidence.requires_domain(DOMAIN_REPOSITORY) is False, prompt
        assert evidence.requires_domain(DOMAIN_VALIDATION_ARTIFACTS) is False, prompt
        assert evidence.requires_domain(DOMAIN_HISTORICAL_CONTEXT) is False, prompt


# ══ N — no workflow escalation ════════════════════════════════════════════════

def test_case_n_the_evidence_contract_never_changes_the_workflow():
    for prompt, payload in (
        _EXPLANATION,
        (_PASTED_COMPARISON, _PASTED_COMPARISON_INTERPRETATION),
        _README_EDIT,
        _BROAD_DEBUGGING,
        (DOGFOOD_PROMPT, _dogfood_interpretation(BROAD_REPOSITORY)),
        (DOGFOOD_PROMPT, _dogfood_interpretation({})),
    ):
        decision, evidence = _evidence(prompt, payload)
        assert evidence.workflow == decision.recommended_workflow, prompt


def test_case_n_a_chat_order_is_never_promoted_by_its_evidence_needs():
    decision, evidence = _evidence(DOGFOOD_PROMPT, _dogfood_interpretation({}))

    assert decision.recommended_workflow == WORKFLOW_CHAT
    assert evidence.workflow == WORKFLOW_CHAT
    assert evidence.workflow != WORKFLOW_COMMANDER


def test_case_n_the_policy_layer_cannot_reach_a_router():
    """A static proof, so the boundary cannot be lost to a future refactor."""
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1] / "core"
    source = (root / "evidence_policy.py").read_text(encoding="utf-8")

    for forbidden in (
        "select_workflow",
        "route_execution_workflow",
        "mode_router",
        "context_selection",
    ):
        assert forbidden not in source, forbidden


def test_case_n_a_mutated_workflow_no_longer_matches_its_source_decision():
    decision, evidence = _evidence(*_README_EDIT)
    forged = dataclasses.replace(evidence, workflow=WORKFLOW_COMMANDER)

    assert canonical_evidence_fingerprint(evidence) != canonical_evidence_fingerprint(
        forged
    )
    assert evidence.workflow == decision.recommended_workflow


# ══ O — the contract is structural, not linguistic ════════════════════════════

def test_case_o_english_and_vietnamese_orders_specify_identical_evidence():
    english = _contract_for(
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
    vietnamese = _contract_for(
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

    assert canonical_evidence_shape(english) == canonical_evidence_shape(vietnamese)


def test_case_o_a_vietnamese_explanation_needs_only_direct_context():
    evidence = _contract_for(
        "Giải thích phương trình Bellman.",
        {"task": {"type": "question", "provenance": "inferred"}},
    )

    assert evidence.scope == SCOPE_DIRECT_CONTEXT_ONLY
    assert evidence.domains() == (DOMAIN_DIRECT_CONTEXT,)


# ══ The dogfood differential regression ═══════════════════════════════════════

def test_the_dogfood_differential_depends_on_capability_needs_not_the_word_compare():
    broad = _dogfood_evidence()
    direct = _contract_for(DOGFOOD_PROMPT, _dogfood_interpretation({}))

    assert broad.workflow == WORKFLOW_COMMANDER
    assert direct.workflow == WORKFLOW_CHAT
    assert broad.scope == SCOPE_BROAD_REPOSITORY_RECONNAISSANCE
    assert direct.scope == SCOPE_DIRECT_CONTEXT_ONLY
    assert DOMAIN_REPOSITORY in broad.domains()
    assert DOMAIN_REPOSITORY not in direct.domains()
    # Identical comparison semantics on both sides.
    assert DOMAIN_DIRECT_CONTEXT in broad.domains()
    assert DOMAIN_DIRECT_CONTEXT in direct.domains()


def test_scope_never_counts_repository_members():
    """WAITER.2 does not know what the repository contains."""
    rendered = json.dumps(
        canonical_evidence_shape(_dogfood_evidence()), ensure_ascii=False
    )

    for forbidden in ("6087", "6,087", "file_count", "number_of_files", "total_files"):
        assert forbidden not in rendered, forbidden


# ══ No model, no provider, no compute ═════════════════════════════════════════

_COMPUTE_TOKENS: tuple[str, ...] = (
    "gemini",
    "gemma",
    "qwen",
    "claude",
    "gpt",
    "ollama",
    "cloud",
    "provider",
    "model",
    "context window",
    "num_ctx",
    "temperature",
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
        (DOGFOOD_PROMPT, _dogfood_interpretation(BROAD_REPOSITORY)),
    ],
)
def test_no_evidence_contract_names_a_model_or_a_provider(prompt, payload):
    rendered = json.dumps(
        _without_authority(_contract_for(prompt, payload).as_dict()), ensure_ascii=False
    ).lower()

    for token in _COMPUTE_TOKENS:
        assert token not in rendered, token


# ══ Authority ═════════════════════════════════════════════════════════════════

def test_the_evidence_phase_holds_no_acquisition_authority():
    authority = evidence_authority()

    for power in (
        "repository_read_authority",
        "repository_write_authority",
        "external_search_authority",
        "context_selection_authority",
        "indexing_authority",
        "graph_authority",
        "execution_authority",
        "patch_authority",
        "validation_authority",
        "work" + "er_launch_authority",
        "provider_selection_authority",
        "model_selection_authority",
        "planning_authority",
        "project_evolution_authority",
    ):
        assert authority[power] is False, power
    assert authority["human_approval_required"] is True


def test_a_required_evidence_domain_grants_nothing():
    evidence = _dogfood_evidence()
    authority = evidence.as_dict()["authority"]

    assert evidence.requires_domain(DOMAIN_REPOSITORY) is True
    assert authority["repository_read_authority"] is False
    assert evidence.human_approval_required is True


def test_no_evidence_module_can_reach_a_file_a_process_or_a_network():
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1] / "core"
    for name in ("evidence_requirements.py", "evidence_policy.py", "waiter_evidence.py"):
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


# ══ Determinism ═══════════════════════════════════════════════════════════════

def test_the_same_order_always_specifies_the_same_evidence():
    first = _dogfood_evidence()
    second = _dogfood_evidence()

    assert canonical_evidence_fingerprint(first) == canonical_evidence_fingerprint(second)
    assert render_evidence_contract_json(first) == render_evidence_contract_json(second)


def test_an_evidence_contract_renders_as_deterministic_json():
    rendered = render_evidence_contract_json(_dogfood_evidence())
    payload = json.loads(rendered)

    assert payload["phase_id"] == "WAITER.2"
    assert payload["status"] == STATUS_SPECIFIED
    assert payload["scope"] == SCOPE_BROAD_REPOSITORY_RECONNAISSANCE


# ══ Vocabulary and record invariants ══════════════════════════════════════════

def test_every_vocabulary_is_bounded_and_distinct():
    for vocabulary in (
        EVIDENCE_DOMAINS,
        EVIDENCE_ROLES,
        EVIDENCE_TIERS,
        EVIDENCE_SCOPES,
        EVIDENCE_REASONS,
        EVIDENCE_CONTRACT_STATUSES,
        DEFERRED_SOURCE_CLASSES,
    ):
        assert len(set(vocabulary)) == len(vocabulary)
        assert all(isinstance(item, str) and item for item in vocabulary)


def test_every_reason_code_has_a_sentence():
    for reason in EVIDENCE_REASONS:
        assert EVIDENCE_REASON_DESCRIPTIONS[reason].strip()


def test_every_domain_declares_the_capability_that_licenses_it():
    for domain in EVIDENCE_DOMAINS:
        assert domain in DOMAIN_CAPABILITY_LICENCES


def test_a_requirement_must_name_the_fact_it_came_from():
    with pytest.raises(ValueError):
        EvidenceRequirement(
            domain=DOMAIN_REPOSITORY,
            role=ROLE_IMPLEMENTATION_AUTHORITY,
            tier=TIER_REQUIRED_PRIMARY,
            reasons=(),
        )


def test_a_requirement_reason_must_come_from_the_bounded_vocabulary():
    with pytest.raises(ValueError):
        EvidenceRequirement(
            domain=DOMAIN_REPOSITORY,
            role=ROLE_IMPLEMENTATION_AUTHORITY,
            tier=TIER_REQUIRED_PRIMARY,
            reasons=("the user asked us to read the repository",),
        )


def test_an_unsupported_domain_is_a_construction_error():
    with pytest.raises(ValueError):
        EvidenceRequirement(
            domain="the_internet",
            role=ROLE_IMPLEMENTATION_AUTHORITY,
            tier=TIER_REQUIRED_PRIMARY,
            reasons=(EVIDENCE_REPOSITORY_REQUIRED,),
        )


def test_a_specified_contract_must_carry_a_workflow_and_a_scope():
    with pytest.raises(ValueError):
        EvidenceRequirementContract(
            status=STATUS_SPECIFIED,
            workflow=None,
            scope=None,
            reasons=(EVIDENCE_DIRECT_CONTEXT_FROM_TASK,),
        )


def test_a_refused_contract_may_not_carry_requirements():
    with pytest.raises(ValueError):
        EvidenceRequirementContract(
            status=STATUS_NOT_ROUTED,
            workflow=None,
            scope=None,
            requirements=(
                EvidenceRequirement(
                    domain=DOMAIN_DIRECT_CONTEXT,
                    role=ROLE_SUPPLIED_MATERIAL,
                    tier=TIER_REQUIRED_PRIMARY,
                    reasons=(EVIDENCE_DIRECT_CONTEXT_FROM_TASK,),
                ),
            ),
            inconsistencies=(INCONSISTENT_WAITER_NOT_ROUTED,),
        )


def test_a_deferred_source_may_only_be_deferred_or_excluded():
    from core.evidence_requirements import DeferredSource

    with pytest.raises(ValueError):
        DeferredSource(
            source_class=SOURCE_CLASS_SNAPSHOTS,
            disposition=TIER_REQUIRED_PRIMARY,
            reasons=(EVIDENCE_REPOSITORY_REQUIRED,),
        )


def test_a_deferred_source_may_be_deferred():
    from core.evidence_requirements import DeferredSource

    source = DeferredSource(
        source_class=SOURCE_CLASS_SNAPSHOTS,
        disposition=TIER_EXCLUDED_INITIALLY,
        reasons=(EVIDENCE_REPOSITORY_REQUIRED,),
    )

    assert source.as_dict()["disposition"] == TIER_EXCLUDED_INITIALLY


# ══ Not wired ═════════════════════════════════════════════════════════════════

def test_waiter_2_is_not_reachable_from_any_live_path():
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1]
    callers = []
    for path in root.rglob("*.py"):
        parts = set(path.parts)
        if parts & {"__pycache__", "tmp_tests", ".agent", "tests"}:
            continue
        if path.name in (
            "evidence_requirements.py",
            "evidence_policy.py",
            "waiter_evidence.py",
        ):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "waiter_evidence" in text or "derive_evidence_requirements" in text:
            callers.append(str(path.relative_to(root)))

    assert callers == [], callers
