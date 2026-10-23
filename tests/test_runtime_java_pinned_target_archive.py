"""Synthetic streamed tar fixtures only; no Docker, Java or filesystem export."""
from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
import io
import tarfile

import pytest

from core import runtime_java_pinned_target_archive as owner


JAVA_PATH = owner.REQUIREMENT.java.path
JAVAC_PATH = owner.REQUIREMENT.javac.path
CONTROLLER_PATH = owner.REQUIREMENT.controller.path


def _elf(marker=0, *, machine=62, bits=2, endian=1, osabi=0, kind=3):
    data = bytearray(64)
    data[:4] = b"\x7fELF"
    data[4:6] = bytes((bits, endian))
    data[7] = osabi
    data[16:18] = kind.to_bytes(2, "little")
    data[18:20] = machine.to_bytes(2, "little")
    data[32] = marker
    return bytes(data)


JAVA_BYTES, JAVAC_BYTES, CONTROLLER_BYTES = _elf(1), _elf(2), _elf(3)


@pytest.fixture(autouse=True)
def _synthetic_pins(monkeypatch):
    # The production API accepts no target or pins. Pure tests replace metadata
    # in this module only; the immutable requirement owner remains untouched.
    value = replace(owner.REQUIREMENT,
        java=replace(owner.REQUIREMENT.java, sha256=sha256(JAVA_BYTES).hexdigest()),
        javac=replace(owner.REQUIREMENT.javac, sha256=sha256(JAVAC_BYTES).hexdigest()))
    monkeypatch.setattr(owner, "REQUIREMENT", value)


def _entries(*, controller=True):
    result = [(JAVA_PATH, JAVA_BYTES), (JAVAC_PATH, JAVAC_BYTES)]
    if controller:
        result.append((CONTROLLER_PATH, CONTROLLER_BYTES))
    return result


def _tar(entries):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for item in entries:
            name, data, *extra = item
            metadata = extra[0] if extra else {}
            member = tarfile.TarInfo(name.lstrip("/") if name != "/" else ".")
            member.mode = metadata.get("mode", 0o755)
            member.uid, member.gid = metadata.get("uid", 0), metadata.get("gid", 0)
            kind = metadata.get("kind", "file")
            if kind in ("symlink", "hardlink"):
                member.type = tarfile.SYMTYPE if kind == "symlink" else tarfile.LNKTYPE
                member.linkname = data
                archive.addfile(member)
            elif kind == "directory":
                member.type = tarfile.DIRTYPE
                archive.addfile(member)
            else:
                member.size = metadata.get("size", len(data))
                archive.addfile(member, io.BytesIO(data))
    return output.getvalue()


def _inspect(entries):
    return owner.inspect_archive(io.BytesIO(_tar(entries)))


def _fails(entries, code, reason=None):
    with pytest.raises(owner.ArchiveInspectionError) as caught:
        _inspect(entries)
    assert caught.value.code == code
    if reason:
        assert reason in caught.value.reason
    return caught.value


def test_complete_exact_measurements_and_immutable_result():
    result = _inspect(_entries())
    assert result.archive_bytes == len(_tar(_entries()))
    assert result.archive_entries == 3
    assert result.stream_complete and result.all_paths_validated and result.all_links_validated
    assert result.toolchain_pair_result == "exact_single_same_directory_pair"
    for measured, path, content in ((result.java, JAVA_PATH, JAVA_BYTES),
            (result.javac, JAVAC_PATH, JAVAC_BYTES),
            (result.controller, CONTROLLER_PATH, CONTROLLER_BYTES)):
        assert measured.normalized_path == measured.resolved_path == path
        assert measured.sha256 == sha256(content).hexdigest()
        assert measured.size_bytes == len(content)
        assert (measured.elf_class, measured.elf_endianness, measured.elf_osabi,
            measured.elf_type, measured.elf_machine) == (2, 1, 0, 3, 62)
        assert measured.linux_amd64_elf and measured.nonroot_executable
        assert measured.ancestor_traversal_allowed
        assert measured.ancestor_metadata_complete is False
        assert all(value is None for _, value in measured.ancestor_traversal_paths)
        assert measured.link_chain == ()
    with pytest.raises(FrozenInstanceError):
        result.controller.sha256 = "0" * 64


