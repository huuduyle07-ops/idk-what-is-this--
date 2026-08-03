"""CTX.READ.1 immutable receipt and pure freshness tests."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from core.direct_read_receipt import (
    DirectReadFileIdentity,
    DirectReadRangeReceipt,
    DirectReadReceipt,
    verify_direct_read_receipt,
)
from core.repository_inventory import RepositoryFileIdentity


def _receipt(path: Path) -> DirectReadReceipt:
    raw = path.read_bytes()
    observed = path.stat()
    identity = DirectReadFileIdentity.from_stat_result(
        observed,
        content_sha256=hashlib.sha256(raw).hexdigest(),
        scanned_content_sha256=hashlib.sha256(raw).hexdigest(),
    )
    return DirectReadReceipt(
        task_id="run-receipt",
        operation_id="operation-receipt",
        inventory_identity="sha256:" + "a" * 64,
        path=path.name,
        read_status="read_complete",
        read_mode="full_file",
        file_identity=identity,
        ranges=(DirectReadRangeReceipt(1, 1, len(raw), 1),),
        bytes_scanned=len(raw),
        bytes_returned=len(raw),
        lines_scanned=1,
        lines_returned=1,
        truncated=False,
        truncation_reasons=(),
        decoding="utf8",
        replacement_count=0,
        parser_support="unsupported",
        understanding_confidence="raw_text_only",
    )


def test_receipt_contains_stable_identity_ranges_counters_and_authority(
    tmp_path: Path,
) -> None:
    path = tmp_path / "file.custom"
    path.write_bytes(b"hello\n")

    receipt = _receipt(path)
    rendered = receipt.as_dict()

    assert rendered["file_identity"]["content_sha256"] == hashlib.sha256(
        b"hello\n"
    ).hexdigest()
    assert rendered["ranges"] == [
        {"start_line": 1, "end_line": 1, "bytes_returned": 6, "lines_returned": 1}
    ]
    assert rendered["bytes_scanned"] == rendered["bytes_returned"] == 6
    assert rendered["read_authority_granted"] is True
    assert rendered["write_authority"] is False
    assert rendered["patch_authority"] is False
    assert rendered["authority_scope"]["persistent"] is False


def test_receipt_freshness_passes_unchanged_file(tmp_path: Path) -> None:
    path = tmp_path / "file.txt"
    path.write_bytes(b"hello\n")
    receipt = _receipt(path)
    current = RepositoryFileIdentity.from_stat_result(path.stat())

    decision = verify_direct_read_receipt(receipt, current)

    assert decision.status == "fresh"
    assert decision.fresh is True
    assert decision.as_dict()["write_authority"] is False
    assert decision.as_dict()["patch_authority"] is False


def test_receipt_freshness_detects_changed_file(tmp_path: Path) -> None:
    path = tmp_path / "file.txt"
    path.write_bytes(b"hello\n")
    receipt = _receipt(path)
    path.write_text("changed content\n", encoding="utf-8")

    decision = verify_direct_read_receipt(
        receipt, RepositoryFileIdentity.from_stat_result(path.stat())
    )

    assert decision.status == "changed"
    assert decision.receipt_usable_for_future_patch_proposal is False


def test_receipt_freshness_detects_deleted_and_replaced_file(tmp_path: Path) -> None:
    path = tmp_path / "file.txt"
    path.write_bytes(b"hello\n")
    receipt = _receipt(path)
    path.unlink()

    deleted = verify_direct_read_receipt(receipt, None)
    replacement_identity = {
        **receipt.file_identity.as_dict(),
        "inode": receipt.file_identity.inode + 1,
    }
    replaced = verify_direct_read_receipt(receipt, replacement_identity)

    assert deleted.status == "deleted"
    assert replaced.status == "replaced"


def test_receipt_freshness_is_unverifiable_for_incomplete_identity(
    tmp_path: Path,
) -> None:
    path = tmp_path / "file.txt"
    path.write_bytes(b"hello\n")
    receipt = _receipt(path)

    decision = verify_direct_read_receipt(receipt, {"size": 6})

    assert decision.status == "unverifiable"
