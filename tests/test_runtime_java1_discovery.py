"""Pure local artifact inspection negatives; no Docker, Java or repository scan."""
from dataclasses import FrozenInstanceError
from hashlib import sha256
import io
import json
import tarfile

import pytest

from core import sandboxed_java_toolchain_discovery as owner


IMAGE_ID = 'sha256:' + 'a' * 64


def _elf(machine=62, *, bits=2):
    data = bytearray(64)
    data[:4] = b'\x7fELF'
    data[4:6] = bytes((bits, 1))
    data[16:18] = (3).to_bytes(2, 'little')
    data[18:20] = machine.to_bytes(2, 'little')
    return bytes(data)


def _archive(entries):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w') as archive:
        for name, content, kind in entries:
            member = tarfile.TarInfo(name)
            member.mode = 0o755
            if kind == 'symlink':
                member.type, member.linkname = tarfile.SYMTYPE, content
                archive.addfile(member)
            else:
                member.mode = 0o644 if kind == 'nonexec' else 0o755
                member.size = len(content)
                archive.addfile(member, io.BytesIO(content))
    stream.seek(0)
    return stream


def _fixture(*, java=None, javac=None, controller=True):
    entries = [('opt/jdk/bin/java', _elf() if java is None else java, 'file'),
               ('opt/jdk/bin/javac', _elf() if javac is None else javac, 'file'),
               ('usr/bin/java', '/opt/jdk/bin/java', 'symlink'),
               ('usr/bin/javac', '/opt/jdk/bin/javac', 'symlink')]
    if controller:
        entries += [('usr/local/bin/python3.12', _elf(), 'file'),
                    ('usr/local/bin/python3', 'python3.12', 'symlink'),
                    ('usr/local/bin/python', 'python3', 'symlink')]
    return entries


def _metadata(**changes):
    result = {'Id': IMAGE_ID, 'Os': 'linux', 'Architecture': 'amd64',
        'Variant': '', 'Size': 12345, 'RepoDigests': [],
        'Config': {'User': 'root', 'Env': ['PATH=/opt/jdk/bin:/usr/bin'], 'Volumes': {}}}
    result.update(changes)
    return result


def _capture(stdout=b'', *, exit_code=0):
    return owner.sandbox._Capture('sandbox_completed', exit_code, stdout, b'', False)


def test_exact_linux_amd64_executable_pairs_and_controller_hash_from_stream():
    pairs = owner._inspect_tar(_archive(_fixture()))
    assert len(pairs) == 1
    pair = pairs[0]
    assert pair.java_path == '/opt/jdk/bin/java'
    assert pair.javac_path == '/opt/jdk/bin/javac'
    assert pair.controller_path == '/usr/local/bin/python'
    assert pair.java_sha256 == pair.javac_sha256 == pair.controller_sha256 == sha256(_elf()).hexdigest()
    with pytest.raises(FrozenInstanceError):
        pair.java_path = '/host/java.exe'


@pytest.mark.parametrize('invalid', (b'MZ' + b'\x00' * 62, _elf(183), _elf(bits=1), b'#!/bin/sh\njava\n'))
def test_windows_wrong_architecture_and_scripts_never_become_java_runtime(invalid):
    assert owner._inspect_tar(_archive(_fixture(java=invalid))) == ()
    assert owner._inspect_tar(_archive(_fixture(javac=invalid))) == ()


def test_nonexecutable_java_and_compiler_files_are_ineligible():
    entries = _fixture()
    entries[0] = (entries[0][0], entries[0][1], 'nonexec')
    assert owner._inspect_tar(_archive(entries)) == ()


def test_root_only_executable_or_parent_directory_cannot_be_nonroot_toolchain():
    member = tarfile.TarInfo('opt/jdk/bin/java')
    member.uid = member.gid = 0
    member.mode = 0o700
    assert owner._nonroot_can_execute(member) is False
    assert owner._nonroot_can_traverse('/opt/jdk/bin/java', {'/opt/jdk': False}) is False
    member.uid = 65534
    assert owner._nonroot_can_execute(member) is True
    member.uid = 0
    member.gid = 65534
    member.mode = 0o710
    assert owner._nonroot_can_execute(member) is True


