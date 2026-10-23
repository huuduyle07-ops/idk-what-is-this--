"""Pure diagnostic semantics checks; no Docker, threads or runtime execution."""
import io
import tarfile

import pytest

from scripts import measure_runtime_java_discovery_diag1 as diag
from tests.test_runtime_java1_discovery import _archive, _fixture


@pytest.mark.parametrize('trials,classification', [
    ([], 'UNRESOLVED'),
    ([{'timed_out': True}], 'EXPORT_TRANSPORT_EXCEEDS_BOUND'),
    ([{'completed_within_bound': False}], 'UNRESOLVED'),
    ([{'completed_within_bound': True}], 'UNRESOLVED'),
    ([{'completed_within_bound': True}, {'timed_out': True}], 'PARSER_OR_SCAN_BACKPRESSURE'),
    ([{'completed_within_bound': True}, {'completed_within_bound': True}], 'TRANSIENT_OR_CACHE_SENSITIVE'),
    ([{'completed_within_bound': True}, {'completed_within_bound': False}], 'UNRESOLVED'),
])
def test_classification_keeps_transport_stop_and_does_not_invent_success(trials, classification):
    assert diag.classify(trials) == classification


def test_measured_archive_preserves_exact_original_toolchain_semantics(monkeypatch):
    original_open = tarfile.open
    trial = {'archive_entries_observed': 0}
    expected = diag.original._inspect_tar(_archive(_fixture()))
    monkeypatch.setattr(tarfile, 'open', lambda *a, **k: diag.ArchiveObserver(original_open(*a, **k), trial))
    assert diag.original._inspect_tar(_archive(_fixture())) == expected
    assert trial['archive_entries_observed'] == len(_fixture())


@pytest.mark.parametrize('entries,match', [
    ([('../host/java', b'bad', 'file')], 'image_path_invalid'),
    ([('a', '../../host', 'symlink')], 'image_link_escapes_root'),
])
def test_observer_retains_path_and_link_rejection(monkeypatch, entries, match):
    archive = _archive(entries)
    original_open = tarfile.open
    trial = {'archive_entries_observed': 0}
    monkeypatch.setattr(tarfile, 'open', lambda *a, **k: diag.ArchiveObserver(original_open(*a, **k), trial))
    with pytest.raises(diag.original.LocalJavaDiscoveryError, match=match):
        diag.original._inspect_tar(archive)


def test_observer_retains_original_entry_limit(monkeypatch):
    archive = _archive(_fixture())
    original_open = tarfile.open
    trial = {'archive_entries_observed': 0}
    monkeypatch.setattr(diag.original, 'MAX_ARCHIVE_ENTRIES', 1)
    monkeypatch.setattr(tarfile, 'open', lambda *a, **k: diag.ArchiveObserver(original_open(*a, **k), trial))
    with pytest.raises(diag.original.LocalJavaDiscoveryError, match='image_archive_entry_limit'):
        diag.original._inspect_tar(archive)
    assert trial['archive_entries_observed'] == 2


def test_stream_instrumentation_denies_unbounded_capture_and_bounds_stderr():
    trial = {'stderr_bytes_received': 0, 'stderr_buffer': bytearray()}
    stream = diag.MeasuredPipe(io.BytesIO(b'x' * 9000), trial, 1)
    with pytest.raises(ValueError, match='unbounded_read_denied'):
        stream.read()
    assert len(stream.read(9000)) == 9000
    assert trial['stderr_bytes_received'] == 9000
    assert len(trial['stderr_buffer']) == 8192


