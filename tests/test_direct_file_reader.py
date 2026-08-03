"""Focused CTX.READ.1 mode, range, encoding, and descriptor tests."""

from __future__ import annotations

import copy
import os
from pathlib import Path

import pytest

import core.direct_file_reader as reader_module
from core.direct_context_runtime import (
    compute_repository_inventory_identity,
    execute_direct_context,
)
from core.direct_file_reader import (
    DirectReadBudgets,
    build_match_windows,
    choose_direct_read_mode,
    normalize_direct_read_ranges,
)
from core.file_capabilities import classify_file_capability
from core.repository_inventory import (
    create_repository_inventory,
    repository_inventory_from_entries,
)


def _write(root: Path, relative: str, content: str | bytes) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_bytes(content.encode("utf-8"))
    return path


def _proposal(inventory, paths: tuple[str, ...] | None = None):
    entries = {
        entry.relative_path.as_posix(): entry for entry in inventory.entries
    }
    selected_paths = paths or tuple(entries)
    selected = [
        {
            "path": path,
            "actionability_score": 80,
            "estimated_bytes": entries[path].file_identity.size_bytes,
            "role": "primary_or_supporting_target",
            "selection_reason": "trusted test proposal",
            "read_authority": False,
            "write_authority": False,
        }
        for path in selected_paths
    ]
    return {
        "selected": selected,
        "excluded": [],
        "total_estimated_bytes": sum(item["estimated_bytes"] for item in selected),
        "max_files": 8,
        "max_total_bytes": 1_048_576,
        "read_authority": False,
        "write_authority": False,
    }


def _run(
    root: Path,
    inventory,
    selected_files,
    *,
    proposal=None,
    budgets=None,
    search_evidence=None,
    capabilities=None,
):
    request = {
        "schema_version": 1,
        "task_id": "run-test",
        "repository_root": str(root.resolve()),
        "inventory_identity": compute_repository_inventory_identity(inventory),
        "selected_files": selected_files,
    }
    if budgets is not None:
        request["budgets"] = budgets
    return execute_direct_context(
        root,
        inventory,
        request,
        proposed_read_set=proposal or _proposal(inventory),
        search_evidence=search_evidence,
        capabilities=capabilities,
    )


def test_small_file_mode_is_full_file() -> None:
    capability = classify_file_capability(
        "app.py", size_bytes=20, text_hint=True, is_binary=False
    )

    decision = choose_direct_read_mode(
        file_size=20,
        repository_tier="small",
        lexical_matches=(),
        capability=capability,
        budgets=DirectReadBudgets(),
    )

    assert decision.mode == "full_file"
    assert decision.accepted is True
    assert decision.as_dict()["write_authority"] is False


def test_one_file_unsupported_project_selects_full_file() -> None:
    capability = classify_file_capability(
        "program.unknown", size_bytes=12, text_hint=True, is_binary=False
    )

    decision = choose_direct_read_mode(
        file_size=12,
        repository_tier="single_file",
        lexical_matches=(),
        capability=capability,
    )

    assert capability.parser_support == "unsupported"
    assert decision.mode == "full_file"
    assert "single readable" in decision.reason


def test_large_matched_and_unmatched_mode_decisions_are_bounded() -> None:
    capability = classify_file_capability(
        "large.custom", size_bytes=300_000, text_hint=True, is_binary=False
    )

    matched = choose_direct_read_mode(
        file_size=300_000,
        repository_tier="large",
        lexical_matches=({"line": 20},),
        capability=capability,
    )
    unmatched = choose_direct_read_mode(
        file_size=300_000,
        repository_tier="large",
        lexical_matches=(),
        capability=capability,
    )
    unknown = choose_direct_read_mode(
        file_size=None,
        repository_tier="large",
        lexical_matches=(),
        capability=capability,
    )

    assert matched.mode == "match_windows"
    assert unmatched.mode == "explicit_ranges"
    assert unmatched.default_ranges[0].start_line == 1
    assert unknown.mode is None


def test_explicit_ranges_normalize_and_overlaps_merge_deterministically() -> None:
    first = normalize_direct_read_ranges(
        [(20, 30), {"start_line": 1, "end_line": 5}, (4, 10), (11, 12)]
    )
    second = normalize_direct_read_ranges(
        reversed([(20, 30), (1, 5), (4, 10), (11, 12)])
    )

    assert first == second
    assert [(item.start_line, item.end_line) for item in first] == [
        (1, 12),
        (20, 30),
    ]


