"""ANALYSIS.EVIDENCE.LIVE.1 — role-balanced source evidence acquisition.

The failure this phase answers, measured against the real ``deepseek-harness``
monorepo before any code was written:

    inventory      6,126 indexable files, 2,700 of them TypeScript
    selected       12 files - 11 markdown documents, 1 package.json
    source read    0 files, 0 characters
    budget spent   59,674 of 60,000 characters, all of it on prose

The answer that came back was accurate and shallow, and nothing was
misconfigured: ``.ts`` is a supported extension, the files were in the
inventory, and the route was correct.  Documentation simply reached the reader
first and there was no role that could hold code, so there was nothing to
reserve.

These tests pin the fix and its bounds.  The file cap is still 12, the character
cap is still 60,000, and every assertion below is about *allocation*.
"""

from __future__ import annotations

import builtins
import socket
import time

import pytest

from core.analysis_evidence import (
    MAX_CHARS_PER_FILE,
    MAX_EVIDENCE_FILES,
    MAX_TOTAL_CHARS,
    AnalysisEvidence,
    build_analysis_answer_prompt,
    collect_analysis_evidence,
    select_analysis_paths,
)
from core.analysis_evidence_roles import (
    ANALYSIS_EVIDENCE_PROFILES,
    BALANCED_ROLES,
    EVIDENCE_ROLES,
    PROFILE_ARCHITECTURE_IMPLEMENTATION,
    PROFILE_DEPENDENCY_CONFIGURATION,
    PROFILE_DOCUMENTATION_EXPLANATION,
    PROFILE_GENERAL_ANALYSIS,
    PROFILE_IMPLEMENTATION_DETAIL,
    ROLE_IMPLEMENTATION_SOURCE,
    ROLE_PACKAGE_MANIFEST,
    ROLE_PROJECT_DOCUMENT,
    ROLE_REQUESTED_PATH,
    ROLE_TEST_EXAMPLE,
    candidate_sort_key,
    classify_evidence_role,
    derive_evidence_profile,
    plan_analysis_evidence,
    profile_requires_source,
    subject_tokens,
)
from core.live_task_routing import route_live_task


# ── Prompts, in the shape the live routes actually receive them ───────────────

T5_PROMPT = (
    "Analyze the architecture of this deepseek-harness repository and compare it "
    "against C.A.T.T.U.S at ../C.A.T.T.U.S. Explain how each one is implemented "
    "internally, then recommend ideas C.A.T.T.U.S could adopt."
)
DOC_PROMPT = "Summarize the README and explain what the documentation says."
IMPL_PROMPT = "How does the retrieval module work internally?"
ARCH_PROMPT = "Explain the architecture of this project and how it is implemented."
MANIFEST_PROMPT = "What scripts and dependencies does this package declare?"


def _obligations(prompt: str) -> tuple[str, ...]:
    return route_live_task(prompt, repository_available=True).obligations


