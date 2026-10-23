"""SANDBOX.2 additive policy epoch and fixed verification ladder.

Receipts authenticate infrastructure measurements in this process only. They
are never a SANDBOX.1 adapter, task authorization, or executor capability.
"""
from copy import deepcopy
from dataclasses import asdict, dataclass, field, replace
from hashlib import sha256
import hmac
import json
from pathlib import Path
import secrets
import select
import socket
import tempfile

from core import candidate_runtime_sandbox as baseline
from core import sandboxed_java_capture_recovery as recovery
from core import thread_compatible_runtime_sandbox_probe as probe

PHASE_ID = 'RUNTIME.SANDBOX.2'
SCHEMA_VERSION = 'runtime_sandbox_2_v1'
COMPLETE = 'RUNTIME_SANDBOX_2_COMPLETE_WITH_WARNINGS'
FALLBACK_BLOCKED = 'RUNTIME_SANDBOX_2_BLOCKED_THREAD_FALLBACK_UNAVAILABLE'
CLONE_BLOCKED = 'RUNTIME_SANDBOX_2_BLOCKED_LEGACY_CLONE_POLICY'
CONTAINMENT_BLOCKED = 'RUNTIME_SANDBOX_2_BLOCKED_CONTAINMENT_REGRESSION'
JAVA_BLOCKED = 'RUNTIME_SANDBOX_2_BLOCKED_JAVA_INCOMPATIBLE'
UNRESOLVED = 'RUNTIME_SANDBOX_2_BLOCKED_UNRESOLVED'
PASSED = 'stage_passed'
IMAGE = recovery.IMAGE
BASELINE_POLICY_SHA256 = recovery.SECCOMP_HASH
BASELINE_DESCRIPTOR = recovery.SANDBOX_DESCRIPTOR
BASELINE_RECEIPT = recovery.SANDBOX_RECEIPT
POLICY = deepcopy(baseline._SECCOMP)
POLICY['syscalls'][0]['names'].remove('clone3')
POLICY['syscalls'].append({'names': ['clone3'], 'action': 'SCMP_ACT_ERRNO', 'errnoRet': 38})
POLICY_BYTES = baseline._json(POLICY).encode()
POLICY_SHA256 = sha256(POLICY_BYTES).hexdigest()
POLICY_PATH = Path(__file__).resolve().parents[1] / 'docs/roadmap/RUNTIME_SANDBOX_2_SECCOMP.json'
LADDER = ('clone3', 'pthread', 'boundary', 'descendant', 'timeout', 'stdout', 'stderr',
    'tmp', 'controller', 'javac_version', 'java_version')
AUTHORITIES = ('runtime_authority', 'repository_write_authority', 'apply_authority',
    'shell_available', 'arbitrary_command_authority', 'host_mount_authority', 'network_authority')
_SECRET = secrets.token_bytes(32)


def policy_diff():
    return {'baseline_profile': baseline.SCHEMA_VERSION, 'candidate_profile': SCHEMA_VERSION,
        'baseline_sha256': BASELINE_POLICY_SHA256, 'candidate_sha256': POLICY_SHA256,
        'semantic_changes': [{'syscall': 'clone3', 'old_action': 'SCMP_ACT_ERRNO',
            'old_errno': 1, 'new_action': 'SCMP_ACT_ERRNO', 'new_errno': 38,
            'execution_allowed_before': False, 'execution_allowed_after': False}],
        'legacy_clone_rules_unchanged': True,
        'legacy_clone_policy': 'allow_except_seven_forbidden_namespace_bits',
        'thread_only_clone_enforced': False}


