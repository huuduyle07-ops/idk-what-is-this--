"""Focused contracts for bounded CTX.SELECT.1 candidate discovery."""

from __future__ import annotations

import copy

import pytest

from core.file_candidate_selector import (
    DEFAULT_LEXICAL_EXCLUDE_PATHS,
    MAX_CANDIDATE_FILES,
    MAX_DIRECTORY_SYNOPSIS,
    MAX_EXACT_NAME_MATCHES,
    MAX_EXPANSION_ROUNDS,
    MAX_LEXICAL_FILES,
    MAX_LEXICAL_EXCLUDE_PATHS,
    MAX_LEXICAL_INCLUDE_PATHS,
    MAX_LEXICAL_MATCHES,
    MAX_LEXICAL_MATCH_LENGTH,
    MAX_LEXICAL_TERMS,
    MAX_LIKELY_ENTRYPOINTS,
    MAX_ROOT_ENTRIES,
    MAX_SUPPLIED_LEXICAL_TERMS,
    MAX_SUPPLIED_REFERENCE_EVIDENCE_PER_FILE,
    MAX_TOKEN_NAME_MATCHES,
    build_candidate_filename_report,
    build_lexical_search_request,
    classify_repository_tier,
    consume_lexical_search_results,
    rank_candidates,
)
from core.file_capabilities import classify_file_capability


def _capability(path: str, size_bytes: int | None = 100, **metadata: object):
    return classify_file_capability(path, size_bytes=size_bytes, **metadata)


def _capabilities(count: int, prefix: str = "src") -> tuple[object, ...]:
    return tuple(
        _capability(f"{prefix}/pkg_{index:03d}/module_{index:03d}.py")
        for index in range(count)
    )


def _match(path: str, line: int, term: str = "router", excerpt: str = "router") -> dict[str, object]:
    return {
        "path": path,
        "line_number": line,
        "matched_term": term,
        "excerpt": excerpt,
        "result_source": "supplied_test_result",
    }


def test_one_file_repository_recommends_the_single_safe_readable_file() -> None:
    report = build_candidate_filename_report([_capability("README.yaml")])

    assert report.repository_tier == "small"
    assert report.readable_file_count == 1
    assert report.complete_relative_paths == ("README.yaml",)
    assert report.candidate_files == ("README.yaml",)
    assert [item.kind for item in report.evidence_for("README.yaml")] == [
        "single_readable_file",
        "unsupported_but_readable_text",
    ]


def test_small_repository_exposes_complete_safe_readable_path_list() -> None:
    capabilities = [
        _capability("README.md"),
        _capability("src/app.py"),
        _capability(".env"),
        _capability("certs/private.pem"),
    ]
    report = build_candidate_filename_report(capabilities)

    assert report.repository_tier == "small"
    assert report.repository_file_count == 4
    assert report.readable_file_count == 2
    assert report.complete_relative_paths == ("README.md", "src/app.py")
    assert tuple(item.path for item in report.capability_metadata) == (
        "README.md",
        "src/app.py",
    )
    assert ".env" not in report.complete_relative_paths
    assert "certs/private.pem" not in report.complete_relative_paths
    assert dict(report.truncation)["complete_relative_paths"].truncated is False


def test_medium_repository_exposes_synopsis_and_not_all_paths() -> None:
    report = build_candidate_filename_report(_capabilities(31))

    assert report.repository_tier == "medium"
    assert report.readable_file_count == 31
    assert report.complete_relative_paths == ()
    assert report.root_entries == ("src/",)
    assert report.directory_synopsis
    assert len(report.directory_synopsis) <= MAX_DIRECTORY_SYNOPSIS
    metadata = dict(report.truncation)["complete_relative_paths"]
    assert metadata.as_dict() == {
        "total": 31,
        "returned": 0,
        "limit": 0,
        "truncated": True,
    }


def test_large_repository_never_exposes_a_full_path_list() -> None:
    report = build_candidate_filename_report(_capabilities(301))

    assert report.repository_tier == "large"
    assert report.readable_file_count == 301
    assert report.complete_relative_paths == ()
    assert len(report.root_entries) <= MAX_ROOT_ENTRIES
    assert len(report.directory_synopsis) <= MAX_DIRECTORY_SYNOPSIS
    assert sum(dict(report.directory_file_counts).values()) >= 301
    assert sum(dict(report.file_type_counts).values()) == 301
    assert len(report.candidate_files) <= MAX_CANDIDATE_FILES


