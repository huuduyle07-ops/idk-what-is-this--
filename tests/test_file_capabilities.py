"""Focused contracts for CTX.SELECT.1 file capability classification."""

from __future__ import annotations

import copy
from dataclasses import FrozenInstanceError

import pytest

import config
from core.file_capabilities import (
    EDITABILITY_STATES,
    INDEXABILITY_STATES,
    PARSER_SUPPORT_STATES,
    READABILITY_STATES,
    READ_POLICY_STATES,
    UNDERSTANDING_CONFIDENCE_STATES,
    classify_file_capabilities,
    classify_file_capability,
)
from core.source_file_policy import SUPPORTED_EXTENSIONS as SOURCE_SUPPORTED_EXTENSIONS


EXPECTED_SUPPORTED_EXTENSIONS = {
    ".txt",
    ".md",
    ".pdf",
    ".docx",
    ".json",
    ".py",
    ".rs",
    ".mojo",
    ".lua",
    ".c",
    ".h",
    ".cpp",
    ".cxx",
    ".cc",
    ".hpp",
    ".hxx",
    ".cs",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
    ".html",
    ".htm",
    ".css",
    ".scss",
    ".sass",
    ".go",
    ".java",
    ".kt",
    ".kts",
}


def test_supported_source_text_is_readable_and_canonical_indexable() -> None:
    capability = classify_file_capability("src/router.py", size_bytes=123)

    assert capability.readability == "readable_text"
    assert capability.parser_support == "supported"
    assert capability.indexability == "canonical_indexable"
    assert capability.direct_read_allowed is True
    assert capability.read_policy == "auto_read_allowed"
    assert capability.editability == "editable"
    assert capability.understanding_confidence == "parsed"


def test_unsupported_safe_text_remains_direct_context_readable() -> None:
    capability = classify_file_capability("src/router.yaml", size_bytes=80)

    assert capability.readability == "readable_text"
    assert capability.parser_support == "unsupported"
    assert capability.indexability == "direct_context_only"
    assert capability.direct_read_allowed is True
    assert capability.editability == "editable_with_review"
    assert capability.understanding_confidence == "raw_text_only"


@pytest.mark.parametrize(
    ("path", "expected"),
    [("settings.yaml", "unsupported"), ("guide.pdf", "partial")],
)
def test_parser_hint_cannot_overstate_canonical_parser_support(
    path: str,
    expected: str,
) -> None:
    capability = classify_file_capability(path, parser_support="supported")

    assert capability.parser_support == expected
    assert any("parser-support hint" in reason for reason in capability.reasons)
    assert any("raw direct context" in reason for reason in capability.reasons)


def test_unmanaged_binary_file_is_opaque_and_not_directly_readable() -> None:
    capability = classify_file_capability("assets/logo.png", size_bytes=512)

    assert capability.readability == "opaque_binary"
    assert capability.parser_support == "not_applicable"
    assert capability.indexability == "not_indexable"
    assert capability.direct_read_allowed is False
    assert capability.read_policy == "hard_no_auto_read"
    assert capability.editability == "opaque"


def test_binary_metadata_fails_closed_even_with_conflicting_text_hint() -> None:
    capability = classify_file_capability(
        "data/payload.dat",
        is_binary=True,
        readability="readable_text",
        text_hint=True,
    )

    assert capability.readability == "opaque_binary"
    assert capability.direct_read_allowed is False
    assert capability.read_policy == "hard_no_auto_read"
    assert "conflicting text-readability hint failed closed" in capability.reasons


def test_sensitive_policy_distinguishes_placeholder_env_and_hard_secrets() -> None:
    placeholder = classify_file_capability(".env.example", size_bytes=20)
    environment = classify_file_capability(".env", size_bytes=20)
    private_key = classify_file_capability("certs/private.pem", size_bytes=20)
    credential_store = classify_file_capability("profile/cookies.sqlite", size_bytes=20)

    assert placeholder.read_policy == "auto_read_allowed"
    assert placeholder.direct_read_allowed is True
    assert placeholder.editability == "editable_with_review"
    assert environment.readability == "sensitive"
    assert environment.read_policy == "explicit_human_approval_required"
    assert environment.direct_read_allowed is False
    assert environment.editability == "sensitive_requires_approval"
    for capability in (private_key, credential_store):
        assert capability.read_policy == "hard_no_auto_read"
        assert capability.direct_read_allowed is False
        assert capability.editability == "forbidden"


def test_generated_file_is_readable_but_not_a_direct_patch_target() -> None:
    capability = classify_file_capability(
        "generated/client.py",
        size_bytes=100,
        authoritative_source="schema/client.json",
    )

    assert capability.direct_read_allowed is True
    assert capability.editability == "generated_do_not_edit"
    assert capability.authoritative_source == "schema/client.json"


