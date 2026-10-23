"""Pure original-owner fixtures for the PINNED.1B evidence edge.

Measurements below are controlled test data, not live Docker/image proof. Both
upstreams are nevertheless issued by their original owners and authenticated
through their unchanged public validators. No workload or transport can run.
"""
from copy import copy, deepcopy
from dataclasses import FrozenInstanceError, fields, replace
import inspect
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from tests._preflight_runtime1_guard import no_runtime_effects

with no_runtime_effects(strict=False):
    from core import runtime_java_pinned_backend_target_binding as owner
    from core import runtime_java_pinned_target_inspection as target_owner
    from core import sandbox_backend_binding as bind_owner
    from core import sandboxed_java_toolchain_discovery as discovery_owner
    from tests import test_runtime_sandbox_bind1 as bind_controls
    from tests import test_runtime_java_pinned_target_inspection as target_controls


_ORIGINAL_BIND_ISSUER = bind_owner.issue_sandbox_backend_binding
_ORIGINAL_TARGET_ISSUER = target_owner.inspect_target
_ROUTE = "local-docker:npipe:////./pipe/dockerDesktopLinuxEngine"
_VERSION = " Exact.01 "
_FALSE_CLAIMS = (
    "daemon_identity_claimed", "daemon_continuity_claimed", "aba_resistance_claimed",
    "exact_provider_proven", "runtime_controller_identity_proven", "java1c_linkage_proven",
    "java1c_invoked", "runtime_proof_issued", "complete_inventory_claimed",
    "global_provider_absence_claimed", "global_provider_uniqueness_claimed",
    "runtime_authority", "repository_write_authority", "apply_authority",
    "compatibility_authority",
)


@pytest.fixture(autouse=True)
def guarded():
    with no_runtime_effects(strict=True) as effects, \
            patch("threading.Thread.start", side_effect=effects.deny("thread_start")), \
            patch.dict(bind_owner._LIVE, {}, clear=True), \
            patch.dict(target_owner._LIVE, {}, clear=True), \
            patch.dict(owner._LIVE, {}, clear=True), \
            patch.dict(owner._ATTEMPTS, {}, clear=True), \
            patch.dict(owner._UPSTREAM_ORIGINS, {}, clear=True):
        yield
    assert effects.denied_attempts == {}


