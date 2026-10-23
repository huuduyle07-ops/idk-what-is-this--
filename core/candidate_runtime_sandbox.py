"""RUNTIME.SANDBOX.1: measured effect containment, never runtime authority.

Only embedded synthetic probes can run. Backend options and local endpoint are
implementation-owned. Exported evidence is report-only. No executor is wired.
"""
from __future__ import annotations

import base64
from dataclasses import asdict, dataclass, field, replace
from hashlib import sha256
import hmac
import json
import os
from pathlib import Path, PurePosixPath
import platform
import secrets
import select
import shutil
import socket
import subprocess
import tempfile
from threading import Event, Thread
from time import monotonic, perf_counter

from core.candidate_runtime_sandbox_probe import PROBE_SOURCE

PHASE_ID = 'RUNTIME.SANDBOX.1'
SCHEMA_VERSION = 'runtime_sandbox_1_v1'
CONTRACT_VERSION = 'candidate_runtime_effect_boundary_v1'
LOCAL_IMAGE = 'python:3.12-slim'
EXECUTABLE_ID = 'runtime.sandbox1.fixed_python_probe_v1'
PROBE_IDS = ('boundary', 'descendant', 'timeout', 'stdout', 'stderr')
MANDATORY_REQUIREMENTS = (
    'ephemeral_working_directory', 'fixed_executable_and_arguments',
    'exact_source_and_classpath', 'hard_wall_clock_timeout',
    'hard_stdout_stderr_bounds', 'all_child_process_cleanup',
    'no_persistent_diagnostic_artifacts', 'candidate_filesystem_isolation',
    'candidate_network_isolation', 'candidate_environment_isolation',
    'candidate_extra_process_prevention',
)
TIMING_FIELDS = ('backend_availability_seconds', 'sandbox_startup_seconds',
    'probe_execution_seconds', 'teardown_seconds', 'filesystem_seconds',
    'network_seconds', 'environment_seconds', 'descendant_seconds',
    'timeout_seconds', 'stdout_seconds', 'stderr_seconds', 'total_seconds')
_SECRET = secrets.token_bytes(32)
_VERIFIED_ADAPTER = None
_FIXTURE = b'RUNTIME.SANDBOX.1 exact synthetic projection\n'
_WORKLOAD_ENVIRONMENT = {'PATH': '/usr/local/bin:/usr/bin:/bin', 'LANG': 'C.UTF-8',
    'GPG_KEY': '', 'PYTHON_VERSION': '', 'PYTHON_SHA256': '',
    'SANDBOX_PUBLIC_SENTINEL': 'phase-owned', 'HOME': '/work', 'HOSTNAME': 'runtime-sandbox1'}
_DENIED_SYSCALLS = ('socket', 'socketpair', 'connect', 'bind', 'listen', 'accept',
    'accept4', 'sendto', 'recvfrom', 'sendmsg', 'recvmsg', 'recvmmsg', 'sendmmsg',
    'io_uring_setup', 'io_uring_enter', 'io_uring_register', 'unshare', 'setns',
    'mount', 'umount2', 'pivot_root', 'ptrace', 'process_vm_readv',
    'process_vm_writev', 'bpf', 'perf_event_open', 'keyctl', 'add_key',
    'request_key', 'open_by_handle_at', 'name_to_handle_at', 'userfaultfd',
    'init_module', 'finit_module', 'delete_module', 'kexec_load', 'kexec_file_load',
    'reboot', 'clone3')
_SECCOMP = {'defaultAction': 'SCMP_ACT_ALLOW', 'syscalls': [
    {'names': list(_DENIED_SYSCALLS), 'action': 'SCMP_ACT_ERRNO', 'errnoRet': 1},
    *({'names': ['clone'], 'action': 'SCMP_ACT_ERRNO', 'errnoRet': 1,
       'args': [{'index': 0, 'value': flag, 'valueTwo': flag,
                 'op': 'SCMP_CMP_MASKED_EQ'}]}
      for flag in (0x20000, 0x2000000, 0x4000000, 0x8000000,
                   0x10000000, 0x20000000, 0x40000000)),
]}


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _hash(value):
    return sha256(_json(value).encode()).hexdigest()


def _sign(value):
    return hmac.new(_SECRET, _json(value).encode(), 'sha256').hexdigest()


