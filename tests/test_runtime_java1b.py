"""Pure deterministic pipe/poller simulations, never live Java evidence."""
import ast
import base64
from copy import deepcopy
import json
from types import SimpleNamespace
import threading

import pytest

from core import java_single_thread_capture as capture
from core import sandboxed_java_capture_recovery as recovery
from core import sandboxed_java_single_thread_probe as probe
from core.sandboxed_java_toolchain_probe import JAVA_PROBE_SOURCE
from tests.test_runtime_sandbox1 import _safe_config
from tests._preflight_runtime1_guard import no_runtime_effects


@pytest.fixture(autouse=True)
def no_real_runtime():
    with no_runtime_effects(strict=False):
        yield


@pytest.fixture
def capture_monkeypatch(no_real_runtime):
    # Restore simulation overrides before the enclosing effect guard restores
    # real functions. Reversing these exits leaks the guard's temporary mocks.
    with pytest.MonkeyPatch.context() as monkeypatch:
        yield monkeypatch


@pytest.fixture
def simulation(capture_monkeypatch):
    monkeypatch = capture_monkeypatch
    def make(stdout=(b'',), stderr=(b'',), *, exit_code=0, early_exit=False,
            never_exit=False, poll_error=False, register_error=False, blocking_error=False,
            on_start_error=False, cleanup_map_error=False, group_survives=False,
            selector_error=False, launch_error=False):
        events, buffers = [], {101: list(stdout), 102: list(stderr)}
        clock = [0.0]

        def monotonic():
            clock[0] += .001
            return clock[0]

        class Stream:
            closed = False
            def __init__(self, fd): self.fd = fd
            def fileno(self): return self.fd
            def close(self):
                self.closed = True
                events.append(('close', self.fd))

        class Process:
            pid = 12
            returncode = exit_code if early_exit else None
            def __init__(self):
                self.stdout, self.stderr = Stream(101), Stream(102)
            def poll(self):
                if not never_exit and not any(buffers.values()) and self.returncode is None:
                    self.returncode = exit_code
                return self.returncode
            def kill(self):
                events.append(('kill_child', self.pid))
                self.returncode = -9
            def wait(self, timeout):
                events.append(('wait', timeout))
                if self.returncode is None: self.returncode = exit_code
                return self.returncode

        process = Process()
        maps = {}
        poller_created = [False]

        class Poller:
            closed = False
            def register(self, stream, mask, data):
                maps[stream.fd] = SimpleNamespace(fd=stream.fd, fileobj=stream, data=data)
                if register_error and data == 1: raise OSError('partial register')
            def unregister(self, stream):
                events.append(('unregister', stream.fd))
                return maps.pop(stream.fd)
            def get_map(self):
                if cleanup_map_error and any(e[0] == 'wait' for e in events):
                    raise OSError('selector map failure during cleanup')
                return maps
            def select(self, timeout):
                events.append(('poll', timeout))
                if poll_error: raise OSError('poll failed')
                return [(key, 1) for key in maps.values()]
            def close(self):
                self.closed = True
                maps.clear()
                events.append(('close_poller', 0))

        poller = Poller()

        def create_poller():
            if selector_error: raise OSError('selector creation failed')
            poller_created[0] = True
            return poller

        def launch(argv, **kwargs):
            if launch_error: raise OSError('child launch failed')
            events.append(('launch', (argv, kwargs)))
            return process

        def read(fd, size):
            assert 1 <= size <= 256
            events.append(('read', (fd, size)))
            if not buffers[fd]:
                raise BlockingIOError()
            data = buffers[fd].pop(0)
            if isinstance(data, Exception): raise data
            if len(data) > size: buffers[fd].insert(0, data[size:])
            return data[:size]

        def set_blocking(fd, flag):
            assert flag is False
            if blocking_error and fd == 102: raise OSError('partial nonblocking setup')

        def killpg(pid, sig):
            assert pid == process.pid
            events.append(('kill_group' if sig else 'group_check', pid))
            if sig:
                if process.returncode is None: process.returncode = -9
            elif not group_survives:
                raise ProcessLookupError()

        def waitpid(pid, flags):
            assert pid == -process.pid
            raise ChildProcessError()

        monkeypatch.setattr(capture.subprocess, 'Popen', launch)
        monkeypatch.setattr(capture.selectors, 'DefaultSelector', create_poller)
        monkeypatch.setattr(capture.os, 'read', read)
        monkeypatch.setattr(capture.os, 'set_blocking', set_blocking)
        monkeypatch.setattr(capture.os, 'killpg', killpg, raising=False)
        monkeypatch.setattr(capture.os, 'waitpid', waitpid, raising=False)
        monkeypatch.setattr(capture.os, 'WNOHANG', 1, raising=False)
        monkeypatch.setattr(capture.signal, 'SIGKILL', 9, raising=False)
        monkeypatch.setattr(capture.time, 'monotonic', monotonic)
        # No capture case is allowed to construct or start a reader thread.
        monkeypatch.setattr(threading, 'Thread', lambda *a, **k: pytest.fail('thread constructed'))

        def on_start(child):
            if on_start_error: raise ValueError('controller setup failed')

        def run(limit=32, deadline=.2):
            result = capture.capture_process(['fixed-phase-fixture'], limit,
                deadline=deadline, on_start=on_start)
            if result['pid'] is not None:
                assert process.stdout.closed and process.stderr.closed
                assert process.returncode is not None
                assert not maps and (not poller_created[0] or poller.closed)
                assert any(e[0] == 'wait' for e in events)
            return result

        return SimpleNamespace(run=run, events=events, process=process, poller=poller)
    return make


