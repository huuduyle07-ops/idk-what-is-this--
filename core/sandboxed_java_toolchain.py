"""RUNTIME.JAVA.1 local infrastructure capability, never runtime authority.

Only the embedded Java fixture can run. Frozen SANDBOX.1 owns the effect
contract and hard process controls. No executor, runtime consent, repository
root, candidate source, behavioral oracle, model or author enters this owner.
"""
from __future__ import annotations

import base64
from dataclasses import asdict, dataclass, field, replace
from hashlib import sha256
import hmac
import json
from pathlib import Path, PurePosixPath
import secrets
import select
import socket
import subprocess
import tempfile
from time import perf_counter

from core import candidate_runtime_sandbox as sandbox
from core import sandboxed_java_toolchain_discovery as discovery
from core.sandboxed_java_toolchain_probe import (JAVA_SOURCE, EXPECTED_OUTPUT,
    SOURCE_PATH, COMPILE_ARGUMENTS, RUNTIME_ARGUMENTS, JAVA_PROBE_SOURCE)

PHASE_ID = 'RUNTIME.JAVA.1'
SCHEMA_VERSION = 'runtime_java_1_v1'
COMPLETE = 'RUNTIME_JAVA_1_COMPLETE_WITH_WARNINGS'
UNAVAILABLE = 'RUNTIME_JAVA_1_BLOCKED_TOOLCHAIN_UNAVAILABLE'
INCOMPATIBLE = 'RUNTIME_JAVA_1_BLOCKED_SANDBOX_INCOMPATIBLE'
TIMING_FIELDS = ('artifact_discovery_seconds', 'sandbox_startup_seconds',
    'source_projection_seconds', 'javac_seconds', 'java_seconds',
    'toolchain_identity_seconds', 'image_boundary_verification_seconds',
    'teardown_seconds', 'total_seconds')
_SECRET = secrets.token_bytes(32)
_TIMEOUT_MS = 10000
_STREAM_LIMIT = 8192


def _json(value): return sandbox._json(value)
def _hash(value): return sha256(_json(value).encode()).hexdigest()
def _sign(value): return hmac.new(_SECRET, _json(value).encode(), 'sha256').hexdigest()
def _digest(value):
    return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


class SandboxedJavaToolchainError(ValueError):
    def __init__(self, code, reason=''):
        self.code, self.reason = code, reason or code
        self.java_execution_count = self.bank_execution_count = 0
        super().__init__(code + ': ' + self.reason)


@dataclass(frozen=True, slots=True)
class ExactJavaSandboxInput:
    path: str = SOURCE_PATH
    content: bytes = JAVA_SOURCE

    def __post_init__(self):
        if type(self.path) is not str or self.path != SOURCE_PATH or type(self.content) is not bytes or self.content != JAVA_SOURCE:
            raise SandboxedJavaToolchainError('java_input_not_phase_owned')


@dataclass(frozen=True, slots=True)
class JavaToolchainExecutionSpec:
    javac_path: str
    java_path: str
    javac_sha256: str
    java_sha256: str
    inputs: tuple[ExactJavaSandboxInput, ...] = field(default=(ExactJavaSandboxInput(),), init=False)
    timeout_ms: int = field(default=_TIMEOUT_MS, init=False)
    stdout_limit_bytes: int = field(default=_STREAM_LIMIT, init=False)
    stderr_limit_bytes: int = field(default=_STREAM_LIMIT, init=False)
    shell: bool = field(default=False, init=False)

    def __post_init__(self):
        for path, binary in ((self.javac_path, 'javac'), (self.java_path, 'java')):
            if (type(path) is not str or not path.startswith('/') or len(path) > 512
                or str(PurePosixPath(path)) != path or '..' in PurePosixPath(path).parts
                or PurePosixPath(path).name != binary or any(c in path for c in ('\n', '\r', '\x00', '\\'))):
                raise SandboxedJavaToolchainError('java_executable_identity_invalid')
        if not _digest(self.javac_sha256) or not _digest(self.java_sha256):
            raise SandboxedJavaToolchainError('java_executable_identity_invalid')

    @property
    def compile_argv(self): return (self.javac_path, *COMPILE_ARGUMENTS)
    @property
    def runtime_argv(self): return (self.java_path, *RUNTIME_ARGUMENTS)
    @property
    def compile_invocation_identity(self):
        return _hash({'argv': self.compile_argv, 'executable_sha256': self.javac_sha256, 'shell': False})
    @property
    def runtime_invocation_identity(self):
        return _hash({'argv': self.runtime_argv, 'executable_sha256': self.java_sha256, 'shell': False})