class CandidateRuntimeSandboxError(ValueError):
    def __init__(self, code, reason=''):
        self.code, self.reason = code, reason or code
        self.candidate_execution_count = 0
        super().__init__(code + ': ' + self.reason)


@dataclass(frozen=True, slots=True)
class ExactSandboxInput:
    path: str
    content: bytes

    def __post_init__(self):
        if (type(self.path) is not str or self.path != 'projection.txt'
                or type(self.content) is not bytes or self.content != _FIXTURE
                or PurePosixPath(self.path).is_absolute()):
            raise CandidateRuntimeSandboxError('sandbox_input_not_phase_owned')


@dataclass(frozen=True, slots=True)
class CandidateRuntimeSandboxExecutionSpec:
    executable_identity: str
    argv: tuple[str, ...]
    inputs: tuple[ExactSandboxInput, ...]
    environment: tuple[tuple[str, str], ...] = ()
    timeout_ms: int = 5000
    stdout_limit_bytes: int = 8192
    stderr_limit_bytes: int = 8192

    def __post_init__(self):
        if (self.executable_identity != EXECUTABLE_ID or type(self.argv) is not tuple
                or len(self.argv) != 1 or self.argv[0] not in PROBE_IDS):
            raise CandidateRuntimeSandboxError('sandbox_executable_policy_denied')
        if (type(self.inputs) is not tuple or len(self.inputs) != 1
                or type(self.inputs[0]) is not ExactSandboxInput):
            raise CandidateRuntimeSandboxError('sandbox_input_not_phase_owned')
        if type(self.environment) is not tuple or self.environment != ():
            raise CandidateRuntimeSandboxError('sandbox_environment_policy_denied')
        for value, low, high in ((self.timeout_ms, 250, 10000),
                (self.stdout_limit_bytes, 256, 16384), (self.stderr_limit_bytes, 256, 16384)):
            if type(value) is not int or not low <= value <= high:
                raise CandidateRuntimeSandboxError('sandbox_bound_invalid')


def synthetic_probe_spec(probe_id):
    return CandidateRuntimeSandboxExecutionSpec(EXECUTABLE_ID, (probe_id,),
        (ExactSandboxInput('projection.txt', _FIXTURE),),
        timeout_ms=10000 if probe_id == 'timeout' else 5000)


@dataclass(frozen=True, slots=True)
class SandboxBackendObservation:
    supported_host_platform: str
    backend_identity: str
    backend_version: str
    image_identity: str
    cli_present: bool
    backend_available: bool
    reason: str
    backend_kind: str = 'docker_linux_local'


@dataclass(frozen=True, slots=True)
class SandboxProbeOutcome:
    probe_id: str
    probe_sha256: str
    timeout_ms: int
    stdout_limit_bytes: int
    stderr_limit_bytes: int
    status: str
    passed_dimensions: tuple[str, ...]
    cleanup_verified: bool
    stdout_size: int
    stderr_size: int
    # Canonical measured facts exclude durations, namespace/PID/temp identifiers.
    measured_facts: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class CandidateRuntimeSandboxVerificationReceipt:
    backend: SandboxBackendObservation
    outcomes: tuple[SandboxProbeOutcome, ...]
    status: str
    missing_requirements: tuple[str, ...]
    cleanup_outcome: str
    _signature: str = field(default='', repr=False, compare=False)
    schema_version: str = field(default=SCHEMA_VERSION, init=False)
    phase_id: str = field(default=PHASE_ID, init=False)
    verification_contract_version: str = field(default=CONTRACT_VERSION, init=False)
    seccomp_policy_sha256: str = field(default=_hash(_SECCOMP), init=False)
    authority: str = field(default='infrastructure_effect_measurement_only', init=False)
    candidate_execution_count: int = field(default=0, init=False)
    java_execution_count: int = field(default=0, init=False)
    bank_execution_count: int = field(default=0, init=False)
    behavioral_scenario_count: int = field(default=0, init=False)
    model_calls: int = field(default=0, init=False)
    author_calls: int = field(default=0, init=False)
    repository_traversals: int = field(default=0, init=False)
    source_mutation: int = field(default=0, init=False)
    runtime_authority: bool = field(default=False, init=False)
    repository_write_authority: bool = field(default=False, init=False)
    apply_authority: bool = field(default=False, init=False)

    def _payload(self):
        value = asdict(self)
        value.pop('_signature')
        return value

    @property
    def fingerprint(self):
        return _hash(self._payload())

    def as_dict(self):
        return {**json.loads(_json(self._payload())), 'verification_receipt_fingerprint': self.fingerprint}