@pytest.fixture
def control(monkeypatch):
    """Every upstream call creates new originals through its public issuer."""
    state = SimpleNamespace(events=[], bind_issues=[], target_issues=[],
        bind_route=_ROUTE, bind_version=_VERSION, target_version=_VERSION,
        configure_bind=None, configure_target=None, after_bind=None,
        after_target=None, target_commands=[])

    def issue_bind():
        state.events.append("bind_issue")
        generator = bind_controls.control.__wrapped__()
        controlled = next(generator)
        try:
            if state.configure_bind:
                state.configure_bind(controlled)
            with patch.object(bind_owner, "_backend_witness",
                    return_value=(state.bind_route, state.bind_version)):
                result = _ORIGINAL_BIND_ISSUER()
        finally:
            generator.close()
        state.bind_issues.append(result)
        state.events.append("bind_done")
        return state.after_bind(result) if state.after_bind else result

    def inspect_target():
        state.events.append("inspection_issue")
        endpoint = "npipe:////./pipe/dockerDesktopLinuxEngine"
        controlled = SimpleNamespace(
            prefix=("fixed-docker.exe", "--config", "absent", "--host", endpoint),
            metadata=target_controls._metadata(),
            configuration=target_controls._configuration("d" * 64),
            archive=target_controls._archive_result(), workspace_removed=True,
            captures={}, name=None, cleanup={key: True for key in (
                "export_child_reaped", "export_pipes_closed",
                "deadline_supervisor_stopped", "stderr_reader_stopped")})
        if state.configure_target:
            state.configure_target(controlled)

        def measured(argv, **kwargs):
            assert argv[:len(controlled.prefix)] == controlled.prefix
            command = argv[len(controlled.prefix):]
            state.target_commands.append(command)
            role = command[0]
            if command[:2] == ("image", "inspect"):
                assert command == ("image", "inspect", target_owner.IMAGE, "--format", "{{json .}}")
                role = "image"
                capture = target_controls._capture(json.dumps(controlled.metadata).encode())
            elif role == "version":
                capture = target_controls._capture(json.dumps({"Server": {
                    "Os": "linux", "Version": state.target_version}}).encode())
            elif role == "create":
                controlled.name = command[command.index("--name") + 1]
                capture = target_controls._capture(b"d" * 64)
            elif role == "inspect" and command[-1] == "{{json .}}":
                assert command[1] == controlled.name
                role = "configuration"
                capture = target_controls._capture(json.dumps(controlled.configuration).encode())
            elif role == "inspect":
                assert command == ("inspect", controlled.name, "--format", "{{.State.Running}}")
                role = "absence"
                capture = target_controls._capture(exit_code=1, stderr=b"No such object: fixture")
            elif role == "rm":
                assert command == ("rm", "--force", "--volumes", controlled.name)
                capture = target_controls._capture()
            else:
                pytest.fail("Unexpected target control: " + repr(command))
            return controlled.captures.get(role, capture)

        def exported(prefix, name):
            assert prefix == controlled.prefix and name == controlled.name
            return target_owner.ExportResult(controlled.archive, target_owner.COMPLETE,
                "fixture_archive", 5.0, controlled.archive.archive_bytes,
                tuple(controlled.cleanup.items()))

        with patch.object(target_owner, "_fixed_route", return_value=(controlled.prefix, endpoint)), \
                patch.object(target_owner.sandbox, "_bounded_process", measured), \
                patch.object(target_owner, "_make_workspace", return_value=SimpleNamespace(name="C:/fixture/pinned1b")), \
                patch.object(target_owner, "_write_profile", side_effect=lambda directory: Path(directory) / "seccomp.json"), \
                patch.object(target_owner, "_remove_workspace", return_value=controlled.workspace_removed), \
                patch.object(target_owner, "_export_target", exported):
            result = _ORIGINAL_TARGET_ISSUER()
        state.target_issues.append(result)
        state.events.append("inspection_done")
        return state.after_target(result) if state.after_target else result

    state.issue_bind, state.inspect_target = issue_bind, inspect_target
    monkeypatch.setattr(bind_owner, "issue_sandbox_backend_binding", issue_bind)
    monkeypatch.setattr(target_owner, "inspect_target", inspect_target)
    return state


@pytest.fixture
def issued(control):
    outcome = owner.issue_pinned_backend_target_binding()
    assert outcome.status == owner.COMPLETE, outcome.reason
    assert outcome.receipt is not None
    return outcome


def _upstreams(outcome):
    return (outcome.bind_attachment, outcome.sandbox_descriptor,
        outcome.sandbox_receipt, outcome.inspection_receipt)


def _validate(outcome, receipt=None, upstreams=None):
    return owner.validate_pinned_backend_target_binding(
        outcome.receipt if receipt is None else receipt,
        *(_upstreams(outcome) if upstreams is None else upstreams))


def _assert_rejected(outcome, *, receipt=None, upstreams=None, status=None):
    with pytest.raises(owner.PinnedBindingBlocked) as error:
        _validate(outcome, receipt=receipt, upstreams=upstreams)
    assert error.value.status == (owner.MISMATCH if status is None else status)


def _mutate(value, key, changed):
    """Return original value so authentication-tamper tests can restore it."""
    original = getattr(value, key)
    object.__setattr__(value, key, changed)
    return original


