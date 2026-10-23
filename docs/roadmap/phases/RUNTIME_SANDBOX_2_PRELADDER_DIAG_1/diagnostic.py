"""One host-context observation of the unchanged SANDBOX.2 public owner.

No owner function, constant, frame local or returned value is replaced. The
observer retains original objects until authentication checks finish; exported
JSON remains report-only and contains neither signatures nor process secrets.
"""
from __future__ import annotations

import argparse
import ast
import base64
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import hmac
import json
from pathlib import Path
import sys
import threading
from types import FunctionType

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
from core import candidate_runtime_sandbox as baseline
from core import thread_compatible_runtime_sandbox as owner

PHASE = 'RUNTIME.SANDBOX.2.PRELADDER.DIAG.1'
ENDPOINT = 'npipe:////./pipe/dockerDesktopLinuxEngine'
IMAGE = 'sha256:f6d7dc31a15bb37a618ebed6772beda3de95fdcc3394eb5a1def9b1d20673f7a'
SOURCE_HASHES = {
    'core/thread_compatible_runtime_sandbox.py': '8eea18d16c330dc7d116065ac9d23833bb2a0af58448b02438c26526141b1d45',
    'core/candidate_runtime_sandbox.py': 'ebe409e7e798ec1e8f48c4bd2c49e5cd8b282906251f7c2c38c2933d1ef51913',
    'core/thread_compatible_runtime_sandbox_probe.py': 'be45d3a0106186d84a0464234f701140df6e90e99107477af358886cf5568075',
}


def write_json(name, value):
    (HERE / name).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n',
                            encoding='utf-8', newline='\n')


def check_sources():
    measured = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                for name in SOURCE_HASHES}
    assert measured == SOURCE_HASHES, 'frozen source drift; never repin'
    assert owner.IMAGE == IMAGE
    return measured