@dataclass(frozen=True, slots=True)
class CandidateRuntimeSandboxDescriptor:
    backend_kind: str
    backend_identity: str
    backend_version: str
    supported_host_platform: str
    image_identity: str
    available: bool
    verified: bool
    enforced_requirements: tuple[str, ...]
    verification_receipt_fingerprint: str
    _signature: str = field(default='', repr=False, compare=False)
    schema_version: str = field(default=SCHEMA_VERSION, init=False)
    phase_id: str = field(default=PHASE_ID, init=False)
    workspace_filesystem_policy: str = field(default='ephemeral_tmpfs_exact_inputs_only', init=False)
    child_process_policy: str = field(default='descendants_confined_to_private_namespaces_and_cgroup_then_destroyed', init=False)
    shell_available: bool = field(default=False, init=False)
    arbitrary_command_authority: bool = field(default=False, init=False)
    repository_write_authority: bool = field(default=False, init=False)
    runtime_authority: bool = field(default=False, init=False)
    apply_authority: bool = field(default=False, init=False)

    @property
    def backend_available(self): return self.available

    @property
    def backend_verified(self): return self.verified

    def _payload(self):
        value = asdict(self)
        value.pop('_signature')
        return value

    @property
    def fingerprint(self): return _hash(self._payload())

    def as_dict(self):
        value = json.loads(_json(self._payload()))
        for name, requirement in (
                ('network_isolation_enforced', 'candidate_network_isolation'),
                ('host_filesystem_isolation_enforced', 'candidate_filesystem_isolation'),
                ('environment_isolation_enforced', 'candidate_environment_isolation'),
                ('child_process_policy_enforced', 'candidate_extra_process_prevention'),
                ('process_tree_cleanup_enforced', 'all_child_process_cleanup'),
                ('timeout_enforced', 'hard_wall_clock_timeout'),
                ('stdout_bound_enforced', 'hard_stdout_stderr_bounds'),
                ('stderr_bound_enforced', 'hard_stdout_stderr_bounds'),
                ('persistent_artifact_policy_enforced', 'no_persistent_diagnostic_artifacts')):
            value[name] = requirement in self.enforced_requirements
        return {**value, 'sandbox_descriptor_fingerprint': self.fingerprint}


def _authentic(value, kind):
    return (type(value) is kind and type(value._signature) is str
        and hmac.compare_digest(value._signature, _sign(value._payload())))


def validate_sandbox_verification_receipt(receipt):
    if not _authentic(receipt, CandidateRuntimeSandboxVerificationReceipt):
        raise CandidateRuntimeSandboxError('sandbox_receipt_unauthenticated')
    return receipt


def validate_sandbox_descriptor(descriptor, receipt):
    validate_sandbox_verification_receipt(receipt)
    if (not _authentic(descriptor, CandidateRuntimeSandboxDescriptor)
            or descriptor.verification_receipt_fingerprint != receipt.fingerprint
            or descriptor._payload() != _descriptor(receipt)._payload()):
        raise CandidateRuntimeSandboxError('sandbox_descriptor_unauthenticated')
    return descriptor


def sandbox_satisfies_executor_boundary(descriptor, executor_required_boundary=MANDATORY_REQUIREMENTS):
    # A consumer cannot shrink the frozen mandatory set or bless exported JSON.
    return (type(executor_required_boundary) is tuple
        and executor_required_boundary == MANDATORY_REQUIREMENTS
        and _authentic(descriptor, CandidateRuntimeSandboxDescriptor)
        and descriptor.available is True and descriptor.verified is True
        and descriptor.enforced_requirements == MANDATORY_REQUIREMENTS)


@dataclass(frozen=True, slots=True)
class _Capture:
    status: str
    exit_code: int | None
    stdout: bytes
    stderr: bytes
    deadline_triggered: bool
    termination_verified: bool = False
    termination_within_deadline: bool = False
    measured_termination_ms: float | None = None