def test_exact_live_owners_bind_all_roles_in_independent_contexts(issued, control):
    receipt = issued.receipt
    attachment, descriptor, sandbox_receipt, inspection = _upstreams(issued)
    assert _validate(issued) is receipt
    assert control.events == ["bind_issue", "bind_done", "inspection_issue", "inspection_done"]
    assert len(control.bind_issues) == len(control.target_issues) == 1
    assert bind_owner.validate_sandbox_backend_binding(attachment, descriptor, sandbox_receipt) is attachment
    assert target_owner.validate_target_inspection_receipt(inspection) is inspection
    assert receipt.phase_id == "RUNTIME.JAVA.PINNED.1B"
    assert receipt.schema_version == "runtime_java_pinned_backend_target_binding_1b_v1"
    assert receipt.requirement_profile == "RUNTIME.JAVA.PINNED.1"
    assert receipt.requirement_schema == "runtime_java_pinned_1_v1"
    assert receipt.target_image_identity == attachment.image_identity == inspection.image_identity == target_owner.IMAGE
    assert receipt.canonical_backend_route_identity == attachment.canonical_backend_identity == inspection.backend_route_identity == _ROUTE
    assert receipt.canonical_backend_server_version == attachment.canonical_backend_version == inspection.backend_server_version == _VERSION
    assert receipt.bind_attachment_id == attachment.attachment_id
    assert receipt.bind_attachment_fingerprint == attachment.fingerprint
    assert receipt.bind_semantics_id == bind_owner.BINDING_SEMANTICS
    assert receipt.bind_bracket_equal is True
    assert receipt.bind_sandbox_descriptor_fingerprint == descriptor.fingerprint
    assert receipt.bind_sandbox_receipt_fingerprint == sandbox_receipt.fingerprint
    assert receipt.bind_sandbox_receipt_evidence_digest == sandbox_receipt.evidence_sha256
    assert receipt.inspection_owner_identity == inspection.owner_identity
    assert receipt.inspection_proof_context_identity == inspection.proof_context_identity
    assert receipt.inspection_receipt_id == inspection.receipt_id
    assert receipt.inspection_receipt_fingerprint == inspection.fingerprint
    assert receipt.inspection_evidence_digest == inspection.evidence_digest
    assert receipt.inspection_cleanup_evidence_digest == inspection.cleanup_evidence_digest
    assert receipt.proof_context_identity != inspection.proof_context_identity
    assert all(len(getattr(receipt, key)) == 64 for key in ("receipt_id", "proof_context_identity", "fingerprint", "evidence_digest"))
    assert receipt.issuing_pid == owner.os.getpid()
    assert owner._SECRET != bind_owner._SECRET != target_owner._SECRET
    assert all(getattr(receipt, key) is True for key in (
        "route_equal", "version_equal", "image_equal", "upstream_authenticated", "binding_result",
        "bind_cleanup_verified", "bind_sandbox_cleanup_verified", "inspection_cleanup_verified"))
    assert receipt.remaining_phase_containers == 0
    assert descriptor.seccomp_policy_sha256 == bind_owner.POLICY_SHA256
    assert all(command[0] not in {"start", "run", "exec", "pull", "build", "ps"}
        for command in control.target_commands)
    with pytest.raises(FrozenInstanceError):
        receipt.requirement_profile = "changed"


def test_receipt_report_and_repeated_validation_grant_no_authority_or_lifecycle(issued, control, monkeypatch):
    receipt = issued.receipt
    before = deepcopy(receipt.as_dict())
    report = issued.as_dict()
    assert receipt.as_dict()["report_only"] is True
    assert all(getattr(receipt, key) is False for key in _FALSE_CLAIMS)
    assert not any(hasattr(receipt, key) for key in ("consume", "invalidate", "lease_id", "lifecycle_state"))
    monkeypatch.setattr(bind_owner, "issue_sandbox_backend_binding", lambda: pytest.fail("validation issued BIND"))
    monkeypatch.setattr(target_owner, "inspect_target", lambda: pytest.fail("validation inspected target"))
    monkeypatch.setattr(bind_owner, "sandbox_backend_binding_satisfies_java1_discovery",
        lambda *args: pytest.fail("old discovery comparator used with PINNED evidence"))
    for _ in range(3):
        assert _validate(issued) is receipt
    assert receipt.as_dict() == before
    assert issued.as_dict() == report
    json.dumps(report, allow_nan=False)