@pytest.mark.parametrize(
    ("count", "expected"),
    [(0, "small"), (30, "small"), (31, "medium"), (300, "medium"), (301, "large")],
)
def test_repository_tier_threshold_boundaries_are_deterministic(count: int, expected: str) -> None:
    assert classify_repository_tier(count) == expected
    assert classify_repository_tier(count) == classify_repository_tier(count)


def test_repository_tier_thresholds_are_configurable_but_validated() -> None:
    assert classify_repository_tier(2, small_max=1, medium_max=2) == "medium"
    assert classify_repository_tier(3, small_max=1, medium_max=2) == "large"
    with pytest.raises(ValueError, match="0 <= small < medium"):
        classify_repository_tier(1, small_max=2, medium_max=2)


def test_user_named_file_ranks_first_when_safe() -> None:
    capabilities = [_capability("core/main.py"), _capability("core/router.py")]
    report = build_candidate_filename_report(
        capabilities,
        task_terms=["main.py"],
        user_named_files=["core/router.py"],
    )
    ranked = rank_candidates(capabilities, filename_report=report)

    assert report.candidate_files[0] == "core/router.py"
    assert ranked[0].path == "core/router.py"
    assert "user_named_file" in {item.kind for item in ranked[0].positive_evidence}


def test_exact_filename_match_outranks_token_only_match() -> None:
    capabilities = [
        _capability("core/router.py"),
        _capability("core/router_helpers.py"),
    ]
    report = build_candidate_filename_report(capabilities, task_terms=["router.py"])

    assert report.exact_name_matches == ("core/router.py",)
    assert report.candidate_files[0] == "core/router.py"
    assert "core/router_helpers.py" in report.token_name_matches


def test_likely_entrypoint_receives_bounded_evidence() -> None:
    capabilities = [_capability(f"service_{index:02d}/main.py") for index in range(25)]
    report = build_candidate_filename_report(capabilities)

    assert len(report.likely_entrypoints) == MAX_LIKELY_ENTRYPOINTS
    assert dict(report.truncation)["likely_entrypoints"].as_dict() == {
        "total": 25,
        "returned": MAX_LIKELY_ENTRYPOINTS,
        "limit": MAX_LIKELY_ENTRYPOINTS,
        "truncated": True,
    }
    for path in report.likely_entrypoints:
        assert "likely_entrypoint" in {item.kind for item in report.evidence_for(path)}


def test_matching_test_file_is_associated_with_source_candidate() -> None:
    capabilities = [_capability("core/router.py"), _capability("tests/test_router.py")]
    report = build_candidate_filename_report(
        capabilities,
        user_named_files=["core/router.py"],
    )
    ranked = rank_candidates(capabilities, filename_report=report)
    by_path = {item.path: item for item in ranked}

    assert report.tests_for("core/router.py") == ("tests/test_router.py",)
    assert report.tests_for("tests/test_router.py") == ("core/router.py",)
    assert by_path["core/router.py"].validation_candidates == ("tests/test_router.py",)
    assert by_path["tests/test_router.py"].role == "validation"


def test_ambiguous_same_stem_files_are_not_paired_across_unrelated_packages() -> None:
    capabilities = [
        _capability("pkg_a/router.py"),
        _capability("pkg_b/router.py"),
        _capability("tests/test_router.py"),
    ]

    report = build_candidate_filename_report(capabilities, task_terms=["router"])

    assert report.tests_for("pkg_a/router.py") == ()
    assert report.tests_for("pkg_b/router.py") == ()
    assert report.tests_for("tests/test_router.py") == ()


def test_same_stem_test_pair_uses_directory_locality_when_sources_are_ambiguous() -> None:
    capabilities = [
        _capability("pkg_a/router.py"),
        _capability("pkg_b/router.py"),
        _capability("tests/pkg_a/test_router.py"),
    ]

    report = build_candidate_filename_report(capabilities, task_terms=["router"])

    assert report.tests_for("pkg_a/router.py") == ("tests/pkg_a/test_router.py",)
    assert report.tests_for("pkg_b/router.py") == ()


