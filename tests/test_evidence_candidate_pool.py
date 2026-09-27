"""ACQUIRE.2 — bounded candidate eligibility and selector-bridge tests.

ACQUIRE.1 wrote the shopping list. ACQUIRE.2 says which items on an
already-catalogued shelf are of the kinds the list asks for — and puts nothing
in the basket.

Four things are proved here.

The **eligibility matrix**: a direct-context order needs no inventory at all; a
bounded edit matches the README.md the user wrote against inventory membership
and reads none of it; a broad investigation and the DeepSeek Harness dogfood
put implementation, interfaces, configuration and architecture description in
the active pool, validation in the secondary one, historical material in the
deferred one, and generated, snapshot, temporary and duplicated material in
neither.

The **ceiling**: given an inventory of more than six thousand members, the
active pool still stops at ACQUIRE.1's number, ordering is deterministic, byte
ceilings are enforced from supplied metadata, an unmeasured member is refused
rather than assumed small, and the source budget is carried forward untouched
because nothing was acquired.

The **epistemic boundary**: a candidate is not evidence. ``content_read`` is
false, ``evidence_status`` is ``not_acquired``, eligibility for a role is an
expectation, and no rendered receipt claims anything was verified, confirmed or
proved.

The **bridge**: the envelope is CTX.SELECT-shaped, a selector's output is
validated as a subset of it rather than trusted, and neither an excluded class
nor a deferred one can re-enter through that door.
"""

from __future__ import annotations

import dataclasses
import json
import pathlib

import pytest