@pytest.mark.parametrize("path", ["generated/client.py", "vendor/client.py"])
def test_path_derived_generated_or_vendor_gate_cannot_be_weakened(path: str) -> None:
    capability = classify_file_capability(
        {
            "path": path,
            "generated": False,
            "vendor": False,
            "editability": "editable",
        }
    )

    assert capability.editability == "generated_do_not_edit"


@pytest.mark.parametrize(
    ("path", "metadata"),
    [
        ("../outside.py", {}),
        ("C:/outside.py", {}),
        ("src/router.py", {"repository_contained": False}),
    ],
)
def test_outside_repository_path_is_rejected(path: str, metadata: dict[str, bool]) -> None:
    capability = classify_file_capability(path, **metadata)

    assert capability.repository_contained is False
    assert capability.direct_read_allowed is False
    assert capability.read_policy == "hard_no_auto_read"
    assert capability.editability == "outside_scope"


def test_symlink_escape_is_rejected_even_for_supported_source() -> None:
    capability = classify_file_capability(
        "src/router.py",
        repository_contained=True,
        symlink_escape=True,
    )

    assert capability.repository_contained is True
    assert capability.symlink_escape is True
    assert capability.direct_read_allowed is False
    assert capability.read_policy == "hard_no_auto_read"
    assert capability.editability == "forbidden"


def test_capability_classification_is_deterministic_immutable_and_nonmutating() -> None:
    record = {
        "path": "src/example.mojo",
        "size_bytes": 17,
        "text_hint": True,
        "generated": False,
    }
    before = copy.deepcopy(record)

    first = classify_file_capability(record)
    second = classify_file_capability(copy.deepcopy(record))

    assert first == second
    assert first.as_dict() == second.as_dict()
    assert record == before
    assert first.reasons == tuple(sorted(set(first.reasons)))
    with pytest.raises(FrozenInstanceError):
        first.path = "elsewhere.mojo"  # type: ignore[misc]


def test_bulk_classification_rejects_duplicates_and_nondeterministic_order() -> None:
    with pytest.raises(ValueError, match="duplicate canonical paths"):
        classify_file_capabilities(["src/A.py", "src/a.py"])
    with pytest.raises(ValueError, match="deterministic path ordering"):
        classify_file_capabilities(["src/z.py", "src/a.py"])


def test_capability_state_sets_are_stable_and_complete() -> None:
    assert READABILITY_STATES == (
        "readable_text",
        "readable_limited",
        "opaque_binary",
        "unreadable",
        "sensitive",
    )
    assert PARSER_SUPPORT_STATES == (
        "supported",
        "partial",
        "unsupported",
        "not_applicable",
    )
    assert INDEXABILITY_STATES == (
        "canonical_indexable",
        "direct_context_only",
        "not_indexable",
    )
    assert EDITABILITY_STATES == (
        "editable",
        "editable_with_review",
        "read_only",
        "generated_do_not_edit",
        "sensitive_requires_approval",
        "outside_scope",
        "opaque",
        "forbidden",
    )
    assert READ_POLICY_STATES == (
        "auto_read_allowed",
        "explicit_human_approval_required",
        "hard_no_auto_read",
    )
    assert UNDERSTANDING_CONFIDENCE_STATES == (
        "parsed",
        "partial",
        "raw_text_only",
        "unknown",
    )


def test_supported_extension_policy_is_an_exact_reexport_not_a_semantic_change() -> None:
    assert SOURCE_SUPPORTED_EXTENSIONS == EXPECTED_SUPPORTED_EXTENSIONS
    assert config.SUPPORTED_EXTENSIONS is SOURCE_SUPPORTED_EXTENSIONS


@pytest.mark.parametrize(
    ("editability", "expected_policy"),
    [
        ("forbidden", "hard_no_auto_read"),
        ("outside_scope", "hard_no_auto_read"),
        ("opaque", "hard_no_auto_read"),
        ("sensitive_requires_approval", "explicit_human_approval_required"),
    ],
)
def test_restrictive_editability_tightens_direct_read_policy(
    editability: str,
    expected_policy: str,
) -> None:
    capability = classify_file_capability("notes.txt", editability=editability)

    assert capability.editability == editability
    assert capability.read_policy == expected_policy
    assert capability.direct_read_allowed is False
    assert capability.indexability == "not_indexable"


def test_public_read_policy_field_tightens_incomplete_inventory_mapping() -> None:
    capability = classify_file_capability(
        {
            "path": "notes.txt",
            "read_policy": "explicit_human_approval_required",
        }
    )

    assert capability.read_policy == "explicit_human_approval_required"
    assert capability.editability == "sensitive_requires_approval"
    assert capability.direct_read_allowed is False


def test_sensitive_readability_implies_approval_policy_and_editability() -> None:
    capability = classify_file_capability("notes.txt", readability="sensitive")

    assert capability.readability == "sensitive"
    assert capability.read_policy == "explicit_human_approval_required"
    assert capability.editability == "sensitive_requires_approval"
    assert capability.direct_read_allowed is False
    assert capability.indexability == "not_indexable"
