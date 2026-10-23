"""Additive JAVA.1B runtime source; frozen JAVA.1 source stays byte-identical."""
import ast
import base64
import json

from core import candidate_runtime_sandbox as sandbox
from core.java_single_thread_capture import capture_source
from core.sandboxed_java_toolchain_probe import JAVA_PROBE_SOURCE

JAVAC_PATH = '/opt/temurin-26.0.2.1/bin/javac'
JAVAC_SHA256 = 'e21c219e342544cbf107d25e86ed1d809eac6cc57bce8f68750a42783f13e023'

request = {'inputs': [{'path': 'projection.txt',
    'bytes': base64.b64encode(sandbox._FIXTURE).decode()}], 'host_paths': [], 'port': 1}
BOUNDARY_FIXTURE = ('import io,sys\n'
    + 'sys.stdin=io.TextIOWrapper(io.BytesIO(' + repr((json.dumps(request) + '\n').encode()) + '))\n'
    + "sys.argv=['runtime-sandbox1','boundary']\n" + sandbox.PROBE_SOURCE)

OBSERVER_SOURCE = r'''
thread_start_attempts = 0
def forbidden_thread_start(self, *args, **kwargs):
    global thread_start_attempts
    thread_start_attempts += 1
    raise RuntimeError('JAVA.1B controller reader threads forbidden')
threading.Thread.start = forbidden_thread_start
def controller_state():
    return {'pid': os.getpid(), 'python_threads': threading.active_count(),
        'os_threads': len(os.listdir('/proc/self/task')),
        'thread_start_attempts': thread_start_attempts}
controller_deadline = time.monotonic() + 5
'''

RUN_SOURCE = r'''
def run(stage, argv, limit):
    tick = time.perf_counter()
    before = controller_state()
    def started(child):
        facts['toolchain_launch_count'] += 1
        if stage == 'java': facts['synthetic_java_execution_count'] += 1
        try:
            facts['descendants_contained'] &= boundary(child.pid) == parent_boundary
        except OSError:
            facts['descendants_contained'] = False
    captured = capture_process(argv, limit, deadline=controller_deadline, on_start=started)
    result = {key: value for key, value in captured.items() if key not in ('stdout', 'stderr')}
    result.update(argv=argv, stdout_b64=base64.b64encode(captured['stdout']).decode(),
        stderr_b64=base64.b64encode(captured['stderr']).decode(),
        capture_method='single_thread_selector', threads_before=before,
        threads_after=controller_state(), limit_bytes=limit)
    facts['stages'][stage] = result
    timings[stage + '_seconds'] = time.perf_counter() - tick
    return (result['status'] == 'completed' and result['exit_code'] == 0
        and result['cleanup_verified'] and not result['overflow']
        and result['threads_after']['python_threads'] == 1
        and result['threads_after']['os_threads'] == 1
        and thread_start_attempts == 0)
'''


def recovered_java_source():
    """Replace only run(), retaining the original execute() and fixed sequence."""
    tree = ast.parse(JAVA_PROBE_SOURCE)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run')
    lines = JAVA_PROBE_SOURCE.splitlines(keepends=True)
    replacement = capture_source() + OBSERVER_SOURCE + positive_run_source()
    return ''.join(lines[:node.lineno - 1]) + replacement + ''.join(lines[node.end_lineno:])


def positive_run_source():
    """Keep PIDs and capture observations outside the semantic receipt facts."""
    replacement = r'''
    observations = {key: value for key, value in result.items()
        if key not in ('argv', 'stdout_b64', 'stderr_b64')}
    timings.setdefault('capture_observations', []).append({'stage': stage, **observations})
    facts['stages'][stage] = {key: result[key] for key in
        ('exit_code', 'overflow', 'argv', 'stdout_b64', 'stderr_b64')}
    if (result['status'] != 'completed' or not result['cleanup_verified']
        or result['threads_after']['python_threads'] != 1
        or result['threads_after']['os_threads'] != 1 or thread_start_attempts != 0):
        facts['controller_error'] = 'single_thread_capture_incomplete:' + result['status']
'''
    return RUN_SOURCE.replace("    facts['stages'][stage] = result\n", replacement)


def gate_source(mode):
    if mode not in ('non_java', 'javac_version'):
        raise ValueError('fixed_recovery_gate_required')
    boundary = next(ast.get_source_segment(JAVA_PROBE_SOURCE, n)
        for n in ast.parse(JAVA_PROBE_SOURCE).body
        if isinstance(n, ast.FunctionDef) and n.name == 'boundary')
    header = r'''
import base64, hashlib, json, os, subprocess, sys, threading, time
facts = {'stages': {}, 'toolchain_launch_count': 0,
    'synthetic_java_execution_count': 0, 'descendants_contained': True}
timings = {}
'''
    body = r'''
facts['controller_before'] = controller_state()
parent_boundary = boundary(os.getpid())
if MODE == 'non_java':
    run('non_java_boundary', [sys.executable, '-I', '-S', '-B', '-c', BOUNDARY_FIXTURE], 1024)
    for path in ('/work/projection.txt', '/work/workspace-write'):
        if os.path.exists(path): os.unlink(path)
else:
    with open(JAVAC_PATH, 'rb') as binary:
        digest = hashlib.file_digest(binary, 'sha256').hexdigest()
    facts['javac_sha256'] = digest
    if digest == JAVAC_SHA256:
        run('javac_identity', [JAVAC_PATH, '-version'], 1024)
    else:
        facts['controller_error'] = 'exact_javac_hash_mismatch'
facts['controller_after'] = controller_state()
facts['phase_pids_after_cleanup'] = sorted(int(n) for n in os.listdir('/proc') if n.isdigit())[:128]
facts['work_files_after_cleanup'] = sorted(os.listdir('/work'))[:16]
print(json.dumps({'facts': facts, 'timings': timings}, sort_keys=True), flush=True)
'''
    return (header + capture_source() + '\n' + boundary + '\n' + OBSERVER_SOURCE + RUN_SOURCE
        + '\nMODE = ' + repr(mode) + '\nBOUNDARY_FIXTURE = ' + repr(BOUNDARY_FIXTURE)
        + '\nJAVAC_PATH = ' + repr(JAVAC_PATH) + '\nJAVAC_SHA256 = ' + repr(JAVAC_SHA256)
        + '\n' + body)