# These are statements/predicates present in frozen code, in source execution
# order. Absence of private config is an observation, not an owner requirement.
# The nested bounded-process implementation is expanded in the static audit.
_ROWS = [
    ('report_initialization', 'replay', 318, 'frozen constants, policy_diff()', 'initialization exception', 'PRELADDER_INITIALIZATION_FAILURE'),
    ('docker_binary_endpoint_lookup', '_docker_prefix', 364, "shutil.which('docker'), _local_endpoint()", 'lookup exception; empty prefix if unavailable', 'DOCKER_PREFIX_CONSTRUCTION_FAILURE'),
    ('docker_binary_endpoint_availability_branch', '_docker_prefix', 365, 'binary and endpoint', 'returns empty tuple if missing (no exception)', 'DOCKER_PREFIX_CONSTRUCTION_FAILURE'),
    ('docker_binary_resolution', '_docker_prefix', 366, 'binary path', 'OSError/path resolution error', 'DOCKER_PREFIX_CONSTRUCTION_FAILURE'),
    ('docker_owner_root_resolution', '_docker_prefix', 367, 'baseline __file__', 'OSError/path resolution error', 'DOCKER_PREFIX_CONSTRUCTION_FAILURE'),
    ('docker_binary_boundary_branch', '_docker_prefix', 368, 'resolved path, owner root, Windows .exe suffix', 'returns empty tuple when rejected', 'DOCKER_PREFIX_CONSTRUCTION_FAILURE'),
    ('private_config_path_construction', '_docker_prefix', 371, 'tempfile.gettempdir(), secrets.token_hex(16)', 'temporary-root/path/random exception; no mkdir or absence check', 'PRIVATE_CONFIG_SETUP_FAILURE'),
    ('docker_prefix_return', '_docker_prefix', 372, 'binary, absent_config, endpoint', 'returns exact tuple', 'DOCKER_PREFIX_CONSTRUCTION_FAILURE'),
    ('policy_file_read', 'replay', 328, 'POLICY_PATH.read_bytes()', 'OSError', 'POLICY_READ_FAILURE'),
    ('policy_baseline_identity', 'validate_policy_bytes', 59, 'baseline policy hash == historical baseline digest', 'ValueError historical_policy_identity_changed', 'POLICY_VALIDATION_FAILURE'),
    ('policy_expected_copy', 'validate_policy_bytes', 61, 'deepcopy baseline policy', 'copy exception', 'POLICY_VALIDATION_FAILURE'),
    ('policy_clone3_remove', 'validate_policy_bytes', 62, 'remove clone3 from first names list', 'ValueError/KeyError/TypeError', 'POLICY_VALIDATION_FAILURE'),
    ('policy_errno38_append', 'validate_policy_bytes', 63, 'append fixed clone3 errno 38 denial', 'list access/append exception', 'POLICY_VALIDATION_FAILURE'),
    ('policy_raw_type', 'validate_policy_bytes', 64, 'type(raw) is bytes', 'ValueError canonical policy required', 'POLICY_VALIDATION_FAILURE'),
    ('policy_exact_bytes', 'validate_policy_bytes', 64, 'raw == baseline._json(expected).encode()', 'ValueError canonical policy required', 'POLICY_VALIDATION_FAILURE'),
    ('policy_exact_hash', 'validate_policy_bytes', 65, 'sha256(raw) == POLICY_SHA256', 'ValueError canonical policy required', 'POLICY_VALIDATION_FAILURE'),
    ('exact_image_control', 'replay', 329, 'prefix + image inspect exact IMAGE --format {{json .}}', 'Popen OSError; nonzero exit or bounded capture failure', 'EXACT_IMAGE_INSPECTION_FAILURE'),
    ('image_control_environment', '_bounded_process', 294, 'minimal frozen environment and host-only sentinel', 'environment construction exception', 'PRELADDER_CONTROL_FAILURE'),
    ('image_control_deadlines', '_bounded_process', 296, 'monotonic start, timeout and abort deadlines', 'clock/arithmetic exception', 'PRELADDER_CONTROL_FAILURE'),
    ('image_control_process_launch', '_bounded_process', 299, 'Popen shell=False, hidden Windows child, stdin/stdout/stderr pipes', 'OSError before control try', 'EXACT_IMAGE_INSPECTION_FAILURE'),
    ('image_control_capture_preparation', '_bounded_process', 302, 'Event, two bytearrays, read closure, two bounded reader Threads', 'thread/event/buffer construction exception', 'PRELADDER_CONTROL_FAILURE'),
    ('image_control_reader_start', '_bounded_process', 316, 'start both daemon readers', 'RuntimeError/OSError', 'PRELADDER_CONTROL_FAILURE'),
    ('image_control_stdin_write', '_bounded_process', 322, 'original empty input bytes', 'OSError becomes control failure', 'PRELADDER_CONTROL_FAILURE'),
    ('image_control_stdin_close', '_bounded_process', 323, 'close original stdin pipe', 'OSError becomes control failure', 'PRELADDER_CONTROL_FAILURE'),
    ('image_control_process_completion', '_bounded_process', 324, 'poll with output/timeout limits and wait; kill on abort', 'timeout/output bound/control failure', 'EXACT_IMAGE_INSPECTION_FAILURE'),
    ('image_control_reader_join', '_bounded_process', 345, 'join both reader threads (2 seconds each)', 'surviving reader => sandbox_control_failure', 'PRELADDER_CONTROL_FAILURE'),
    ('image_control_pipe_close', '_bounded_process', 348, 'close stdout and stderr', 'OSError', 'PRELADDER_CONTROL_FAILURE'),
    ('image_control_capture_return', '_bounded_process', 353, 'original _Capture with bounded bytes and original return code', 'capture construction exception', 'PRELADDER_CONTROL_FAILURE'),
    ('image_capture_status_requirement', 'replay', 331, 'image.status == sandbox_completed', 'other status selects {}, no parsing', 'EXACT_IMAGE_INSPECTION_FAILURE'),
    ('image_capture_exit_requirement', 'replay', 331, 'image.exit_code == 0', 'nonzero exit selects {}, no parsing', 'EXACT_IMAGE_INSPECTION_FAILURE'),
    ('image_output_parse', 'replay', 331, 'json.loads(original capture.stdout) only on completed exit 0', 'ValueError/JSONDecodeError; failed control supplies {} without parsing', 'IMAGE_OUTPUT_PARSE_FAILURE'),
    ('metadata_prefix_requirement', 'replay', 332, 'not prefix', 'ValueError exact_local_java_image_required', 'DOCKER_PREFIX_UNAVAILABLE'),
    ('metadata_id_requirement', 'replay', 332, "metadata.get('Id') == IMAGE", 'AttributeError on non-.get receiver; identity rejection', 'IMAGE_ID_MISMATCH'),
    ('metadata_os_requirement', 'replay', 332, "metadata.get('Os') == 'linux'", 'OS rejection', 'IMAGE_OS_MISMATCH'),
    ('metadata_arch_requirement', 'replay', 333, "metadata.get('Architecture') == 'amd64'", 'architecture rejection', 'IMAGE_ARCH_MISMATCH'),
    ('metadata_volumes_requirement', 'replay', 333, "not metadata.get('Config', {}).get('Volumes')", 'AttributeError if Config lacks .get; truthy volumes rejected', 'DECLARED_VOLUME_REJECTION'),
    ('temporary_workspace_create', 'replay', 335, "TemporaryDirectory(prefix='runtime-sandbox2-').__enter__()", 'OSError', 'TEMP_WORKSPACE_SETUP_FAILURE'),
    ('workspace_path_construction', 'replay', 336, 'root/seccomp.json, root/host-sentinel.txt', 'path exception', 'TEMP_WORKSPACE_SETUP_FAILURE'),
    ('policy_workspace_write', 'replay', 337, 'POLICY_BYTES to seccomp.json', 'OSError', 'TEMP_WORKSPACE_SETUP_FAILURE'),
    ('sentinel_workspace_write', 'replay', 338, 'fixed sentinel bytes to host-sentinel.txt', 'OSError', 'TEMP_WORKSPACE_SETUP_FAILURE'),
    ('host_tcp_socket_construction', 'replay', 339, 'default TCP socket construction', 'OSError', 'HOST_CONTROL_SETUP_FAILURE'),
    ('host_tcp_socket_enter', 'replay', 339, 'TCP socket context entry', 'context entry exception', 'HOST_CONTROL_SETUP_FAILURE'),
    ('host_udp_socket_construction', 'replay', 339, 'AF_INET/SOCK_DGRAM socket construction', 'OSError', 'HOST_CONTROL_SETUP_FAILURE'),
    ('host_udp_socket_enter', 'replay', 339, 'UDP socket context entry', 'context entry exception', 'HOST_CONTROL_SETUP_FAILURE'),
    ('host_tcp_bind', 'replay', 340, '127.0.0.1 ephemeral port', 'OSError', 'HOST_CONTROL_SETUP_FAILURE'),
    ('host_tcp_listen', 'replay', 341, 'listen(1)', 'OSError', 'HOST_CONTROL_SETUP_FAILURE'),
    ('host_port_read', 'replay', 342, 'endpoint.getsockname()[1]', 'OSError', 'HOST_CONTROL_SETUP_FAILURE'),
    ('host_udp_bind', 'replay', 343, '127.0.0.1 same port', 'OSError', 'HOST_CONTROL_SETUP_FAILURE'),
    ('ladder_first_mode', 'replay', 344, 'first frozen LADDER element clone3', 'iterator exception', 'PRELADDER_CONTROL_FAILURE'),
    ('invoke_mode_requirement', 'invoke', 257, 'mode in LADDER', 'ValueError fixed_sandbox2_probe_required', 'PRELADDER_CONTROL_FAILURE'),
    ('invoke_original_probe_selection', 'invoke', 258, 'clone3 in baseline.PROBE_IDS (false)', 'selection exception', 'PRELADDER_CONTROL_FAILURE'),
    ('invoke_probe_spec_selection', 'invoke', 259, 'None for clone3; no baseline synthetic spec call', 'selection exception', 'PRELADDER_CONTROL_FAILURE'),
    ('invoke_fixed_source_selection', 'invoke', 260, "probe.source_for('clone3')", 'ValueError; fixed NS_FLAGS/BPF/header/body construction', 'PRELADDER_CONTROL_FAILURE'),
    ('invoke_fixed_command_construction', 'invoke', 261, "-I -S -B -c fixed source", 'command construction exception', 'PRELADDER_CONTROL_FAILURE'),
    ('invoke_container_name_construction', 'invoke', 262, "runtime-sandbox2- + secrets.token_hex(12)", 'random/name exception', 'PRELADDER_CONTROL_FAILURE'),
    ('invoke_control_callable_construction', 'invoke', 263, 'frozen lambda forwarding prefix and bounded limits', 'initialization exception', 'PRELADDER_CONTROL_FAILURE'),
    ('invoke_capture_initialization', 'invoke', 264, '_Capture sandbox_launch_failed, facts {}, cleanup false', 'initialization exception', 'PRELADDER_CONTROL_FAILURE'),
    ('first_create_argv_construction', 'invoke', 266, 'frozen create flags/environment/entrypoint/exact image/source', 'argument expansion exception before bounded-process call', 'PRELADDER_CONTROL_FAILURE'),
]


