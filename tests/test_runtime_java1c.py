"""JAVA.1C guarded authentication, stop gates, exact output and lifecycle tests."""
import ast
import base64
from copy import deepcopy
from dataclasses import replace
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from core import sandboxed_java_positive_continuation as owner
from core import sandboxed_java_positive_probe as probe
from tests._preflight_runtime1_guard import no_runtime_effects
from tests.test_runtime_sandbox1 import _safe_config


@pytest.fixture(autouse=True)
def guarded():
    with no_runtime_effects(strict=False):
        yield


@pytest.fixture
def safe_patch(guarded):
    with pytest.MonkeyPatch.context() as patch:
        yield patch


def capture(**changes):
    return replace(owner.baseline._Capture('sandbox_completed', 0, b'', b'', False, False, True), **changes)


def sandbox_pair():
    return owner.sandbox2._evidence_pair({'status': owner.sandbox2.COMPLETE,
        'stages': [{'mode': m, 'verdict': owner.sandbox2.PASSED} for m in owner.sandbox2.LADDER],
        'cleanup_verified': True})


def facts():
    boundary = {'namespaces': dict.fromkeys(('user', 'mnt', 'net', 'pid', 'ipc', 'cgroup', 'uts'), 'same'),
        'cgroup': '0::/\n'}
    state = {'pid': 1, 'uid': 65534, 'gid': 65534, 'python_threads': 1, 'os_threads': 1,
        'thread_start_attempts': 0, 'capabilities_zero': True, 'no_new_privileges': True,
        'environment': dict(owner.baseline._WORKLOAD_ENVIRONMENT), 'boundary': boundary,
        'pids_max': '128', 'memory_max': '134217728', 'cpu_max': '100000 100000',
        'readonly_root': True, 'work_writable': True, 'tmp_writable': True}
    stages = {}
    for index, (name, argv, limit) in enumerate(owner.INVOCATIONS, 7):
        stdout = {'javac_identity': b'javac 26.0.2.1\n', 'java': probe.EXPECTED_OUTPUT}.get(name, b'')
        stderr = b'openjdk version "26.0.2.1"\n' if name == 'java_identity' else b''
        stages[name] = {'status': 'completed', 'pid': index, 'exit_code': 0,
            'cleanup_verified': True, 'overflow': False, 'timed_out': False,
            'eof': [True, True], 'capture_method': 'single_thread_selector',
            'threads_before': deepcopy(state), 'threads_after': deepcopy(state),
            'limit_bytes': limit, 'stdout_b64': base64.b64encode(stdout).decode(),
            'stderr_b64': base64.b64encode(stderr).decode(), 'argv': list(argv),
            'child_boundary': deepcopy(boundary), 'child_waited': True, 'pipes_closed': True,
            'selector_cleanup_verified': True, 'cleanup_errors': [], 'controller_error': ''}
    rows = [{'path': 'JavaSandboxProbe.java', 'kind': 'file', 'sha256': probe.SOURCE_SHA256,
        'size_bytes': len(probe.JAVA_SOURCE)}, {'path': 'classes', 'kind': 'directory'},
        {'path': 'classes/JavaSandboxProbe.class', 'kind': 'file', 'sha256': 'a' * 64, 'size_bytes': 123}]
    return {'controller_before': state, 'controller_after': deepcopy(state), 'stages': stages,
        'phase_pids_after_cleanup': [1], 'descendants_contained': True, 'work_before': [],
        'source_readback_exact': True, 'source_sha256': probe.SOURCE_SHA256,
        'source_size_bytes': len(probe.JAVA_SOURCE), 'javac_binary_sha256': probe.JAVAC_SHA256,
        'java_binary_sha256': probe.JAVA_SHA256, 'class_manifest': [deepcopy(rows[2])],
        'work_after_compile': rows, 'work_after_runtime': deepcopy(rows), 'unexpected_output_files': [],
        'toolchain_launch_count': 2, 'synthetic_java_execution_count': 1}