def test_java_pair_without_frozen_projection_controller_is_reported_but_unusable():
    pair, = owner._inspect_tar(_archive(_fixture(controller=False)))
    assert pair.controller_path == pair.controller_sha256 == ''
    artifact = owner.LocalJavaArtifact(IMAGE_ID, toolchains=(pair,),
        status='local_java_controller_unavailable')
    discovery = owner.LocalJavaDiscovery((artifact,), True, True, 'no_eligible_exact_local_java_toolchain')
    assert discovery.available_toolchains == ()


def test_compiler_and_runtime_must_resolve_into_same_exact_toolchain_directory():
    entries = _fixture()
    entries[1] = ('opt/other/bin/javac', _elf(), 'file')
    entries[3] = ('usr/bin/javac', '/opt/other/bin/javac', 'symlink')
    assert owner._inspect_tar(_archive(entries)) == ()


@pytest.mark.parametrize('path', ('../host/java', '/opt/../host/java', 'C:\\host\\java.exe', 'bad\x00path'))
def test_image_paths_cannot_escape_or_become_windows_host_paths(path):
    with pytest.raises(owner.LocalJavaDiscoveryError):
        owner._image_path(path)


def test_link_cycle_and_root_escape_are_rejected():
    with pytest.raises(owner.LocalJavaDiscoveryError, match='image_link_cycle'):
        owner._resolve_link('/a', {'/a': '/b', '/b': '/a'})
    with pytest.raises(owner.LocalJavaDiscoveryError, match='image_link_escapes_root'):
        owner._link_target('/a', '../../host')
    assert owner._resolve_link('/opt/jdk/bin/java', {'/opt/jdk': '/usr/lib/jvm/jdk'}) == '/usr/lib/jvm/jdk/bin/java'


def test_archive_hard_cap_applies_while_reading_and_unbounded_reads_are_denied(monkeypatch):
    monkeypatch.setattr(owner, 'MAX_ARCHIVE_BYTES', 4)
    stream = owner._BoundedArchiveStream(io.BytesIO(b'12345'))
    assert stream.read(4) == b'1234'
    with pytest.raises(owner.LocalJavaDiscoveryError, match='image_archive_size_limit'):
        stream.read(4)
    with pytest.raises(owner.LocalJavaDiscoveryError, match='archive_unbounded_read_denied'):
        owner._BoundedArchiveStream(io.BytesIO()).read()


def test_archive_entry_limit_does_not_expand_to_host_extraction(monkeypatch):
    monkeypatch.setattr(owner, 'MAX_ARCHIVE_ENTRIES', 1)
    with pytest.raises(owner.LocalJavaDiscoveryError, match='image_archive_entry_limit'):
        owner._inspect_tar(_archive(_fixture()))


def test_metadata_binds_immutable_identity_platform_environment_size_and_image_user():
    artifact = owner._image_metadata(IMAGE_ID, _metadata())
    assert artifact.image_identity == IMAGE_ID
    assert artifact.os == 'linux' and artifact.architecture == 'amd64'
    assert artifact.image_user == 'root'
    assert artifact.image_environment == ('PATH=/opt/jdk/bin:/usr/bin',)
    assert artifact.image_size_bytes == 12345
    with pytest.raises(owner.LocalJavaDiscoveryError):
        owner._image_metadata(IMAGE_ID, _metadata(Id='mutable:tag'))
    with pytest.raises(owner.LocalJavaDiscoveryError):
        owner._image_metadata(IMAGE_ID, _metadata(Config=['not metadata']))


def test_no_local_backend_never_creates_inspection_resources(monkeypatch):
    monkeypatch.setattr(owner.sandbox, '_docker_prefix', lambda: ())
    def denied(*args, **kwargs):
        raise AssertionError('missing artifact path attempted effects')
    monkeypatch.setattr(owner.sandbox, '_bounded_process', denied)
    monkeypatch.setattr(owner.tempfile, 'TemporaryDirectory', denied)
    result = owner.discover_local_java_artifacts()
    assert result.artifacts == result.available_toolchains == ()
    assert result.complete_inventory is False
    assert result.cleanup_verified is True


