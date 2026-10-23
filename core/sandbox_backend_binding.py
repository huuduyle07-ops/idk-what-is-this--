"""Evidence for the original JAVA.1 local route/Server.Version contract only.

One fixed PRE/version, fresh SANDBOX.2 ladder, POST/version bracket. Equality
does not identify a daemon process and cannot prove continuity or resist ABA.
Public validation and discovery comparison are pure and grant no authority.
"""
from copy import copy, deepcopy
from dataclasses import asdict, dataclass, field, fields, replace
import hmac
import json
import os
import secrets
import subprocess
from types import SimpleNamespace
from unittest.mock import patch

from core import candidate_runtime_sandbox as sandbox
from core import thread_compatible_runtime_sandbox as sandbox2

PHASE_ID = 'RUNTIME.SANDBOX.BIND.1'
SCHEMA_VERSION = 'runtime_sandbox_backend_binding_1_v1'
COMPLETE = 'RUNTIME_SANDBOX_BIND_1_COMPLETE_WITH_WARNINGS'
PRE_MEASUREMENT = 'RUNTIME_SANDBOX_BIND_1_BLOCKED_PRE_MEASUREMENT'
SANDBOX_AUTH = 'RUNTIME_SANDBOX_BIND_1_BLOCKED_SANDBOX_AUTH'
ROUTE_VERSION_CHANGED = 'RUNTIME_SANDBOX_BIND_1_BLOCKED_ROUTE_VERSION_CHANGED'
ATTACHMENT_AUTH = 'RUNTIME_SANDBOX_BIND_1_BLOCKED_ATTACHMENT_AUTH'
CLEANUP = 'RUNTIME_SANDBOX_BIND_1_BLOCKED_CLEANUP'
UNRESOLVED = 'RUNTIME_SANDBOX_BIND_1_BLOCKED_UNRESOLVED'
POLICY_SHA256 = '5a36bdf1676c4b0d7b4bef489f5e90b5c8fb201b5194be48baf61f4206a81f75'
BINDING_SEMANTICS = 'original_java1_route_and_server_version_v1'
METHOD_ID = 'frozen_local_docker_version_server_v1'
AUTHORITIES = ('runtime_authority', 'real_task_runtime_authority',
    'repository_write_authority', 'apply_authority', 'network_authority',
    'host_mount_authority', 'shell_authority', 'shell_available',
    'arbitrary_command_authority', 'compatibility_authority',
    'daemon_continuity_authority')
PROHIBITED_EFFECTS = ('java_source_compilations', 'java_fixture_executions',
    'artifact_discovery_calls', 'artifact_exports', 'java1c_invocations',
    'java1d_retries', 'executor1r_retries', 'bank_executions',
    'runtime_lease_consumptions', 'reflection_lease_consumptions',
    'repository_runtime_writes', 'apply_actions', 'outbound_network_calls',
    'shell_calls', 'host_mounts')
_SECRET = secrets.token_bytes(32)
# Strong object references are intentional: evidence has no consumption lifecycle.
# Each record also retains the immutable, originally signed bytes and exact pair.
_LIVE = {}


class BindingBlocked(ValueError):
    def __init__(self, status, reason):
        super().__init__(reason)
        self.status = status


def _payload(value):
    result = asdict(value)
    result.pop('_signature')
    return result


def _projection(value):
    return sandbox._json(_payload(value)).encode()


def _sign(value):
    return hmac.new(_SECRET, _projection(value), 'sha256').hexdigest()