def static_ledger():
    rows = []
    for i, (name, function, line, inputs, failures, category) in enumerate(_ROWS):
        rows.append({'order': i + 1, 'step': name, 'function': function,
                     'source': 'core/candidate_runtime_sandbox.py' if function in ('_docker_prefix', '_bounded_process')
                     else 'core/thread_compatible_runtime_sandbox.py',
                     'line': line, 'input': inputs, 'possible_exception_status': failures,
                     'can_terminate_before_ladder': name not in ('docker_binary_endpoint_availability_branch',
                         'docker_binary_boundary_branch', 'docker_prefix_return'),
                     'creates_container': False, 'failure_category': category})
    return rows


def classify_steps(states):
    """Pure first-failure classifier; preserves measured continuation facts."""
    rows = []
    first = None
    for template in static_ledger():
        value = states.get(template['step'], {'state': 'NOT_REACHED'})
        if isinstance(value, str):
            value = {'state': value}
        assert value['state'] in ('PASS', 'FAIL', 'NOT_REACHED')
        row = {**template, **deepcopy(value)}
        if first is None and row['state'] == 'FAIL':
            first = row
        rows.append(row)
    return {'ordered_pre_ladder_ledger': rows,
            'first_failing_step': first,
            'classification': first['failure_category'] if first else
                'PRELADDER_COMPLETE' if all(r['state'] == 'PASS' for r in rows)
                else 'PRELADDER_OBSERVATION_UNAVAILABLE'}


def metadata_states(prefix, metadata):
    """Evaluate the exact frozen short-circuit terms, with no invented type gate."""
    tree = ast.parse((ROOT / 'core/thread_compatible_runtime_sandbox.py').read_text(encoding='utf-8'))
    replay = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'replay')
    expression = next(n.test for n in ast.walk(replay) if isinstance(n, ast.If)
                      and n.lineno == 332)
    assert isinstance(expression, ast.BoolOp) and isinstance(expression.op, ast.Or)
    names = ('metadata_prefix_requirement', 'metadata_id_requirement', 'metadata_os_requirement',
             'metadata_arch_requirement', 'metadata_volumes_requirement')
    result = {}
    for name, term in zip(names, expression.values, strict=True):
        try:
            rejected = bool(eval(compile(ast.Expression(term), '<frozen metadata term>', 'eval'),
                                 {'__builtins__': {}}, {'prefix': prefix, 'metadata': metadata, 'IMAGE': IMAGE}))
        except (AttributeError, TypeError, ValueError) as error:
            result[name] = {'state': 'FAIL', 'error': type(error).__name__ + ': ' + str(error),
                            'failure_category': 'IMAGE_METADATA_ACCESS_FAILURE'}
            break
        result[name] = {'state': 'FAIL' if rejected else 'PASS', 'measured_rejection': rejected}
        if rejected:
            break
    return result