@pytest.mark.parametrize('os_name,architecture', (('windows', 'amd64'), ('linux', 'arm64')))
def test_wrong_platform_inventory_never_creates_or_starts_container(monkeypatch, os_name, architecture):
    monkeypatch.setattr(owner.sandbox, '_docker_prefix', lambda: ('phase-fixed-docker',))
    calls = []
    def control(argv, **kwargs):
        calls.append(argv[1:])
        if argv[1] == 'version':
            return _capture(json.dumps({'Server': {'Os': 'linux', 'Version': '1'}}).encode())
        if argv[1:3] == ('image', 'ls'):
            return _capture((IMAGE_ID + '\n').encode())
        if argv[1:3] == ('image', 'inspect'):
            return _capture(json.dumps(_metadata(Os=os_name, Architecture=architecture)).encode())
        raise AssertionError('platform rejection attempted Docker lifecycle')
    monkeypatch.setattr(owner.sandbox, '_bounded_process', control)
    result = owner.discover_local_java_artifacts()
    assert result.complete_inventory and result.cleanup_verified
    assert result.available_toolchains == ()
    assert result.artifacts[0].status == 'local_image_platform_ineligible'
    assert not any(command[0] in ('create', 'start', 'exec', 'pull', 'build') for command in calls)


def test_declared_image_volumes_are_rejected_before_container_creation(monkeypatch):
    monkeypatch.setattr(owner.sandbox, '_docker_prefix', lambda: ('phase-fixed-docker',))
    def control(argv, **kwargs):
        if argv[1] == 'version':
            return _capture(json.dumps({'Server': {'Os': 'linux', 'Version': '1'}}).encode())
        if argv[1:3] == ('image', 'ls'):
            return _capture((IMAGE_ID + '\n').encode())
        if argv[1:3] == ('image', 'inspect'):
            metadata = _metadata()
            metadata['Config']['Volumes'] = {'/data': {}}
            return _capture(json.dumps(metadata).encode())
        raise AssertionError('declared mount attempted Docker lifecycle')
    monkeypatch.setattr(owner.sandbox, '_bounded_process', control)
    result = owner.discover_local_java_artifacts()
    assert result.complete_inventory and result.cleanup_verified
    assert result.artifacts[0].status == 'local_image_mounts_ineligible'
    assert result.available_toolchains == ()


def test_empty_measured_inventory_is_complete_without_any_container_or_host_file(monkeypatch):
    monkeypatch.setattr(owner.sandbox, '_docker_prefix', lambda: ('phase-fixed-docker',))
    def control(argv, **kwargs):
        if argv[1] == 'version':
            return _capture(json.dumps({'Server': {'Os': 'linux', 'Version': '1'}}).encode())
        if argv[1:3] == ('image', 'ls'):
            return _capture()
        raise AssertionError('empty inventory attempted effects')
    monkeypatch.setattr(owner.sandbox, '_bounded_process', control)
    monkeypatch.setattr(owner.tempfile, 'TemporaryDirectory', lambda **kwargs: pytest.fail('empty inventory created host file'))
    result = owner.discover_local_java_artifacts()
    assert result.complete_inventory and result.cleanup_verified
    assert result.reason == 'no_eligible_exact_local_java_toolchain'


@pytest.mark.parametrize('removed', (False, True))
def test_export_failure_still_removes_stopped_container_and_measures_absence(monkeypatch, removed):
    calls, inspected = [], [False]
    def control(argv, **kwargs):
        calls.append(argv[1:])
        if argv[1] == 'create':
            assert '--pull' in argv and argv[argv.index('--pull') + 1] == 'never'
            assert '--network' in argv and argv[argv.index('--network') + 1] == 'none'
            assert '--user' in argv and argv[argv.index('--user') + 1] == '65534:65534'
            return _capture(b'phase-container-id\n')
        if argv[1] == 'inspect' and not inspected[0]:
            inspected[0] = True
            return _capture(b'{}')
        if argv[1] == 'rm':
            return _capture(exit_code=0 if removed else 1)
        if argv[1] == 'inspect':
            return owner.sandbox._Capture('sandbox_completed', 1 if removed else 0,
                b'' if removed else b'false', b'No such object' if removed else b'', False)
        raise AssertionError('inspection attempted a workload')
    monkeypatch.setattr(owner.sandbox, '_bounded_process', control)
    monkeypatch.setattr(owner, '_stopped_configuration_safe', lambda *args: True)
    def export_failed(*args):
        raise owner.LocalJavaDiscoveryError('image_export_timeout')
    monkeypatch.setattr(owner, '_export_filesystem', export_failed)
    pairs, status, cleanup = owner._container_files(('fixed-docker',), IMAGE_ID, 'phase-seccomp')
    assert pairs == () and status == 'image_export_timeout'
    assert cleanup is removed
    assert any(command[0] == 'rm' for command in calls)
    assert not any(command[0] in ('start', 'exec', 'pull', 'build') for command in calls)