def validate_policy_bytes(raw):
    if baseline._hash(baseline._SECCOMP) != BASELINE_POLICY_SHA256:
        raise ValueError('historical_policy_identity_changed')
    expected = deepcopy(baseline._SECCOMP)
    expected['syscalls'][0]['names'].remove('clone3')
    expected['syscalls'].append({'names': ['clone3'], 'action': 'SCMP_ACT_ERRNO', 'errnoRet': 38})
    if (type(raw) is not bytes or raw != baseline._json(expected).encode()
            or sha256(raw).hexdigest() != POLICY_SHA256):
        raise ValueError('exact_sandbox2_canonical_policy_required')
    return True


def _payload(value):
    data = asdict(value)
    data.pop('_signature')
    return data


def _sign(value):
    return hmac.new(_SECRET, baseline._json(_payload(value)).encode(), 'sha256').hexdigest()


@dataclass(frozen=True, slots=True)
class ThreadCompatibleSandboxReceipt:
    status: str
    stage_results: tuple[tuple[str, str], ...]
    evidence_sha256: str
    cleanup_verified: bool
    compatibility_classification: str
    _signature: str = field(default='', repr=False, compare=False)
    phase_id: str = field(default=PHASE_ID, init=False)
    schema_version: str = field(default=SCHEMA_VERSION, init=False)
    seccomp_policy_sha256: str = field(default=POLICY_SHA256, init=False)
    baseline_seccomp_policy_sha256: str = field(default=BASELINE_POLICY_SHA256, init=False)
    baseline_descriptor_fingerprint: str = field(default=BASELINE_DESCRIPTOR, init=False)
    baseline_receipt_fingerprint: str = field(default=BASELINE_RECEIPT, init=False)
    image_identity: str = field(default=IMAGE, init=False)
    authority: str = field(default='infrastructure_compatibility_measurement_only', init=False)
    runtime_authority: bool = field(default=False, init=False)
    repository_write_authority: bool = field(default=False, init=False)
    apply_authority: bool = field(default=False, init=False)
    shell_available: bool = field(default=False, init=False)
    arbitrary_command_authority: bool = field(default=False, init=False)
    host_mount_authority: bool = field(default=False, init=False)
    network_authority: bool = field(default=False, init=False)

    @property
    def fingerprint(self): return baseline._hash(_payload(self))

    def as_dict(self): return {**_payload(self), 'verification_receipt_fingerprint': self.fingerprint}


@dataclass(frozen=True, slots=True)
class ThreadCompatibleSandboxDescriptor:
    verification_receipt_fingerprint: str
    status: str
    eligible_for_java1_continuation: bool
    _signature: str = field(default='', repr=False, compare=False)
    phase_id: str = field(default=PHASE_ID, init=False)
    schema_version: str = field(default=SCHEMA_VERSION, init=False)
    seccomp_policy_sha256: str = field(default=POLICY_SHA256, init=False)
    image_identity: str = field(default=IMAGE, init=False)
    baseline_descriptor_fingerprint: str = field(default=BASELINE_DESCRIPTOR, init=False)
    relationship: str = field(default='additive_epoch_preserving_SANDBOX_1_history', init=False)
    runtime_authority: bool = field(default=False, init=False)
    repository_write_authority: bool = field(default=False, init=False)
    apply_authority: bool = field(default=False, init=False)
    shell_available: bool = field(default=False, init=False)
    arbitrary_command_authority: bool = field(default=False, init=False)
    host_mount_authority: bool = field(default=False, init=False)
    network_authority: bool = field(default=False, init=False)

    @property
    def fingerprint(self): return baseline._hash(_payload(self))

    def as_dict(self): return {**_payload(self), 'sandbox_descriptor_fingerprint': self.fingerprint}


def validate_receipt(receipt):
    if (type(receipt) is not ThreadCompatibleSandboxReceipt
            or not hmac.compare_digest(receipt._signature, _sign(receipt))):
        raise ValueError('sandbox2_receipt_unauthenticated')
    return receipt


