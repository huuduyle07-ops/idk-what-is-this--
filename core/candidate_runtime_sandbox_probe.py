"""Phase-owned hostile fixture. Never a candidate, shell or Java harness."""

PROBE_SOURCE = r'''
import base64, errno, hashlib, json, os, signal, socket, subprocess, sys, time

request = json.loads(sys.stdin.buffer.readline(131073))
mode = sys.argv[1]
def emit(value):
    print(json.dumps(value, sort_keys=True), flush=True)
def denied(operation):
    try:
        result = operation()
        if hasattr(result, 'close'): result.close()
        return False
    except OSError as error:
        return error.errno in (errno.EPERM, errno.EACCES, errno.EROFS, errno.ENOENT)
def boundary():
    return {name: os.readlink('/proc/self/ns/' + name)
            for name in ('pid', 'mnt', 'net', 'ipc', 'cgroup')}
if mode == 'boundary':
    manifest = []
    for item in request['inputs']:
        data = base64.b64decode(item['bytes'])
        path = '/work/' + item['path']
        with open(path, 'xb') as output: output.write(data)
        with open(path, 'rb') as source: actual = source.read()
        manifest.append({'path': item['path'], 'sha256': hashlib.sha256(actual).hexdigest(),
                         'size_bytes': len(actual)})
    with open('/work/workspace-write', 'xb') as output: output.write(b'workspace-write')
    host_reads = [denied(lambda path=path: open(path, 'rb')) for path in request['host_paths']]
    host_writes = [denied(lambda path=path: open(path, 'wb')) for path in request['host_paths']]
    root_denied = denied(lambda: open('/phase-owned-root-write', 'wb'))
    socket_results = {}
    for name, family, kind in (('ipv4_tcp', socket.AF_INET, socket.SOCK_STREAM),
            ('ipv6_tcp', socket.AF_INET6, socket.SOCK_STREAM),
            ('dns_udp', socket.AF_INET, socket.SOCK_DGRAM),
            ('unix_socket', socket.AF_UNIX, socket.SOCK_STREAM)):
        socket_results[name] = denied(lambda family=family, kind=kind: socket.socket(family, kind))
    local_denied = denied(lambda: socket.create_connection(('127.0.0.1', request['port']), .2))
    pair_denied = denied(socket.socketpair)
    env = dict(os.environ)
    emit({'manifest': manifest, 'workspace_write': True, 'external_read_denied': all(host_reads),
          'external_write_denied': all(host_writes), 'root_write_denied': root_denied,
          'socket_denials': socket_results, 'local_connect_denied': local_denied,
          'socketpair_denied': pair_denied, 'environment': env,
          'host_secret_absent': 'CATTUS_SANDBOX_HOST_ONLY' not in env,
          'uid': os.getuid(), 'namespaces': sorted(boundary()), 'pid_is_one': os.getpid() == 1,
          'no_new_privileges': 'NoNewPrivs:\t1' in open('/proc/self/status').read(),
          'capabilities_zero': 'CapEff:\t0000000000000000' in open('/proc/self/status').read()})
elif mode in ('descendant', 'timeout'):
    child_source = "import json,os,time; print(json.dumps({'namespaces':{n:os.readlink('/proc/self/ns/'+n) for n in ('pid','mnt','net','ipc','cgroup')},'cgroup':open('/proc/self/cgroup').read()}),flush=True); time.sleep(60)"
    child = subprocess.Popen([sys.executable, '-I', '-S', '-B', '-c', child_source], stdout=subprocess.PIPE)
    evidence = json.loads(child.stdout.readline(4096))
    emit({'child_spawned': True, 'child_alive': child.poll() is None,
          'same_namespaces': evidence['namespaces'] == boundary(),
          'same_cgroup': evidence['cgroup'] == open('/proc/self/cgroup').read(),
          'pid_is_one': os.getpid() == 1})
    if mode == 'timeout':
        while True: time.sleep(.1)
elif mode in ('stdout', 'stderr'):
    stream = 1 if mode == 'stdout' else 2
    while True: os.write(stream, b'X' * 4096)
else:
    raise SystemExit(64)
'''
