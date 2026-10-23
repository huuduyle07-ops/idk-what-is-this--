"""Pure bounded archive evidence for the single PINNED.1A target.

The frozen discovery owner remains the authority for path, link, ELF and access
semantics. This wrapper adds complete-stream validation and detailed immutable
measurements. It never extracts, persists or executes archive contents.
"""
from dataclasses import dataclass
from pathlib import PurePosixPath
import tarfile

from core import runtime_java_pinned_requirement as requirement
from core import sandboxed_java_toolchain_discovery as frozen


REQUIREMENT = requirement.REQUIREMENT
INCOMPLETE = "PINNED_PROVIDER_INSPECTION_INCOMPLETE"
TOOLCHAIN_MISMATCH = "PINNED_TOOLCHAIN_MISMATCH"
CONTROLLER_MISMATCH = "PINNED_CONTROLLER_MISMATCH"
# A separate bounded parser-header read policy, not an increase to any frozen
# archive, executable, entry, link or export budget. Tarfile otherwise reads an
# entire GNU/PAX extension into memory even in stream mode.
MAX_METADATA_BYTES = 65536


class ArchiveInspectionError(ValueError):
    def __init__(self, code, reason):
        super().__init__(reason)
        self.code = code
        self.reason = reason


@dataclass(frozen=True, slots=True)
class LinkResolutionHop:
    link_path: str
    target_path: str
    link_kind: str


@dataclass(frozen=True, slots=True)
class ExecutableMeasurement:
    normalized_path: str
    resolved_path: str
    sha256: str
    size_bytes: int
    elf_class: int
    elf_endianness: int
    elf_osabi: int
    elf_type: int
    elf_machine: int
    linux_amd64_elf: bool
    mode: int
    uid: int
    gid: int
    nonroot_executable: bool
    ancestor_traversal_allowed: bool
    ancestor_metadata_complete: bool
    ancestor_traversal_paths: tuple[tuple[str, bool | None], ...]
    link_chain: tuple[LinkResolutionHop, ...]
    link_resolution_result: str


@dataclass(frozen=True, slots=True)
class ArchiveInspectionResult:
    archive_bytes: int
    archive_entries: int
    java: ExecutableMeasurement
    javac: ExecutableMeasurement
    controller: ExecutableMeasurement
    toolchain_pair_result: str
    stream_complete: bool = True
    all_paths_validated: bool = True
    all_links_validated: bool = True


class _ArchiveStream:
    """Count all raw bytes and inspect 512-byte records without retaining tar."""
    def __init__(self, stream):
        self.stream = stream
        self.size = 0
        self.partial = b""
        self.last_nonzero_block_end = 0

    def read(self, size=-1):
        if type(size) is not int or size < 0:
            raise ArchiveInspectionError(INCOMPLETE, "archive_unbounded_read_denied")
        limit = REQUIREMENT.inspection_bounds.max_archive_bytes
        block = self.stream.read(min(size, limit - self.size + 1))
        if not isinstance(block, bytes):
            raise ArchiveInspectionError(INCOMPLETE, "archive_nonbytes_stream")
        self.size += len(block)
        if self.size > limit:
            raise ArchiveInspectionError(INCOMPLETE, "image_archive_size_limit")
        data = self.partial + block
        complete_bytes = len(data) // tarfile.BLOCKSIZE * tarfile.BLOCKSIZE
        position = self.size - len(data)
        for index in range(0, complete_bytes, tarfile.BLOCKSIZE):
            if any(data[index:index + tarfile.BLOCKSIZE]):
                self.last_nonzero_block_end = position + index + tarfile.BLOCKSIZE
        self.partial = data[complete_bytes:]
        return block


class _ExecutableStream:
    """Observe only the header and byte count around the frozen hash primitive."""
    def __init__(self, stream, prefix=b""):
        self.stream = stream
        self.prefix = prefix
        self.header = b""
        self.size = 0

    def read(self, size):
        data = self.prefix[:size]
        self.prefix = self.prefix[len(data):]
        if len(data) < size:
            data += self.stream.read(size - len(data))
        self.header += data[:max(0, 64 - len(self.header))]
        self.size += len(data)
        return data