def synthetic_java_spec(pair):
    if type(pair) is not discovery.LocalJavaToolchainPair:
        raise SandboxedJavaToolchainError('java_artifact_untrusted_type')
    return JavaToolchainExecutionSpec(pair.javac_path, pair.java_path, pair.javac_sha256, pair.java_sha256)


@dataclass(frozen=True, slots=True)
class SandboxedJavaToolchainVerificationReceipt:
    sandbox_descriptor_fingerprint: str
    sandbox_verification_receipt_fingerprint: str
    sandbox_binding_authenticated: bool
    artifact_inventory: tuple[discovery.LocalJavaArtifact, ...]
    discovery_complete: bool
    discovery_reason: str
    java_artifact_identity: str
    os: str
    architecture: str
    javac_executable_identity: str
    java_executable_identity: str
    compiler_version: str
    runtime_version: str
    source_sha256: str
    compile_invocation_identity: str
    runtime_invocation_identity: str
    class_output: tuple[tuple[str, str, int], ...]
    canonical_results: tuple[tuple[str, str], ...]
    image_boundary_outcomes: tuple[sandbox.SandboxProbeOutcome, ...]
    compile_result: str
    runtime_result: str
    bounded_stdout: str
    bounded_stderr: str
    cleanup_result: str
    status: str
    reason: str
    toolchain_launch_count: int | None
    synthetic_java_execution_count: int | None
    java_workload_launch_attempted: bool
    _signature: str = field(default='', repr=False, compare=False)
    schema_version: str = field(default=SCHEMA_VERSION, init=False)
    phase_id: str = field(default=PHASE_ID, init=False)
    seccomp_policy_sha256: str = field(default=_hash(sandbox._SECCOMP), init=False)
    timeout_ms: int = field(default=_TIMEOUT_MS, init=False)
    stdout_limit_bytes: int = field(default=_STREAM_LIMIT, init=False)
    stderr_limit_bytes: int = field(default=_STREAM_LIMIT, init=False)
    expected_output: str = field(default=EXPECTED_OUTPUT.decode(), init=False)
    authority: str = field(default='synthetic_java_infrastructure_measurement_only', init=False)
    candidate_execution_count: int = field(default=0, init=False)
    bank_execution_count: int = field(default=0, init=False)
    behavioral_scenario_count: int = field(default=0, init=False)
    reflection_count: int = field(default=0, init=False)
    console_count: int = field(default=0, init=False)
    model_calls: int = field(default=0, init=False)
    author_calls: int = field(default=0, init=False)
    repository_traversals: int = field(default=0, init=False)
    source_mutation: int = field(default=0, init=False)
    image_pulls: int = field(default=0, init=False)
    installations: int = field(default=0, init=False)
    downloads: int = field(default=0, init=False)
    runtime_authority: bool = field(default=False, init=False)
    repository_write_authority: bool = field(default=False, init=False)
    apply_authority: bool = field(default=False, init=False)

    def _payload(self):
        value = asdict(self); value.pop('_signature'); return value
    @property
    def fingerprint(self): return _hash(self._payload())
    def as_dict(self):
        return {**json.loads(_json(self._payload())), 'verification_receipt_fingerprint': self.fingerprint}