def _bounded_process(argv, *, input_bytes=b'', timeout_ms=5000,
                     stdout_limit=16384, stderr_limit=16384, on_abort=None,
                     abort_after_ms=None):
    """Bound both readers while bytes arrive; never communicate-then-truncate."""
    env = {name: os.environ[name] for name in ('SystemRoot', 'WINDIR') if name in os.environ}
    env['CATTUS_SANDBOX_HOST_ONLY'] = 'synthetic-host-only-secret'
    started = monotonic()
    deadline = started + timeout_ms / 1000
    trigger = started + (abort_after_ms or timeout_ms) / 1000
    process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, shell=False, env=env,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    overflow = Event()
    outputs = [bytearray(), bytearray()]
    def read(stream, output, bound):
        while True:
            data = stream.read(256)
            if not data: break
            remaining = bound - len(output)
            output.extend(data[:remaining])
            if len(data) > remaining:
                overflow.set()
                break
    readers = [Thread(target=read, args=(stream, output, limit), daemon=True)
        for stream, output, limit in zip((process.stdout, process.stderr), outputs,
                                       (stdout_limit, stderr_limit))]
    for reader in readers: reader.start()
    status = 'sandbox_completed'
    terminated = False
    within_deadline = False
    termination_ms = None
    try:
        process.stdin.write(input_bytes)
        process.stdin.close()
        while process.poll() is None:
            if overflow.wait(.005):
                status = 'sandbox_output_limit_exceeded'
                break
            if monotonic() >= trigger:
                status = 'sandbox_timeout'
                break
        if status != 'sandbox_completed':
            # Disconnect the attached client immediately so output backpressure
            # cannot delay the daemon's kill/stop response. No join precedes kill.
            process.kill()
            if on_abort is not None:
                terminated = on_abort()
                within_deadline = terminated and monotonic() <= deadline
                if terminated: termination_ms = (monotonic() - started) * 1000
        process.wait(timeout=2)
    except (OSError, subprocess.TimeoutExpired):
        status = 'sandbox_control_failure'
        process.kill()
        process.wait(timeout=2)
    finally:
        for reader in readers: reader.join(timeout=2)
        if any(reader.is_alive() for reader in readers):
            status = 'sandbox_control_failure'
        for stream in (process.stdout, process.stderr): stream.close()
    if overflow.is_set() and status == 'sandbox_completed':
        status = 'sandbox_output_limit_exceeded'
    if status == 'sandbox_completed':
        within_deadline = monotonic() <= deadline
    return _Capture(status, process.returncode, bytes(outputs[0]), bytes(outputs[1]),
                    status == 'sandbox_timeout', terminated, within_deadline, termination_ms)


def _local_endpoint():
    if os.name == 'nt': return 'npipe:////./pipe/dockerDesktopLinuxEngine'
    if platform.system() == 'Linux': return 'unix:///var/run/docker.sock'
    return ''


def _docker_prefix():
    binary, endpoint = shutil.which('docker'), _local_endpoint()
    if not binary or not endpoint: return ()
    resolved = Path(binary).resolve()
    owner_root = Path(__file__).resolve().parents[1]
    if resolved.is_relative_to(owner_root) or (os.name == 'nt' and resolved.suffix.lower() != '.exe'):
        return ()
    # No user's Docker config, context, credential helper, plugin or remote host.
    absent_config = str(Path(tempfile.gettempdir()) / ('runtime-sandbox1-no-config-' + secrets.token_hex(16)))
    return (binary, '--config', absent_config, '--host', endpoint)


def discover_local_sandbox_backend(*, timings=None):
    tick = perf_counter()
    host = platform.system() + '-' + platform.machine()
    prefix = _docker_prefix()
    observed = SandboxBackendObservation(host, '', '', '', bool(shutil.which('docker')),
        False, 'sandbox_backend_unavailable')
    try:
        if not prefix: return observed
        version = _bounded_process((*prefix, 'version', '--format', '{{json .}}'), timeout_ms=8000)
        if version.status != 'sandbox_completed' or version.exit_code != 0:
            return replace(observed, reason='sandbox_backend_unavailable_local_engine_unreachable')
        data = json.loads(version.stdout)
        if type(data) is not dict: raise ValueError('non-object version metadata')
        server = data.get('Server') or {}
        if type(server) is not dict or not server.get('Version'): raise ValueError('backend version missing')
        identity = 'local-docker:' + _local_endpoint()
        observed = replace(observed, backend_identity=identity, backend_version=str(server.get('Version', '')))
        if server.get('Os') != 'linux':
            return replace(observed, reason='backend_not_eligible_non_linux_engine')
        image = _bounded_process((*prefix, 'image', 'inspect', LOCAL_IMAGE,
            '--format', '{{json .}}'), timeout_ms=8000, stdout_limit=65536)
        if image.status != 'sandbox_completed' or image.exit_code != 0:
            return replace(observed, reason='sandbox_backend_unavailable_exact_local_image_missing')
        details = json.loads(image.stdout)
        if type(details) is not dict: raise ValueError('non-object image metadata')
        image_id = details.get('Id', '')
        if (details.get('Os') != 'linux' or not isinstance(image_id, str)
                or len(image_id) != 71 or not image_id.startswith('sha256:')
                or any(c not in '0123456789abcdef' for c in image_id[7:])):
            return replace(observed, reason='backend_not_eligible_image_identity_invalid')
        return replace(observed, image_identity=image_id, backend_available=True, reason='backend_available_not_verified')
    except (OSError, ValueError, subprocess.SubprocessError):
        return replace(observed, reason='sandbox_backend_unavailable_detection_failed')
    finally:
        if timings is not None: timings['backend_availability_seconds'] = perf_counter() - tick