def test_frozen_source_and_fixed_invocations_and_selector_are_preserved():
    assert owner.sha256(probe.JAVA_SOURCE).hexdigest() == probe.SOURCE_SHA256
    assert len(probe.JAVA_SOURCE) == 129
    assert probe.COMPILE_ARGV == (probe.JAVAC_PATH, *owner.recovery.java.COMPILE_ARGUMENTS)
    assert probe.RUNTIME_ARGV == (probe.JAVA_PATH, *owner.recovery.java.RUNTIME_ARGUMENTS)
    source = probe.source()
    compile(source, '<fixed-java1c>', 'exec')
    from core.java_single_thread_capture import capture_source
    assert capture_source() in source
    assert 'reader.start()' not in source and 'communicate(' not in source
    assert 'shell=False' in source and 'sys.stdin' not in source
    with pytest.raises(TypeError): probe.source(b'arbitrary Java')
    with pytest.raises(TypeError): owner.verify({'verified': True})


def test_positive_evaluation_is_pure_and_does_not_issue_evidence():
    assert owner.evaluate(capture(), facts(), True) == (owner.COMPLETE, 'exact_frozen_java_fixture_verified')


def progress_bytes(measurements):
    rows = []
    for name, _, _ in owner.INVOCATIONS:
        s = measurements['stages'][name]
        rows.extend([{'event': 'started', 'stage': name, 'pid': s['pid']},
            {'event': 'completed', 'stage': name, 'pid': s['pid'],
                'exit_code': s['exit_code'], 'cleanup_verified': s['cleanup_verified']}])
    return ('\n'.join(json.dumps(r) for r in rows) + '\n').encode()


def test_bounded_controller_progress_agrees_with_final_child_measurements():
    measurements = facts()
    raw = progress_bytes(measurements)
    assert len(raw) < owner.STREAM_LIMIT
    assert len(owner._progress(raw)) == 4
    assert owner.evaluate(capture(stderr=raw), measurements, True)[0] == owner.COMPLETE
    assert len(owner._progress(raw.splitlines()[0])) == 1  # Survives a timeout after launch.


@pytest.mark.parametrize('mutation', ['duplicate', 'arbitrary', 'pid', 'exit', 'extra', 'oversize'])
def test_forged_or_inconsistent_controller_progress_cannot_verify(mutation):
    measurements = facts()
    raw = progress_bytes(measurements)
    if mutation == 'duplicate': raw += raw
    if mutation == 'arbitrary': raw = b'warning\n'
    if mutation == 'pid': raw = raw.replace(b'"pid": 7', b'"pid": 99')
    if mutation == 'exit': raw = raw.replace(b'"exit_code": 0', b'"exit_code": 1')
    if mutation == 'extra': raw = raw.replace(b'"stage": "javac"', b'"stage": "other"')
    if mutation == 'oversize': raw = b'X' * (owner.STREAM_LIMIT + 1)
    assert owner.evaluate(capture(stderr=raw), measurements, True)[0] != owner.COMPLETE


@pytest.mark.parametrize('mutation', ['json', 'unsigned', 'tamper', 'other_epoch', 'classification', 'image', 'policy'])
def test_sandbox_authentication_rejects_forgery_and_other_bindings(mutation):
    sd, sr = sandbox_pair()
    if mutation == 'json': sd, sr = sd.as_dict(), sr.as_dict()
    if mutation == 'unsigned': sr = replace(sr, _signature='')
    if mutation == 'tamper': sd = replace(sd, verification_receipt_fingerprint='0' * 64)
    if mutation == 'other_epoch': sd = SimpleNamespace(**sd.as_dict())
    if mutation == 'classification': sr = replace(sr, compatibility_classification='executor_eligible')
    if mutation == 'image': object.__setattr__(sr, 'image_identity', 'sha256:' + '0' * 64)
    if mutation == 'policy': object.__setattr__(sr, 'seccomp_policy_sha256', owner.sandbox2.BASELINE_POLICY_SHA256)
    with pytest.raises(ValueError): owner.authenticate_sandbox2(sd, sr)


@pytest.mark.parametrize('key,value', [('source_sha256', '0' * 64), ('source_size_bytes', 130),
    ('source_readback_exact', False), ('work_before', ['injected']),
    ('javac_binary_sha256', '0' * 64), ('java_binary_sha256', '0' * 64)])
def test_source_and_binary_mismatches_fail_closed(key, value):
    changed = facts()
    changed[key] = value
    assert owner.evaluate(capture(), changed, True)[0] in (owner.COMPILE_FAILURE, owner.AUTHENTICATION)