def test_match_windows_merge_and_range_count_is_capped() -> None:
    merged = build_match_windows(
        [{"line": 100}, {"line": 110}], lines_before=10, lines_after=10
    )
    capped = normalize_direct_read_ranges(
        [(index * 10 + 1, index * 10 + 2) for index in range(20)],
        max_ranges=3,
    )

    assert [(item.start_line, item.end_line) for item in merged] == [(90, 120)]
    assert len(capped) == 3


def test_zero_width_match_context_is_supported() -> None:
    windows = build_match_windows(
        [{"line": 7}], lines_before=0, lines_after=0
    )

    assert [(item.start_line, item.end_line) for item in windows] == [(7, 7)]


def test_safe_utf8_ascii_and_bom_files_read_successfully(tmp_path: Path) -> None:
    _write(tmp_path, "utf8.txt", "snowman: ☃\n")
    _write(tmp_path, "ascii.txt", b"plain ascii\n")
    _write(tmp_path, "bom.txt", b"\xef\xbb\xbfwith bom\n")
    inventory = create_repository_inventory(tmp_path)

    result = _run(
        tmp_path,
        inventory,
        [
            {"path": "utf8.txt", "requested_mode": "full_file"},
            {"path": "ascii.txt", "requested_mode": "full_file"},
            {"path": "bom.txt", "requested_mode": "full_file"},
        ],
    )

    assert result.status == "operation_complete"
    by_path = {item.path: item for item in result.file_results}
    assert by_path["utf8.txt"].content == "snowman: ☃\n"
    assert by_path["ascii.txt"].receipt.decoding == "utf8"
    assert by_path["bom.txt"].content == "with bom\n"
    assert by_path["bom.txt"].receipt.decoding == "utf8_bom"


def test_unsupported_extension_is_raw_text_without_ast_claim(tmp_path: Path) -> None:
    _write(tmp_path, "only.mystery", "usable direct context\n")
    inventory = create_repository_inventory(tmp_path)

    result = _run(
        tmp_path,
        inventory,
        [{"path": "only.mystery", "requested_mode": "auto"}],
    )
    receipt = result.read_receipts[0]

    assert result.file_results[0].content == "usable direct context\n"
    assert receipt.read_mode == "full_file"
    assert receipt.parser_support == "unsupported"
    assert receipt.understanding_confidence == "raw_text_only"


@pytest.mark.parametrize(
    "relative,payload,expected_status",
    [
        ("invalid.custom", b"hello\xffworld", "encoding_unsupported"),
        ("binary.custom", b"hello\x00world", "binary_or_opaque"),
        ("image.png", b"not-even-opened", "binary_or_opaque"),
    ],
)
def test_invalid_utf8_and_binary_content_return_no_content(
    tmp_path: Path, relative: str, payload: bytes, expected_status: str
) -> None:
    _write(tmp_path, relative, payload)
    inventory = create_repository_inventory(tmp_path)

    result = _run(
        tmp_path, inventory, [{"path": relative, "requested_mode": "full_file"}]
    )
    file_result = result.file_results[0]

    assert file_result.read_status == expected_status
    assert file_result.content is None
    assert file_result.receipt is None
    assert file_result.read_authority_granted is False


@pytest.mark.parametrize(
    "relative,approval,forbidden",
    [
        (".env", True, False),
        ("private.pem", False, True),
        ("credentials/store.txt", False, True),
    ],
)
def test_sensitive_policy_never_exposes_content(
    tmp_path: Path, relative: str, approval: bool, forbidden: bool
) -> None:
    secret = "NEVER_ECHO_THIS_SECRET"
    _write(tmp_path, relative, secret)
    inventory = create_repository_inventory(tmp_path)
    if relative not in {entry.relative_path.as_posix() for entry in inventory.entries}:
        pytest.skip("canonical inventory policy excludes the sensitive fixture")

    result = _run(
        tmp_path, inventory, [{"path": relative, "requested_mode": "full_file"}]
    )
    file_result = result.file_results[0]

    assert file_result.read_status == "sensitive_file_blocked"
    assert file_result.approval_required is approval
    assert file_result.forbidden is forbidden
    assert secret not in repr(result.as_dict())


