"""SANDBOX.2 fixed probes; no candidate source or arbitrary command interface."""
from core import sandboxed_java_single_thread_probe as single

NAMESPACE_FLAGS = {'mnt': 0x20000, 'cgroup': 0x2000000, 'uts': 0x4000000,
    'ipc': 0x8000000, 'user': 0x10000000, 'pid': 0x20000000, 'net': 0x40000000}
PTHREAD_CLONE_FLAGS = 0x3D0F00
JAVA_PATH = '/opt/temurin-26.0.2.1/bin/java'
JAVA_SHA256 = 'a719fab9108ba87eba82655ba904edbee0a91ff13365579519f44f99100382b2'

# A second, strictly restrictive filter used ONLY inside the native fixture.
# x86_64 seccomp_data offsets: nr=0, arch=4, args[0] low/high=16/20.
# Deny other ABIs, and deny clone unless flags match the full 64-bit word.
CLONE_WITNESS_BPF = (
    (0x20, 0, 0, 4), (0x15, 1, 0, 0xC000003E), (0x06, 0, 0, 0x50001),
    (0x20, 0, 0, 0), (0x15, 0, 5, 56),
    (0x20, 0, 0, 20), (0x15, 0, 2, 0),
    (0x20, 0, 0, 16), (0x15, 1, 0, PTHREAD_CLONE_FLAGS),
    (0x06, 0, 0, 0x50001), (0x06, 0, 0, 0x7FFF0000))

NATIVE_HEADER = r'''
import ctypes, errno, json, os, socket, time
libc = ctypes.CDLL(None, use_errno=True)
libc.syscall.restype = ctypes.c_long
libc.gnu_get_libc_version.restype = ctypes.c_char_p
def call(number, *args):
    ctypes.set_errno(0)
    result = libc.syscall(ctypes.c_long(number), *args)
    return {'result': result, 'errno': ctypes.get_errno()}
def state():
    text = open('/proc/self/status').read()
    return {'pid': os.getpid(), 'ppid': os.getppid(),
        'tid': call(186)['result'], 'uid': os.getuid(), 'gid': os.getgid(),
        'namespaces': {n: os.readlink('/proc/thread-self/ns/' + n) for n in NS_FLAGS},
        'cgroup': open('/proc/thread-self/cgroup').read().strip(),
        'os_threads': len(os.listdir('/proc/self/task')),
        'processes': sorted(int(n) for n in os.listdir('/proc') if n.isdigit()),
        'pids_current': open('/sys/fs/cgroup/pids.current').read().strip(),
        'pids_max': open('/sys/fs/cgroup/pids.max').read().strip(),
        'memory_max': open('/sys/fs/cgroup/memory.max').read().strip(),
        'capabilities_zero': 'CapEff:\t0000000000000000' in text,
        'no_new_privileges': 'NoNewPrivs:\t1' in text}
def emit(facts):
    print(json.dumps(facts, sort_keys=True), flush=True)
'''

CLONE3_BODY = r'''
before = state()
probe = call(435, ctypes.c_void_p(), ctypes.c_size_t(0))
emit({'clone3': probe, 'before': before, 'after': state(),
    'libc_version': libc.gnu_get_libc_version().decode()})
'''