@pytest.mark.parametrize('key,value', [('uid', 0), ('gid', 0), ('python_threads', 2),
    ('os_threads', 2), ('thread_start_attempts', 1), ('capabilities_zero', False),
    ('no_new_privileges', False), ('pids_max', '129'), ('memory_max', '268435456'),
    ('cpu_max', '200000 100000'), ('readonly_root', False), ('environment', {})])
def test_containment_or_controller_regression_revokes_verification(key, value):
    changed = facts()
    changed['controller_after'][key] = value
    assert owner.evaluate(capture(), changed, True)[0] == owner.SANDBOX_REGRESSION


@pytest.mark.parametrize('name', ['javac', 'java'])
@pytest.mark.parametrize('change', [{'exit_code': 1}, {'overflow': True}, {'timed_out': True},
    {'argv': ['/bin/sh']}, {'eof': [True, False]}, {'limit_bytes': 4096}])
def test_each_stage_failure_has_typed_blocked_result(name, change):
    changed = facts()
    changed['stages'][name].update(change)
    assert owner.evaluate(capture(), changed, True)[0] == (owner.COMPILE_FAILURE if name == 'javac' else owner.RUNTIME_FAILURE)


@pytest.mark.parametrize('stream,data', [('stdout', b'JAVA_SANDBOX_OK\n'), ('stdout', b' JAVA_SANDBOX_OK'),
    ('stdout', b'JAVA_SANDBOX_OK\x00'), ('stdout', b''), ('stderr', b'warning\n')])
def test_runtime_output_is_compared_as_exact_bytes_without_normalization(stream, data):
    changed = facts()
    changed['stages']['java'][stream + '_b64'] = base64.b64encode(data).decode()
    assert owner.evaluate(capture(), changed, True)[0] == owner.RUNTIME_FAILURE


@pytest.mark.parametrize('mutation', ['extra', 'missing', 'symlink', 'empty', 'oversize', 'digest', 'source', 'runtime'])
def test_class_manifest_requires_exact_ephemeral_output(mutation):
    changed = facts()
    if mutation == 'extra': changed['unexpected_output_files'] = ['classes/Extra.class']
    if mutation == 'missing': changed['class_manifest'] = []
    if mutation == 'symlink': changed['work_after_compile'][2]['kind'] = 'other'
    if mutation == 'empty': changed['work_after_compile'][2]['size_bytes'] = 0
    if mutation == 'oversize': changed['work_after_compile'][2]['size_bytes'] = 32769
    if mutation == 'digest': changed['work_after_compile'][2]['sha256'] = 'not-a-digest'
    if mutation == 'source': changed['work_after_compile'][0]['sha256'] = '0' * 64
    if mutation == 'runtime': changed['work_after_runtime'][2]['sha256'] = '0' * 64
    assert owner.evaluate(capture(), changed, True)[0] != owner.COMPLETE


@pytest.mark.parametrize('mutation', ['container', 'process', 'capture', 'fds', 'selector', 'wait', 'error'])
def test_every_cleanup_failure_revokes_positive_verification(mutation):
    changed = facts()
    if mutation == 'process': changed['phase_pids_after_cleanup'].append(7)
    if mutation == 'capture': changed['stages']['java']['cleanup_verified'] = False
    if mutation == 'fds': changed['stages']['java']['pipes_closed'] = False
    if mutation == 'selector': changed['stages']['java']['selector_cleanup_verified'] = False
    if mutation == 'wait': changed['stages']['javac']['child_waited'] = False
    if mutation == 'error': changed['stages']['javac']['cleanup_errors'] = ['process_group_survived']
    assert owner.evaluate(capture(), changed, mutation != 'container')[0] == owner.CLEANUP_FAILURE


def safe_config():
    config = _safe_config()
    config['Image'] = owner.IMAGE
    config['Config']['Cmd'] = ['-I', '-S', '-B', '-c', probe.source()]
    config['HostConfig']['SecurityOpt'] = ['no-new-privileges=true', 'seccomp=' + owner.sandbox2.POLICY_BYTES.decode()]
    return config