class _BoundedTarInfo(tarfile.TarInfo):
    """Bound parser-internal metadata reads before TarInfo processes them."""
    @staticmethod
    def _check_pax_metadata(metadata):
        total = 0
        for key, value in metadata.items():
            total += len(key.encode("utf-8", "surrogateescape"))
            total += len(value.encode("utf-8", "surrogateescape"))
            if total > MAX_METADATA_BYTES:
                raise ArchiveInspectionError(INCOMPLETE, "archive_effective_metadata_size_limit")

    def _proc_member(self, archive):
        self._check_pax_metadata(archive.pax_headers)
        archive._pinned_header_count = getattr(archive, "_pinned_header_count", 0) + 1
        if archive._pinned_header_count > REQUIREMENT.inspection_bounds.max_archive_entries:
            raise ArchiveInspectionError(INCOMPLETE, "image_archive_entry_limit")
        if self.type in (tarfile.XHDTYPE, tarfile.XGLTYPE,
                tarfile.GNUTYPE_LONGNAME, tarfile.GNUTYPE_LONGLINK):
            if not 0 <= self.size <= MAX_METADATA_BYTES:
                raise ArchiveInspectionError(INCOMPLETE, "archive_metadata_header_size_limit")
        if self.type == tarfile.GNUTYPE_SPARSE:
            raise ArchiveInspectionError(INCOMPLETE, "archive_sparse_metadata_unsupported")
        return super()._proc_member(archive)

    def _proc_pax(self, archive):
        member = super()._proc_pax(archive)
        self._check_pax_metadata(archive.pax_headers)
        self._check_pax_metadata(member.pax_headers)
        return member

    def _proc_gnusparse_00(self, *args, **kwargs):
        raise ArchiveInspectionError(INCOMPLETE, "archive_sparse_metadata_unsupported")

    def _proc_gnusparse_01(self, *args, **kwargs):
        raise ArchiveInspectionError(INCOMPLETE, "archive_sparse_metadata_unsupported")

    def _proc_gnusparse_10(self, *args, **kwargs):
        raise ArchiveInspectionError(INCOMPLETE, "archive_sparse_metadata_unsupported")


class _TracingLinks(dict):
    def __init__(self, links, kinds):
        super().__init__(links)
        self.kinds = kinds
        self.chain = []

    def __getitem__(self, path):
        target = super().__getitem__(path)
        self.chain.append(LinkResolutionHop(path, target, self.kinds[path]))
        return target


@dataclass(frozen=True, slots=True)
class _File:
    size: int
    mode: int
    uid: int
    gid: int
    executable: bool
    sha256: str
    header: bytes


def _ancestors(path):
    result = []
    parent = PurePosixPath(path).parent
    while True:
        result.append(str(parent))
        if str(parent) == "/":
            return result
        parent = parent.parent


def _measure(path, expected_hash, code, links, kinds, files, directories):
    trace = _TracingLinks(links, kinds)
    resolved = frozen._resolve_link(path, trace)
    entry = files.get(resolved)
    if entry is None:
        raise ArchiveInspectionError(code, "exact_executable_missing")
    if entry.size > REQUIREMENT.inspection_bounds.max_executable_bytes:
        raise ArchiveInspectionError(INCOMPLETE, "image_executable_size_limit")
    if not entry.executable:
        raise ArchiveInspectionError(code, "exact_executable_nonroot_permission_denied")
    if not entry.sha256 or not frozen._linux_amd64_elf(entry.header):
        raise ArchiveInspectionError(code, "exact_executable_linux_amd64_elf_required")
    if expected_hash is not None and entry.sha256 != expected_hash:
        raise ArchiveInspectionError(code, "exact_executable_sha256_mismatch")
    traversed_paths = (path, resolved, *(hop.link_path for hop in trace.chain),
                       *(hop.target_path for hop in trace.chain))
    traversal = all(frozen._nonroot_can_traverse(p, directories) for p in traversed_paths)
    if not traversal:
        raise ArchiveInspectionError(code, "exact_executable_ancestor_traversal_denied")
    ancestors = sorted({p for item in traversed_paths for p in _ancestors(item)})
    facts = tuple((p, directories.get(p)) for p in ancestors)
    header = entry.header
    return ExecutableMeasurement(path, resolved, entry.sha256, entry.size,
        header[4], header[5], header[7], int.from_bytes(header[16:18], "little"),
        int.from_bytes(header[18:20], "little"), True, entry.mode, entry.uid,
        entry.gid, True, True, all(value is not None for _, value in facts),
        facts, tuple(trace.chain), "resolved_within_image_root")


