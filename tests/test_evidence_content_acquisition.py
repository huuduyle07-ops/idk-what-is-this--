"""ACQUIRE.3 bounded source acquisition and receipt regressions.

Every actual read in this file targets a tiny pytest-created repository.  No
test invokes ACQUIRE.3 against the C.A.T.T.U.S working tree and no test uses a
network or provider.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import stat
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

import pytest

import core.evidence_content_acquisition as acquisition_runtime
from core.candidate_eligibility import (
    CANDIDATE_RECEIPT_SCHEMA_VERSION,
)
from core.candidate_inventory import CandidateInventory, InventoryMember
from core.content_acquisition import (
    ACQUISITION_AUTHORIZATION_VALIDATED,
    AUTHORIZATION_BOUNDED_REPOSITORY_READ,
    AUTHORIZATION_EXISTING_CONTEXT_REFERENCE,
    AUTHORIZATION_EXPLICIT_HUMAN_APPROVAL,
    AUTHORIZATION_EXTERNAL_DISCOVERY_ACKNOWLEDGED,
    AUTHORITY_NOT_VERIFIED,
    FAILURE_CANDIDATE_MISSING,
    FAILURE_CANDIDATE_STALE,
    FAILURE_NON_REGULAR_FILE,
    FAILURE_READ_ERROR,
    FAILURE_STALE_DURING_ACQUISITION,
    FAILURE_SYMLINK_REJECTED,
    FAILURE_UNSAFE_PATH,
    INCONSISTENT_AUTHORIZATION_BINDING,
    INCONSISTENT_AUTHORIZATION_CANDIDATE,
    INCONSISTENT_AUTHORIZATION_WIDENED,
    INCONSISTENT_CANDIDATE_RECEIPT,
    INCONSISTENT_INVENTORY,
    INCONSISTENT_REPOSITORY_ROOT_INVALID,
    INCONSISTENT_SELECTION_BUDGET,
    INCONSISTENT_SELECTION_DEFERRED,
    INCONSISTENT_SELECTION_OUTSIDE_POOL,
    MODE_EXISTING_CONTEXT,
    MODE_REPOSITORY_READ,
    SELECTION_SOURCE_CTX_SELECT,
    STATUS_ACQUIRED,
    STATUS_AUTHORIZATION_REQUIRED,
    STATUS_BLOCKED,
    STATUS_BUDGET_BLOCKED,
    STATUS_EXTERNAL_DISCOVERY_REQUIRED,
    STATUS_PARTIAL,
    STATUS_STALE_CANDIDATES,
    VERIFICATION_UNVERIFIED,
    AcquisitionAuthorization,
    AcquisitionBudgetSummary,
    AcquisitionSelection,
    authorization_fingerprint,
    render_content_acquisition_result_json,
    selection_fingerprint,
)
from core.eligibility_policy import MAX_DEFERRED_CANDIDATES
from core.evidence_acquire_request import derive_acquisition_requests
from core.evidence_candidate_pool import derive_candidate_eligibility
from core.evidence_content_acquisition import (
    acquire_selected_content,
    acquisition_request_fingerprint,
    candidate_receipt_fingerprint,
)
from core.evidence_requirements import (
    DOMAIN_DIRECT_CONTEXT,
    DOMAIN_EXTERNAL_INFORMATION,
    DOMAIN_REPOSITORY,
    DOMAIN_VALIDATION_ARTIFACTS,
    EVIDENCE_DOMAINS,
    ROLE_IMPLEMENTATION_AUTHORITY,
    ROLE_VALIDATION_EVIDENCE,
    TIER_DEFERRED,
    TIER_REQUIRED_PRIMARY,
    TIER_REQUIRED_SECONDARY,
)
from core.execution_waiter import route_execution_workflow
from core.input_completion import complete_intake_from_semantic_outcome
from core.intake_completion import STATE_READY
from core.semantic_waiter_adapter import (
    ScriptedSemanticModelClient,
    SemanticWaiterModelAdapter,
)
from core.semantic_waiter_runner import understand_request_semantically
from core.waiter_evidence import derive_evidence_requirements


REPOSITORY_IDENTITY = "acquire-3-fixture"
BOUNDED_REPOSITORY = {
    "repository_inspection_required": True,
    "local_repository_required": True,
}
BROAD_REPOSITORY = {
    "multi_stage": True,
    "repository_inspection_required": True,
    "local_repository_required": True,
}


@lru_cache(maxsize=32)
def _upstream_cached(prompt: str, payload_json: str):
    payload = json.loads(payload_json)
    adapter = SemanticWaiterModelAdapter(
        ScriptedSemanticModelClient([json.dumps(payload)])
    )
    outcome = understand_request_semantically(prompt, adapter=adapter)
    completion_outcome = complete_intake_from_semantic_outcome(outcome)
    assert completion_outcome.state == STATE_READY
    completion = completion_outcome.decision
    decision = route_execution_workflow(outcome.contract, completion)
    evidence = derive_evidence_requirements(
        decision, outcome.contract, completion
    )
    acquisition = derive_acquisition_requests(
        evidence, decision, outcome.contract, completion
    )
    assert acquisition.ready
    return acquisition, evidence


def _upstream(prompt: str, payload: dict):
    return _upstream_cached(
        prompt,
        json.dumps(payload, ensure_ascii=False, sort_keys=True),
    )


def _implementation_upstream(target: str = "a.py", *, broad: bool = False):
    prompt = f"Investigate and update {target}." if broad else f"Implement the change in {target}."
    payload = {
        "task": {
            "type": "debugging" if broad else "implementation",
            "provenance": "inferred",
        },
        "subjects": [{"value": target, "provenance": "explicit"}],
        "execution_requirements": BROAD_REPOSITORY if broad else BOUNDED_REPOSITORY,
    }
    return _upstream(prompt, payload)


def _test_debugging_upstream(target: str = "tests/test_indexer.py"):
    return _upstream(
        f"Investigate why {target} fails after the last change.",
        {
            "task": {"type": "debugging", "provenance": "inferred"},
            "subjects": [{"value": target, "provenance": "explicit"}],
            "execution_requirements": BOUNDED_REPOSITORY,
        },
    )


def _direct_context_upstream():
    return _upstream(
        "Explain the Bellman equation.",
        {"task": {"type": "question", "provenance": "inferred"}},
    )


def _external_upstream():
    return _upstream(
        "What is the current stable release of Python?",
        {
            "task": {"type": "question", "provenance": "inferred"},
            "execution_requirements": {"external_information_required": True},
        },
    )


def _direct_plus_external_upstream():
    subjects = [
        "this supplied API description",
        "current official API",
    ]
    return _upstream(
        "Compare this supplied API description with the current official API:\n\n"
        "`GET /v1/items -> {items: []}`\n",
        {
            "task": {
                "type": "comparative_analysis",
                "provenance": "inferred",
            },
            "subjects": [
                {"value": subject, "provenance": "explicit"}
                for subject in subjects
            ],
            "relationships": [
                {
                    "type": "comparison",
                    "subjects": subjects,
                    "provenance": "explicit",
                }
            ],
            "execution_requirements": {"external_information_required": True},
        },
    )


def _repository_plus_external_upstream():
    subjects = [
        "our retry policy in core/executor.py",
        "current published guidance for exponential backoff",
    ]
    return _upstream(
        "Compare our retry policy in core/executor.py against the current "
        "published guidance for exponential backoff.",
        {
            "task": {
                "type": "comparative_analysis",
                "provenance": "inferred",
            },
            "subjects": [
                {"value": subject, "provenance": "explicit"}
                for subject in subjects
            ],
            "relationships": [
                {
                    "type": "comparison",
                    "subjects": subjects,
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


def _member(identifier: str, size: int | None, **kwargs) -> InventoryMember:
    parser_support = kwargs.pop("parser_support", "supported")
    return InventoryMember(
        identifier,
        size_bytes=size,
        parser_support=parser_support,
        **kwargs,
    )


def _inventory(*members: InventoryMember) -> CandidateInventory:
    return CandidateInventory(
        repository_identity=REPOSITORY_IDENTITY,
        members=tuple(members),
    )


def _eligibility(acquisition, evidence, inventory=None):
    return derive_candidate_eligibility(acquisition, evidence, inventory)


def _selection(acquisition, receipt, identifiers=(), *, source="human_selection"):
    ordered = tuple(sorted(identifiers, key=lambda item: (item.casefold(), item)))
    return AcquisitionSelection(
        candidate_identifiers=ordered,
        candidate_receipt_fingerprint=candidate_receipt_fingerprint(receipt),
        acquisition_request_fingerprint=acquisition_request_fingerprint(acquisition),
        inventory_fingerprint=receipt.inventory_fingerprint,
        repository_identity=receipt.repository_identity,
        source=source,
    )


def _canonical_domains(values) -> tuple[str, ...]:
    present = set(values)
    return tuple(domain for domain in EVIDENCE_DOMAINS if domain in present)


def _authorization(
    acquisition,
    receipt,
    selection,
    *,
    root: Path | str | None = None,
    allowed_identifiers=None,
    allowed_domains=None,
    max_sources=None,
    max_total_bytes=None,
    max_per_source_bytes=None,
):
    identifiers = tuple(
        sorted(
            selection.candidate_identifiers
            if allowed_identifiers is None
            else tuple(allowed_identifiers),
            key=lambda item: (item.casefold(), item),
        )
    )
    candidates = [receipt.candidate(identifier) for identifier in identifiers]
    candidates = [candidate for candidate in candidates if candidate is not None]
    domains = (
        _canonical_domains(candidate.domain for candidate in candidates)
        if allowed_domains is None
        else _canonical_domains(allowed_domains)
    )
    file_sizes = [
        int(candidate.size_bytes or 0)
        for candidate in candidates
        if candidate.domain in {DOMAIN_REPOSITORY, DOMAIN_VALIDATION_ARTIFACTS}
    ]
    reasons = [AUTHORIZATION_EXPLICIT_HUMAN_APPROVAL]
    if set(domains) & {DOMAIN_REPOSITORY, DOMAIN_VALIDATION_ARTIFACTS}:
        reasons.append(AUTHORIZATION_BOUNDED_REPOSITORY_READ)
    if DOMAIN_DIRECT_CONTEXT in set(domains):
        reasons.append(AUTHORIZATION_EXISTING_CONTEXT_REFERENCE)
    if DOMAIN_EXTERNAL_INFORMATION in set(domains):
        reasons.append(AUTHORIZATION_EXTERNAL_DISCOVERY_ACKNOWLEDGED)
    return AcquisitionAuthorization(
        acquisition_allowed=True,
        human_approved=True,
        candidate_pool_fingerprint=candidate_receipt_fingerprint(receipt),
        acquisition_request_fingerprint=acquisition_request_fingerprint(acquisition),
        inventory_fingerprint=receipt.inventory_fingerprint,
        repository_identity=receipt.repository_identity,
        repository_root=str(Path(root).resolve()) if root is not None else None,
        allowed_candidate_identifiers=identifiers,
        allowed_domains=domains,
        max_sources=len(identifiers) if max_sources is None else max_sources,
        max_total_bytes=(
            sum(file_sizes) if max_total_bytes is None else max_total_bytes
        ),
        max_per_source_bytes=(
            max(file_sizes, default=0)
            if max_per_source_bytes is None
            else max_per_source_bytes
        ),
        reasons=tuple(reasons),
    )


def _write(root: Path, identifier: str, content: bytes) -> Path:
    target = root.joinpath(*identifier.split("/"))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return target


def _repository_case(
    root: Path,
    files: dict[str, bytes],
    *,
    target: str = "a.py",
    extra_members: tuple[InventoryMember, ...] = (),
    broad: bool = False,
):
    for identifier, content in files.items():
        _write(root, identifier, content)
    inventory = _inventory(
        *(
            _member(identifier, len(content))
            for identifier, content in files.items()
        ),
        *extra_members,
    )
    acquisition, evidence = _implementation_upstream(target, broad=broad)
    receipt = _eligibility(acquisition, evidence, inventory)
    return acquisition, receipt, inventory


def _run(root, acquisition, receipt, inventory, identifiers, **authorization_kwargs):
    selection = _selection(acquisition, receipt, identifiers)
    authorization = _authorization(
        acquisition,
        receipt,
        selection,
        root=root,
        **authorization_kwargs,
    )
    result = acquire_selected_content(
        acquisition,
        receipt,
        selection,
        authorization,
        inventory=inventory,
    )
    return result, selection, authorization


# ── authorization and binding gates ──────────────────────────────────────────


def test_no_authorization_performs_no_filesystem_access(tmp_path, monkeypatch):
    acquisition, receipt, inventory = _repository_case(tmp_path, {"a.py": b"a"})
    selection = _selection(acquisition, receipt, ("a.py",))
    monkeypatch.setattr(
        acquisition_runtime,
        "_candidate_lstat",
        lambda path: pytest.fail(f"filesystem touched without authorization: {path}"),
    )

    result = acquire_selected_content(
        acquisition, receipt, selection, inventory=inventory
    )

    assert result.status == STATUS_AUTHORIZATION_REQUIRED
    assert result.acquired_receipts == ()
    assert result.as_dict()["authority"]["repository_read_authority"] is False


def test_human_approved_false_performs_no_filesystem_access(tmp_path, monkeypatch):
    acquisition, receipt, inventory = _repository_case(tmp_path, {"a.py": b"a"})
    selection = _selection(acquisition, receipt, ("a.py",))
    granted = _authorization(acquisition, receipt, selection, root=tmp_path)
    authorization = dataclasses.replace(
        granted,
        human_approved=False,
        reasons=(AUTHORIZATION_BOUNDED_REPOSITORY_READ,),
    )
    monkeypatch.setattr(
        acquisition_runtime,
        "_candidate_lstat",
        lambda path: pytest.fail(f"filesystem touched without human approval: {path}"),
    )

    result = acquire_selected_content(
        acquisition, receipt, selection, authorization, inventory=inventory
    )

    assert result.status == STATUS_AUTHORIZATION_REQUIRED
    assert result.human_approval_present is False


def test_authorization_fingerprint_mismatch_blocks_before_root_access(
    tmp_path, monkeypatch
):
    acquisition, receipt, inventory = _repository_case(tmp_path, {"a.py": b"a"})
    selection = _selection(acquisition, receipt, ("a.py",))
    authorization = dataclasses.replace(
        _authorization(acquisition, receipt, selection, root=tmp_path),
        candidate_pool_fingerprint="0" * 64,
    )
    monkeypatch.setattr(
        acquisition_runtime,
        "_candidate_lstat",
        lambda path: pytest.fail(f"root touched before fingerprint gate: {path}"),
    )

    result = acquire_selected_content(
        acquisition, receipt, selection, authorization, inventory=inventory
    )

    assert result.status == STATUS_BLOCKED
    assert INCONSISTENT_AUTHORIZATION_BINDING in result.inconsistencies


def test_authorization_cannot_add_a_candidate(tmp_path):
    acquisition, receipt, inventory = _repository_case(tmp_path, {"a.py": b"a"})
    selection = _selection(acquisition, receipt, ("a.py",))
    authorization = _authorization(
        acquisition,
        receipt,
        selection,
        root=tmp_path,
        allowed_identifiers=("a.py", "invented.py"),
        max_sources=2,
    )

    result = acquire_selected_content(
        acquisition, receipt, selection, authorization, inventory=inventory
    )

    assert result.status == STATUS_BLOCKED
    assert INCONSISTENT_AUTHORIZATION_CANDIDATE in result.inconsistencies


def test_authorization_budget_cannot_exceed_acquire_1(tmp_path, monkeypatch):
    acquisition, receipt, inventory = _repository_case(tmp_path, {"a.py": b"a"})
    selection = _selection(acquisition, receipt, ("a.py",))
    authorization = _authorization(
        acquisition,
        receipt,
        selection,
        root=tmp_path,
        max_sources=9,
    )
    monkeypatch.setattr(
        acquisition_runtime,
        "_open_readonly",
        lambda path: pytest.fail(f"read attempted under widened grant: {path}"),
    )

    result = acquire_selected_content(
        acquisition, receipt, selection, authorization, inventory=inventory
    )

    assert result.status == STATUS_BUDGET_BLOCKED
    assert INCONSISTENT_AUTHORIZATION_WIDENED in result.inconsistencies


def test_authorization_may_narrow_and_fingerprints_are_deterministic(tmp_path):
    acquisition, receipt, inventory = _repository_case(
        tmp_path, {"a.py": b"alpha", "b.py": b"bravo"}
    )
    selection = _selection(acquisition, receipt, ("a.py",))
    authorization = _authorization(acquisition, receipt, selection, root=tmp_path)

    first = acquire_selected_content(
        acquisition, receipt, selection, authorization, inventory=inventory
    )
    second = acquire_selected_content(
        acquisition, receipt, selection, authorization, inventory=inventory
    )

    assert first.status == STATUS_ACQUIRED
    assert first.selection_fingerprint == second.selection_fingerprint
    assert first.authorization_fingerprint == second.authorization_fingerprint
    assert first.selection_fingerprint == selection_fingerprint(selection)
    assert first.authorization_fingerprint == authorization_fingerprint(authorization)


def test_authorization_allowlist_is_an_envelope_not_the_spent_selection(
    tmp_path, monkeypatch
):
    acquisition, receipt, inventory = _repository_case(
        tmp_path,
        {"a.py": b"a", "b.py": b"b", "c.py": b"c"},
        target="b.py",
    )
    selection = _selection(acquisition, receipt, ("b.py",))
    authorization = _authorization(
        acquisition,
        receipt,
        selection,
        root=tmp_path,
        allowed_identifiers=("a.py", "b.py", "c.py"),
        max_sources=1,
        max_total_bytes=1,
        max_per_source_bytes=1,
    )
    touched: list[str] = []
    opened: list[str] = []
    original = acquisition_runtime._candidate_lstat
    original_open = acquisition_runtime._open_readonly

    def spy(path):
        if path.name in {"a.py", "b.py", "c.py"}:
            touched.append(path.name)
        return original(path)

    monkeypatch.setattr(acquisition_runtime, "_candidate_lstat", spy)
    monkeypatch.setattr(
        acquisition_runtime,
        "_open_readonly",
        lambda path: (opened.append(path.name), original_open(path))[1],
    )

    result = acquire_selected_content(
        acquisition, receipt, selection, authorization, inventory=inventory
    )

    assert result.status == STATUS_ACQUIRED
    assert result.payloads[0].content == b"b"
    assert set(touched) == {"b.py"}
    assert set(opened) == {"b.py"}


def test_mixed_direct_context_does_not_lower_repository_per_source_limit(tmp_path):
    content = b"x" * 100_000
    acquisition, receipt, inventory = _repository_case(
        tmp_path, {"core/a.py": content}, target="core/a.py", broad=True
    )
    direct = next(
        candidate
        for candidate in receipt.active_candidates
        if candidate.domain == DOMAIN_DIRECT_CONTEXT
    )
    selection = _selection(acquisition, receipt, ("core/a.py", direct.identifier))
    authorization = _authorization(
        acquisition,
        receipt,
        selection,
        root=tmp_path,
        max_sources=2,
        max_total_bytes=len(content),
        max_per_source_bytes=len(content),
    )

    result = acquire_selected_content(
        acquisition, receipt, selection, authorization, inventory=inventory
    )

    assert result.status == STATUS_ACQUIRED
    assert result.payloads[0].content == content
    assert len(result.direct_context_receipts) == 1


def test_selection_rejects_unserializable_or_overlong_identifiers():
    for identifier in ("\ud800", "x" * 1_025):
        with pytest.raises(ValueError):
            AcquisitionSelection(
                candidate_identifiers=(identifier,),
                candidate_receipt_fingerprint="0" * 64,
                acquisition_request_fingerprint="1" * 64,
            )


def test_authorization_rejects_control_surrogate_and_network_share_roots(
    tmp_path
):
    acquisition, receipt, inventory = _repository_case(tmp_path, {"a.py": b"a"})
    selection = _selection(acquisition, receipt, ("a.py",))
    authorization = _authorization(
        acquisition, receipt, selection, root=tmp_path
    )

    for root in (str(tmp_path) + "\x00bad", "C:\\" + "\ud800", r"\\server\share"):
        with pytest.raises(ValueError):
            dataclasses.replace(authorization, repository_root=root)


def test_tampered_nul_root_returns_bounded_invalid_root_result(tmp_path):
    acquisition, receipt, inventory = _repository_case(tmp_path, {"a.py": b"a"})
    selection = _selection(acquisition, receipt, ("a.py",))
    authorization = _authorization(
        acquisition, receipt, selection, root=tmp_path
    )
    object.__setattr__(
        authorization, "repository_root", str(tmp_path.resolve()) + "\x00bad"
    )

    result = acquire_selected_content(
        acquisition, receipt, selection, authorization, inventory=inventory
    )

    assert result.status == STATUS_BLOCKED
    assert INCONSISTENT_REPOSITORY_ROOT_INVALID in result.inconsistencies


# ── exact read, path safety and staleness ─────────────────────────────────────


def test_valid_tiny_source_reads_exact_bytes_and_sha256(tmp_path):
    content = b"\x00alpha\xff"
    acquisition, receipt, inventory = _repository_case(tmp_path, {"a.py": content})

    result, _, _ = _run(tmp_path, acquisition, receipt, inventory, ("a.py",))

    source = result.acquired_receipts[0]
    assert result.status == STATUS_ACQUIRED
    assert result.payloads[0].content == content
    assert source.content_sha256 == hashlib.sha256(content).hexdigest()
    assert source.bytes_acquired == len(content)
    assert source.acquisition_mode == MODE_REPOSITORY_READ
    assert source.verification_status == VERIFICATION_UNVERIFIED
    assert source.authority_status == AUTHORITY_NOT_VERIFIED
    assert source.expected_roles == (ROLE_IMPLEMENTATION_AUTHORITY,)
    assert result.budget.bytes_acquired == len(content)
    assert result.budget.bytes_remaining == 0


@pytest.mark.parametrize(
    "identifier",
    (
        "invented.py",
        "../escape.py",
        "/absolute.py",
        "C:/absolute.py",
    ),
)
def test_outside_or_arbitrary_selection_never_reaches_filesystem(
    tmp_path, monkeypatch, identifier
):
    acquisition, receipt, inventory = _repository_case(tmp_path, {"a.py": b"a"})
    selection = _selection(acquisition, receipt, (identifier,))
    authorization = _authorization(
        acquisition,
        receipt,
        selection,
        root=tmp_path,
        allowed_identifiers=(identifier,),
        max_sources=1,
    )
    monkeypatch.setattr(
        acquisition_runtime,
        "_candidate_lstat",
        lambda path: pytest.fail(f"arbitrary path reached filesystem: {path}"),
    )

    result = acquire_selected_content(
        acquisition, receipt, selection, authorization, inventory=inventory
    )

    assert result.status == STATUS_BLOCKED
    assert INCONSISTENT_SELECTION_OUTSIDE_POOL in result.inconsistencies


def test_case_alias_of_an_eligible_identifier_is_not_accepted(tmp_path, monkeypatch):
    acquisition, receipt, inventory = _repository_case(tmp_path, {"Alpha.py": b"a"}, target="Alpha.py")
    selection = _selection(acquisition, receipt, ("alpha.py",))
    authorization = _authorization(
        acquisition,
        receipt,
        selection,
        root=tmp_path,
        allowed_identifiers=("alpha.py",),
        max_sources=1,
    )
    monkeypatch.setattr(
        acquisition_runtime,
        "_candidate_lstat",
        lambda path: pytest.fail(f"case alias reached filesystem: {path}"),
    )

    result = acquire_selected_content(
        acquisition, receipt, selection, authorization, inventory=inventory
    )

    assert INCONSISTENT_SELECTION_OUTSIDE_POOL in result.inconsistencies


def test_deleted_candidate_is_stale_and_no_substitute_is_read(tmp_path, monkeypatch):
    acquisition, receipt, inventory = _repository_case(
        tmp_path, {"a.py": b"aaa", "b.py": b"bbb"}
    )
    (tmp_path / "a.py").unlink()
    opened: list[str] = []
    original = acquisition_runtime._open_readonly
    monkeypatch.setattr(
        acquisition_runtime,
        "_open_readonly",
        lambda path: (opened.append(path.name), original(path))[1],
    )

    result, _, _ = _run(tmp_path, acquisition, receipt, inventory, ("a.py",))

    assert result.status == STATUS_STALE_CANDIDATES
    assert result.failed_receipts[0].failure_code == FAILURE_CANDIDATE_MISSING
    assert opened == []
    assert result.as_dict()["guardrails"]["substitution_performed"] is False


def test_size_change_after_acquire_2_is_stale_before_open(tmp_path, monkeypatch):
    acquisition, receipt, inventory = _repository_case(tmp_path, {"a.py": b"aaa"})
    (tmp_path / "a.py").write_bytes(b"changed")
    monkeypatch.setattr(
        acquisition_runtime,
        "_open_readonly",
        lambda path: pytest.fail(f"stale file opened: {path}"),
    )

    result, _, _ = _run(tmp_path, acquisition, receipt, inventory, ("a.py",))

    assert result.status == STATUS_STALE_CANDIDATES
    assert result.failed_receipts[0].failure_code == FAILURE_CANDIDATE_STALE


def test_non_regular_selected_member_is_rejected(tmp_path):
    (tmp_path / "a.py").mkdir()
    inventory = _inventory(_member("a.py", 0))
    acquisition, evidence = _implementation_upstream("a.py")
    receipt = _eligibility(acquisition, evidence, inventory)

    result, _, _ = _run(tmp_path, acquisition, receipt, inventory, ("a.py",))

    assert result.status == STATUS_BLOCKED
    assert result.failed_receipts[0].failure_code == FAILURE_NON_REGULAR_FILE


def test_relative_repository_root_is_rejected_before_candidate_access(
    tmp_path, monkeypatch
):
    acquisition, receipt, inventory = _repository_case(tmp_path, {"a.py": b"a"})
    selection = _selection(acquisition, receipt, ("a.py",))
    authorization = dataclasses.replace(
        _authorization(acquisition, receipt, selection, root=tmp_path),
        repository_root="relative/root",
    )
    monkeypatch.setattr(
        acquisition_runtime,
        "_candidate_lstat",
        lambda path: pytest.fail(f"relative root touched: {path}"),
    )

    result = acquire_selected_content(
        acquisition, receipt, selection, authorization, inventory=inventory
    )

    assert result.status == STATUS_BLOCKED
    assert INCONSISTENT_REPOSITORY_ROOT_INVALID in result.inconsistencies


def test_leaf_symlink_is_rejected(tmp_path):
    target = _write(tmp_path, "real.py", b"x")
    link = tmp_path / "a.py"
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable")
    inventory = _inventory(_member("a.py", 1))
    acquisition, evidence = _implementation_upstream("a.py")
    receipt = _eligibility(acquisition, evidence, inventory)

    result, _, _ = _run(tmp_path, acquisition, receipt, inventory, ("a.py",))

    assert result.status == STATUS_BLOCKED
    assert result.failed_receipts[0].failure_code == FAILURE_SYMLINK_REJECTED


def test_parent_symlink_is_rejected(tmp_path):
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir(exist_ok=True)
    (outside / "a.py").write_bytes(b"x")
    try:
        os.symlink(outside, tmp_path / "linked", target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("directory symlink creation is unavailable")
    inventory = _inventory(_member("linked/a.py", 1))
    acquisition, evidence = _implementation_upstream("linked/a.py")
    receipt = _eligibility(acquisition, evidence, inventory)

    result, _, _ = _run(
        tmp_path, acquisition, receipt, inventory, ("linked/a.py",)
    )

    assert result.failed_receipts[0].failure_code == FAILURE_SYMLINK_REJECTED


@pytest.mark.parametrize(
    ("identifier", "symlink_component"),
    (("a.py", "a.py"), ("linked/a.py", "linked")),
)
def test_symlink_policy_is_enforced_without_platform_symlink_privilege(
    tmp_path, monkeypatch, identifier, symlink_component
):
    acquisition, receipt, inventory = _repository_case(
        tmp_path, {identifier: b"x"}, target=identifier
    )
    original_lstat = acquisition_runtime._candidate_lstat
    original_open = acquisition_runtime._open_readonly
    opened: list[str] = []

    def symlink_lstat(path):
        metadata = original_lstat(path)
        if path.name == symlink_component:
            values = list(metadata)
            values[stat.ST_MODE] = stat.S_IFLNK | 0o777
            return os.stat_result(values)
        return metadata

    def spy_open(path):
        opened.append(path.name)
        return original_open(path)

    monkeypatch.setattr(acquisition_runtime, "_candidate_lstat", symlink_lstat)
    monkeypatch.setattr(acquisition_runtime, "_open_readonly", spy_open)

    result, _, _ = _run(
        tmp_path, acquisition, receipt, inventory, (identifier,)
    )

    assert result.status == STATUS_BLOCKED
    assert result.failed_receipts[0].failure_code == FAILURE_SYMLINK_REJECTED
    assert opened == []


def test_forged_eligibility_cannot_read_an_inventory_hard_exclusion(
    tmp_path, monkeypatch
):
    acquisition, receipt, _ = _repository_case(tmp_path, {"a.py": b"a"})
    excluded_inventory = _inventory(
        _member("a.py", 1, read_policy="hard_no_auto_read")
    )
    forged_envelopes = tuple(
        dataclasses.replace(
            envelope,
            inventory_fingerprint=excluded_inventory.fingerprint(),
        )
        for envelope in receipt.selector_envelopes
    )
    forged_receipt = dataclasses.replace(
        receipt,
        inventory_fingerprint=excluded_inventory.fingerprint(),
        selector_envelopes=forged_envelopes,
    )
    selection = _selection(acquisition, forged_receipt, ("a.py",))
    authorization = _authorization(
        acquisition, forged_receipt, selection, root=tmp_path
    )
    monkeypatch.setattr(
        acquisition_runtime,
        "_candidate_lstat",
        lambda path: pytest.fail(f"forged exclusion reached filesystem: {path}"),
    )

    result = acquire_selected_content(
        acquisition,
        forged_receipt,
        selection,
        authorization,
        inventory=excluded_inventory,
    )

    assert result.status == STATUS_BLOCKED
    assert INCONSISTENT_CANDIDATE_RECEIPT in result.inconsistencies


def test_authorized_root_replacement_is_detected_before_candidate_open(
    tmp_path, monkeypatch
):
    acquisition, receipt, inventory = _repository_case(tmp_path, {"a.py": b"a"})
    canonical_root = tmp_path.resolve()
    original_lstat = acquisition_runtime._candidate_lstat
    root_checks = 0
    opened: list[str] = []

    def changing_root_lstat(path):
        nonlocal root_checks
        metadata = original_lstat(path)
        if Path(path) == canonical_root:
            root_checks += 1
            if root_checks >= 3:
                values = list(metadata)
                values[stat.ST_INO] = int(metadata.st_ino) + 1
                return os.stat_result(values)
        return metadata

    monkeypatch.setattr(
        acquisition_runtime, "_candidate_lstat", changing_root_lstat
    )
    monkeypatch.setattr(
        acquisition_runtime,
        "_open_readonly",
        lambda path: opened.append(path.name),
    )

    result, _, _ = _run(tmp_path, acquisition, receipt, inventory, ("a.py",))

    assert result.status == STATUS_BLOCKED
    assert result.failed_receipts[0].failure_code == FAILURE_UNSAFE_PATH
    assert opened == []


@pytest.mark.parametrize("marker", ("attributes", "tag"))
def test_windows_reparse_metadata_is_rejected(marker):
    reparse_flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0) or 1_024)
    metadata = SimpleNamespace(
        st_mode=stat.S_IFREG | 0o644,
        st_file_attributes=reparse_flag if marker == "attributes" else 0,
        st_reparse_tag=0xA000000C if marker == "tag" else 0,
    )

    assert acquisition_runtime._is_reparse_or_symlink(metadata) is True


def test_reparse_root_is_refused_without_candidate_open(tmp_path, monkeypatch):
    acquisition, receipt, inventory = _repository_case(tmp_path, {"a.py": b"a"})
    root = tmp_path.resolve()
    original_lstat = acquisition_runtime._candidate_lstat
    reparse_flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0) or 1_024)
    opened: list[str] = []

    def root_reparse_lstat(path):
        if Path(path) == root:
            return SimpleNamespace(
                st_mode=stat.S_IFDIR | 0o755,
                st_file_attributes=reparse_flag,
                st_reparse_tag=0,
            )
        return original_lstat(path)

    monkeypatch.setattr(
        acquisition_runtime, "_candidate_lstat", root_reparse_lstat
    )
    monkeypatch.setattr(
        acquisition_runtime,
        "_open_readonly",
        lambda path: opened.append(path.name),
    )

    result, _, _ = _run(tmp_path, acquisition, receipt, inventory, ("a.py",))

    assert result.status == STATUS_BLOCKED
    assert INCONSISTENT_REPOSITORY_ROOT_INVALID in result.inconsistencies
    assert opened == []


# ── budgets, ordering and exact subset ────────────────────────────────────────


def test_per_source_authorization_limit_is_a_pre_read_budget_block(tmp_path, monkeypatch):
    acquisition, receipt, inventory = _repository_case(tmp_path, {"a.py": b"1234"})
    monkeypatch.setattr(
        acquisition_runtime,
        "_candidate_lstat",
        lambda path: pytest.fail(f"over-budget selection touched filesystem: {path}"),
    )

    result, _, _ = _run(
        tmp_path,
        acquisition,
        receipt,
        inventory,
        ("a.py",),
        max_per_source_bytes=3,
        max_total_bytes=4,
    )

    assert result.status == STATUS_BUDGET_BLOCKED
    assert INCONSISTENT_SELECTION_BUDGET in result.inconsistencies


def test_total_byte_limit_rejects_whole_selection_without_choosing(tmp_path, monkeypatch):
    acquisition, receipt, inventory = _repository_case(
        tmp_path, {"a.py": b"123", "b.py": b"456"}
    )
    monkeypatch.setattr(
        acquisition_runtime,
        "_candidate_lstat",
        lambda path: pytest.fail(f"over-budget subset touched filesystem: {path}"),
    )

    result, _, _ = _run(
        tmp_path,
        acquisition,
        receipt,
        inventory,
        ("a.py", "b.py"),
        max_total_bytes=5,
        max_per_source_bytes=3,
    )

    assert result.status == STATUS_BUDGET_BLOCKED
    assert result.acquired_receipts == ()
    assert INCONSISTENT_SELECTION_BUDGET in result.inconsistencies


def test_source_count_limit_rejects_whole_selection(tmp_path, monkeypatch):
    acquisition, receipt, inventory = _repository_case(
        tmp_path, {"a.py": b"1", "b.py": b"2"}
    )
    selection = _selection(acquisition, receipt, ("a.py", "b.py"))
    authorization = _authorization(
        acquisition,
        receipt,
        selection,
        root=tmp_path,
        max_sources=1,
    )
    monkeypatch.setattr(
        acquisition_runtime,
        "_candidate_lstat",
        lambda path: pytest.fail(f"over-count selection touched filesystem: {path}"),
    )

    result = acquire_selected_content(
        acquisition, receipt, selection, authorization, inventory=inventory
    )

    assert result.status == STATUS_BUDGET_BLOCKED
    assert INCONSISTENT_SELECTION_BUDGET in result.inconsistencies


def test_exact_source_and_byte_boundaries_are_allowed(tmp_path):
    acquisition, receipt, inventory = _repository_case(
        tmp_path, {"a.py": b"123", "b.py": b"456"}
    )

    result, _, _ = _run(
        tmp_path,
        acquisition,
        receipt,
        inventory,
        ("a.py", "b.py"),
        max_sources=2,
        max_total_bytes=6,
        max_per_source_bytes=3,
    )

    assert result.status == STATUS_ACQUIRED
    assert result.budget.sources_acquired == 2
    assert result.budget.sources_remaining == 0
    assert result.budget.bytes_acquired == 6
    assert result.budget.bytes_remaining == 0


def test_selection_contract_requires_canonical_order():
    with pytest.raises(ValueError, match="canonically ordered"):
        AcquisitionSelection(
            candidate_identifiers=("b.py", "a.py"),
            candidate_receipt_fingerprint="0" * 64,
            acquisition_request_fingerprint="1" * 64,
        )


def test_a_b_c_d_e_selection_touches_only_b_and_d(tmp_path, monkeypatch):
    files = {name: name.encode("ascii") for name in ("a.py", "b.py", "c.py", "d.py", "e.py")}
    acquisition, receipt, inventory = _repository_case(tmp_path, files, target="b.py")
    touched: list[str] = []
    opened: list[str] = []
    original = acquisition_runtime._candidate_lstat
    original_open = acquisition_runtime._open_readonly

    def spy(path):
        if path.name in set(files):
            touched.append(path.name)
        return original(path)

    monkeypatch.setattr(acquisition_runtime, "_candidate_lstat", spy)
    monkeypatch.setattr(
        acquisition_runtime,
        "_open_readonly",
        lambda path: (opened.append(path.name), original_open(path))[1],
    )
    result, _, _ = _run(
        tmp_path, acquisition, receipt, inventory, ("b.py", "d.py")
    )

    assert result.status == STATUS_ACQUIRED
    assert {item.candidate_identifier for item in result.acquired_receipts} == {
        "b.py",
        "d.py",
    }
    assert set(touched) == {"b.py", "d.py"}
    assert set(opened) == {"b.py", "d.py"}
    assert not {"a.py", "c.py", "e.py"} & set(touched)
    assert not {"a.py", "c.py", "e.py"} & set(opened)


def test_ctx_select_claim_is_validated_but_not_executed(tmp_path):
    acquisition, receipt, inventory = _repository_case(tmp_path, {"a.py": b"a"})
    selection = _selection(
        acquisition,
        receipt,
        ("a.py",),
        source=SELECTION_SOURCE_CTX_SELECT,
    )
    authorization = _authorization(acquisition, receipt, selection, root=tmp_path)

    result = acquire_selected_content(
        acquisition, receipt, selection, authorization, inventory=inventory
    )

    assert result.status == STATUS_ACQUIRED
    assert result.as_dict()["guardrails"]["ctx_select_executed"] is False


# ── tiers, target artifact, direct context and external ───────────────────────


def test_primary_candidate_may_be_acquired(tmp_path):
    acquisition, receipt, inventory = _repository_case(tmp_path, {"a.py": b"a"})
    result, _, _ = _run(tmp_path, acquisition, receipt, inventory, ("a.py",))

    assert result.acquired_receipts[0].tier == TIER_REQUIRED_PRIMARY


def test_validation_candidate_may_be_acquired_without_running_it(tmp_path):
    content = b"def test_failure(): assert False\n"
    _write(tmp_path, "tests/test_indexer.py", content)
    inventory = _inventory(_member("tests/test_indexer.py", len(content)))
    acquisition, evidence = _test_debugging_upstream()
    receipt = _eligibility(acquisition, evidence, inventory)

    result, _, _ = _run(
        tmp_path,
        acquisition,
        receipt,
        inventory,
        ("tests/test_indexer.py",),
    )

    source = result.acquired_receipts[0]
    assert source.tier == TIER_REQUIRED_PRIMARY
    assert source.expected_roles == (ROLE_VALIDATION_EVIDENCE,)
    assert source.verification_status == VERIFICATION_UNVERIFIED
    assert result.as_dict()["guardrails"]["validation_executed"] is False


def test_secondary_validation_candidate_may_be_acquired(tmp_path):
    source = b"def f(): return 1\n"
    test = b"def test_f(): assert True\n"
    _write(tmp_path, "core/a.py", source)
    _write(tmp_path, "tests/test_a.py", test)
    inventory = _inventory(
        _member("core/a.py", len(source)),
        _member("tests/test_a.py", len(test)),
    )
    acquisition, evidence = _implementation_upstream("core/a.py", broad=True)
    receipt = _eligibility(acquisition, evidence, inventory)
    candidate = receipt.candidate("tests/test_a.py")
    assert candidate is not None and candidate.tier == TIER_REQUIRED_SECONDARY

    result, _, _ = _run(
        tmp_path, acquisition, receipt, inventory, ("tests/test_a.py",)
    )

    assert result.status == STATUS_ACQUIRED
    assert result.acquired_receipts[0].tier == TIER_REQUIRED_SECONDARY


def test_deferred_candidate_selection_is_structurally_rejected(tmp_path, monkeypatch):
    current = b"x"
    history = b"old"
    _write(tmp_path, "core/a.py", current)
    _write(tmp_path, "docs/proposals/old.md", history)
    inventory = _inventory(
        _member("core/a.py", len(current)),
        _member(
            "docs/proposals/old.md",
            len(history),
            parser_support="not_applicable",
        ),
    )
    acquisition, evidence = _implementation_upstream("core/a.py", broad=True)
    receipt = _eligibility(acquisition, evidence, inventory)
    deferred = receipt.candidate("docs/proposals/old.md")
    assert deferred is not None and deferred.tier == TIER_DEFERRED
    selection = _selection(
        acquisition, receipt, ("docs/proposals/old.md",)
    )
    authorization = _authorization(
        acquisition,
        receipt,
        selection,
        root=tmp_path,
        allowed_identifiers=("docs/proposals/old.md",),
        allowed_domains=(deferred.domain,),
        max_sources=1,
        max_total_bytes=len(history),
        max_per_source_bytes=len(history),
    )
    monkeypatch.setattr(
        acquisition_runtime,
        "_candidate_lstat",
        lambda path: pytest.fail(f"deferred path touched: {path}"),
    )

    result = acquire_selected_content(
        acquisition, receipt, selection, authorization, inventory=inventory
    )

    assert result.status == STATUS_BLOCKED
    assert INCONSISTENT_SELECTION_DEFERRED in result.inconsistencies


def test_excluded_candidate_selection_is_rejected(tmp_path, monkeypatch):
    _write(tmp_path, "a.py", b"a")
    _write(tmp_path, "build/bundle.js", b"bundle")
    inventory = _inventory(
        _member("a.py", 1),
        _member("build/bundle.js", 6, generated=True),
    )
    acquisition, evidence = _implementation_upstream("a.py")
    receipt = _eligibility(acquisition, evidence, inventory)
    assert receipt.candidate("build/bundle.js") is None
    selection = _selection(acquisition, receipt, ("build/bundle.js",))
    authorization = _authorization(
        acquisition,
        receipt,
        selection,
        root=tmp_path,
        allowed_identifiers=("build/bundle.js",),
        allowed_domains=(DOMAIN_REPOSITORY,),
        max_sources=1,
        max_total_bytes=6,
        max_per_source_bytes=6,
    )
    monkeypatch.setattr(
        acquisition_runtime,
        "_candidate_lstat",
        lambda path: pytest.fail(f"excluded path touched: {path}"),
    )

    result = acquire_selected_content(
        acquisition, receipt, selection, authorization, inventory=inventory
    )

    assert INCONSISTENT_SELECTION_OUTSIDE_POOL in result.inconsistencies


def test_explicit_readme_target_is_acquired_without_authority_role(tmp_path):
    content = b"Fix teh typo.\n"
    _write(tmp_path, "README.md", content)
    inventory = _inventory(
        _member("README.md", len(content), parser_support="not_applicable")
    )
    acquisition, evidence = _implementation_upstream("README.md")
    receipt = _eligibility(acquisition, evidence, inventory)
    candidate = receipt.candidate("README.md")
    assert candidate is not None and candidate.eligible_roles == ()

    result, _, _ = _run(
        tmp_path, acquisition, receipt, inventory, ("README.md",)
    )

    source = result.acquired_receipts[0]
    assert source.target_artifact is True
    assert source.expected_roles == ()
    assert source.eligible_source_classes == ()
    assert source.verification_status == VERIFICATION_UNVERIFIED
    assert result.as_dict()["authority"]["patch_authority"] is False


def test_direct_context_produces_reference_without_filesystem_activity(monkeypatch):
    acquisition, evidence = _direct_context_upstream()
    receipt = _eligibility(acquisition, evidence)
    identifier = receipt.active_candidates[0].identifier
    selection = _selection(acquisition, receipt, (identifier,))
    authorization = _authorization(acquisition, receipt, selection)
    monkeypatch.setattr(
        acquisition_runtime,
        "_candidate_lstat",
        lambda path: pytest.fail(f"direct context touched filesystem: {path}"),
    )

    result = acquire_selected_content(
        acquisition, receipt, selection, authorization
    )

    direct = result.direct_context_receipts[0]
    assert result.status == STATUS_ACQUIRED
    assert direct.acquisition_mode == MODE_EXISTING_CONTEXT
    assert direct.acquisition_status == "already_available_reference"
    assert result.payloads == ()
    assert result.budget.sources_acquired == 1
    assert result.budget.bytes_acquired == 0
    assert result.as_dict()["guardrails"]["repository_files_read"] is False


def test_external_only_requires_candidate_discovery_and_never_network():
    acquisition, evidence = _external_upstream()
    receipt = _eligibility(acquisition, evidence)
    selection = _selection(acquisition, receipt, ())
    authorization = _authorization(
        acquisition,
        receipt,
        selection,
        allowed_domains=(DOMAIN_EXTERNAL_INFORMATION,),
        max_sources=0,
        max_total_bytes=0,
        max_per_source_bytes=0,
    )

    result = acquire_selected_content(
        acquisition, receipt, selection, authorization
    )

    assert result.status == STATUS_EXTERNAL_DISCOVERY_REQUIRED
    assert len(result.unresolved_external_requests) == 1
    payload = result.as_dict()
    assert payload["guardrails"]["network_called"] is False
    assert payload["guardrails"]["web_search_performed"] is False
    assert payload["unresolved_external_requests"][0]["query_generated"] is False


def test_direct_context_plus_external_is_partial_even_when_external_is_not_granted():
    acquisition, evidence = _direct_plus_external_upstream()
    receipt = _eligibility(acquisition, evidence)
    direct_ids = tuple(
        candidate.identifier
        for candidate in receipt.active_candidates + receipt.secondary_candidates
        if candidate.domain == DOMAIN_DIRECT_CONTEXT
    )
    selection = _selection(acquisition, receipt, direct_ids)
    authorization = _authorization(acquisition, receipt, selection)

    result = acquire_selected_content(
        acquisition, receipt, selection, authorization
    )

    assert result.status == STATUS_PARTIAL
    assert len(result.direct_context_receipts) == 1
    assert len(result.unresolved_external_requests) == 1
    assert result.acquired_receipts == ()
    assert result.budget.sources_selected == 1
    assert result.budget.sources_acquired == 1
    assert result.budget.bytes_acquired == 0


def _repository_external_case(tmp_path):
    content = b"abc"
    _write(tmp_path, "core/executor.py", content)
    inventory = _inventory(_member("core/executor.py", len(content)))
    acquisition, evidence = _repository_plus_external_upstream()
    receipt = _eligibility(acquisition, evidence, inventory)
    return acquisition, receipt, inventory


def test_repository_plus_external_is_partial(tmp_path):
    acquisition, receipt, inventory = _repository_external_case(tmp_path)
    result, _, _ = _run(
        tmp_path,
        acquisition,
        receipt,
        inventory,
        ("core/executor.py",),
    )

    assert result.status == STATUS_PARTIAL
    assert result.payloads[0].content == b"abc"
    assert len(result.unresolved_external_requests) == 1
    assert result.budget.sources_acquired == 1
    assert result.budget.bytes_acquired == 3


def test_stale_repository_plus_external_is_blocked_as_mixed_unresolved(tmp_path):
    acquisition, receipt, inventory = _repository_external_case(tmp_path)
    selection = _selection(acquisition, receipt, ("core/executor.py",))
    authorization = _authorization(
        acquisition, receipt, selection, root=tmp_path
    )
    (tmp_path / "core/executor.py").unlink()

    result = acquire_selected_content(
        acquisition, receipt, selection, authorization, inventory=inventory
    )

    assert result.status == STATUS_BLOCKED
    assert result.acquired_receipts == ()
    assert result.failed_receipts[0].failure_code == FAILURE_CANDIDATE_MISSING
    assert len(result.unresolved_external_requests) == 1
    assert result.budget.bytes_read == 0


def test_direct_repository_and_external_have_exact_mixed_budget_accounting(tmp_path):
    acquisition, receipt, inventory = _repository_external_case(tmp_path)
    selected_ids = tuple(
        candidate.identifier
        for candidate in receipt.active_candidates + receipt.secondary_candidates
        if candidate.domain in {DOMAIN_DIRECT_CONTEXT, DOMAIN_REPOSITORY}
    )
    selection = _selection(acquisition, receipt, selected_ids)
    authorization = _authorization(
        acquisition, receipt, selection, root=tmp_path
    )

    result = acquire_selected_content(
        acquisition, receipt, selection, authorization, inventory=inventory
    )

    assert result.status == STATUS_PARTIAL
    assert len(result.acquired_receipts) == 1
    assert len(result.direct_context_receipts) == 1
    assert len(result.unresolved_external_requests) == 1
    assert result.budget.sources_selected == 2
    assert result.budget.sources_acquired == 2
    assert result.budget.bytes_selected_reserved == 3
    assert result.budget.bytes_acquired == 3
    assert result.budget.bytes_read == 3


# ── partial results, payload safety, hashes and tamper binding ─────────────────


def test_partial_acquisition_keeps_success_and_does_not_replace_stale_source(tmp_path):
    acquisition, receipt, inventory = _repository_case(
        tmp_path, {"a.py": b"aaa", "b.py": b"bbb", "c.py": b"ccc"}
    )
    (tmp_path / "b.py").write_bytes(b"changed")

    result, _, _ = _run(
        tmp_path, acquisition, receipt, inventory, ("a.py", "b.py")
    )

    assert result.status == STATUS_PARTIAL
    assert [item.candidate_identifier for item in result.acquired_receipts] == ["a.py"]
    assert [item.candidate_identifier for item in result.failed_receipts] == ["b.py"]
    assert result.failed_receipts[0].failure_code == FAILURE_CANDIDATE_STALE
    assert all(item.candidate_identifier != "c.py" for item in result.acquired_receipts)
    assert result.budget.sources_selected == 2
    assert result.budget.sources_acquired == 1


def test_receipt_serialization_never_contains_source_payload(tmp_path):
    secret = b"UNIQUE_TEST_SECRET_TOKEN_91af"
    acquisition, receipt, inventory = _repository_case(tmp_path, {"a.py": secret})
    result, _, _ = _run(tmp_path, acquisition, receipt, inventory, ("a.py",))

    rendered = render_content_acquisition_result_json(result)

    assert secret.decode("ascii") not in rendered
    assert result.payloads[0].content == secret
    assert result.as_dict()["payloads_serialized"] is False


def test_receipt_contains_no_epistemic_promotion_claim(tmp_path):
    acquisition, receipt, inventory = _repository_case(tmp_path, {"a.py": b"a"})
    result, _, _ = _run(tmp_path, acquisition, receipt, inventory, ("a.py",))
    rendered = render_content_acquisition_result_json(result).casefold()

    for forbidden in (
        "verified_evidence",
        "source proves",
        "source confirms",
        "grounded claim",
        "claim supported",
        "confidence 0.9",
    ):
        assert forbidden not in rendered
    assert '"verification_status": "unverified"' in rendered
    assert '"authority_status": "not_verified"' in rendered


def test_receipt_contract_rejects_non_file_domains_and_deferred_tiers(tmp_path):
    acquisition, receipt, inventory = _repository_case(tmp_path, {"a.py": b"a"})
    result, _, _ = _run(tmp_path, acquisition, receipt, inventory, ("a.py",))
    source = result.acquired_receipts[0]

    with pytest.raises(ValueError, match="repository-backed domain"):
        dataclasses.replace(source, domain=DOMAIN_EXTERNAL_INFORMATION)
    with pytest.raises(ValueError, match="active tier"):
        dataclasses.replace(source, tier=TIER_DEFERRED)

    direct_acquisition, direct_evidence = _direct_context_upstream()
    direct_receipt = _eligibility(direct_acquisition, direct_evidence)
    identifier = direct_receipt.active_candidates[0].identifier
    direct_selection = _selection(
        direct_acquisition, direct_receipt, (identifier,)
    )
    direct_authorization = _authorization(
        direct_acquisition, direct_receipt, direct_selection
    )
    direct_result = acquire_selected_content(
        direct_acquisition,
        direct_receipt,
        direct_selection,
        direct_authorization,
    )
    with pytest.raises(ValueError, match="active tier"):
        dataclasses.replace(
            direct_result.direct_context_receipts[0], tier=TIER_DEFERRED
        )


def test_result_collections_are_deeply_type_checked_and_immutable(tmp_path):
    acquisition, receipt, inventory = _repository_case(tmp_path, {"a.py": b"a"})
    result, _, _ = _run(tmp_path, acquisition, receipt, inventory, ("a.py",))

    with pytest.raises(TypeError, match="immutable tuple"):
        dataclasses.replace(result, acquired_receipts=list(result.acquired_receipts))
    with pytest.raises(TypeError, match="unsupported item type"):
        dataclasses.replace(result, acquired_receipts=("not-a-receipt",))
    with pytest.raises(TypeError, match="AcquisitionBudgetSummary"):
        dataclasses.replace(result, budget={})


def test_result_rejects_authority_binding_and_per_source_budget_contradictions(
    tmp_path
):
    acquisition, receipt, inventory = _repository_case(tmp_path, {"a.py": b"a"})
    result, _, _ = _run(tmp_path, acquisition, receipt, inventory, ("a.py",))

    with pytest.raises(ValueError, match="requires its fingerprint"):
        dataclasses.replace(result, authorization_fingerprint=None)
    with pytest.raises(ValueError, match="per-source"):
        dataclasses.replace(
            result,
            budget=dataclasses.replace(result.budget, max_per_source_bytes=0),
        )

    wrong_binding = dataclasses.replace(
        result.acquired_receipts[0].source_binding,
        candidate_receipt_fingerprint="f" * 64,
    )
    wrong_receipt = dataclasses.replace(
        result.acquired_receipts[0], source_binding=wrong_binding
    )
    wrong_payload = dataclasses.replace(
        result.payloads[0], source_binding=wrong_binding
    )
    with pytest.raises(ValueError, match="provenance"):
        dataclasses.replace(
            result,
            acquired_receipts=(wrong_receipt,),
            payloads=(wrong_payload,),
        )


def test_external_result_cannot_claim_repository_scope():
    acquisition, evidence = _external_upstream()
    receipt = _eligibility(acquisition, evidence)
    selection = _selection(acquisition, receipt, ())
    authorization = _authorization(
        acquisition,
        receipt,
        selection,
        allowed_domains=(DOMAIN_EXTERNAL_INFORMATION,),
        max_sources=0,
        max_total_bytes=0,
        max_per_source_bytes=0,
    )
    result = acquire_selected_content(
        acquisition, receipt, selection, authorization
    )

    with pytest.raises(ValueError, match="exactly match repository"):
        dataclasses.replace(result, repository_scope_authorized=True)


def test_same_bytes_have_same_hash_and_one_byte_change_differs(tmp_path):
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    third_root = tmp_path / "third"
    hashes = []
    for root, content in (
        (first_root, b"same"),
        (second_root, b"same"),
        (third_root, b"same!"),
    ):
        root.mkdir()
        acquisition, receipt, inventory = _repository_case(root, {"a.py": content})
        result, _, _ = _run(root, acquisition, receipt, inventory, ("a.py",))
        hashes.append(result.acquired_receipts[0].content_sha256)

    assert hashes[0] == hashes[1]
    assert hashes[0] != hashes[2]


def test_selection_fingerprint_tamper_blocks_before_read(tmp_path, monkeypatch):
    acquisition, receipt, inventory = _repository_case(tmp_path, {"a.py": b"a"})
    selection = dataclasses.replace(
        _selection(acquisition, receipt, ("a.py",)),
        candidate_receipt_fingerprint="0" * 64,
    )
    authorization = _authorization(acquisition, receipt, selection, root=tmp_path)
    monkeypatch.setattr(
        acquisition_runtime,
        "_candidate_lstat",
        lambda path: pytest.fail(f"tampered selection touched filesystem: {path}"),
    )

    result = acquire_selected_content(
        acquisition, receipt, selection, authorization, inventory=inventory
    )

    assert result.status == STATUS_BLOCKED


def test_inventory_fingerprint_tamper_blocks_before_read(tmp_path, monkeypatch):
    acquisition, receipt, inventory = _repository_case(tmp_path, {"a.py": b"a"})
    selection = _selection(acquisition, receipt, ("a.py",))
    authorization = _authorization(acquisition, receipt, selection, root=tmp_path)
    changed_inventory = _inventory(_member("a.py", 1), _member("extra.py", 1))
    monkeypatch.setattr(
        acquisition_runtime,
        "_candidate_lstat",
        lambda path: pytest.fail(f"wrong inventory touched filesystem: {path}"),
    )

    result = acquire_selected_content(
        acquisition,
        receipt,
        selection,
        authorization,
        inventory=changed_inventory,
    )

    assert result.status == STATUS_BLOCKED
    assert INCONSISTENT_INVENTORY in result.inconsistencies


def test_candidate_receipt_schema_tamper_blocks_before_read(tmp_path, monkeypatch):
    acquisition, receipt, inventory = _repository_case(tmp_path, {"a.py": b"a"})
    tampered = dataclasses.replace(receipt, schema_version="tampered")
    selection = _selection(acquisition, tampered, ("a.py",))
    authorization = _authorization(acquisition, tampered, selection, root=tmp_path)
    monkeypatch.setattr(
        acquisition_runtime,
        "_candidate_lstat",
        lambda path: pytest.fail(f"wrong receipt schema touched filesystem: {path}"),
    )

    result = acquire_selected_content(
        acquisition, tampered, selection, authorization, inventory=inventory
    )

    assert result.status == STATUS_BLOCKED
    assert tampered.schema_version != CANDIDATE_RECEIPT_SCHEMA_VERSION


def test_forged_direct_context_identity_is_rederived_and_blocked(monkeypatch):
    acquisition, evidence = _direct_context_upstream()
    receipt = _eligibility(acquisition, evidence)
    forged_candidate = dataclasses.replace(
        receipt.active_candidates[0],
        identifier=f"supplied_context:{'0' * 64}",
    )
    forged_receipt = dataclasses.replace(
        receipt, active_candidates=(forged_candidate,)
    )
    selection = _selection(
        acquisition, forged_receipt, (forged_candidate.identifier,)
    )
    authorization = _authorization(
        acquisition, forged_receipt, selection
    )
    monkeypatch.setattr(
        acquisition_runtime,
        "_candidate_lstat",
        lambda path: pytest.fail(f"forged direct context touched filesystem: {path}"),
    )

    result = acquire_selected_content(
        acquisition, forged_receipt, selection, authorization
    )

    assert result.status == STATUS_BLOCKED
    assert INCONSISTENT_CANDIDATE_RECEIPT in result.inconsistencies


def test_forged_external_envelope_is_rederived_and_blocked(monkeypatch):
    acquisition, evidence = _external_upstream()
    receipt = _eligibility(acquisition, evidence)
    forged_envelope = dataclasses.replace(
        receipt.external_envelopes[0], freshness="not_applicable"
    )
    forged_receipt = dataclasses.replace(
        receipt, external_envelopes=(forged_envelope,)
    )
    selection = _selection(acquisition, forged_receipt, ())
    authorization = _authorization(
        acquisition,
        forged_receipt,
        selection,
        allowed_domains=(DOMAIN_EXTERNAL_INFORMATION,),
        max_sources=0,
        max_total_bytes=0,
        max_per_source_bytes=0,
    )
    monkeypatch.setattr(
        acquisition_runtime,
        "_candidate_lstat",
        lambda path: pytest.fail(f"forged external envelope touched filesystem: {path}"),
    )

    result = acquire_selected_content(
        acquisition, forged_receipt, selection, authorization
    )

    assert result.status == STATUS_BLOCKED
    assert INCONSISTENT_CANDIDATE_RECEIPT in result.inconsistencies


def test_multichunk_read_never_requests_more_than_fixed_or_remaining_bound(
    tmp_path, monkeypatch
):
    content = b"x" * 100_000
    acquisition, receipt, inventory = _repository_case(
        tmp_path, {"a.py": content}
    )
    requested: list[int] = []
    original_read = acquisition_runtime._descriptor_read

    def bounded_read(descriptor, count):
        requested.append(count)
        return original_read(descriptor, count)

    monkeypatch.setattr(acquisition_runtime, "_descriptor_read", bounded_read)

    result, _, _ = _run(tmp_path, acquisition, receipt, inventory, ("a.py",))

    assert result.status == STATUS_ACQUIRED
    assert requested == [65_536, 34_464]
    assert result.budget.bytes_read == len(content)


def test_short_read_accepts_no_payload_or_hash(tmp_path, monkeypatch):
    acquisition, receipt, inventory = _repository_case(
        tmp_path, {"a.py": b"abcde"}
    )
    original_read = acquisition_runtime._descriptor_read
    calls = 0

    def short_read(descriptor, count):
        nonlocal calls
        calls += 1
        if calls == 1:
            return original_read(descriptor, min(count, 2))
        return b""

    monkeypatch.setattr(acquisition_runtime, "_descriptor_read", short_read)

    result, _, _ = _run(tmp_path, acquisition, receipt, inventory, ("a.py",))

    assert result.status == STATUS_BLOCKED
    assert result.failed_receipts[0].failure_code == FAILURE_READ_ERROR
    assert result.payloads == ()
    assert result.acquired_receipts == ()
    assert result.budget.bytes_read == 2
    assert result.budget.bytes_acquired == 0


def test_same_size_replacement_before_open_is_rejected_as_toctou(tmp_path, monkeypatch):
    acquisition, receipt, inventory = _repository_case(tmp_path, {"a.py": b"old"})
    original_open = acquisition_runtime._open_readonly
    replacement = tmp_path / "replacement.tmp"

    def replace_then_open(path):
        replacement.write_bytes(b"new")
        os.replace(replacement, path)
        return original_open(path)

    monkeypatch.setattr(acquisition_runtime, "_open_readonly", replace_then_open)

    result, _, _ = _run(tmp_path, acquisition, receipt, inventory, ("a.py",))

    assert result.status == STATUS_STALE_CANDIDATES
    assert result.failed_receipts[0].failure_code == FAILURE_STALE_DURING_ACQUISITION
    assert result.payloads == ()


# ── anti-6087 bounded acquisition ─────────────────────────────────────────────


def test_deepseek_6200_inventory_reads_only_explicit_two_source_subset(
    tmp_path, monkeypatch
):
    members = tuple(
        _member(f"src/f{index:04d}.py", 2)
        for index in range(6_200)
    )
    inventory = _inventory(*members)
    _write(tmp_path, "src/f0000.py", b"00")
    _write(tmp_path, "src/f0001.py", b"01")
    acquisition, evidence = _implementation_upstream("src/f0000.py")
    receipt = _eligibility(acquisition, evidence, inventory)
    assert len(receipt.active_candidates) <= receipt.candidate_limit
    assert receipt.candidate("src/f0000.py") is not None
    assert receipt.candidate("src/f0001.py") is not None
    touched: list[str] = []
    opened: list[str] = []
    original = acquisition_runtime._candidate_lstat
    original_open = acquisition_runtime._open_readonly

    def spy(path):
        if path.name.startswith("f"):
            touched.append(path.name)
        return original(path)

    monkeypatch.setattr(acquisition_runtime, "_candidate_lstat", spy)
    monkeypatch.setattr(
        acquisition_runtime,
        "_open_readonly",
        lambda path: (opened.append(path.name), original_open(path))[1],
    )

    result, _, _ = _run(
        tmp_path,
        acquisition,
        receipt,
        inventory,
        ("src/f0000.py", "src/f0001.py"),
    )

    assert result.status == STATUS_ACQUIRED
    assert result.budget.sources_acquired == 2
    assert result.budget.sources_acquired <= receipt.source_limit_reserved
    assert result.budget.bytes_acquired == 4
    assert result.budget.bytes_read == 4
    assert result.budget.bytes_acquired <= receipt.byte_limit
    assert set(touched) == {"f0000.py", "f0001.py"}
    assert set(opened) == {"f0000.py", "f0001.py"}
    assert result.as_dict()["guardrails"]["repository_traversal_performed"] is False
    assert result.as_dict()["guardrails"]["substitution_performed"] is False