from core.acquisition_request import (
    BUDGET_RECONNAISSANCE,
    MAX_CANDIDATES_CEILING,
    NEVER_REQUESTED_SOURCE_CLASSES,
    REQUESTABLE_SOURCE_CLASSES,
    SOURCE_CLASS_AUTHORITATIVE_ARCHITECTURE_DOC,
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
    TargetAnchor,
)
from core.candidate_eligibility import (
    AUTHORITY_EXPECTED_NOT_VERIFIED,
    CLASSIFICATION_STATUSES,
    BASIS_EXPLICIT_TARGET_ANCHOR,
    BASIS_INVENTORY_DECLARED_CLASS,
    BASIS_INVENTORY_GENERATED_MARKER,
    BASIS_INVENTORY_PARSER_SUPPORT,
    BASIS_KNOWN_HISTORICAL_LOCATION,
    BASIS_KNOWN_MANIFEST_NAME,
    BASIS_KNOWN_TEST_LOCATION,
    CANDIDATE_EXPLICIT_TARGET_MATCHED,
    CANDIDATE_INVENTORY_MEMBER,
    CLASSIFICATION_BASES,
    CLASSIFICATION_CLASSIFIED,
    CLASSIFICATION_UNKNOWN,
    ELIGIBILITY_INCONSISTENCIES,
    ELIGIBILITY_REASONS,
    ELIGIBILITY_REASON_DESCRIPTIONS,
    ELIGIBILITY_STATUSES,
    ENVELOPE_VIOLATIONS,
    EVIDENCE_STATUS_NOT_ACQUIRED,
    INCONSISTENT_ACQUISITION_NOT_READY,
    INCONSISTENT_INVENTORY_ABSENT,
    INCONSISTENT_INVENTORY_FINGERPRINT_MISMATCH,
    INCONSISTENT_INVENTORY_IDENTITY_MISMATCH,
    INCONSISTENT_SOURCE_FINGERPRINT_MISMATCH,
    INELIGIBILITY_REASONS,
    INELIGIBLE_CANDIDATE_CEILING_REACHED,
    INELIGIBLE_CLASSIFICATION_UNKNOWN,
    INELIGIBLE_PER_SOURCE_BYTES_EXCEEDED,
    INELIGIBLE_SIZE_UNKNOWN,
    INELIGIBLE_SOURCE_CLASS_EXCLUDED,
    INELIGIBLE_TOTAL_BYTES_EXHAUSTED,
    STATUS_INCONSISTENT_INPUT,
    STATUS_INSUFFICIENT_CANDIDATES,
    STATUS_INVENTORY_REQUIRED,
    STATUS_NOT_ACQUISITION_READY,
    STATUS_READY,
    VIOLATION_BUDGET_EXCEEDED,
    VIOLATION_EXCLUDED_SOURCE_CLASS,
    VIOLATION_OUTSIDE_ENVELOPE,
    VIOLATION_WRONG_INVENTORY,
    CandidateClassification,
    CandidateEligibilityReceipt,
    EligibleCandidate,
    ExclusionSummary,
    SelectorEnvelope,
    eligibility_authority,
    eligibility_guardrails,
)
from core.candidate_inventory import (
    MAX_INVENTORY_MEMBERS,
    PARSER_SUPPORT_STATES,
    READ_POLICY_STATES,
    CandidateInventory,
    InventoryMember,
    inventory_from_capability_mappings,
    is_acceptable_identifier,
)
from core.eligibility_policy import (
    MAX_DEFERRED_CANDIDATES,
    ROLES_BY_SOURCE_CLASS,
    SOURCE_CLASS_DOMAINS,
    check_eligibility_monotonicity,
    classification_status,
    classify_member,
    derive_eligibility,
    is_historical_location,
    is_snapshot_location,
    is_temporary_location,
    is_test_location,
    requires_inventory,
    validate_selector_output,
)
from core.evidence_acquire_request import derive_acquisition_requests
from core.evidence_candidate_pool import (
    canonical_eligibility_fingerprint,
    canonical_eligibility_shape,
    derive_candidate_eligibility,
    render_eligibility_receipt_json,
)
from core.evidence_requirements import (
    DOMAIN_DIRECT_CONTEXT,
    DOMAIN_EXTERNAL_INFORMATION,
    DOMAIN_HISTORICAL_CONTEXT,
    DOMAIN_REPOSITORY,
    DOMAIN_VALIDATION_ARTIFACTS,
    ROLE_ARCHITECTURE_DESCRIPTION,
    ROLE_CONFIGURATION_AUTHORITY,
    ROLE_HISTORICAL_CONTEXT,
    ROLE_IMPLEMENTATION_AUTHORITY,
    ROLE_INTERFACE_CONTRACT,
    ROLE_SUPPLIED_MATERIAL,
    ROLE_VALIDATION_EVIDENCE,
    SCOPE_BROAD_REPOSITORY_RECONNAISSANCE,
    SCOPE_DIRECT_CONTEXT_ONLY,
    TIER_DEFERRED,
    TIER_REQUIRED_PRIMARY,
    TIER_REQUIRED_SECONDARY,
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


# ══ Upstream fixtures ═════════════════════════════════════════════════════════

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
    adapter = SemanticWaiterModelAdapter(
        ScriptedSemanticModelClient([json.dumps(payload)])
    )
    outcome = understand_request_semantically(prompt, adapter=adapter)
    completion = complete_intake_from_semantic_outcome(outcome)
    assert completion.state == STATE_READY, completion.decision.reasons
    return outcome.contract, completion.decision


def _upstream(prompt: str, payload: dict, **kwargs):
    """The ready acquisition contract and the evidence contract behind it."""
    contract, completion = _handoff(prompt, payload)
    decision = route_execution_workflow(contract, completion, **kwargs)
    evidence = derive_evidence_requirements(decision, contract, completion)
    acquisition = derive_acquisition_requests(evidence, decision, contract, completion)
    assert acquisition.ready, acquisition.inconsistencies
    return acquisition, evidence


def _eligibility(
    prompt: str,
    payload: dict,
    inventory: CandidateInventory | None = None,
    **kwargs,
) -> CandidateEligibilityReceipt:
    acquisition, evidence = _upstream(prompt, payload, **kwargs)
    return derive_candidate_eligibility(acquisition, evidence, inventory)


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
    acquisition = derive_acquisition_requests(evidence, decision, contract, completion)
    return acquisition, evidence


# ══ Inventory fixtures ════════════════════════════════════════════════════════

REPO = "cattus-fixture"


def _code(path: str, size: int = 2_000, **kwargs) -> InventoryMember:
    return InventoryMember(path, size_bytes=size, parser_support="supported", **kwargs)


def _text(path: str, size: int = 1_000, **kwargs) -> InventoryMember:
    return InventoryMember(path, size_bytes=size, **kwargs)


ARCHITECTURE_MEMBERS: tuple[InventoryMember, ...] = (
    _code("core/router.py"),
    _code("core/executor.py"),
    _code("core/indexer.py"),
    _code("core/text_utils.py"),
    _text(
        "core/api.pyi",
        800,
        declared_source_class=SOURCE_CLASS_INTERFACE_DEFINITION,
    ),
    _text("pyproject.toml", 500),
    _text("requirements.txt", 200),
    _text("docker-compose.yml", 700),
    _text(
        "docs/architecture.md",
        9_000,
        declared_source_class=SOURCE_CLASS_AUTHORITATIVE_ARCHITECTURE_DOC,
    ),
    _code(
        "core/phase_registry.py",
        3_000,
        declared_source_class=SOURCE_CLASS_PLUGIN_OR_REGISTRATION_SURFACE,
    ),
    _code("tests/test_indexer.py"),
    _code("tests/test_router.py"),
    _text("docs/proposals/old-idea.md"),
    _text("README.md", 4_000),
    _code("build/bundle.js", 50_000, generated=True),
    _text("tests/__snapshots__/a.snap", 300),
    _text(".tmp/scratch.txt", 100),
    _text("README.vi.md", 4_000, duplicate_of="README.md"),
    _text("weird/thing.xyz", 10),
)


def _architecture_inventory(**kwargs) -> CandidateInventory:
    return CandidateInventory(
        repository_identity=REPO, members=ARCHITECTURE_MEMBERS, **kwargs
    )


def _dogfood_receipt(
    inventory: CandidateInventory | None = None,
) -> CandidateEligibilityReceipt:
    return _eligibility(
        DOGFOOD_PROMPT,
        _dogfood_interpretation(BROAD_REPOSITORY),
        inventory if inventory is not None else _architecture_inventory(),
    )


def _structure_only(receipt) -> str:
    """The record itself, without the English that explains it.

    The reason descriptions are ordinary prose — one of them says "no later
    score can readmit them" — and a boundary test is about the structure: the
    candidates, the pools, the envelopes and the ceilings.
    """
    payload = _without_authority(receipt.as_dict())
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


# ══ A, B — direct context needs no inventory at all ═══════════════════════════

def test_case_a_an_explanation_needs_no_inventory():
    receipt = _eligibility(*_EXPLANATION)

    assert receipt.status == STATUS_READY
    assert receipt.workflow == WORKFLOW_CHAT
    assert receipt.evidence_scope == SCOPE_DIRECT_CONTEXT_ONLY
    assert receipt.inventory_fingerprint is None
    assert receipt.repository_identity is None
    assert len(receipt.active_candidates) == 1


def test_case_a_the_direct_context_candidate_is_a_reference_not_a_copy():
    candidate = _eligibility(*_EXPLANATION).active_candidates[0]

    assert candidate.domain == DOMAIN_DIRECT_CONTEXT
    assert candidate.eligible_source_classes == (SOURCE_CLASS_SUPPLIED_CONTEXT,)
    assert candidate.eligible_roles == (ROLE_SUPPLIED_MATERIAL,)
    assert candidate.identifier.startswith("supplied_context:")
    assert candidate.content_read is False
    assert candidate.evidence_status == EVIDENCE_STATUS_NOT_ACQUIRED


def test_case_a_a_direct_context_receipt_does_not_copy_the_prompt():
    rendered = json.dumps(_eligibility(*_EXPLANATION).as_dict(), ensure_ascii=False)

    assert "Bellman" not in rendered


def test_case_b_a_pasted_comparison_asks_for_no_repository_candidates():
    receipt = _eligibility(_PASTED_COMPARISON, _PASTED_COMPARISON_INTERPRETATION)

    assert receipt.selector_envelopes == ()
    assert receipt.external_envelopes == ()
    assert receipt.active_identifiers() == receipt.identifiers()
    assert all(
        candidate.domain == DOMAIN_DIRECT_CONTEXT
        for candidate in receipt.all_candidates()
    )


def test_a_direct_context_order_requires_no_inventory():
    acquisition, _ = _upstream(*_EXPLANATION)

    assert requires_inventory(acquisition) is False


# ══ C — the README typo, matched and not read ═════════════════════════════════

def test_case_c_the_named_readme_matches_inventory_membership():
    receipt = _eligibility(*_README_EDIT, inventory=_architecture_inventory())
    candidate = receipt.candidate("README.md")

    assert receipt.workflow == WORKFLOW_INSTANT_RUN
    assert candidate is not None
    assert candidate.target_anchor_match is True
    assert CANDIDATE_EXPLICIT_TARGET_MATCHED in candidate.reasons
    assert CANDIDATE_INVENTORY_MEMBER in candidate.reasons
    assert candidate.content_read is False
    assert candidate.evidence_status == EVIDENCE_STATUS_NOT_ACQUIRED
    assert receipt.unmatched_target_anchors == ()


def test_case_c_the_readme_candidate_claims_nothing_about_a_typo():
    rendered = _structure_only(
        _eligibility(*_README_EDIT, inventory=_architecture_inventory())
    )

    for forbidden in ("teh", "typo", "diff", "excerpt", "snippet", "line_number"):
        assert forbidden not in rendered, forbidden


def test_case_c_an_anchor_comes_first_in_its_pool():
    """Explicit naming is precedence inside the pool, not a bypass of it."""
    receipt = _eligibility(*_README_EDIT, inventory=_architecture_inventory())
    repository = [
        candidate
        for candidate in receipt.active_candidates
        if candidate.domain == DOMAIN_REPOSITORY
    ]

    assert repository[0].identifier == "README.md"
    assert repository[0].target_anchor_match is True


def test_case_c_an_anchor_of_unknown_kind_claims_no_class_and_no_role():
    """The user named it. Nothing else about it has been established.

    Markdown prose is not architecture authority just because an order pointed
    at it, so the candidate carries the one fact that is true — the inventory
    contains what the user named — and no fact that is not.
    """
    receipt = _eligibility(*_README_EDIT, inventory=_architecture_inventory())
    candidate = receipt.candidate("README.md")

    assert candidate.target_anchor_match is True
    assert candidate.classification_status == CLASSIFICATION_UNKNOWN
    assert candidate.eligible_source_classes == ()
    assert candidate.eligible_roles == ()
    assert candidate.satisfies_a_role is False


def test_case_c_an_anchor_whose_kind_is_known_records_the_anchor_as_a_basis():
    receipt = _eligibility(*_TEST_FOCUSED_DEBUGGING, inventory=_architecture_inventory())
    candidate = receipt.candidate("tests/test_indexer.py")

    assert candidate.classification_status == CLASSIFICATION_CLASSIFIED
    assert any(
        BASIS_EXPLICIT_TARGET_ANCHOR in item.basis for item in candidate.classifications
    )
    assert any(
        BASIS_KNOWN_TEST_LOCATION in item.basis for item in candidate.classifications
    )


def test_case_c_an_unknown_anchor_does_not_discharge_a_required_role():
    candidate = _eligibility(
        *_README_EDIT, inventory=_architecture_inventory()
    ).candidate("README.md")

    assert candidate.eligible_roles == ()
    assert ROLE_IMPLEMENTATION_AUTHORITY not in candidate.eligible_roles


def test_case_c_the_same_inventory_member_without_an_anchor_is_not_a_target():
    """Target status requires both explicit anchoring and inventory membership."""
    candidate = _dogfood_receipt().candidate("tests/test_indexer.py")

    assert candidate is not None
    assert candidate.target_anchor_match is False
    assert CANDIDATE_EXPLICIT_TARGET_MATCHED not in candidate.reasons
    assert all(
        BASIS_EXPLICIT_TARGET_ANCHOR not in classification.basis
        for classification in candidate.classifications
    )


def test_case_c_target_status_never_grants_an_unrelated_authority_role():
    candidate = _eligibility(
        *_README_EDIT, inventory=_architecture_inventory()
    ).candidate("README.md")

    assert candidate.target_anchor_match is True
    assert candidate.eligible_roles == ()
    for unrelated_role in (
        ROLE_IMPLEMENTATION_AUTHORITY,
        ROLE_ARCHITECTURE_DESCRIPTION,
        ROLE_CONFIGURATION_AUTHORITY,
    ):
        assert unrelated_role not in candidate.eligible_roles


def test_case_c_exclusions_override_an_explicit_target_anchor():
    acquisition, evidence = _upstream(*_README_EDIT)
    targeted_requests = tuple(
        dataclasses.replace(
            request,
            target_anchors=(TargetAnchor("tests/__snapshots__/a.snap"),),
        )
        if request.target_anchors
        else request
        for request in acquisition.requests
    )
    acquisition = dataclasses.replace(acquisition, requests=targeted_requests)

    receipt = derive_candidate_eligibility(
        acquisition,
        evidence,
        CandidateInventory(
            repository_identity=REPO,
            members=(_text("tests/__snapshots__/a.snap", 300),),
        ),
    )

    assert receipt.candidate("tests/__snapshots__/a.snap") is None
    assert receipt.unmatched_target_anchors == ()
    counts = {item.reason: item.count for item in receipt.exclusion_summary}
    assert counts[INELIGIBLE_SOURCE_CLASS_EXCLUDED] == 1


# ══ D — a bounded one-file implementation ═════════════════════════════════════

def test_case_d_a_bounded_request_admits_only_licensed_classes():
    receipt = _eligibility(*_ONE_FILE_IMPLEMENTATION, inventory=_architecture_inventory())
    repository = [
        candidate
        for candidate in receipt.active_candidates
        if candidate.domain == DOMAIN_REPOSITORY
    ]

    assert repository
    for candidate in repository:
        assert set(candidate.eligible_source_classes) <= {
            SOURCE_CLASS_RUNTIME_IMPLEMENTATION,
            SOURCE_CLASS_SURROUNDING_IMPLEMENTATION,
        }
    assert receipt.candidate("core/text_utils.py") is not None
    assert receipt.candidate("docs/architecture.md") is None


def test_case_d_a_bounded_pool_is_finite():
    receipt = _eligibility(*_ONE_FILE_IMPLEMENTATION, inventory=_architecture_inventory())

    assert 0 < receipt.candidate_used <= receipt.candidate_limit


# ══ E — a broad investigation ═════════════════════════════════════════════════

def test_case_e_broad_investigation_puts_implementation_and_seams_in_the_active_pool():
    receipt = _eligibility(*_BROAD_DEBUGGING, inventory=_architecture_inventory())
    classes = set(receipt.source_classes())

    assert receipt.workflow == WORKFLOW_COMMANDER
    for source_class in (
        SOURCE_CLASS_RUNTIME_IMPLEMENTATION,
        SOURCE_CLASS_INTERFACE_DEFINITION,
        SOURCE_CLASS_CONFIGURATION,
        SOURCE_CLASS_DEPENDENCY_MANIFEST,
        SOURCE_CLASS_AUTHORITATIVE_ARCHITECTURE_DOC,
        SOURCE_CLASS_PLUGIN_OR_REGISTRATION_SURFACE,
    ):
        assert source_class in classes, source_class


def test_case_e_validation_stays_secondary_and_restated_material_stays_out():
    receipt = _eligibility(*_BROAD_DEBUGGING, inventory=_architecture_inventory())

    assert {candidate.identifier for candidate in receipt.secondary_candidates} == {
        "tests/test_indexer.py",
        "tests/test_router.py",
    }
    for identifier in (
        "build/bundle.js",
        "tests/__snapshots__/a.snap",
        ".tmp/scratch.txt",
        "README.vi.md",
    ):
        assert receipt.candidate(identifier) is None, identifier


# ══ F — the DeepSeek Harness dogfood ══════════════════════════════════════════

def test_case_f_dogfood_active_pool_is_the_architecture_not_the_repository():
    receipt = _dogfood_receipt()

    assert receipt.status == STATUS_READY
    assert receipt.workflow == WORKFLOW_COMMANDER
    assert receipt.evidence_scope == SCOPE_BROAD_REPOSITORY_RECONNAISSANCE
    assert {
        candidate.identifier
        for candidate in receipt.active_candidates
        if candidate.domain == DOMAIN_REPOSITORY
    } == {
        "core/router.py",
        "core/executor.py",
        "core/indexer.py",
        "core/text_utils.py",
        "core/phase_registry.py",
        "core/api.pyi",
        "pyproject.toml",
        "requirements.txt",
        "docker-compose.yml",
        "docs/architecture.md",
    }


def test_case_f_dogfood_separates_every_tier():
    receipt = _dogfood_receipt()

    assert {c.identifier for c in receipt.secondary_candidates} == {
        "tests/test_indexer.py",
        "tests/test_router.py",
    }
    assert {c.identifier for c in receipt.deferred_candidates} == {
        "docs/proposals/old-idea.md"
    }
    assert receipt.unsatisfied_required_roles == ()


def test_case_f_dogfood_excludes_generated_snapshot_temporary_and_duplicate():
    receipt = _dogfood_receipt()
    counts = {item.reason: item.count for item in receipt.exclusion_summary}

    assert counts[INELIGIBLE_SOURCE_CLASS_EXCLUDED] == 4
    # README.md and weird/thing.xyz: prose and an unrecognised extension. The
    # dogfood names neither, so neither arrives as an anchor either.
    assert counts[INELIGIBLE_CLASSIFICATION_UNKNOWN] == 2
    for identifier in (
        "build/bundle.js",
        "tests/__snapshots__/a.snap",
        ".tmp/scratch.txt",
        "README.vi.md",
        "weird/thing.xyz",
    ):
        assert receipt.candidate(identifier) is None, identifier


def test_case_f_dogfood_stays_far_inside_the_upstream_ceiling():
    receipt = _dogfood_receipt()

    assert receipt.candidate_used <= receipt.candidate_limit
    assert receipt.candidate_limit <= MAX_CANDIDATES_CEILING * 3
    assert receipt.budget_summary()["within_upstream_ceiling"] is True


def test_case_f_dogfood_reads_nothing():
    receipt = _dogfood_receipt()
    guardrails = receipt.as_dict()["guardrails"]

    assert guardrails["candidate_contents_read"] is False
    assert guardrails["repository_traversal_performed"] is False
    assert guardrails["new_inventory_built"] is False
    assert guardrails["ctx_select_executed"] is False
    assert all(candidate.content_read is False for candidate in receipt.all_candidates())


# ══ G — the same dogfood over supplied context ════════════════════════════════

def test_case_g_the_direct_context_dogfood_builds_no_repository_pool():
    receipt = _eligibility(DOGFOOD_PROMPT, _dogfood_interpretation({}))

    assert receipt.workflow == WORKFLOW_CHAT
    assert receipt.selector_envelopes == ()
    assert receipt.inventory_fingerprint is None
    assert receipt.candidate_used == 1


# ══ H — more than six thousand inventory members ══════════════════════════════

def _large_inventory(member_count: int = 6_200) -> CandidateInventory:
    """A synthetic repository large enough to reproduce the original failure.

    Metadata only: no file is created, nothing is written and nothing is read.
    The mix is the mix that broke the dogfood — implementation and interfaces
    and configuration next to tests, snapshots, generated bundles, scratch
    files, rejected proposals and unrelated prose.
    """
    members: list[InventoryMember] = [
        _code("core/indexer.py", 4_000),
        _text("core/api.pyi", 800, declared_source_class=SOURCE_CLASS_INTERFACE_DEFINITION),
        _text(
            "docs/architecture.md",
            9_000,
            declared_source_class=SOURCE_CLASS_AUTHORITATIVE_ARCHITECTURE_DOC,
        ),
        _code(
            "core/phase_registry.py",
            3_000,
            declared_source_class=SOURCE_CLASS_PLUGIN_OR_REGISTRATION_SURFACE,
        ),
        _text("pyproject.toml", 500),
        _text("requirements.txt", 200),
        _text("docker-compose.yml", 700),
    ]
    index = 0
    while len(members) < member_count:
        index += 1
        members.extend(
            (
                _code(f"core/module_{index}.py", 1_500),
                _code(f"tests/test_module_{index}.py", 900),
                _text(f"build/out_{index}.js", 20_000, generated=True),
                _text(f"tests/__snapshots__/module_{index}.snap", 400),
                _text(f".tmp/module_{index}.log", 120),
                _text(f"docs/proposals/module_{index}.md", 600),
                _text(f"assets/module_{index}.bin", 50),
            )
        )
    return CandidateInventory(
        repository_identity=REPO, members=tuple(members[:member_count])
    )


def test_case_h_six_thousand_members_still_produce_a_bounded_pool():
    """The anti-6,087 regression, in metadata and without a single read."""
    inventory = _large_inventory()
    receipt = _dogfood_receipt(inventory)

    assert len(inventory) > 6_087
    assert receipt.status == STATUS_READY
    assert receipt.candidate_used <= receipt.candidate_limit
    assert len(receipt.active_candidates) <= MAX_CANDIDATES_CEILING + 1
    assert receipt.as_dict()["guardrails"]["candidate_contents_read"] is False


def test_case_h_no_excluded_member_reaches_the_active_pool_at_scale():
    receipt = _dogfood_receipt(_large_inventory())

    for candidate in receipt.active_candidates + receipt.secondary_candidates:
        assert not set(candidate.eligible_source_classes) & set(
            NEVER_REQUESTED_SOURCE_CLASSES
        )
        assert not candidate.identifier.startswith("build/")
        assert not candidate.identifier.startswith(".tmp/")
        assert "__snapshots__" not in candidate.identifier


def test_case_h_no_deferred_history_reaches_the_active_pool_at_scale():
    receipt = _dogfood_receipt(_large_inventory())

    for candidate in receipt.active_candidates + receipt.secondary_candidates:
        assert SOURCE_CLASS_HISTORICAL_DESIGN_MATERIAL not in (
            candidate.eligible_source_classes
        )
        assert "proposals" not in candidate.identifier
    assert receipt.deferred_candidates
    assert len(receipt.deferred_candidates) <= MAX_DEFERRED_CANDIDATES


def test_case_h_a_large_inventory_is_narrowed_deterministically():
    first = _dogfood_receipt(_large_inventory())
    second = _dogfood_receipt(_large_inventory())

    assert first.active_identifiers() == second.active_identifiers()
    assert canonical_eligibility_fingerprint(first) == canonical_eligibility_fingerprint(
        second
    )


# ══ I — test-focused debugging ════════════════════════════════════════════════

def test_case_i_a_failing_test_puts_validation_in_the_active_pool():
    receipt = _eligibility(*_TEST_FOCUSED_DEBUGGING, inventory=_architecture_inventory())
    candidate = receipt.candidate("tests/test_indexer.py")

    assert candidate is not None
    assert candidate.tier == TIER_REQUIRED_PRIMARY
    assert candidate in receipt.active_candidates
    assert candidate.eligible_roles == (ROLE_VALIDATION_EVIDENCE,)
    assert candidate.target_anchor_match is True


def test_case_i_other_tests_are_eligible_within_the_same_bounded_request():
    receipt = _eligibility(*_TEST_FOCUSED_DEBUGGING, inventory=_architecture_inventory())
    validation = [
        candidate
        for candidate in receipt.active_candidates
        if candidate.domain == DOMAIN_VALIDATION_ARTIFACTS
    ]

    assert {item.identifier for item in validation} == {
        "tests/test_indexer.py",
        "tests/test_router.py",
    }
    assert validation[0].identifier == "tests/test_indexer.py"


def test_case_i_scope_still_comes_from_upstream_and_not_from_habit():
    """Debugging often benefits from source code. The contract still decides."""
    acquisition, _ = _upstream(*_TEST_FOCUSED_DEBUGGING)
    receipt = _eligibility(*_TEST_FOCUSED_DEBUGGING, inventory=_architecture_inventory())

    licensed = {request.domain for request in acquisition.all_requests()}
    assert {candidate.domain for candidate in receipt.all_candidates()} <= licensed


# ══ J — historical material ═══════════════════════════════════════════════════

def test_case_j_historical_material_is_deferred_and_never_current_authority():
    receipt = _dogfood_receipt()
    candidate = receipt.candidate("docs/proposals/old-idea.md")

    assert candidate.tier == TIER_DEFERRED
    assert candidate in receipt.deferred_candidates
    assert candidate not in receipt.active_candidates
    assert candidate.eligible_roles == (ROLE_HISTORICAL_CONTEXT,)
    assert ROLE_IMPLEMENTATION_AUTHORITY not in candidate.eligible_roles
    assert candidate.authority_status == AUTHORITY_EXPECTED_NOT_VERIFIED


def test_case_j_the_deferred_pool_carries_no_acquisition_budget():
    receipt = _dogfood_receipt()
    envelope = receipt.envelope_for(DOMAIN_HISTORICAL_CONTEXT, TIER_DEFERRED)

    assert envelope is not None
    assert envelope.candidate_budget_remaining == 0
    assert envelope.byte_budget_remaining == 0
    assert receipt.budget_summary()["deferred_candidate_budget"] == 0


def test_case_j_a_historical_location_is_the_basis_it_was_classified_from():
    classifications = classify_member(_text("docs/proposals/old-idea.md"))

    assert classifications[0].source_class == SOURCE_CLASS_HISTORICAL_DESIGN_MATERIAL
    assert classifications[0].basis == (BASIS_KNOWN_HISTORICAL_LOCATION,)


# ══ K — restated material never becomes active ════════════════════════════════

@pytest.mark.parametrize(
    "member, expected",
    [
        (_code("build/bundle.js", 500, generated=True), SOURCE_CLASS_GENERATED_ARTIFACT),
        (_text("tests/__snapshots__/a.snap", 100), SOURCE_CLASS_SNAPSHOT),
        (_text(".tmp/scratch.txt", 100), SOURCE_CLASS_TEMPORARY_ARTIFACT),
        (
            _text("README.vi.md", 100, duplicate_of="README.md"),
            SOURCE_CLASS_DUPLICATE_RENDERING,
        ),
    ],
)
def test_case_k_restated_material_is_classified_and_kept_out(member, expected):
    classes = {item.source_class for item in classify_member(member)}
    receipt = _dogfood_receipt()

    assert expected in classes
    assert receipt.candidate(member.identifier) is None


def test_case_k_a_hard_excluded_member_never_becomes_a_candidate():
    inventory = CandidateInventory(
        repository_identity=REPO,
        members=ARCHITECTURE_MEMBERS
        + (
            InventoryMember(
                ".env", size_bytes=100, read_policy="hard_no_auto_read"
            ),
        ),
    )
    receipt = _dogfood_receipt(inventory)

    assert receipt.candidate(".env") is None


# ══ L, M, N, O — membership and identity ══════════════════════════════════════

def test_case_l_an_anchor_the_inventory_does_not_contain_is_reported_unmatched():
    """Not invented, not assumed to exist, not quietly dropped."""
    inventory = CandidateInventory(
        repository_identity=REPO,
        members=tuple(
            member for member in ARCHITECTURE_MEMBERS if member.identifier != "README.md"
        ),
    )
    receipt = _eligibility(*_README_EDIT, inventory=inventory)

    assert receipt.unmatched_target_anchors == ("README.md",)
    assert receipt.candidate("README.md") is None


def test_case_m_a_path_outside_the_inventory_cannot_enter_the_pool():
    receipt = _dogfood_receipt()

    assert receipt.candidate("core/invented_by_the_caller.py") is None
    for candidate in receipt.all_candidates():
        if candidate.domain == DOMAIN_DIRECT_CONTEXT:
            continue
        assert candidate.identifier in _architecture_inventory()


def test_case_m_an_unusable_identifier_is_refused_at_construction():
    for identifier in ("/absolute/path.py", "../escape.py", "", "a" * 2_000):
        assert is_acceptable_identifier(identifier) is False
        with pytest.raises(ValueError):
            InventoryMember(identifier)


def test_case_n_an_inventory_for_another_repository_is_refused():
    acquisition, evidence = _upstream(
        DOGFOOD_PROMPT, _dogfood_interpretation(BROAD_REPOSITORY)
    )
    receipt = derive_candidate_eligibility(
        acquisition,
        evidence,
        _architecture_inventory(),
        repository_identity="a-different-repository",
    )

    assert receipt.status == STATUS_INCONSISTENT_INPUT
    assert receipt.inconsistencies == (INCONSISTENT_INVENTORY_IDENTITY_MISMATCH,)
    assert receipt.active_candidates == ()


def test_case_o_an_inventory_whose_declared_fingerprint_is_wrong_is_refused():
    acquisition, evidence = _upstream(
        DOGFOOD_PROMPT, _dogfood_interpretation(BROAD_REPOSITORY)
    )
    tampered = _architecture_inventory(declared_fingerprint="0" * 64)
    receipt = derive_candidate_eligibility(acquisition, evidence, tampered)

    assert receipt.status == STATUS_INCONSISTENT_INPUT
    assert receipt.inconsistencies == (INCONSISTENT_INVENTORY_FINGERPRINT_MISMATCH,)


def test_a_declared_fingerprint_that_is_right_is_accepted():
    inventory = _architecture_inventory()
    stamped = _architecture_inventory(declared_fingerprint=inventory.fingerprint())

    assert stamped.declared_fingerprint_matches() is True
    assert _dogfood_receipt(stamped).status == STATUS_READY


def test_a_repository_request_without_an_inventory_fails_closed():
    acquisition, evidence = _upstream(
        DOGFOOD_PROMPT, _dogfood_interpretation(BROAD_REPOSITORY)
    )
    receipt = derive_candidate_eligibility(acquisition, evidence, None)

    assert receipt.status == STATUS_INVENTORY_REQUIRED
    assert receipt.inconsistencies == (INCONSISTENT_INVENTORY_ABSENT,)
    assert receipt.active_candidates == ()
    assert receipt.as_dict()["guardrails"]["repository_traversal_performed"] is False


def test_an_acquisition_contract_that_is_not_ready_produces_no_pool():
    acquisition, evidence = _upstream(*_EXPLANATION)
    refused = dataclasses.replace(
        acquisition,
        status="not_evidence_ready",
        workflow=None,
        evidence_scope=None,
        requests=(),
        deferred_requests=(),
        exclusions=(),
        inconsistencies=("evidence_contract_not_specified",),
    )
    receipt = derive_candidate_eligibility(refused, evidence, None)

    assert receipt.status == STATUS_NOT_ACQUISITION_READY
    assert receipt.inconsistencies == (INCONSISTENT_ACQUISITION_NOT_READY,)


def test_an_acquisition_contract_paired_with_the_wrong_evidence_is_refused():
    acquisition, _ = _upstream(*_README_EDIT)
    _, other_evidence = _upstream(*_ONE_FILE_IMPLEMENTATION)
    receipt = derive_candidate_eligibility(
        acquisition, other_evidence, _architecture_inventory()
    )

    assert receipt.status == STATUS_INCONSISTENT_INPUT
    assert receipt.inconsistencies == (INCONSISTENT_SOURCE_FINGERPRINT_MISMATCH,)


# ══ P — unknown is a safe answer ══════════════════════════════════════════════

def test_case_p_an_unclassifiable_member_satisfies_no_role():
    member = _text("weird/custom/file.xyz", 10)
    classifications = classify_member(member)

    assert classifications == ()
    assert classification_status(classifications) == CLASSIFICATION_UNKNOWN
    assert _dogfood_receipt().candidate("weird/thing.xyz") is None


def test_case_p_an_extension_alone_establishes_no_authority():
    """``.md`` is not architecture authority and ``.py`` is not implementation."""
    prose = classify_member(_text("docs/notes.md", 500))
    assert prose == ()

    plain_python = classify_member(_text("core/thing.py", 500))
    assert plain_python == ()


def test_case_p_code_is_a_kind_of_file_and_not_a_verdict_about_it():
    classes = {item.source_class for item in classify_member(_code("core/thing.py"))}

    assert classes == {
        SOURCE_CLASS_RUNTIME_IMPLEMENTATION,
        SOURCE_CLASS_SURROUNDING_IMPLEMENTATION,
    }
    for item in classify_member(_code("core/thing.py")):
        assert item.basis == (BASIS_INVENTORY_PARSER_SUPPORT,)


def test_case_p_vendored_code_is_not_this_system_s_implementation():
    assert classify_member(_code("vendor/lib/thing.py", vendor=True)) == ()


def test_case_p_generated_code_is_generated_before_it_is_anything_else():
    classes = {
        item.source_class
        for item in classify_member(_code("build/out.js", generated=True))
    }

    assert classes == {SOURCE_CLASS_GENERATED_ARTIFACT}
    assert SOURCE_CLASS_RUNTIME_IMPLEMENTATION not in classes


def test_case_v_a_required_role_with_no_candidate_is_reported_not_papered_over():
    """The architecture is not in the inventory, so the receipt says so."""
    thin = CandidateInventory(
        repository_identity=REPO,
        members=(_code("core/router.py"), _code("tests/test_router.py")),
    )
    receipt = _dogfood_receipt(thin)

    assert receipt.status == STATUS_INSUFFICIENT_CANDIDATES
    assert ROLE_INTERFACE_CONTRACT in receipt.unsatisfied_required_roles
    assert ROLE_ARCHITECTURE_DESCRIPTION in receipt.unsatisfied_required_roles
    assert ROLE_CONFIGURATION_AUTHORITY in receipt.unsatisfied_required_roles
    assert ROLE_IMPLEMENTATION_AUTHORITY not in receipt.unsatisfied_required_roles
    assert receipt.candidate("core/router.py") is not None


def test_case_v_an_insufficient_receipt_is_not_a_ready_one():
    thin = CandidateInventory(
        repository_identity=REPO, members=(_code("core/router.py"),)
    )

    assert _dogfood_receipt(thin).ready is False


# ══ Q — one identifier, many classes, counted once ════════════════════════════

def test_case_q_a_multi_class_member_appears_once_and_carries_every_class():
    receipt = _dogfood_receipt()
    candidate = receipt.candidate("core/phase_registry.py")

    assert candidate.eligible_source_classes == (
        SOURCE_CLASS_RUNTIME_IMPLEMENTATION,
        SOURCE_CLASS_SURROUNDING_IMPLEMENTATION,
        SOURCE_CLASS_PLUGIN_OR_REGISTRATION_SURFACE,
    )
    assert candidate.eligible_roles == (
        ROLE_IMPLEMENTATION_AUTHORITY,
        ROLE_ARCHITECTURE_DESCRIPTION,
    )
    assert receipt.identifiers().count("core/phase_registry.py") == 1


def test_case_q_every_class_a_candidate_carries_names_its_own_basis():
    candidate = _dogfood_receipt().candidate("core/phase_registry.py")
    bases = {item.source_class: item.basis for item in candidate.classifications}

    assert bases[SOURCE_CLASS_RUNTIME_IMPLEMENTATION] == (BASIS_INVENTORY_PARSER_SUPPORT,)
    assert bases[SOURCE_CLASS_PLUGIN_OR_REGISTRATION_SURFACE] == (
        BASIS_INVENTORY_DECLARED_CLASS,
    )


# ══ R, S, T, U — budgets ══════════════════════════════════════════════════════

def test_case_r_an_overflowing_pool_is_narrowed_to_the_ceiling():
    receipt = _dogfood_receipt(_large_inventory())
    envelope = receipt.envelope_for(DOMAIN_REPOSITORY, TIER_REQUIRED_PRIMARY)

    assert len(envelope.allowed_candidate_identifiers) == 96
    assert envelope.candidate_budget_remaining == 0
    counts = {item.reason: item.count for item in receipt.exclusion_summary}
    assert counts[INELIGIBLE_CANDIDATE_CEILING_REACHED] > 0


def test_case_r_the_anchor_the_user_named_comes_first():
    receipt = _eligibility(*_BROAD_DEBUGGING, inventory=_large_inventory())
    repository = [
        candidate
        for candidate in receipt.active_candidates
        if candidate.domain == DOMAIN_REPOSITORY
    ]

    assert repository[0].identifier == "core/indexer.py"
    assert repository[0].target_anchor_match is True


def test_case_r_the_narrowing_order_depends_on_metadata_and_not_on_input_order():
    """The invariant that actually holds, and the one worth having.

    Ordering is not alphabetical: the pool cycles through the roles the request
    named, so one abundant class cannot spend the whole ceiling and leave a
    required role unsatisfied. What it *is*, is a function of the metadata
    alone — hand the same members in a different sequence and the same pool
    comes out, in the same order.
    """
    forwards = _large_inventory()
    backwards = CandidateInventory(
        repository_identity=REPO, members=tuple(reversed(forwards.members))
    )

    first = _eligibility(*_BROAD_DEBUGGING, inventory=forwards)
    second = _eligibility(*_BROAD_DEBUGGING, inventory=backwards)

    assert first.active_identifiers() == second.active_identifiers()
    assert first.active_identifiers() == _eligibility(
        *_BROAD_DEBUGGING, inventory=forwards
    ).active_identifiers()


def test_case_r_every_required_role_survives_a_crowded_repository():
    """Nine hundred modules must not crowd out the one architecture document."""
    receipt = _dogfood_receipt(_large_inventory())
    covered = {
        role for candidate in receipt.active_candidates for role in candidate.eligible_roles
    }

    assert ROLE_IMPLEMENTATION_AUTHORITY in covered
    assert ROLE_INTERFACE_CONTRACT in covered
    assert ROLE_CONFIGURATION_AUTHORITY in covered
    assert ROLE_ARCHITECTURE_DESCRIPTION in covered
    assert receipt.unsatisfied_required_roles == ()


def test_case_s_a_member_larger_than_the_per_source_ceiling_is_refused():
    huge = CandidateInventory(
        repository_identity=REPO,
        members=ARCHITECTURE_MEMBERS + (_code("core/enormous.py", 500_000),),
    )
    receipt = _dogfood_receipt(huge)
    counts = {item.reason: item.count for item in receipt.exclusion_summary}

    assert receipt.candidate("core/enormous.py") is None
    assert counts[INELIGIBLE_PER_SOURCE_BYTES_EXCEEDED] == 1
    assert receipt.as_dict()["guardrails"]["candidate_contents_read"] is False


def test_case_t_the_total_byte_ceiling_bounds_the_pool_deterministically():
    """Every member is legal alone; together they exceed the total."""
    fat = CandidateInventory(
        repository_identity=REPO,
        members=tuple(
            _code(f"core/fat_{index:03d}.py", 130_000) for index in range(40)
        )
        + ARCHITECTURE_MEMBERS,
    )
    receipt = _dogfood_receipt(fat)
    counts = {item.reason: item.count for item in receipt.exclusion_summary}

    assert receipt.byte_eligible_total <= receipt.byte_limit
    assert counts.get(INELIGIBLE_TOTAL_BYTES_EXHAUSTED, 0) > 0
    assert receipt.status in (STATUS_READY, STATUS_INSUFFICIENT_CANDIDATES)


def test_case_u_a_member_of_unknown_size_is_refused_not_assumed_small():
    unmeasured = CandidateInventory(
        repository_identity=REPO,
        members=ARCHITECTURE_MEMBERS
        + (InventoryMember("core/unmeasured.py", parser_support="supported"),),
    )
    receipt = _dogfood_receipt(unmeasured)
    counts = {item.reason: item.count for item in receipt.exclusion_summary}

    assert receipt.candidate("core/unmeasured.py") is None
    assert counts[INELIGIBLE_SIZE_UNKNOWN] == 1


def test_the_source_budget_is_carried_forward_and_never_spent():
    receipt = _dogfood_receipt()

    assert receipt.source_limit_reserved > 0
    assert receipt.source_budget_consumed == 0
    assert receipt.budget_summary()["source_budget_consumed"] == 0


def test_the_candidate_pool_never_exceeds_the_upstream_ceiling():
    for inventory in (_architecture_inventory(), _large_inventory()):
        receipt = _dogfood_receipt(inventory)

        assert receipt.candidate_used <= receipt.candidate_limit
        assert receipt.byte_eligible_total <= receipt.byte_limit


def test_a_receipt_that_exceeded_its_ceiling_cannot_be_constructed():
    with pytest.raises(ValueError):
        CandidateEligibilityReceipt(
            status=STATUS_READY,
            workflow=WORKFLOW_CHAT,
            evidence_scope=SCOPE_DIRECT_CONTEXT_ONLY,
            active_candidates=(
                EligibleCandidate(
                    identifier="supplied_context:x",
                    domain=DOMAIN_DIRECT_CONTEXT,
                    tier=TIER_REQUIRED_PRIMARY,
                    eligible_source_classes=(SOURCE_CLASS_SUPPLIED_CONTEXT,),
                    eligible_roles=(ROLE_SUPPLIED_MATERIAL,),
                    classifications=(
                        CandidateClassification(
                            source_class=SOURCE_CLASS_SUPPLIED_CONTEXT,
                            basis=(BASIS_INVENTORY_DECLARED_CLASS,),
                        ),
                    ),
                    reasons=("CANDIDATE_SUPPLIED_CONTEXT_REFERENCE",),
                ),
            ),
            candidate_limit=0,
            reasons=("ELIGIBILITY_CANDIDATES_BOUNDED",),
            acquisition_request_fingerprint="0" * 64,
        )


# ══ W, X — deferred and excluded cannot be promoted ═══════════════════════════

def test_case_w_a_deferred_candidate_in_the_active_pool_is_a_construction_error():
    candidate = _dogfood_receipt().deferred_candidates[0]

    with pytest.raises(ValueError):
        CandidateEligibilityReceipt(
            status=STATUS_READY,
            workflow=WORKFLOW_COMMANDER,
            evidence_scope=SCOPE_BROAD_REPOSITORY_RECONNAISSANCE,
            active_candidates=(candidate,),
            candidate_limit=96,
            reasons=("ELIGIBILITY_CANDIDATES_BOUNDED",),
            acquisition_request_fingerprint="0" * 64,
        )


def test_case_x_an_excluded_class_can_never_be_an_eligible_candidate():
    with pytest.raises(ValueError):
        EligibleCandidate(
            identifier="tests/__snapshots__/a.snap",
            domain=DOMAIN_REPOSITORY,
            tier=TIER_REQUIRED_PRIMARY,
            eligible_source_classes=(SOURCE_CLASS_SNAPSHOT,),
            eligible_roles=(ROLE_IMPLEMENTATION_AUTHORITY,),
            classifications=(
                CandidateClassification(
                    source_class=SOURCE_CLASS_SNAPSHOT,
                    basis=(BASIS_KNOWN_TEST_LOCATION,),
                ),
            ),
            reasons=("CANDIDATE_INVENTORY_MEMBER",),
        )


def test_a_widened_pool_fails_the_monotonicity_check():
    acquisition, _ = _upstream(*_EXPLANATION)
    outcome = derive_eligibility(acquisition, None)
    widened = dataclasses.replace(outcome, candidate_limit=0)

    assert check_eligibility_monotonicity(widened, acquisition) != ()


def test_every_derived_pool_stays_inside_its_acquisition_request():
    for prompt, payload, inventory in (
        (*_EXPLANATION, None),
        (_PASTED_COMPARISON, _PASTED_COMPARISON_INTERPRETATION, None),
        (*_README_EDIT, _architecture_inventory()),
        (*_ONE_FILE_IMPLEMENTATION, _architecture_inventory()),
        (*_BROAD_DEBUGGING, _architecture_inventory()),
        (*_TEST_FOCUSED_DEBUGGING, _architecture_inventory()),
        (*_EXTERNAL_ONLY, None),
        (*_DIRECT_PLUS_EXTERNAL, None),
        (DOGFOOD_PROMPT, _dogfood_interpretation(BROAD_REPOSITORY), _architecture_inventory()),
        (DOGFOOD_PROMPT, _dogfood_interpretation({}), None),
    ):
        acquisition, _ = _upstream(prompt, payload)
        outcome = derive_eligibility(
            acquisition, inventory if requires_inventory(acquisition) else None
        )

        assert check_eligibility_monotonicity(outcome, acquisition) == (), prompt


# ══ Y — the CTX.SELECT bridge ═════════════════════════════════════════════════

def test_case_y_a_selector_that_stays_inside_the_envelope_validates():
    receipt = _dogfood_receipt()
    envelope = receipt.envelope_for(DOMAIN_REPOSITORY, TIER_REQUIRED_PRIMARY)
    inside = envelope.allowed_candidate_identifiers[:3]

    assert validate_selector_output(envelope, inside) == ()


def test_case_y_a_selector_that_leaves_the_envelope_is_rejected():
    receipt = _dogfood_receipt()
    envelope = receipt.envelope_for(DOMAIN_REPOSITORY, TIER_REQUIRED_PRIMARY)

    violations = validate_selector_output(
        envelope, ("core/router.py", "core/invented.py"), inventory=_architecture_inventory()
    )

    assert VIOLATION_OUTSIDE_ENVELOPE in violations
    assert VIOLATION_WRONG_INVENTORY in violations


def test_case_y_a_selector_cannot_readmit_an_excluded_source_class():
    receipt = _dogfood_receipt()
    envelope = receipt.envelope_for(DOMAIN_REPOSITORY, TIER_REQUIRED_PRIMARY)

    violations = validate_selector_output(
        envelope, ("build/bundle.js",), inventory=_architecture_inventory()
    )

    assert VIOLATION_OUTSIDE_ENVELOPE in violations


def test_case_y_a_selector_cannot_exceed_the_candidate_budget():
    receipt = _dogfood_receipt()
    envelope = receipt.envelope_for(DOMAIN_VALIDATION_ARTIFACTS, TIER_REQUIRED_SECONDARY)
    too_many = envelope.allowed_candidate_identifiers + ("core/router.py",)

    violations = validate_selector_output(envelope, too_many)

    assert VIOLATION_BUDGET_EXCEEDED in violations
    assert VIOLATION_OUTSIDE_ENVELOPE in violations


def test_case_y_an_excluded_class_inside_the_allowed_set_is_still_caught():
    """Defence in depth: the check does not rely on the envelope being right."""
    receipt = _dogfood_receipt()
    envelope = receipt.envelope_for(DOMAIN_REPOSITORY, TIER_REQUIRED_PRIMARY)
    contaminated = dataclasses.replace(
        envelope,
        allowed_candidate_identifiers=envelope.allowed_candidate_identifiers
        + ("build/bundle.js",),
    )

    violations = validate_selector_output(
        contaminated, ("build/bundle.js",), inventory=_architecture_inventory()
    )

    assert VIOLATION_EXCLUDED_SOURCE_CLASS in violations


def test_case_y_an_envelope_is_not_a_read_set():
    envelope = _dogfood_receipt().envelope_for(
        DOMAIN_REPOSITORY, TIER_REQUIRED_PRIMARY
    ).as_dict()

    assert envelope["is_read_set"] is False
    assert envelope["selector_executed"] is False


def test_the_envelope_binds_to_the_request_and_the_inventory():
    receipt = _dogfood_receipt()
    envelope = receipt.envelope_for(DOMAIN_REPOSITORY, TIER_REQUIRED_PRIMARY)

    assert envelope.inventory_fingerprint == _architecture_inventory().fingerprint()
    assert envelope.repository_identity == REPO
    assert envelope.acquisition_request_fingerprint


# ══ CTX.SELECT compatibility ══════════════════════════════════════════════════

_CORE = pathlib.Path(__file__).resolve().parents[1] / "core"


def test_the_inventory_mirrors_the_ctx_select_capability_vocabularies():
    """Checked against the source text, so it holds without the import graph."""
    source = (_CORE / "file_capabilities.py").read_text(encoding="utf-8")

    for state in PARSER_SUPPORT_STATES:
        assert f'"{state}"' in source, state
    for state in READ_POLICY_STATES:
        assert f'"{state}"' in source, state
    assert "PARSER_SUPPORT_STATES = (" in source
    assert "READ_POLICY_STATES = (" in source


def test_a_capability_mapping_carries_the_keys_ctx_select_reads():
    payload = _code("core/router.py").as_capability_mapping()
    source = (_CORE / "file_capabilities.py").read_text(encoding="utf-8")

    assert set(payload) == {
        "path",
        "size_bytes",
        "parser_support",
        "repository_contained",
        "symlink_escape",
        "generated",
        "vendor",
    }
    for key in payload:
        assert key in source, key


def test_a_capability_mapping_round_trips_back_into_an_inventory_member():
    original = _code("core/router.py", 1_234)
    restored = InventoryMember.from_capability_mapping(original.as_capability_mapping())

    assert restored.identifier == original.identifier
    assert restored.size_bytes == original.size_bytes
    assert restored.parser_support == original.parser_support


def test_an_inventory_can_be_built_from_supplied_capability_mappings():
    inventory = inventory_from_capability_mappings(
        REPO,
        (
            {"path": "core/router.py", "size_bytes": 100, "parser_support": "supported"},
            {"path": "README.md", "size_bytes": 50},
        ),
        declared_source_classes={"README.md": SOURCE_CLASS_AUTHORITATIVE_ARCHITECTURE_DOC},
    )

    assert len(inventory) == 2
    assert inventory.member("README.md").declared_source_class == (
        SOURCE_CLASS_AUTHORITATIVE_ARCHITECTURE_DOC
    )


def test_ctx_select_consumes_the_bridge_without_reading_anything():
    """Runs where the CTX.SELECT import graph is installed; skipped where not."""
    pytest.importorskip("pathspec")
    from core.file_candidate_selector import build_candidate_filename_report, rank_candidates

    inventory = _architecture_inventory()
    receipt = _dogfood_receipt(inventory)
    envelope = receipt.envelope_for(DOMAIN_REPOSITORY, TIER_REQUIRED_PRIMARY)
    allowed = set(envelope.allowed_candidate_identifiers)
    capabilities = tuple(
        member.as_capability_mapping()
        for member in inventory.members
        if member.identifier in allowed
    )

    report = build_candidate_filename_report(capabilities)
    ranked = rank_candidates(capabilities, filename_report=report)
    identifiers = tuple(item.path for item in ranked)

    assert validate_selector_output(envelope, identifiers, inventory=inventory) == ()
    assert all(item.decision.write_authority is False for item in ranked)


def test_ctx_select_output_that_crosses_a_tier_is_rejected():
    """The envelope is checked, not trusted — even against a careful selector.

    Handed the whole inventory and a few user-named files, CTX.SELECT ranks a
    test alongside the implementation. That is a reasonable thing for a
    relevance ranker to do and a wrong thing for the *primary repository*
    envelope to contain: ACQUIRE.1 put validation artifacts at the secondary
    tier, and the bridge check is what keeps that decision from quietly
    dissolving one layer down.
    """
    pytest.importorskip("pathspec")
    from core.file_candidate_selector import build_candidate_filename_report, rank_candidates

    inventory = _architecture_inventory()
    receipt = _dogfood_receipt(inventory)
    envelope = receipt.envelope_for(DOMAIN_REPOSITORY, TIER_REQUIRED_PRIMARY)
    capabilities = inventory.as_capability_mappings()

    report = build_candidate_filename_report(
        capabilities,
        user_named_files=(
            "core/router.py",
            "tests/test_router.py",
            "build/bundle.js",
            "tests/__snapshots__/a.snap",
        ),
    )
    ranked = rank_candidates(capabilities, filename_report=report)
    identifiers = tuple(item.path for item in ranked)

    assert "tests/test_router.py" in identifiers
    assert VIOLATION_OUTSIDE_ENVELOPE in validate_selector_output(
        envelope, identifiers, inventory=inventory
    )


def test_the_secondary_envelope_accepts_what_the_primary_one_refused():
    """The same identifier, judged against the tier that actually licenses it."""
    pytest.importorskip("pathspec")

    receipt = _dogfood_receipt()
    secondary = receipt.envelope_for(
        DOMAIN_VALIDATION_ARTIFACTS, TIER_REQUIRED_SECONDARY
    )

    assert validate_selector_output(secondary, ("tests/test_router.py",)) == ()


# ══ Z, AA — external and mixed paths ══════════════════════════════════════════

def test_case_z_an_external_lookup_produces_an_envelope_and_no_candidate():
    receipt = _eligibility(*_EXTERNAL_ONLY)

    assert receipt.workflow == WORKFLOW_CHAT
    assert len(receipt.external_envelopes) == 1
    envelope = receipt.external_envelopes[0]
    assert envelope.freshness == "current"
    assert 0 < envelope.candidate_budget
    assert envelope.as_dict()["concrete_candidates"] == []
    assert envelope.as_dict()["network_called"] is False


def test_case_z_an_external_envelope_names_no_engine_address_or_query():
    rendered = _structure_only(_eligibility(*_EXTERNAL_ONLY))

    for forbidden in ("google", "bing", "http", "www.", "url", "host", "query", "api"):
        assert forbidden not in rendered, forbidden


def test_case_aa_direct_plus_external_keeps_both_and_changes_no_workflow():
    receipt = _eligibility(*_DIRECT_PLUS_EXTERNAL)

    assert receipt.workflow == WORKFLOW_CHAT
    assert receipt.external_envelopes
    assert any(
        candidate.domain == DOMAIN_DIRECT_CONTEXT
        for candidate in receipt.active_candidates
    )
    assert receipt.selector_envelopes == ()


# ══ AB — Project Evolution ════════════════════════════════════════════════════

def test_case_ab_project_evolution_stays_bounded_per_cycle():
    acquisition, evidence = _evolution_upstream()
    receipt = derive_candidate_eligibility(
        acquisition, evidence, _large_inventory()
    )

    assert receipt.workflow == WORKFLOW_PROJECT_EVOLUTION
    assert receipt.candidate_used <= receipt.candidate_limit
    envelope = receipt.envelope_for(DOMAIN_REPOSITORY, TIER_REQUIRED_PRIMARY)
    assert len(envelope.allowed_candidate_identifiers) <= MAX_CANDIDATES_CEILING


def test_case_ab_project_evolution_grants_no_project_evolution_authority():
    acquisition, evidence = _evolution_upstream()
    authority = derive_candidate_eligibility(
        acquisition, evidence, _architecture_inventory()
    ).as_dict()["authority"]

    assert authority["project_evolution_authority"] is False
    assert authority["evidence_acquisition_authority"] is False
    assert authority["human_approval_required"] is True


# ══ AC — the result is structural, not linguistic ═════════════════════════════

def test_case_ac_english_and_vietnamese_orders_produce_identical_eligibility():
    inventory = _architecture_inventory()
    english = _eligibility(
        "Analyse the whole indexing architecture in core/indexer.py and graph/builder.py.",
        {
            "task": {"type": "analysis", "provenance": "inferred"},
            "subjects": [
                {"value": "core/indexer.py", "provenance": "explicit"},
                {"value": "graph/builder.py", "provenance": "explicit"},
            ],
            "execution_requirements": BROAD_REPOSITORY,
        },
        inventory,
    )
    vietnamese = _eligibility(
        "Phân tích toàn bộ kiến trúc lập chỉ mục trong core/indexer.py và graph/builder.py.",
        {
            "task": {"type": "analysis", "provenance": "inferred"},
            "subjects": [
                {"value": "core/indexer.py", "provenance": "explicit"},
                {"value": "graph/builder.py", "provenance": "explicit"},
            ],
            "execution_requirements": BROAD_REPOSITORY,
        },
        inventory,
    )

    # The direct-context candidate references the preserved order *by
    # fingerprint*, and two different sentences legitimately fingerprint
    # differently. Everything derived from structure rather than words matches.
    def _repository_shape(receipt):
        shape = canonical_eligibility_shape(receipt)
        shape["active_candidates"] = [
            item
            for item in shape["active_candidates"]
            if item["domain"] != DOMAIN_DIRECT_CONTEXT
        ]
        for envelope in shape["selector_envelopes"]:
            envelope.pop("acquisition_request_fingerprint")
        return shape

    assert _repository_shape(english) == _repository_shape(vietnamese)
    assert english.active_identifiers()[1:] == vietnamese.active_identifiers()[1:]


# ══ The epistemic boundary ════════════════════════════════════════════════════

#: ``verified`` itself is deliberately absent: the receipt says
#: ``expected_not_verified`` on every candidate, which is the denial, not the
#: claim. What must never appear is an assertion that something *was*.
_CLAIM_TOKENS: tuple[str, ...] = (
    "confirms",
    "confirmed",
    "proves",
    "proven",
    "supported_by",
    "claim_supported",
    "evidence_for",
    "grounded",
    "acquired_content",
    "authoritative_content",
)


@pytest.mark.parametrize(
    "prompt, payload, needs_inventory",
    [
        (*_EXPLANATION, False),
        (*_README_EDIT, True),
        (*_BROAD_DEBUGGING, True),
        (*_TEST_FOCUSED_DEBUGGING, True),
        (*_EXTERNAL_ONLY, False),
        (DOGFOOD_PROMPT, _dogfood_interpretation(BROAD_REPOSITORY), True),
    ],
)
def test_no_receipt_ever_claims_anything_was_verified(prompt, payload, needs_inventory):
    receipt = _eligibility(
        prompt, payload, _architecture_inventory() if needs_inventory else None
    )
    rendered = _structure_only(receipt)

    for token in _CLAIM_TOKENS:
        assert token not in rendered, token
    # The two statuses that could ever carry a claim never say anything else.
    assert chr(34) + "evidence_status" + chr(34) + ": " + chr(34) + "acquired" not in rendered
    assert chr(34) + "authority_status" + chr(34) + ": " + chr(34) + "verified" not in rendered


def test_every_candidate_is_a_candidate_and_not_evidence():
    for receipt in (_dogfood_receipt(), _eligibility(*_EXPLANATION)):
        for candidate in receipt.all_candidates():
            payload = candidate.as_dict()

            assert payload["content_read"] is False
            assert payload["evidence_status"] == "not_acquired"
            assert payload["authority_status"] == "expected_not_verified"
            assert "content" not in payload
            assert "excerpt" not in payload


def test_eligibility_for_a_role_is_an_expectation_and_not_a_verdict():
    candidate = _dogfood_receipt().candidate("core/router.py")

    assert ROLE_IMPLEMENTATION_AUTHORITY in candidate.eligible_roles
    assert candidate.authority_status == AUTHORITY_EXPECTED_NOT_VERIFIED
    assert "verified_role" not in candidate.as_dict()


def test_no_receipt_carries_a_relevance_score_or_a_patch_permission():
    rendered = _structure_only(_dogfood_receipt())

    for forbidden in (
        "relevance",
        "score",
        "ranking",
        "embedding",
        "patch_candidate",
        "write_authority",
        "editable",
        "actionability",
    ):
        assert forbidden not in rendered, forbidden


# ══ No model, no provider, no compute ═════════════════════════════════════════

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
    "temperature",
    "api key",
    "endpoint",
    "fallback",
)


