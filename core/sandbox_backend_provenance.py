"""SANDBOX.2P provenance preflight; the frozen route cannot prove freshness.

This phase obtains a fresh owner pair, measures the original backend witness,
and reauthenticates that exact pair. It stops before attachment issuance:
separate Docker CLI connections provide no owner-defined daemon continuity.
No report, caller witness, or endpoint/version equality can remove that stop.
"""
import json
import subprocess
from unittest.mock import patch

from core import candidate_runtime_sandbox as baseline
from core import sandboxed_java_positive_continuation as java1c
from core import thread_compatible_runtime_sandbox as sandbox2

PHASE_ID = 'RUNTIME.SANDBOX.2P'
SCHEMA_VERSION = 'runtime_sandbox_2p_v1'
BACKEND_IDENTITY = 'RUNTIME_SANDBOX_2P_BLOCKED_BACKEND_IDENTITY'
BACKEND_VERSION = 'RUNTIME_SANDBOX_2P_BLOCKED_BACKEND_VERSION'
FRESHNESS = 'RUNTIME_SANDBOX_2P_BLOCKED_FRESHNESS'
BINDING = 'RUNTIME_SANDBOX_2P_BLOCKED_BINDING'
UNRESOLVED = 'RUNTIME_SANDBOX_2P_BLOCKED_UNRESOLVED'
POLICY_SHA256 = '5a36bdf1676c4b0d7b4bef489f5e90b5c8fb201b5194be48baf61f4206a81f75'
METHOD_ID = 'frozen_local_docker_version_server_v1'
AUTHORITIES = ('runtime_authority', 'real_task_runtime_authority',
    'repository_write_authority', 'apply_authority', 'network_authority',
    'host_mount_authority', 'shell_authority', 'shell_available',
    'arbitrary_command_authority', 'compatibility_authority')


class ProvenanceBlocked(ValueError):
    def __init__(self, status, reason):
        super().__init__(reason)
        self.status = status


def _authenticate_pair(descriptor, receipt):
    # Existing public SANDBOX.2 validator plus the existing exact ladder gate.
    java1c.authenticate_sandbox2(descriptor, receipt)
    if any(value.phase_id != 'RUNTIME.SANDBOX.2'
            or value.schema_version != 'runtime_sandbox_2_v1'
            or value.seccomp_policy_sha256 != POLICY_SHA256
            for value in (descriptor, receipt)):
        raise ValueError('sandbox2p_exact_phase_schema_policy_required')
    return descriptor, receipt


def _backend_witness(raw, endpoint):
    """Original JAVA.1/SANDBOX.1 semantics, without image inspection.

    Both frozen owners require a truthy Server.Version and Linux Server.Os.
    Identity is their literal endpoint prefix; version is str(Server.Version).
    There is no strip, case-fold, semver coercion, or client-field fallback.
    """
    try:
        value = json.loads(raw)
        if type(value) is not dict:
            raise ValueError('non_object_version_metadata')
        server = value.get('Server') or {}
        if type(server) is not dict or server.get('Os') != 'linux':
            raise ValueError('linux_server_required')
        if not server.get('Version'):
            raise ValueError('server_version_missing')
        return {'backend_identity': 'local-docker:' + endpoint,
            'backend_version': str(server['Version']),
            'backend_endpoint_identity': endpoint,
            'server_os': server['Os'], 'measurement_method_id': METHOD_ID}
    except (ValueError, TypeError, UnicodeError) as error:
        raise ProvenanceBlocked(BACKEND_VERSION, 'original_server_version_unavailable') from error


def _measure_backend():
    # Only the frozen owner chooses the executable, absent config, and host.
    prefix, endpoint = baseline._docker_prefix(), baseline._local_endpoint()
    if (not endpoint or len(prefix) != 5 or prefix[1] != '--config'
            or prefix[3:] != ('--host', endpoint)):
        raise ProvenanceBlocked(BACKEND_IDENTITY, 'frozen_local_docker_route_unavailable')
    capture = baseline._bounded_process((*prefix, 'version', '--format', '{{json .}}'),
        timeout_ms=8000, stdout_limit=65536)
    if (capture.status != 'sandbox_completed' or capture.exit_code != 0
            or not capture.termination_within_deadline):
        raise ProvenanceBlocked(BACKEND_VERSION, 'bounded_server_version_measurement_failed')
    return _backend_witness(capture.stdout, endpoint)


