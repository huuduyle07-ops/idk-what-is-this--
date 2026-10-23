"""Bounded, observation-only measurement of the known JAVA.1D export blocker.

No inventory, provider verification, receipt issuance or runtime capability.
Run once with an exclusive output file. A raw timeout stops before parsing.
"""
from __future__ import annotations

from contextlib import ExitStack
from dataclasses import asdict
import argparse
import json
import os
from pathlib import Path
import selectors
import subprocess
import sys
import tempfile
import threading
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
from core import sandboxed_java_toolchain_discovery as original

TARGET = 'sha256:09361da47d33ad0d44f89947d5e99003e94594e885328cdb5cd7b1c515a1a089'
PHASE = 'RUNTIME.JAVA.DISCOVERY.DIAG.1'
COMPLETE = 'RUNTIME_JAVA_DISCOVERY_DIAG_1_COMPLETE_WITH_WARNINGS'


def milliseconds(seconds):
    return round(seconds * 1000, 3)


def classify(trials):
    if not trials:
        return 'UNRESOLVED'
    raw = trials[0]
    if raw.get('timed_out'):
        return 'EXPORT_TRANSPORT_EXCEEDS_BOUND'
    if not raw.get('completed_within_bound') or len(trials) != 2:
        return 'UNRESOLVED'
    parser = trials[1]
    if parser.get('timed_out'):
        # The raw control also changes host capture. Do not attribute this
        # difference to the semantic parser alone without CPU/wait evidence.
        return 'PARSER_OR_SCAN_BACKPRESSURE'
    if parser.get('completed_within_bound'):
        return 'TRANSIENT_OR_CACHE_SENSITIVE'
    return 'UNRESOLVED'


class MeasuredPipe:
    def __init__(self, stream, trial, index):
        self.stream, self.trial, self.index = stream, trial, index

    def __getattr__(self, name):
        return getattr(self.stream, name)

    def read(self, size=-1):
        if size < 0:
            raise ValueError('diagnostic_unbounded_read_denied')
        begin = time.perf_counter()
        data = self.stream.read(size)
        end = time.perf_counter()
        if self.index == 0:
            t = self.trial
            t['stdout_read_calls'] += 1
            t['reader_wait_and_copy_seconds'] += end - begin
            t['bytes_received'] += len(data)
            if data and t['first_byte_at'] is None:
                t['first_byte_at'] = end
        else:
            self.trial['stderr_bytes_received'] += len(data)
            remaining = 8192 - len(self.trial['stderr_buffer'])
            self.trial['stderr_buffer'].extend(data[:remaining])
        return data


class MeasuredChild:
    def __init__(self, child, trial):
        self.child, self.trial = child, trial
        self.stdout = MeasuredPipe(child.stdout, trial, 0)
        self.stderr = MeasuredPipe(child.stderr, trial, 1)

    def __getattr__(self, name):
        return getattr(self.child, name)

    def kill(self):
        if self.trial['kill_at'] is None:
            self.trial['kill_at'] = time.perf_counter()
        return self.child.kill()

    def wait(self, *args, **kwargs):
        result = self.child.wait(*args, **kwargs)
        if self.trial['reaped_at'] is None:
            self.trial['reaped_at'] = time.perf_counter()
        return result


class ArchiveObserver:
    """Count entries yielded to the unchanged original semantic scanner."""
    def __init__(self, archive, trial):
        self.archive, self.trial = archive, trial

    def __getattr__(self, name):
        return getattr(self.archive, name)

    def __enter__(self):
        self.archive.__enter__()
        return self

    def __exit__(self, *args):
        return self.archive.__exit__(*args)

    def __iter__(self):
        for member in self.archive:
            self.trial['archive_entries_observed'] += 1
            yield member


