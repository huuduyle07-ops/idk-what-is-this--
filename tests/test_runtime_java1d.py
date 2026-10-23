"""Pure JAVA.1D stop-gate controls; fabricated fixtures are never live proof."""
from dataclasses import replace
import inspect
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from scripts import replay_runtime_java1d as owner
from tests._preflight_runtime1_guard import no_runtime_effects
from tests.test_runtime_java1c import sandbox_pair


@pytest.fixture(autouse=True)
def guarded():
    with no_runtime_effects(strict=True) as effects:
        yield
    assert effects.denied_attempts == {}


def test_authenticated_sandbox2_still_lacks_the_original_backend_witnesses():
    descriptor, receipt = sandbox_pair()
    report = owner.assess_authenticated_backend(descriptor, receipt)
    assert report['status'] == owner.BACKEND_BINDING
    assert report['missing_backend_witnesses'] == [
        'descriptor.backend_identity', 'descriptor.backend_version',
        'receipt.backend_identity', 'receipt.backend_version']
    assert report['sandbox_backend_identity'] is report['sandbox_backend_version'] is None
    assert report['backend_binding_result'] == report['backend_freshness_result'] == 'unproven'
    assert report['sandbox_descriptor_fingerprint'] == descriptor.fingerprint
    assert report['sandbox_receipt_fingerprint'] == receipt.fingerprint


@pytest.mark.parametrize('kind', ('json', 'caller_backend', 'tampered', 'wrong_receipt'))
def test_report_json_and_caller_backend_claims_cannot_fill_owner_witnesses(kind):
    descriptor, receipt = sandbox_pair()
    if kind == 'json':
        descriptor, receipt = descriptor.as_dict(), receipt.as_dict()
    elif kind == 'caller_backend':
        descriptor = SimpleNamespace(**descriptor.as_dict(),
            backend_identity='local-docker:claimed', backend_version='claimed')
    elif kind == 'tampered':
        descriptor = replace(descriptor, verification_receipt_fingerprint='0' * 64)
    else:
        receipt = replace(receipt, evidence_sha256='0' * 64)
    with pytest.raises(ValueError):
        owner.assess_authenticated_backend(descriptor, receipt)


def test_live_entry_has_no_caller_source_backend_or_json_inputs():
    assert not inspect.signature(owner.replay).parameters
    with pytest.raises(TypeError):
        owner.replay({'backend_version': 'caller'})


def test_measured_binding_block_stops_before_discovery_java_or_any_receipt_issuance():
    descriptor, receipt = sandbox_pair()
    live = {'cleanup_verified': True, 'phase_container_count_after_teardown': 0,
        'javac_version_count': 1, 'java_version_count': 1,
        'compile_count': 0, 'jvm_fixture_count': 0, 'stages': []}
    def denied(*args, **kwargs):
        raise AssertionError('backend blocker reached a later gate')
    with patch.object(owner.java1c, '_obtain_live_sandbox2', return_value=(descriptor, receipt, live)), \
            patch.object(owner.discovery, 'discover_local_java_artifacts', denied), \
            patch.object(owner.java1c, 'verify', denied):
        report = owner.replay()
    assert report['status'] == owner.BACKEND_BINDING
    assert report['provider_receipt_issued'] is False
    assert report['java1d_receipt_fingerprint'] is None
    assert report['discovery_attempted'] is report['java1c_verification_attempted'] is False
    assert report['complete_inventory'] is report['inventory_count'] is report['inventory_sha256'] is None
    assert report['artifact_inventory'] is report['selected_image_membership'] is None
    assert report['fresh_java1c_authenticated'] is False
    assert report['compatibility_asserted'] is report['runtime_java_1_v1_identity_asserted'] is False
    assert report['cleanup_verified'] is True
    assert report['exported_json_is_report_only'] is True
    assert all(report[key] is False for key in owner.sandbox2.AUTHORITIES)
    for key in ('docker_calls', 'docker_discovery_calls', 'docker_inspect_calls',
            'containers_created', 'source_projections', 'java1c_compile_executions',
            'java1c_fixture_executions', 'synth_runtime_lease_consumptions',
            'reflection_lease_consumptions', 'bank_executions', 'executor1r_retries',
            'repository_runtime_writes', 'apply_actions'):
        assert report['effects'][key] == 0


def test_failed_live_authentication_never_claims_cleanup_or_live_java():
    with patch.object(owner.java1c, '_obtain_live_sandbox2', side_effect=ValueError('unauthenticated')):
        report = owner.replay()
    assert report['status'] == owner.UNRESOLVED
    assert report['fresh_sandbox2_authenticated'] is report['fresh_java1c_authenticated'] is False
    assert report['cleanup_verified'] is report['remaining_phase_containers'] is None
    assert report['provider_receipt_issued'] is False


def test_cleanup_failure_blocks_even_the_successfully_authenticated_attempt():
    descriptor, receipt = sandbox_pair()
    live = {'cleanup_verified': False, 'phase_container_count_after_teardown': 1,
        'javac_version_count': 0, 'java_version_count': 0,
        'compile_count': 0, 'jvm_fixture_count': 0, 'stages': []}
    with patch.object(owner.java1c, '_obtain_live_sandbox2', return_value=(descriptor, receipt, live)):
        report = owner.replay()
    assert report['status'] == owner.CLEANUP
    assert report['provider_receipt_issued'] is False


def test_separate_report_epoch_never_relabels_an_existing_provider():
    assert owner.PHASE_ID == 'RUNTIME.JAVA.1D'
    assert owner.SCHEMA_VERSION == 'runtime_java_1d_v1'
    assert owner.java1c.PHASE_ID == 'RUNTIME.JAVA.1C'
    assert owner.java1c.SCHEMA_VERSION == 'runtime_java_1c_v1'
    assert owner.POLICY_SHA256 == owner.java1c.POLICY_SHA256
