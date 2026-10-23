"""JAVA.1B fixed recovery gates and handoff to the existing Java verifier."""
from contextlib import contextmanager
from hashlib import sha256
import json
from pathlib import Path
import secrets
import tempfile

from core import candidate_runtime_sandbox as sandbox
from core import sandboxed_java_toolchain as java
from core.sandboxed_java_single_thread_probe import (
    BOUNDARY_FIXTURE, JAVAC_PATH, gate_source, recovered_java_source)

IMAGE = 'sha256:f6d7dc31a15bb37a618ebed6772beda3de95fdcc3394eb5a1def9b1d20673f7a'
SANDBOX_DESCRIPTOR = '4b36a9f12aa4411bc41f869f437d66a470b5eb36403b90147091d2555859bf9c'
SANDBOX_RECEIPT = '53f7dcd60f46cda18adbd8037d996d7beb4e7fa7df4e6778cff69a82935426e9'
SECCOMP_HASH = '855462482bcdd76cd2b52d8cdd40683af1165a47c041d687bc64723acc4e1447'
RECOVERED = 'RUNTIME_JAVA_1B_CONTROLLER_RECOVERED'
CAPTURE_FAILURE = 'RUNTIME_JAVA_1B_CAPTURE_FAILURE'
CLEANUP_FAILURE = 'RUNTIME_JAVA_1B_CLEANUP_FAILURE'
JAVA_FAILURE = 'RUNTIME_JAVA_1B_JAVA_STAGE_REACHED_WITH_MEASURED_FAILURE'
NON_JAVA_PASS = 'non_java_capture_verified'


def safe_configuration(config, source):
    try:
        settings = config['Config']
        if settings['Cmd'] != ['-I', '-S', '-B', '-c', source]: return False
        normalized = {**config, 'Config': {**settings,
            'Cmd': ['-I', '-S', '-B', '-c', sandbox.PROBE_SOURCE, 'boundary']}}
        return sandbox._safe_configuration(normalized, IMAGE)
    except (KeyError, TypeError):
        return False


def capture_healthy(stage):
    try:
        return (stage['status'] == 'completed' and stage['pid'] > 1
            and stage['cleanup_verified'] is True and stage['overflow'] is False
            and stage['timed_out'] is False and stage['eof'] == [True, True]
            and stage['capture_method'] == 'single_thread_selector'
            and all(stage[key]['python_threads'] == stage[key]['os_threads'] == 1
                and stage[key]['thread_start_attempts'] == 0
                for key in ('threads_before', 'threads_after'))
            and all(len(java._stage_bytes(stage, stream)) <= stage['limit_bytes']
                for stream in ('stdout', 'stderr')))
    except (KeyError, TypeError, ValueError):
        return False


def classify_gate(mode, capture, facts, container_cleanup):
    """Pure report predicate. Never issues a runtime capability or consent."""
    if mode not in ('non_java', 'javac_version'):
        return CAPTURE_FAILURE
    if not container_cleanup:
        return CLEANUP_FAILURE
    stage = facts.get('stages', {}).get('non_java_boundary' if mode == 'non_java' else 'javac_identity', {})
    if stage.get('cleanup_verified') is False or facts.get('phase_pids_after_cleanup') != [1]:
        return CLEANUP_FAILURE
    expected_argv = (['/usr/local/bin/python', '-I', '-S', '-B', '-c', BOUNDARY_FIXTURE]
        if mode == 'non_java' else [JAVAC_PATH, '-version'])
    if (capture.status != 'sandbox_completed' or capture.exit_code != 0
            or not capture.termination_within_deadline or not capture_healthy(stage)
            or stage.get('argv') != expected_argv or stage.get('limit_bytes') != 1024):
        return CAPTURE_FAILURE
    if mode == 'non_java':
        try:
            boundary = json.loads(java._stage_bytes(stage, 'stdout'))
            expected = [{'path': 'projection.txt', 'sha256': sha256(sandbox._FIXTURE).hexdigest(),
                'size_bytes': len(sandbox._FIXTURE)}]
            passed = (stage['exit_code'] == 0 and boundary['manifest'] == expected
                and boundary['uid'] == 65534 and boundary['host_secret_absent'] is True
                and boundary['environment'] == sandbox._WORKLOAD_ENVIRONMENT
                and facts['descendants_contained'] is True
                and not java._stage_bytes(stage, 'stderr')
                and facts['work_files_after_cleanup'] == [])
            return NON_JAVA_PASS if passed else CAPTURE_FAILURE
        except (KeyError, TypeError, ValueError):
            return CAPTURE_FAILURE
    if stage['exit_code'] != 0:
        return JAVA_FAILURE
    return RECOVERED if (facts.get('descendants_contained') is True
        and (java._stage_bytes(stage, 'stdout') + java._stage_bytes(stage, 'stderr')).strip()) else CAPTURE_FAILURE