class PipePoller:
    """One-thread incremental capture; Windows anonymous pipes are not sockets."""
    def __init__(self, streams):
        self.streams, self.selector = streams, None
        if os.name != 'nt':
            self.selector = selectors.DefaultSelector()
            for stream in streams:
                os.set_blocking(stream.fileno(), False)
                self.selector.register(stream, selectors.EVENT_READ)

    def ready(self, stream):
        if os.name == 'nt':
            import _winapi
            import msvcrt
            try:
                # On this Python, size=0 returns (available, bytes_left).
                available = _winapi.PeekNamedPipe(msvcrt.get_osfhandle(stream.fileno()), 0)[0]
                return min(65536, available)
            except OSError as error:
                if error.winerror == 109:
                    return -1
                raise
        return 65536 if any(key.fileobj is stream for key, _ in self.selector.select(0)) else 0

    def close(self):
        if self.selector is not None:
            self.selector.close()


def raw_drain(prefix, name, trial):
    env = {key: os.environ[key] for key in ('SystemRoot', 'WINDIR') if key in os.environ}
    env['CATTUS_SANDBOX_HOST_ONLY'] = 'synthetic-host-only-secret'
    child = poller = None
    trial['timed_out'] = False
    trial.update(raw_poll_iterations=0, raw_idle_sleep_ms=0, raw_pipe_probe_ms=0)
    cpu = time.thread_time()
    try:
        child = subprocess.Popen((*prefix, 'export', name), stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False, env=env,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        trial['budget_anchor'] = time.perf_counter()
        deadline = trial['budget_anchor'] + original.EXPORT_TIMEOUT_MS / 1000
        poller = PipePoller((child.stdout, child.stderr))
        eof = [False, False]
        while not all(eof) or child.poll() is None:
            trial['raw_poll_iterations'] += 1
            if time.perf_counter() >= deadline:
                trial['timed_out'] = True
                raise original.LocalJavaDiscoveryError('image_export_timeout')
            activity = False
            for index, stream in enumerate((child.stdout, child.stderr)):
                if eof[index]:
                    continue
                probe = time.perf_counter()
                available = poller.ready(stream)
                trial['raw_pipe_probe_ms'] += milliseconds(time.perf_counter() - probe)
                if available == -1:
                    eof[index] = True
                elif available:
                    begin = time.perf_counter()
                    data = os.read(stream.fileno(), available)
                    end = time.perf_counter()
                    activity = True
                    if not data:
                        eof[index] = True
                    if index == 0:
                        trial['bytes_received'] += len(data)
                        trial['stdout_read_calls'] += 1
                        trial['reader_wait_and_copy_seconds'] += end - begin
                        if data and trial['first_byte_at'] is None:
                            trial['first_byte_at'] = end
                        if trial['bytes_received'] > original.MAX_ARCHIVE_BYTES:
                            raise original.LocalJavaDiscoveryError('image_archive_size_limit')
                    else:
                        trial['stderr_bytes_received'] += len(data)
                        trial['stderr_buffer'].extend(data[:8192 - len(trial['stderr_buffer'])])
                        if trial['stderr_bytes_received'] > 8192:
                            raise original.LocalJavaDiscoveryError('image_export_stderr_limit')
            if not activity:
                sleep_start = time.perf_counter()
                time.sleep(min(.001, max(0, deadline - time.perf_counter())))
                trial['raw_idle_sleep_ms'] += milliseconds(time.perf_counter() - sleep_start)
        trial['stream_finished_at'] = time.perf_counter()
        if child.wait(timeout=2) != 0:
            raise original.LocalJavaDiscoveryError('image_export_failed')
        return ()  # No discovery claim; the archive was never interpreted.
    finally:
        trial['raw_main_thread_cpu_ms'] = milliseconds(time.thread_time() - cpu)
        if poller is not None:
            poller.close()
        if child is not None:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=2)
            child.stdout.close()
            child.stderr.close()