def test_raw_drain_reaps_and_closes_after_frozen_timeout(monkeypatch):
    import subprocess
    class Child:
        stdout, stderr = io.BytesIO(), io.BytesIO()
        returncode = None
        killed = False
        def poll(self): return self.returncode
        def kill(self): self.killed = True; self.returncode = -9
        def wait(self, **kwargs): return self.returncode
    child = Child()
    ticks = iter([0, 31])
    monkeypatch.setattr(subprocess, 'Popen', lambda *a, **k: child)
    monkeypatch.setattr(diag.time, 'perf_counter', lambda: next(ticks))
    monkeypatch.setattr(diag, 'PipePoller', lambda streams: type('Poller', (), {'close': lambda self: None})())
    trial = {}
    with pytest.raises(diag.original.LocalJavaDiscoveryError, match='image_export_timeout'):
        diag.raw_drain(('fixed-docker',), 'stopped', trial)
    assert trial['timed_out'] and child.killed
    assert child.stdout.closed and child.stderr.closed
    assert diag.original.EXPORT_TIMEOUT_MS == 30000


def test_raw_success_does_not_parse_or_return_discovery_toolchains(monkeypatch):
    import os
    import subprocess
    class Child:
        stdout, stderr = io.BytesIO(b'not-even-a-tar'), io.BytesIO()
        returncode = 0
        def poll(self): return 0
        def wait(self, **kwargs): return 0
    child = Child()
    monkeypatch.setattr(subprocess, 'Popen', lambda *a, **k: child)
    monkeypatch.setattr(diag, 'PipePoller', lambda streams: type('Poller', (), {
        'ready': lambda self, stream: -1, 'close': lambda self: None})())
    monkeypatch.setattr(diag.original, '_inspect_tar', lambda *a: pytest.fail('raw control parsed archive'))
    trial = {}
    assert diag.raw_drain(('fixed-docker',), 'stopped', trial) == ()
    assert not trial['timed_out']
    assert child.stdout.closed and child.stderr.closed


def test_raw_timeout_stops_before_parser_inventory_or_provider_verification(monkeypatch, tmp_path):
    import json
    sandbox = diag.original.sandbox
    prefix = ('fixed-docker', '--host', 'fixed-endpoint')
    monkeypatch.setattr(sandbox, '_docker_prefix', lambda: prefix)
    monkeypatch.setattr(sandbox, '_local_endpoint', lambda: prefix[-1])
    monkeypatch.setattr(diag.tempfile, 'tempdir', str(tmp_path))
    calls = []
    def control(argv, **kwargs):
        command = argv[len(prefix):]
        calls.append(command)
        if command[0] == 'version':
            output = {'Server': {'Version': 'fixture'}}
        elif command[:2] == ('image', 'inspect'):
            assert command[2] == diag.TARGET
            output = {'Id': diag.TARGET, 'Os': 'linux', 'Architecture': 'amd64',
                'Size': 1, 'Config': {}}
        elif command[0] == 'ps':
            return sandbox._Capture('sandbox_completed', 0, b'', b'', False)
        else:
            pytest.fail('unexpected control command')
        return sandbox._Capture('sandbox_completed', 0, json.dumps(output).encode(), b'', False)
    monkeypatch.setattr(sandbox, '_bounded_process', control)
    def drain(prefix, name, trial):
        assert trial['mode'] == 'raw_drain'
        trial['timed_out'] = True
        raise diag.original.LocalJavaDiscoveryError('image_export_timeout')
    monkeypatch.setattr(diag, 'raw_drain', drain)
    def container(prefix, image, profile):
        assert image == diag.TARGET
        try:
            diag.original._export_filesystem(prefix, 'fixture-stopped')
        except diag.original.LocalJavaDiscoveryError as error:
            return (), str(error), True
        pytest.fail('unexpected export completion')
    monkeypatch.setattr(diag.original, '_container_files', container)
    monkeypatch.setattr(diag.original, 'discover_local_java_artifacts', lambda *a, **k: pytest.fail('full inventory invoked'))
    result = diag.measure()
    assert result['trial_order'] == ['raw_drain']
    assert result['root_cause_classification'] == 'EXPORT_TRANSPORT_EXCEEDS_BOUND'
    assert result['effects']['parser_path_export_calls'] == 0
    assert not result['java1d_retried'] and not result['java1c_invoked']
    assert not result['production_discovery_success_issued']
    assert result['authority_changes'] == []
    assert not any(command[0] in ('start', 'exec', 'pull', 'build') for command in calls)