@pytest.mark.parametrize('stdout,stderr,expected_out,expected_err', [
    ((b'hello', b''), (b'',), b'hello', b''),
    ((b'',), (b'error', b''), b'', b'error'),
    ((b'a', b'b', b''), (b'1', b'2', b''), b'ab', b'12')])
def test_stdout_stderr_and_interleaving(simulation, stdout, stderr, expected_out, expected_err):
    result = simulation(stdout, stderr).run()
    assert result['status'] == 'completed'
    assert result['stdout'] == expected_out and result['stderr'] == expected_err
    assert result['eof'] == [True, True] and result['cleanup_verified']


@pytest.mark.parametrize('first', [101, 102])
def test_each_stream_can_reach_eof_first(simulation, first):
    sim = simulation((b'',) if first == 101 else (b'a', b'b', b''),
        (b'',) if first == 102 else (b'1', b'2', b''))
    result = sim.run()
    assert result['status'] == 'completed'
    assert next(fd for event, fd in sim.events if event == 'unregister') == first


def test_child_exit_before_reads_complete_still_drains_both_pipes(simulation):
    result = simulation((b'a', b'b', b''), (b'1', b'2', b''), early_exit=True).run()
    assert result['stdout'] == b'ab' and result['stderr'] == b'12'
    assert result['exit_code'] == 0 and result['cleanup_verified']


@pytest.mark.parametrize('stream', ['stdout', 'stderr'])
def test_independent_hard_caps_kill_and_wait_on_one_extra_byte(simulation, stream):
    sim = simulation(**{stream: (b'X' * 1000, b'')})
    result = sim.run(limit=4)
    assert result['status'] == 'output_limit' and result['overflow']
    assert result[stream] == b'XXXX'
    assert result['read_bytes'][0 if stream == 'stdout' else 1] == 5
    assert result['cleanup_verified']


def test_exact_cap_is_allowed_and_eof_checked_with_one_byte_probe(simulation):
    result = simulation((b'abcd', b'')).run(limit=4)
    assert result['status'] == 'completed' and result['stdout'] == b'abcd'


def test_timeout_even_after_both_streams_close_kills_child(simulation):
    result = simulation(never_exit=True).run(deadline=.02)
    assert result['status'] == 'timeout' and result['timed_out']
    assert result['exit_code'] == -9 and result['cleanup_verified']