def test_duplicate_canonical_paths_are_rejected() -> None:
    capabilities = [_capability("core/Router.py"), _capability("core/router.py")]

    with pytest.raises(ValueError, match="duplicate canonical paths"):
        build_candidate_filename_report(capabilities, task_terms=["router"])


def test_candidate_ordering_is_deterministic_and_inputs_are_not_mutated() -> None:
    capabilities = [
        _capability("tests/test_router.py"),
        _capability("core/router_helpers.py"),
        _capability("core/router.py"),
        _capability("main.py"),
    ]
    task_terms = ["router", "main"]
    before_capabilities = tuple(capability.as_dict() for capability in capabilities)
    before_terms = copy.deepcopy(task_terms)

    first = build_candidate_filename_report(capabilities, task_terms=task_terms)
    second = build_candidate_filename_report(reversed(capabilities), task_terms=reversed(task_terms))

    assert first == second
    assert first.as_dict() == second.as_dict()
    assert tuple(capability.as_dict() for capability in capabilities) == before_capabilities
    assert task_terms == before_terms


def test_user_named_symbol_generator_is_materialized_once_and_keeps_evidence() -> None:
    report = build_candidate_filename_report(
        [_capability("core/dispatch_request.py")],
        user_named_symbols=(value for value in ("dispatch", "request")),
    )

    kinds = {
        item.kind
        for item in dict(report.evidence_by_path)["core/dispatch_request.py"]
    }
    assert "user_named_symbol" in kinds


def test_every_candidate_name_list_reports_truncation_metadata() -> None:
    capabilities = [_capability(f"service_{index:03d}/main.py") for index in range(100)]
    report = build_candidate_filename_report(capabilities, task_terms=["main"])
    truncation = dict(report.truncation)

    assert set(truncation) == {
        "candidate_files",
        "capability_metadata",
        "complete_relative_paths",
        "directory_file_counts",
        "directory_synopsis",
        "exact_name_matches",
        "file_type_counts",
        "likely_entrypoints",
        "root_entries",
        "token_name_matches",
    }
    assert truncation["candidate_files"].returned == MAX_CANDIDATE_FILES
    assert truncation["candidate_files"].truncated is True
    assert truncation["likely_entrypoints"].limit == MAX_LIKELY_ENTRYPOINTS
    assert truncation["exact_name_matches"].limit == MAX_EXACT_NAME_MATCHES
    assert truncation["token_name_matches"].limit == MAX_TOKEN_NAME_MATCHES


def test_lexical_search_request_is_hard_bounded_and_deterministic() -> None:
    terms = [f"term_{index:02d}" for index in range(50)]
    request = build_lexical_search_request(
        reversed(terms),
        include_paths=["core/", "tests/", ".git/", "../outside/"],
        exclude_paths=["build/"],
        max_matches=999,
        max_files=999,
        max_match_length=999,
        max_expansion_rounds=999,
    )

    assert len(request.terms) == MAX_LEXICAL_TERMS
    assert request.terms == tuple(sorted(request.terms, key=lambda value: (value.casefold(), value)))
    assert request.terms_truncation.truncated is True
    assert request.max_matches == MAX_LEXICAL_MATCHES == 200
    assert request.max_files == MAX_LEXICAL_FILES == 40
    assert request.max_match_length == MAX_LEXICAL_MATCH_LENGTH == 240
    assert request.max_expansion_rounds == MAX_EXPANSION_ROUNDS == 2
    assert request.include_paths == ("core/", "tests/")
    assert set(DEFAULT_LEXICAL_EXCLUDE_PATHS) <= set(request.exclude_paths)
    assert "build/" in request.exclude_paths
    assert request.include_paths_truncation.total == 2
    assert request.include_paths_truncation.truncated is False
    assert request.exclude_paths_truncation.truncated is False