@dataclass(frozen=True, slots=True)
class SandboxBackendBindingAttachment:
    sandbox_descriptor_fingerprint: str
    sandbox_receipt_fingerprint: str
    sandbox_receipt_evidence_sha256: str
    image_identity: str
    backend_identity_pre: str
    backend_version_pre: str
    backend_identity_post: str
    backend_version_post: str
    canonical_backend_identity: str
    canonical_backend_version: str
    attachment_id: str
    issuing_pid: int
    _signature: str = field(default='', repr=False, compare=False)
    phase_id: str = field(default=PHASE_ID, init=False)
    schema_version: str = field(default=SCHEMA_VERSION, init=False)
    sandbox_phase_id: str = field(default='RUNTIME.SANDBOX.2', init=False)
    sandbox_schema_version: str = field(default='runtime_sandbox_2_v1', init=False)
    sandbox_policy_sha256: str = field(default=POLICY_SHA256, init=False)
    binding_semantics: str = field(default=BINDING_SEMANTICS, init=False)
    measurement_method_id: str = field(default=METHOD_ID, init=False)
    route_version_bracket_equal: bool = field(default=True, init=False)
    daemon_instance_identity_available: bool = field(default=False, init=False)
    daemon_continuity_proven: bool = field(default=False, init=False)
    aba_resistance_proven: bool = field(default=False, init=False)
    sandbox_cleanup_verified: bool = field(default=True, init=False)
    pre_control_reaped_and_pipes_closed: bool = field(default=True, init=False)
    post_control_reaped_and_pipes_closed: bool = field(default=True, init=False)
    temporary_workspace_removed: bool = field(default=True, init=False)
    remaining_phase_containers: int = field(default=0, init=False)
    runtime_authority: bool = field(default=False, init=False)
    real_task_runtime_authority: bool = field(default=False, init=False)
    repository_write_authority: bool = field(default=False, init=False)
    apply_authority: bool = field(default=False, init=False)
    network_authority: bool = field(default=False, init=False)
    host_mount_authority: bool = field(default=False, init=False)
    shell_authority: bool = field(default=False, init=False)
    shell_available: bool = field(default=False, init=False)
    arbitrary_command_authority: bool = field(default=False, init=False)
    compatibility_authority: bool = field(default=False, init=False)
    daemon_continuity_authority: bool = field(default=False, init=False)

    @property
    def fingerprint(self):
        return sandbox._hash(_payload(self))

    def as_dict(self):
        """Report only: neither this projection nor a copy authenticates."""
        return {**_payload(self), 'attachment_fingerprint': self.fingerprint}


def _authenticate_pair(descriptor, receipt):
    sandbox2.validate_descriptor(descriptor, receipt)
    sandbox2.validate_policy_bytes(sandbox2.POLICY_BYTES)
    if (any(value.phase_id != 'RUNTIME.SANDBOX.2'
            or value.schema_version != 'runtime_sandbox_2_v1'
            or value.seccomp_policy_sha256 != POLICY_SHA256
            or value.image_identity != sandbox2.IMAGE
            or value.status != sandbox2.COMPLETE
            or any(getattr(value, key) is not False for key in sandbox2.AUTHORITIES)
            for value in (descriptor, receipt))
            or descriptor.eligible_for_java1_continuation is not True
            or receipt.cleanup_verified is not True
            or receipt.compatibility_classification != 'eligible_for_JAVA_1_continuation_only'
            or receipt.stage_results != tuple((m, sandbox2.PASSED) for m in sandbox2.LADDER)):
        raise ValueError('sandbox_bind1_exact_authenticated_sandbox2_required')


def _validate_attachment(attachment):
    if type(attachment) is not SandboxBackendBindingAttachment:
        raise ValueError('sandbox_bind1_live_attachment_required')
    record = _LIVE.get(attachment.attachment_id)
    if (record is None or record[0] is not attachment
            or type(attachment.issuing_pid) is not int
            or attachment.issuing_pid != os.getpid()):
        raise ValueError('sandbox_bind1_live_process_provenance_required')
    if (type(attachment._signature) is not str
            or not hmac.compare_digest(attachment._signature, _sign(attachment))
            or _projection(attachment) != record[3]):
        raise ValueError('sandbox_bind1_signature_or_projection_changed')
    if (attachment.phase_id != PHASE_ID or attachment.schema_version != SCHEMA_VERSION
            or attachment.sandbox_phase_id != 'RUNTIME.SANDBOX.2'
            or attachment.sandbox_schema_version != 'runtime_sandbox_2_v1'
            or attachment.sandbox_policy_sha256 != POLICY_SHA256
            or attachment.binding_semantics != BINDING_SEMANTICS
            or attachment.measurement_method_id != METHOD_ID
            or attachment.route_version_bracket_equal is not True
            or any(getattr(attachment, key) is not False for key in AUTHORITIES + (
                'daemon_instance_identity_available', 'daemon_continuity_proven',
                'aba_resistance_proven'))
            or any(getattr(attachment, key) is not True for key in (
                'sandbox_cleanup_verified', 'pre_control_reaped_and_pipes_closed',
                'post_control_reaped_and_pipes_closed', 'temporary_workspace_removed'))
            or type(attachment.remaining_phase_containers) is not int
            or attachment.remaining_phase_containers != 0):
        raise ValueError('sandbox_bind1_exact_semantics_required')
    if (any(type(getattr(attachment, key)) is not str for key in (
            'backend_identity_pre', 'backend_identity_post', 'backend_version_pre',
            'backend_version_post', 'canonical_backend_identity', 'canonical_backend_version'))
            or not attachment.canonical_backend_identity.startswith('local-docker:')
            or not attachment.canonical_backend_version
            or not (attachment.backend_identity_pre == attachment.backend_identity_post
                == attachment.canonical_backend_identity)
            or not (attachment.backend_version_pre == attachment.backend_version_post
                == attachment.canonical_backend_version)):
        raise ValueError('sandbox_bind1_exact_bracket_equality_required')
    return record