def _safe_configuration(config, image_id, probe_id='boundary'):
    try:
        return _safe_configuration_facts(config, image_id, probe_id)
    except (AttributeError, KeyError, TypeError, ValueError):
        return False


def _safe_configuration_facts(config, image_id, probe_id):
    """Independent pre-launch Docker inspection, not intent-only validation."""
    host, settings = config.get('HostConfig', {}), config.get('Config', {})
    return (config.get('Image') == image_id and host.get('Privileged') is False
        and host.get('NetworkMode') == 'none' and host.get('PidMode') in ('', None)
        and host.get('IpcMode') == 'none' and host.get('CgroupnsMode') == 'private'
        and host.get('ReadonlyRootfs') is True and not host.get('Binds')
        and not host.get('Mounts') and not config.get('Mounts')
        and host.get('CapDrop') == ['ALL'] and not host.get('CapAdd')
        and host.get('LogConfig', {}).get('Type') == 'none'
        and host.get('PidsLimit') == 128 and host.get('Memory') == 134217728
        and host.get('NanoCpus') == 1000000000
        and settings.get('User') == '65534:65534'
        and settings.get('WorkingDir') == '/work'
        and settings.get('Entrypoint') == ['/usr/local/bin/python']
        and settings.get('Cmd') == ['-I', '-S', '-B', '-c', PROBE_SOURCE, probe_id]
        and len(settings.get('Env', [])) == len(_WORKLOAD_ENVIRONMENT)
        and dict(item.split('=', 1) for item in settings.get('Env', [])) == _WORKLOAD_ENVIRONMENT
        and host.get('Tmpfs') == {'/work': 'rw,nosuid,nodev,size=32m,mode=1777',
            '/tmp': 'rw,nosuid,nodev,noexec,size=16m,mode=1777'}
        and set(host.get('SecurityOpt', [])) == {'no-new-privileges=true', 'seccomp=' + _json(_SECCOMP)})


def _facts_passed(probe, capture, facts, cleanup, host_unchanged, endpoint_quiet):
    """Pure negative matrix shared by verifier and unit tests; no evidence issuance."""
    spec = synthetic_probe_spec(probe)
    if (not cleanup or type(facts) is not dict
            or len(capture.stdout) > spec.stdout_limit_bytes
            or len(capture.stderr) > spec.stderr_limit_bytes): return ()
    dimensions = []
    if probe == 'boundary' and capture.status == 'sandbox_completed' and capture.exit_code == 0:
        expected = [{'path': 'projection.txt', 'sha256': sha256(_FIXTURE).hexdigest(), 'size_bytes': len(_FIXTURE)}]
        if facts.get('manifest') == expected:
            dimensions.extend(('exact_source_and_classpath', 'fixed_executable_and_arguments'))
        if facts.get('workspace_write') is True:
            dimensions.append('ephemeral_working_directory')
        if all(facts.get(x) is True for x in ('external_read_denied', 'external_write_denied', 'root_write_denied')) and host_unchanged:
            dimensions.append('candidate_filesystem_isolation')
        denials = facts.get('socket_denials', {})
        if (set(denials) == {'ipv4_tcp', 'ipv6_tcp', 'dns_udp', 'unix_socket'}
                and all(x is True for x in denials.values())
                and facts.get('local_connect_denied') is True
                and facts.get('socketpair_denied') is True and endpoint_quiet):
            dimensions.append('candidate_network_isolation')
        if (facts.get('host_secret_absent') is True and facts.get('environment') == _WORKLOAD_ENVIRONMENT):
            dimensions.append('candidate_environment_isolation')
        if not (facts.get('uid') == 65534 and facts.get('pid_is_one') is True
                and facts.get('no_new_privileges') is True and facts.get('capabilities_zero') is True):
            return ()
    if probe in ('descendant', 'timeout') and all(facts.get(x) is True for x in (
            'child_spawned', 'child_alive', 'same_namespaces', 'same_cgroup', 'pid_is_one')):
        if (probe == 'descendant' and capture.status == 'sandbox_completed' and capture.exit_code == 0):
            dimensions.extend(('candidate_extra_process_prevention', 'all_child_process_cleanup'))
        if (probe == 'timeout' and capture.status == 'sandbox_timeout'
                and capture.deadline_triggered and capture.termination_verified
                and capture.termination_within_deadline):
            dimensions.extend(('hard_wall_clock_timeout', 'all_child_process_cleanup'))
    if probe in ('stdout', 'stderr') and capture.status == 'sandbox_output_limit_exceeded':
        stream = capture.stdout if probe == 'stdout' else capture.stderr
        if len(stream) == (spec.stdout_limit_bytes if probe == 'stdout' else spec.stderr_limit_bytes):
            dimensions.append('hard_stdout_stderr_bounds')
    return tuple(dimensions)