def measure():
    if original.EXPORT_TIMEOUT_MS != 30000:
        raise ValueError('frozen_export_timeout_changed')
    sandbox = original.sandbox
    prefix = sandbox._docker_prefix()
    if not prefix or prefix[-1] != sandbox._local_endpoint():
        raise ValueError('frozen_local_endpoint_unavailable')
    result = {'phase_id': PHASE, 'status': COMPLETE, 'target_image': TARGET,
        'original_export_timeout_ms': original.EXPORT_TIMEOUT_MS,
        'local_endpoint': prefix[-1], 'trials': [], 'docker_controls': [],
        'host_children': [], 'thread_start_attempts': [],
        'python_threads_before': threading.active_count(),
        'production_timeout_changed': False, 'production_discovery_code_changed': False,
        'discovery_scope_changed': False, 'production_discovery_success_issued': False,
        'java1d_retried': False, 'java1c_invoked': False, 'compat2_created': False,
        'authority_changes': [], 'compatibility_relations_created': 0,
        'optional_third_trial_count': 0, 'archive_persisted': False}
    active = {'stage': 'image_identity', 'trial': None}
    children = []
    popen, bounded = subprocess.Popen, sandbox._bounded_process
    thread_start, export = threading.Thread.start, original._export_filesystem
    tar_open, inspect_tar, clock = original.tarfile.open, original._inspect_tar, original.monotonic

    def observe_start(thread, *args, **kwargs):
        result['thread_start_attempts'].append({'stage': active['stage'],
            'trial': active['trial']['mode'] if active['trial'] else None,
            'target': getattr(getattr(thread, '_target', None), '__name__', '')})
        return thread_start(thread, *args, **kwargs)

    def observe_popen(argv, *args, **kwargs):
        command = tuple(argv[len(prefix):])
        if tuple(argv[:len(prefix)]) != tuple(prefix) or command[0] not in ('version', 'image', 'create', 'inspect', 'export', 'rm', 'ps'):
            raise ValueError('unexpected_diagnostic_process')
        begin = time.perf_counter()
        child = popen(argv, *args, **kwargs)
        children.append((child, command[0]))
        if command[0] == 'export':
            trial = active['trial']
            trial.update(export_launch_at=begin, child_launched_at=time.perf_counter())
            proxy = MeasuredChild(child, trial)
            trial['_child'] = proxy
            return proxy
        return child

    def control(argv, **kwargs):
        command = tuple(argv[len(prefix):])
        before = time.perf_counter()
        prior = active['stage']
        active['stage'] = command[0]
        try:
            captured = bounded(argv, **kwargs)
        finally:
            active['stage'] = prior
        record = {'command': list(command), 'elapsed_ms': milliseconds(time.perf_counter() - before),
            'status': captured.status, 'exit_code': captured.exit_code,
            'stderr': captured.stderr.decode('utf-8', 'replace')[:8192]}
        result['docker_controls'].append(record)
        if active['trial'] is not None:
            trial = active['trial']
            trial['control_calls'].append(record)
            if command[0] == 'create':
                trial['container_name'] = command[command.index('--name') + 1]
                trial['container_id'] = captured.stdout.decode('ascii', 'replace').strip()
        return captured

    def archive_open(*args, **kwargs):
        return ArchiveObserver(tar_open(*args, **kwargs), active['trial'])

    def parser(stream):
        trial = active['trial']
        begin, cpu, reading = time.perf_counter(), time.thread_time(), trial['reader_wait_and_copy_seconds']
        try:
            return inspect_tar(stream)
        finally:
            trial['parser_wall_ms'] = milliseconds(time.perf_counter() - begin)
            trial['parser_main_thread_cpu_ms'] = milliseconds(time.thread_time() - cpu)
            trial['parser_work_estimate_ms'] = max(0, trial['parser_wall_ms'] - milliseconds(trial['reader_wait_and_copy_seconds'] - reading))

    def monotonic():
        value = clock()
        trial = active['trial']
        if trial is not None and trial['budget_anchor'] is None:
            trial['budget_anchor'] = time.perf_counter()
        return value

    def measured_export(prefix, name):
        trial = active['trial']
        trial['container_name'] = name
        active['stage'] = 'export'
        try:
            if trial['mode'] == 'raw_drain':
                return raw_drain(prefix, name, trial)
            return export(prefix, name)
        except original.LocalJavaDiscoveryError as error:
            trial['timed_out'] = str(error) == 'image_export_timeout'
            raise
        finally:
            now = time.perf_counter()
            if '_child' in trial:
                child = trial.pop('_child')
                trial['export_exit_code'] = child.returncode
                trial['child_reaped'] = trial['reaped_at'] is not None and child.returncode is not None
                trial['pipes_closed'] = all(s is None or s.closed for s in (child.stdin, child.stdout, child.stderr))
                anchor = trial['budget_anchor']
                trial['elapsed_ms'] = milliseconds(now - anchor)
                trial['export_process_launch_latency_ms'] = milliseconds(trial['child_launched_at'] - trial['export_launch_at'])
                trial['time_to_first_byte_ms'] = milliseconds(trial['first_byte_at'] - anchor) if trial['first_byte_at'] else None
                trial['kill_requested_after_ms'] = milliseconds(trial['kill_at'] - anchor) if trial['kill_at'] else None
                trial['supervisor_overshoot_ms'] = max(0, trial['kill_requested_after_ms'] - 30000) if trial['timed_out'] and trial['kill_at'] else None
                trial['termination_ms'] = milliseconds(trial['reaped_at'] - trial['kill_at']) if trial['kill_at'] and trial['reaped_at'] else None
                trial['stream_or_reap_elapsed_ms'] = milliseconds((trial['stream_finished_at'] or trial['reaped_at'] or now) - anchor)
                trial['average_stream_bytes_per_second'] = round(trial['bytes_received'] / max((trial['stream_finished_at'] or now) - anchor, .000001), 3)
            active['stage'] = 'trial_control'

    with ExitStack() as stack:
        for obj, name, replacement in ((subprocess, 'Popen', observe_popen),
                (threading.Thread, 'start', observe_start), (sandbox, '_bounded_process', control),
                (original, '_export_filesystem', measured_export), (original.tarfile, 'open', archive_open),
                (original, '_inspect_tar', parser), (original, 'monotonic', monotonic)):
            stack.enter_context(patch.object(obj, name, replacement))
        version = control((*prefix, 'version', '--format', '{{json .}}'), timeout_ms=8000, stdout_limit=65536)
        if version.status != 'sandbox_completed' or version.exit_code != 0:
            raise ValueError('local_docker_backend_unavailable')
        result['server_version'] = json.loads(version.stdout)['Server']['Version']
        identity = control((*prefix, 'image', 'inspect', TARGET, '--format', '{{json .}}'), timeout_ms=8000, stdout_limit=65536)
        if identity.status != 'sandbox_completed' or identity.exit_code != 0:
            raise ValueError('exact_image_not_available')
        metadata = json.loads(identity.stdout)
        artifact = original._image_metadata(TARGET, metadata)
        if artifact.os != 'linux' or artifact.architecture != 'amd64' or artifact.image_declared_volumes:
            raise ValueError('original_image_eligibility_changed')
        result['image_metadata'] = asdict(artifact)
        result['image_metadata'].update(created=metadata.get('Created'), rootfs_layer_count=len(metadata.get('RootFS', {}).get('Layers', [])))
        with tempfile.TemporaryDirectory(prefix='runtime-java-discovery-diag1-') as directory:
            profile = Path(directory) / 'seccomp.json'
            profile.write_text(sandbox._json(sandbox._SECCOMP), encoding='utf-8')
            for mode in ('raw_drain', 'original_parser'):
                trial = {'mode': mode, 'container_started': False, 'control_calls': [],
                    'bytes_received': 0, 'archive_entries_observed': 0 if mode == 'original_parser' else None,
                    'stdout_read_calls': 0, 'reader_wait_and_copy_seconds': 0,
                    'stderr_bytes_received': 0, 'stderr_buffer': bytearray(),
                    'first_byte_at': None, 'kill_at': None, 'reaped_at': None,
                    'budget_anchor': None, 'stream_finished_at': None, 'timed_out': False,
                    'capture_method': 'single_thread_PeekNamedPipe_incremental_os_read' if mode == 'raw_drain' and os.name == 'nt' else 'single_thread_selector_os_read' if mode == 'raw_drain' else 'unchanged_original_buffered_stdout_main_thread_guard_and_stderr_threads',
                    'python_threads_before': threading.active_count()}
                active.update(trial=trial, stage='trial_control')
                starts = len(result['thread_start_attempts'])
                begin = time.perf_counter()
                _, status, cleanup = original._container_files(prefix, TARGET, profile)
                trial.update(original_container_status=status, container_cleanup_verified=cleanup,
                    python_threads_after=threading.active_count())
                trial['setup_latency_ms'] = round(sum(c['elapsed_ms'] for c in trial['control_calls'] if c['command'][0] in ('create', 'inspect') and c['exit_code'] == 0), 3)
                trial['container_cleanup_ms'] = round(sum(c['elapsed_ms'] for c in trial['control_calls'] if c['command'][0] == 'rm' or c['exit_code'] != 0), 3)
                trial['trial_total_ms'] = milliseconds(time.perf_counter() - begin)
                trial['thread_start_attempts'] = result['thread_start_attempts'][starts:]
                trial['export_thread_start_count'] = sum(t['stage'] == 'export' for t in trial['thread_start_attempts'])
                trial['stderr'] = bytes(trial.pop('stderr_buffer')).decode('utf-8', 'replace')
                trial['completed_within_bound'] = bool(status == 'image_files_inspected' and not trial['timed_out'] and trial.get('stream_or_reap_elapsed_ms', float('inf')) <= 30000 and trial.get('export_exit_code') == 0)
                trial['reader_wait_and_copy_ms'] = milliseconds(trial.pop('reader_wait_and_copy_seconds'))
                for key in ('first_byte_at', 'kill_at', 'reaped_at', 'budget_anchor', 'export_launch_at', 'child_launched_at', 'stream_finished_at'):
                    trial.pop(key, None)
                result['trials'].append(trial)
                print(json.dumps({'trial': mode, 'elapsed_ms': trial.get('elapsed_ms'), 'bytes': trial['bytes_received'], 'timed_out': trial['timed_out'], 'cleanup': cleanup}), flush=True)
                if trial['timed_out'] or not trial['completed_within_bound'] or not cleanup or not trial.get('child_reaped') or not trial.get('pipes_closed'):
                    break
            active.update(trial=None, stage='final_cleanup_check')
        result['temporary_controller_state_removed'] = not Path(directory).exists()
        absent = control((*prefix, 'ps', '--all', '--filter', 'name=runtime-java1-discovery-', '--format', '{{.Names}}'), timeout_ms=8000, stdout_limit=65536)
        names = set(absent.stdout.decode().splitlines())
        result['remaining_diagnostic_containers'] = sum(t.get('container_name') in names for t in result['trials']) if absent.status == 'sandbox_completed' and absent.exit_code == 0 else None

    for child, command in children:
        result['host_children'].append({'pid': child.pid, 'command': command,
            'reaped': child.returncode is not None,
            'pipes_closed': all(s is None or s.closed for s in (child.stdin, child.stdout, child.stderr))})
    result['python_threads_after'] = threading.active_count()
    result['trial_count'] = len(result['trials'])
    result['trial_order'] = [t['mode'] for t in result['trials']]
    result['root_cause_classification'] = classify(result['trials'])
    result['cleanup_verified'] = (result['remaining_diagnostic_containers'] == 0
        and result['temporary_controller_state_removed']
        and all(t['container_cleanup_verified'] for t in result['trials'])
        and all(c['reaped'] and c['pipes_closed'] for c in result['host_children']))
    result['effects'] = {'image_identity_inspections': 1,
        'container_creates': sum(c['command'][0] == 'create' for c in result['docker_controls']),
        'export_calls': result['trial_count'], 'raw_drain_export_calls': 1,
        'parser_path_export_calls': sum(t['mode'] == 'original_parser' for t in result['trials']),
        'optional_third_diagnostic_export_calls': 0, 'docker_control_calls': len(result['docker_controls']),
        'docker_total_calls': len(children), 'host_child_processes': len(children),
        **{key: 0 for key in ('container_starts', 'java_executions', 'javac_executions',
            'java_compilations', 'source_projections', 'network', 'shell', 'host_mounts',
            'synth_runtime_lease_consumption', 'reflection_lease_consumption', 'BANK',
            'EXECUTOR_1R', 'Apply', 'repository_runtime_writes')}}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    # Reserve the result before effects, so an existing report cannot cause a
    # silent second live measurement or overwrite any earlier evidence.
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        result = measure()
        stream.write(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({k: result[k] for k in ('status', 'root_cause_classification', 'trial_count', 'cleanup_verified')}, indent=2))


if __name__ == '__main__':
    main()