def validate_sandbox_backend_binding(attachment, sandbox_descriptor, sandbox_receipt):
    """Pure live provenance/pair validation; no Docker, mutation, or authority."""
    record = _validate_attachment(attachment)
    _authenticate_pair(sandbox_descriptor, sandbox_receipt)
    if (sandbox_descriptor is not record[1] or sandbox_receipt is not record[2]
            or sandbox_descriptor.fingerprint != attachment.sandbox_descriptor_fingerprint
            or sandbox_receipt.fingerprint != attachment.sandbox_receipt_fingerprint
            or sandbox_receipt.evidence_sha256 != attachment.sandbox_receipt_evidence_sha256
            or sandbox_descriptor.image_identity != attachment.image_identity
            or sandbox_receipt.image_identity != attachment.image_identity):
        raise ValueError('sandbox_bind1_exact_pair_required')
    return attachment


def sandbox_backend_binding_satisfies_java1_discovery(
        attachment, discovery_backend_identity, discovery_backend_version):
    """Compare original JAVA.1 values only; strings do not authenticate discovery.

    Future JAVA.1D must obtain both values from the exact original discovery
    owner. A true result grants no compatibility or daemon continuity authority.
    """
    try:
        record = _validate_attachment(attachment)
        validate_sandbox_backend_binding(attachment, record[1], record[2])
        return (type(discovery_backend_identity) is str
            and type(discovery_backend_version) is str
            and discovery_backend_identity == attachment.canonical_backend_identity
            and discovery_backend_version == attachment.canonical_backend_version)
    except (ValueError, TypeError, AttributeError, KeyError):
        return False


def _fixed_route():
    prefix, endpoint = sandbox._docker_prefix(), sandbox._local_endpoint()
    if (not endpoint or len(prefix) != 5 or prefix[1] != '--config'
            or prefix[3:] != ('--host', endpoint)):
        raise ValueError('frozen_local_docker_route_unavailable')
    return prefix, endpoint


def _backend_witness(raw, endpoint):
    value = json.loads(raw)
    if type(value) is not dict:
        raise ValueError('non_object_version_metadata')
    server = value.get('Server') or {}
    if type(server) is not dict or server.get('Os') != 'linux' or not server.get('Version'):
        raise ValueError('original_linux_server_version_required')
    return 'local-docker:' + endpoint, str(server['Version'])


def _measure_backend():
    prefix, endpoint = _fixed_route()
    capture = sandbox._bounded_process((*prefix, 'version', '--format', '{{json .}}'),
        timeout_ms=8000, stdout_limit=65536)
    if capture.status != 'sandbox_completed':
        raise BindingBlocked(CLEANUP, 'backend_control_completion_not_verified')
    if capture.exit_code != 0 or capture.termination_within_deadline is not True:
        raise ValueError('bounded_server_version_measurement_failed')
    return _backend_witness(capture.stdout, endpoint)


def _check_live_pair(descriptor, receipt, live):
    _authenticate_pair(descriptor, receipt)
    if (live['cleanup_verified'] is not True
            or live['temporary_workspace_removed'] is not True
            or type(live['phase_container_count_after_teardown']) is not int
            or live['phase_container_count_after_teardown'] != 0):
        raise BindingBlocked(CLEANUP, 'fresh_sandbox2_cleanup_not_verified')
    if (live['descriptor']['sandbox_descriptor_fingerprint'] != descriptor.fingerprint
            or live['verification_receipt']['verification_receipt_fingerprint'] != receipt.fingerprint
            or receipt.evidence_sha256 != sandbox._hash(live['stages'])):
        raise ValueError('fresh_sandbox2_live_evidence_changed')