def validate_descriptor(descriptor, receipt):
    validate_receipt(receipt)
    if (type(descriptor) is not ThreadCompatibleSandboxDescriptor
            or not hmac.compare_digest(descriptor._signature, _sign(descriptor))
            or descriptor.verification_receipt_fingerprint != receipt.fingerprint
            or descriptor.status != receipt.status
            or descriptor.eligible_for_java1_continuation != (receipt.status == COMPLETE)):
        raise ValueError('sandbox2_descriptor_unauthenticated')
    return descriptor


def _evidence_pair(result):
    status = result['status']
    if status == COMPLETE and (not result['cleanup_verified']
            or tuple(s['mode'] for s in result['stages']) != LADDER
            or any(s['verdict'] != PASSED for s in result['stages'])):
        raise ValueError('sandbox2_completion_evidence_incomplete')
    receipt = ThreadCompatibleSandboxReceipt(status,
        tuple((s['mode'], s['verdict']) for s in result['stages']),
        baseline._hash(result['stages']), result['cleanup_verified'],
        'eligible_for_JAVA_1_continuation_only' if status == COMPLETE else 'blocked_no_java_capability')
    receipt = replace(receipt, _signature=_sign(receipt))
    descriptor = ThreadCompatibleSandboxDescriptor(receipt.fingerprint, status, status == COMPLETE)
    descriptor = replace(descriptor, _signature=_sign(descriptor))
    validate_descriptor(descriptor, receipt)
    return descriptor, receipt


def safe_configuration(config, mode):
    """Inspect the new policy first; delegate every other frozen config check."""
    try:
        host, settings = config['HostConfig'], config['Config']
        expected_cmd = (['-I', '-S', '-B', '-c', baseline.PROBE_SOURCE, mode]
            if mode in baseline.PROBE_IDS else ['-I', '-S', '-B', '-c', probe.source_for(mode)])
        if (settings['Cmd'] != expected_cmd or set(host['SecurityOpt']) !=
                {'no-new-privileges=true', 'seccomp=' + POLICY_BYTES.decode()}): return False
        normalized = {**config, 'HostConfig': {**host,
            'SecurityOpt': ['no-new-privileges=true', 'seccomp=' + baseline._json(baseline._SECCOMP)]},
            'Config': {**settings, 'Cmd': ['-I', '-S', '-B', '-c', baseline.PROBE_SOURCE, 'boundary']}}
        return baseline._safe_configuration(normalized, IMAGE)
    except (KeyError, TypeError, ValueError): return False


def _state_safe(state):
    return (state.get('uid') == state.get('gid') == 65534
        and state.get('pid') == 1 and state.get('processes') == [1]
        and state.get('capabilities_zero') is True and state.get('no_new_privileges') is True
        and state.get('pids_max') == '128' and state.get('memory_max') == '134217728')