def test_public_issuer_has_no_caller_evidence_route_image_or_requirement_arguments(control):
    assert not inspect.signature(owner.issue_pinned_backend_target_binding).parameters
    for value in ("alias", target_owner.IMAGE, {}, None):
        with pytest.raises(TypeError):
            owner.issue_pinned_backend_target_binding(value)
    assert control.events == []


@pytest.mark.parametrize("kind", ["copy", "deepcopy", "replace", "json", "reconstructed", "wrapper", "subclass"])
def test_same_attachment_fields_fingerprints_and_hashes_never_recreate_authenticity(issued, kind):
    receipt = issued.receipt
    if kind == "copy": candidate = copy(receipt)
    elif kind == "deepcopy": candidate = deepcopy(receipt)
    elif kind == "replace": candidate = replace(receipt)
    elif kind == "json": candidate = json.loads(json.dumps(receipt.as_dict()))
    elif kind == "wrapper": candidate = SimpleNamespace(**receipt.as_dict())
    else:
        cls = owner.PinnedJavaBackendTargetBindingReceipt
        if kind == "subclass":
            class Subclass(cls): pass
            cls = Subclass
        candidate = cls(**{field.name: getattr(receipt, field.name) for field in fields(receipt) if field.init})
    if hasattr(candidate, "fingerprint"):
        assert candidate.fingerprint == receipt.fingerprint
    _assert_rejected(issued, receipt=candidate)
    assert _validate(issued) is receipt


@pytest.mark.parametrize("field,value", [
    *[(key, "changed") for key in (
        "phase_id", "schema_version", "requirement_profile", "requirement_schema", "owner_identity",
        "proof_context_identity", "receipt_id", "target_image_identity",
        "canonical_backend_route_identity", "canonical_backend_server_version", "bind_attachment_id",
        "bind_attachment_fingerprint", "bind_semantics_id", "bind_sandbox_descriptor_fingerprint",
        "bind_sandbox_receipt_fingerprint", "bind_sandbox_receipt_evidence_digest",
        "inspection_owner_identity", "inspection_proof_context_identity", "inspection_receipt_id",
        "inspection_receipt_fingerprint", "inspection_evidence_digest", "inspection_cleanup_evidence_digest",
        "inspection_image_identity", "inspection_backend_route_identity", "inspection_backend_server_version",
        "inspection_controller_evidence_digest", "evidence_digest")],
    ("_signature", "0" * 64), ("issuing_pid", -1), ("bind_bracket_equal", False),
    ("route_equal", False), ("version_equal", False), ("image_equal", False),
    ("upstream_authenticated", False), ("binding_result", False),
    ("inspection_controller_identity", ()), ("inspection_controller_source_identity", ()),
    *[(key, True) for key in _FALSE_CLAIMS],
])
def test_changed_live_identity_hmac_digest_or_forbidden_claim_fails_closed(issued, field, value):
    original = _mutate(issued.receipt, field, value)
    try:
        _assert_rejected(issued)
    finally:
        object.__setattr__(issued.receipt, field, original)
    assert _validate(issued) is issued.receipt


def test_new_owner_signed_tampering_cannot_replace_registered_projection(issued):
    receipt = issued.receipt
    original, signature = receipt.canonical_backend_server_version, receipt._signature
    try:
        object.__setattr__(receipt, "canonical_backend_server_version", "changed")
        object.__setattr__(receipt, "_signature", owner._sign(receipt))
        _assert_rejected(issued)
    finally:
        object.__setattr__(receipt, "canonical_backend_server_version", original)
        object.__setattr__(receipt, "_signature", signature)


def test_wrong_process_or_missing_registry_rejects_original_live_object(issued, monkeypatch):
    pid = owner.os.getpid()
    monkeypatch.setattr(owner.os, "getpid", lambda: pid + 1)
    _assert_rejected(issued)
    monkeypatch.setattr(owner.os, "getpid", lambda: pid)
    owner._LIVE.clear()
    _assert_rejected(issued)


