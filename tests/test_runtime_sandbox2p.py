"""Pure provenance preflight tests; fabricated pairs are never live proof."""
from copy import deepcopy
from dataclasses import replace
import inspect
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from core import sandbox_backend_provenance as owner
from tests._preflight_runtime1_guard import no_runtime_effects
from tests.test_runtime_java1c import capture, sandbox_pair


@pytest.fixture(autouse=True)
def guarded():
    with no_runtime_effects(strict=True) as effects:
        yield
    assert effects.denied_attempts == {}


def live_fixture():
    descriptor, receipt = sandbox_pair()
    live = {'status': owner.sandbox2.COMPLETE, 'cleanup_verified': True,
        'temporary_workspace_removed': True, 'phase_container_count_after_teardown': 0,
        'javac_version_count': 1, 'java_version_count': 1,
        'compile_count': 0, 'jvm_fixture_count': 0,
        'stages': [{'mode': m, 'verdict': owner.sandbox2.PASSED} for m in owner.sandbox2.LADDER],
        'descriptor': descriptor.as_dict(), 'verification_receipt': receipt.as_dict()}
    return descriptor, receipt, live


@pytest.mark.parametrize('version', ['26.0.2', ' AbC.01\n', '0', 123, True, ['exact']])
def test_original_semantics_preserve_exact_server_version_and_literal_route(version):
    endpoint = 'npipe:////./pipe/dockerDesktopLinuxEngine'
    result = owner._backend_witness(json.dumps({'Server': {'Os': 'linux', 'Version': version},
        'Client': {'Version': 'different'}, 'Context': 'caller-context'}), endpoint)
    assert result['backend_identity'] == 'local-docker:' + endpoint
    assert result['backend_version'] == str(version)
    assert result['backend_endpoint_identity'] == endpoint
    assert result['server_os'] == 'linux'


@pytest.mark.parametrize('value', [[], None, {}, {'Server': []}, {'Server': 'alias'},
    {'Server': {'Version': '1'}}, {'Server': {'Os': 'windows', 'Version': '1'}},
    {'Server': {'Os': 'Linux', 'Version': '1'}},
    {'Server': {'Os': 'linux', 'Version': ''}}, {'Server': {'Os': 'linux', 'Version': 0}},
    {'Server': {'Os': 'linux', 'Version': False}}, {'Client': {'Os': 'linux', 'Version': '1'}},
    {'Context': 'desktop-linux'}, {'Id': 'sha256:' + 'a' * 64}, {'timestamp': 123}])
def test_client_context_image_timestamp_and_missing_server_cannot_replace_witness(value):
    with pytest.raises(owner.ProvenanceBlocked) as error:
        owner._backend_witness(json.dumps(value), 'fixed-endpoint')
    assert error.value.status == owner.BACKEND_VERSION


@pytest.mark.parametrize('raw', [b'not json', b'\xff', b'{'])
def test_invalid_or_truncated_version_json_blocks(raw):
    with pytest.raises(owner.ProvenanceBlocked):
        owner._backend_witness(raw, 'fixed-endpoint')


def test_measurement_uses_only_frozen_route_and_one_bounded_version_control():
    endpoint = owner.baseline._local_endpoint()
    prefix = ('fixed-docker.exe', '--config', 'absent', '--host', endpoint)
    calls = []
    def control(argv, **kwargs):
        calls.append((argv, kwargs))
        return capture(stdout=b'{"Server":{"Os":"linux","Version":" Exact "}}')
    with patch.object(owner.baseline, '_docker_prefix', return_value=prefix), \
            patch.object(owner.baseline, '_bounded_process', control):
        result = owner._measure_backend()
    assert result['backend_version'] == ' Exact '
    assert calls == [(prefix + ('version', '--format', '{{json .}}'),
        {'timeout_ms': 8000, 'stdout_limit': 65536})]


@pytest.mark.parametrize('prefix', [(), ('docker',),
    ('docker', '--config', 'absent', '--context', 'desktop-linux'),
    ('docker', '--config', 'absent', '--host', 'tcp://caller')])
def test_missing_or_nonfrozen_route_stops_before_control(prefix):
    with patch.object(owner.baseline, '_docker_prefix', return_value=prefix):
        with pytest.raises(owner.ProvenanceBlocked) as error:
            owner._measure_backend()
    assert error.value.status == owner.BACKEND_IDENTITY


@pytest.mark.parametrize('changes', [{'status': 'sandbox_timeout'}, {'exit_code': 1},
    {'termination_within_deadline': False}, {'status': 'sandbox_control_failure'}])
def test_failed_or_unbounded_control_never_becomes_a_backend_witness(changes):
    endpoint = owner.baseline._local_endpoint()
    with patch.object(owner.baseline, '_docker_prefix',
            return_value=('docker', '--config', 'absent', '--host', endpoint)), \
            patch.object(owner.baseline, '_bounded_process', return_value=capture(**changes)):
        with pytest.raises(owner.ProvenanceBlocked):
            owner._measure_backend()


@pytest.mark.parametrize('kind', ['descriptor_json', 'receipt_json', 'wrapper', 'wrong_receipt',
    'wrong_descriptor', 'descriptor_phase', 'receipt_phase', 'descriptor_schema',
    'receipt_schema', 'descriptor_policy', 'receipt_policy'])