@pytest.mark.parametrize('section,key,value', [('HostConfig', 'NetworkMode', 'host'),
    ('HostConfig', 'Binds', ['/host:/work']), ('HostConfig', 'ReadonlyRootfs', False),
    ('HostConfig', 'PidsLimit', 256), ('HostConfig', 'Memory', 268435456),
    ('HostConfig', 'NanoCpus', 2000000000), ('HostConfig', 'CapAdd', ['SYS_ADMIN']),
    ('HostConfig', 'SecurityOpt', ['seccomp=unconfined']), ('Config', 'User', '0:0'),
    ('Config', 'Env', ['PATH=/bin']), ('Config', 'Cmd', ['/bin/sh'])])
def test_inspection_rejects_each_policy_expansion(section, key, value):
    config = safe_config()
    assert owner.safe_configuration(config)
    config[section][key] = value
    assert not owner.safe_configuration(config)


def stub_verification(patch, *, changed=None, count=0, cleanup=True):
    sd, sr = sandbox_pair()
    from tests.test_runtime_java1b import stage_facts
    compiler = stage_facts()
    runtime = stage_facts()
    runtime['stages']['javac_identity']['argv'] = [probe.JAVA_PATH, '-version']
    live = {'stages': [{'mode': 'javac_version', 'facts': compiler}, {'mode': 'java_version', 'facts': runtime}]}
    patch.setattr(owner, '_obtain_live_sandbox2', lambda: (sd, sr, live))
    patch.setattr(owner.baseline, '_docker_prefix', lambda: ('fixed-docker',))
    def control(argv, **kwargs):
        if 'image' in argv:
            return capture(stdout=json.dumps({'Id': owner.IMAGE, 'Os': 'linux', 'Architecture': 'amd64', 'Config': {}}).encode())
        return capture(stdout=b'leftover\n' * count)
    patch.setattr(owner.baseline, '_bounded_process', control)
    patch.setattr(owner, '_invoke', lambda *args: (capture(), changed or facts(), cleanup, True))
    return sd, sr


def test_new_authenticated_pair_binds_fresh_sandbox_and_pure_compatibility(safe_patch):
    sd, sr = stub_verification(safe_patch)
    descriptor, receipt, report = owner.verify()
    assert owner.validate_descriptor(descriptor, receipt) is descriptor
    assert report['status'] == owner.COMPLETE and report['pure_executor_compatibility']
    with no_runtime_effects(strict=True):
        assert owner.java_toolchain_satisfies_executor_runtime(descriptor, receipt, sd, sr)
    assert receipt.sandbox_descriptor_fingerprint == sd.fingerprint
    assert sd.fingerprint != owner.HISTORICAL_DESCRIPTOR  # Snapshot IDs are measured per run.
    for value in (descriptor, receipt):
        assert '_signature' not in value.as_dict()
        assert all(value.as_dict()[k] is False for k in owner.sandbox2.AUTHORITIES)
    for key in ('available', 'verified', 'sandbox_compatibility', 'source_projection_supported', 'class_output_projection_supported'):
        assert descriptor.as_dict()[key] is True
    assert report['runtime_policy_authorizations_consumed'] == report['bank_execution_count'] == report['behavioral_execution_count'] == 0
    assert not report['executor_refreshed_or_resumed']
    assert not owner.recovery.java.java_toolchain_satisfies_executor_runtime(descriptor, sd)
    assert not owner.java_toolchain_satisfies_executor_runtime(descriptor.as_dict(), receipt.as_dict(), sd, sr)
    with pytest.raises(ValueError): owner.validate_receipt(replace(receipt, class_sha256='0' * 64))
    with pytest.raises(ValueError): owner.validate_descriptor(replace(descriptor, _signature=''), receipt)


@pytest.mark.parametrize('count,cleanup', [(1, True), (0, False)])
def test_final_cleanup_failure_never_issues_descriptor(safe_patch, count, cleanup):
    stub_verification(safe_patch, count=count, cleanup=cleanup)
    descriptor, receipt, report = owner.verify()
    assert descriptor is receipt is None
    assert report['status'] == owner.CLEANUP_FAILURE and not report['pure_executor_compatibility']


def test_authentication_failure_cannot_reach_java_or_issue_descriptor(safe_patch):
    def unauthenticated(): raise ValueError('sandbox2_receipt_unauthenticated')
    safe_patch.setattr(owner, '_obtain_live_sandbox2', unauthenticated)
    safe_patch.setattr(owner.baseline, '_docker_prefix', lambda: ())
    safe_patch.setattr(owner, '_invoke', lambda *args: pytest.fail('Java launched without authentication'))
    descriptor, receipt, report = owner.verify()
    assert descriptor is receipt is None and report['status'] == owner.AUTHENTICATION
    assert report['compile_count'] == report['jvm_fixture_count'] == 0


