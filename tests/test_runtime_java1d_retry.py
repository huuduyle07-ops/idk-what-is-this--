"""Pure retry controls; all fabricated owner proofs are development fixtures."""
from copy import copy, deepcopy
from dataclasses import asdict, replace
import inspect
from unittest.mock import patch

import pytest

from core import sandboxed_java_discovery_continuation as owner
from tests._preflight_runtime1_guard import no_runtime_effects
from tests.test_runtime_java1c import capture
from tests.test_runtime_sandbox_bind1 import control, issued


@pytest.fixture(autouse=True)
def guarded():
    with no_runtime_effects(strict=True) as effects:
        yield
    assert effects.denied_attempts == {}


def inventory(attachment):
    pair = owner.discovery.LocalJavaToolchainPair(owner.JAVA_PATH, owner.JAVA_SHA256,
        owner.JAVAC_PATH, owner.JAVAC_SHA256, '/usr/local/bin/python', 'a' * 64)
    artifact = owner.discovery.LocalJavaArtifact(owner.IMAGE, os='linux', architecture='amd64',
        toolchains=(pair,), status='local_java_toolchain_present')
    return owner.discovery.LocalJavaDiscovery((artifact,), True, True, 'eligible_exact_local_java_toolchain_present',
        attachment.canonical_backend_identity, attachment.canonical_backend_version)


def java_pair(sd, sr):
    j = owner.java1c
    receipt = j.JavaContinuationReceipt(sd.fingerprint, sr.fingerprint,
        'javac fixture', 'java fixture', 'b' * 64, 100, 'c' * 64)
    receipt = replace(receipt, _signature=j._sign(receipt))
    descriptor = j.JavaContinuationDescriptor(receipt.fingerprint, sd.fingerprint, sr.fingerprint)
    descriptor = replace(descriptor, _signature=j._sign(descriptor))
    return descriptor, receipt


@pytest.fixture
def harness(issued):
    attachment, sd, sr = issued
    jd, jr = java_pair(sd, sr)
    state = {'binding': issued, 'inventory': inventory(attachment), 'java': (jd, jr), 'order': [],
        'java_report': {'cleanup_verified': True, 'child_and_capture_cleanup_verified': True,
            'temporary_workspace_removed': True, 'compile_count': 1, 'jvm_fixture_count': 1,
            'java_workload_attempted': True, 'live_sandbox2': {'javac_version_count': 1, 'java_version_count': 1}}}
    def bind():
        state['order'].append('binding'); return state['binding']
    def discover():
        state['order'].append('discovery'); return state['inventory']
    def java():
        state['order'].append('java1c'); return *state['java'], state['java_report']
    with patch.object(owner.binding, 'issue_sandbox_backend_binding', bind), \
            patch.object(owner.discovery, 'discover_local_java_artifacts', discover), \
            patch.object(owner.java1c, 'verify', java), \
            patch.object(owner.sandbox, '_bounded_process', return_value=capture(stdout=b'')):
        yield state


def test_exact_owners_order_one_binding_and_positive_separate_receipt(harness):
    receipt, report = owner.verify()
    assert harness['order'] == ['binding', 'discovery', 'java1c']
    assert report['status'] == owner.COMPLETE
    assert report['binding_issuance_attempts'] == report['discovery_invocations'] == report['java1c_invocations'] == 1
    assert owner.validate_provider_continuation_receipt(receipt) is receipt
    assert receipt.phase_id == 'RUNTIME.JAVA.1D' and receipt.schema_version == 'runtime_java_1d_v1'
    assert receipt.complete_inventory is receipt.backend_binding_result is True
    assert receipt.exact_pinned_image_membership is receipt.toolchain_coherence is True
    assert receipt.artifact_inventory == harness['inventory'].artifacts
    assert receipt.binding_attachment_id == harness['binding'][0].attachment_id
    assert receipt.sandbox_receipt_evidence_sha256 == harness['binding'][2].evidence_sha256
    assert receipt.java1c_receipt_fingerprint == harness['java'][1].fingerprint
    for key in owner.AUTHORITIES + ('daemon_continuity_proven', 'aba_resistance_proven',
            'compatibility_asserted', 'runtime_java_1_v1_identity_asserted', 'synth_auth_requirement_satisfied'):
        assert getattr(receipt, key) is False
    assert '_signature' not in receipt.as_dict()


def test_exact_owner_values_are_passed_to_public_binding_helper(harness):
    original = owner.binding.sandbox_backend_binding_satisfies_java1_discovery
    with patch.object(owner.binding, 'sandbox_backend_binding_satisfies_java1_discovery', wraps=original) as compare:
        receipt, _ = owner.verify()
    assert receipt is not None
    assert compare.call_count == 2  # Initial gate and final pure revalidation.
    for call in compare.call_args_list:
        assert call.args[0] is harness['binding'][0]
        assert call.args[1] is harness['inventory'].backend_identity
        assert call.args[2] is harness['inventory'].backend_version


@pytest.mark.parametrize('change,status', [
    ('incomplete', owner.DISCOVERY_INCOMPLETE), ('identity', owner.BACKEND_BINDING),
    ('version', owner.BACKEND_BINDING), ('missing', owner.ARTIFACT_MISSING),
    ('toolchain', owner.PROVIDER_COHERENCE), ('duplicates', owner.PROVIDER_COHERENCE),
    ('cleanup', owner.CLEANUP), ('platform', owner.PROVIDER_COHERENCE)])