def test_env_example_is_auto_readable(tmp_path: Path) -> None:
    _write(tmp_path, ".env.example", "SAFE_PLACEHOLDER=value\n")
    inventory = create_repository_inventory(tmp_path)

    result = _run(
        tmp_path,
        inventory,
        [{"path": ".env.example", "requested_mode": "full_file"}],
    )

    assert result.file_results[0].read_status == "read_complete"


def test_match_windows_return_only_merged_bounded_context(tmp_path: Path) -> None:
    content = "".join(f"line-{line}\n" for line in range(1, 301))
    _write(tmp_path, "large.txt", content)
    inventory = create_repository_inventory(tmp_path)
    search = {
        "matches": [
            {"path": "large.txt", "line_number": 100, "matched_term": "needle"},
            {"path": "large.txt", "line_number": 110, "matched_term": "needle"},
        ]
    }

    result = _run(
        tmp_path,
        inventory,
        [
            {
                "path": "large.txt",
                "requested_mode": "match_windows",
                "match_locations": [
                    {"line": 110, "term": "needle"},
                    {"line": 100, "term": "needle"},
                ],
            }
        ],
        budgets={
            **DirectReadBudgets().as_dict(),
            "match_lines_before": 10,
            "match_lines_after": 10,
        },
        search_evidence=search,
    )
    receipt = result.read_receipts[0]

    assert [(item.start_line, item.end_line) for item in receipt.ranges] == [(90, 120)]
    assert "line-89\n" not in result.file_results[0].content
    assert "line-90\n" in result.file_results[0].content
    assert "line-120\n" in result.file_results[0].content
    assert "line-121\n" not in result.file_results[0].content


def test_untrusted_match_location_is_ignored_and_read_fails_closed(tmp_path: Path) -> None:
    _write(tmp_path, "large.txt", "".join(f"line-{line}\n" for line in range(200)))
    inventory = create_repository_inventory(tmp_path)

    result = _run(
        tmp_path,
        inventory,
        [
            {
                "path": "large.txt",
                "requested_mode": "match_windows",
                "match_locations": [{"line": 150, "term": "fabricated"}],
            }
        ],
        search_evidence={"matches": []},
    )

    assert result.file_results[0].read_status == "read_failed"
    assert result.file_results[0].content is None
    assert "untrusted match locations" in result.warnings[0]


def test_match_window_limit_is_explicit_in_receipt(tmp_path: Path) -> None:
    _write(tmp_path, "many.txt", "".join(f"line-{line}\n" for line in range(1, 101)))
    inventory = create_repository_inventory(tmp_path)
    matches = [
        {"path": "many.txt", "line_number": line, "matched_term": "needle"}
        for line in range(10, 30, 2)
    ]

    result = _run(
        tmp_path,
        inventory,
        [
            {
                "path": "many.txt",
                "requested_mode": "match_windows",
                "match_locations": [
                    {"line": item["line_number"], "term": "needle"}
                    for item in matches
                ],
            }
        ],
        budgets={
            **DirectReadBudgets().as_dict(),
            "match_lines_before": 0,
            "match_lines_after": 0,
        },
        search_evidence={"matches": matches},
    )

    assert result.read_receipts[0].read_status == "read_complete_with_truncation"
    assert "match_window_limit" in result.read_receipts[0].truncation_reasons
    assert len(result.read_receipts[0].ranges) == 8


def test_explicit_range_line_and_return_byte_budgets_are_accurate(tmp_path: Path) -> None:
    _write(tmp_path, "app.txt", "alpha\nbeta\ngamma\ndelta\n")
    inventory = create_repository_inventory(tmp_path)

    result = _run(
        tmp_path,
        inventory,
        [
            {
                "path": "app.txt",
                "requested_mode": "explicit_ranges",
                "ranges": [{"start_line": 1, "end_line": 4}],
            }
        ],
        budgets={
            **DirectReadBudgets().as_dict(),
            "max_total_bytes": 11,
            "max_lines_per_file": 2,
        },
    )
    receipt = result.read_receipts[0]

    assert result.file_results[0].content == "alpha\nbeta\n"
    assert receipt.bytes_returned == 11
    assert receipt.lines_returned == 2
    assert receipt.truncated is True
    assert "line_return_limit" in receipt.truncation_reasons