@pytest.mark.parametrize("role", [0, 1, 2, 3])
@pytest.mark.parametrize("kind", ["copy", "deepcopy", "json", "wrapper"])
def test_same_upstream_projection_cannot_substitute_for_retained_original(issued, role, kind):
    upstreams = list(_upstreams(issued))
    original = upstreams[role]
    if kind == "copy": candidate = copy(original)
    elif kind == "deepcopy": candidate = deepcopy(original)
    elif kind == "json": candidate = json.loads(json.dumps(original.as_dict()))
    else: candidate = SimpleNamespace(**original.as_dict())
    if hasattr(candidate, "fingerprint"):
        assert candidate.fingerprint == original.fingerprint
    upstreams[role] = candidate
    _assert_rejected(issued, upstreams=upstreams)


@pytest.mark.parametrize("role", [0, 1, 2, 3])
def test_different_authentic_upstream_or_same_descriptor_different_receipt_is_rejected(issued, control, role):
    other = owner.issue_pinned_backend_target_binding()
    assert other.status == owner.COMPLETE
    assert _validate(other) is other.receipt
    upstreams = list(_upstreams(issued))
    upstreams[role] = _upstreams(other)[role]
    # The frozen sandbox owner can issue equal fingerprints to different objects.
    if role in (1, 2):
        assert upstreams[role].fingerprint == _upstreams(issued)[role].fingerprint
    _assert_rejected(issued, upstreams=upstreams)
    assert _validate(issued) is issued.receipt


def test_entire_other_authenticated_bind_pair_cannot_be_rebound(issued, control):
    other = owner.issue_pinned_backend_target_binding()
    assert other.status == owner.COMPLETE
    _assert_rejected(issued, upstreams=(*_upstreams(other)[:3], issued.inspection_receipt))
    assert _validate(issued) is issued.receipt


@pytest.mark.parametrize("role,field,value", [
    (0, "canonical_backend_identity", "local-docker:changed"),
    (0, "canonical_backend_version", "changed"),
    (0, "image_identity", "sha256:" + "a" * 64),
    (0, "sandbox_descriptor_fingerprint", "0" * 64),
    (0, "sandbox_receipt_fingerprint", "0" * 64),
    (0, "sandbox_receipt_evidence_sha256", "0" * 64),
    (1, "verification_receipt_fingerprint", "0" * 64),
    (2, "evidence_sha256", "0" * 64),
    (3, "proof_context_identity", "0" * 64),
    (3, "receipt_id", "0" * 64),
    (3, "image_identity", "sha256:" + "a" * 64),
    (3, "backend_route_identity", "local-docker:changed"),
    (3, "backend_server_version", "changed"),
    (3, "image_metadata_digest", "0" * 64),
    (3, "inspection_configuration_digest", "0" * 64),
    (3, "evidence_digest", "0" * 64),
    (3, "cleanup_evidence_digest", "0" * 64),
])
def test_upstream_identity_fingerprint_and_digest_tampering_is_reauthenticated(issued, role, field, value):
    upstream = _upstreams(issued)[role]
    original = _mutate(upstream, field, value)
    try:
        _assert_rejected(issued)
    finally:
        object.__setattr__(upstream, field, original)
    assert _validate(issued) is issued.receipt


@pytest.mark.parametrize("role", ["java", "javac", "controller"])
def test_changed_nested_inspection_measurement_cannot_hide_behind_cached_digest(issued, role):
    measured = getattr(issued.inspection_receipt.archive, role)
    original = _mutate(measured, "sha256", "0" * 64)
    try:
        _assert_rejected(issued)
    finally:
        object.__setattr__(measured, "sha256", original)