def _invoke_probe(prefix, backend, spec, profile, sentinel, port, timings):
    name = 'runtime-sandbox1-' + secrets.token_hex(12)
    ctl = lambda *args: _bounded_process((*prefix, *args), timeout_ms=8000, stdout_limit=65536)
    cleanup = False
    facts = {}
    captured = _Capture('sandbox_launch_failed', None, b'', b'', False)
    start = perf_counter()
    try:
        create = ctl('create', '--name', name, '--pull', 'never', '--interactive',
            '--hostname', 'runtime-sandbox1',
            '--network', 'none', '--read-only', '--user', '65534:65534',
            '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges=true',
            '--security-opt', 'seccomp=' + str(profile), '--cgroupns', 'private',
            '--ipc', 'none', '--pids-limit', '128', '--memory', '128m', '--cpus', '1',
            '--log-driver', 'none', '--tmpfs', '/work:rw,nosuid,nodev,size=32m,mode=1777',
            '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=16m,mode=1777',
            '--workdir', '/work',
            *(token for key, value in _WORKLOAD_ENVIRONMENT.items() for token in ('--env', key + '=' + value)),
            '--entrypoint', '/usr/local/bin/python', backend.image_identity,
            '-I', '-S', '-B', '-c', PROBE_SOURCE, *spec.argv)
        if create.status != 'sandbox_completed' or create.exit_code != 0:
            raise CandidateRuntimeSandboxError('sandbox_launch_failed', create.stderr.decode(errors='replace')[:500])
        inspect = ctl('inspect', name, '--format', '{{json .}}')
        config = json.loads(inspect.stdout) if inspect.exit_code == 0 else {}
        if not _safe_configuration(config, backend.image_identity, spec.argv[0]):
            raise CandidateRuntimeSandboxError('backend_not_eligible_unsafe_configuration')
        # Image-config environment must be erased, not merely supplemented.
        timings['sandbox_startup_seconds'] += perf_counter() - start
        normalized = str(sentinel).replace('\\', '/').replace(':', '').lstrip('/')
        if os.name == 'nt':
            normalized = normalized[0].lower() + normalized[1:]
            host_paths = ['/run/desktop/mnt/host/' + normalized, '/host_mnt/' + normalized]
        else: host_paths = [str(sentinel)]
        payload = (_json({'inputs': [{'path': item.path, 'bytes': base64.b64encode(item.content).decode()}
                    for item in spec.inputs], 'host_paths': host_paths, 'port': port}) + '\n').encode()
        tick = perf_counter()
        def stop_at_bound():
            killed = ctl('kill', name)
            stopped = ctl('inspect', name, '--format', '{{.State.Running}}')
            return (killed.status == 'sandbox_completed' and killed.exit_code == 0
                and stopped.status == 'sandbox_completed' and stopped.stdout.strip() == b'false')
        captured = _bounded_process((*prefix, 'start', '--attach', '--interactive', name),
            input_bytes=payload, timeout_ms=spec.timeout_ms,
            stdout_limit=spec.stdout_limit_bytes, stderr_limit=spec.stderr_limit_bytes,
            on_abort=stop_at_bound,
            # Reserve half of the upper bound for daemon-side stop confirmation.
            # No allowance extends the consumer's requested maximum.
            abort_after_ms=spec.timeout_ms // 2 if spec.argv[0] == 'timeout' else None)
        timings['probe_execution_seconds'] += perf_counter() - tick
        if spec.argv[0] in ('boundary', 'descendant', 'timeout'):
            try:
                parsed = json.loads(captured.stdout)
                facts = parsed if type(parsed) is dict else {}
            except (ValueError, UnicodeError): pass
    finally:
        tick = perf_counter()
        # Kill and remove by phase-owned name even when create/control timed out.
        ctl('kill', name)
        removed = ctl('rm', '--force', '--volumes', name)
        absent = ctl('inspect', name, '--format', '{{.State.Running}}')
        cleanup = (removed.status == 'sandbox_completed' and removed.exit_code == 0
            and absent.status == 'sandbox_completed' and absent.exit_code != 0
            and any(message in absent.stderr.lower() for message in (b'no such object', b'no such container')))
        facts['cleanup_control'] = {'remove_status': removed.status, 'remove_exit_code': removed.exit_code,
            'inspect_status': absent.status, 'inspect_exit_code': absent.exit_code,
            'inspect_error': absent.stderr.decode(errors='replace').replace(name, '<phase-container>')[:300]}
        timings['teardown_seconds'] += perf_counter() - tick
    return captured, facts, cleanup


def _descriptor(receipt):
    validate_sandbox_verification_receipt(receipt)
    enforced = tuple(x for x in MANDATORY_REQUIREMENTS if x not in receipt.missing_requirements)
    descriptor = CandidateRuntimeSandboxDescriptor(receipt.backend.backend_kind,
        receipt.backend.backend_identity, receipt.backend.backend_version,
        receipt.backend.supported_host_platform, receipt.backend.image_identity,
        receipt.backend.backend_available, receipt.status == 'RUNTIME_SANDBOX_1_COMPLETE_WITH_WARNINGS',
        enforced, receipt.fingerprint)
    return replace(descriptor, _signature=_sign(descriptor._payload()))


def verify_candidate_runtime_sandbox(*, timings=None, diagnostics=None):
    global _VERIFIED_ADAPTER
    _VERIFIED_ADAPTER = None
    measured = {name: 0.0 for name in TIMING_FIELDS}
    total = perf_counter()
    backend = discover_local_sandbox_backend(timings=measured)
    outcomes = []
    enforced = set()
    cleanup_all = True
    if backend.backend_available:
        prefix = _docker_prefix()
        with tempfile.TemporaryDirectory(prefix='runtime-sandbox1-verifier-') as root:
            profile, sentinel = Path(root) / 'seccomp.json', Path(root) / 'host-sentinel.txt'
            profile.write_text(_json(_SECCOMP), encoding='utf-8')
            sentinel.write_bytes(b'phase-owned-host-sentinel')
            with socket.socket() as endpoint, socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as dns:
                endpoint.bind(('127.0.0.1', 0)); endpoint.listen(1)
                port = endpoint.getsockname()[1]
                dns.bind(('127.0.0.1', port))
                for probe in PROBE_IDS:
                    spec = synthetic_probe_spec(probe)
                    tick = perf_counter()
                    try:
                        capture, facts, cleanup = _invoke_probe(prefix, backend, spec, profile, sentinel, port, measured)
                    except (CandidateRuntimeSandboxError, OSError, ValueError, subprocess.SubprocessError) as error:
                        capture, facts, cleanup = _Capture(getattr(error, 'code', 'sandbox_control_failure'), None,
                            b'', str(error).encode()[:8192], False), {}, False
                    unchanged = sentinel.read_bytes() == b'phase-owned-host-sentinel'
                    quiet = not select.select([endpoint, dns], [], [], 0)[0]
                    passed = _facts_passed(probe, capture, facts, cleanup, unchanged, quiet)
                    if diagnostics is not None:
                        diagnostics[probe] = {'status': capture.status,
                            'control_stderr': capture.stderr.decode(errors='replace')[:500] if not facts else '',
                            'termination_verified': capture.termination_verified,
                            'termination_within_requested_deadline': capture.termination_within_deadline,
                            'deadline_triggered': capture.deadline_triggered,
                            'cleanup_verified': cleanup,
                            'requested_timeout_ms': spec.timeout_ms,
                            'supervisor_abort_trigger_ms': spec.timeout_ms // 2 if probe == 'timeout' else spec.timeout_ms,
                            'measured_confirmed_termination_ms': capture.measured_termination_ms,
                            'measured_probe_and_teardown_seconds': perf_counter() - tick}
                    elapsed = perf_counter() - tick
                    for dimension in (('filesystem', 'network', 'environment') if probe == 'boundary' else (probe,)):
                        measured[dimension + '_seconds'] += elapsed
                    enforced.update(passed)
                    cleanup_all &= cleanup
                    facts['termination_within_requested_deadline'] = capture.termination_within_deadline
                    canonical = tuple(sorted((key, _json(value)) for key, value in facts.items()))
                    outcomes.append(SandboxProbeOutcome(probe, sha256(PROBE_SOURCE.encode()).hexdigest(),
                        spec.timeout_ms, spec.stdout_limit_bytes, spec.stderr_limit_bytes,
                        capture.status, passed, cleanup, len(capture.stdout), len(capture.stderr), canonical))
                    if not cleanup: break
        workspace_absent = not Path(root).exists()
        if cleanup_all and workspace_absent and len(outcomes) == len(PROBE_IDS):
            enforced.add('no_persistent_diagnostic_artifacts')
    missing = tuple(x for x in MANDATORY_REQUIREMENTS if x not in enforced)
    # The timeout fixture cannot bless a deadline overrun by another workload.
    if not all(dict(outcome.measured_facts).get('termination_within_requested_deadline') == 'true'
               for outcome in outcomes):
        enforced.discard('hard_wall_clock_timeout')
        missing = tuple(x for x in MANDATORY_REQUIREMENTS if x not in enforced)
    if not cleanup_all:
        enforced.discard('all_child_process_cleanup')
        enforced.discard('no_persistent_diagnostic_artifacts')
        enforced.discard('candidate_extra_process_prevention')
        missing = tuple(x for x in MANDATORY_REQUIREMENTS if x not in enforced)
    # Both stream-specific adversarial tests are mandatory for the combined field.
    if not all(any(o.probe_id == probe and 'hard_stdout_stderr_bounds' in o.passed_dimensions
                   for o in outcomes) for probe in ('stdout', 'stderr')):
        enforced.discard('hard_stdout_stderr_bounds')
        missing = tuple(x for x in MANDATORY_REQUIREMENTS if x not in enforced)
    status = ('RUNTIME_SANDBOX_1_BLOCKED_BACKEND_UNAVAILABLE' if not backend.backend_available else
        'sandbox_capability_incomplete' if missing else 'RUNTIME_SANDBOX_1_COMPLETE_WITH_WARNINGS')
    receipt = CandidateRuntimeSandboxVerificationReceipt(backend, tuple(outcomes), status, missing,
        'not_required_no_workload_launched' if not backend.backend_available else
        'all_phase_resources_removed' if cleanup_all and workspace_absent else 'cleanup_not_verified')
    receipt = replace(receipt, _signature=_sign(receipt._payload()))
    measured['total_seconds'] = perf_counter() - total
    if timings is not None: timings.update(measured)
    descriptor = _descriptor(receipt)
    if sandbox_satisfies_executor_boundary(descriptor):
        _VERIFIED_ADAPTER = CandidateRuntimeSandboxAdapter(descriptor, receipt)
    return descriptor, receipt


@dataclass(frozen=True, slots=True)
class CandidateRuntimeSandboxAdapter:
    """Proof handle only. V1 accepts phase-owned probes; no candidate runner."""
    descriptor: CandidateRuntimeSandboxDescriptor
    receipt: CandidateRuntimeSandboxVerificationReceipt

    def __post_init__(self):
        validate_sandbox_descriptor(self.descriptor, self.receipt)
        if not sandbox_satisfies_executor_boundary(self.descriptor):
            raise CandidateRuntimeSandboxError('sandbox_capability_incomplete')


def get_verified_candidate_runtime_sandbox(descriptor=None, receipt=None):
    # Pure local lookup; never launches verification or takes runtime consent.
    if descriptor is None and receipt is None: return _VERIFIED_ADAPTER
    validate_sandbox_descriptor(descriptor, receipt)
    return CandidateRuntimeSandboxAdapter(descriptor, receipt) if sandbox_satisfies_executor_boundary(descriptor) else None