def test_lexical_search_path_lists_are_capped_with_metadata() -> None:
    request = build_lexical_search_request(
        ["router"],
        include_paths=(f"src/package_{index:03d}/" for index in range(100)),
        exclude_paths=(f"generated_{index:03d}/" for index in range(100)),
    )

    assert len(request.include_paths) == MAX_LEXICAL_INCLUDE_PATHS
    assert request.include_paths_truncation.as_dict() == {
        "total": 100,
        "returned": MAX_LEXICAL_INCLUDE_PATHS,
        "limit": MAX_LEXICAL_INCLUDE_PATHS,
        "truncated": True,
    }
    assert len(request.exclude_paths) == MAX_LEXICAL_EXCLUDE_PATHS
    assert set(DEFAULT_LEXICAL_EXCLUDE_PATHS) <= set(request.exclude_paths)
    assert request.exclude_paths_truncation.total == (
        len(DEFAULT_LEXICAL_EXCLUDE_PATHS) + 100
    )
    assert request.exclude_paths_truncation.truncated is True


def test_sensitive_include_prefixes_never_enter_lexical_scope() -> None:
    request = build_lexical_search_request(
        ["router"],
        include_paths=["secrets/", "credentials/", ".env", "core/"],
    )

    assert request.include_paths == ("core/",)
    assert request.scope_mode == "explicit_paths"
    assert request.safe_inventory_filter_required is True
    assert request.production_execution_authorized is False


def test_all_sensitive_include_prefixes_create_a_match_none_scope() -> None:
    request = build_lexical_search_request(
        ["router"],
        include_paths=["secrets/", ".env"],
    )
    normalized = consume_lexical_search_results(
        [_match("core/router.py", 1)],
        request=request,
        capabilities=[_capability("core/router.py")],
    )

    assert request.include_paths == ()
    assert request.scope_mode == "match_none"
    assert normalized.matches == ()
    assert normalized.excluded[0].reason == "empty_safe_search_scope"


def test_lexical_term_intake_has_a_defensive_processing_bound() -> None:
    with pytest.raises(ValueError, match="defensive input limit"):
        build_lexical_search_request(
            (f"term_{index}" for index in range(MAX_SUPPLIED_LEXICAL_TERMS + 1))
        )


def test_reference_evidence_intake_has_a_defensive_per_file_bound() -> None:
    capability = _capability("core/router.py")
    report = build_candidate_filename_report([capability], task_terms=["router"])

    with pytest.raises(ValueError, match="defensive input limit"):
        rank_candidates(
            [capability],
            filename_report=report,
            reference_evidence={
                "core/router.py": (
                    {
                        "kind": "direct_symbol_reference",
                        "detail": f"dispatch_{index}",
                    }
                    for index in range(
                        MAX_SUPPLIED_REFERENCE_EVIDENCE_PER_FILE + 1
                    )
                )
            },
        )


def test_sensitive_lexical_result_never_retains_or_renders_its_excerpt() -> None:
    capabilities = [
        _capability(".env"),
        _capability("certs/private.pem"),
        _capability("core/router.py"),
    ]
    request = build_lexical_search_request(["secret"])
    supplied = [
        _match(".env", 1, term="secret", excerpt="VERY_SECRET_ENV_VALUE"),
        _match("certs/private.pem", 1, term="secret", excerpt="VERY_SECRET_PRIVATE_KEY"),
        _match("core/router.py", 2, term="secret", excerpt="safe bounded match"),
    ]

    result = consume_lexical_search_results(
        supplied,
        request=request,
        capabilities=capabilities,
    )
    rendered = repr(result.as_dict())

    assert [item.path for item in result.matches] == ["core/router.py"]
    assert {item.path for item in result.excluded} == {".env", "certs/private.pem"}
    assert all(item.as_dict()["excerpt"] is None for item in result.excluded)
    assert "VERY_SECRET" not in rendered


def test_binary_lexical_result_is_rejected_without_an_excerpt() -> None:
    capability = _capability("assets/logo.png")
    request = build_lexical_search_request(["logo"])

    result = consume_lexical_search_results(
        [_match("assets/logo.png", 1, term="logo", excerpt="binary bytes")],
        request=request,
        capabilities=[capability],
    )

    assert result.matches == ()
    assert result.excluded[0].reason == "security_policy_exclusion"
    assert result.excluded[0].as_dict()["excerpt"] is None