def _effects(calls):
    return {'docker_calls': len(calls),
        'version_calls': sum(r['command'] == 'version' for r in calls),
        'container_create_attempts': sum(r['command'] == 'create' for r in calls),
        'containers_created': sum(r['command'] == 'create' and r['completed']
            and r['exit_code'] == 0 for r in calls),
        'container_start_attempts': sum(r['command'] == 'start' for r in calls),
        'image_inspect_calls': sum(r['command'] == 'image' and r['operation'] == 'inspect' for r in calls),
        'image_inventory_calls': sum(r['command'] == 'image' and r['operation'] == 'ls' for r in calls),
        'image_exports': sum(r['command'] == 'export' for r in calls),
        'image_pulls': sum(r['command'] == 'pull' for r in calls),
        'image_builds': sum(r['command'] == 'build' for r in calls)}


def _run():
    report = {'phase_id': PHASE_ID, 'schema_version': SCHEMA_VERSION,
        'status': UNRESOLVED, 'reason': 'bracket_not_completed',
        'identity_semantics': '"local-docker:" + sandbox._local_endpoint()',
        'version_semantics': 'str(server["Version"]); dict Server, Os == "linux", truthy Version',
        'comparison_semantics': 'exact Python string equality; no normalization',
        'binding_semantics': BINDING_SEMANTICS, 'measurement_method_id': METHOD_ID,
        'sandbox_phase_id': 'RUNTIME.SANDBOX.2', 'sandbox_schema_version': 'runtime_sandbox_2_v1',
        'sandbox_policy_sha256': POLICY_SHA256,
        **dict.fromkeys(('backend_identity_pre', 'backend_version_pre',
            'backend_identity_post', 'backend_version_post', 'canonical_backend_identity',
            'canonical_backend_version', 'sandbox_descriptor_fingerprint',
            'sandbox_receipt_fingerprint', 'sandbox_receipt_evidence_sha256', 'image_identity',
            'attachment_id', 'attachment_fingerprint', 'remaining_phase_containers'), None),
        'route_version_bracket_equal': False, 'daemon_instance_identity_available': False,
        'daemon_continuity_proven': False, 'aba_resistance_proven': False,
        'fresh_sandbox2_invocations': 0, 'fresh_sandbox2_authenticated': False,
        'exact_live_pair_revalidated': False, 'attachment_issued': False,
        'attachment_authentication': False, 'pair_binding': False,
        'exported_json_is_report_only': True, 'cleanup_verified': False,
        **dict.fromkeys(AUTHORITIES, False),
        'prohibited_effects': dict.fromkeys(PROHIBITED_EFFECTS, 0)}
    calls, scope = [], ['binding_pre']
    invoke = sandbox._bounded_process

    def observed(argv, **kwargs):
        row = {'scope': scope[0], 'command': argv[5] if len(argv) > 5 else '',
            'operation': argv[6] if len(argv) > 6 and argv[5] == 'image' else None,
            'completed': False, 'exit_code': None, 'control_reaped_and_pipes_closed': False}
        calls.append(row)
        capture = invoke(argv, **kwargs)
        row.update(completed=capture.status == 'sandbox_completed', exit_code=capture.exit_code,
            control_reaped_and_pipes_closed=capture.status in (
                'sandbox_completed', 'sandbox_timeout', 'sandbox_output_limit_exceeded'))
        return capture

    attachment = descriptor = receipt = live = None
    blocked_status = PRE_MEASUREMENT
    try:
        with patch.object(sandbox, '_bounded_process', observed):
            pre = _measure_backend()
            report.update(backend_identity_pre=pre[0], backend_version_pre=pre[1])
            scope[0], blocked_status = 'sandbox2_infrastructure', SANDBOX_AUTH
            report['fresh_sandbox2_invocations'] = 1
            live = sandbox2.replay()
            report['live_sandbox2'] = live
            if (live['cleanup_verified'] is not True
                    or live['temporary_workspace_removed'] is not True
                    or type(live['phase_container_count_after_teardown']) is not int
                    or live['phase_container_count_after_teardown'] != 0):
                raise BindingBlocked(CLEANUP, 'fresh_sandbox2_cleanup_not_verified')
            # The frozen public replay exports a report. Its existing issuer
            # reconstructs the exact pair from THIS invocation, never a file.
            descriptor, receipt = sandbox2._evidence_pair(live)
            _check_live_pair(descriptor, receipt, live)
            report.update(fresh_sandbox2_authenticated=True,
                sandbox_descriptor_fingerprint=descriptor.fingerprint,
                sandbox_receipt_fingerprint=receipt.fingerprint,
                sandbox_receipt_evidence_sha256=receipt.evidence_sha256,
                image_identity=descriptor.image_identity)
            scope[0], blocked_status = 'binding_post', UNRESOLVED
            post = _measure_backend()
            report.update(backend_identity_post=post[0], backend_version_post=post[1])
            blocked_status = SANDBOX_AUTH
            _check_live_pair(descriptor, receipt, live)
            report['exact_live_pair_revalidated'] = True
            if pre != post:
                raise BindingBlocked(ROUTE_VERSION_CHANGED, 'original_route_or_server_version_changed')
            report.update(route_version_bracket_equal=True,
                canonical_backend_identity=pre[0], canonical_backend_version=pre[1])
            binding_calls = [r for r in calls if r['scope'].startswith('binding_')]
            if (len(binding_calls) != 2 or any(r['command'] != 'version'
                    or not r['control_reaped_and_pipes_closed'] for r in binding_calls)):
                raise BindingBlocked(CLEANUP, 'two_reaped_version_controls_required')
            blocked_status = ATTACHMENT_AUTH
            unsigned = SandboxBackendBindingAttachment(descriptor.fingerprint, receipt.fingerprint,
                receipt.evidence_sha256, descriptor.image_identity, *pre, *post, *pre,
                secrets.token_hex(32), os.getpid())
            attachment = replace(unsigned, _signature=_sign(unsigned))
            _LIVE[attachment.attachment_id] = (attachment, descriptor, receipt, _projection(attachment))
            validate_sandbox_backend_binding(attachment, descriptor, receipt)
            report.update(status=COMPLETE, reason='original_java1_route_and_version_bracket_equal_only',
                attachment_issued=True, attachment_id=attachment.attachment_id,
                attachment_fingerprint=attachment.fingerprint,
                attachment_authentication=True, pair_binding=True, attachment=attachment.as_dict())
    except BindingBlocked as error:
        report.update(status=error.status, reason=str(error))
    except (OSError, ValueError, TypeError, AttributeError, KeyError, subprocess.SubprocessError) as error:
        report.update(status=blocked_status, reason='bounded_backend_binding_failed',
            controller_error=type(error).__name__ + ': ' + str(error)[:250])
    if report['status'] != COMPLETE and attachment is not None:
        _LIVE.pop(attachment.attachment_id, None)
        attachment = None
    report['docker_control_calls'] = calls
    report['binding_only_effects'] = _effects([r for r in calls if r['scope'].startswith('binding_')])
    report['sandbox2_infrastructure_effects'] = _effects([r for r in calls if r['scope'] == 'sandbox2_infrastructure'])
    for label in ('pre', 'post'):
        rows = [r for r in calls if r['scope'] == 'binding_' + label]
        report[label + '_control_reaped_and_pipes_closed'] = (len(rows) == 1
            and rows[0]['control_reaped_and_pipes_closed'])
    if live is not None:
        report['remaining_phase_containers'] = live.get('phase_container_count_after_teardown')
        report['temporary_workspace_removed'] = live.get('temporary_workspace_removed') is True
        report['sandbox_cleanup_verified'] = live.get('cleanup_verified') is True
        report['sandbox2_infrastructure_effects'].update(
            javac_version_count=live.get('javac_version_count'),
            java_version_count=live.get('java_version_count'),
            compile_count=live.get('compile_count'), java_fixture_count=live.get('jvm_fixture_count'))
        report['cleanup_verified'] = (report['sandbox_cleanup_verified']
            and report['temporary_workspace_removed'] and report['remaining_phase_containers'] == 0
            and all(r['control_reaped_and_pipes_closed'] for r in calls if r['scope'].startswith('binding_')))
    return attachment, descriptor, receipt, report


