"""JAVA.1C positive infrastructure proof on live-authenticated SANDBOX.2.

The only effectful public operation takes no arguments. Exported reports cannot
be imported as capability. The new receipt has a separate process-local key;
neither this owner nor its pure compatibility facade resumes EXECUTOR.1.
"""
import base64
from dataclasses import asdict, dataclass, field, replace
from hashlib import sha256
import hmac
import json
from pathlib import Path
import secrets
import subprocess
import tempfile

from core import candidate_runtime_sandbox as baseline
from core import thread_compatible_runtime_sandbox as sandbox2
from core import sandboxed_java_capture_recovery as recovery
from core import sandboxed_java_positive_probe as probe

PHASE_ID = 'RUNTIME.JAVA.1C'
SCHEMA_VERSION = 'runtime_java_1c_v1'
COMPLETE = 'RUNTIME_JAVA_1_COMPLETE_WITH_WARNINGS'
COMPILE_FAILURE = 'RUNTIME_JAVA_1C_BLOCKED_COMPILE_FAILURE'
RUNTIME_FAILURE = 'RUNTIME_JAVA_1C_BLOCKED_RUNTIME_FAILURE'
SANDBOX_REGRESSION = 'RUNTIME_JAVA_1C_BLOCKED_SANDBOX_REGRESSION'
AUTHENTICATION = 'RUNTIME_JAVA_1C_BLOCKED_AUTHENTICATION'
CLEANUP_FAILURE = 'RUNTIME_JAVA_1C_BLOCKED_CLEANUP'
POLICY_SHA256 = '5a36bdf1676c4b0d7b4bef489f5e90b5c8fb201b5194be48baf61f4206a81f75'
HISTORICAL_DESCRIPTOR = 'f9cc912a4f14d9c2582b10dd0a80269f9ac78f4c582a90e4d1b0fff6ae38807e'
HISTORICAL_RECEIPT = 'b9639a0caf3788a7f8d9dfe145b8b4894639721f7c43e1b08a0b9da4cca523d0'
IMAGE = recovery.IMAGE
TIMEOUT_MS = 10000
ABORT_AFTER_MS = 5000
STREAM_LIMIT = 8192
INVOCATIONS = (('javac', probe.COMPILE_ARGV, 2048), ('java', probe.RUNTIME_ARGV, 1024))
_SECRET = secrets.token_bytes(32)


def _payload(value):
    result = asdict(value)
    result.pop('_signature')
    return result


def _sign(value):
    return hmac.new(_SECRET, baseline._json(_payload(value)).encode(), 'sha256').hexdigest()


def authenticate_sandbox2(descriptor, receipt):
    """Validate original issuer objects, including their measured snapshot binding."""
    sandbox2.validate_descriptor(descriptor, receipt)
    sandbox2.validate_policy_bytes(sandbox2.POLICY_BYTES)
    if (descriptor.status != sandbox2.COMPLETE or receipt.status != sandbox2.COMPLETE
            or descriptor.eligible_for_java1_continuation is not True
            or receipt.compatibility_classification != 'eligible_for_JAVA_1_continuation_only'
            or receipt.cleanup_verified is not True
            or receipt.stage_results != tuple((m, sandbox2.PASSED) for m in sandbox2.LADDER)
            or descriptor.verification_receipt_fingerprint != receipt.fingerprint
            or descriptor.seccomp_policy_sha256 != receipt.seccomp_policy_sha256
            or receipt.seccomp_policy_sha256 != POLICY_SHA256
            or sandbox2.POLICY_SHA256 != POLICY_SHA256
            or descriptor.image_identity != IMAGE or receipt.image_identity != IMAGE
            or any(getattr(value, key) is not False for value in (descriptor, receipt)
                for key in sandbox2.AUTHORITIES)):
        raise ValueError('java1c_live_sandbox2_binding_rejected')
    return descriptor, receipt