def invoke_gate(prefix, profile, mode):
    source = gate_source(mode)
    name = 'runtime-java1b-' + secrets.token_hex(12)
    ctl = lambda *args: sandbox._bounded_process((*prefix, *args), timeout_ms=8000, stdout_limit=65536)
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
            raise ValueError('fixed_recovery_container_create_failed')
        inspected = ctl('inspect', name, '--format', '{{json .}}')
        if (inspected.status != 'sandbox_completed' or inspected.exit_code != 0
                or not safe_configuration(json.loads(inspected.stdout), source)):
            raise ValueError('frozen_recovery_configuration_rejected')

        def stop():
            killed = ctl('kill', name)
            stopped = ctl('inspect', name, '--format', '{{.State.Running}}')
            return (killed.exit_code == 0 and stopped.status == 'sandbox_completed'
                and stopped.stdout.strip() == b'false')

        capture = sandbox._bounded_process((*prefix, 'start', '--attach', '--interactive', name),
            timeout_ms=10000, stdout_limit=8192, stderr_limit=8192,
            on_abort=stop, abort_after_ms=5000)
        if capture.status == 'sandbox_completed' and capture.exit_code == 0:
            facts = json.loads(capture.stdout)['facts']
    except (OSError, ValueError, KeyError) as error:
        facts['outer_controller_error'] = type(error).__name__ + ': ' + str(error)[:200]
    finally:
        ctl('kill', name)
        removed = ctl('rm', '--force', '--volumes', name)
        absent = ctl('inspect', name, '--format', '{{.State.Running}}')
        cleanup = (removed.status == 'sandbox_completed' and removed.exit_code == 0
            and absent.status == 'sandbox_completed' and absent.exit_code != 0
            and any(s in absent.stderr.lower() for s in (b'no such object', b'no such container')))
    return capture, facts, cleanup


@contextmanager
def recovered_controller_binding():
    """Bind new capture in memory; retain every historical source-file byte."""
    old_source, old_invoke = java.JAVA_PROBE_SOURCE, java._invoke_java

    def exact_image_only(prefix, artifact, *args):
        if artifact.image_identity != IMAGE:
            raise java.SandboxedJavaToolchainError('java1b_exact_image_required')
        return old_invoke(prefix, artifact, *args)

    java.JAVA_PROBE_SOURCE = recovered_java_source()
    java._invoke_java = exact_image_only
    try:
        yield
    finally:
        java.JAVA_PROBE_SOURCE, java._invoke_java = old_source, old_invoke