@dataclass(frozen=True, slots=True)
class SandboxedJavaToolchainDescriptor:
    sandbox_descriptor_fingerprint: str
    sandbox_verification_receipt_fingerprint: str
    java_artifact_identity: str
    os: str
    architecture: str
    javac_available: bool
    java_runtime_available: bool
    javac_executable_identity: str
    java_executable_identity: str
    compiler_version: str
    runtime_version: str
    compile_invocation_identity: str
    runtime_invocation_identity: str
    source_projection_supported: bool
    class_output_projection_supported: bool
    sandbox_compatibility: bool
    available: bool
    verified: bool
    verification_receipt_fingerprint: str
    _signature: str = field(default='', repr=False, compare=False)
    schema_version: str = field(default=SCHEMA_VERSION, init=False)
    phase_id: str = field(default=PHASE_ID, init=False)
    invocation_surface: str = field(default='fixed_phase_owned_source_javac_and_standalone_main_only', init=False)
    runtime_authority: bool = field(default=False, init=False)
    repository_write_authority: bool = field(default=False, init=False)
    apply_authority: bool = field(default=False, init=False)

    def _payload(self):
        value = asdict(self); value.pop('_signature'); return value
    @property
    def fingerprint(self): return _hash(self._payload())
    def as_dict(self):
        return {**json.loads(_json(self._payload())), 'java_descriptor_fingerprint': self.fingerprint}


def _authentic(value, kind):
    try:
        return type(value) is kind and type(value._signature) is str and hmac.compare_digest(value._signature, _sign(value._payload()))
    except (TypeError, ValueError, OverflowError): return False


def validate_java_verification_receipt(receipt):
    if not _authentic(receipt, SandboxedJavaToolchainVerificationReceipt):
        raise SandboxedJavaToolchainError('java_receipt_unauthenticated')
    return receipt


def _descriptor(receipt):
    validate_java_verification_receipt(receipt)
    verified = receipt.status == COMPLETE
    available = bool(receipt.java_artifact_identity and receipt.os == 'linux' and receipt.architecture == 'amd64')
    record = SandboxedJavaToolchainDescriptor(receipt.sandbox_descriptor_fingerprint,
        receipt.sandbox_verification_receipt_fingerprint, receipt.java_artifact_identity,
        receipt.os, receipt.architecture, available, available,
        receipt.javac_executable_identity, receipt.java_executable_identity,
        receipt.compiler_version, receipt.runtime_version,
        receipt.compile_invocation_identity, receipt.runtime_invocation_identity,
        verified, verified, verified, available, verified, receipt.fingerprint)
    return replace(record, _signature=_sign(record._payload()))


def validate_java_descriptor(descriptor, receipt):
    validate_java_verification_receipt(receipt)
    if not _authentic(descriptor, SandboxedJavaToolchainDescriptor) or descriptor._payload() != _descriptor(receipt)._payload():
        raise SandboxedJavaToolchainError('java_descriptor_unauthenticated')
    return descriptor


def java_toolchain_satisfies_executor_runtime(java_descriptor, sandbox_descriptor):
    return (_authentic(java_descriptor, SandboxedJavaToolchainDescriptor)
        and sandbox.sandbox_satisfies_executor_boundary(sandbox_descriptor)
        and java_descriptor.available is True and java_descriptor.verified is True
        and java_descriptor.javac_available is True and java_descriptor.java_runtime_available is True
        and java_descriptor.sandbox_compatibility is True
        and java_descriptor.source_projection_supported is True
        and java_descriptor.class_output_projection_supported is True
        and java_descriptor.os == 'linux' and java_descriptor.architecture == 'amd64'
        and java_descriptor.sandbox_descriptor_fingerprint == sandbox_descriptor.fingerprint
        and java_descriptor.sandbox_verification_receipt_fingerprint == sandbox_descriptor.verification_receipt_fingerprint)


def _safe_java_configuration(config, image_identity):
    # Delegate every frozen isolation check after independently authenticating
    # the *actual* new entrypoint/cmd. Environment equality stays unchanged.
    try:
        settings = config['Config']
        if (settings.get('Entrypoint') != ['/usr/local/bin/python'] or
            settings.get('Cmd') != ['-I', '-S', '-B', '-c', JAVA_PROBE_SOURCE]): return False
        normalized = {**config, 'Config': {**settings,
            'Cmd': ['-I', '-S', '-B', '-c', sandbox.PROBE_SOURCE, 'boundary']}}
        return sandbox._safe_configuration(normalized, image_identity)
    except (KeyError, TypeError, AttributeError): return False


def _stage_bytes(stage, name):
    return base64.b64decode(stage[name + '_b64'], validate=True)