def test_inconclusive_outer_timeout_reports_unknown_counts_and_unproven_child_cleanup(safe_patch):
    stub_verification(safe_patch)
    safe_patch.setattr(owner, '_invoke', lambda *args: (
        capture(status='sandbox_timeout', exit_code=1, termination_within_deadline=False), {}, True, True))
    descriptor, receipt, report = owner.verify()
    assert descriptor is receipt is None and report['status'] == owner.CLEANUP_FAILURE
    assert report['compile_count'] is report['jvm_fixture_count'] is None
    assert not report['cleanup_verified'] and report['container_cleanup_verified']


@pytest.mark.parametrize('inspection,kill_error', [(True, False), (False, False), (True, True)])
def test_invoke_inspects_before_start_and_removes_even_after_kill_exception(safe_patch, inspection, kill_error):
    calls = []
    def control(argv, **kwargs):
        calls.append(argv)
        if 'create' in argv: return capture()
        if 'start' in argv: return capture(stdout=json.dumps({'facts': facts()}).encode())
        if 'kill' in argv and kill_error: raise OSError('kill unavailable')
        if 'inspect' in argv:
            if argv[-1] == '{{json .}}':
                config = safe_config()
                if not inspection: config['HostConfig']['NetworkMode'] = 'host'
                return capture(stdout=json.dumps(config).encode())
            return capture(exit_code=1, stderr=b'No such container')
        return capture()
    safe_patch.setattr(owner.baseline, '_bounded_process', control)
    _, _, cleaned, inspected = owner._invoke(('fixed-docker',), Path('fixed-phase-profile.json'))
    assert cleaned and inspected is inspection
    assert any('rm' in argv for argv in calls)
    assert any('start' in argv for argv in calls) is inspection
    created = next(a for a in calls if 'create' in a)
    assert '--network' in created and created[created.index('--network') + 1] == 'none'
    assert '--mount' not in created and '--volume' not in created
    assert created[-1] == probe.source()


@pytest.mark.parametrize('stop', ['source', 'javac', 'extra_class', 'empty_class'])
def test_fixed_controller_stops_before_runtime_on_any_projection_or_compile_failure(stop):
    # Execute the actual fixed execute() with an in-memory filesystem and
    # capture substitute; the global audit guard still forbids real processes.
    tree = ast.parse(probe.BODY)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'execute')
    namespace = {k: getattr(probe, k) for k in ('JAVA_SOURCE', 'SOURCE_SHA256', 'JAVAC_PATH',
        'JAVAC_SHA256', 'JAVA_PATH', 'JAVA_SHA256', 'COMPILE_ARGV', 'RUNTIME_ARGV')}
    calls, records, projected = [], {'stages': {}}, [False]
    class Hash:
        file_digest = staticmethod(lambda file, algorithm: SimpleNamespace(hexdigest=lambda: {
            probe.JAVAC_PATH: probe.JAVAC_SHA256, probe.JAVA_PATH: probe.JAVA_SHA256}[file.name]))
        sha256 = staticmethod(owner.sha256)
    def opened(path, mode):
        value = io.BytesIO(probe.JAVA_SOURCE if stop != 'source' else b'changed')
        value.name = path
        return value
    def rows():
        if not projected[0]: return []
        result = deepcopy(facts()['work_after_compile'])
        if stop == 'extra_class': result.append({'path': 'classes/Extra.class', 'kind': 'file'})
        if stop == 'empty_class': result[2]['size_bytes'] = 0
        return result
    def run(stage, *args):
        calls.append(stage)
        projected[0] = stage == 'javac'
        return stage != stop
    namespace.update(facts=records, controller_state=lambda: {}, manifest=rows,
        hashlib=Hash, open=opened, os=SimpleNamespace(mkdir=lambda path: None), run=run)
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<fixed-execute>', 'exec'), namespace)
    namespace['execute']()
    assert 'java' not in calls
    if stop == 'source': assert calls == []
    if stop == 'javac': assert calls == ['javac']