def test_lexical_match_and_file_counts_are_capped_after_deterministic_sorting() -> None:
    capabilities = [_capability(f"src/file_{index:02d}.py") for index in range(45)]
    supplied = [
        _match(capability.path, line)
        for capability in reversed(capabilities)
        for line in range(6, 0, -1)
    ]
    request = build_lexical_search_request(["router"])

    result = consume_lexical_search_results(
        supplied,
        request=request,
        capabilities=capabilities,
    )

    assert len(result.matches) == MAX_LEXICAL_MATCHES
    assert result.matched_file_count <= MAX_LEXICAL_FILES
    assert len({item.path for item in result.matches}) <= MAX_LEXICAL_FILES
    assert result.matches == tuple(
        sorted(
            result.matches,
            key=lambda item: (
                item.path,
                item.line_number,
                item.location or "",
                item.matched_term.casefold(),
                item.result_source,
            ),
        )
    )
    metadata = dict(result.truncation)
    assert metadata["files"].as_dict() == {
        "total": 45,
        "returned": 40,
        "limit": 40,
        "truncated": True,
    }
    assert metadata["matches"].truncated is True


def test_lexical_result_ordering_is_deterministic_nonmutating_and_clips_excerpts() -> None:
    capabilities = [_capability("core/a.py"), _capability("core/b.py")]
    supplied = [
        _match("core/b.py", 3, excerpt="x" * 300),
        _match("core/a.py", 7),
        _match("core/a.py", 2),
    ]
    before = copy.deepcopy(supplied)
    request = build_lexical_search_request(["router"], max_match_length=12)

    first = consume_lexical_search_results(
        supplied,
        request=request,
        capabilities=capabilities,
    )
    second = consume_lexical_search_results(
        reversed(supplied),
        request=request,
        capabilities=reversed(capabilities),
    )

    assert first == second
    assert supplied == before
    assert [(item.path, item.line_number) for item in first.matches] == [
        ("core/a.py", 2),
        ("core/a.py", 7),
        ("core/b.py", 3),
    ]
    assert first.matches[-1].excerpt == "x" * 12
    assert first.matches[-1].truncated is True


@pytest.mark.parametrize(
    ("result", "reason"),
    [
        ({"path": "core/router.py", "matched_term": "router"}, "missing_location"),
        ({"path": "core/router.py", "line_number": 0, "matched_term": "router"}, "invalid_location"),
        ({"path": "../router.py", "line_number": 1, "matched_term": "router"}, "unsafe_path"),
        ({"path": "core/router.py", "line_number": 1, "matched_term": "other"}, "unrequested_term"),
    ],
)
def test_invalid_supplied_lexical_results_fail_closed(result: dict[str, object], reason: str) -> None:
    normalized = consume_lexical_search_results(
        [result],
        request=build_lexical_search_request(["router"]),
        capabilities=[_capability("core/router.py")],
    )

    assert normalized.matches == ()
    assert normalized.excluded[0].reason == reason


@pytest.mark.parametrize(
    "editability",
    ["forbidden", "outside_scope", "opaque", "sensitive_requires_approval"],
)
def test_lexical_results_never_expose_restrictive_editability_excerpts(
    editability: str,
) -> None:
    capability = classify_file_capability("notes.txt", editability=editability)
    normalized = consume_lexical_search_results(
        [
            {
                "path": "notes.txt",
                "line_number": 1,
                "matched_term": "router",
                "excerpt": "must not escape",
            }
        ],
        request=build_lexical_search_request(["router"]),
        capabilities=[capability],
    )

    assert normalized.matches == ()
    assert normalized.excluded[0].reason == "security_policy_exclusion"


def test_incomplete_mapping_read_policy_blocks_lexical_excerpt() -> None:
    normalized = consume_lexical_search_results(
        [
            {
                "path": "notes.txt",
                "line_number": 1,
                "matched_term": "router",
                "excerpt": "must not escape",
            }
        ],
        request=build_lexical_search_request(["router"]),
        capabilities=[
            {
                "path": "notes.txt",
                "read_policy": "explicit_human_approval_required",
            }
        ],
    )

    assert normalized.matches == ()
    assert normalized.excluded[0].reason == "security_policy_exclusion"