def test_known_directory_metadata_completeness_and_nonroot_ownership():
    parents = ("/", "/opt", "/opt/temurin-26.0.2.1", "/opt/temurin-26.0.2.1/bin",
        "/usr", "/usr/local", "/usr/local/bin")
    entries = [(p, b"", {"kind": "directory", "mode": 0o755}) for p in parents]
    entries += [(JAVA_PATH, JAVA_BYTES, {"mode": 0o700, "uid": 65534}),
        (JAVAC_PATH, JAVAC_BYTES, {"mode": 0o710, "gid": 65534}),
        (CONTROLLER_PATH, CONTROLLER_BYTES)]
    result = _inspect(entries)
    assert result.java.ancestor_metadata_complete
    assert result.controller.ancestor_metadata_complete
    assert all(value is True for _, value in result.javac.ancestor_traversal_paths)
    assert result.java.uid == result.javac.gid == 65534


def test_relative_symlink_and_hardlink_chain_measured_without_extraction():
    entries = [("/actual/bin/java", JAVA_BYTES), ("/actual/bin/javac", JAVAC_BYTES),
        ("/actual/python-real", CONTROLLER_BYTES),
        (JAVA_PATH, "/actual/bin/java", {"kind": "symlink"}),
        (JAVAC_PATH, "actual/bin/javac", {"kind": "hardlink"}),
        ("/usr/local/bin/python3", "/actual/python-real", {"kind": "symlink"}),
        (CONTROLLER_PATH, "python3", {"kind": "symlink"})]
    result = _inspect(entries)
    assert result.java.resolved_path == "/actual/bin/java"
    assert result.javac.link_chain[0].link_kind == "hardlink"
    assert [(hop.link_path, hop.target_path) for hop in result.controller.link_chain] == [
        (CONTROLLER_PATH, "/usr/local/bin/python3"),
        ("/usr/local/bin/python3", "/actual/python-real")]


def test_directory_symlink_resolution_uses_frozen_prefix_semantics():
    entries = [("/actual/bin/java", JAVA_BYTES), ("/actual/bin/javac", JAVAC_BYTES),
        ("/opt/temurin-26.0.2.1", "/actual", {"kind": "symlink"}),
        (CONTROLLER_PATH, CONTROLLER_BYTES)]
    result = _inspect(entries)
    assert result.java.resolved_path == "/actual/bin/java"
    assert result.java.link_chain[0].link_path == "/opt/temurin-26.0.2.1"


@pytest.mark.parametrize("path", ("../host", "opt/../host", "bad\\path", "bad\x00path"))
def test_any_archive_path_traversal_is_incomplete(path):
    # NUL in a tar header is a terminator, so exercise the same frozen primitive
    # through a fabricated TarInfo emitted by the parser for this special case.
    if "\x00" in path:
        with pytest.raises(owner.frozen.LocalJavaDiscoveryError):
            owner.frozen._image_path(path)
    else:
        _fails(_entries() + [(path, b"unrelated")], owner.INCOMPLETE)


@pytest.mark.parametrize("kind,target", (("symlink", "../../escape"),
    ("hardlink", "../escape"), ("symlink", "/../escape"),
    ("symlink", "bad\\target")))
def test_unrelated_link_root_escape_blocks(kind, target):
    _fails(_entries() + [("/unrelated", target, {"kind": kind})], owner.INCOMPLETE)


def test_unrelated_link_cycle_blocks_complete_archive():
    _fails(_entries() + [("/a", "/b", {"kind": "symlink"}),
        ("/b", "/a", {"kind": "hardlink"})], owner.INCOMPLETE, "image_link_cycle")