def classify(mode, capture, facts, cleanup, *, host_unchanged=True, endpoint_quiet=True):
    """Fail closed before the next fixed stage. No runtime receipt is issued."""
    if not cleanup: return CONTAINMENT_BLOCKED
    if mode in baseline.PROBE_IDS:
        passed = set(baseline._facts_passed(mode, capture, facts, cleanup, host_unchanged, endpoint_quiet))
        required = {'boundary': {'exact_source_and_classpath', 'fixed_executable_and_arguments',
            'ephemeral_working_directory', 'candidate_filesystem_isolation',
            'candidate_network_isolation', 'candidate_environment_isolation'},
            'descendant': {'candidate_extra_process_prevention', 'all_child_process_cleanup'},
            'timeout': {'hard_wall_clock_timeout', 'all_child_process_cleanup'},
            'stdout': {'hard_stdout_stderr_bounds'}, 'stderr': {'hard_stdout_stderr_bounds'}}[mode]
        return PASSED if (required <= passed and capture.termination_within_deadline) else CONTAINMENT_BLOCKED
    if (capture.status != 'sandbox_completed' or capture.exit_code != 0
            or not capture.termination_within_deadline): return UNRESOLVED
    try:
        if mode == 'clone3':
            return PASSED if (facts['clone3'] == {'result': -1, 'errno': 38}
                and _state_safe(facts['before']) and _state_safe(facts['after'])
                and facts['before']['os_threads'] == facts['after']['os_threads'] == 1) else UNRESOLVED
        if mode == 'pthread':
            if any(r.get(op) != {'result': -1, 'errno': 1}
                    for r in facts['namespace_probes'].values() for op in ('clone', 'unshare', 'setns')):
                return CONTAINMENT_BLOCKED
            if set(facts['namespace_probes']) != set(probe.NAMESPACE_FLAGS): return UNRESOLVED
            threads = facts['pthreads']
            if not threads: return UNRESOLVED
            if threads[0]['create_return_code'] != 0:
                # An EPERM return alone does not identify the denied syscall.
                # Do not blame legacy clone without syscall-specific evidence.
                return FALLBACK_BLOCKED
            if (len(threads) != 2 or facts['witness_filter']['result'] != 0
                    or facts['witness_rejects_other_flags'] != {'result': -1, 'errno': 1}
                    or facts['witness_flags'] != probe.PTHREAD_CLONE_FLAGS): return UNRESOLVED
            for record in threads:
                before, during, after = record['before'], record['thread'], record['after']
                if (record['create_return_code'] != 0 or record['join_return_code'] != 0
                        or not all(_state_safe(s) for s in (before, during, after))
                        or before['os_threads'] != 1 or after['os_threads'] != 1
                        or during['os_threads'] != 2 or during['tid'] == during['pid']
                        or before['namespaces'] != during['namespaces'] or before['namespaces'] != after['namespaces']
                        or before['cgroup'] != during['cgroup'] or before['cgroup'] != after['cgroup']
                        or before['ppid'] != during['ppid'] or record['socket_errno'] != 1):
                    return CONTAINMENT_BLOCKED
            return PASSED if (_state_safe(facts['after']) and facts['after']['os_threads'] == 1) else CONTAINMENT_BLOCKED
        if mode == 'tmp':
            return PASSED if (facts['writable'] == ['/work', '/tmp'] and facts['removed'] == [True, True]
                and facts['uid'] == facts['gid'] == 65534) else CONTAINMENT_BLOCKED
        if mode in ('controller', 'javac_version', 'java_version'):
            adjusted = deepcopy(facts)
            gate_mode = 'non_java' if mode == 'controller' else 'javac_version'
            if mode == 'java_version':
                stage = adjusted['stages']['javac_identity']
                if stage['argv'] != [probe.JAVA_PATH, '-version']: return UNRESOLVED
                stage['argv'] = [probe.single.JAVAC_PATH, '-version']
            verdict = recovery.classify_gate(gate_mode, capture, adjusted, cleanup)
            if verdict == recovery.JAVA_FAILURE: return JAVA_BLOCKED
            if facts.get('work_files_after_cleanup') != []: return CONTAINMENT_BLOCKED
            if verdict in (recovery.RECOVERED, recovery.NON_JAVA_PASS): return PASSED
            return CONTAINMENT_BLOCKED if verdict == recovery.CLEANUP_FAILURE else UNRESOLVED
    except (KeyError, TypeError, ValueError): return UNRESOLVED
    return UNRESOLVED