def test_requested_full_file_never_reads_past_per_file_byte_budget(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "large.txt", "x" * 100)
    inventory = create_repository_inventory(tmp_path)

    result = _run(
        tmp_path,
        inventory,
        [{"path": "large.txt", "requested_mode": "full_file"}],
        budgets={**DirectReadBudgets().as_dict(), "max_bytes_per_file": 20},
    )

    assert result.file_results[0].read_status == "budget_exhausted"
    assert result.file_results[0].bytes_scanned == 0


def test_long_excerpt_line_is_bounded_with_accurate_metadata(tmp_path: Path) -> None:
    _write(tmp_path, "line.txt", "x" * 100 + "\n")
    inventory = create_repository_inventory(tmp_path)

    result = _run(
        tmp_path,
        inventory,
        [{"path": "line.txt", "requested_mode": "full_file"}],
        budgets={**DirectReadBudgets().as_dict(), "max_excerpt_line_length": 12},
    )
    receipt = result.read_receipts[0]

    assert len(result.file_results[0].content.encode("utf-8")) == 12
    assert receipt.bytes_returned == 12
    assert "excerpt_line_length" in receipt.truncation_reasons


def test_symlink_file_is_rejected(tmp_path: Path) -> None:
    target = _write(tmp_path, "target.txt", "safe\n")
    link = tmp_path / "link.txt"
    try:
        link.symlink_to(target)
    except OSError as exc:
        pytest.skip(f"symlink creation is unavailable: {exc}")
    inventory = repository_inventory_from_entries(
        tmp_path, [(link, Path("link.txt"))], sort_entries=True
    )

    result = _run(
        tmp_path, inventory, [{"path": "link.txt", "requested_mode": "full_file"}]
    )

    assert result.file_results[0].read_status == "symlink_rejected"
    assert result.file_results[0].content is None


def test_post_inventory_symlink_escape_is_rejected(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    path = _write(repo, "app.txt", "inside\n")
    outside = _write(tmp_path, "outside.txt", "outside secret\n")
    inventory = create_repository_inventory(repo)
    path.unlink()
    try:
        path.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"symlink creation is unavailable: {exc}")

    result = _run(
        repo, inventory, [{"path": "app.txt", "requested_mode": "full_file"}]
    )

    assert result.file_results[0].read_status == "symlink_rejected"
    assert "outside secret" not in repr(result.as_dict())


def test_replaced_file_after_inventory_fails_closed(tmp_path: Path) -> None:
    path = _write(tmp_path, "app.txt", "before\n")
    inventory = create_repository_inventory(tmp_path)
    path.unlink()
    path.write_text("after!\n", encoding="utf-8")

    result = _run(
        tmp_path, inventory, [{"path": "app.txt", "requested_mode": "full_file"}]
    )

    assert result.file_results[0].read_status == "file_changed_or_replaced"
    assert result.file_results[0].content is None


def test_file_changed_during_read_discards_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _write(tmp_path, "app.txt", "before\n")
    inventory = create_repository_inventory(tmp_path)
    original = reader_module._scan_descriptor

    def mutate_after_read(*args, **kwargs):
        snapshot = original(*args, **kwargs)
        path.write_text("changed during read\n", encoding="utf-8")
        return snapshot

    monkeypatch.setattr(reader_module, "_scan_descriptor", mutate_after_read)
    result = _run(
        tmp_path, inventory, [{"path": "app.txt", "requested_mode": "full_file"}]
    )

    assert result.file_results[0].read_status == "file_changed_or_replaced"
    assert result.file_results[0].content is None


def test_request_inputs_are_not_mutated(tmp_path: Path) -> None:
    _write(tmp_path, "app.txt", "content\n")
    inventory = create_repository_inventory(tmp_path)
    selected = [{"path": "app.txt", "requested_mode": "full_file"}]
    proposal = _proposal(inventory)
    before_selected = copy.deepcopy(selected)
    before_proposal = copy.deepcopy(proposal)

    _run(tmp_path, inventory, selected, proposal=proposal)

    assert selected == before_selected
    assert proposal == before_proposal
