"""Fixed JAVA.1A diagnostic; reuses JAVA.1 capture without its execute route."""
import ast

from core.candidate_runtime_sandbox_probe import PROBE_SOURCE
from core.sandboxed_java_toolchain_probe import JAVA_PROBE_SOURCE


def capture_functions():
    """Copy exact function text, never import/execute the Java fixture sequence."""
    tree = ast.parse(JAVA_PROBE_SOURCE)
    return '\n'.join(ast.get_source_segment(JAVA_PROBE_SOURCE, node)
        for node in tree.body if isinstance(node, ast.FunctionDef)
        and node.name in ('boundary', 'run'))


# Only the already-proven SANDBOX.1 boundary fixture is used for repeats.
# Its fixed request enters through an in-memory stdin; no arbitrary commands.
BOUNDARY_FIXTURE = (
    "import io,sys\n"
    "sys.stdin=io.TextIOWrapper(io.BytesIO(b'{\"inputs\":[],\"host_paths\":[],\"port\":1}\\n'))\n"
    "sys.argv=['runtime-sandbox1','boundary']\n" + PROBE_SOURCE)

DIAGNOSTIC_BODY = r'''
import base64, ctypes, errno, hashlib, json, os, resource, subprocess, sys, threading, time
from types import SimpleNamespace

def small_read(path):
    try:
        with open(path) as stream: return stream.read(4096).strip()
    except OSError: return None

def state():
    status = small_read('/proc/self/status') or ''
    fields = dict(line.split(':', 1) for line in status.splitlines() if ':' in line)
    return {'pid': os.getpid(), 'os_threads': len(os.listdir('/proc/self/task')),
        'python_threads': threading.active_count(),
        'reader_threads_alive': sum(t.is_alive() for t in readers),
        'pids_current': small_read('/sys/fs/cgroup/pids.current'),
        'pids_max': small_read('/sys/fs/cgroup/pids.max'),
        'pids_events': small_read('/sys/fs/cgroup/pids.events'),
        'memory_current': small_read('/sys/fs/cgroup/memory.current'),
        'memory_max': small_read('/sys/fs/cgroup/memory.max'),
        'memory_events': small_read('/sys/fs/cgroup/memory.events'),
        'vm_size': fields.get('VmSize', '').strip(),
        'vm_rss': fields.get('VmRSS', '').strip(),
        'seccomp_mode': fields.get('Seccomp', '').strip()}

readers, children, attempts, events = [], [], [], []
class ObservedThread(threading.Thread):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.purpose = 'stdout_reader' if len(readers) % 2 == 0 else 'stderr_reader'
        self.started_ok = False
        self.joined_ok = False
        readers.append(self)
    def start(self):
        event = {'purpose': self.purpose, 'before_start': state()}
        events.append(event)
        try:
            super().start()
            self.started_ok = True
            event['started'] = True
        except RuntimeError as error:
            event.update(started=False, error_type=type(error).__name__, error=str(error)[:100])
            raise
    def join(self, *args, **kwargs):
        super().join(*args, **kwargs)
        self.joined_ok = not self.is_alive()

class ObservedPopen(subprocess.Popen):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        children.append(self)

facts = {'stages': {}, 'toolchain_launch_count': 0,
    'synthetic_java_execution_count': 0, 'descendants_contained': True}
timings = {}
namespace = dict(globals())
namespace['threading'] = SimpleNamespace(Event=threading.Event, Thread=ObservedThread)
namespace['subprocess'] = SimpleNamespace(Popen=ObservedPopen,
    PIPE=subprocess.PIPE, DEVNULL=subprocess.DEVNULL)
exec(CAPTURE_FUNCTIONS, namespace)
namespace['parent_boundary'] = namespace['boundary'](os.getpid())
baseline = state()
for index in range(3):
    first_event, first_reader = len(events), len(readers)
    attempt = {'index': index, 'before': state()}
    try:
        attempt['capture_completed'] = namespace['run']('non_java_boundary',
            [sys.executable, '-I', '-S', '-B', '-c', BOUNDARY_FIXTURE], 1024)
        stage = facts['stages']['non_java_boundary']
        attempt['child_exit_code'] = stage['exit_code']
        attempt['stdout_bytes'] = len(base64.b64decode(stage['stdout_b64']))
        attempt['stderr_bytes'] = len(base64.b64decode(stage['stderr_b64']))
    except (RuntimeError, OSError, subprocess.SubprocessError) as error:
        attempt.update(capture_completed=False, error_type=type(error).__name__,
            error=str(error)[:100])
    finally:
        # Diagnostic recovery only. The frozen run() has no start-failure finally.
        for child in children:
            if child.poll() is None: child.kill()
            child.wait(timeout=1)
        for reader in readers[first_reader:]:
            if reader.started_ok: reader.join(timeout=1)
        for child in children:
            for stream in (child.stdout, child.stderr):
                if not stream.closed: stream.close()
        path = '/work/workspace-write'
        if os.path.exists(path): os.unlink(path)
        attempt['reader_start_events'] = events[first_event:]
        attempt['readers_created'] = len(readers) - first_reader
        attempt['readers_started'] = sum(t.started_ok for t in readers[first_reader:])
        attempt['readers_joined'] = sum(t.joined_ok for t in readers[first_reader:])
        attempt['live_children_after_cleanup'] = sum(p.poll() is None for p in children)
        attempt['open_child_streams_after_cleanup'] = sum(not s.closed
            for p in children for s in (p.stdout, p.stderr))
        attempt['after_cleanup'] = state()
        attempts.append(attempt)
    if attempt['after_cleanup']['reader_threads_alive'] or attempt['live_children_after_cleanup']:
        break

native = {}
if any(a.get('error_type') == 'RuntimeError' for a in attempts):
    # No tracing, alternate policy, syscall fallback or limits mutation.
    # Invalid clone3 arguments cannot create a process even if allowed.
    libc = ctypes.CDLL(None, use_errno=True)
    libc.gnu_get_libc_version.restype = ctypes.c_char_p
    native['libc_version'] = libc.gnu_get_libc_version().decode('ascii')
    libc.syscall.restype = ctypes.c_long
    ctypes.set_errno(0)
    native['clone3_invalid_arguments_result'] = libc.syscall(
        ctypes.c_long(435), ctypes.c_void_p(), ctypes.c_size_t(0))
    native['clone3_errno'] = ctypes.get_errno()
    callback_type = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p)
    callback = callback_type(lambda ignored: None)
    thread_id = ctypes.c_ulong()
    libc.pthread_create.argtypes = [ctypes.POINTER(ctypes.c_ulong), ctypes.c_void_p,
        callback_type, ctypes.c_void_p]
    libc.pthread_create.restype = ctypes.c_int
    native['pthread_create_return_code'] = libc.pthread_create(
        ctypes.byref(thread_id), None, callback, None)
    if native['pthread_create_return_code'] == 0:
        libc.pthread_join.argtypes = [ctypes.c_ulong, ctypes.c_void_p]
        native['pthread_join_return_code'] = libc.pthread_join(thread_id, None)
    native['rlimit_nproc'] = list(resource.getrlimit(resource.RLIMIT_NPROC))
    native['rlimit_as'] = list(resource.getrlimit(resource.RLIMIT_AS))
    native['rlimit_stack'] = list(resource.getrlimit(resource.RLIMIT_STACK))

print(json.dumps({'controller': {'executable': sys.executable,
    'python_version': sys.version.split()[0], 'pid': os.getpid(), 'uid': os.getuid(),
    'owner': 'sandbox_container', 'baseline': baseline},
    'attempts': attempts, 'native': native, 'after_cleanup': state(),
    'container_processes_after_cleanup': sorted(int(n) for n in os.listdir('/proc') if n.isdigit())[:128],
    'work_files_after_cleanup': sorted(os.listdir('/work'))[:16],
    'java_launch_count': 0, 'compilation_count': 0, 'jvm_fixture_count': 0},
    sort_keys=True), flush=True)
'''


def diagnostic_source():
    return ('CAPTURE_FUNCTIONS = ' + repr(capture_functions()) + '\n'
        + 'BOUNDARY_FIXTURE = ' + repr(BOUNDARY_FIXTURE) + '\n' + DIAGNOSTIC_BODY)