def test_more_than_forty_hops_blocks_and_forty_is_allowed():
    for hops in (40, 41):
        entries = _entries() + [(f"/link-{i}", f"/link-{i + 1}", {"kind": "symlink"})
            for i in range(hops)]
        entries.append((f"/link-{hops}", b"unrelated"))
        if hops == 40:
            assert _inspect(entries).all_links_validated
        else:
            _fails(entries, owner.INCOMPLETE, "image_link_cycle")


@pytest.mark.parametrize("extra", ((JAVA_PATH, JAVA_BYTES),
    ("opt//temurin-26.0.2.1/bin/./java", JAVA_BYTES),
    ("/unrelated", b"a")))
def test_duplicate_normalized_archive_paths_are_never_ranked(extra):
    entries = _entries()
    if extra[0] == "/unrelated":
        entries.append(("/unrelated", b"b"))
    _fails(entries + [extra], owner.INCOMPLETE, "duplicate_normalized_archive_path")


@pytest.mark.parametrize("invalid", (b"MZ" + b"\x00" * 62,
    _elf(machine=183), _elf(bits=1), _elf(endian=2), _elf(osabi=9),
    _elf(kind=1), b"#!/bin/sh\njava\n", b"tiny"))
def test_wrong_java_elf_cannot_become_provider_identity(invalid):
    entries = _entries()
    entries[0] = (JAVA_PATH, invalid)
    _fails(entries, owner.TOOLCHAIN_MISMATCH)


@pytest.mark.parametrize("which", (0, 1))
def test_complete_byte_hash_equality_for_each_required_tool(which):
    entries = _entries()
    path, data = entries[which]
    entries[which] = (path, data + b"changed complete bytes")
    _fails(entries, owner.TOOLCHAIN_MISMATCH, "sha256_mismatch")


@pytest.mark.parametrize("path", (JAVA_PATH, JAVAC_PATH, CONTROLLER_PATH))
def test_root_only_execution_is_not_nonroot_eligibility(path):
    entries = [(p, data, {"mode": 0o700} if p == path else {}) for p, data in _entries()]
    _fails(entries, owner.CONTROLLER_MISMATCH if path == CONTROLLER_PATH
        else owner.TOOLCHAIN_MISMATCH, "nonroot_permission_denied")


def test_known_parent_and_intermediate_link_parent_access_are_checked():
    _fails(_entries() + [("/usr/local", b"", {"kind": "directory", "mode": 0o700})],
        owner.CONTROLLER_MISMATCH, "ancestor_traversal_denied")
    entries = _entries(controller=False) + [("/actual-python", CONTROLLER_BYTES),
        (CONTROLLER_PATH, "/restricted/link", {"kind": "symlink"}),
        ("/restricted/link", "/actual-python", {"kind": "symlink"}),
        ("/restricted", b"", {"kind": "directory", "mode": 0o700})]
    _fails(entries, owner.CONTROLLER_MISMATCH, "ancestor_traversal_denied")


def test_exact_pair_requires_same_resolved_directory():
    entries = [(JAVA_PATH, JAVA_BYTES), ("/other/javac", JAVAC_BYTES),
        (JAVAC_PATH, "/other/javac", {"kind": "symlink"}),
        (CONTROLLER_PATH, CONTROLLER_BYTES)]
    _fails(entries, owner.TOOLCHAIN_MISMATCH, "same_directory_pair_required")


def test_distinct_exact_paths_cannot_alias_one_executable_pair(monkeypatch):
    monkeypatch.setattr(owner, "REQUIREMENT", replace(owner.REQUIREMENT,
        javac=replace(owner.REQUIREMENT.javac, sha256=sha256(JAVA_BYTES).hexdigest())))
    entries = [(JAVA_PATH, JAVA_BYTES), (JAVAC_PATH, JAVA_PATH, {"kind": "symlink"}),
        (CONTROLLER_PATH, CONTROLLER_BYTES)]
    _fails(entries, owner.TOOLCHAIN_MISMATCH, "ambiguous_exact_toolchain_pair")