def _java_failure(capture, facts, cleanup, spec):
    """Pure negative evaluator. Fabricated facts never issue capability."""
    if not cleanup: return 'java_cleanup_not_verified'
    if capture.status != 'sandbox_completed' or capture.exit_code != 0:
        return 'sandbox_java_incompatible:' + capture.status
    if not capture.termination_within_deadline: return 'java_hard_timeout_not_verified'
    if len(capture.stdout) > _STREAM_LIMIT or len(capture.stderr) > _STREAM_LIMIT:
        return 'java_output_limit_exceeded'
    try:
        if (facts['environment'] != sandbox._WORKLOAD_ENVIRONMENT or facts['uid'] != 65534
            or not all(facts[x] is True for x in ('pid_is_one', 'no_new_privileges',
                'capabilities_zero', 'descendants_contained'))): return 'java_runtime_boundary_incomplete'
        if facts['source_sha256'] != sha256(JAVA_SOURCE).hexdigest() or facts['source_size_bytes'] != len(JAVA_SOURCE):
            return 'java_source_projection_mismatch'
        if facts['javac_binary_sha256'] != spec.javac_sha256 or facts['java_binary_sha256'] != spec.java_sha256:
            return 'java_executable_identity_mismatch'
        stages = facts['stages']
        invocations = (('javac_identity', (spec.javac_path, '-version'), 1024),
            ('java_identity', (spec.java_path, '-version'), 1024),
            ('javac', spec.compile_argv, 2048), ('java', spec.runtime_argv, 1024))
        for name, argv, bound in invocations:
            stage = stages.get(name)
            if type(stage) is not dict: return 'java_compile_failure' if name == 'javac' else 'sandbox_java_incompatible:' + name + '_not_completed'
            if stage['argv'] != list(argv): return 'java_invocation_identity_mismatch'
            if stage['overflow'] is not False or any(len(_stage_bytes(stage, stream)) > bound for stream in ('stdout', 'stderr')):
                return 'java_output_limit_exceeded'
            if stage['exit_code'] != 0:
                return 'java_compile_failure' if name == 'javac' else 'sandbox_java_incompatible:' + name + '_failed'
        if set(stages) != {x[0] for x in invocations}: return 'java_invocation_identity_mismatch'
        if not (_stage_bytes(stages['javac_identity'], 'stdout') + _stage_bytes(stages['javac_identity'], 'stderr')).strip():
            return 'java_compiler_identity_missing'
        if not (_stage_bytes(stages['java_identity'], 'stdout') + _stage_bytes(stages['java_identity'], 'stderr')).strip():
            return 'java_runtime_identity_missing'
        manifest = facts['class_manifest']
        if (len(manifest) != 1 or manifest[0]['path'] != 'JavaSandboxProbe.class'
            or not _digest(manifest[0]['sha256']) or type(manifest[0]['size_bytes']) is not int
            or not 0 < manifest[0]['size_bytes'] <= 32768): return 'java_class_output_mismatch'
        if _stage_bytes(stages['javac'], 'stdout') or _stage_bytes(stages['javac'], 'stderr'):
            return 'java_compile_diagnostics_unexpected'
        if _stage_bytes(stages['java'], 'stdout') != EXPECTED_OUTPUT or _stage_bytes(stages['java'], 'stderr'):
            return 'java_probe_output_mismatch'
        if facts.get('controller_error'): return 'sandbox_java_incompatible:controller_error'
        return ''
    except (KeyError, TypeError, ValueError): return 'java_runtime_boundary_incomplete'