def issue_sandbox_backend_binding():
    """Obtain values and one fresh pair internally; no caller-selected inputs."""
    attachment, descriptor, receipt, report = _run()
    if report['status'] != COMPLETE:
        raise BindingBlocked(report['status'], report['reason'])
    return attachment, descriptor, receipt


def _negative_matrix(attachment, descriptor, receipt):
    """Controlled in-process tamper/copy checks; restored before final validation."""
    results = {}

    def rejects(name, candidate, sd=descriptor, sr=receipt):
        try:
            validate_sandbox_backend_binding(candidate, sd, sr)
        except (ValueError, TypeError, AttributeError, KeyError):
            results[name] = True
        else:
            results[name] = False

    for name, candidate in (('copy', copy(attachment)), ('deepcopy', deepcopy(attachment)),
            ('dataclasses_replace', replace(attachment)), ('exported_json', attachment.as_dict()),
            ('wrapper', SimpleNamespace(**attachment.as_dict()))):
        rejects(name, candidate)
    data = json.loads(json.dumps(attachment.as_dict()))
    rejects('json_reconstruction', SandboxBackendBindingAttachment(**{
        f.name: data[f.name] for f in fields(attachment) if f.init and f.name != '_signature'}))
    class Subclass(SandboxBackendBindingAttachment):
        pass
    rejects('subclass', Subclass(**{f.name: getattr(attachment, f.name)
        for f in fields(attachment) if f.init}))
    rejects('wrong_descriptor', attachment, replace(descriptor, verification_receipt_fingerprint='0' * 64))
    rejects('same_descriptor_different_receipt', attachment, descriptor,
        replace(receipt, evidence_sha256='0' * 64))
    rejects('same_receipt_different_descriptor', attachment, deepcopy(descriptor), receipt)
    rejects('wrong_receipt', attachment, descriptor, deepcopy(receipt))
    with patch.object(os, 'getpid', return_value=attachment.issuing_pid + 1):
        rejects('wrong_process', attachment)
    changes = {'_signature': '0' * 64,
        **dict.fromkeys(('backend_identity_pre', 'backend_identity_post',
            'backend_version_pre', 'backend_version_post', 'canonical_backend_identity',
            'canonical_backend_version', 'sandbox_descriptor_fingerprint',
            'sandbox_receipt_fingerprint', 'sandbox_receipt_evidence_sha256',
            'sandbox_policy_sha256', 'image_identity', 'phase_id', 'schema_version',
            'sandbox_phase_id', 'sandbox_schema_version', 'binding_semantics',
            'measurement_method_id'), 'changed'),
        'route_version_bracket_equal': False,
        'daemon_continuity_proven': True, 'aba_resistance_proven': True,
        'daemon_instance_identity_available': True,
        **dict.fromkeys(AUTHORITIES, True)}
    for key, value in changes.items():
        original = getattr(attachment, key)
        try:
            object.__setattr__(attachment, key, value)
            rejects('tampered_' + key, attachment)
        finally:
            object.__setattr__(attachment, key, original)
    compare = sandbox_backend_binding_satisfies_java1_discovery
    results['discovery_wrong_identity'] = not compare(attachment, 'caller-backend-alias', attachment.canonical_backend_version)
    results['discovery_wrong_version'] = not compare(attachment, attachment.canonical_backend_identity, 'wrong')
    results['context_name_substitution'] = not compare(attachment, 'desktop-linux', attachment.canonical_backend_version)
    for name, metadata in (
            ('client_version_substitution', {'Client': {'Os': 'linux', 'Version': '1'}}),
            ('api_version_substitution', {'Server': {'Os': 'linux', 'ApiVersion': '1'}})):
        try:
            _backend_witness(json.dumps(metadata), 'controlled-local-endpoint')
        except ValueError:
            results[name] = True
        else:
            results[name] = False
    validate_sandbox_backend_binding(attachment, descriptor, receipt)
    return results


def replay():
    """Record one strict bracket proof, pure negative controls, then stop."""
    attachment, descriptor, receipt, report = _run()
    if report['status'] == COMPLETE:
        try:
            report['negative_authentication_matrix'] = _negative_matrix(attachment, descriptor, receipt)
            report['copy_json_process_hmac_negatives_rejected'] = all(report['negative_authentication_matrix'].values())
            report['controlled_discovery_comparison'] = sandbox_backend_binding_satisfies_java1_discovery(
                attachment, attachment.canonical_backend_identity, attachment.canonical_backend_version)
            report['discovery_comparison_is_authenticated_discovery_evidence'] = False
            if not report['copy_json_process_hmac_negatives_rejected'] or not report['controlled_discovery_comparison']:
                raise ValueError('negative_control_or_comparison_failed')
        except (ValueError, TypeError, AttributeError, KeyError) as error:
            report.update(status=ATTACHMENT_AUTH, reason=str(error))
    return report