def invoke(prefix, profile, mode, sentinel, port):
    if mode not in LADDER: raise ValueError('fixed_sandbox2_probe_required')
    original = mode in baseline.PROBE_IDS
    spec = baseline.synthetic_probe_spec(mode) if original else None
    source = baseline.PROBE_SOURCE if original else probe.source_for(mode)
    cmd = ['-I', '-S', '-B', '-c', source, *([mode] if original else [])]
    name = 'runtime-sandbox2-' + secrets.token_hex(12)
    ctl = lambda *args: baseline._bounded_process((*prefix, *args), timeout_ms=8000, stdout_limit=65536)
    capture, facts, cleanup = baseline._Capture('sandbox_launch_failed', None, b'', b'', False), {}, False
    try:
        created = ctl('create', '--name', name, '--pull', 'never', '--interactive',
            '--hostname', 'runtime-sandbox1', '--network', 'none', '--read-only',
            '--user', '65534:65534', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges=true', '--security-opt', 'seccomp=' + str(profile),
            '--cgroupns', 'private', '--ipc', 'none', '--pids-limit', '128',
            '--memory', '128m', '--cpus', '1', '--log-driver', 'none',
            '--tmpfs', '/work:rw,nosuid,nodev,size=32m,mode=1777',
            '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=16m,mode=1777', '--workdir', '/work',
            *(token for key, value in baseline._WORKLOAD_ENVIRONMENT.items()
                for token in ('--env', key + '=' + value)),
            '--entrypoint', '/usr/local/bin/python', IMAGE, *cmd)
        if created.status != 'sandbox_completed' or created.exit_code != 0:
            raise ValueError('sandbox2_create_failed:' + created.stderr.decode(errors='replace')[:200])
        observed = ctl('inspect', name, '--format', '{{json .}}')
        if (observed.status != 'sandbox_completed' or observed.exit_code != 0
                or not safe_configuration(json.loads(observed.stdout), mode)):
            raise ValueError('sandbox2_inspected_configuration_rejected')
        normalized = str(sentinel).replace('\\', '/').replace(':', '').lstrip('/')
        normalized = normalized[0].lower() + normalized[1:]
        host_paths = ['/run/desktop/mnt/host/' + normalized, '/host_mnt/' + normalized]
        if baseline.os.name != 'nt': host_paths = [str(sentinel)]
        import base64
        payload = (baseline._json({'inputs': [{'path': 'projection.txt',
            'bytes': base64.b64encode(baseline._FIXTURE).decode()}],
            'host_paths': host_paths, 'port': port}) + '\n').encode() if original else b''
        def stop():
            killed = ctl('kill', name)
            stopped = ctl('inspect', name, '--format', '{{.State.Running}}')
            return (killed.status == 'sandbox_completed' and killed.exit_code == 0
                and stopped.status == 'sandbox_completed' and stopped.stdout.strip() == b'false')
        capture = baseline._bounded_process((*prefix, 'start', '--attach', '--interactive', name),
            input_bytes=payload, timeout_ms=spec.timeout_ms if original else 10000,
            stdout_limit=8192, stderr_limit=8192, on_abort=stop,
            abort_after_ms=5000 if not original or mode == 'timeout' else None)
        if mode not in ('stdout', 'stderr'):
            try:
                parsed = json.loads(capture.stdout)
                facts = parsed.get('facts', parsed)
            except (ValueError, AttributeError): pass
    except (OSError, ValueError) as error:
        facts['controller_error'] = type(error).__name__ + ': ' + str(error)[:250]
    finally:
        ctl('kill', name)
        removed = ctl('rm', '--force', '--volumes', name)
        absent = ctl('inspect', name, '--format', '{{.State.Running}}')
        cleanup = (removed.status == 'sandbox_completed' and removed.exit_code == 0
            and absent.status == 'sandbox_completed' and absent.exit_code != 0
            and any(s in absent.stderr.lower() for s in (b'no such object', b'no such container')))
    return capture, facts, cleanup