def replay():
    result = {'phase_id': 'RUNTIME.JAVA.1B', 'report_only': True, 'status': CAPTURE_FAILURE,
        'runtime_authority': False, 'repository_write_authority': False, 'apply_authority': False,
        'runtime_policy_authorizations_consumed': 0, 'bank_execution_count': 0,
        'behavioral_execution_count': 0, 'reflection_count': 0, 'console_count': 0,
        'compile_count': 0, 'jvm_fixture_count': 0, 'java_version_launch_count': 0,
        'executor_refreshed_or_resumed': False, 'image_identity': IMAGE,
        'seccomp_policy_sha256': sandbox._hash(sandbox._SECCOMP), 'gates': []}
    prefix = sandbox._docker_prefix()
    try:
        descriptor, receipt = sandbox.verify_candidate_runtime_sandbox()
        sandbox.validate_sandbox_descriptor(descriptor, receipt)
        result['sandbox_authentication'] = {'status': receipt.status,
            'descriptor_fingerprint': descriptor.fingerprint, 'receipt_fingerprint': receipt.fingerprint}
        if (sandbox.get_verified_candidate_runtime_sandbox(descriptor, receipt) is None
                or descriptor.fingerprint != SANDBOX_DESCRIPTOR or receipt.fingerprint != SANDBOX_RECEIPT
                or sandbox._hash(sandbox._SECCOMP) != SECCOMP_HASH):
            raise ValueError('exact_frozen_sandbox_authentication_required')
        image = sandbox._bounded_process((*prefix, 'image', 'inspect', IMAGE, '--format', '{{json .}}'),
            timeout_ms=8000, stdout_limit=65536)
        metadata = json.loads(image.stdout) if image.exit_code == 0 else {}
        if (metadata.get('Id') != IMAGE or metadata.get('Os') != 'linux'
                or metadata.get('Architecture') != 'amd64' or metadata.get('Config', {}).get('Volumes')):
            raise ValueError('exact_local_java_image_required')
        with tempfile.TemporaryDirectory(prefix='runtime-java1b-') as root:
            profile = Path(root) / 'seccomp.json'
            profile.write_text(sandbox._json(sandbox._SECCOMP), encoding='utf-8')
            for mode in ('non_java', 'javac_version'):
                capture, facts, cleanup = invoke_gate(prefix, profile, mode)
                status = classify_gate(mode, capture, facts, cleanup)
                result['gates'].append({'mode': mode, 'status': status, 'facts': facts,
                    'container_cleanup_verified': cleanup, 'outer_capture_status': capture.status,
                    'outer_stderr': capture.stderr.decode(errors='replace')[:500]})
                result['status'] = CAPTURE_FAILURE if status == NON_JAVA_PASS else status
                if mode == 'javac_version':
                    result['java_version_launch_count'] = facts.get('toolchain_launch_count', 0)
                if status != (NON_JAVA_PASS if mode == 'non_java' else RECOVERED): break
        result['temporary_workspace_removed'] = not Path(root).exists()
        if result['status'] == RECOVERED and len(result['gates']) == 2:
            with recovered_controller_binding():
                diagnostics = {}
                java_descriptor, java_receipt = java.verify_sandboxed_java_toolchain(
                    descriptor, receipt, diagnostics=diagnostics)
                java.validate_java_descriptor(java_descriptor, java_receipt)
                result['java1_continuation'] = {'descriptor': java_descriptor.as_dict(),
                    'verification_receipt': java_receipt.as_dict(), 'diagnostics': diagnostics}
                canonical = dict(java_receipt.canonical_results)
                stages = json.loads(canonical.get('stages', '{}'))
                result['compile_count'] = int('javac' in stages)
                result['jvm_fixture_count'] = int('java' in stages)
                if java_receipt.status != java.COMPLETE:
                    result['status'] = JAVA_FAILURE
    except (OSError, ValueError) as error:
        result['controller_error'] = type(error).__name__ + ': ' + str(error)[:200]
    finally:
        remaining = sandbox._bounded_process((*prefix, 'ps', '-a', '--format', '{{.Names}}',
            '--filter', 'name=runtime-java1', '--filter', 'name=runtime-sandbox1'), timeout_ms=8000)
        result['phase_container_count_after_teardown'] = (len(remaining.stdout.splitlines())
            if remaining.status == 'sandbox_completed' and remaining.exit_code == 0 else None)
        if result['phase_container_count_after_teardown'] != 0:
            result['status'] = CLEANUP_FAILURE
    return result