def test_inherited_open_pipe_after_child_exit_is_bounded_by_deadline(simulation):
    result = simulation(stdout=(), early_exit=True).run(deadline=.02)
    assert result['status'] == 'timeout' and result['cleanup_verified']


def test_child_crash_preserves_exit_code_and_bounded_diagnostic(simulation):
    result = simulation(stderr=(b'crashed', b''), exit_code=-11, early_exit=True).run()
    assert result['status'] == 'completed' and result['exit_code'] == -11
    assert result['stderr'] == b'crashed' and result['cleanup_verified']


@pytest.mark.parametrize('failure', ['poll_error', 'register_error', 'blocking_error', 'on_start_error', 'selector_error'])
def test_every_exception_after_child_creation_cleans_partial_setup(simulation, failure):
    sim = simulation(**{failure: True})
    result = sim.run()
    assert result['status'] == 'controller_exception'
    assert result['cleanup_verified']
    closed = next(i for i, e in enumerate(sim.events) if e[0] == 'close')
    assert all(i < closed for i, e in enumerate(sim.events) if e[0] == 'unregister')


def test_cleanup_map_error_still_closes_poller_and_both_pipes(simulation):
    result = simulation(cleanup_map_error=True).run()
    assert not result['cleanup_verified']
    assert 'selector_map_failed' in result['cleanup_errors']


def test_surviving_process_group_revokes_cleanup(simulation):
    result = simulation(group_survives=True).run()
    assert not result['cleanup_verified'] and 'process_group_survived' in result['cleanup_errors']


def test_deadline_before_launch_has_zero_processes(simulation):
    sim = simulation()
    result = sim.run(deadline=0)
    assert result['pid'] is None and result['status'] == 'timeout'
    assert not any(e[0] == 'launch' for e in sim.events)


def test_child_launch_exception_leaves_no_resources(simulation):
    result = simulation(launch_error=True).run()
    assert result['status'] == 'controller_exception' and result['pid'] is None
    assert result['cleanup_verified']


def test_retryable_pipe_read_conditions_do_not_lose_bytes(simulation):
    result = simulation((BlockingIOError(), InterruptedError(), b'ok', b'')).run()
    assert result['status'] == 'completed' and result['stdout'] == b'ok'


def test_launch_is_shell_false_closed_environment_and_own_process_group(simulation):
    sim = simulation()
    sim.run()
    argv, kwargs = next(value for event, value in sim.events if event == 'launch')
    assert argv == ['fixed-phase-fixture']
    assert kwargs['shell'] is False and kwargs['start_new_session'] is True
    assert kwargs['cwd'] == '/work' and kwargs['env'] == dict(capture.os.environ)


def test_runtime_source_replaces_only_capture_and_preserves_execute_exactly():
    original, recovered = ast.parse(JAVA_PROBE_SOURCE), ast.parse(probe.recovered_java_source())
    old_execute = next(n for n in original.body if isinstance(n, ast.FunctionDef) and n.name == 'execute')
    new_execute = next(n for n in recovered.body if isinstance(n, ast.FunctionDef) and n.name == 'execute')
    assert ast.dump(old_execute) == ast.dump(new_execute)
    assert ast.get_source_segment(JAVA_PROBE_SOURCE, old_execute) == ast.get_source_segment(probe.recovered_java_source(), new_execute)
    assert 'reader.start()' not in probe.recovered_java_source()
    assert 'communicate(' not in capture.capture_source()
    assert 'asyncio' not in capture.capture_source()
    for mode in ('non_java', 'javac_version'):
        compile(probe.gate_source(mode), '<fixed-java1b-gate>', 'exec')
    compile(probe.recovered_java_source(), '<recovered-java1-controller>', 'exec')


def test_in_memory_binding_restores_historical_owner_even_on_exception():
    source, invoke = recovery.java.JAVA_PROBE_SOURCE, recovery.java._invoke_java
    with pytest.raises(RuntimeError):
        with recovery.recovered_controller_binding():
            assert recovery.java.JAVA_PROBE_SOURCE == probe.recovered_java_source()
            raise RuntimeError('stop')
    assert recovery.java.JAVA_PROBE_SOURCE == source and recovery.java._invoke_java is invoke


