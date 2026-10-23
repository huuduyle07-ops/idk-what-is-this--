"""JAVA.1A report-only controller isolation. Never issues a capability receipt."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import secrets
import tempfile
import threading

from core import candidate_runtime_sandbox as sandbox
from core.runtime_java_controller_diagnostic_probe import diagnostic_source

IMAGE = 'sha256:f6d7dc31a15bb37a618ebed6772beda3de95fdcc3394eb5a1def9b1d20673f7a'
UNRESOLVED = 'RUNTIME_JAVA_1A_CONTROLLER_FAILURE_UNRESOLVED'


def classify(facts, cleanup):
    """Measured ownership precedes classification; absence cannot mean success."""
    if not cleanup or type(facts) is not dict:
        return UNRESOLVED, 'other_measured_controller_failure'
    attempts = facts.get('attempts', [])
    if (facts.get('controller', {}).get('owner') != 'sandbox_container'
            or len(attempts) != 3):
        return UNRESOLVED, 'other_measured_controller_failure'
    if any(a.get('after_cleanup', {}).get('reader_threads_alive', 0) for a in attempts):
        return 'RUNTIME_JAVA_1A_CONTROLLER_THREAD_LEAK_FOUND', 'controller_thread_leak_detected'
    failed = [event for a in attempts for event in a.get('reader_start_events', [])
        if event.get('started') is False]
    if failed:
        # A full-looking PID count alone does not prove a pids controller denial.
        return UNRESOLVED, 'sandbox_controller_thread_failure'
    # Healthy non-Java capture alone cannot bless JAVA.1A (javac is unmeasured).
    return UNRESOLVED, 'java_stage_not_started'


def host_state(readers):
    result = {'pid': os.getpid(), 'python_threads': threading.active_count(),
        'reader_threads_alive': sum(r.is_alive() for r in readers)}
    try:
        import psutil
        process = psutil.Process(os.getpid())
        result['os_threads'] = process.num_threads()
        if os.name == 'nt': result['open_handles'] = process.num_handles()
    except ImportError:
        result['os_threads'] = None
    return result


@contextmanager
def observe_host_readers():
    original = sandbox.Thread
    readers = []

    class Reader(original):
        started_ok = False
        joined_ok = False

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            readers.append(self)

        def start(self):
            super().start()
            self.started_ok = True

        def join(self, *args, **kwargs):
            super().join(*args, **kwargs)
            self.joined_ok = not self.is_alive()

    sandbox.Thread = Reader
    try:
        yield readers
    finally:
        sandbox.Thread = original


def safe_configuration(config, source):
    """Validate exact diagnostic argv, then delegate every frozen policy check."""
    try:
        settings = config['Config']
        if settings['Cmd'] != ['-I', '-S', '-B', '-c', source]: return False
        normalized = {**config, 'Config': {**settings,
            'Cmd': ['-I', '-S', '-B', '-c', sandbox.PROBE_SOURCE, 'boundary']}}
        return sandbox._safe_configuration(normalized, IMAGE)
    except (KeyError, TypeError):
        return False


def invoke_diagnostic(prefix, profile):
    source = diagnostic_source()
    name = 'runtime-java1a-' + secrets.token_hex(12)
    ctl = lambda *args: sandbox._bounded_process((*prefix, *args),
        timeout_ms=8000, stdout_limit=65536)
    facts, cleanup = {}, False
    capture = sandbox._Capture('sandbox_launch_failed', None, b'', b'', False)
    try:
        created = ctl('create', '--name', name, '--pull', 'never', '--interactive',
            '--hostname', 'runtime-sandbox1', '--network', 'none', '--read-only',
            '--user', '65534:65534', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges=true', '--security-opt', 'seccomp=' + str(profile),
            '--cgroupns', 'private', '--ipc', 'none', '--pids-limit', '128',
            '--memory', '128m', '--cpus', '1', '--log-driver', 'none',
            '--tmpfs', '/work:rw,nosuid,nodev,size=32m,mode=1777',
            '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=16m,mode=1777', '--workdir', '/work',
            *(token for key, value in sandbox._WORKLOAD_ENVIRONMENT.items()
                for token in ('--env', key + '=' + value)),
            '--entrypoint', '/usr/local/bin/python', IMAGE, '-I', '-S', '-B', '-c', source)
        if created.status != 'sandbox_completed' or created.exit_code != 0:
            raise ValueError('diagnostic_create_failed')
        inspected = ctl('inspect', name, '--format', '{{json .}}')
        if (inspected.status != 'sandbox_completed' or inspected.exit_code != 0
                or not safe_configuration(json.loads(inspected.stdout), source)):
            raise ValueError('diagnostic_configuration_rejected')

        def stop():
            killed = ctl('kill', name)
            stopped = ctl('inspect', name, '--format', '{{.State.Running}}')
            return (killed.exit_code == 0 and stopped.status == 'sandbox_completed'
                and stopped.stdout.strip() == b'false')

        capture = sandbox._bounded_process((*prefix, 'start', '--attach', '--interactive', name),
            timeout_ms=10000, stdout_limit=8192, stderr_limit=8192,
            on_abort=stop, abort_after_ms=5000)
        if capture.status == 'sandbox_completed' and capture.exit_code == 0:
            facts = json.loads(capture.stdout)
    finally:
        ctl('kill', name)
        removed = ctl('rm', '--force', '--volumes', name)
        absent = ctl('inspect', name, '--format', '{{.State.Running}}')
        cleanup = (removed.status == 'sandbox_completed' and removed.exit_code == 0
            and absent.status == 'sandbox_completed' and absent.exit_code != 0
            and any(s in absent.stderr.lower() for s in (b'no such object', b'no such container')))
    return capture, facts, cleanup


def replay():
    result = {'phase_id': 'RUNTIME.JAVA.1A', 'report_only': True, 'status': UNRESOLVED,
        'runtime_authority': False, 'repository_write_authority': False, 'apply_authority': False,
        'runtime_policy_authorizations_consumed': 0, 'bank_execution_count': 0,
        'behavioral_execution_count': 0, 'reflection_count': 0, 'console_count': 0,
        'java_launch_count': 0, 'compilation_count': 0, 'jvm_fixture_count': 0,
        'seccomp_jvm_causality_proven': False, 'executor_refreshed_or_resumed': False,
        'image_identity': IMAGE, 'seccomp_policy_sha256': sandbox._hash(sandbox._SECCOMP),
        'historical_interpretation': 'RUNTIME_JAVA_1_BLOCKED_SANDBOX_INCOMPATIBLE was an umbrella '
            'blocked outcome. Its measured cause was controller output-reader thread start '
            'failure. No JVM/seccomp incompatibility was proven.'}
    with observe_host_readers() as readers:
        result['host_before'] = host_state(readers)
        descriptor, receipt = sandbox.verify_candidate_runtime_sandbox()
        sandbox.validate_sandbox_descriptor(descriptor, receipt)
        result['sandbox_authentication'] = {'status': receipt.status,
            'descriptor_fingerprint': descriptor.fingerprint,
            'receipt_fingerprint': receipt.fingerprint}
        prefix = sandbox._docker_prefix()
        try:
            if sandbox.get_verified_candidate_runtime_sandbox(descriptor, receipt) is None:
                raise ValueError('frozen_sandbox_not_authenticated')
            image = sandbox._bounded_process((*prefix, 'image', 'inspect', IMAGE,
                '--format', '{{json .}}'), timeout_ms=8000, stdout_limit=65536)
            metadata = json.loads(image.stdout) if image.exit_code == 0 else {}
            if (metadata.get('Id') != IMAGE or metadata.get('Os') != 'linux'
                    or metadata.get('Architecture') != 'amd64'
                    or metadata.get('Config', {}).get('Volumes')):
                raise ValueError('exact_local_image_unavailable_or_ineligible')
            with tempfile.TemporaryDirectory(prefix='runtime-java1a-') as root:
                profile = Path(root) / 'seccomp.json'
                profile.write_text(sandbox._json(sandbox._SECCOMP), encoding='utf-8')
                capture, facts, cleanup = invoke_diagnostic(prefix, profile)
                result.update(measurements=facts, container_cleanup_verified=cleanup,
                    capture_status=capture.status, capture_exit_code=capture.exit_code,
                    bounded_controller_stderr=capture.stderr.decode(errors='replace')[:500])
                result['status'], result['classification'] = classify(facts, cleanup)
            result['temporary_workspace_removed'] = not Path(root).exists()
        except (OSError, ValueError) as error:
            result['diagnostic_error'] = type(error).__name__ + ': ' + str(error)[:200]
        finally:
            remaining = sandbox._bounded_process((*prefix, 'ps', '-a', '--format', '{{.Names}}',
                '--filter', 'name=runtime-java1', '--filter', 'name=runtime-sandbox1'), timeout_ms=8000)
            result['phase_container_count_after_teardown'] = (
                len(remaining.stdout.splitlines()) if remaining.status == 'sandbox_completed'
                and remaining.exit_code == 0 else None)
            result['host_after_cleanup'] = host_state(readers)
            result['host_readers'] = {'created': len(readers),
                'started': sum(r.started_ok for r in readers),
                'joined': sum(r.joined_ok for r in readers),
                'surviving': sum(r.is_alive() for r in readers)}
    return result