def assess_backend_freshness(descriptor, receipt):
    """Pure, fail-closed assessment of the frozen owner's continuity contract.

    Authenticating a snapshot does not keep its Docker daemon alive or pin
    subsequent connections to the same instance. Timestamps, repeated version
    equality, and endpoint equality cannot rule out replacement (including ABA).
    """
    _authenticate_pair(descriptor, receipt)
    return {'status': FRESHNESS,
        'reason': 'frozen_owner_has_no_backend_continuity_binding',
        'backend_freshness_result': 'unproven',
        'owner_defined_backend_continuity_mechanism': None,
        'sandbox_pair_authentication_proves_backend_continuity': False,
        'endpoint_version_equality_proves_backend_continuity': False,
        'timestamp_proves_backend_continuity': False,
        'attachment_issued': False}


def _effects(calls):
    return {'docker_calls': len(calls),
        'container_create_attempts': sum(r['command'] == 'create' for r in calls),
        'containers_created': sum(r['command'] == 'create' and r['completed']
            and r['exit_code'] == 0 for r in calls),
        'container_start_attempts': sum(r['command'] == 'start' for r in calls),
        'version_calls': sum(r['command'] == 'version' for r in calls),
        'image_inspect_calls': sum(r['command'] == 'image' and r['operation'] == 'inspect'
            for r in calls),
        'image_inventory_calls': sum(r['command'] == 'image' and r['operation'] == 'ls'
            for r in calls),
        'image_exports': sum(r['command'] == 'export' for r in calls),
        'image_pulls': sum(r['command'] == 'pull' for r in calls),
        'image_builds': sum(r['command'] == 'build' for r in calls)}


