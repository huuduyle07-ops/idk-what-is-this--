"""RUNTIME.JAVA.1 fixed infrastructure fixture/controller; no candidate harness."""

JAVA_SOURCE = (b'final class JavaSandboxProbe {\n'
    b'    public static void main(String[] args) {\n'
    b'        System.out.print("JAVA_SANDBOX_OK");\n'
    b'    }\n}\n')
EXPECTED_OUTPUT = b'JAVA_SANDBOX_OK'
SOURCE_PATH = 'JavaSandboxProbe.java'
COMPILE_ARGUMENTS = ('-J-Xms8m', '-J-Xmx32m', '-J-XX:ActiveProcessorCount=1',
    '-J-XX:-UsePerfData', '-d', '/work/classes', '/work/JavaSandboxProbe.java')
RUNTIME_ARGUMENTS = ('-Xms8m', '-Xmx32m', '-XX:ActiveProcessorCount=1',
    '-XX:-UsePerfData', '-cp', '/work/classes', 'JavaSandboxProbe')

# No command string, shell, arbitrary source, main class or caller flags exist.
# The image is immutable and both binary bytes are authenticated before launch.
JAVA_PROBE_SOURCE = r'''
import base64, hashlib, json, os, subprocess, sys, threading, time
request = json.loads(sys.stdin.buffer.readline(16385))
facts = {'stages': {}, 'class_manifest': [], 'source_sha256': '',
    'toolchain_launch_count': 0, 'synthetic_java_execution_count': 0,
    'source_size_bytes': 0, 'environment': dict(os.environ), 'uid': os.getuid(),
    'pid_is_one': os.getpid() == 1,
    'no_new_privileges': 'NoNewPrivs:\t1' in open('/proc/self/status').read(),
    'capabilities_zero': 'CapEff:\t0000000000000000' in open('/proc/self/status').read(),
    'descendants_contained': True}
timings = {}
def boundary(pid):
    return ({n: os.readlink('/proc/' + str(pid) + '/ns/' + n)
        for n in ('pid', 'mnt', 'net', 'ipc', 'cgroup')},
        open('/proc/' + str(pid) + '/cgroup').read())
parent_boundary = boundary(os.getpid())
def run(stage, argv, limit):
    tick = time.perf_counter()
    child = subprocess.Popen(argv, shell=False, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=dict(os.environ), cwd='/work')
    facts['toolchain_launch_count'] += 1
    if stage == 'java': facts['synthetic_java_execution_count'] += 1
    try:
        facts['descendants_contained'] &= boundary(child.pid) == parent_boundary
    except OSError:
        # A process too short to measure cannot grant containment verification.
        facts['descendants_contained'] = False
    outputs = [bytearray(), bytearray()]
    overflow = threading.Event()
    def read(stream, output):
        while True:
            data = stream.read(256)
            if not data: break
            available = limit - len(output)
            output.extend(data[:available])
            if len(data) > available:
                overflow.set()
                break
    readers = [threading.Thread(target=read, args=(s, b), daemon=True)
        for s, b in zip((child.stdout, child.stderr), outputs)]
    for reader in readers: reader.start()
    while child.poll() is None:
        if overflow.wait(.005):
            child.kill()
            break
    child.wait()
    for reader in readers: reader.join()
    for stream in (child.stdout, child.stderr): stream.close()
    result = {'exit_code': child.returncode, 'overflow': overflow.is_set(),
        'argv': argv, 'stdout_b64': base64.b64encode(outputs[0]).decode(),
        'stderr_b64': base64.b64encode(outputs[1]).decode()}
    facts['stages'][stage] = result
    timings[stage + '_seconds'] = time.perf_counter() - tick
    return result['exit_code'] == 0 and not result['overflow']
def execute():
    for kind in ('javac', 'java'):
        path = request[kind + '_path']
        with open(path, 'rb') as binary:
            digest = hashlib.file_digest(binary, 'sha256').hexdigest()
        facts[kind + '_binary_sha256'] = digest
        if digest != request[kind + '_sha256']: return
    if not (facts['uid'] == 65534 and facts['pid_is_one']
        and facts['no_new_privileges'] and facts['capabilities_zero']): return
    tick = time.perf_counter()
    source = base64.b64decode(request['source_b64'], validate=True)
    with open('/work/JavaSandboxProbe.java', 'xb') as target: target.write(source)
    with open('/work/JavaSandboxProbe.java', 'rb') as projected: actual = projected.read()
    facts['source_sha256'] = hashlib.sha256(actual).hexdigest()
    facts['source_size_bytes'] = len(actual)
    timings['source_projection_seconds'] = time.perf_counter() - tick
    if facts['source_sha256'] != request['source_sha256']: return
    os.mkdir('/work/classes')
    if not run('javac_identity', [request['javac_path'], '-version'], 1024): return
    if not run('java_identity', [request['java_path'], '-version'], 1024): return
    if not run('javac', [request['javac_path'], '-J-Xms8m', '-J-Xmx32m',
        '-J-XX:ActiveProcessorCount=1', '-J-XX:-UsePerfData', '-d',
        '/work/classes', '/work/JavaSandboxProbe.java'], 2048): return
    for root, dirs, files in os.walk('/work/classes', followlinks=False):
        for name in sorted(files):
            path = os.path.join(root, name)
            with open(path, 'rb') as output:
                facts['class_manifest'].append({'path': os.path.relpath(path, '/work/classes'),
                    'sha256': hashlib.file_digest(output, 'sha256').hexdigest(),
                    'size_bytes': os.path.getsize(path)})
    if [row['path'] for row in facts['class_manifest']] != ['JavaSandboxProbe.class']: return
    run('java', [request['java_path'], '-Xms8m', '-Xmx32m',
        '-XX:ActiveProcessorCount=1', '-XX:-UsePerfData', '-cp',
        '/work/classes', 'JavaSandboxProbe'], 1024)
try:
    execute()
except (OSError, ValueError, subprocess.SubprocessError) as error:
    facts['controller_error'] = type(error).__name__ + ': ' + str(error)[:500]
print(json.dumps({'facts': facts, 'timings': timings}, sort_keys=True), flush=True)
'''