def test_shadowed_members_beneath_directory_link_cannot_choose_pair_bytes():
    entries = _entries() + [("/actual/bin/java", JAVA_BYTES),
        ("/actual/bin/javac", JAVAC_BYTES),
        ("/opt/temurin-26.0.2.1", "/actual", {"kind": "symlink"})]
    _fails(entries, owner.INCOMPLETE, "ambiguous_resolved_archive_file")


def test_unrelated_valid_toolchain_is_not_selected_or_ranked():
    entries = _entries() + [("/other/bin/java", _elf(6)), ("/other/bin/javac", _elf(7))]
    result = _inspect(entries)
    assert result.java.normalized_path == JAVA_PATH
    _fails(entries[1:], owner.TOOLCHAIN_MISMATCH, "exact_executable_missing")


def test_controller_hash_is_current_measurement_without_requirement_pin():
    entries = _entries()
    entries[-1] = (CONTROLLER_PATH, _elf(8))
    result = _inspect(entries)
    assert result.controller.sha256 == sha256(_elf(8)).hexdigest()
    assert owner.REQUIREMENT.controller.pinned_sha256 is None
    assert not hasattr(result, "runtime_controller_same_executable_proven")


def test_controller_missing_invalid_elf_and_dangling_link_block():
    _fails(_entries(controller=False), owner.CONTROLLER_MISMATCH, "missing")
    _fails(_entries(controller=False) + [(CONTROLLER_PATH, b"MZ" + b"0" * 62)],
        owner.CONTROLLER_MISMATCH, "elf_required")
    _fails(_entries(controller=False) + [(CONTROLLER_PATH, "/missing", {"kind": "symlink"})],
        owner.CONTROLLER_MISMATCH, "missing")


def _bound(monkeypatch, **changes):
    monkeypatch.setattr(owner, "REQUIREMENT", replace(owner.REQUIREMENT,
        inspection_bounds=replace(owner.REQUIREMENT.inspection_bounds, **changes)))


def test_archive_byte_bound_counts_tail_and_drains_without_retention(monkeypatch):
    raw = _tar(_entries())
    _bound(monkeypatch, max_archive_bytes=len(raw))
    assert owner.inspect_archive(io.BytesIO(raw)).archive_bytes == len(raw)
    with pytest.raises(owner.ArchiveInspectionError) as caught:
        owner.inspect_archive(io.BytesIO(raw + b"\x00" * 512))
    assert caught.value.code == owner.INCOMPLETE
    assert caught.value.reason == "image_archive_size_limit"


def test_archive_entry_bound_includes_unrelated_paths(monkeypatch):
    _bound(monkeypatch, max_archive_entries=3)
    _fails(_entries() + [("/unrelated", b"")], owner.INCOMPLETE, "entry_limit")


@pytest.mark.parametrize("path", (JAVA_PATH, JAVAC_PATH, CONTROLLER_PATH))
def test_exact_executable_bound_is_fail_closed(monkeypatch, path):
    _bound(monkeypatch, max_executable_bytes=64)
    entries = [(p, data + b"x" if p == path else data) for p, data in _entries()]
    _fails(entries, owner.INCOMPLETE, "executable_size_limit")


@pytest.mark.parametrize("cut", (512 + 10, 3 * 1024, 3 * 1024 + 512, 10239))
def test_truncated_member_or_tar_terminator_is_incomplete(cut):
    raw = _tar(_entries())
    with pytest.raises(owner.ArchiveInspectionError) as caught:
        owner.inspect_archive(io.BytesIO(raw[:cut]))
    assert caught.value.code == owner.INCOMPLETE