def _subjects(prompt: str) -> tuple[str, ...]:
    return route_live_task(prompt, repository_available=True).subjects


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _write(path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _mixed_repo(tmp_path):
    """Docs and source both present, in the proportions that caused the bug."""
    repo = tmp_path / "mixed"
    _write(repo / "README.md", "# Mixed\nAn agent workspace.\n")
    _write(repo / "package.json", '{"name": "mixed", "scripts": {"build": "tsc"}}\n')
    for index in range(40):
        _write(repo / "docs" / f"note-{index:03d}.md", f"# note {index}\n" + "d" * 400)
    for index in range(30):
        _write(
            repo / "packages" / f"pkg{index:02d}" / "src" / "index.ts",
            f"export class Service{index} {{\n  run() {{\n    return {index};\n  }}\n}}\n",
        )
    return repo


def _docs_only_repo(tmp_path):
    repo = tmp_path / "docsonly"
    _write(repo / "README.md", "# Docs only\n")
    for index in range(8):
        _write(repo / "docs" / f"page-{index}.md", "prose\n")
    return repo


def _source_only_repo(tmp_path):
    repo = tmp_path / "srconly"
    _write(repo / "package.json", '{"name": "srconly"}\n')
    for index in range(6):
        _write(repo / "src" / f"mod{index}.ts", f"export function run{index}() {{}}\n")
    return repo


def _tiny_repo(tmp_path):
    """One README and two source files - the small-repository case."""
    repo = tmp_path / "tiny"
    _write(repo / "README.md", "# Tiny\n")
    _write(repo / "app.ts", "export function main() {}\n")
    _write(repo / "helper.ts", "export function help() {}\n")
    return repo


def _paths(evidence: AnalysisEvidence) -> list[str]:
    return [item.path for item in evidence.items]


def _roles(evidence: AnalysisEvidence) -> dict[str, int]:
    return evidence.files_by_role()


# ══════════════════════════════════════════════════════════════════════════════
# 1. Profiles are read off the task, not off the repository
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize(
    "prompt, expected",
    [
        (T5_PROMPT, PROFILE_ARCHITECTURE_IMPLEMENTATION),
        (ARCH_PROMPT, PROFILE_ARCHITECTURE_IMPLEMENTATION),
        (IMPL_PROMPT, PROFILE_IMPLEMENTATION_DETAIL),
        (DOC_PROMPT, PROFILE_DOCUMENTATION_EXPLANATION),
        (MANIFEST_PROMPT, PROFILE_DEPENDENCY_CONFIGURATION),
    ],
)
def test_profile_matrix(prompt, expected):
    assert (
        derive_evidence_profile(
            obligations=_obligations(prompt), subjects=_subjects(prompt)
        )
        == expected
    )


def test_a_request_with_no_task_words_gets_the_general_profile():
    assert derive_evidence_profile() == PROFILE_GENERAL_ANALYSIS
    assert derive_evidence_profile(obligations=(), subjects=("",)) == PROFILE_GENERAL_ANALYSIS


def test_profile_derivation_is_deterministic():
    first = derive_evidence_profile(obligations=_obligations(T5_PROMPT))
    second = derive_evidence_profile(obligations=_obligations(T5_PROMPT))
    assert first == second == PROFILE_ARCHITECTURE_IMPLEMENTATION


def test_only_architecture_and_implementation_profiles_reserve_source():
    reserving = {
        profile for profile in ANALYSIS_EVIDENCE_PROFILES if profile_requires_source(profile)
    }
    assert reserving == {
        PROFILE_ARCHITECTURE_IMPLEMENTATION,
        PROFILE_IMPLEMENTATION_DETAIL,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 2. Role classification
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize(
    "path, expected",
    [
        ("packages/api/src/index.ts", ROLE_IMPLEMENTATION_SOURCE),
        ("apps/web/src/main.tsx", ROLE_IMPLEMENTATION_SOURCE),
        ("core/pipeline.py", ROLE_IMPLEMENTATION_SOURCE),
        ("README.md", ROLE_PROJECT_DOCUMENT),
        ("docs/architecture.md", ROLE_PROJECT_DOCUMENT),
        ("package.json", ROLE_PACKAGE_MANIFEST),
        ("pyproject.toml", ROLE_PACKAGE_MANIFEST),
        ("packages/api/tests/runner.spec.ts", ROLE_TEST_EXAMPLE),
        ("tests/test_pipeline.py", ROLE_TEST_EXAMPLE),
        ("packages/api/src/gateway.test.ts", ROLE_TEST_EXAMPLE),
        ("examples/basic/app.ts", ROLE_TEST_EXAMPLE),
        ("assets/logo.svg", None),
        ("data/fixtures.bin", None),
    ],
)
def test_role_classification_matrix(path, expected):
    assert classify_evidence_role(path) == expected


def test_typescript_is_implementation_source_by_the_canonical_extension_policy():
    assert classify_evidence_role("src/a.ts") == ROLE_IMPLEMENTATION_SOURCE
    assert classify_evidence_role("src/a.tsx") == ROLE_IMPLEMENTATION_SOURCE


def test_a_markdown_file_whose_name_contains_ts_is_not_source():
    """The false positive the brief names explicitly."""
    assert classify_evidence_role("README.ts.md") == ROLE_PROJECT_DOCUMENT
    assert classify_evidence_role("docs/how.ts.works.md") == ROLE_PROJECT_DOCUMENT


def test_every_balanced_role_is_in_the_frozen_vocabulary():
    assert set(BALANCED_ROLES) <= set(EVIDENCE_ROLES)


# ══════════════════════════════════════════════════════════════════════════════
# 3. The primary invariant: docs cannot take the whole budget
# ══════════════════════════════════════════════════════════════════════════════

def test_architecture_question_reaches_source_in_a_documentation_heavy_repository(tmp_path):
    repo = _mixed_repo(tmp_path)
    evidence = collect_analysis_evidence(
        str(repo), obligations=_obligations(ARCH_PROMPT)
    )

    roles = _roles(evidence)
    assert evidence.profile == PROFILE_ARCHITECTURE_IMPLEMENTATION
    assert roles.get(ROLE_IMPLEMENTATION_SOURCE, 0) >= 4, roles
    assert roles.get(ROLE_PROJECT_DOCUMENT, 0) >= 3, roles
    assert evidence.source_backed


def test_the_same_repository_still_starves_source_under_a_document_profile(tmp_path):
    """The starvation was real, not theoretical: it is one profile away.

    Same repository, same caps, same code — only the profile differs.  With no
    source reservation the twelve slots fill with prose and manifests and the
    thirty TypeScript files are never opened, which is exactly what the live T5
    run did before this phase and exactly what it must keep doing for a question
    that asked about documentation.
    """
    repo = _mixed_repo(tmp_path)
    selections = select_analysis_paths(
        [p.relative_to(repo).as_posix() for p in sorted(repo.rglob("*")) if p.is_file()],
        profile=PROFILE_DOCUMENTATION_EXPLANATION,
    )
    roles = [role for _path, role in selections]
    assert len(selections) == MAX_EVIDENCE_FILES
    assert ROLE_IMPLEMENTATION_SOURCE not in roles
    assert roles.count(ROLE_PROJECT_DOCUMENT) >= 10


def test_source_evidence_is_actually_read_not_merely_listed(tmp_path):
    repo = _mixed_repo(tmp_path)
    evidence = collect_analysis_evidence(
        str(repo), obligations=_obligations(ARCH_PROMPT)
    )
    source = [
        item for item in evidence.items if item.role == ROLE_IMPLEMENTATION_SOURCE
    ]
    assert source
    assert all(item.text.strip() for item in source)
    assert any("export class Service" in item.text for item in source)
    assert evidence.chars_by_role()[ROLE_IMPLEMENTATION_SOURCE] > 0


def test_implementation_question_reserves_source(tmp_path):
    repo = _mixed_repo(tmp_path)
    evidence = collect_analysis_evidence(
        str(repo), obligations=_obligations(IMPL_PROMPT)
    )
    assert evidence.profile == PROFILE_IMPLEMENTATION_DETAIL
    assert _roles(evidence).get(ROLE_IMPLEMENTATION_SOURCE, 0) >= 5


# ══════════════════════════════════════════════════════════════════════════════
# 4. ... and the converse: a documentation question stays documentation-centric
# ══════════════════════════════════════════════════════════════════════════════

def test_documentation_question_is_not_forced_to_read_source(tmp_path):
    repo = _mixed_repo(tmp_path)
    evidence = collect_analysis_evidence(
        str(repo), obligations=_obligations(DOC_PROMPT)
    )
    roles = _roles(evidence)
    assert evidence.profile == PROFILE_DOCUMENTATION_EXPLANATION
    assert roles.get(ROLE_PROJECT_DOCUMENT, 0) >= 4
    assert roles.get(ROLE_IMPLEMENTATION_SOURCE, 0) == 0, roles
    assert not evidence.unmet_role_requirements


def test_manifest_question_centres_manifests_without_a_source_reservation(tmp_path):
    repo = tmp_path / "manifests"
    _write(repo / "README.md", "# m\n")
    _write(repo / "package.json", '{"scripts": {"build": "tsc"}}\n')
    _write(repo / "pyproject.toml", "[project]\nname='m'\n")
    _write(repo / "requirements.txt", "requests\n")
    for index in range(10):
        _write(repo / "src" / f"m{index}.ts", "export const x = 1;\n")

    evidence = collect_analysis_evidence(
        str(repo), obligations=_obligations(MANIFEST_PROMPT)
    )
    roles = _roles(evidence)
    assert evidence.profile == PROFILE_DEPENDENCY_CONFIGURATION
    assert roles.get(ROLE_PACKAGE_MANIFEST, 0) >= 3
    assert not profile_requires_source(evidence.profile)


# ══════════════════════════════════════════════════════════════════════════════
# 5. Conditional minimums — never manufacture evidence
# ══════════════════════════════════════════════════════════════════════════════

def test_no_source_available_means_no_unmet_requirement_is_invented(tmp_path):
    repo = _docs_only_repo(tmp_path)
    evidence = collect_analysis_evidence(
        str(repo), obligations=_obligations(ARCH_PROMPT)
    )
    assert _roles(evidence).get(ROLE_IMPLEMENTATION_SOURCE, 0) == 0
    assert evidence.unmet_role_requirements == ()
    assert any("no supported implementation source" in gap.lower() for gap in evidence.gaps)


def test_no_documentation_available_still_yields_source_only_analysis(tmp_path):
    repo = _source_only_repo(tmp_path)
    evidence = collect_analysis_evidence(
        str(repo), obligations=_obligations(ARCH_PROMPT)
    )
    roles = _roles(evidence)
    assert roles.get(ROLE_IMPLEMENTATION_SOURCE, 0) >= 4
    assert roles.get(ROLE_PROJECT_DOCUMENT, 0) == 0
    assert evidence.unmet_role_requirements == ()


def test_a_small_repository_is_not_over_engineered(tmp_path):
    repo = _tiny_repo(tmp_path)
    evidence = collect_analysis_evidence(
        str(repo), obligations=_obligations(ARCH_PROMPT)
    )
    assert sorted(_paths(evidence)) == ["README.md", "app.ts", "helper.ts"]
    assert evidence.unmet_role_requirements == ()


# ══════════════════════════════════════════════════════════════════════════════
# 6. Exact requested paths remain strongest
# ══════════════════════════════════════════════════════════════════════════════

def test_an_exactly_requested_path_is_first_and_survives_every_quota(tmp_path):
    repo = _mixed_repo(tmp_path)
    evidence = collect_analysis_evidence(
        str(repo),
        requested_paths=["docs/note-037.md"],
        obligations=_obligations(ARCH_PROMPT),
    )
    assert evidence.items[0].path == "docs/note-037.md"
    assert evidence.items[0].role == ROLE_REQUESTED_PATH
    assert _roles(evidence).get(ROLE_IMPLEMENTATION_SOURCE, 0) >= 4


def test_several_requested_paths_keep_the_order_the_user_wrote(tmp_path):
    repo = _mixed_repo(tmp_path)
    evidence = collect_analysis_evidence(
        str(repo),
        requested_paths=["packages/pkg07/src/index.ts", "README.md"],
        obligations=_obligations(ARCH_PROMPT),
    )
    assert _paths(evidence)[:2] == ["packages/pkg07/src/index.ts", "README.md"]
    assert [item.role for item in evidence.items[:2]] == [
        ROLE_REQUESTED_PATH,
        ROLE_REQUESTED_PATH,
    ]


def test_a_requested_path_is_never_counted_against_a_role_reservation(tmp_path):
    repo = _mixed_repo(tmp_path)
    evidence = collect_analysis_evidence(
        str(repo),
        requested_paths=["packages/pkg01/src/index.ts"],
        obligations=_obligations(ARCH_PROMPT),
    )
    roles = _roles(evidence)
    assert roles[ROLE_REQUESTED_PATH] == 1
    assert roles.get(ROLE_IMPLEMENTATION_SOURCE, 0) >= 4


# ══════════════════════════════════════════════════════════════════════════════
# 7. Nothing crowds out primary implementation source
# ══════════════════════════════════════════════════════════════════════════════

def test_tests_and_examples_do_not_fill_the_implementation_reservation(tmp_path):
    repo = tmp_path / "testheavy"
    _write(repo / "README.md", "# t\n")
    for index in range(40):
        _write(repo / "tests" / f"a{index:02d}.spec.ts", "describe('x', () => {});\n")
        _write(repo / "examples" / f"e{index:02d}.ts", "export const demo = 1;\n")
    for index in range(6):
        _write(repo / "src" / f"real{index}.ts", "export class Real {}\n")

    evidence = collect_analysis_evidence(
        str(repo), obligations=_obligations(ARCH_PROMPT)
    )
    source = [i.path for i in evidence.items if i.role == ROLE_IMPLEMENTATION_SOURCE]
    assert len(source) >= 4
    assert all(path.startswith("src/") for path in source), source


def test_generated_and_vendored_source_does_not_displace_primary_source(tmp_path):
    repo = tmp_path / "generated"
    _write(repo / "README.md", "# g\n")
    for index in range(40):
        _write(repo / "packages" / "a" / "dist" / f"b{index:02d}.ts", "export const g = 1;\n")
        _write(
            repo / "packages" / "a" / "node_modules" / "dep" / f"v{index:02d}.ts",
            "export const v = 1;\n",
        )
    for index in range(5):
        _write(repo / "packages" / "a" / "src" / f"p{index}.ts", "export class P {}\n")

    evidence = collect_analysis_evidence(
        str(repo), obligations=_obligations(ARCH_PROMPT)
    )
    source = [i.path for i in evidence.items if i.role == ROLE_IMPLEMENTATION_SOURCE]
    assert len(source) >= 4
    assert all("/src/" in path for path in source), source


def test_a_manifest_does_not_consume_the_source_reservation(tmp_path):
    repo = tmp_path / "manyманifests"
    _write(repo / "README.md", "# m\n")
    for index in range(12):
        _write(repo / "packages" / f"p{index:02d}" / "package.json", '{"name": "p"}\n')
    for index in range(6):
        _write(repo / "packages" / f"p{index:02d}" / "src" / "index.ts", "export class Q {}\n")

    evidence = collect_analysis_evidence(
        str(repo), obligations=_obligations(ARCH_PROMPT)
    )
    roles = _roles(evidence)
    # Twelve manifests are available and only six source files; the source
    # reservation is still met, and source is interleaved early enough to be
    # read rather than parked behind every manifest.
    assert roles.get(ROLE_IMPLEMENTATION_SOURCE, 0) >= 4, roles
    reading_order = [item.role for item in evidence.items]
    assert ROLE_IMPLEMENTATION_SOURCE in reading_order[:3], reading_order


# ══════════════════════════════════════════════════════════════════════════════
# 8. Bounds are unchanged
# ══════════════════════════════════════════════════════════════════════════════

def test_the_global_caps_did_not_move():
    assert MAX_EVIDENCE_FILES == 12
    assert MAX_TOTAL_CHARS == 60_000
    assert MAX_CHARS_PER_FILE == 6_000


def test_role_balance_operates_under_the_same_file_and_character_caps(tmp_path):
    repo = _mixed_repo(tmp_path)
    evidence = collect_analysis_evidence(
        str(repo), obligations=_obligations(ARCH_PROMPT)
    )
    assert len(evidence.items) <= MAX_EVIDENCE_FILES
    assert sum(len(item.text) for item in evidence.items) <= MAX_TOTAL_CHARS
    assert all(len(item.text) <= MAX_CHARS_PER_FILE for item in evidence.items)


def test_one_huge_source_file_cannot_take_the_whole_source_allowance(tmp_path):
    repo = tmp_path / "huge"
    _write(repo / "README.md", "# h\n")
    _write(repo / "package.json", "{}\n")
    _write(repo / "src" / "giant.ts", "export const big = 1;\n" + "y" * 5_000_000)
    for index in range(5):
        _write(repo / "src" / f"small{index}.ts", "export class S {}\n")

    evidence = collect_analysis_evidence(
        str(repo), obligations=_obligations(ARCH_PROMPT)
    )
    giant = [i for i in evidence.items if i.path == "src/giant.ts"]
    assert giant and giant[0].truncated
    assert len(giant[0].text) == MAX_CHARS_PER_FILE
    assert _roles(evidence).get(ROLE_IMPLEMENTATION_SOURCE, 0) >= 4


def test_reserved_roles_are_interleaved_so_each_survives_the_character_budget(tmp_path):
    """The reservation is only real if it is read, not merely selected."""
    repo = tmp_path / "fat"
    for index in range(10):
        _write(repo / "docs" / f"d{index:02d}.md", "m" * 20_000)
    for index in range(10):
        _write(repo / "src" / f"s{index:02d}.ts", "export class Big {}\n" + "s" * 20_000)

    evidence = collect_analysis_evidence(
        str(repo), obligations=_obligations(ARCH_PROMPT)
    )
    chars = evidence.chars_by_role()
    assert chars.get(ROLE_IMPLEMENTATION_SOURCE, 0) > 0
    assert chars.get(ROLE_PROJECT_DOCUMENT, 0) > 0
    assert sum(chars.values()) <= MAX_TOTAL_CHARS


# ══════════════════════════════════════════════════════════════════════════════
# 9. Determinism, inventory reuse, no traversal
# ══════════════════════════════════════════════════════════════════════════════

def test_selection_is_deterministic_over_the_same_inventory():
    paths = [
        "README.md", "package.json", "docs/a.md", "docs/b.md",
        "src/index.ts", "src/util.ts", "tests/util.spec.ts",
    ]
    runs = [
        select_analysis_paths(
            paths, subjects=["util"], profile=PROFILE_ARCHITECTURE_IMPLEMENTATION
        )
        for _ in range(5)
    ]
    assert all(run == runs[0] for run in runs)


def test_ordering_does_not_depend_on_the_order_the_inventory_arrives_in():
    paths = ["src/b.ts", "README.md", "src/a.ts", "package.json", "docs/x.md"]
    forward = select_analysis_paths(paths, profile=PROFILE_ARCHITECTURE_IMPLEMENTATION)
    backward = select_analysis_paths(
        list(reversed(paths)), profile=PROFILE_ARCHITECTURE_IMPLEMENTATION
    )
    assert sorted(forward) == sorted(backward)


def test_the_supplied_inventory_is_reused_and_no_walk_is_added(tmp_path, monkeypatch):
    repo = _mixed_repo(tmp_path)

    class _Entry:
        def __init__(self, relative):
            from pathlib import Path as _Path

            self.relative_path = _Path(relative)

    class _Inventory:
        indexable_entries = tuple(
            _Entry(p)
            for p in ("README.md", "package.json", "packages/pkg00/src/index.ts")
        )

    def _refuse_walk(*args, **kwargs):  # pragma: no cover - the point is not calling it
        raise AssertionError("analysis evidence must not walk the repository")

    import os as _os

    monkeypatch.setattr(_os, "walk", _refuse_walk)
    evidence = collect_analysis_evidence(
        str(repo), inventory=_Inventory(), obligations=_obligations(ARCH_PROMPT)
    )
    assert sorted(_paths(evidence)) == [
        "README.md",
        "package.json",
        "packages/pkg00/src/index.ts",
    ]


def test_planning_reads_no_files_and_opens_nothing(monkeypatch):
    def _refuse_open(*args, **kwargs):  # pragma: no cover
        raise AssertionError("selection must not open a file")

    monkeypatch.setattr(builtins, "open", _refuse_open)
    plan = plan_analysis_evidence(
        ["README.md", "src/index.ts", "package.json"],
        profile=PROFILE_ARCHITECTURE_IMPLEMENTATION,
    )
    assert plan.selections


def test_selection_makes_no_network_call(monkeypatch):
    def _refuse(*args, **kwargs):  # pragma: no cover
        raise AssertionError("analysis evidence selection must not use the network")

    monkeypatch.setattr(socket, "socket", _refuse)
    monkeypatch.setattr(socket, "create_connection", _refuse)
    assert plan_analysis_evidence(["README.md"], profile=PROFILE_GENERAL_ANALYSIS).selections


def test_subject_tokens_are_bounded_and_word_shaped():
    tokens = subject_tokens(
        ["architecture of this deepseek-harness repository and compare it"]
    )
    assert "architecture" in tokens
    assert "deepseek" in tokens
    assert "repository" not in tokens  # a stop word, not a path signal
    assert len(tokens) <= 12


def test_obligation_words_reach_the_source_the_question_is_about():
    """The measured miss: the question named the package and nothing used it.

    On the live T5 request the preserved subjects are only
    ("deepseek", "harness"), which reaches UI dialogs and API plumbing.  The
    words that say what the question is *about* -- agent loop, extension model --
    live in the obligations, and until they were used the acquired source was
    real source about the wrong thing.
    """
    paths = [
        "README.md",
        "package.json",
        "packages/client/ui-settings/src/DeepSeekModelsEditor.tsx",
        "packages/client/ui-settings/src/DeepSeekOnboardingDialog.tsx",
        "packages/api/gateway/src/index.ts",
        "packages/core/agent-loop/src/agent.ts",
        "packages/core/agent-loop/src/index.ts",
    ]
    subjects = ["this repository (deepseek-harness", "DeepSeek AI"]
    obligations = [
        "Focus on how each one structures its agent loop and extension model"
    ]

    without = [
        path
        for path, role in select_analysis_paths(
            paths, subjects=subjects, profile=PROFILE_ARCHITECTURE_IMPLEMENTATION
        )
        if role == ROLE_IMPLEMENTATION_SOURCE
    ]
    with_obligations = [
        path
        for path, role in select_analysis_paths(
            paths,
            subjects=subjects,
            obligations=obligations,
            profile=PROFILE_ARCHITECTURE_IMPLEMENTATION,
        )
        if role == ROLE_IMPLEMENTATION_SOURCE
    ]

    assert without[0].startswith("packages/client/ui-settings/"), without
    assert with_obligations[0].startswith("packages/core/agent-loop/"), with_obligations
    assert subject_tokens(subjects + obligations)[:2] == ("deepseek", "harness")


def test_build_configuration_does_not_outrank_the_module_it_configures():
    tokens = subject_tokens(["agent loop"])
    config = candidate_sort_key(
        "packages/core/agent-loop/tsdown.config.ts", ROLE_IMPLEMENTATION_SOURCE, tokens
    )
    module = candidate_sort_key(
        "packages/core/agent-loop/src/agent.ts", ROLE_IMPLEMENTATION_SOURCE, tokens
    )
    assert module < config


def test_archived_material_is_demoted_beneath_current_material():
    tokens = subject_tokens(["architecture"])
    archived = candidate_sort_key(
        "notes/archived/architecture/old.md", ROLE_PROJECT_DOCUMENT, tokens
    )
    current = candidate_sort_key("docs/architecture.md", ROLE_PROJECT_DOCUMENT, tokens)
    assert current < archived


def test_files_read_block_groups_the_prompt_by_role(tmp_path):
    repo = _mixed_repo(tmp_path)
    prompt = build_analysis_answer_prompt(
        user_query=ARCH_PROMPT,
        evidence=collect_analysis_evidence(
            str(repo), obligations=_obligations(ARCH_PROMPT)
        ),
        repo_path=str(repo),
    )
    block = prompt.split("[FILES READ]")[1].split("[EVIDENCE GAPS]")[0]
    assert f"{ROLE_IMPLEMENTATION_SOURCE} (" in block
    assert f"{ROLE_PROJECT_DOCUMENT} (" in block
    assert "README.md" in block


def test_candidate_ordering_never_depends_on_hashing():
    tokens = ("session",)
    keys = [
        candidate_sort_key(path, ROLE_IMPLEMENTATION_SOURCE, tokens)
        for path in ("src/session.ts", "src/other.ts", "dist/session.ts")
    ]
    # subject match beats no match; generated output loses to both.
    assert keys[0] < keys[1] < keys[2]
    assert keys == [
        candidate_sort_key(path, ROLE_IMPLEMENTATION_SOURCE, tokens)
        for path in ("src/session.ts", "src/other.ts", "dist/session.ts")
    ]


# ══════════════════════════════════════════════════════════════════════════════
# 10. The receipt
# ══════════════════════════════════════════════════════════════════════════════

def test_role_coverage_receipt_reports_allocation_without_confidence(tmp_path):
    repo = _mixed_repo(tmp_path)
    payload = collect_analysis_evidence(
        str(repo), obligations=_obligations(ARCH_PROMPT)
    ).as_dict()

    assert payload["evidence_profile"] == PROFILE_ARCHITECTURE_IMPLEMENTATION
    assert ROLE_IMPLEMENTATION_SOURCE in payload["available_roles"]
    assert payload["selected_files_by_role"][ROLE_IMPLEMENTATION_SOURCE] >= 4
    assert payload["selected_chars_by_role"][ROLE_IMPLEMENTATION_SOURCE] > 0
    assert payload["role_coverage"][ROLE_IMPLEMENTATION_SOURCE]["available"] == 30
    assert payload["role_coverage"][ROLE_IMPLEMENTATION_SOURCE]["required"] == 4
    assert payload["unmet_role_requirements"] == []
    assert payload["selection_reason"].startswith("profile=")
    assert payload["source_backed"] is True

    serialized = repr(payload).lower()
    assert "confidence" not in serialized
    assert "probability" not in serialized
    assert "export class service" not in serialized  # no source dumps


def test_the_receipt_grants_no_authority(tmp_path):
    payload = collect_analysis_evidence(
        str(_mixed_repo(tmp_path)), obligations=_obligations(ARCH_PROMPT)
    ).as_dict()
    forbidden = (
        "write_authority",
        "patch_application_authority",
        "defect_established",
        "patch_candidate",
        "patch_plan",
    )
    assert not any(key in payload for key in forbidden)


# ══════════════════════════════════════════════════════════════════════════════
# 11. Honesty when source could not be reached
# ══════════════════════════════════════════════════════════════════════════════

def test_a_documentation_only_architecture_answer_declares_the_limitation(tmp_path):
    repo = _docs_only_repo(tmp_path)
    evidence = collect_analysis_evidence(
        str(repo), obligations=_obligations(ARCH_PROMPT)
    )
    prompt = build_analysis_answer_prompt(
        user_query=ARCH_PROMPT, evidence=evidence, repo_path=str(repo)
    )
    assert "implementation source" in prompt.lower()
    assert "documentation alone" in prompt.lower()


def test_the_answer_prompt_separates_documentation_from_implementation_proof(tmp_path):
    repo = _mixed_repo(tmp_path)
    prompt = build_analysis_answer_prompt(
        user_query=ARCH_PROMPT,
        evidence=collect_analysis_evidence(
            str(repo), obligations=_obligations(ARCH_PROMPT)
        ),
        repo_path=str(repo),
    )
    lowered = prompt.lower()
    assert "documentation describes intent" in lowered
    assert "source files show implementation" in lowered
    # still a read-only answer prompt
    assert "do not emit json, a patch, a diff" in lowered


def test_source_evidence_appears_in_the_rendered_prompt_block(tmp_path):
    repo = _mixed_repo(tmp_path)
    prompt = build_analysis_answer_prompt(
        user_query=ARCH_PROMPT,
        evidence=collect_analysis_evidence(
            str(repo), obligations=_obligations(ARCH_PROMPT)
        ),
        repo_path=str(repo),
    )
    assert f"role={ROLE_IMPLEMENTATION_SOURCE}" in prompt
    assert "export class Service" in prompt


# ══════════════════════════════════════════════════════════════════════════════
# 12. Compatibility with the frozen prerequisites
# ══════════════════════════════════════════════════════════════════════════════

def test_the_route_for_the_t5_request_is_unchanged():
    route = route_live_task(T5_PROMPT, repository_available=True)
    assert route.task_shape == "analysis_only"
    assert route.selected_workflow == "analysis_answer"
    assert route.patch_localization_allowed is False
    assert route.write_authority is False
    assert route.patch_application_authority is False


def test_acquired_typescript_symbols_can_ground_an_answer(tmp_path):
    """ANSWER.GROUND.LIVE.1/.2 reads the excerpts this phase acquires."""
    from core.repository_symbol_membership import declared_symbols

    repo = _mixed_repo(tmp_path)
    evidence = collect_analysis_evidence(
        str(repo), obligations=_obligations(ARCH_PROMPT)
    )
    names = {
        name
        for item in evidence.items
        if item.role == ROLE_IMPLEMENTATION_SOURCE
        for _owner, name in declared_symbols(item.text)
    }
    assert any(name.startswith("Service") for name in names), sorted(names)


def test_multi_root_access_is_still_refused(tmp_path):
    repo = _mixed_repo(tmp_path)
    (tmp_path / "C.A.T.T.U.S").mkdir()
    (tmp_path / "C.A.T.T.U.S" / "README.md").write_text("secret", encoding="utf-8")

    evidence = collect_analysis_evidence(
        str(repo),
        requested_paths=["../C.A.T.T.U.S/README.md", "/etc/passwd"],
        obligations=_obligations(T5_PROMPT),
    )
    assert all(not item.path.startswith("..") for item in evidence.items)
    assert all("C.A.T.T.U.S" not in item.path for item in evidence.items)
    assert all("secret" not in item.text for item in evidence.items)


# ══════════════════════════════════════════════════════════════════════════════
# 13. Cost
# ══════════════════════════════════════════════════════════════════════════════

def test_role_balanced_selection_over_a_large_inventory_is_cheap():
    paths = (
        ["README.md", "package.json"]
        + [f"docs/note-{i:04d}.md" for i in range(2_000)]
        + [f"packages/p{i // 100:02d}/src/f{i:04d}.ts" for i in range(2_000)]
    )
    started = time.perf_counter()
    for _ in range(5):
        plan_analysis_evidence(
            paths,
            subjects=["architecture", "gateway"],
            profile=PROFILE_ARCHITECTURE_IMPLEMENTATION,
        )
    elapsed = (time.perf_counter() - started) / 5
    assert elapsed < 0.5, f"role-balanced selection took {elapsed * 1000:.1f} ms"