@pytest.mark.parametrize('cleanup_verified', [True, False])
def test_positive_path_preserves_receipt_schema_and_rejects_capture_cleanup_failure(cleanup_verified):
    import time
    from tests.test_runtime_java1 import _facts, _pair
    spec = recovery.java.synthetic_java_spec(_pair())
    facts = _facts(spec)
    facts.update(toolchain_launch_count=3, synthetic_java_execution_count=0)
    namespace = {'time': time, 'base64': base64, 'facts': facts, 'timings': {},
        'controller_deadline': 5, 'thread_start_attempts': 0, 'parent_boundary': 'same',
        'boundary': lambda pid: 'same', 'controller_state': lambda: {
            'pid': 1, 'python_threads': 1, 'os_threads': 1, 'thread_start_attempts': 0}}

    def captured(argv, limit, *, deadline, on_start):
        on_start(SimpleNamespace(pid=2))
        return {'status': 'completed', 'pid': 2, 'exit_code': 0, 'overflow': False,
            'cleanup_verified': cleanup_verified, 'stdout': recovery.java.EXPECTED_OUTPUT,
            'stderr': b'', 'timed_out': False, 'eof': [True, True]}

    namespace['capture_process'] = captured
    exec(probe.positive_run_source(), namespace)
    namespace['run']('java', list(spec.runtime_argv), 1024)
    assert set(facts['stages']['java']) == {'exit_code', 'overflow', 'argv', 'stdout_b64', 'stderr_b64'}
    assert 'capture_observations' not in facts
    assert namespace['timings']['capture_observations'][0]['pid'] == 2
    failure = recovery.java._java_failure(outer_capture(), facts, True, spec)
    assert failure == ('' if cleanup_verified else 'sandbox_java_incompatible:controller_error')


def test_positive_binding_refuses_any_other_image_before_launch():
    with recovery.recovered_controller_binding():
        with pytest.raises(recovery.java.SandboxedJavaToolchainError, match='exact_image_required'):
            recovery.java._invoke_java(('fixed-local-docker',), SimpleNamespace(image_identity='sha256:' + '0' * 64))


@pytest.mark.parametrize('section,key,value', [
    ('HostConfig', 'PidsLimit', 256), ('HostConfig', 'Memory', 268435456),
    ('HostConfig', 'NetworkMode', 'host'), ('HostConfig', 'Binds', ['/host:/work']),
    ('HostConfig', 'SecurityOpt', ['seccomp=unconfined']), ('Config', 'User', '0:0')])
def test_recovery_still_rejects_frozen_policy_changes(section, key, value):
    config = deepcopy(_safe_config())
    source = probe.gate_source('non_java')
    config['Image'], config['Config']['Cmd'] = recovery.IMAGE, ['-I', '-S', '-B', '-c', source]
    assert recovery.safe_configuration(config, source)
    config[section][key] = value
    assert not recovery.safe_configuration(config, source)


def stage_facts(mode='javac_version', exit_code=0):
    state = {'python_threads': 1, 'os_threads': 1, 'thread_start_attempts': 0}
    stdout = b'javac 26.0.2.1\n'
    key, argv = 'javac_identity', [probe.JAVAC_PATH, '-version']
    if mode == 'non_java':
        stdout = json.dumps({'manifest': [{'path': 'projection.txt',
            'sha256': recovery.sha256(recovery.sandbox._FIXTURE).hexdigest(),
            'size_bytes': len(recovery.sandbox._FIXTURE)}], 'uid': 65534,
            'host_secret_absent': True, 'environment': recovery.sandbox._WORKLOAD_ENVIRONMENT}).encode()
        key, argv = 'non_java_boundary', ['/usr/local/bin/python', '-I', '-S', '-B', '-c', probe.BOUNDARY_FIXTURE]
    stage = {'status': 'completed', 'pid': 2, 'exit_code': exit_code,
        'cleanup_verified': True, 'overflow': False, 'timed_out': False,
        'eof': [True, True], 'capture_method': 'single_thread_selector',
        'threads_before': state, 'threads_after': dict(state), 'limit_bytes': 1024,
        'stdout_b64': base64.b64encode(stdout).decode(), 'stderr_b64': '', 'argv': argv}
    return {'stages': {key: stage}, 'phase_pids_after_cleanup': [1],
        'work_files_after_cleanup': [], 'toolchain_launch_count': 1, 'descendants_contained': True}