def test_trailing_nonzero_data_and_nonrecord_tail_are_incomplete():
    for suffix in (b"extra content" + b"\x00" * 1024, b"x" * 512, b"\x00"):
        with pytest.raises(owner.ArchiveInspectionError) as caught:
            owner.inspect_archive(io.BytesIO(_tar(_entries()) + suffix))
        assert caught.value.code == owner.INCOMPLETE


def test_unrelated_truncated_file_is_not_partial_positive_evidence():
    raw = _tar(_entries() + [("/unrelated", b"x" * 5000, {"mode": 0o644})])
    with pytest.raises(owner.ArchiveInspectionError) as caught:
        owner.inspect_archive(io.BytesIO(raw[:5000]))
    assert caught.value.code == owner.INCOMPLETE


def test_stream_transport_error_blocks_known_tool_bytes():
    class BrokenStream(io.BytesIO):
        def read(self, size=-1):
            if self.tell() >= 10240:
                raise OSError("stream unavailable")
            return super().read(size)
    with pytest.raises(owner.ArchiveInspectionError) as caught:
        owner.inspect_archive(BrokenStream(_tar(_entries())))
    assert caught.value.code == owner.INCOMPLETE


@pytest.mark.parametrize("kind", (tarfile.XHDTYPE, tarfile.XGLTYPE,
    tarfile.GNUTYPE_LONGNAME, tarfile.GNUTYPE_LONGLINK))
def test_huge_extended_metadata_is_rejected_before_payload_allocation(kind):
    member = tarfile.TarInfo("metadata")
    member.type, member.size = kind, owner.MAX_METADATA_BYTES + 1
    raw = member.tobuf(format=tarfile.USTAR_FORMAT)
    class HeaderOnlyStream(io.BytesIO):
        calls = []
        def read(self, size=-1):
            assert 0 <= size <= 65536
            self.calls.append(size)
            return super().read(size)
    stream = HeaderOnlyStream(raw)
    with pytest.raises(owner.ArchiveInspectionError) as caught:
        owner.inspect_archive(stream)
    assert caught.value.code == owner.INCOMPLETE
    assert caught.value.reason == "archive_metadata_header_size_limit"
    assert stream.tell() == 512
    assert max(stream.calls) <= 10240


def test_normal_pax_metadata_is_bounded_and_counted_as_a_physical_header():
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for index, (path, data) in enumerate(_entries()):
            member = tarfile.TarInfo(path.lstrip("/"))
            member.mode, member.size = 0o755, len(data)
            if index == 0:
                member.pax_headers = {"comment": "pure bounded metadata fixture"}
            archive.addfile(member, io.BytesIO(data))
    result = owner.inspect_archive(io.BytesIO(output.getvalue()))
    assert result.archive_entries == 4  # Three files and one PAX extension.
    assert result.java.sha256 == sha256(JAVA_BYTES).hexdigest()


def test_many_global_pax_headers_cannot_accumulate_archive_sized_metadata():
    def global_header(key):
        payload = key + "=" + "x" * 40000 + "\n"
        length = len(payload) + 2
        while length != len(str(length)) + 1 + len(payload):
            length = len(str(length)) + 1 + len(payload)
        raw = (str(length) + " " + payload).encode()
        member = tarfile.TarInfo("global-metadata")
        member.type, member.size = tarfile.XGLTYPE, len(raw)
        return member.tobuf(format=tarfile.USTAR_FORMAT) + raw + b"\x00" * (-len(raw) % 512)
    raw = global_header("first") + global_header("second") + _tar(_entries())
    with pytest.raises(owner.ArchiveInspectionError) as caught:
        owner.inspect_archive(io.BytesIO(raw))
    assert caught.value.code == owner.INCOMPLETE
    assert caught.value.reason == "archive_effective_metadata_size_limit"