def test_discovery_failure_stops_before_java_and_receipt(harness, change, status):
    inv = harness['inventory']
    if change == 'incomplete': inv = replace(inv, complete_inventory=False)
    elif change == 'identity': inv = replace(inv, backend_identity=inv.backend_identity + ' ')
    elif change == 'version': inv = replace(inv, backend_version=inv.backend_version.strip())
    elif change == 'missing': inv = replace(inv, artifacts=())
    elif change == 'cleanup': inv = replace(inv, cleanup_verified=False)
    elif change == 'duplicates': inv = replace(inv, artifacts=inv.artifacts * 2)
    elif change == 'platform': inv = replace(inv, artifacts=(replace(inv.artifacts[0], os='windows'),))
    else: inv = replace(inv, artifacts=(replace(inv.artifacts[0], toolchains=()),))
    harness['inventory'] = inv
    receipt, report = owner.verify()
    assert receipt is None and report['positive_receipt_issued'] is False
    assert report['status'] == status
    assert harness['order'] == ['binding', 'discovery']
    assert report['inventory_count'] == len(inv.artifacts)


@pytest.mark.parametrize('kind', ['json', 'copy', 'wrong_pair'])
def test_binding_json_copy_and_wrong_pair_stop_before_discovery(harness, kind):
    a, sd, sr = harness['binding']
    if kind == 'json': a = a.as_dict()
    elif kind == 'copy': a = copy(a)
    else: sd = deepcopy(sd)
    harness['binding'] = a, sd, sr
    receipt, report = owner.verify()
    assert receipt is None and report['status'] == owner.BACKEND_BINDING
    assert harness['order'] == ['binding']


@pytest.mark.parametrize('kind', ['json', 'tamper', 'cleanup'])
def test_java_authentication_or_cleanup_never_issues_positive_receipt(harness, kind):
    jd, jr = harness['java']
    if kind == 'json': jd, jr = jd.as_dict(), jr.as_dict()
    elif kind == 'tamper': jr = replace(jr, evidence_sha256='0' * 64)
    else: harness['java_report']['cleanup_verified'] = False
    harness['java'] = jd, jr
    receipt, report = owner.verify()
    assert receipt is None and report['positive_receipt_issued'] is False
    assert report['status'] == (owner.CLEANUP if kind == 'cleanup' else owner.JAVA_AUTHENTICATION)


@pytest.mark.parametrize('field,value', [('image_identity', 'sha256:' + '0' * 64),
    ('java_path', '/different/java'), ('java_sha256', '0' * 64),
    ('javac_path', '/different/javac'), ('javac_sha256', '0' * 64)])
def test_authenticated_but_incoherent_java_provider_is_rejected(harness, field, value):
    # Test-only signing fixture exercises coherence independently of HMAC failure.
    jd, jr = harness['java']
    changed = replace(jr)
    object.__setattr__(changed, field, value)
    object.__setattr__(changed, '_signature', owner.java1c._sign(changed))
    descriptor = replace(jd, verification_receipt_fingerprint=changed.fingerprint)
    descriptor = replace(descriptor, _signature=owner.java1c._sign(descriptor))
    harness['java'] = descriptor, changed
    receipt, report = owner.verify()
    assert receipt is None and report['status'] == owner.PROVIDER_COHERENCE


@pytest.mark.parametrize('kind', ['json', 'copy', 'tamper', 'wrong_process'])
def test_positive_report_copy_tamper_or_other_process_is_not_capability(harness, kind):
    receipt, _ = owner.verify()
    candidate = receipt
    if kind == 'json': candidate = receipt.as_dict()
    elif kind == 'copy': candidate = copy(receipt)
    elif kind == 'tamper': candidate = replace(receipt, inventory_sha256='0' * 64)
    with patch.object(owner.os, 'getpid', return_value=receipt.issuing_pid + (kind == 'wrong_process')):
        with pytest.raises(ValueError): owner.validate_provider_continuation_receipt(candidate)


def test_canonical_inventory_preserves_records_and_is_order_independent(issued):
    inv = inventory(issued[0])
    second = replace(inv.artifacts[0], image_identity='sha256:' + '0' * 64)
    first = replace(inv, artifacts=(*inv.artifacts, second, *inv.artifacts))
    reverse = replace(first, artifacts=tuple(reversed(first.artifacts)))
    artifacts, digest = owner._canonical_inventory(first)
    assert owner._canonical_inventory(reverse) == (artifacts, digest)
    assert len(artifacts) == 3 and artifacts.count(inv.artifacts[0]) == 2
    assert digest == owner.sandbox._hash([asdict(a) for a in artifacts])
    assert owner._canonical_inventory(replace(inv, artifacts=(replace(inv.artifacts[0], image_user='changed'),)))[1] != owner._canonical_inventory(inv)[1]


def test_no_caller_source_endpoint_or_metadata_inputs():
    assert not inspect.signature(owner.verify).parameters
    with pytest.raises(TypeError): owner.verify({'image_identity': owner.IMAGE})