def inspect_archive(stream):
    """Inspect the complete stream for only the immutable requirement's paths.

    Unknown ancestor metadata is recorded explicitly, following the frozen
    primitive; it requires later runtime confirmation and proves no runtime fact.
    A tar EOF without two zero records, trailing nonzero data, truncated members,
    any invalid path/link or any resource overflow blocks the entire result.
    """
    wrapped = _ArchiveStream(stream)
    seen, links, kinds, files, directories = set(), {}, {}, {}, {}
    count = 0
    try:
        with tarfile.open(fileobj=wrapped, mode="r|", stream=True,
                tarinfo=_BoundedTarInfo) as archive:
            for member in archive:
                count += 1
                if count > REQUIREMENT.inspection_bounds.max_archive_entries:
                    raise ArchiveInspectionError(INCOMPLETE, "image_archive_entry_limit")
                path = frozen._image_path(member.name)
                if path in seen:
                    raise ArchiveInspectionError(INCOMPLETE, "duplicate_normalized_archive_path")
                seen.add(path)
                if member.isdir():
                    directories[path] = frozen._nonroot_can_execute(member)
                elif member.issym() or member.islnk():
                    links[path] = frozen._link_target(path, member.linkname,
                        hardlink=member.islnk())
                    kinds[path] = "hardlink" if member.islnk() else "symlink"
                elif member.isfile():
                    executable = frozen._nonroot_can_execute(member)
                    digest, header = "", b""
                    if executable and 20 <= member.size <= min(
                            REQUIREMENT.inspection_bounds.max_executable_bytes,
                            frozen.MAX_EXECUTABLE_BYTES):
                        content = archive.extractfile(member)
                        if content is None:
                            raise ArchiveInspectionError(INCOMPLETE, "image_executable_missing")
                        with content:
                            header = content.read(min(64, member.size))
                            if frozen._linux_amd64_elf(header):
                                observed = _ExecutableStream(content, header)
                                digest = frozen._read_executable(observed, member.size)
                                if observed.size != member.size:
                                    raise ArchiveInspectionError(INCOMPLETE, "image_executable_truncated")
                                header = observed.header
                    files[path] = _File(member.size, member.mode, member.uid,
                        member.gid, executable, digest, header)
            member_end = archive.offset
            header_count = getattr(archive, "_pinned_header_count", 0)
        # Tarfile stream mode can stop at a zero header with buffered bytes left;
        # draining the underlying stream accounts for every byte, including tail.
        while wrapped.read(65536):
            pass
        if (wrapped.partial or wrapped.size < member_end + 2 * tarfile.BLOCKSIZE
                or wrapped.last_nonzero_block_end > member_end):
            raise ArchiveInspectionError(INCOMPLETE, "archive_termination_or_trailing_data_invalid")
        # Validate every link, even unrelated ones, through the frozen resolver.
        for path in seen:
            frozen._resolve_link(path, links)
        # A regular archive member beneath a directory symlink would describe
        # the same resolved filesystem record as its physical destination.
        # Preserve ambiguity instead of choosing either tar member's bytes.
        resolved_files = set()
        for path in files:
            resolved = frozen._resolve_link(path, links)
            if resolved in resolved_files:
                raise ArchiveInspectionError(INCOMPLETE, "ambiguous_resolved_archive_file")
            resolved_files.add(resolved)
        java = _measure(REQUIREMENT.java.path, REQUIREMENT.java.sha256,
            TOOLCHAIN_MISMATCH, links, kinds, files, directories)
        javac = _measure(REQUIREMENT.javac.path, REQUIREMENT.javac.sha256,
            TOOLCHAIN_MISMATCH, links, kinds, files, directories)
        if PurePosixPath(java.resolved_path).parent != PurePosixPath(javac.resolved_path).parent:
            raise ArchiveInspectionError(TOOLCHAIN_MISMATCH, "exact_toolchain_same_directory_pair_required")
        if java.resolved_path == javac.resolved_path:
            raise ArchiveInspectionError(TOOLCHAIN_MISMATCH, "ambiguous_exact_toolchain_pair")
        controller = _measure(REQUIREMENT.controller.path, None,
            CONTROLLER_MISMATCH, links, kinds, files, directories)
        return ArchiveInspectionResult(wrapped.size, header_count, java, javac,
            controller, "exact_single_same_directory_pair")
    except ArchiveInspectionError:
        raise
    except (frozen.LocalJavaDiscoveryError, tarfile.TarError, OSError,
            ValueError, TypeError, AttributeError, EOFError, RecursionError) as error:
        raise ArchiveInspectionError(INCOMPLETE,
            str(error) if isinstance(error, frozen.LocalJavaDiscoveryError)
            else "archive_inspection_failed:" + type(error).__name__) from error