@pytest.mark.parametrize("part", ["route", "version", "version_whitespace", "version_case"])
def test_genuine_authenticated_backend_values_must_match_exactly(control, part):
    if part == "route": control.bind_route = _ROUTE + "changed"
    elif part == "version": control.bind_version = "29.6.1"
    elif part == "version_whitespace": control.bind_version = _VERSION.strip()
    else: control.bind_version = _VERSION.lower()
    outcome = owner.issue_pinned_backend_target_binding()
    assert outcome.status == owner.MISMATCH and outcome.receipt is None
    assert owner._LIVE == {}
    assert len(control.bind_issues) == len(control.target_issues) == 1
    attachment, descriptor, receipt = control.bind_issues[0]
    assert bind_owner.validate_sandbox_backend_binding(attachment, descriptor, receipt) is attachment
    assert target_owner.validate_target_inspection_receipt(control.target_issues[0].receipt)


def test_image_mismatch_has_no_fallback_even_when_toolchain_hashes_match(control):
    def changed_image(result):
        attachment, descriptor, receipt = result
        object.__setattr__(attachment, "image_identity", "sha256:" + "a" * 64)
        return attachment, descriptor, receipt
    control.after_bind = changed_image
    outcome = owner.issue_pinned_backend_target_binding()
    assert outcome.status == owner.MISMATCH and outcome.receipt is None
    assert owner._LIVE == {}


@pytest.mark.parametrize("role,value", [("bind", "json"), ("bind", "string"),
    ("inspection", "json"), ("inspection", "string"), ("inspection", "old_discovery"),
    ("inspection", "copied"), ("inspection", "wrapper")])
def test_public_issuer_rejects_report_only_fabricated_or_old_discovery_upstreams(control, role, value):
    if role == "bind":
        control.after_bind = lambda result: (
            json.loads(json.dumps(result[0].as_dict())) if value == "json" else "BIND.1",
            result[1], result[2])
    else:
        def substitute(result):
            if value == "json": candidate = json.loads(json.dumps(result.receipt.as_dict()))
            elif value == "string": candidate = "RUNTIME.JAVA.PINNED.1A"
            elif value == "copied": candidate = copy(result.receipt)
            elif value == "wrapper": candidate = SimpleNamespace(**result.receipt.as_dict())
            else:
                candidate = discovery_owner.LocalJavaDiscovery((), True, True, "old_discovery",
                    _ROUTE, _VERSION)
            return replace(result, receipt=candidate)
        control.after_target = substitute
    outcome = owner.issue_pinned_backend_target_binding()
    assert outcome.status == owner.MISMATCH and outcome.receipt is None
    assert owner._LIVE == {}


@pytest.mark.parametrize("role", [0, 1, 2, 3])
def test_caller_strings_pretending_to_be_any_upstream_are_rejected(issued, role):
    upstreams = list(_upstreams(issued))
    upstreams[role] = str(upstreams[role].fingerprint)
    _assert_rejected(issued, upstreams=upstreams)


@pytest.mark.parametrize("source,failure", [("bind", "workspace"), ("bind", "containers"),
    ("bind", "sandbox_cleanup"), ("inspection", "workspace"),
    ("inspection", "export_child_reaped"), ("inspection", "absence")])
def test_original_owner_cleanup_failures_prevent_positive_attachment(control, source, failure):
    if source == "bind":
        def configure(controlled):
            key, value = {"workspace": ("temporary_workspace_removed", False),
                "containers": ("phase_container_count_after_teardown", 1),
                "sandbox_cleanup": ("cleanup_verified", False)}[failure]
            controlled.live[key] = value
        control.configure_bind = configure
    else:
        def configure(controlled):
            if failure == "workspace": controlled.workspace_removed = False
            elif failure == "absence":
                controlled.captures["absence"] = target_controls._capture(exit_code=1, stderr=b"unavailable")
            else: controlled.cleanup[failure] = False
        control.configure_target = configure
    outcome = owner.issue_pinned_backend_target_binding()
    assert outcome.status == owner.CLEANUP_FAILURE and outcome.receipt is None
    assert owner._LIVE == {}