def outer_capture():
    return recovery.sandbox._Capture('sandbox_completed', 0, b'', b'', False, False, True)


def test_native_java_failure_is_distinct_from_controller_recovery():
    assert recovery.classify_gate('javac_version', outer_capture(), stage_facts(exit_code=1), True) == recovery.JAVA_FAILURE
    assert recovery.classify_gate('javac_version', outer_capture(), stage_facts(), True) == recovery.RECOVERED
    assert recovery.classify_gate('non_java', outer_capture(), stage_facts('non_java'), True) == recovery.NON_JAVA_PASS


@pytest.mark.parametrize('change', [
    {'overflow': True}, {'timed_out': True}, {'cleanup_verified': False}, {'pid': None},
    {'eof': [True, False]}, {'argv': ['/bin/sh']}, {'limit_bytes': 2048},
    {'threads_after': {'python_threads': 2, 'os_threads': 2, 'thread_start_attempts': 1}}])
def test_incomplete_or_unbounded_capture_cannot_pass_gate(change):
    facts = stage_facts()
    facts['stages']['javac_identity'].update(change)
    assert recovery.classify_gate('javac_version', outer_capture(), facts, True) != recovery.RECOVERED


@pytest.mark.parametrize('stop_at', ['non_java', 'javac_version'])
def test_live_orchestration_stops_at_first_failed_gate_without_java_continuation(capture_monkeypatch, stop_at):
    monkeypatch = capture_monkeypatch
    calls = []
    descriptor = SimpleNamespace(fingerprint=recovery.SANDBOX_DESCRIPTOR)
    receipt = SimpleNamespace(fingerprint=recovery.SANDBOX_RECEIPT, status='authenticated-test-only')
    monkeypatch.setattr(recovery.sandbox, '_docker_prefix', lambda: ('fixed-local-docker',))
    monkeypatch.setattr(recovery.sandbox, 'verify_candidate_runtime_sandbox', lambda: (descriptor, receipt))
    monkeypatch.setattr(recovery.sandbox, 'validate_sandbox_descriptor', lambda *args: None)
    monkeypatch.setattr(recovery.sandbox, 'get_verified_candidate_runtime_sandbox', lambda *args: object())

    def control(argv, **kwargs):
        if 'image' in argv:
            metadata = {'Id': recovery.IMAGE, 'Os': 'linux', 'Architecture': 'amd64', 'Config': {}}
            return recovery.sandbox._Capture('sandbox_completed', 0, json.dumps(metadata).encode(), b'', False)
        return recovery.sandbox._Capture('sandbox_completed', 0, b'', b'', False)

    def invoke(prefix, profile, mode):
        calls.append(mode)
        facts = stage_facts(mode, exit_code=1 if mode == stop_at else 0)
        return outer_capture(), facts, True

    monkeypatch.setattr(recovery.sandbox, '_bounded_process', control)
    monkeypatch.setattr(recovery, 'invoke_gate', invoke)
    monkeypatch.setattr(recovery.java, 'verify_sandboxed_java_toolchain',
        lambda *args, **kwargs: pytest.fail('continued after failed gate'))
    result = recovery.replay()
    assert calls == (['non_java'] if stop_at == 'non_java' else ['non_java', 'javac_version'])
    assert result['status'] == (recovery.CAPTURE_FAILURE if stop_at == 'non_java' else recovery.JAVA_FAILURE)
    assert result['compile_count'] == result['jvm_fixture_count'] == 0
    assert not any(result[key] for key in ('runtime_authority', 'repository_write_authority', 'apply_authority'))
