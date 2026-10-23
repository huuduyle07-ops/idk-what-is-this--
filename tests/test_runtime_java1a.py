"""JAVA.1A contract negatives; fabricated data never grants runtime capability."""
import ast
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from core import runtime_java_controller_diagnostic as owner
from core import runtime_java_controller_diagnostic_probe as probe
from core.sandboxed_java_toolchain_probe import JAVA_PROBE_SOURCE
from tests.test_runtime_sandbox1 import _safe_config


def measurements(*, fail=True, survivors=0):
    return {'controller': {'owner': 'sandbox_container'}, 'attempts': [
        {'reader_start_events': [{'started': not fail}],
         'after_cleanup': {'reader_threads_alive': survivors}}
        for _ in range(3)]}


def test_exact_capture_functions_are_reused_without_java_execute_sequence():
    original = ast.parse(JAVA_PROBE_SOURCE)
    expected = [ast.get_source_segment(JAVA_PROBE_SOURCE, node) for node in original.body
        if isinstance(node, ast.FunctionDef) and node.name in ('boundary', 'run')]
    assert probe.capture_functions() == '\n'.join(expected)
    assert [node.name for node in ast.parse(probe.capture_functions()).body] == ['boundary', 'run']
    assert 'def execute' not in probe.diagnostic_source()
    assert '/opt/temurin' not in probe.diagnostic_source()
    assert probe.BOUNDARY_FIXTURE.endswith(owner.sandbox.PROBE_SOURCE)
    compile(probe.diagnostic_source(), '<java1a-fixed-diagnostic>', 'exec')


def test_failed_container_reader_is_never_classified_as_host_or_jvm():
    status, classification = owner.classify(measurements(), True)
    assert status == owner.UNRESOLVED
    assert classification == 'sandbox_controller_thread_failure'


def test_surviving_reader_is_reported_as_leak():
    assert owner.classify(measurements(fail=False, survivors=1), True) == (
        'RUNTIME_JAVA_1A_CONTROLLER_THREAD_LEAK_FOUND', 'controller_thread_leak_detected')


@pytest.mark.parametrize('facts,cleanup', [({}, True), (None, True),
    (measurements(), False), ({'attempts': []}, True)])
def test_missing_measurements_or_teardown_cannot_mean_success(facts, cleanup):
    assert owner.classify(facts, cleanup)[0] == owner.UNRESOLVED


def test_non_java_health_never_claims_java_success():
    assert owner.classify(measurements(fail=False), True) == (
        owner.UNRESOLVED, 'java_stage_not_started')


def test_diagnostic_config_delegates_every_frozen_boundary_check():
    config = _safe_config()
    config['Image'] = owner.IMAGE
    source = probe.diagnostic_source()
    config['Config']['Cmd'] = ['-I', '-S', '-B', '-c', source]
    assert owner.safe_configuration(config, source)
    assert not owner.safe_configuration(config, source + '\n')


@pytest.mark.parametrize('section,key,value', [
    ('HostConfig', 'PidsLimit', 256), ('HostConfig', 'Memory', 268435456),
    ('HostConfig', 'NetworkMode', 'host'), ('HostConfig', 'ReadonlyRootfs', False),
    ('HostConfig', 'Binds', ['/host:/work']), ('Config', 'User', '0:0'),
    ('HostConfig', 'SecurityOpt', ['no-new-privileges=true']),
    ('Config', 'Entrypoint', ['/bin/sh']), ('Config', 'Env', [])])
def test_policy_changes_are_rejected(section, key, value):
    config = deepcopy(_safe_config())
    config['Image'] = owner.IMAGE
    source = probe.diagnostic_source()
    config['Config']['Cmd'] = ['-I', '-S', '-B', '-c', source]
    config[section][key] = value
    assert not owner.safe_configuration(config, source)


def test_host_observer_joins_and_restores_original_reader_class():
    original = owner.sandbox.Thread
    with owner.observe_host_readers() as readers:
        reader = owner.sandbox.Thread(target=lambda: None)
        reader.start()
        reader.join(timeout=1)
        assert readers == [reader]
        assert reader.started_ok and reader.joined_ok and not reader.is_alive()
    assert owner.sandbox.Thread is original


def test_historical_thread_site_launches_child_before_first_stdout_start():
    run = next(node for node in ast.parse(JAVA_PROBE_SOURCE).body
        if isinstance(node, ast.FunctionDef) and node.name == 'run')
    starts = [node.lineno for node in ast.walk(run) if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute) and node.func.attr == 'start']
    launches = [node.lineno for node in ast.walk(run) if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute) and node.func.attr == 'Popen']
    assert len(starts) == len(launches) == 1
    assert launches[0] < starts[0]
    assert JAVA_PROBE_SOURCE.splitlines()[starts[0] - 1].strip() == 'for reader in readers: reader.start()'


@pytest.mark.parametrize('failed_reader', [0, 1])
def test_frozen_start_failure_bypasses_its_normal_child_and_reader_cleanup(failed_reader):
    """Control-flow evidence, not a claim that a live reader leak was observed."""
    import base64
    import io
    import threading
    import time

    child = SimpleNamespace(pid=2, stdout=io.BytesIO(), stderr=io.BytesIO())
    events = []

    class Reader:
        def __init__(self, **kwargs):
            self.index = sum(kind == 'create' for kind, _ in events)
            events.append(('create', self.index))

        def start(self):
            events.append(('start', self.index))
            if self.index == failed_reader: raise RuntimeError("can't start new thread")

        def join(self):
            events.append(('join', self.index))

    namespace = {'os': SimpleNamespace(getpid=lambda: 1, environ={}),
        'subprocess': SimpleNamespace(Popen=lambda *args, **kwargs: child, PIPE=-1, DEVNULL=-3),
        'threading': SimpleNamespace(Thread=Reader, Event=threading.Event),
        'time': time, 'base64': base64,
        'facts': {'toolchain_launch_count': 0, 'descendants_contained': True}, 'timings': {}}
    exec(probe.capture_functions(), namespace)
    namespace.update(boundary=lambda pid: 'same-container', parent_boundary='same-container')
    with pytest.raises(RuntimeError, match="can't start new thread"):
        namespace['run']('non_java_boundary', ['fixed-fixture'], 1024)
    assert namespace['facts']['toolchain_launch_count'] == 1
    assert not any(kind == 'join' for kind, _ in events)
    assert not child.stdout.closed and not child.stderr.closed
    child.stdout.close()
    child.stderr.close()


def test_diagnostic_has_no_authorization_or_executor_imports():
    source = Path(owner.__file__).read_text(encoding='utf-8')
    imports = [node for node in ast.walk(ast.parse(source))
        if isinstance(node, (ast.Import, ast.ImportFrom))]
    assert not any('authorization' in ast.unparse(node) or 'executor' in ast.unparse(node)
        for node in imports)