def test_normal_gnu_longname_is_bounded_and_extension_counts_toward_limit(monkeypatch):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w", format=tarfile.GNU_FORMAT) as archive:
        for path, data in _entries() + [("/" + "long" * 45, b"unrelated")]:
            member = tarfile.TarInfo(path.lstrip("/"))
            member.mode, member.size = 0o755, len(data)
            archive.addfile(member, io.BytesIO(data))
    raw = output.getvalue()
    assert owner.inspect_archive(io.BytesIO(raw)).archive_entries == 5
    _bound(monkeypatch, max_archive_entries=4)
    with pytest.raises(owner.ArchiveInspectionError) as caught:
        owner.inspect_archive(io.BytesIO(raw))
    assert caught.value.code == owner.INCOMPLETE
    assert caught.value.reason == "image_archive_entry_limit"


@pytest.mark.parametrize("raw", (b"truncated header",))
def test_truncated_first_tar_header_is_incomplete(raw):
    with pytest.raises(owner.ArchiveInspectionError) as caught:
        owner.inspect_archive(io.BytesIO(raw))
    assert caught.value.code == owner.INCOMPLETE


def test_truncated_extended_header_payload_is_incomplete():
    member = tarfile.TarInfo("metadata")
    member.type, member.size = tarfile.GNUTYPE_LONGNAME, 2048
    raw = member.tobuf(format=tarfile.USTAR_FORMAT) + b"partial payload"
    with pytest.raises(owner.ArchiveInspectionError) as caught:
        owner.inspect_archive(io.BytesIO(raw))
    assert caught.value.code == owner.INCOMPLETE


def test_sparse_metadata_cannot_accumulate_an_unbounded_extent_map():
    member = tarfile.TarInfo("sparse")
    member.type = tarfile.GNUTYPE_SPARSE
    with pytest.raises(owner.ArchiveInspectionError) as caught:
        owner.inspect_archive(io.BytesIO(member.tobuf(format=tarfile.GNU_FORMAT)))
    assert caught.value.reason == "archive_sparse_metadata_unsupported"
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w", format=tarfile.PAX_FORMAT) as archive:
        member = tarfile.TarInfo("pax-sparse")
        member.pax_headers = {"GNU.sparse.map": "0,64", "GNU.sparse.size": "64"}
        member.size, member.mode = 64, 0o755
        archive.addfile(member, io.BytesIO(b"x" * 64))
    with pytest.raises(owner.ArchiveInspectionError) as caught:
        owner.inspect_archive(io.BytesIO(output.getvalue()))
    assert caught.value.reason == "archive_sparse_metadata_unsupported"


def test_nonelf_executable_is_not_fully_hashed(monkeypatch):
    calls = []
    original = owner.frozen._read_executable
    def measured(stream, size):
        calls.append(size)
        return original(stream, size)
    monkeypatch.setattr(owner.frozen, "_read_executable", measured)
    result = _inspect(_entries() + [("/unrelated-script", b"#!/bin/sh\n" + b"x" * 20000)])
    assert result.stream_complete
    assert calls == [64, 64, 64]


def test_no_unbounded_read_extractall_or_persisted_archive(monkeypatch):
    class StrictStream(io.BytesIO):
        def read(self, size=-1):
            assert 0 <= size <= 65536
            return super().read(size)
    def denied(*args, **kwargs):
        raise AssertionError("host extraction is forbidden")
    monkeypatch.setattr(tarfile.TarFile, "extract", denied)
    monkeypatch.setattr(tarfile.TarFile, "extractall", denied)
    result = owner.inspect_archive(StrictStream(_tar(_entries())))
    assert result.stream_complete
    assert not hasattr(result, "complete_inventory")
    assert not hasattr(result, "exact_provider_proven")


def test_production_parser_has_no_caller_target_or_limit_arguments():
    with pytest.raises(TypeError):
        owner.inspect_archive(io.BytesIO(), image_identity="mutable:tag")
    assert owner.REQUIREMENT.image_identity == owner.requirement.IMAGE
    assert owner.REQUIREMENT.inspection_bounds.export_timeout_ms == owner.frozen.EXPORT_TIMEOUT_MS