def _obtain_live_sandbox2():
    # replay() owns the live ladder but exports report data only. Reconstruct
    # through that same issuer immediately, from this invocation's local result.
    # No public JSON-input path exists. Never load the historical LOCAL.json.
    live = sandbox2.replay()
    sandbox2.validate_policy_bytes(sandbox2.POLICY_PATH.read_bytes())
    descriptor, receipt = sandbox2._evidence_pair(live)
    authenticate_sandbox2(descriptor, receipt)
    if (live['descriptor']['sandbox_descriptor_fingerprint'] != descriptor.fingerprint
            or live['verification_receipt']['verification_receipt_fingerprint'] != receipt.fingerprint
            or receipt.evidence_sha256 != baseline._hash(live['stages'])
            or live['cleanup_verified'] is not True):
        raise ValueError('java1c_live_sandbox2_fingerprint_mismatch')
    return descriptor, receipt, live


def safe_configuration(config):
    """Check the actual command/policy; delegate all frozen remaining settings."""
    try:
        host, settings = config['HostConfig'], config['Config']
        if (settings['Cmd'] != ['-I', '-S', '-B', '-c', probe.source()]
                or set(host['SecurityOpt']) != {'no-new-privileges=true',
                    'seccomp=' + sandbox2.POLICY_BYTES.decode()}):
            return False
        normalized = {**config, 'HostConfig': {**host, 'SecurityOpt': [
            'no-new-privileges=true', 'seccomp=' + baseline._json(baseline._SECCOMP)]},
            'Config': {**settings, 'Cmd': ['-I', '-S', '-B', '-c', baseline.PROBE_SOURCE, 'boundary']}}
        return baseline._safe_configuration(normalized, IMAGE)
    except (KeyError, TypeError, ValueError):
        return False


def _bytes(stage, stream):
    return base64.b64decode(stage[stream + '_b64'], validate=True)


