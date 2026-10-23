"""JAVA.1C fixed controller, reusing JAVA.1B's single-thread selector capture."""
from core.java_single_thread_capture import capture_source
from core.sandboxed_java_single_thread_probe import JAVAC_PATH, JAVAC_SHA256
from core.thread_compatible_runtime_sandbox_probe import JAVA_PATH, JAVA_SHA256
from core.sandboxed_java_toolchain_probe import (
    JAVA_SOURCE, EXPECTED_OUTPUT, COMPILE_ARGUMENTS, RUNTIME_ARGUMENTS)

SOURCE_SHA256 = '3975c5e03edb79439d6146b7714a6d3c31af86ce42f05624cdf6c28f69b4e224'
COMPILE_ARGV = (JAVAC_PATH, *COMPILE_ARGUMENTS)
RUNTIME_ARGV = (JAVA_PATH, *RUNTIME_ARGUMENTS)

BODY = r'''
thread_start_attempts = 0
def forbidden_thread_start(self, *args, **kwargs):
    global thread_start_attempts
    thread_start_attempts += 1
    raise RuntimeError('JAVA.1C controller reader threads forbidden')
threading.Thread.start = forbidden_thread_start
controller_deadline = time.monotonic() + 5
facts = {'stages': {}, 'class_manifest': [], 'toolchain_launch_count': 0,
    'synthetic_java_execution_count': 0, 'descendants_contained': True}
def boundary(pid):
    return {'namespaces': {n: os.readlink('/proc/' + str(pid) + '/ns/' + n)
        for n in ('user', 'mnt', 'net', 'pid', 'ipc', 'cgroup', 'uts')},
        'cgroup': open('/proc/' + str(pid) + '/cgroup').read()}
def controller_state():
    status = open('/proc/self/status').read()
    return {'pid': os.getpid(), 'uid': os.getuid(), 'gid': os.getgid(),
        'python_threads': threading.active_count(),
        'os_threads': len(os.listdir('/proc/self/task')),
        'thread_start_attempts': thread_start_attempts,
        'capabilities_zero': 'CapEff:\t0000000000000000' in status,
        'no_new_privileges': 'NoNewPrivs:\t1' in status,
        'environment': dict(os.environ), 'boundary': boundary(os.getpid()),
        'pids_max': open('/sys/fs/cgroup/pids.max').read().strip(),
        'memory_max': open('/sys/fs/cgroup/memory.max').read().strip(),
        'cpu_max': open('/sys/fs/cgroup/cpu.max').read().strip(),
        'readonly_root': bool(os.statvfs('/').f_flag & os.ST_RDONLY),
        'work_writable': not bool(os.statvfs('/work').f_flag & os.ST_RDONLY),
        'tmp_writable': not bool(os.statvfs('/tmp').f_flag & os.ST_RDONLY)}
def manifest():
    rows = []
    for root, dirs, files in os.walk('/work', followlinks=False):
        for name in sorted(dirs + files):
            path = os.path.join(root, name)
            mode = os.lstat(path).st_mode
            kind = 'file' if stat.S_ISREG(mode) else 'directory' if stat.S_ISDIR(mode) else 'other'
            row = {'path': os.path.relpath(path, '/work'), 'kind': kind}
            if kind == 'file':
                with open(path, 'rb') as output:
                    row.update(sha256=hashlib.file_digest(output, 'sha256').hexdigest(),
                        size_bytes=os.path.getsize(path))
            rows.append(row)
    return sorted(rows, key=lambda r: r['path'])
def run(stage, argv, limit):
    before = controller_state()
    observed = {}
    def started(child):
        facts['toolchain_launch_count'] += 1
        if stage == 'java': facts['synthetic_java_execution_count'] += 1
        print(json.dumps({'event': 'started', 'stage': stage, 'pid': child.pid}), file=sys.stderr, flush=True)
        observed.update(boundary(child.pid))
        facts['descendants_contained'] &= observed == before['boundary']
    captured = capture_process(argv, limit, deadline=controller_deadline, on_start=started)
    after = controller_state()
    result = {k: v for k, v in captured.items() if k not in ('stdout', 'stderr')}
    result.update(argv=list(argv), stdout_b64=base64.b64encode(captured['stdout']).decode(),
        stderr_b64=base64.b64encode(captured['stderr']).decode(), limit_bytes=limit,
        capture_method='single_thread_selector',
        threads_before={k: before[k] for k in ('pid', 'python_threads', 'os_threads', 'thread_start_attempts')},
        threads_after={k: after[k] for k in ('pid', 'python_threads', 'os_threads', 'thread_start_attempts')},
        child_boundary=observed,
        selector_cleanup_verified=captured['cleanup_verified'])
    facts['stages'][stage] = result
    print(json.dumps({'event': 'completed', 'stage': stage, 'pid': result['pid'],
        'exit_code': result['exit_code'], 'cleanup_verified': result['cleanup_verified']}), file=sys.stderr, flush=True)
    return (result['status'] == 'completed' and result['exit_code'] == 0
        and result['cleanup_verified'] and not result['overflow']
        and result['eof'] == [True, True] and facts['descendants_contained']
        and (stage != 'javac' or not captured['stdout'] and not captured['stderr']))
def execute():
    facts['controller_before'] = controller_state()
    facts['work_before'] = manifest()
    if facts['work_before']: return
    for kind, path, expected in (('javac', JAVAC_PATH, JAVAC_SHA256), ('java', JAVA_PATH, JAVA_SHA256)):
        with open(path, 'rb') as binary: digest = hashlib.file_digest(binary, 'sha256').hexdigest()
        facts[kind + '_binary_sha256'] = digest
        if digest != expected: return
    if hashlib.sha256(JAVA_SOURCE).hexdigest() != SOURCE_SHA256: return
    with open('/work/JavaSandboxProbe.java', 'xb') as target: target.write(JAVA_SOURCE)
    with open('/work/JavaSandboxProbe.java', 'rb') as projected: actual = projected.read()
    facts['source_sha256'] = hashlib.sha256(actual).hexdigest()
    facts['source_size_bytes'] = len(actual)
    facts['source_readback_exact'] = actual == JAVA_SOURCE
    if facts['source_sha256'] != SOURCE_SHA256 or not facts['source_readback_exact']: return
    os.mkdir('/work/classes')
    if not run('javac', COMPILE_ARGV, 2048): return
    rows = manifest()
    facts['work_after_compile'] = rows
    facts['unexpected_output_files'] = [r['path'] for r in rows if r['path'] not in
        ('JavaSandboxProbe.java', 'classes', 'classes/JavaSandboxProbe.class')]
    facts['class_manifest'] = [r for r in rows if r['path'] == 'classes/JavaSandboxProbe.class']
    if (facts['unexpected_output_files'] or len(rows) != 3 or len(facts['class_manifest']) != 1
        or [(r['path'], r['kind']) for r in rows] != [('JavaSandboxProbe.java', 'file'),
            ('classes', 'directory'), ('classes/JavaSandboxProbe.class', 'file')]
        or rows[0]['sha256'] != SOURCE_SHA256 or rows[0]['size_bytes'] != len(JAVA_SOURCE)
        or not 0 < rows[2]['size_bytes'] <= 32768): return
    if not run('java', RUNTIME_ARGV, 1024): return
    facts['work_after_runtime'] = manifest()
try:
    execute()
except Exception as error:
    facts['controller_error'] = type(error).__name__ + ': ' + str(error)[:250]
finally:
    facts['controller_after'] = controller_state()
    facts['phase_pids_after_cleanup'] = sorted(int(n) for n in os.listdir('/proc') if n.isdigit())[:129]
print(json.dumps({'facts': facts}, sort_keys=True), flush=True)
'''


def source():
    """No caller source, flags, environment or stdin payload is accepted."""
    constants = {k: globals()[k] for k in ('JAVA_SOURCE', 'EXPECTED_OUTPUT', 'SOURCE_SHA256',
        'JAVAC_PATH', 'JAVAC_SHA256', 'JAVA_PATH', 'JAVA_SHA256', 'COMPILE_ARGV', 'RUNTIME_ARGV')}
    return ('import base64, hashlib, json, stat, sys, threading\n' + capture_source() + '\n'
        + ''.join(k + ' = ' + repr(v) + '\n' for k, v in constants.items()) + BODY)