def replay():
    """No caller input; no Java/discovery/executor or attachment issuance path."""
    report = {'phase_id': PHASE_ID, 'schema_version': SCHEMA_VERSION,
        'status': UNRESOLVED, 'reason': 'fresh_sandbox2_not_authenticated',
        'sandbox_phase_id': 'RUNTIME.SANDBOX.2',
        'sandbox_schema_version': 'runtime_sandbox_2_v1',
        'sandbox_policy_sha256': POLICY_SHA256,
        'fresh_sandbox2_authenticated': False, 'exact_live_pair_revalidated': False,
        'sandbox_descriptor_fingerprint': None, 'sandbox_receipt_fingerprint': None,
        'image_identity': None, 'backend_identity': None, 'backend_version': None,
        'backend_endpoint_identity': None, 'measurement_method_id': METHOD_ID,
        'backend_measurement_completed': False,
        'backend_binding_result': 'unproven', 'backend_freshness_result': 'unproven',
        'attachment_issued': False, 'provenance_attachment_id': None,
        'provenance_attachment_fingerprint': None,
        'process_local_attachment_authentication': 'not_attempted_no_issuance',
        'copy_json_rejection': 'no_live_attachment_exists_to_copy_or_reconstruct',
        'negative_authentication_matrix': 'not_run_no_attachment_issued',
        'attachment_schema_validator_and_hmac_domain': 'not_created_freshness_stop',
        'exported_json_is_report_only': True,
        'cleanup_verified': None, 'remaining_phase_containers': None,
        'provenance_control_cleanup_verified': True,
        **dict.fromkeys(AUTHORITIES, False)}
    calls, scope = [], ['sandbox2_infrastructure']
    invoke = baseline._bounded_process

    def observed(argv, **kwargs):
        # Record only operation names, never arbitrary argv/output or secrets.
        row = {'scope': scope[0], 'command': argv[5] if len(argv) > 5 else '',
            'operation': argv[6] if len(argv) > 6 and argv[5] == 'image' else None,
            'completed': False, 'exit_code': None, 'control_reaped_and_pipes_closed': False}
        calls.append(row)
        capture = invoke(argv, **kwargs)
        # The frozen bounded-process implementation waits, joins readers, and
        # closes pipes before returning. Control failure cannot prove cleanup.
        row.update(completed=capture.status == 'sandbox_completed',
            exit_code=capture.exit_code,
            control_reaped_and_pipes_closed=capture.status in (
                'sandbox_completed', 'sandbox_timeout', 'sandbox_output_limit_exceeded'))
        return capture

    descriptor = receipt = live = None
    try:
        with patch.object(baseline, '_bounded_process', observed):
            descriptor, receipt, live = java1c._obtain_live_sandbox2()
            _authenticate_pair(descriptor, receipt)
            fingerprints = descriptor.fingerprint, receipt.fingerprint
            report.update(fresh_sandbox2_authenticated=True,
                sandbox_descriptor_fingerprint=fingerprints[0],
                sandbox_receipt_fingerprint=fingerprints[1], image_identity=descriptor.image_identity)
            if (live['cleanup_verified'] is not True
                    or live['temporary_workspace_removed'] is not True
                    or live['phase_container_count_after_teardown'] != 0):
                raise ProvenanceBlocked(UNRESOLVED, 'sandbox2_cleanup_not_verified')
            scope[0] = 'provenance_only'
            report.update(_measure_backend(), backend_measurement_completed=True)
            _authenticate_pair(descriptor, receipt)
            if (fingerprints != (descriptor.fingerprint, receipt.fingerprint)
                    or live['descriptor']['sandbox_descriptor_fingerprint'] != fingerprints[0]
                    or live['verification_receipt']['verification_receipt_fingerprint'] != fingerprints[1]
                    or receipt.evidence_sha256 != baseline._hash(live['stages'])):
                raise ProvenanceBlocked(BINDING, 'exact_live_sandbox2_pair_changed')
            report['exact_live_pair_revalidated'] = True
            report.update(assess_backend_freshness(descriptor, receipt))
            # Required stop: no attachment type, signer, registry, or validator
            # is implemented before an owner-defined continuity proof exists.
    except ProvenanceBlocked as error:
        report.update(status=error.status, reason=str(error))
    except (OSError, ValueError, TypeError, AttributeError, KeyError, subprocess.SubprocessError) as error:
        report.update(status=BINDING if descriptor is not None else UNRESOLVED,
            reason='live_provenance_preflight_failed',
            controller_error=type(error).__name__ + ': ' + str(error)[:250])
    report['docker_control_calls'] = calls
    report['sandbox2_infrastructure_effects'] = _effects(
        [r for r in calls if r['scope'] == 'sandbox2_infrastructure'])
    report['additional_provenance_effects'] = _effects(
        [r for r in calls if r['scope'] == 'provenance_only'])
    report['provenance_control_cleanup_verified'] = all(
        r['control_reaped_and_pipes_closed'] for r in calls if r['scope'] == 'provenance_only')
    report['prohibited_effects'] = dict.fromkeys(('java_source_projections', 'compile_executions',
        'java_fixture_executions', 'artifact_discovery_calls', 'artifact_exports', 'image_pulls',
        'image_builds', 'bank_executions', 'executor1r_retries', 'java1d_retries',
        'runtime_lease_consumptions', 'reflection_lease_consumptions', 'repository_runtime_writes',
        'apply_actions', 'outbound_network_calls', 'shell_calls', 'host_mounts'), 0)
    if live is not None:
        report['live_sandbox2'] = live
        report['remaining_phase_containers'] = live['phase_container_count_after_teardown']
        report['sandbox2_infrastructure_effects'].update(
            javac_version_count=live['javac_version_count'], java_version_count=live['java_version_count'],
            compile_count=live['compile_count'], java_fixture_count=live['jvm_fixture_count'],
            host_loopback_listener_sockets=2)
        report['cleanup_verified'] = (live['cleanup_verified'] is True
            and live['temporary_workspace_removed'] is True
            and report['remaining_phase_containers'] == 0
            and report['provenance_control_cleanup_verified'])
        if not report['cleanup_verified']:
            report.update(status=UNRESOLVED, reason='phase_cleanup_not_verified')
    return report