def _progress(raw):
    """Bounded controller diagnostics; child stdout/stderr remain separate."""
    if not raw: return []
    rows = [json.loads(line) for line in raw.splitlines()]
    if len(rows) > len(INVOCATIONS) * 2: raise ValueError('unexpected_controller_progress')
    for i, row in enumerate(rows):
        expected = {'event', 'stage', 'pid'} | ({'exit_code', 'cleanup_verified'} if i % 2 else set())
        if (type(row) is not dict or set(row) != expected
                or row['event'] != ('completed' if i % 2 else 'started')
                or row['stage'] != INVOCATIONS[i // 2][0]
                or type(row['pid']) is not int or row['pid'] <= 1
                or (i % 2 and row['pid'] != rows[i - 1]['pid'])):
            raise ValueError('unexpected_controller_progress')
    return rows


def _state_safe(state):
    try:
        quota, period = map(int, state['cpu_max'].split())
        return (state['pid'] == 1 and state['uid'] == state['gid'] == 65534
            and state['python_threads'] == state['os_threads'] == 1
            and state['thread_start_attempts'] == 0
            and state['capabilities_zero'] is True and state['no_new_privileges'] is True
            and state['environment'] == baseline._WORKLOAD_ENVIRONMENT
            and state['pids_max'] == '128' and state['memory_max'] == '134217728'
            and quota == period and quota > 0 and state['readonly_root'] is True
            and state['work_writable'] is True and state['tmp_writable'] is True
            and set(state['boundary']['namespaces']) == {'user', 'mnt', 'net', 'pid', 'ipc', 'cgroup', 'uts'})
    except (KeyError, TypeError, ValueError):
        return False


def evaluate(capture, facts, container_cleanup):
    """Pure fail-closed predicate; fabricated measurements issue no capability."""
    if container_cleanup is not True:
        return CLEANUP_FAILURE, 'container_removal_not_verified'
    try:
        stages = facts.get('stages', {})
        if (facts.get('phase_pids_after_cleanup') != [1]
                or any(any(s.get(k) is not True for k in ('cleanup_verified', 'child_waited',
                    'pipes_closed', 'selector_cleanup_verified')) or s.get('cleanup_errors') != []
                    for s in stages.values())):
            return CLEANUP_FAILURE, 'child_or_capture_cleanup_not_verified'
        before, after = facts['controller_before'], facts['controller_after']
        if (not _state_safe(before) or not _state_safe(after)
                or before['boundary'] != after['boundary']
                or facts.get('descendants_contained') is not True):
            return SANDBOX_REGRESSION, 'runtime_boundary_or_controller_changed'
        for stage in stages.values():
            if stage['child_boundary'] != before['boundary']:
                return SANDBOX_REGRESSION, 'child_namespace_or_cgroup_changed'
        if (capture.status != 'sandbox_completed' or capture.exit_code != 0
                or not capture.termination_within_deadline
                or len(capture.stdout) > STREAM_LIMIT or len(capture.stderr) > STREAM_LIMIT):
            return (RUNTIME_FAILURE if 'java' in stages else COMPILE_FAILURE), 'outer_capture_failed'
        progress = _progress(capture.stderr)
        if progress and (len(progress) != len(INVOCATIONS) * 2 or any(
                row['pid'] != stages[row['stage']]['pid'] or
                (row['event'] == 'completed' and (row['exit_code'] != stages[row['stage']]['exit_code']
                    or row['cleanup_verified'] is not stages[row['stage']]['cleanup_verified'])) for row in progress)):
            return SANDBOX_REGRESSION, 'controller_progress_disagrees_with_final_evidence'
        if (facts.get('javac_binary_sha256') != probe.JAVAC_SHA256
                or facts.get('java_binary_sha256') != probe.JAVA_SHA256):
            return AUTHENTICATION, 'exact_executable_hash_mismatch'
        if (facts.get('work_before') != [] or facts.get('source_readback_exact') is not True
                or facts.get('source_sha256') != probe.SOURCE_SHA256
                or facts.get('source_size_bytes') != len(probe.JAVA_SOURCE)
                or sha256(probe.JAVA_SOURCE).hexdigest() != probe.SOURCE_SHA256):
            return COMPILE_FAILURE, 'exact_source_projection_not_verified'
        for name, argv, limit in INVOCATIONS:
            stage = stages.get(name)
            failure = RUNTIME_FAILURE if name == 'java' else COMPILE_FAILURE
            if (type(stage) is not dict or stage.get('argv') != list(argv)
                    or stage.get('limit_bytes') != limit or not recovery.capture_healthy(stage)
                    or stage.get('child_waited') is not True or stage.get('pipes_closed') is not True
                    or stage.get('selector_cleanup_verified') is not True or stage.get('cleanup_errors') != []
                    or stage.get('controller_error') or stage.get('exit_code') != 0):
                return failure, name + '_failed_or_not_completed'
        if set(stages) != {s[0] for s in INVOCATIONS} or facts.get('controller_error'):
            return SANDBOX_REGRESSION, 'unexpected_stage_or_controller_error'
        if facts.get('toolchain_launch_count') != 2 or facts.get('synthetic_java_execution_count') != 1:
            return SANDBOX_REGRESSION, 'unexpected_launch_count'
        rows = facts['work_after_compile']
        if (facts.get('unexpected_output_files') != [] or len(rows) != 3
                or [(r['path'], r['kind']) for r in rows] != [
                    ('JavaSandboxProbe.java', 'file'), ('classes', 'directory'),
                    ('classes/JavaSandboxProbe.class', 'file')]
                or rows[0]['sha256'] != probe.SOURCE_SHA256 or rows[0]['size_bytes'] != len(probe.JAVA_SOURCE)
                or facts['class_manifest'] != [rows[2]]
                or not recovery.java._digest(rows[2]['sha256'])
                or type(rows[2]['size_bytes']) is not int or not 0 < rows[2]['size_bytes'] <= 32768):
            return COMPILE_FAILURE, 'exact_class_output_not_verified'
        if facts.get('work_after_runtime') != rows:
            return RUNTIME_FAILURE, 'workspace_changed_during_runtime'
        if _bytes(stages['javac'], 'stdout') or _bytes(stages['javac'], 'stderr'):
            return COMPILE_FAILURE, 'unexpected_compile_diagnostics'
        if _bytes(stages['java'], 'stdout') != probe.EXPECTED_OUTPUT or _bytes(stages['java'], 'stderr'):
            return RUNTIME_FAILURE, 'exact_runtime_output_mismatch'
        return COMPLETE, 'exact_frozen_java_fixture_verified'
    except (KeyError, TypeError, ValueError, AttributeError):
        return SANDBOX_REGRESSION, 'incomplete_measurement'


@dataclass(frozen=True, slots=True)
class JavaContinuationReceipt:
    sandbox_descriptor_fingerprint: str
    sandbox_receipt_fingerprint: str
    compiler_version: str
    runtime_version: str
    class_sha256: str
    class_size_bytes: int
    evidence_sha256: str
    _signature: str = field(default='', repr=False, compare=False)
    phase_id: str = field(default=PHASE_ID, init=False)
    schema_version: str = field(default=SCHEMA_VERSION, init=False)
    status: str = field(default=COMPLETE, init=False)
    seccomp_policy_sha256: str = field(default=POLICY_SHA256, init=False)
    image_identity: str = field(default=IMAGE, init=False)
    javac_path: str = field(default=probe.JAVAC_PATH, init=False)
    javac_sha256: str = field(default=probe.JAVAC_SHA256, init=False)
    java_path: str = field(default=probe.JAVA_PATH, init=False)
    java_sha256: str = field(default=probe.JAVA_SHA256, init=False)
    source_sha256: str = field(default=probe.SOURCE_SHA256, init=False)
    compile_argv: tuple[str, ...] = field(default=probe.COMPILE_ARGV, init=False)
    runtime_argv: tuple[str, ...] = field(default=probe.RUNTIME_ARGV, init=False)
    expected_runtime_stdout: str = field(default='JAVA_SANDBOX_OK', init=False)
    expected_runtime_stderr: str = field(default='', init=False)
    cleanup_verified: bool = field(default=True, init=False)
    runtime_authority: bool = field(default=False, init=False)
    repository_write_authority: bool = field(default=False, init=False)
    apply_authority: bool = field(default=False, init=False)
    shell_available: bool = field(default=False, init=False)
    arbitrary_command_authority: bool = field(default=False, init=False)
    network_authority: bool = field(default=False, init=False)
    host_mount_authority: bool = field(default=False, init=False)

    @property
    def fingerprint(self): return baseline._hash(_payload(self))

    def as_dict(self): return {**_payload(self), 'verification_receipt_fingerprint': self.fingerprint}


@dataclass(frozen=True, slots=True)
class JavaContinuationDescriptor:
    verification_receipt_fingerprint: str
    sandbox_descriptor_fingerprint: str
    sandbox_receipt_fingerprint: str
    _signature: str = field(default='', repr=False, compare=False)
    phase_id: str = field(default=PHASE_ID, init=False)
    schema_version: str = field(default=SCHEMA_VERSION, init=False)
    status: str = field(default=COMPLETE, init=False)
    available: bool = field(default=True, init=False)
    verified: bool = field(default=True, init=False)
    sandbox_compatibility: bool = field(default=True, init=False)
    source_projection_supported: bool = field(default=True, init=False)
    class_output_projection_supported: bool = field(default=True, init=False)
    runtime_authority: bool = field(default=False, init=False)
    repository_write_authority: bool = field(default=False, init=False)
    apply_authority: bool = field(default=False, init=False)
    shell_available: bool = field(default=False, init=False)
    arbitrary_command_authority: bool = field(default=False, init=False)
    network_authority: bool = field(default=False, init=False)
    host_mount_authority: bool = field(default=False, init=False)

    @property
    def fingerprint(self): return baseline._hash(_payload(self))

    def as_dict(self): return {**_payload(self), 'java_descriptor_fingerprint': self.fingerprint}


def validate_receipt(receipt):
    if type(receipt) is not JavaContinuationReceipt or not hmac.compare_digest(receipt._signature, _sign(receipt)):
        raise ValueError('java1c_receipt_unauthenticated')
    return receipt


def validate_descriptor(descriptor, receipt):
    validate_receipt(receipt)
    if (type(descriptor) is not JavaContinuationDescriptor
            or not hmac.compare_digest(descriptor._signature, _sign(descriptor))
            or descriptor.verification_receipt_fingerprint != receipt.fingerprint
            or descriptor.sandbox_descriptor_fingerprint != receipt.sandbox_descriptor_fingerprint
            or descriptor.sandbox_receipt_fingerprint != receipt.sandbox_receipt_fingerprint):
        raise ValueError('java1c_descriptor_unauthenticated')
    return descriptor


def java_toolchain_satisfies_executor_runtime(descriptor, receipt, sandbox_descriptor, sandbox_receipt):
    """Pure infrastructure compatibility only; no executor adapter or consent."""
    try:
        validate_descriptor(descriptor, receipt)
        authenticate_sandbox2(sandbox_descriptor, sandbox_receipt)
        return (descriptor.sandbox_descriptor_fingerprint == sandbox_descriptor.fingerprint
            and descriptor.sandbox_receipt_fingerprint == sandbox_receipt.fingerprint)
    except (ValueError, TypeError, AttributeError):
        return False


def _invoke(prefix, profile):
    name = 'runtime-java1c-' + secrets.token_hex(12)
    ctl = lambda *args: baseline._bounded_process((*prefix, *args), timeout_ms=8000, stdout_limit=65536)
    capture = baseline._Capture('sandbox_launch_failed', None, b'', b'', False)
    facts, cleanup, inspected_ok = {}, False, False
    try:
        created = ctl('create', '--name', name, '--pull', 'never', '--interactive',
            '--hostname', 'runtime-sandbox1', '--network', 'none', '--read-only',
            '--user', '65534:65534', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges=true', '--security-opt', 'seccomp=' + str(profile),
            '--cgroupns', 'private', '--ipc', 'none', '--pids-limit', '128',
            '--memory', '128m', '--cpus', '1', '--log-driver', 'none',
            '--tmpfs', '/work:rw,nosuid,nodev,size=32m,mode=1777',
            '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=16m,mode=1777', '--workdir', '/work',
            *(token for key, value in baseline._WORKLOAD_ENVIRONMENT.items() for token in ('--env', key + '=' + value)),
            '--entrypoint', '/usr/local/bin/python', IMAGE, '-I', '-S', '-B', '-c', probe.source())
        if created.status != 'sandbox_completed' or created.exit_code != 0:
            raise ValueError('exact_java1c_container_create_failed:' + created.stderr.decode(errors='replace')[:200])
        inspected = ctl('inspect', name, '--format', '{{json .}}')
        inspected_ok = (inspected.status == 'sandbox_completed' and inspected.exit_code == 0
            and safe_configuration(json.loads(inspected.stdout)))
        if not inspected_ok: raise ValueError('java1c_inspected_configuration_rejected')
        def stop():
            killed = ctl('kill', name)
            stopped = ctl('inspect', name, '--format', '{{.State.Running}}')
            return (killed.status == 'sandbox_completed' and killed.exit_code == 0
                and stopped.status == 'sandbox_completed' and stopped.stdout.strip() == b'false')
        capture = baseline._bounded_process((*prefix, 'start', '--attach', '--interactive', name),
            timeout_ms=TIMEOUT_MS, stdout_limit=STREAM_LIMIT, stderr_limit=STREAM_LIMIT,
            on_abort=stop, abort_after_ms=ABORT_AFTER_MS)
        if capture.stdout: facts = json.loads(capture.stdout)['facts']
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        facts['outer_controller_error'] = type(error).__name__ + ': ' + str(error)[:250]
    finally:
        def cleanup_control(*args):
            try: return ctl(*args)
            except (OSError, ValueError, subprocess.SubprocessError):
                return baseline._Capture('cleanup_control_failed', None, b'', b'', False)
        cleanup_control('kill', name)
        removed = cleanup_control('rm', '--force', '--volumes', name)
        absent = cleanup_control('inspect', name, '--format', '{{.State.Running}}')
        cleanup = (removed.status == 'sandbox_completed' and removed.exit_code == 0
            and absent.status == 'sandbox_completed' and absent.exit_code != 0
            and any(s in absent.stderr.lower() for s in (b'no such object', b'no such container')))
    return capture, facts, cleanup, inspected_ok


def verify():
    """Reissue SANDBOX.2 live, then verify only the frozen phase-owned fixture."""
    report = {'phase_id': PHASE_ID, 'status': AUTHENTICATION, 'reason': 'not_authenticated',
        **dict.fromkeys(sandbox2.AUTHORITIES, False), 'image_identity': IMAGE,
        'seccomp_policy_sha256': POLICY_SHA256, 'historical_sandbox_descriptor_fingerprint': HISTORICAL_DESCRIPTOR,
        'historical_sandbox_receipt_fingerprint': HISTORICAL_RECEIPT,
        'runtime_policy_authorizations_consumed': 0, 'bank_execution_count': 0,
        'behavioral_execution_count': 0, 'reflection_count': 0, 'console_count': 0,
        'executor_run_count': 0, 'model_calls': 0, 'author_calls': 0,
        'executor_refreshed_or_resumed': False, 'compile_count': 0, 'jvm_fixture_count': 0,
        'pure_executor_compatibility': False, 'cleanup_verified': False, 'java_workload_attempted': False,
        'exported_json_is_report_only': True, 'facts': {}, 'temporary_workspace_removed': True,
        'timeout_ms': TIMEOUT_MS, 'abort_after_ms': ABORT_AFTER_MS,
        'stdout_limit_bytes': STREAM_LIMIT, 'stderr_limit_bytes': STREAM_LIMIT}
    sd = sr = None
    prefix = baseline._docker_prefix()
    try:
        sd, sr, live = _obtain_live_sandbox2()
        authenticate_sandbox2(sd, sr)
        report['sandbox_authentication'] = {'authenticated_in_issuing_process': True,
            'descriptor_fingerprint': sd.fingerprint, 'receipt_fingerprint': sr.fingerprint,
            'evidence_sha256': sr.evidence_sha256, 'compatibility_classification': sr.compatibility_classification}
        report['live_sandbox2'] = live
        # Both exact version commands already passed in the authenticated live
        # ladder. Bind those bytes rather than spending the unchanged five-
        # second controller window launching the same two JVMs a second time.
        identity_stages = {s['mode']: s['facts']['stages']['javac_identity']
            for s in live['stages'] if s['mode'] in ('javac_version', 'java_version')}
        report['toolchain_versions'] = {}
        for mode, path in (('javac_version', probe.JAVAC_PATH), ('java_version', probe.JAVA_PATH)):
            stage = identity_stages[mode]
            if stage['argv'] != [path, '-version'] or not recovery.capture_healthy(stage) or stage['exit_code'] != 0:
                raise ValueError('authenticated_live_toolchain_version_missing')
            value = (_bytes(stage, 'stdout') + _bytes(stage, 'stderr')).decode()
            if not value: raise ValueError('authenticated_live_toolchain_version_empty')
            report['toolchain_versions'][mode] = value
        image = baseline._bounded_process((*prefix, 'image', 'inspect', IMAGE, '--format', '{{json .}}'),
            timeout_ms=8000, stdout_limit=65536)
        metadata = json.loads(image.stdout) if image.status == 'sandbox_completed' and image.exit_code == 0 else {}
        if (not prefix or metadata.get('Id') != IMAGE or metadata.get('Os') != 'linux'
                or metadata.get('Architecture') != 'amd64' or metadata.get('Config', {}).get('Volumes')):
            raise ValueError('exact_local_java_image_required')
        report['image_identity_verified'] = True
        with tempfile.TemporaryDirectory(prefix='runtime-java1c-profile-') as root:
            report['temporary_workspace_removed'] = False
            profile = Path(root) / 'seccomp.json'
            profile.write_bytes(sandbox2.POLICY_BYTES)
            sandbox2.validate_policy_bytes(profile.read_bytes())
            report['java_workload_attempted'] = True
            capture, facts, cleanup, inspected_ok = _invoke(prefix, profile)
            report.update(facts=facts, container_cleanup_verified=cleanup,
                inspected_configuration_verified=inspected_ok, outer_capture_status=capture.status,
                outer_exit_code=capture.exit_code, outer_stderr=capture.stderr.decode(errors='replace'),
                outer_stdout_size=len(capture.stdout), termination_within_deadline=capture.termination_within_deadline,
                termination_verified=capture.termination_verified, measured_termination_ms=capture.measured_termination_ms)
            try: report['controller_progress'] = _progress(capture.stderr)
            except (ValueError, TypeError): report['controller_progress'] = []
            report['status'], report['reason'] = evaluate(capture, facts, cleanup)
            if not inspected_ok: report['status'], report['reason'] = SANDBOX_REGRESSION, 'inspected_configuration_rejected'
            report['host_profile_workspace_files'] = sorted(p.name for p in Path(root).iterdir())
            if report['host_profile_workspace_files'] != ['seccomp.json']:
                report['status'], report['reason'] = CLEANUP_FAILURE, 'unexpected_host_workspace_artifact'
        report['temporary_workspace_removed'] = not Path(root).exists()
    except (OSError, ValueError, TypeError, AttributeError, KeyError, subprocess.SubprocessError) as error:
        report['controller_error'] = type(error).__name__ + ': ' + str(error)[:250]
    finally:
        try:
            remaining = baseline._bounded_process((*prefix, 'ps', '-a', '--format', '{{.Names}}',
                '--filter', 'name=runtime-java1c-', '--filter', 'name=runtime-sandbox2-'), timeout_ms=8000) if prefix else None
            count = len(remaining.stdout.splitlines()) if (remaining is not None
                and remaining.status == 'sandbox_completed' and remaining.exit_code == 0) else None
        except (OSError, ValueError, subprocess.SubprocessError):
            count = None
        report['phase_container_count_after_teardown'] = count
        stages = report['facts'].get('stages', {})
        report['child_and_capture_cleanup_verified'] = (report['facts'].get('phase_pids_after_cleanup') == [1]
            and all(all(s.get(k) is True for k in ('cleanup_verified', 'child_waited', 'pipes_closed',
                'selector_cleanup_verified')) and s.get('cleanup_errors') == [] for s in stages.values()))
        report['cleanup_verified'] = (count == 0 and report['temporary_workspace_removed'] is True
            and report.get('container_cleanup_verified', not report['java_workload_attempted']) is True
            and (not report['java_workload_attempted'] or report['child_and_capture_cleanup_verified']))
        if sd is not None and not report['cleanup_verified']:
            report['status'], report['reason'] = CLEANUP_FAILURE, 'phase_cleanup_not_verified'
    stages = report['facts'].get('stages', {})
    progress = report.get('controller_progress', [])
    for name, count_key in (('javac', 'compile_count'), ('java', 'jvm_fixture_count')):
        report[count_key] = (int(type(stages.get(name, {}).get('pid')) is int
            or any(r['stage'] == name and r['event'] == 'started' for r in progress))
            if stages or progress or not report['java_workload_attempted'] else None)
    report['decoded_stages'] = {name: {**stage, 'stdout': _bytes(stage, 'stdout').decode(errors='replace'),
        'stderr': _bytes(stage, 'stderr').decode(errors='replace')} for name, stage in stages.items()}
    if report['status'] != COMPLETE:
        return None, None, report
    # Only this verified live operation issues positive process-local evidence.
    facts = report['facts']
    row = facts['class_manifest'][0]
    receipt = JavaContinuationReceipt(sd.fingerprint, sr.fingerprint, report['toolchain_versions']['javac_version'],
        report['toolchain_versions']['java_version'], row['sha256'], row['size_bytes'], baseline._hash({
            'facts': facts, 'cleanup_verified': report['cleanup_verified'],
            'inspected_configuration_verified': report['inspected_configuration_verified'],
            'remaining_phase_containers': count, 'temporary_workspace_removed': report['temporary_workspace_removed']}))
    receipt = replace(receipt, _signature=_sign(receipt))
    descriptor = JavaContinuationDescriptor(receipt.fingerprint, sd.fingerprint, sr.fingerprint)
    descriptor = replace(descriptor, _signature=_sign(descriptor))
    validate_descriptor(descriptor, receipt)
    report['pure_executor_compatibility'] = java_toolchain_satisfies_executor_runtime(descriptor, receipt, sd, sr)
    report.update(descriptor=descriptor.as_dict(), verification_receipt=receipt.as_dict(),
        receipt_authenticated_in_issuing_process=True,
        host_persistent_java_artifact_count=0,
        source_class_tmpfs_destroyed=True, tmp_diagnostics_destroyed=True)
    return descriptor, receipt, report