def _verify_image_boundary(prefix, artifact, sandbox_receipt, profile, root, measured):
    """Re-measure all frozen dimensions against the new image; no tag trust."""
    backend = replace(sandbox_receipt.backend, image_identity=artifact.image_identity)
    outcomes, enforced = [], set()
    sentinel = Path(root) / 'host-sentinel.txt'
    sentinel.write_bytes(b'phase-owned-host-sentinel')
    frozen_timings = {key: 0.0 for key in sandbox.TIMING_FIELDS}
    started = perf_counter()
    with socket.socket() as endpoint, socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as dns:
        endpoint.bind(('127.0.0.1', 0)); endpoint.listen(1)
        port = endpoint.getsockname()[1]; dns.bind(('127.0.0.1', port))
        for mode in sandbox.PROBE_IDS:
            spec = sandbox.synthetic_probe_spec(mode)
            capture, facts, cleanup = sandbox._invoke_probe(prefix, backend, spec, profile, sentinel, port, frozen_timings)
            unchanged = sentinel.read_bytes() == b'phase-owned-host-sentinel'
            quiet = not select.select([endpoint, dns], [], [], 0)[0]
            passed = sandbox._facts_passed(mode, capture, facts, cleanup, unchanged, quiet)
            facts['termination_within_requested_deadline'] = capture.termination_within_deadline
            outcomes.append(sandbox.SandboxProbeOutcome(mode, sha256(sandbox.PROBE_SOURCE.encode()).hexdigest(),
                spec.timeout_ms, spec.stdout_limit_bytes, spec.stderr_limit_bytes,
                capture.status, passed, cleanup, len(capture.stdout), len(capture.stderr),
                tuple(sorted((key, _json(value)) for key, value in facts.items()))))
            enforced.update(passed)
            if not cleanup: break
    measured['image_boundary_verification_seconds'] += perf_counter() - started
    safe = (len(outcomes) == len(sandbox.PROBE_IDS) and all(o.cleanup_verified for o in outcomes)
        and all(dict(o.measured_facts).get('termination_within_requested_deadline') == 'true' for o in outcomes)
        and all(any(o.probe_id == mode and 'hard_stdout_stderr_bounds' in o.passed_dimensions for o in outcomes)
            for mode in ('stdout', 'stderr'))
        and set(sandbox.MANDATORY_REQUIREMENTS) - {'no_persistent_diagnostic_artifacts'} <= enforced)
    return tuple(outcomes), safe