def test_pair_authentication_rejects_replacement_or_changed_exact_contract(kind):
    descriptor, receipt = sandbox_pair()
    if kind == 'descriptor_json': descriptor = descriptor.as_dict()
    elif kind == 'receipt_json': receipt = receipt.as_dict()
    elif kind == 'wrapper': descriptor = SimpleNamespace(**descriptor.as_dict(), backend_identity='alias')
    elif kind == 'wrong_receipt': receipt = replace(receipt, evidence_sha256='0' * 64)
    elif kind == 'wrong_descriptor': descriptor = replace(descriptor, verification_receipt_fingerprint='0' * 64)
    else:
        role, field = kind.split('_', 1)
        target = descriptor if role == 'descriptor' else receipt
        object.__setattr__(target, {'phase': 'phase_id', 'schema': 'schema_version',
            'policy': 'seccomp_policy_sha256'}[field], 'changed')
        # Even an owner-signed wrong phase/schema/policy must fail the exact gate.
        object.__setattr__(target, '_signature', owner.sandbox2._sign(target))
    with pytest.raises(ValueError):
        owner.assess_backend_freshness(descriptor, receipt)


def test_authentic_snapshot_cannot_supply_daemon_continuity_or_timestamp_freshness():
    descriptor, receipt = sandbox_pair()
    before = deepcopy((descriptor.as_dict(), receipt.as_dict()))
    result = owner.assess_backend_freshness(descriptor, receipt)
    assert result['status'] == owner.FRESHNESS
    assert result['owner_defined_backend_continuity_mechanism'] is None
    assert result['timestamp_proves_backend_continuity'] is False
    assert result['endpoint_version_equality_proves_backend_continuity'] is False
    assert result['attachment_issued'] is False
    assert before == (descriptor.as_dict(), receipt.as_dict())


def test_replay_measures_revalidates_and_stops_without_discovery_java_or_attachment():
    descriptor, receipt, live = live_fixture()
    endpoint = owner.baseline._local_endpoint()
    with patch.object(owner.java1c, '_obtain_live_sandbox2', return_value=(descriptor, receipt, live)), \
            patch.object(owner.baseline, '_docker_prefix',
                return_value=('docker', '--config', 'absent', '--host', endpoint)), \
            patch.object(owner.baseline, '_bounded_process',
                return_value=capture(stdout=b'{"Server":{"Os":"linux","Version":"1"}}')):
        report = owner.replay()
    assert report['status'] == owner.FRESHNESS
    assert report['fresh_sandbox2_authenticated'] is report['exact_live_pair_revalidated'] is True
    assert report['backend_identity'] == 'local-docker:' + endpoint
    assert report['backend_version'] == '1'
    assert report['sandbox_descriptor_fingerprint'] == descriptor.fingerprint
    assert report['sandbox_receipt_fingerprint'] == receipt.fingerprint
    assert report['additional_provenance_effects']['docker_calls'] == 1
    assert report['additional_provenance_effects']['version_calls'] == 1
    assert report['sandbox2_infrastructure_effects']['docker_calls'] == 0  # mocked ladder
    assert report['attachment_issued'] is False
    assert report['provenance_attachment_id'] is report['provenance_attachment_fingerprint'] is None
    assert report['process_local_attachment_authentication'] == 'not_attempted_no_issuance'
    assert report['negative_authentication_matrix'] == 'not_run_no_attachment_issued'
    assert report['cleanup_verified'] is True
    assert all(report[key] is False for key in owner.AUTHORITIES)
    assert set(report['prohibited_effects'].values()) == {0}


@pytest.mark.parametrize('change', ['descriptor', 'receipt', 'stage_evidence'])
def test_pair_or_evidence_changed_during_measurement_blocks_before_freshness(change):
    descriptor, receipt, live = live_fixture()
    def measure():
        if change == 'descriptor':
            object.__setattr__(descriptor, 'image_identity', 'changed')
        elif change == 'receipt':
            object.__setattr__(receipt, 'evidence_sha256', '0' * 64)
        else: live['stages'][0]['extra'] = 'changed'
        return {'backend_identity': 'measured', 'backend_version': 'measured'}
    with patch.object(owner.java1c, '_obtain_live_sandbox2', return_value=(descriptor, receipt, live)), \
            patch.object(owner, '_measure_backend', measure):
        report = owner.replay()
    assert report['status'] == owner.BINDING
    assert report['exact_live_pair_revalidated'] is report['attachment_issued'] is False


@pytest.mark.parametrize('key,value', [('cleanup_verified', False),
    ('temporary_workspace_removed', False), ('phase_container_count_after_teardown', 1)])
def test_sandbox_cleanup_failure_prevents_additional_measurement(key, value):
    descriptor, receipt, live = live_fixture()
    live[key] = value
    with patch.object(owner.java1c, '_obtain_live_sandbox2', return_value=(descriptor, receipt, live)):
        report = owner.replay()
    assert report['status'] == owner.UNRESOLVED
    assert report['cleanup_verified'] is False
    assert report['additional_provenance_effects']['docker_calls'] == 0
    assert report['backend_measurement_completed'] is report['attachment_issued'] is False


def test_failed_live_issuance_does_not_invent_cleanup():
    with patch.object(owner.java1c, '_obtain_live_sandbox2', side_effect=ValueError('unavailable')):
        report = owner.replay()
    assert report['status'] == owner.UNRESOLVED
    assert report['fresh_sandbox2_authenticated'] is report['attachment_issued'] is False
    assert report['cleanup_verified'] is report['remaining_phase_containers'] is None


def test_no_public_caller_backend_endpoint_report_or_freshness_override():
    assert not inspect.signature(owner.replay).parameters
    for value in ({'backend_identity': 'caller'}, 'desktop-linux', {'timestamp': 123}):
        with pytest.raises(TypeError): owner.replay(value)
    assert owner.POLICY_SHA256 == owner.sandbox2.POLICY_SHA256
    assert not hasattr(owner, 'SandboxBackendProvenanceAttachment')
    assert not hasattr(owner, '_SECRET')  # signing domain is deferred at the required stop