PTHREAD_BODY = r'''
facts = {'before': state(), 'namespace_probes': {}, 'pthreads': [],
    'libc_version': libc.gnu_get_libc_version().decode(), 'witness_flags': WITNESS_FLAGS}
def namespace_denials():
    for name, flag in NS_FLAGS.items():
        record = {}
        # No CLONE_VM and no child stack: fork-like raw clone. A hypothetical
        # successful child exits immediately, and the parent waits before stop.
        record['clone'] = call(56, ctypes.c_ulong(flag | 17), ctypes.c_void_p(),
            ctypes.c_void_p(), ctypes.c_void_p(), ctypes.c_ulong(0))
        if record['clone']['result'] == 0: os._exit(88)
        if record['clone']['result'] > 0:
            os.waitpid(record['clone']['result'], 0)
        facts['namespace_probes'][name] = record
        if record['clone'] != {'result': -1, 'errno': errno.EPERM}: return False
        record['unshare'] = call(272, ctypes.c_ulong(flag))
        if record['unshare'] != {'result': -1, 'errno': errno.EPERM}: return False
        fd = os.open('/proc/self/ns/' + name, os.O_RDONLY)
        try: record['setns'] = call(308, ctypes.c_int(fd), ctypes.c_int(flag))
        finally: os.close(fd)
        if record['setns'] != {'result': -1, 'errno': errno.EPERM}: return False
    return True
callback_type = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p)
libc.pthread_create.argtypes = [ctypes.POINTER(ctypes.c_ulong), ctypes.c_void_p,
    callback_type, ctypes.c_void_p]
libc.pthread_create.restype = ctypes.c_int
libc.pthread_join.argtypes = [ctypes.c_ulong, ctypes.c_void_p]
libc.pthread_join.restype = ctypes.c_int
def pthread(label):
    record = {'label': label, 'before': state()}
    def observe(ignored):
        try:
            record['thread'] = state()
            try:
                s = socket.socket()
                s.close()
                record['socket_errno'] = 0
            except OSError as error: record['socket_errno'] = error.errno
        except Exception as error: record['callback_error'] = type(error).__name__
        return None
    callback = callback_type(observe)
    tid = ctypes.c_ulong()
    record['create_return_code'] = libc.pthread_create(ctypes.byref(tid), None, callback, None)
    if record['create_return_code'] == 0:
        record['join_return_code'] = libc.pthread_join(tid, None)
    # Kernel task disappearance can trail pthread_join's userspace return.
    until = time.monotonic() + .1
    while len(os.listdir('/proc/self/task')) != 1 and time.monotonic() < until:
        time.sleep(.001)
    record['after'] = state()
    facts['pthreads'].append(record)
    return record['create_return_code'] == 0 and record.get('join_return_code') == 0
def witness_filter():
    class Filter(ctypes.Structure):
        _fields_ = [('code', ctypes.c_ushort), ('jt', ctypes.c_ubyte),
            ('jf', ctypes.c_ubyte), ('k', ctypes.c_uint)]
    class Program(ctypes.Structure):
        _fields_ = [('len', ctypes.c_ushort), ('filter', ctypes.POINTER(Filter))]
    array = (Filter * len(BPF))(*(Filter(*row) for row in BPF))
    program = Program(len(BPF), array)
    ctypes.set_errno(0)
    result = libc.prctl(ctypes.c_int(22), ctypes.c_ulong(2),
        ctypes.byref(program), ctypes.c_ulong(0), ctypes.c_ulong(0))
    return {'result': result, 'errno': ctypes.get_errno()}
if namespace_denials() and pthread('candidate_unmodified'):
    facts['witness_filter'] = witness_filter()
    if facts['witness_filter']['result'] == 0:
        # Verify mismatch really is rejected before the second pthread call.
        facts['witness_rejects_other_flags'] = call(56, ctypes.c_ulong(17),
            ctypes.c_void_p(), ctypes.c_void_p(), ctypes.c_void_p(), ctypes.c_ulong(0))
        if facts['witness_rejects_other_flags']['result'] == 0: os._exit(89)
        if facts['witness_rejects_other_flags']['result'] > 0:
            os.waitpid(facts['witness_rejects_other_flags']['result'], 0)
        if facts['witness_rejects_other_flags'] == {'result': -1, 'errno': errno.EPERM}:
            pthread('exact_legacy_clone_flags')
facts['after'] = state()
emit(facts)
'''

TMP_BODY = r'''
import json, os
facts = {'writable': [], 'removed': []}
for root in ('/work', '/tmp'):
    path = root + '/sandbox2-fixed-write'
    with open(path, 'xb') as target: target.write(b'phase-owned')
    facts['writable'].append(root)
    os.unlink(path)
    facts['removed'].append(not os.path.exists(path))
facts['uid'], facts['gid'] = os.getuid(), os.getgid()
print(json.dumps(facts, sort_keys=True), flush=True)
'''


def source_for(mode):
    if mode in ('clone3', 'pthread'):
        return ('NS_FLAGS = ' + repr(NAMESPACE_FLAGS) + '\nWITNESS_FLAGS = '
            + repr(PTHREAD_CLONE_FLAGS) + '\nBPF = ' + repr(CLONE_WITNESS_BPF)
            + '\n' + NATIVE_HEADER + (CLONE3_BODY if mode == 'clone3' else PTHREAD_BODY))
    if mode == 'tmp': return TMP_BODY
    if mode == 'controller': return single.gate_source('non_java')
    if mode == 'javac_version': return single.gate_source(mode)
    if mode == 'java_version':
        # Reuse the exact JAVA.1B capture/observer, changing only fixed identity.
        original = single.gate_source('javac_version')
        return original.replace(repr(single.JAVAC_PATH), repr(JAVA_PATH)).replace(
            repr(single.JAVAC_SHA256), repr(JAVA_SHA256))
    raise ValueError('fixed_sandbox2_probe_required')