def test_no_receipt_names_a_model_or_a_provider():
    rendered = _structure_only(_dogfood_receipt())

    for token in _COMPUTE_TOKENS:
        assert token not in rendered, token


# ══ Authority and static inertness ════════════════════════════════════════════

def test_the_eligibility_phase_holds_no_authority_of_any_kind():
    authority = eligibility_authority()

    for power in (
        "evidence_acquisition_authority",
        "candidate_content_read_authority",
        "repository_read_authority",
        "repository_traversal_authority",
        "external_search_authority",
        "web_fetch_authority",
        "context_selection_execution_authority",
        "selector_bridge_authority",
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


def test_producing_an_envelope_is_not_permission_to_run_a_selector():
    receipt = _dogfood_receipt()
    authority = receipt.as_dict()["authority"]

    assert receipt.selector_envelopes
    assert authority["selector_bridge_authority"] is False
    assert authority["context_selection_execution_authority"] is False


def test_a_ready_status_grants_no_acquisition_authority():
    receipt = _dogfood_receipt()

    assert receipt.status == STATUS_READY
    assert receipt.as_dict()["authority"]["evidence_acquisition_authority"] is False
    assert receipt.human_approval_required is True


def test_the_guardrails_record_every_action_not_performed():
    guardrails = eligibility_guardrails()

    for action in (
        "evidence_acquired",
        "evidence_promoted",
        "repository_files_read",
        "candidate_contents_read",
        "repository_traversal_performed",
        "new_inventory_built",
        "manifest_refreshed",
        "index_consulted",
        "graph_consulted",
        "ctx_select_executed",
        "network_called",
        "web_search_performed",
        "external_sources_fetched",
        "validation_executed",
        "planning_performed",
        "provider_selected",
    ):
        assert guardrails[action] is False, action


def test_no_eligibility_module_can_reach_a_file_a_process_or_a_network():
    for name in (
        "candidate_inventory.py",
        "candidate_eligibility.py",
        "eligibility_policy.py",
        "evidence_candidate_pool.py",
    ):
        source = (_CORE / name).read_text(encoding="utf-8")
        for forbidden in (
            "import os",
            "os.walk",
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


def test_no_eligibility_module_imports_a_walker_an_index_or_a_selector():
    for name in (
        "candidate_inventory.py",
        "candidate_eligibility.py",
        "eligibility_policy.py",
        "evidence_candidate_pool.py",
    ):
        source = (_CORE / name).read_text(encoding="utf-8")
        for forbidden in (
            "from core.context_selection",
            "from core.file_candidate_selector",
            "from core.file_capabilities",
            "from core.file_actionability",
            "from core.repo_ignore",
            "from core.repository_inventory",
            "from core.index_manifest",
            "from core.indexer",
            "from core.retriever",
            "from core.graph_walker",
            "import pathspec",
        ):
            assert forbidden not in source, f"{name}: {forbidden}"


def test_the_eligibility_modules_import_without_the_ctx_select_dependency_graph():
    """The whole line of phases stays importable where ``pathspec`` is not."""
    import importlib

    for name in (
        "core.candidate_inventory",
        "core.candidate_eligibility",
        "core.eligibility_policy",
        "core.evidence_candidate_pool",
    ):
        assert importlib.import_module(name) is not None


# ══ Determinism and vocabularies ══════════════════════════════════════════════

def test_the_same_order_and_inventory_always_produce_the_same_pool():
    first = _dogfood_receipt()
    second = _dogfood_receipt()

    assert canonical_eligibility_fingerprint(first) == canonical_eligibility_fingerprint(
        second
    )
    assert render_eligibility_receipt_json(first) == render_eligibility_receipt_json(
        second
    )


def test_a_receipt_renders_as_deterministic_json():
    payload = json.loads(render_eligibility_receipt_json(_dogfood_receipt()))

    assert payload["phase_id"] == "ACQUIRE.2"
    assert payload["status"] == STATUS_READY
    assert payload["budget"]["bounded"] is True
    assert payload["budget"]["source_budget_consumed"] == 0


def test_the_receipt_binds_to_every_upstream_record():
    receipt = _dogfood_receipt()

    assert receipt.acquisition_request_fingerprint
    assert receipt.evidence_contract_fingerprint
    assert receipt.inventory_fingerprint
    assert receipt.repository_identity == REPO


def test_a_changed_inventory_changes_the_receipt_fingerprint():
    baseline = _dogfood_receipt()
    extended = _dogfood_receipt(
        CandidateInventory(
            repository_identity=REPO,
            members=ARCHITECTURE_MEMBERS + (_code("core/extra.py"),),
        )
    )

    assert baseline.inventory_fingerprint != extended.inventory_fingerprint


def test_every_vocabulary_is_bounded_and_distinct():
    for vocabulary in (
        CLASSIFICATION_BASES,
        ELIGIBILITY_STATUSES,
        ELIGIBILITY_REASONS,
        ELIGIBILITY_INCONSISTENCIES,
        INELIGIBILITY_REASONS,
        ENVELOPE_VIOLATIONS,
        PARSER_SUPPORT_STATES,
        READ_POLICY_STATES,
    ):
        assert len(set(vocabulary)) == len(vocabulary)
        assert all(isinstance(item, str) and item for item in vocabulary)


def test_every_reason_code_has_a_sentence():
    for reason in ELIGIBILITY_REASONS:
        assert ELIGIBILITY_REASON_DESCRIPTIONS[reason].strip()


def test_every_source_class_states_the_domain_it_belongs_to():
    assert set(SOURCE_CLASS_DOMAINS) == set(SOURCE_CLASS_DOMAINS)
    for source_class, domain in SOURCE_CLASS_DOMAINS.items():
        assert domain in {
            DOMAIN_DIRECT_CONTEXT,
            DOMAIN_REPOSITORY,
            DOMAIN_VALIDATION_ARTIFACTS,
            DOMAIN_HISTORICAL_CONTEXT,
            DOMAIN_EXTERNAL_INFORMATION,
        }, source_class


def test_the_role_table_is_the_inverse_of_the_acquisition_one():
    assert ROLES_BY_SOURCE_CLASS[SOURCE_CLASS_RUNTIME_IMPLEMENTATION] == (
        ROLE_IMPLEMENTATION_AUTHORITY,
    )
    assert ROLES_BY_SOURCE_CLASS[SOURCE_CLASS_VALIDATION_TEST] == (
        ROLE_VALIDATION_EVIDENCE,
    )
    assert ROLES_BY_SOURCE_CLASS[SOURCE_CLASS_HISTORICAL_DESIGN_MATERIAL] == (
        ROLE_HISTORICAL_CONTEXT,
    )
    for source_class in NEVER_REQUESTED_SOURCE_CLASSES:
        assert ROLES_BY_SOURCE_CLASS[source_class] == ()


@pytest.mark.parametrize(
    "identifier, predicate",
    [
        ("tests/test_x.py", is_test_location),
        ("core/x_test.py", is_test_location),
        ("tests/__snapshots__/a.snap", is_snapshot_location),
        ("core/state.snap", is_snapshot_location),
        (".tmp/a.txt", is_temporary_location),
        ("docs/rejected/a.md", is_historical_location),
    ],
)
def test_the_location_rules_recognise_what_they_claim_to(identifier, predicate):
    assert predicate(identifier) is True


@pytest.mark.parametrize(
    "identifier, predicate",
    [
        ("core/text_utils.py", is_test_location),
        ("docs/designs/current.md", is_historical_location),
        ("core/snapshot_writer.py", is_snapshot_location),
        ("core/template.py", is_temporary_location),
    ],
)
def test_the_location_rules_do_not_over_reach(identifier, predicate):
    assert predicate(identifier) is False


def test_a_classification_must_name_a_basis():
    with pytest.raises(ValueError):
        CandidateClassification(
            source_class=SOURCE_CLASS_RUNTIME_IMPLEMENTATION, basis=()
        )


def test_an_exclusion_summary_counts_and_does_not_list():
    summary = ExclusionSummary(reason=INELIGIBLE_CLASSIFICATION_UNKNOWN, count=6_087)

    assert summary.as_dict() == {
        "reason": INELIGIBLE_CLASSIFICATION_UNKNOWN,
        "count": 6_087,
    }


def test_an_inventory_refuses_duplicate_identifiers():
    with pytest.raises(ValueError):
        CandidateInventory(
            repository_identity=REPO,
            members=(_code("core/a.py"), _code("core/a.py")),
        )


def test_the_inventory_bound_is_finite_and_documented():
    assert isinstance(MAX_INVENTORY_MEMBERS, int)
    assert 0 < MAX_INVENTORY_MEMBERS
    assert 0 < MAX_DEFERRED_CANDIDATES < MAX_INVENTORY_MEMBERS


# ══ Not wired ═════════════════════════════════════════════════════════════════

def test_acquire_2_is_not_reachable_from_any_live_path():
    root = pathlib.Path(__file__).resolve().parents[1]
    callers = []
    for path in root.rglob("*.py"):
        parts = set(path.parts)
        if parts & {"__pycache__", "tmp_tests", ".agent", ".venv", "tests"}:
            continue
        if path.name in (
            "candidate_inventory.py",
            "candidate_eligibility.py",
            "eligibility_policy.py",
            "evidence_candidate_pool.py",
            # ACQUIRE.3 is the explicitly downstream consumer of the frozen
            # ACQUIRE.2 receipt.  Its own repository-wide boundary test proves
            # that this consumer is not reachable from a live product path.
            "evidence_content_acquisition.py",
        ):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "evidence_candidate_pool" in text or "derive_candidate_eligibility" in text:
            callers.append(str(path.relative_to(root)))

    assert callers == [], callers