def _invoke_java(prefix, artifact, pair, spec, profile, measured):
    name = 'runtime-java1-' + secrets.token_hex(12)
    ctl = lambda *args: sandbox._bounded_process((*prefix, *args), timeout_ms=8000, stdout_limit=65536)
    capture = sandbox._Capture('sandbox_launch_failed', None, b'', b'', False)
    facts, cleanup = {}, False
    tick = perf_counter()
    try:
        created = ctl('create', '--name', name, '--pull', 'never', '--interactive',
            '--hostname', 'runtime-sandbox1', '--network', 'none', '--read-only',
            '--user', '65534:65534', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges=true', '--security-opt', 'seccomp=' + str(profile),
            '--cgroupns', 'private', '--ipc', 'none', '--pids-limit', '128',
            '--memory', '128m', '--cpus', '1', '--log-driver', 'none',
            '--tmpfs', '/work:rw,nosuid,nodev,size=32m,mode=1777',
            '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=16m,mode=1777', '--workdir', '/work',
            *(token for key, value in sandbox._WORKLOAD_ENVIRONMENT.items() for token in ('--env', key + '=' + value)),
            '--entrypoint', '/usr/local/bin/python', artifact.image_identity,
            '-I', '-S', '-B', '-c', JAVA_PROBE_SOURCE)
        if created.status != 'sandbox_completed' or created.exit_code != 0:
            raise SandboxedJavaToolchainError('sandbox_java_incompatible:create_failed', created.stderr.decode(errors='replace')[:500])
        inspected = ctl('inspect', name, '--format', '{{json .}}')
        config = json.loads(inspected.stdout) if inspected.exit_code == 0 else {}
        if not _safe_java_configuration(config, artifact.image_identity):
            raise SandboxedJavaToolchainError('java_runtime_boundary_incomplete:unsafe_image_configuration')
        measured['sandbox_startup_seconds'] += perf_counter() - tick
        payload = {'source_b64': base64.b64encode(spec.inputs[0].content).decode(),
            'source_sha256': sha256(JAVA_SOURCE).hexdigest(),
            'javac_path': pair.javac_path, 'java_path': pair.java_path,
            'javac_sha256': pair.javac_sha256, 'java_sha256': pair.java_sha256}
        def stop_at_bound():
            killed = ctl('kill', name)
            stopped = ctl('inspect', name, '--format', '{{.State.Running}}')
            return killed.exit_code == 0 and stopped.status == 'sandbox_completed' and stopped.stdout.strip() == b'false'
        capture = sandbox._bounded_process((*prefix, 'start', '--attach', '--interactive', name),
            input_bytes=(_json(payload) + '\n').encode(), timeout_ms=spec.timeout_ms,
            stdout_limit=spec.stdout_limit_bytes, stderr_limit=spec.stderr_limit_bytes,
            on_abort=stop_at_bound, abort_after_ms=spec.timeout_ms // 2)
        parsed = json.loads(capture.stdout) if capture.stdout else {}
        facts = parsed.get('facts', {})
        if type(facts) is not dict: facts = {}
        stage_timings = parsed.get('timings', {})
        if type(stage_timings) is not dict: stage_timings = {}
        for key in ('source_projection_seconds', 'javac_seconds', 'java_seconds'):
            value = stage_timings.get(key, 0.0)
            if type(value) in (int, float) and 0 <= value <= 10: measured[key] += value
        for key in ('javac_identity_seconds', 'java_identity_seconds'):
            value = stage_timings.get(key, 0.0)
            if type(value) in (int, float) and 0 <= value <= 10:
                measured['toolchain_identity_seconds'] += value
    except (SandboxedJavaToolchainError, OSError, ValueError, subprocess.SubprocessError) as error:
        capture = sandbox._Capture(getattr(error, 'code', 'sandbox_control_failure'), None,
            b'', str(error).encode()[:8192], False)
    finally:
        tick = perf_counter()
        ctl('kill', name)
        removed = ctl('rm', '--force', '--volumes', name)
        absent = ctl('inspect', name, '--format', '{{.State.Running}}')
        cleanup = (removed.status == 'sandbox_completed' and removed.exit_code == 0
            and absent.status == 'sandbox_completed' and absent.exit_code != 0
            and any(x in absent.stderr.lower() for x in (b'no such object', b'no such container')))
        measured['teardown_seconds'] += perf_counter() - tick
    return capture, facts, cleanup


def verify_sandboxed_java_toolchain(sandbox_descriptor=None, sandbox_receipt=None, *, timings=None, diagnostics=None):
    """Trusted local verification. Absence never falls back to host Java."""
    started = perf_counter(); measured = {key: 0.0 for key in TIMING_FIELDS}
    adapter = sandbox.get_verified_candidate_runtime_sandbox(sandbox_descriptor, sandbox_receipt)
    # A supplied authentic but incomplete descriptor is still bound truthfully.
    binding = sandbox_descriptor is not None and sandbox_receipt is not None
    if adapter is not None:
        sandbox_descriptor, sandbox_receipt = adapter.descriptor, adapter.receipt; binding = True
    tick = perf_counter(); inventory = discovery.discover_local_java_artifacts()
    measured['artifact_discovery_seconds'] = perf_counter() - tick
    artifact = pair = spec = None
    capture = sandbox._Capture('not_executed', None, b'', b'', False)
    facts, outcomes = {}, ()
    launch_attempted = False
    status, reason = UNAVAILABLE, inventory.reason
    cleanup_result = 'discovery_resources_removed_no_java_workload'
    for item in inventory.artifacts:
        if item.status in ('local_java_toolchain_present', 'local_java_controller_unavailable') and item.toolchains and item.os == 'linux' and item.architecture == 'amd64':
            artifact = item
            pair = next((p for p in item.toolchains if p.controller_path == '/usr/local/bin/python' and _digest(p.controller_sha256)), item.toolchains[0])
            break
    if not inventory.cleanup_verified:
        status, reason, cleanup_result = INCOMPATIBLE, 'java_discovery_cleanup_failed', 'cleanup_not_verified'
    elif artifact is None:
        reason = inventory.reason if not inventory.complete_inventory else 'no_suitable_local_java_artifact'
        if any(item.toolchains for item in inventory.artifacts):
            status, reason = INCOMPATIBLE, 'java_artifact_wrong_platform'
    else:
        spec = synthetic_java_spec(pair)
        status = INCOMPATIBLE
        if adapter is None: reason = 'java_runtime_boundary_incomplete:authenticated_verified_sandbox_missing'
        elif (inventory.backend_identity != sandbox_descriptor.backend_identity
            or inventory.backend_version != sandbox_descriptor.backend_version):
            reason = 'java_runtime_boundary_incomplete:backend_binding_changed'
        elif not inventory.complete_inventory: reason = 'java_artifact_discovery_incomplete'
        elif pair.controller_path != '/usr/local/bin/python' or not _digest(pair.controller_sha256): reason = 'java_runtime_boundary_incomplete:fixed_controller_missing'
        else:
            with tempfile.TemporaryDirectory(prefix='runtime-java1-verifier-') as root:
                profile = Path(root) / 'seccomp.json'
                profile.write_text(_json(sandbox._SECCOMP), encoding='utf-8')
                try:
                    prefix = sandbox._docker_prefix()
                    outcomes, image_safe = _verify_image_boundary(prefix, artifact, sandbox_receipt, profile, root, measured)
                    cleanup_result = ('image_boundary_resources_removed_no_java_workload'
                        if outcomes and all(o.cleanup_verified for o in outcomes) else 'cleanup_not_verified')
                    if not image_safe: reason = 'java_runtime_boundary_incomplete:image_specific_frozen_probes_failed'
                    else:
                        launch_attempted = True
                        capture, facts, cleanup = _invoke_java(prefix, artifact, pair, spec, profile, measured)
                        reason = _java_failure(capture, facts, cleanup, spec)
                        cleanup_result = 'all_phase_resources_removed' if cleanup else 'cleanup_not_verified'
                        if not reason: status, reason = COMPLETE, 'fixed_synthetic_java_probe_verified'
                except (sandbox.CandidateRuntimeSandboxError, OSError, ValueError, subprocess.SubprocessError) as error:
                    reason = 'java_runtime_boundary_incomplete:' + getattr(error, 'code', type(error).__name__)
                    cleanup_result = 'cleanup_not_verified'
            if Path(root).exists(): status, reason, cleanup_result = INCOMPATIBLE, 'java_cleanup_not_verified', 'cleanup_not_verified'
    stages = facts.get('stages', {})
    def version(key):
        try: return (_stage_bytes(stages[key], 'stdout') + _stage_bytes(stages[key], 'stderr')).decode(errors='replace').strip()
        except (KeyError, ValueError, TypeError): return ''
    def result(key):
        if key not in stages: return 'not_executed'
        return 'completed' if stages[key].get('exit_code') == 0 and not stages[key].get('overflow') else 'failed'
    stdout = stderr = ''
    try:
        stdout = _stage_bytes(stages.get('java', {}), 'stdout').decode(errors='replace')
        stderr = _stage_bytes(stages.get('java', {}), 'stderr').decode(errors='replace')
    except (KeyError, ValueError, TypeError): pass
    receipt = SandboxedJavaToolchainVerificationReceipt(
        sandbox_descriptor.fingerprint if binding else '', sandbox_receipt.fingerprint if binding else '', binding,
        inventory.artifacts, inventory.complete_inventory, inventory.reason,
        artifact.image_identity if artifact else '', artifact.os if artifact else '', artifact.architecture if artifact else '',
        (pair.javac_path + '@sha256:' + pair.javac_sha256) if pair else '',
        (pair.java_path + '@sha256:' + pair.java_sha256) if pair else '',
        version('javac_identity'), version('java_identity'), sha256(JAVA_SOURCE).hexdigest(),
        spec.compile_invocation_identity if spec else '', spec.runtime_invocation_identity if spec else '',
        tuple((x['path'], x['sha256'], x['size_bytes']) for x in facts.get('class_manifest', [])),
        tuple(sorted((key, _json(value)) for key, value in facts.items())), outcomes,
        result('javac'), result('java'), stdout, stderr, cleanup_result, status, reason,
        None if launch_attempted and not facts else facts.get('toolchain_launch_count', len(stages)),
        None if launch_attempted and not facts else facts.get('synthetic_java_execution_count', int('java' in stages)), launch_attempted)
    receipt = replace(receipt, _signature=_sign(receipt._payload()))
    measured['total_seconds'] = perf_counter() - started
    if timings is not None: timings.update(measured)
    if diagnostics is not None:
        diagnostics.update({'capture_status': capture.status, 'bounded_control_stderr': capture.stderr.decode(errors='replace'),
            'compile_diagnostics': version('javac'), 'reason': reason,
            'sandbox_binding_authenticated': binding, 'sandbox_verified': bool(adapter),
            'selected_image_size_bytes': artifact.image_size_bytes if artifact else 0})
    return _descriptor(receipt), receipt