@pytest.mark.parametrize("role,key,value", [
    (0, "sandbox_cleanup_verified", False),
    (0, "pre_control_reaped_and_pipes_closed", False),
    (0, "post_control_reaped_and_pipes_closed", False),
    (0, "temporary_workspace_removed", False),
    (0, "remaining_phase_containers", 1),
    (0, "remaining_phase_containers", False),
    (2, "cleanup_verified", False),
])
def test_upstream_cleanup_tampering_returns_cleanup_failure(issued, role, key, value):
    upstream = _upstreams(issued)[role]
    original = _mutate(upstream, key, value)
    try:
        _assert_rejected(issued, status=owner.CLEANUP_FAILURE)
    finally:
        object.__setattr__(upstream, key, original)
    assert _validate(issued) is issued.receipt


@pytest.mark.parametrize("failure", [
    "export_child_reaped", "export_pipes_closed", "deadline_supervisor_stopped",
    "stderr_reader_stopped", "control_children_reaped_and_pipes_closed",
    "stopped_container_removed", "known_container_absence_verified", "temporary_profile_removed",
    "temporary_workspace_removed", "remaining_phase_containers", "missing", "duplicate",
])
def test_all_inspection_cleanup_evidence_is_mandatory_and_exact(issued, failure):
    inspection = issued.inspection_receipt
    cleanup = dict(inspection.cleanup_evidence)
    if failure == "missing": changed = ()
    elif failure == "duplicate": changed = inspection.cleanup_evidence + inspection.cleanup_evidence[:1]
    else:
        cleanup[failure] = 1 if failure == "remaining_phase_containers" else False
        changed = tuple(cleanup.items())
    original = _mutate(inspection, "cleanup_evidence", changed)
    try:
        _assert_rejected(issued, status=owner.CLEANUP_FAILURE)
    finally:
        object.__setattr__(inspection, "cleanup_evidence", original)


@pytest.mark.parametrize("role", ["bind", "inspection"])
def test_completed_attempt_upstreams_cannot_be_replayed_into_new_binding(issued, control, monkeypatch, role):
    if role == "bind":
        monkeypatch.setattr(bind_owner, "issue_sandbox_backend_binding", lambda: _upstreams(issued)[:3])
    else:
        monkeypatch.setattr(target_owner, "inspect_target", lambda: control.target_issues[0])
    other = owner.issue_pinned_backend_target_binding()
    assert other.status == owner.MISMATCH and other.receipt is None
    assert "previous_binding_attempt" in other.reason
    # Reusable evidence validation grants no permission to create new provenance.
    assert _validate(issued) is issued.receipt


def test_private_issuer_requires_owner_established_exact_attempt(issued):
    with pytest.raises(owner.PinnedBindingBlocked) as error:
        owner._issue_receipt("0" * 64, *_upstreams(issued))
    assert error.value.status == owner.MISMATCH
    assert _validate(issued) is issued.receipt


def test_old_discovery_comparator_is_never_used_for_pinned_evidence(control, monkeypatch):
    monkeypatch.setattr(bind_owner, "sandbox_backend_binding_satisfies_java1_discovery",
        lambda *args: pytest.fail("old JAVA.1 comparator used"))
    assert owner.issue_pinned_backend_target_binding().status == owner.COMPLETE


def test_upstream_reauthentication_uses_original_public_owner_validators(issued, monkeypatch):
    for module, name in ((bind_owner, "validate_sandbox_backend_binding"),
            (target_owner, "validate_target_inspection_receipt")):
        original = getattr(module, name)
        with monkeypatch.context() as patches:
            patches.setattr(module, name, lambda *args: (_ for _ in ()).throw(ValueError("owner rejected")))
            _assert_rejected(issued)
        assert getattr(module, name) is original
    assert _validate(issued) is issued.receipt


def test_pure_negative_matrix_authenticates_original_without_mutating_it(issued):
    before = deepcopy(issued.as_dict())
    matrix = owner.negative_authentication_matrix(issued)
    assert matrix and all(type(value) is bool and value for value in matrix.values())
    assert issued.as_dict() == before
    assert _validate(issued) is issued.receipt