def replay():
    result = {'phase_id': PHASE_ID, 'profile_id': SCHEMA_VERSION, 'status': UNRESOLVED,
        **dict.fromkeys(AUTHORITIES, False), 'policy_sha256': POLICY_SHA256,
        'policy_diff': policy_diff(), 'image_identity': IMAGE, 'stages': [],
        'runtime_policy_authorizations_consumed': 0, 'bank_execution_count': 0,
        'behavioral_execution_count': 0, 'reflection_count': 0, 'console_count': 0,
        'compile_count': 0, 'jvm_fixture_count': 0, 'javac_version_count': 0,
        'java_version_count': 0, 'executor_refreshed_or_resumed': False,
        'java1_completed': False, 'cleanup_verified': False}
    prefix = baseline._docker_prefix()
    try:
        validate_policy_bytes(POLICY_PATH.read_bytes())
        image = baseline._bounded_process((*prefix, 'image', 'inspect', IMAGE, '--format', '{{json .}}'),
            timeout_ms=8000, stdout_limit=65536)
        metadata = json.loads(image.stdout) if image.status == 'sandbox_completed' and image.exit_code == 0 else {}
        if (not prefix or metadata.get('Id') != IMAGE or metadata.get('Os') != 'linux'
                or metadata.get('Architecture') != 'amd64' or metadata.get('Config', {}).get('Volumes')):
            raise ValueError('exact_local_java_image_required')
        with tempfile.TemporaryDirectory(prefix='runtime-sandbox2-') as root:
            profile, sentinel = Path(root) / 'seccomp.json', Path(root) / 'host-sentinel.txt'
            profile.write_bytes(POLICY_BYTES)
            sentinel.write_bytes(b'phase-owned-host-sentinel')
            with socket.socket() as endpoint, socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as dns:
                endpoint.bind(('127.0.0.1', 0))
                endpoint.listen(1)
                port = endpoint.getsockname()[1]
                dns.bind(('127.0.0.1', port))
                for mode in LADDER:
                    capture, facts, cleanup = invoke(prefix, profile, mode, sentinel, port)
                    unchanged = sentinel.read_bytes() == b'phase-owned-host-sentinel'
                    quiet = not select.select([endpoint, dns], [], [], 0)[0]
                    verdict = classify(mode, capture, facts, cleanup,
                        host_unchanged=unchanged, endpoint_quiet=quiet)
                    result['stages'].append({'mode': mode, 'verdict': verdict, 'facts': facts,
                        'capture_status': capture.status, 'exit_code': capture.exit_code,
                        'stdout_size': len(capture.stdout), 'stderr_size': len(capture.stderr),
                        'outer_stderr': capture.stderr.decode(errors='replace')[:500],
                        'cleanup_verified': cleanup, 'host_sentinel_unchanged': unchanged,
                        'host_endpoints_quiet': quiet, 'termination_verified': capture.termination_verified,
                        'termination_within_deadline': capture.termination_within_deadline,
                        'measured_termination_ms': capture.measured_termination_ms})
                    if mode in ('javac_version', 'java_version'):
                        result[mode.replace('_version', '_version_count')] = facts.get('toolchain_launch_count', 0)
                    if not unchanged or not quiet: verdict = CONTAINMENT_BLOCKED
                    if verdict != PASSED:
                        result['stages'][-1]['verdict'] = result['status'] = verdict
                        break
                else: result['status'] = COMPLETE
        result['temporary_workspace_removed'] = not Path(root).exists()
    except (OSError, ValueError) as error:
        result['controller_error'] = type(error).__name__ + ': ' + str(error)[:250]
    finally:
        if prefix:
            remaining = baseline._bounded_process((*prefix, 'ps', '-a', '--format', '{{.Names}}',
                '--filter', 'name=runtime-sandbox2-'), timeout_ms=8000)
            count = len(remaining.stdout.splitlines()) if remaining.status == 'sandbox_completed' and remaining.exit_code == 0 else None
        else: count = None
        result['phase_container_count_after_teardown'] = count
        result['cleanup_verified'] = (count == 0 and result.get('temporary_workspace_removed') is True
            and all(s['cleanup_verified'] for s in result['stages']))
        if result['stages'] and not result['cleanup_verified']: result['status'] = CONTAINMENT_BLOCKED
    descriptor, receipt = _evidence_pair(result)
    result['descriptor'], result['verification_receipt'] = descriptor.as_dict(), receipt.as_dict()
    result['receipt_authenticated_in_issuing_process'] = True
    result['exported_json_is_report_only'] = True
    return result