def instrumentation():
    hooks = {'sys_profile': sys.getprofile(), 'sys_trace': sys.gettrace(),
             'thread_profile': threading.getprofile(), 'thread_trace': threading.gettrace()}
    if hasattr(sys, 'monitoring'):
        hooks.update({f'monitoring_{i}': sys.monitoring.get_tool(i) for i in range(6)})
    return hooks


def owner_snapshot():
    return {module.__name__: {name: (id(value), id(value.__code__) if isinstance(value, FunctionType) else None)
            for name, value in vars(module).items() if isinstance(value, (FunctionType, type))
            or name in ('_SECRET', 'POLICY', '_SECCOMP', 'POLICY_BYTES', 'POLICY_SHA256', 'IMAGE', 'LADDER')}
            for module in (owner, baseline, owner.probe)}


class ObservationUnavailable(RuntimeError):
    pass


class Observer:
    def __init__(self):
        self.states = {}
        self.controls = []
        self.prefixes = []
        self.workspaces = []
        self.host_socket_final_facts = []
        self.raw_trace = []
        self.original_pair = None
        self.original_report = None
        self.metadata = None
        self.exceptions = []
        self.forbidden_calls = []
        self.first_mode = None
        self.create_attempted = False
        self._pending = {}
        self._controls = {}
        self._sockets = {}
        self._active = False
        self._code_names = {owner.replay.__code__: 'replay', baseline._docker_prefix.__code__: '_docker_prefix',
                            owner.invoke.__code__: 'invoke', owner.validate_policy_bytes.__code__: 'validate_policy_bytes'}
        self._line_steps = {(r['function'], r['line']): r['step'] for r in static_ledger()
                            if not r['step'].startswith(('metadata_', 'image_'))
                            and r['function'] != 'validate_policy_bytes'
                            and not r['step'].endswith(('socket_construction', 'socket_enter'))
                            and r['step'] not in ('exact_image_control', 'policy_file_read')}

    def __enter__(self):
        self.before = instrumentation()
        if any(v is not None for v in self.before.values()):
            raise ObservationUnavailable('PRELADDER_OBSERVATION_UNAVAILABLE: instrumentation already owned')
        self._active = True
        sys.settrace(self.observe)
        if sys.gettrace() != self.observe:
            raise ObservationUnavailable('PRELADDER_OBSERVATION_UNAVAILABLE: tracer installation failed')
        return self

    def __exit__(self, exc_type, exc, traceback):
        sys.settrace(self.before['sys_trace'])
        self._active = False
        self.restored = instrumentation() == self.before
        return False

    def mark(self, step, state='PASS', **facts):
        previous = self.states.get(step)
        if not previous or previous['state'] != 'FAIL':
            self.states[step] = {'state': state, **facts}

    def scope(self, frame):
        while frame is not None:
            if frame.f_code is owner.invoke.__code__:
                return 'SANDBOX2_ladder'
            if frame.f_code is owner.replay.__code__:
                return 'SANDBOX2_pre_ladder' if not self.create_attempted and frame.f_lineno < 368 else 'SANDBOX2_owner_teardown'
            frame = frame.f_back
        return 'diagnostic_read_only_control'

    def observe(self, frame, event, arg):
        # No catch around this callback: an observation exception is never
        # swallowed. Pure observer checks must pass before operational use.
        code = frame.f_code
        name = self._code_names.get(code)
        socket_init = owner.socket.socket.__init__.__code__
        socket_enter = owner.socket.socket.__enter__.__code__
        if code in (socket_init, socket_enter):
            if event == 'call':
                if self.create_attempted or self.scope(frame) != 'SANDBOX2_pre_ladder':
                    return None
                if code is socket_init:
                    datagram = frame.f_locals['type'] == owner.socket.SOCK_DGRAM
                    step = 'host_udp_socket_construction' if datagram else 'host_tcp_socket_construction'
                else:
                    datagram = frame.f_locals['self'].type == owner.socket.SOCK_DGRAM
                    step = 'host_udp_socket_enter' if datagram else 'host_tcp_socket_enter'
                self._sockets[id(frame)] = step
            elif event == 'exception' and id(frame) in self._sockets:
                self.mark(self._sockets[id(frame)], 'FAIL', exception={
                    'function': code.co_name, 'source': code.co_filename, 'line': frame.f_lineno,
                    'type': arg[0].__name__, 'message': str(arg[1])})
            elif event == 'return' and id(frame) in self._sockets:
                self.mark(self._sockets.pop(id(frame)))
            return self.observe
        if event == 'call':
            module = frame.f_globals.get('__name__', '')
            if module.startswith(('core.synthetic_', 'core.runtime_java_pinned_', 'core.behavioral_',
                                  'core.sandbox_backend_binding', 'core.sandboxed_java_positive_continuation')):
                self.forbidden_calls.append(module + '.' + code.co_name)
            if code is baseline._bounded_process.__code__:
                argv = tuple(frame.f_locals['argv'])
                row = {'argv': argv, 'scope': self.scope(frame), 'shell': False,
                       'timeout_ms': frame.f_locals['timeout_ms'],
                       'stdout_limit': frame.f_locals['stdout_limit'],
                       'stderr_limit': frame.f_locals['stderr_limit']}
                if '--config' in argv:
                    path = Path(argv[argv.index('--config') + 1])
                    row.update(private_config_path=str(path), config_exists_before=path.exists(),
                               config_is_symlink_before=path.is_symlink())
                if 'create' in argv:
                    self.create_attempted = True
                    self.mark('first_create_argv_construction')
                if row['scope'] == 'SANDBOX2_pre_ladder' and 'image' in argv:
                    self.mark('exact_image_control', control_invocation_observed=True)
                self.controls.append(row)
                self._controls[id(frame)] = row
                return self.observe
            if code is owner.validate_policy_bytes.__code__:
                self.mark('policy_file_read')
            if code is owner.invoke.__code__ and self.first_mode is None:
                self.first_mode = frame.f_locals['mode']
            if code is owner._evidence_pair.__code__:
                return self.observe
            return self.observe if name else None

        if code is baseline._bounded_process.__code__:
            row = self._controls[id(frame)]
            is_image = row['scope'] == 'SANDBOX2_pre_ladder' and 'image' in row['argv']
            if event == 'line' and is_image:
                line = frame.f_lineno
                milestones = {294: 'image_control_environment', 296: 'image_control_deadlines',
                    299: 'image_control_process_launch', 302: 'image_control_capture_preparation',
                    316: 'image_control_reader_start', 322: 'image_control_stdin_write',
                    323: 'image_control_stdin_close', 324: 'image_control_process_completion',
                    345: 'image_control_reader_join', 348: 'image_control_pipe_close',
                    353: 'image_control_capture_return'}
                active = row.get('_pending_step')
                candidate = milestones.get(line)
                if candidate and candidate != active:
                    if active:
                        self.mark(active)
                    row['_pending_step'] = candidate
                if line in (326, 329, 341, 350):
                    self.mark('image_control_process_completion', 'FAIL',
                              failing_control_source_line=line,
                              failure_category='EXACT_IMAGE_INSPECTION_FAILURE')
                if line == 347:
                    self.mark('image_control_reader_join', 'FAIL', failing_control_source_line=line)
            if event == 'exception':
                row.setdefault('exceptions', []).append({'line': frame.f_lineno,
                    'type': arg[0].__name__, 'message': str(arg[1])})
                if is_image:
                    self.mark(row.get('_pending_step', 'exact_image_control'), 'FAIL',
                              exception=row['exceptions'][-1])
            elif event == 'return':
                process = frame.f_locals.get('process')
                streams = [getattr(process, n, None) for n in ('stdin', 'stdout', 'stderr')]
                row.update(status=getattr(arg, 'status', None), exit_code=getattr(arg, 'exit_code', None),
                           process_created=process is not None,
                           process_reaped=process is None or process.returncode is not None,
                           pipes_closed=process is None or all(s is not None and s.closed for s in streams),
                           readers_surviving=sum(t.is_alive() for t in frame.f_locals.get('readers', ())))
                for stream in ('stdout', 'stderr'):
                    data = getattr(arg, stream, None)
                    row[stream] = None if data is None else {'base64': base64.b64encode(data).decode(),
                        'text_utf8_replace': data.decode(errors='replace'), 'bytes': len(data),
                        'sha256': hashlib.sha256(data).hexdigest(),
                        'retention': 'complete_original_bounded_capture'}
                active = row.pop('_pending_step', None)
                if is_image:
                    self.mark('exact_image_control',
                              control_index=self.controls.index(row),
                              capture_status=row['status'], exit_code=row['exit_code'])
                    if active:
                        self.mark(active, 'PASS' if arg is not None else 'FAIL')
                    if process is not None and process.returncode is not None:
                        self.mark('image_control_process_completion')
                    if any(t.is_alive() for t in frame.f_locals.get('readers', ())):
                        self.mark('image_control_reader_join', 'FAIL')
            return self.observe

        if code is owner._evidence_pair.__code__:
            if event == 'return':
                self.original_pair = arg
            return self.observe
        if name is None:
            return None
        if event == 'line':
            line = frame.f_lineno
            pending = self._pending.get(id(frame))
            spans = {'report_initialization': (318, 325),
                     'docker_binary_boundary_branch': (368, 369),
                     'first_create_argv_construction': (266, 276)}
            in_span = pending in spans and spans[pending][0] <= line <= spans[pending][1]
            if pending and not in_span:
                self._pending.pop(id(frame))
                self.mark(pending)
            if not self.create_attempted:
                self.raw_trace.append({'function': name, 'line': line})
                step = self._line_steps.get((name, line))
                if step:
                    self._pending[id(frame)] = step
                if name == 'replay':
                    if line == 328:
                        self._pending[id(frame)] = 'policy_file_read'
                    elif line == 331:
                        image = frame.f_locals['image']
                        self.mark('image_capture_status_requirement', 'PASS' if image.status == 'sandbox_completed' else 'FAIL')
                        if image.status == 'sandbox_completed':
                            self.mark('image_capture_exit_requirement', 'PASS' if image.exit_code == 0 else 'FAIL')
                        if image.status == 'sandbox_completed' and image.exit_code == 0:
                            self._pending[id(frame)] = 'image_output_parse'
                    elif line == 332:
                        self.metadata = frame.f_locals['metadata']
                        self.states.update(metadata_states(frame.f_locals['prefix'], self.metadata))
                    elif line == 336:
                        root = frame.f_locals['root']
                        self.workspaces.append({'path': root, 'exists_at_entry': Path(root).is_dir()})
                    elif line == 339:
                        for path_key in ('profile', 'sentinel'):
                            path = frame.f_locals[path_key]
                            self.workspaces[-1][path_key] = {'path': str(path), 'exists_before_sockets': path.is_file(),
                                'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                elif name == 'validate_policy_bytes':
                    if line == 59:
                        self.mark('policy_baseline_identity', 'PASS' if baseline._hash(baseline._SECCOMP)
                                  == owner.BASELINE_POLICY_SHA256 else 'FAIL')
                    elif line in (61, 62, 63):
                        self._pending[id(frame)] = {61: 'policy_expected_copy', 62: 'policy_clone3_remove',
                                                   63: 'policy_errno38_append'}[line]
                    elif line == 64:
                        raw = frame.f_locals['raw']
                        checks = [('policy_raw_type', type(raw) is bytes)]
                        if checks[-1][1]:
                            checks.append(('policy_exact_bytes', raw == baseline._json(frame.f_locals['expected']).encode()))
                        if checks[-1][1]:
                            checks.append(('policy_exact_hash', hashlib.sha256(raw).hexdigest() == owner.POLICY_SHA256))
                        for key, passed in checks:
                            self.mark(key, 'PASS' if passed else 'FAIL')
        elif event == 'exception':
            error = {'function': name, 'line': frame.f_lineno,
                     'type': arg[0].__name__, 'message': str(arg[1])}
            self.exceptions.append(error)
            step = self._pending.pop(id(frame), None)
            if step and not self.create_attempted:
                self.mark(step, 'FAIL', exception=error)
        elif event == 'return':
            pending = self._pending.pop(id(frame), None)
            if pending and arg is not None:
                self.mark(pending)
            if name == '_docker_prefix' and arg:
                path = Path(arg[2])
                self.prefixes.append({'prefix': arg, 'path': str(path),
                    'exists_at_generation': path.exists(), 'is_symlink_at_generation': path.is_symlink(),
                    'created_by_owner': False, 'owner_requires_absence': False})
            elif name == 'replay':
                self.original_report = arg
                self.host_socket_final_facts = [{'name': key, 'closed_after_owner': value.fileno() == -1}
                    for key in ('endpoint', 'dns') if (value := frame.f_locals.get(key)) is not None]
        return self.observe


def static_audit():
    hashes = check_sources()
    source = (ROOT / 'core/candidate_runtime_sandbox.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    functions = {}
    for name in ('_bounded_process', '_docker_prefix', '_local_endpoint'):
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
        functions[name] = {'source': 'core/candidate_runtime_sandbox.py', 'line': node.lineno,
                           'end_line': node.end_lineno, 'exact_source': ast.get_source_segment(source, node)}
    policy_source = (ROOT / 'core/thread_compatible_runtime_sandbox.py').read_text(encoding='utf-8')
    policy_node = next(n for n in ast.parse(policy_source).body if isinstance(n, ast.FunctionDef)
                       and n.name == 'validate_policy_bytes')
    functions['validate_policy_bytes'] = {'source': 'core/thread_compatible_runtime_sandbox.py',
        'line': policy_node.lineno, 'exact_source': ast.get_source_segment(policy_source, policy_node)}
    probe_source = (ROOT / 'core/thread_compatible_runtime_sandbox_probe.py').read_text(encoding='utf-8')
    node = next(n for n in ast.parse(probe_source).body if isinstance(n, ast.FunctionDef) and n.name == 'source_for')
    functions['source_for'] = {'source': 'core/thread_compatible_runtime_sandbox_probe.py',
        'line': node.lineno, 'exact_source': ast.get_source_segment(probe_source, node)}
    return {'phase_id': PHASE, 'source_hashes': hashes, 'ordered_pre_ladder_steps': static_ledger(),
        'nested_operations_exact_source': functions,
        'metadata_type_requirement': 'No explicit type predicate; .get access can raise AttributeError.',
        'private_config_behavior': 'Only constructs random path. No mkdir and no owner absence validation.',
        'first_container_create_source': {'function': 'invoke', 'line': 266},
        'bounded_process_order': ['minimal environment', 'monotonic deadline/trigger',
            'Popen(shell=False, three pipes, CREATE_NO_WINDOW on Windows)', 'Event and bounded bytearrays',
            'two daemon readers', 'stdin write/close', 'poll output overflow/timeout',
            'kill on abort when needed', 'wait/reap', 'reader join', 'stdout/stderr close',
            'capture construction/return']}


def original_pair_facts(pair):
    descriptor, receipt = pair
    assert owner.validate_receipt(receipt) is receipt
    assert owner.validate_descriptor(descriptor, receipt) is descriptor
    return {'descriptor': descriptor.as_dict(), 'receipt': receipt.as_dict(),
        'original_descriptor_object_id': id(descriptor), 'original_receipt_object_id': id(receipt),
        'exact_descriptor_type': type(descriptor).__module__ + '.' + type(descriptor).__qualname__,
        'exact_receipt_type': type(receipt).__module__ + '.' + type(receipt).__qualname__,
        'HMAC_results': {'descriptor': hmac.compare_digest(descriptor._signature, owner._sign(descriptor)),
                         'receipt': hmac.compare_digest(receipt._signature, owner._sign(receipt))},
        'public_validators_passed': True, 'semantic_eligibility': descriptor.eligible_for_java1_continuation,
        'signatures_exported': False, 'key_material_exported': False,
        'export_is_report_only': True}


def marker(name, value):
    with (HERE / name).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


def live():
    gates = json.loads((HERE / 'validation_pre_live.json').read_text(encoding='utf-8'))
    assert gates['passed'], 'all pure/pre-preservation gates must pass before preflight'
    check_sources()
    import validation
    assert validation.preservation()['passed']
    if any(v is not None for v in instrumentation().values()):
        write_json('live_result.json', {'phase_id': PHASE, 'status': 'PRELADDER_OBSERVATION_UNAVAILABLE',
                                     'operational_issuances': 0})
        return
    marker('HOST_PREFLIGHT_STARTED.json', {'phase_id': PHASE, 'utc': datetime.now(timezone.utc).isoformat(),
                                        'maximum_version_controls': 1})
    observer = Observer()
    before = owner_snapshot()
    escaped = None
    report = None
    with observer:
        prefix, version, transport_error = None, None, None
        try:
            prefix = baseline._docker_prefix()
            if not prefix or prefix[4] != ENDPOINT:
                raise ValueError('frozen_endpoint_prefix_unavailable_no_fallback')
            version = baseline._bounded_process((*prefix, 'version', '--format', '{{json .}}'),
                                                 timeout_ms=8000, stdout_limit=65536)
        except (OSError, ValueError) as error:
            transport_error = {'type': type(error).__name__, 'message': str(error)}
        version_data = None
        try:
            version_data = json.loads(version.stdout) if version is not None else None
        except (ValueError, TypeError):
            pass
        server = version_data.get('Server') if isinstance(version_data, dict) else None
        capable = (version is not None and version.status == 'sandbox_completed' and version.exit_code == 0
                   and isinstance(server, dict) and server.get('Os') == 'linux'
                   and isinstance(server.get('Version'), str) and bool(server['Version']))
        preflight = {'endpoint': ENDPOINT, 'server_version': server.get('Version') if isinstance(server, dict) else None,
                     'linux_server_version_retrieved': capable, 'metadata': version_data,
                     'control_index': 0 if observer.controls else None, 'host_execution_required': True,
                     'transport_error': transport_error}
        write_json('host_preflight.json', preflight)
        if capable:
            # Clear construction states belonging to the separate read-only
            # preflight. Controls/prefixes stay retained with their own scopes.
            observer.states.clear()
            observer.raw_trace.clear()
            marker('LIVE_ATTEMPT_STARTED.json', {'phase_id': PHASE,
                'utc': datetime.now(timezone.utc).isoformat(), 'maximum_operational_issuances': 1})
            try:
                report = owner.replay()  # The sole public operational issuance.
            except Exception as error:
                # Retain escaping exceptions at the top-level diagnostic, never
                # inside the owner; there is no retry and no altered return.
                escaped = {'type': type(error).__name__, 'message': str(error)}
        else:
            # Endpoint unavailable is never attributed to SANDBOX.2 semantics.
            write_json('live_result.json', {'phase_id': PHASE, 'status': 'HOST_DOCKER_ACCESS_UNAVAILABLE',
                'operational_issuances': 0, 'preflight': preflight})
    # Keep exact live report before any downstream formatting/authentication.
    if report is not None:
        assert report is observer.original_report, 'must retain exact original returned object'
        write_json('SANDBOX2_original_report.json', report)
    pair = original_pair_facts(observer.original_pair) if observer.original_pair else None
    if pair is not None:
        write_json('fresh_original_pair.json', pair)
    write_json('observed_controls.json', observer.controls)
    write_json('runtime_pre_ladder_trace.json', {'lines': observer.raw_trace, 'exceptions': observer.exceptions})
    if not capable:
        write_json('live_result.json', {'phase_id': PHASE, 'status': 'HOST_DOCKER_ACCESS_UNAVAILABLE',
            'operational_issuances': 0, 'preflight': preflight,
            'JAVA1C_invoked': False, 'SYNTH_retried': False, 'runtime_authority_issued': False,
            'observer_restored': observer.restored, 'owner_namespace_unchanged': before == owner_snapshot(),
            'source_hashes': check_sources(), 'endpoint': ENDPOINT, 'exact_frozen_image': IMAGE,
            'preservation': validation.preservation()})
        print(json.dumps({'status': 'HOST_DOCKER_ACCESS_UNAVAILABLE', 'operational_issuances': 0}))
        return
    # Independent final confirmation uses the frozen endpoint and exact name
    # filter; no generic image or container inventory and no cleanup mutation.
    independent = Observer()
    with independent:
        final = baseline._bounded_process((*prefix, 'ps', '-a', '--format', '{{.Names}}',
            '--filter', 'name=runtime-sandbox2-'), timeout_ms=8000)
    names = final.stdout.decode(errors='replace').splitlines() if final.status == 'sandbox_completed' and final.exit_code == 0 else None
    write_json('independent_cleanup_controls.json', independent.controls)
    for row in observer.prefixes:
        path = Path(row['path'])
        row.update(exists_after=path.exists(), is_symlink_after=path.is_symlink())
    for row in observer.workspaces:
        row['removed_after'] = not Path(row['path']).exists()
    controls = observer.controls + independent.controls
    cleanup = {'owner_cleanup_verified': report.get('cleanup_verified') if report else None,
        'owner_remaining_container_count': report.get('phase_container_count_after_teardown') if report else None,
        'independent_remaining_containers': names,
        'independent_zero_containers_verified': names == [],
        'all_control_children_reaped': all(c['process_reaped'] for c in controls),
        'all_control_pipes_closed': all(c['pipes_closed'] for c in controls),
        'all_control_readers_stopped': all(c['readers_surviving'] == 0 for c in controls),
        'observer_restored': observer.restored and independent.restored,
        'private_config_paths': observer.prefixes,
        'all_private_config_paths_absent': all(not r['exists_after'] and not r['is_symlink_after'] for r in observer.prefixes),
        'temporary_workspaces': observer.workspaces,
        'temporary_workspaces_removed': all(r['removed_after'] for r in observer.workspaces),
        'host_socket_final_facts': observer.host_socket_final_facts,
        'host_control_sockets_closed': all(r['closed_after_owner'] for r in observer.host_socket_final_facts),
        'workspace_created': bool(observer.workspaces)}
    cleanup['independent_cleanup_verified'] = all(cleanup[k] for k in
        ('independent_zero_containers_verified', 'all_control_children_reaped', 'all_control_pipes_closed',
         'all_control_readers_stopped', 'observer_restored', 'all_private_config_paths_absent',
         'temporary_workspaces_removed', 'host_control_sockets_closed'))
    classification = classify_steps(observer.states)
    effects = {'SANDBOX2_operational_issuances': 1, 'Docker_version_preflight': 1,
               'SANDBOX2_Docker_controls': len(observer.controls) - 1,
               'independent_cleanup_Docker_controls': len(independent.controls),
               'SANDBOX2_container_create_attempts': sum('create' in c['argv'] for c in observer.controls),
               'SANDBOX2_container_start_attempts': sum('start' in c['argv'] for c in observer.controls),
               'SANDBOX2_host_control_sockets': sum(observer.states.get(key, {}).get('state') == 'PASS'
                    for key in ('host_tcp_socket_construction', 'host_udp_socket_construction')),
               'javac_version_probes': report.get('javac_version_count', 0) if report else 0,
               'java_version_probes': report.get('java_version_count', 0) if report else 0}
    effects.update(dict.fromkeys(('PINNED1A_export', 'PINNED1B', 'PINNED1C', 'BIND1', 'JAVA1C', 'SYNTH',
        'Java_compile_outside_frozen_version_probes', 'JVM_fixture', 'SyntheticStateBox', 'reflection',
        'runtime_lease_consumption', 'reflection_lease_consumption', 'BANK', 'EXECUTOR1R', 'Apply',
        'repository_runtime_writes', 'pulls', 'builds', 'generic_image_inventory',
        'alternative_provider_inspection', 'caller_shell_workload', 'host_mounts', 'outbound_workload_network'), 0))
    result = {'phase_id': PHASE, 'status': 'SANDBOX2_PRELADDER_DIAG_COMPLETE'
              if classification['classification'] != 'PRELADDER_OBSERVATION_UNAVAILABLE'
              else 'PRELADDER_OBSERVATION_UNAVAILABLE',
        'diagnostic_only': True, 'preflight': preflight, 'endpoint': ENDPOINT, 'exact_frozen_image': IMAGE,
        'source_hashes': check_sources(), **classification, 'image_metadata': observer.metadata,
        'escaping_owner_exception': escaped, 'first_container_create_attempted': observer.create_attempted,
        'first_ladder_mode_reached': observer.first_mode,
        'owner_status': report.get('status') if report else None,
        'descriptor_status': pair['descriptor']['status'] if pair else None,
        'receipt_status': pair['receipt']['status'] if pair else None,
        'HMAC_results': pair['HMAC_results'] if pair else None,
        'semantic_eligibility': pair['semantic_eligibility'] if pair else None,
        'stage_count': len(report['stages']) if report else None,
        'cleanup': cleanup, 'operational_effects': effects,
        'forbidden_owner_calls': observer.forbidden_calls,
        'owner_namespace_unchanged': before == owner_snapshot(),
        'JAVA1C_invoked': False, 'SYNTH_retried': False, 'runtime_authority_issued': False,
        'historical_nested_root_cause_established': False, 'preservation': validation.preservation()}
    write_json('live_result.json', result)
    print(json.dumps({key: result[key] for key in ('status', 'classification', 'owner_status',
        'first_failing_step', 'stage_count', 'first_container_create_attempted')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('static', 'live'))
    args = parser.parse_args()
    if args.mode == 'static':
        write_json('static_pre_ladder_audit.json', static_audit())
    else:
        live()
