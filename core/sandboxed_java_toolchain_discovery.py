"""RUNTIME.JAVA.1 local image inspection, without starting any workload.

Only the frozen sandbox owner's fixed local Docker endpoint is queried. Image
files are streamed from a stopped, phase-owned container; nothing is extracted
onto the host. This module neither acquires artifacts nor launches Java.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import subprocess
import tarfile
import tempfile
from threading import Event, Thread
from time import monotonic, perf_counter

from core import candidate_runtime_sandbox as sandbox

MAX_ARCHIVE_BYTES = 2 * 1024 * 1024 * 1024
MAX_EXECUTABLE_BYTES = 128 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 250_000
EXPORT_TIMEOUT_MS = 30_000
_CONTROLLER = '/usr/local/bin/python'
_IDENTITY = re.compile(r'sha256:[0-9a-f]{64}\Z')


@dataclass(frozen=True, slots=True)
class LocalJavaToolchainPair:
    java_path: str
    java_sha256: str
    javac_path: str
    javac_sha256: str
    controller_path: str
    controller_sha256: str


@dataclass(frozen=True, slots=True)
class LocalJavaArtifact:
    image_identity: str
    repo_digests: tuple[str, ...] = ()
    os: str = ''
    architecture: str = ''
    variant: str = ''
    image_user: str = ''
    image_environment: tuple[str, ...] = ()
    image_size_bytes: int = 0
    image_declared_volumes: tuple[str, ...] = ()
    toolchains: tuple[LocalJavaToolchainPair, ...] = ()
    status: str = 'not_inspected'
    reason: str = ''
    cleanup_verified: bool = True


@dataclass(frozen=True, slots=True)
class LocalJavaDiscovery:
    artifacts: tuple[LocalJavaArtifact, ...]
    complete_inventory: bool
    cleanup_verified: bool
    reason: str
    backend_identity: str = ''
    backend_version: str = ''
    discovery_sources: tuple[str, ...] = (
        'fixed_local_docker_image_inventory',
        'immutable_local_image_metadata',
        'bounded_stopped_container_filesystem_export',
    )

    @property
    def available_toolchains(self):
        return tuple((artifact, pair) for artifact in self.artifacts
                     if artifact.status == 'local_java_toolchain_present'
                     for pair in artifact.toolchains)


class LocalJavaDiscoveryError(ValueError):
    pass


def _image_path(value):
    if type(value) is not str or '\\' in value or '\x00' in value:
        raise LocalJavaDiscoveryError('image_path_invalid')
    parts = PurePosixPath(value.lstrip('/')).parts
    if '..' in parts:
        raise LocalJavaDiscoveryError('image_path_invalid')
    return '/' + '/'.join(part for part in parts if part not in ('/', '.', ''))


def _link_target(path, target, *, hardlink=False):
    if target.startswith('/') or hardlink:
        return _image_path(target)
    parts = list(PurePosixPath(path).parent.parts)
    for part in PurePosixPath(target).parts:
        if part in ('', '.'):
            continue
        if part == '..':
            if len(parts) <= 1:
                raise LocalJavaDiscoveryError('image_link_escapes_root')
            parts.pop()
        else:
            parts.append(part)
    return _image_path('/'.join(parts))


def _resolve_link(path, links):
    seen = set()
    while True:
        parts = PurePosixPath(path).parts[1:]
        linked = next(((index, '/' + '/'.join(parts[:index]))
            for index in range(1, len(parts) + 1)
            if '/' + '/'.join(parts[:index]) in links), None)
        if linked is None:
            return path
        if path in seen or len(seen) >= 40:
            raise LocalJavaDiscoveryError('image_link_cycle')
        seen.add(path)
        index, prefix = linked
        path = _image_path(links[prefix] + '/' + '/'.join(parts[index:]))


def _linux_amd64_elf(header):
    return (len(header) >= 20 and header[:4] == b'\x7fELF'
        and header[4:6] == b'\x02\x01' and header[7] in (0, 3)
        and int.from_bytes(header[16:18], 'little') in (2, 3)
        and int.from_bytes(header[18:20], 'little') == 62)


def _nonroot_can_execute(member):
    return bool(member.mode & 0o001
        or member.uid == 65534 and member.mode & 0o100
        or member.gid == 65534 and member.mode & 0o010)


def _nonroot_can_traverse(path, directories):
    current = PurePosixPath(path).parent
    while str(current) != '/':
        # Docker export supplies directory metadata. Unlisted parents are
        # still measured by the exact nonroot image-specific launch verifier.
        if str(current) in directories and not directories[str(current)]:
            return False
        current = current.parent
    return directories.get('/', True)


def _read_executable(stream, size):
    if not 20 <= size <= MAX_EXECUTABLE_BYTES:
        return ''
    remaining, digest, header = size, sha256(), b''
    while remaining:
        block = stream.read(min(65536, remaining))
        if not block:
            raise LocalJavaDiscoveryError('image_executable_truncated')
        if not header:
            header = block[:64]
        digest.update(block)
        remaining -= len(block)
    return digest.hexdigest() if _linux_amd64_elf(header) else ''


class _BoundedArchiveStream:
    def __init__(self, stream):
        self.stream = stream
        self.size = 0

    def read(self, size=-1):
        # tarfile's stream mode reads fixed bounded blocks; never read all.
        if type(size) is not int or size < 0:
            raise LocalJavaDiscoveryError('archive_unbounded_read_denied')
        block = self.stream.read(min(size, MAX_ARCHIVE_BYTES - self.size + 1))
        self.size += len(block)
        if self.size > MAX_ARCHIVE_BYTES:
            raise LocalJavaDiscoveryError('image_archive_size_limit')
        return block


def _inspect_tar(stream):
    """Pure archive parsing; no file is extracted, opened or executed."""
    links, binaries, aliases, directories = {}, {}, set(), {}
    count = 0
    with tarfile.open(fileobj=stream, mode='r|') as archive:
        for member in archive:
            count += 1
            if count > MAX_ARCHIVE_ENTRIES:
                raise LocalJavaDiscoveryError('image_archive_entry_limit')
            path = _image_path(member.name)
            name = PurePosixPath(path).name
            wanted = name in ('java', 'javac') or bool(re.fullmatch(r'python3?(?:\.\d+)?', name))
            if member.isdir():
                directories[path] = _nonroot_can_execute(member)
            elif member.issym() or member.islnk():
                links[path] = _link_target(path, member.linkname, hardlink=member.islnk())
                if name in ('java', 'javac') or path == _CONTROLLER:
                    aliases.add(path)
            elif wanted and member.isfile() and _nonroot_can_execute(member):
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise LocalJavaDiscoveryError('image_executable_missing')
                with extracted:
                    digest = _read_executable(extracted, member.size)
                if digest:
                    binaries[path] = digest
                    if name in ('java', 'javac') or path == _CONTROLLER:
                        aliases.add(path)
    controller = _resolve_link(_CONTROLLER, links)
    controller_hash = (binaries.get(controller, '') if
        _nonroot_can_traverse(_CONTROLLER, directories)
        and _nonroot_can_traverse(controller, directories) else '')
    resolved = {}
    for path in sorted(aliases):
        if PurePosixPath(path).name not in ('java', 'javac'):
            continue
        actual = _resolve_link(path, links)
        if actual in binaries and _nonroot_can_traverse(actual, directories):
            resolved[(str(PurePosixPath(actual).parent), PurePosixPath(path).name)] = actual
    pairs = []
    for directory in sorted({key[0] for key in resolved}):
        java, javac = resolved.get((directory, 'java')), resolved.get((directory, 'javac'))
        if java and javac:
            pairs.append(LocalJavaToolchainPair(java, binaries[java], javac, binaries[javac],
                _CONTROLLER if controller_hash else '', controller_hash))
    return tuple(pairs)


def _export_filesystem(prefix, name):
    env = {key: os.environ[key] for key in ('SystemRoot', 'WINDIR') if key in os.environ}
    env['CATTUS_SANDBOX_HOST_ONLY'] = 'synthetic-host-only-secret'
    process = subprocess.Popen((*prefix, 'export', name), stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False, env=env,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    stopped, expired, overflow = Event(), Event(), Event()
    error_bytes = bytearray()
    deadline = monotonic() + EXPORT_TIMEOUT_MS / 1000

    def deadline_guard():
        while not stopped.wait(.02):
            if monotonic() >= deadline:
                expired.set()
                if process.poll() is None:
                    process.kill()
                return

    def stderr_reader():
        while True:
            data = process.stderr.read(256)
            if not data:
                return
            remaining = 8192 - len(error_bytes)
            error_bytes.extend(data[:remaining])
            if len(data) > remaining:
                overflow.set()
                if process.poll() is None:
                    process.kill()
                return

    guard = Thread(target=deadline_guard, daemon=True)
    reader = Thread(target=stderr_reader, daemon=True)
    guard.start()
    reader.start()
    try:
        stream = _BoundedArchiveStream(process.stdout)
        pairs = _inspect_tar(stream)
        # Consume only a bounded remainder so a producer cannot outlive parsing.
        # A normal Docker export finishes at the archive terminator.
        while stream.read(65536):
            pass
        if process.wait(timeout=2) != 0:
            raise LocalJavaDiscoveryError('image_export_failed')
        if expired.is_set():
            raise LocalJavaDiscoveryError('image_export_timeout')
        if overflow.is_set():
            raise LocalJavaDiscoveryError('image_export_stderr_limit')
        return pairs
    except (OSError, subprocess.SubprocessError, tarfile.TarError) as error:
        if expired.is_set():
            raise LocalJavaDiscoveryError('image_export_timeout') from error
        if overflow.is_set():
            raise LocalJavaDiscoveryError('image_export_stderr_limit') from error
        raise LocalJavaDiscoveryError('image_export_inspection_failed') from error
    finally:
        stopped.set()
        if process.poll() is None:
            process.kill()
        process.wait(timeout=2)
        guard.join(timeout=2); reader.join(timeout=2)
        process.stdout.close(); process.stderr.close()


def _stopped_configuration_safe(config, image_id):
    try:
        host, settings = config['HostConfig'], config['Config']
        return (config['Image'] == image_id and not config.get('Mounts')
            and host['Privileged'] is False and host['NetworkMode'] == 'none'
            and host.get('PidMode') in ('', None) and host['IpcMode'] == 'none'
            and host['CgroupnsMode'] == 'private' and host['ReadonlyRootfs'] is True
            and not host.get('Binds') and not host.get('Mounts')
            and host['CapDrop'] == ['ALL'] and not host.get('CapAdd')
            and host['LogConfig']['Type'] == 'none' and host['PidsLimit'] == 128
            and host['Memory'] == 134217728 and host['NanoCpus'] == 1000000000
            and settings['User'] == '65534:65534' and settings['WorkingDir'] == '/work'
            and settings['Entrypoint'] == [_CONTROLLER]
            and settings['Cmd'] == ['-I', '-S', '-B', '-c', 'raise SystemExit(64)']
            and host['Tmpfs'] == {'/work': 'rw,nosuid,nodev,size=32m,mode=1777',
                '/tmp': 'rw,nosuid,nodev,noexec,size=16m,mode=1777'}
            and set(host['SecurityOpt']) == {'no-new-privileges=true',
                'seccomp=' + sandbox._json(sandbox._SECCOMP)}
            and config['State']['Running'] is False)
    except (KeyError, TypeError, AttributeError):
        return False


def _container_files(prefix, image_id, profile):
    name = 'runtime-java1-discovery-' + secrets.token_hex(12)
    ctl = lambda *args: sandbox._bounded_process((*prefix, *args),
        timeout_ms=8000, stdout_limit=65536)
    pairs, status, cleanup = (), 'image_export_inspection_failed', False
    try:
        created = ctl('create', '--name', name, '--pull', 'never',
            '--hostname', 'runtime-sandbox1', '--network', 'none', '--read-only',
            '--user', '65534:65534', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges=true', '--security-opt', 'seccomp=' + str(profile),
            '--cgroupns', 'private', '--ipc', 'none', '--pids-limit', '128',
            '--memory', '128m', '--cpus', '1', '--log-driver', 'none',
            '--tmpfs', '/work:rw,nosuid,nodev,size=32m,mode=1777',
            '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=16m,mode=1777',
            '--workdir', '/work', '--entrypoint', _CONTROLLER, image_id,
            '-I', '-S', '-B', '-c', 'raise SystemExit(64)')
        if created.status != 'sandbox_completed' or created.exit_code != 0:
            raise LocalJavaDiscoveryError('image_inspection_container_create_failed')
        inspected = ctl('inspect', name, '--format', '{{json .}}')
        if inspected.status != 'sandbox_completed' or inspected.exit_code != 0:
            raise LocalJavaDiscoveryError('image_inspection_container_inspect_failed')
        if not _stopped_configuration_safe(json.loads(inspected.stdout), image_id):
            raise LocalJavaDiscoveryError('image_inspection_container_configuration_ineligible')
        pairs = _export_filesystem(prefix, name)
        status = 'image_files_inspected'
    except (LocalJavaDiscoveryError, OSError, ValueError, subprocess.SubprocessError) as error:
        status = str(error) if isinstance(error, LocalJavaDiscoveryError) else 'image_inspection_failed'
    finally:
        removed = ctl('rm', '--force', '--volumes', name)
        absent = ctl('inspect', name, '--format', '{{.State.Running}}')
        known_absent = (absent.status == 'sandbox_completed' and absent.exit_code != 0
            and any(message in absent.stderr.lower() for message in
                (b'no such object', b'no such container')))
        removal_completed = (removed.status == 'sandbox_completed'
            and (removed.exit_code == 0 or any(message in removed.stderr.lower() for message in
                (b'no such object', b'no such container'))))
        cleanup = known_absent and removal_completed
    return pairs, status, cleanup


def _image_metadata(image_id, value):
    if (type(value) is not dict or value.get('Id') != image_id
            or not _IDENTITY.fullmatch(image_id)):
        raise LocalJavaDiscoveryError('local_image_identity_invalid')
    config = value.get('Config') or {}
    if type(config) is not dict:
        raise LocalJavaDiscoveryError('local_image_metadata_invalid')
    environment, digests, volumes = config.get('Env') or [], value.get('RepoDigests') or [], config.get('Volumes') or {}
    size = value.get('Size')
    if (type(environment) is not list
            or any(type(item) is not str or '=' not in item for item in environment)
            or type(digests) is not list or any(type(item) is not str for item in digests)
            or type(volumes) is not dict or any(type(item) is not str for item in volumes)
            or type(size) is not int or size < 0):
        raise LocalJavaDiscoveryError('local_image_metadata_invalid')
    return LocalJavaArtifact(image_id, tuple(sorted(digests)), str(value.get('Os', '')),
        str(value.get('Architecture', '')), str(value.get('Variant', '')),
        str(config.get('User') or ''), tuple(environment), size, tuple(sorted(volumes)))


def discover_local_java_artifacts(*, timings=None):
    """Recheck present local image IDs; never use tags, remote hosts or Java."""
    tick = perf_counter()
    artifacts, complete, cleanup, identity, version = [], False, True, '', ''
    reason = 'local_docker_backend_unavailable'
    try:
        prefix = sandbox._docker_prefix()
        if not prefix:
            return LocalJavaDiscovery((), False, True, reason)
        ctl = lambda *args: sandbox._bounded_process((*prefix, *args),
            timeout_ms=8000, stdout_limit=65536)
        observed = ctl('version', '--format', '{{json .}}')
        if observed.status != 'sandbox_completed' or observed.exit_code != 0:
            return LocalJavaDiscovery((), False, True, reason)
        server = json.loads(observed.stdout).get('Server') or {}
        if type(server) is not dict or server.get('Os') != 'linux' or not server.get('Version'):
            return LocalJavaDiscovery((), False, True, 'local_docker_backend_platform_ineligible')
        identity, version = 'local-docker:' + sandbox._local_endpoint(), str(server['Version'])
        inventory = ctl('image', 'ls', '--all', '--no-trunc', '--quiet')
        if inventory.status != 'sandbox_completed' or inventory.exit_code != 0:
            return LocalJavaDiscovery((), False, True, 'local_image_inventory_unavailable', identity, version)
        image_ids = sorted(set(inventory.stdout.decode('ascii').splitlines()))
        if any(not _IDENTITY.fullmatch(image_id) for image_id in image_ids):
            return LocalJavaDiscovery((), False, True, 'local_image_inventory_invalid', identity, version)
        if not image_ids:
            return LocalJavaDiscovery((), True, True, 'no_eligible_exact_local_java_toolchain', identity, version)
        complete = True
        with tempfile.TemporaryDirectory(prefix='runtime-java1-discovery-') as directory:
            profile = Path(directory) / 'seccomp.json'
            profile.write_text(sandbox._json(sandbox._SECCOMP), encoding='utf-8')
            for image_id in image_ids:
                try:
                    inspected = ctl('image', 'inspect', image_id, '--format', '{{json .}}')
                    if inspected.status != 'sandbox_completed' or inspected.exit_code != 0:
                        raise LocalJavaDiscoveryError('local_image_metadata_unavailable')
                    artifact = _image_metadata(image_id, json.loads(inspected.stdout))
                    if artifact.os != 'linux' or artifact.architecture != 'amd64':
                        artifact = replace(artifact, status='local_image_platform_ineligible',
                            reason='requires_linux_amd64')
                    elif artifact.image_declared_volumes:
                        artifact = replace(artifact, status='local_image_mounts_ineligible',
                            reason='image_declared_volumes_violate_frozen_no_mount_contract')
                    else:
                        pairs, status, removed = _container_files(prefix, image_id, profile)
                        cleanup &= removed
                        if status != 'image_files_inspected' or not removed:
                            complete = False
                            artifact = replace(artifact, status=status,
                                reason=status if removed else 'discovery_container_cleanup_failed',
                                cleanup_verified=removed)
                        else:
                            supported = tuple(pair for pair in pairs if pair.controller_path)
                            artifact = replace(artifact, toolchains=pairs,
                                status='local_java_toolchain_present' if supported else
                                    'local_java_controller_unavailable' if pairs else 'local_java_toolchain_absent',
                                reason='exact_local_elf_toolchain_and_controller_present' if supported else
                                    'frozen_python_projection_controller_missing' if pairs else
                                    'no_executable_linux_amd64_java_javac_pair')
                    artifacts.append(artifact)
                    if not cleanup:
                        break
                except (LocalJavaDiscoveryError, OSError, ValueError, subprocess.SubprocessError) as error:
                    complete = False
                    artifacts.append(LocalJavaArtifact(image_id, status='local_image_inspection_failed',
                        reason=str(error) if isinstance(error, LocalJavaDiscoveryError) else type(error).__name__))
        cleanup &= not Path(directory).exists()
        reason = ('local_java_discovery_cleanup_failed' if not cleanup else
            'local_image_inventory_inspection_incomplete' if not complete else
            'eligible_exact_local_java_toolchain_present' if any(
                artifact.status == 'local_java_toolchain_present' for artifact in artifacts) else
            'no_eligible_exact_local_java_toolchain')
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        complete = False
        reason = 'local_java_artifact_detection_failed:' + type(error).__name__
    finally:
        if timings is not None:
            timings['artifact_discovery_seconds'] = perf_counter() - tick
    return LocalJavaDiscovery(tuple(artifacts), complete, cleanup, reason, identity, version)
