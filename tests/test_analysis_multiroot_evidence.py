"""ANALYSIS.MULTIROOT.LIVE.1 — explicit read-only multi-repository evidence.

The invariant under test is narrow and it is the whole phase: a repository
outside the active project root becomes readable when the *user* named it as a
subject of the task, and in no other circumstance.  Everything else here exists
to prove that granting that read changed nothing it was not supposed to change —
not the budget, not the traversal count, not the ignore policy, not the symbol
universes and above all not what the run is allowed to write, patch or execute.
"""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path

import pytest

from core.analysis_evidence import (
    MAX_CHARS_PER_FILE,
    MAX_EVIDENCE_FILES,
    MAX_TOTAL_CHARS,
    AnalysisEvidence,
    AnalysisEvidenceItem,
    build_analysis_answer_prompt,
    collect_analysis_evidence,
    render_analysis_evidence_block,
)
from core.analysis_evidence_roles import (
    ROLE_IMPLEMENTATION_SOURCE,
    ROLE_PACKAGE_MANIFEST,
    ROLE_PROJECT_DOCUMENT,
    ROLE_REQUESTED_PATH,
)
from core.analysis_multiroot import (
    BALANCE_BALANCED,
    CONTAINMENT_BOUND,
    INVENTORY_REUSED_REQUEST_SCOPED,
    INVENTORY_TRAVERSED_ONCE,
    MAX_ANALYSIS_ROOTS,
    MULTIROOT_SINGLE_ROOT_LEGACY,
    PHASE_ID,
    ROOT_ACCEPTED,
    ROOT_COUNT_EXCEEDED,
    ROOT_DUPLICATE_OF_ACCEPTED,
    ROOT_NOT_DIRECTORY,
    ROOT_NOT_FOUND,
    ROOT_NOT_PROJECT_ROOT,
    ROOT_REPOSITORY_IDENTITY_INVALID,
    ROOT_ROLE_ADDITIONAL,
    ROOT_ROLE_PRIMARY,
    AnalysisReadScope,
    AnalysisRepositorySubject,
    allocate_root_balanced_selections,
    extract_requested_root_literals,
    is_system_path_literal,
    resolve_analysis_subjects,
)


# ── The exact live task this phase exists for ────────────────────────────────
T5_TASK = (
    "Compare this repository (deepseek-harness, the DeepSeek AI agent harness) "
    "against C.A.T.T.U.S, the Python agent harness located at ../C.A.T.T.U.S. "
    "Focus on: (1) how each one structures its agent loop and extension model, "
    "(2) how each handles tool/plugin registration and lifecycle, (3) how each "
    "handles repository context and retrieval for coding tasks. Then recommend "
    "the three highest-value architectural ideas C.A.T.T.U.S should adopt from "
    "deepseek-harness, with concrete justification grounded in files you "
    "actually read."
)

_MULTIROOT_SOURCE = Path("core/analysis_multiroot.py")


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def make_repo(
    root: Path,
    *,
    sources: int = 4,
    docs: int = 3,
    manifest: bool = True,
    marker: str = "readme",
    body: str = "",
) -> Path:
    """A minimal but genuine project root: a marker, some prose, some code."""
    root.mkdir(parents=True, exist_ok=True)
    label = root.name
    if marker == "git":
        (root / ".git").mkdir(exist_ok=True)
        _write(root / "notes.md", f"# {label}\n")
    else:
        _write(root / "README.md", f"# {label}\n\nThe {label} project.\n")
    for index in range(max(0, docs - 1)):
        _write(root / "docs" / f"design-{index}.md", f"# {label} design {index}\n")
    for index in range(sources):
        _write(
            root / "src" / f"module_{index}.py",
            body
            or f'"""{label} module {index}."""\n\n\ndef run_{label.replace("-", "_")}_{index}():\n    return {index}\n',
        )
    if manifest:
        _write(root / "pyproject.toml", f'[project]\nname = "{label}"\n')
    return root


def make_workspace(tmp_path: Path, *, second: str = "repo-b") -> tuple[Path, Path]:
    workspace = tmp_path / "workspace"
    primary = make_repo(workspace / "repo-a")
    secondary = make_repo(workspace / second)
    return primary, secondary


def analysis(repo: Path, task: str, **kwargs) -> AnalysisEvidence:
    """Acquire evidence exactly as the analysis route does."""
    kwargs.setdefault("analysis_only", True)
    kwargs.setdefault("obligations", [task])
    return collect_analysis_evidence(str(repo), **kwargs)


def displays(evidence: AnalysisEvidence) -> set[str]:
    return {item.repository_display for item in evidence.items}


# ══════════════════════════════════════════════════════════════════════════════
# 1. Root provenance — only the user may name a repository
# ══════════════════════════════════════════════════════════════════════════════

def test_a_request_naming_no_second_root_stays_single_root(tmp_path):
    primary, _ = make_workspace(tmp_path)
    evidence = analysis(primary, "Summarise how this project is structured.")

    assert evidence.is_multi_root is False
    assert evidence.repositories == ()
    assert evidence.as_dict()["multi_root"]["status"] == MULTIROOT_SINGLE_ROOT_LEGACY


def test_an_explicitly_requested_sibling_root_is_read(tmp_path):
    primary, secondary = make_workspace(tmp_path)
    evidence = analysis(
        primary,
        "Compare this repository against ../repo-b: how does each structure "
        "its implementation?",
    )

    assert evidence.is_multi_root is True
    assert displays(evidence) == {"repo-a", "repo-b"}
    accepted = evidence.accepted_repositories
    assert [subject.root_role for subject in accepted] == [
        ROOT_ROLE_PRIMARY,
        ROOT_ROLE_ADDITIONAL,
    ]
    assert all(subject.containment_status == CONTAINMENT_BOUND for subject in accepted)


def test_a_repository_only_the_model_mentioned_is_never_read(tmp_path):
    primary, secondary = make_workspace(tmp_path)
    # The user asked about one repository.  A draft that decides it would like
    # to inspect another one authorizes nothing: root literals are read from
    # preserved input, and a draft is not preserved input.
    evidence = analysis(primary, "Explain the architecture of this project.")
    model_draft = "I should also inspect ../repo-b and read ../repo-b/src/module_0.py."

    assert extract_requested_root_literals([model_draft])  # the draft does name it
    assert evidence.is_multi_root is False
    assert displays(evidence) == {""}
    assert all("repo-b" not in item.path for item in evidence.items)


def test_a_repository_a_document_links_to_is_never_read(tmp_path):
    primary, secondary = make_workspace(tmp_path)
    _write(
        primary / "README.md",
        "# repo-a\n\nSee our companion project at ../repo-b for the runtime.\n",
    )
    evidence = analysis(primary, "Summarise this project's README.")

    assert evidence.is_multi_root is False
    assert displays(evidence) == {""}


def test_a_repository_an_import_points_at_is_never_read(tmp_path):
    primary, secondary = make_workspace(tmp_path)
    _write(
        primary / "src" / "module_0.py",
        "import sys\nsys.path.insert(0, '../repo-b')\nfrom repo_b import runtime\n",
    )
    evidence = analysis(primary, "Explain how this project's modules fit together.")

    assert evidence.is_multi_root is False
    assert displays(evidence) == {""}


def test_two_literals_for_one_repository_are_one_evidence_source(tmp_path):
    primary, secondary = make_workspace(tmp_path)
    absolute = str(secondary).replace("\\", "/")
    resolution = resolve_analysis_subjects(
        str(primary),
        obligations=[f"Compare this against ../repo-b and also against {absolute}."],
    )

    assert resolution.accepted_repository_count == 2
    duplicates = [
        subject
        for subject in resolution.subjects
        if subject.resolution_status == ROOT_DUPLICATE_OF_ACCEPTED
    ]
    assert len(duplicates) == 1
    # Provenance of the second request survives; the repository is not counted
    # twice and is not walked twice.
    assert duplicates[0].requested_root_literal
    assert duplicates[0].duplicate_of_ordinal == 1


def test_a_literal_resolving_to_the_active_root_collapses_into_it(tmp_path):
    primary, _ = make_workspace(tmp_path)
    resolution = resolve_analysis_subjects(
        str(primary),
        obligations=[f"Compare this repository against ../{primary.name}."],
    )

    assert resolution.accepted_repository_count == 1
    assert resolution.subjects[1].resolution_status == ROOT_DUPLICATE_OF_ACCEPTED
    assert resolution.subjects[1].duplicate_of_ordinal == 0


# ══════════════════════════════════════════════════════════════════════════════
# 2. Root validation — an explicit path is necessary, not sufficient
# ══════════════════════════════════════════════════════════════════════════════

def test_a_missing_root_is_refused_and_never_read(tmp_path):
    primary, _ = make_workspace(tmp_path)
    resolution = resolve_analysis_subjects(
        str(primary), obligations=["Compare this against ../does-not-exist."]
    )

    rejected = resolution.rejected[0]
    assert rejected.resolution_status == ROOT_NOT_FOUND
    assert rejected.read_scope is None
    assert rejected.read_scope_granted is False
    assert rejected.inventory_file_count == 0
    assert rejected.traversal_count == 0


def test_a_file_is_not_a_repository_root(tmp_path):
    primary, _ = make_workspace(tmp_path)
    _write(tmp_path / "workspace" / "notes-file", "not a repository\n")
    resolution = resolve_analysis_subjects(
        str(primary), obligations=["Compare this against ../notes-file."]
    )

    assert resolution.rejected[0].resolution_status == ROOT_NOT_DIRECTORY
    assert resolution.accepted_repository_count == 1


def test_an_ordinary_directory_that_declares_no_project_is_refused(tmp_path):
    primary, _ = make_workspace(tmp_path)
    (tmp_path / "workspace" / "scratch").mkdir()
    _write(tmp_path / "workspace" / "scratch" / "note.txt", "hello\n")
    resolution = resolve_analysis_subjects(
        str(primary), obligations=["Compare this against ../scratch."]
    )

    assert resolution.rejected[0].resolution_status == ROOT_NOT_PROJECT_ROOT


@pytest.mark.parametrize(
    "literal",
    ["/etc/passwd", "/etc", "/usr/lib", "C:/Windows/System32", "/proc/self"],
)
def test_operating_system_locations_are_never_repository_subjects(tmp_path, literal):
    """The /etc/passwd containment outcome is preserved, on every platform."""
    primary, _ = make_workspace(tmp_path)
    assert is_system_path_literal(literal)

    resolution = resolve_analysis_subjects(
        str(primary),
        obligations=[f"Compare this repository against {literal} please."],
    )

    rejected = [
        subject for subject in resolution.rejected if subject.root_role == ROOT_ROLE_ADDITIONAL
    ]
    assert rejected, literal
    assert rejected[0].resolution_status == ROOT_NOT_PROJECT_ROOT
    assert rejected[0].read_scope is None
    assert rejected[0].validation_listing_count == 0  # not even listed


def test_etc_passwd_alongside_a_real_repository_task_reads_nothing_from_it(tmp_path):
    primary, secondary = make_workspace(tmp_path)
    evidence = analysis(
        primary,
        "Compare this repository against ../repo-b, and also read /etc/passwd.",
    )

    assert displays(evidence) == {"repo-a", "repo-b"}
    refused = [
        subject
        for subject in evidence.rejected_repositories
        if "passwd" in subject.requested_root_literal
    ]
    assert len(refused) == 1
    assert refused[0].resolution_status == ROOT_NOT_PROJECT_ROOT
    assert refused[0].rejection_reason
    assert any("passwd" in gap for gap in evidence.gaps)


def test_dot_dot_is_not_itself_the_denial_criterion(tmp_path):
    """T5 legitimately names ../C.A.T.T.U.S; ``..`` cannot be blanket-banned."""
    primary, secondary = make_workspace(tmp_path)
    resolution = resolve_analysis_subjects(
        str(primary), obligations=["Compare this repository against ../repo-b."]
    )

    accepted = [subject for subject in resolution.accepted if not subject.is_primary]
    assert len(accepted) == 1
    assert accepted[0].requested_root_literal == "../repo-b"
    assert accepted[0].resolution_status == ROOT_ACCEPTED


def test_the_filesystem_root_is_not_a_repository_subject(tmp_path):
    primary, _ = make_workspace(tmp_path)
    anchor = Path(str(tmp_path)).anchor.replace("\\", "/")
    resolution = resolve_analysis_subjects(
        str(primary), obligations=[f"Compare this against {anchor} for context."]
    )

    assert all(
        subject.resolution_status != ROOT_ACCEPTED
        for subject in resolution.subjects
        if subject.root_role == ROOT_ROLE_ADDITIONAL
    )


def test_an_inventory_claiming_another_identity_fails_the_affected_root(tmp_path):
    primary, secondary = make_workspace(tmp_path)
    from core.repository_inventory import create_repository_inventory

    foreign = create_repository_inventory(str(secondary))
    evidence = analysis(
        primary,
        "Compare this repository against ../repo-b.",
        inventory=foreign,
    )

    failed = [
        subject
        for subject in evidence.repositories
        if subject.resolution_status == ROOT_REPOSITORY_IDENTITY_INVALID
    ]
    assert len(failed) == 1
    assert failed[0].is_primary
    assert failed[0].read_scope is None
    # Nothing from the mismatched inventory was merged into the failed root.
    assert all(item.repository_display != "repo-a" for item in evidence.items)


def test_more_roots_than_the_limit_overflow_explicitly(tmp_path):
    workspace = tmp_path / "workspace"
    primary = make_repo(workspace / "repo-a")
    for name in ("repo-b", "repo-c", "repo-d"):
        make_repo(workspace / name)

    resolution = resolve_analysis_subjects(
        str(primary),
        obligations=["Compare this against ../repo-b, ../repo-c and ../repo-d."],
    )

    assert resolution.accepted_repository_count == MAX_ANALYSIS_ROOTS
    overflowed = [
        subject
        for subject in resolution.subjects
        if subject.resolution_status == ROOT_COUNT_EXCEEDED
    ]
    assert len(overflowed) == 2
    # Not silently taking the first two: every extra root is named and refused.
    assert all(subject.rejection_reason for subject in overflowed)
    assert all(subject.read_scope is None for subject in overflowed)


def test_containment_is_per_root_and_never_a_shared_parent(tmp_path):
    primary, secondary = make_workspace(tmp_path)
    resolution = resolve_analysis_subjects(
        str(primary), obligations=["Compare this against ../repo-b."]
    )
    scope_a, scope_b = (subject.read_scope for subject in resolution.accepted)

    assert scope_a is not None and scope_b is not None
    assert scope_a.contains(primary / "src" / "module_0.py")
    assert not scope_a.contains(secondary / "src" / "module_0.py")
    assert scope_b.contains(secondary / "src" / "module_0.py")
    assert not scope_b.contains(primary / "src" / "module_0.py")
    # The common parent is not a boundary either.
    assert not scope_a.contains(primary.parent)


def test_a_relative_path_cannot_climb_out_of_its_own_root(tmp_path):
    primary, secondary = make_workspace(tmp_path)
    scope = AnalysisReadScope(
        repository_id="repo-a-id", canonical_root=str(primary.resolve())
    )

    assert scope.resolve_within("src/module_0.py") is not None
    assert scope.resolve_within("../repo-b/src/module_0.py") is None
    assert scope.resolve_within("..") is None
    assert scope.resolve_within("") is None


def test_the_acquisition_reader_refuses_a_path_that_escapes_its_root(tmp_path):
    """The containment guard sits on the read itself, not only on the helper."""
    from core.analysis_evidence import _UNREADABLE, _read_excerpt

    primary, secondary = make_workspace(tmp_path)
    inside = _read_excerpt(primary.resolve(), "src/module_0.py", MAX_TOTAL_CHARS)
    outside = _read_excerpt(
        primary.resolve(), "../repo-b/src/module_0.py", MAX_TOTAL_CHARS
    )
    missing = _read_excerpt(primary.resolve(), "src", MAX_TOTAL_CHARS)

    assert isinstance(inside, tuple)
    assert outside is None  # refused, and distinguishable from unreadable
    assert missing is _UNREADABLE


def test_a_symlink_out_of_an_approved_root_is_still_refused(tmp_path):
    primary, secondary = make_workspace(tmp_path)
    link = primary / "src" / "escape.py"
    try:
        link.symlink_to(secondary / "src" / "module_0.py")
    except (OSError, NotImplementedError):  # pragma: no cover - platform dependent
        pytest.skip("symlink creation is not permitted in this environment")

    scope = AnalysisReadScope(
        repository_id="repo-a-id", canonical_root=str(primary.resolve())
    )
    # Approving repo-a never approved what repo-a's links reach.
    assert scope.resolve_within("src/escape.py") is None
    assert not scope.contains(link)


def test_a_read_scope_can_never_be_constructed_on_a_rejected_root():
    with pytest.raises(ValueError):
        AnalysisRepositorySubject(
            requested_root_literal="../nope",
            subject_ordinal=1,
            root_role=ROOT_ROLE_ADDITIONAL,
            resolution_status=ROOT_NOT_FOUND,
            read_scope=AnalysisReadScope(repository_id="x", canonical_root="/tmp"),
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("root_role", "commander"),
        ("resolution_status", "probably_fine"),
        ("containment_status", "mostly"),
        ("inventory_status", "0.87"),
    ],
)
def test_root_status_vocabularies_are_closed(field, value):
    kwargs = {
        "requested_root_literal": "../x",
        "subject_ordinal": 1,
        "root_role": ROOT_ROLE_ADDITIONAL,
        "resolution_status": ROOT_NOT_FOUND,
        field: value,
    }
    with pytest.raises(ValueError):
        AnalysisRepositorySubject(**kwargs)


# ══════════════════════════════════════════════════════════════════════════════
# 3. Inventory — reuse the primary, walk a new root exactly once
# ══════════════════════════════════════════════════════════════════════════════

def test_the_primary_inventory_is_reused_and_never_rewalked(tmp_path):
    primary, secondary = make_workspace(tmp_path)
    from core.repository_inventory import create_repository_inventory

    inventory = create_repository_inventory(str(primary))
    evidence = analysis(
        primary,
        "Compare this repository against ../repo-b.",
        inventory=inventory,
    )

    primary_subject = evidence.accepted_repositories[0]
    assert primary_subject.is_primary
    assert primary_subject.inventory_status == INVENTORY_REUSED_REQUEST_SCOPED
    assert primary_subject.traversal_count == 0


def test_an_accepted_additional_root_costs_exactly_one_traversal(tmp_path):
    primary, secondary = make_workspace(tmp_path)
    from core.repository_inventory import create_repository_inventory

    inventory = create_repository_inventory(str(primary))
    evidence = analysis(
        primary,
        "Compare this repository against ../repo-b.",
        inventory=inventory,
    )

    additional = evidence.accepted_repositories[1]
    assert additional.inventory_status == INVENTORY_TRAVERSED_ONCE
    assert additional.traversal_count == 1
    receipt = evidence.as_dict()["multi_root"]
    assert receipt["membership_traversals_added"] == 1


def test_a_refused_root_costs_no_traversal_at_all(tmp_path):
    primary, _ = make_workspace(tmp_path)
    evidence = analysis(
        primary,
        "Compare this repository against ../does-not-exist and /etc/passwd.",
    )

    assert evidence.as_dict()["multi_root"]["membership_traversals_added"] == 0
    assert all(
        subject.inventory_file_count == 0
        for subject in evidence.rejected_repositories
    )


def test_the_additional_root_uses_the_same_ignore_policy(tmp_path):
    primary, secondary = make_workspace(tmp_path)
    _write(secondary / "node_modules" / "left-pad" / "index.js", "module.exports=1\n")
    _write(secondary / "__pycache__" / "cached.py", "cached = True\n")
    _write(secondary / ".venv" / "lib" / "site.py", "site = True\n")
    _write(secondary / ".env", "SECRET_TOKEN=hunter2\n")
    _write(secondary / "dist" / "bundle.js", "bundled\n")

    evidence = analysis(primary, "Compare this repository against ../repo-b.")
    paths = {
        item.path
        for item in evidence.items
        if item.repository_display == "repo-b"
    }

    assert paths, "the additional root should still contribute evidence"
    for excluded in ("node_modules", "__pycache__", ".venv", ".env", "dist"):
        assert not any(excluded in path for path in paths), excluded
    # The secret is not merely unselected — it never reached the excerpt text.
    assert all("hunter2" not in item.text for item in evidence.items)


def test_no_graph_index_or_embedding_is_built_for_the_additional_root(tmp_path):
    primary, secondary = make_workspace(tmp_path)
    analysis(primary, "Compare this repository against ../repo-b.")

    for artifact in (".agent", "index", "graph.json", "embeddings"):
        assert not (secondary / artifact).exists(), artifact
    # And nothing was written into the additional repository at all.
    assert sorted(entry.name for entry in secondary.iterdir()) == [
        "README.md",
        "docs",
        "pyproject.toml",
        "src",
    ]


# ══════════════════════════════════════════════════════════════════════════════
# 4. Budget — allocated across roots, never multiplied by them
# ══════════════════════════════════════════════════════════════════════════════

def test_the_global_file_cap_is_not_multiplied_per_root(tmp_path):
    workspace = tmp_path / "workspace"
    primary = make_repo(workspace / "repo-a", sources=40, docs=20)
    make_repo(workspace / "repo-b", sources=40, docs=20)

    evidence = analysis(
        primary,
        "Compare this repository against ../repo-b: how is each implemented?",
    )

    assert len(evidence.items) == MAX_EVIDENCE_FILES
    assert len(evidence.items) < MAX_EVIDENCE_FILES * 2


def test_the_global_character_cap_is_not_multiplied_per_root(tmp_path):
    workspace = tmp_path / "workspace"
    big = "x = 1\n" * 4_000
    primary = make_repo(workspace / "repo-a", sources=20, body=big)
    make_repo(workspace / "repo-b", sources=20, body=big)

    evidence = analysis(
        primary,
        "Compare this repository against ../repo-b: how is each implemented?",
    )
    total = sum(len(item.text) for item in evidence.items)

    assert total <= MAX_TOTAL_CHARS
    assert all(len(item.text) <= MAX_CHARS_PER_FILE for item in evidence.items)
    assert evidence.as_dict()["multi_root"]["global_bounds"] == {
        "max_files": MAX_EVIDENCE_FILES,
        "max_total_chars": MAX_TOTAL_CHARS,
        "per_root_multiplication": False,
    }


def test_root_a_cannot_spend_the_whole_budget_before_root_b_is_considered(tmp_path):
    workspace = tmp_path / "workspace"
    primary = make_repo(workspace / "repo-a", sources=60, docs=30)
    make_repo(workspace / "repo-b", sources=60, docs=30)

    evidence = analysis(
        primary,
        "Compare this repository against ../repo-b: how is each implemented?",
    )
    per_repository = evidence.files_by_repository()

    assert len(per_repository) == 2
    assert min(per_repository.values()) >= MAX_EVIDENCE_FILES // 2
    assert evidence.as_dict()["multi_root"]["root_balance_status"] == BALANCE_BALANCED


def test_a_root_floor_is_not_a_quota_when_the_other_root_is_small(tmp_path):
    workspace = tmp_path / "workspace"
    primary = make_repo(workspace / "repo-a", sources=60, docs=30)
    make_repo(workspace / "repo-b", sources=1, docs=1, manifest=False)

    evidence = analysis(
        primary,
        "Compare this repository against ../repo-b: how is each implemented?",
    )
    per_repository = evidence.files_by_repository()

    # Availability-aware: repo-b contributes what it has and the unused slots
    # are spent rather than reserved forever.
    assert len(evidence.items) == MAX_EVIDENCE_FILES
    assert sum(per_repository.values()) == MAX_EVIDENCE_FILES
    assert min(per_repository.values()) >= 1


def test_each_root_keeps_its_own_role_balance(tmp_path):
    workspace = tmp_path / "workspace"
    primary = make_repo(workspace / "repo-a", sources=30, docs=30)
    make_repo(workspace / "repo-b", sources=30, docs=30)

    evidence = analysis(
        primary,
        "Compare the architecture and implementation of this repository "
        "against ../repo-b.",
    )
    roles = evidence.roles_by_repository()

    assert len(roles) == 2
    for repository, counts in roles.items():
        assert counts.get(ROLE_IMPLEMENTATION_SOURCE, 0) > 0, repository
        assert counts.get(ROLE_PROJECT_DOCUMENT, 0) > 0, repository


def test_the_second_root_does_not_revert_to_documentation_first(tmp_path):
    workspace = tmp_path / "workspace"
    primary = make_repo(workspace / "repo-a", sources=10, docs=40)
    make_repo(workspace / "repo-b", sources=10, docs=40)

    evidence = analysis(
        primary,
        "Compare the architecture and implementation of this repository "
        "against ../repo-b.",
    )

    assert set(evidence.source_backed_repositories()) == {
        subject.repository_id for subject in evidence.accepted_repositories
    }


def test_an_exactly_requested_file_is_never_evicted_by_balancing(tmp_path):
    workspace = tmp_path / "workspace"
    primary = make_repo(workspace / "repo-a", sources=40, docs=40)
    secondary = make_repo(workspace / "repo-b", sources=40, docs=40)
    _write(primary / "router.py", "def route():\n    return 'a'\n")
    _write(secondary / "router.py", "def route():\n    return 'b'\n")

    evidence = analysis(
        primary,
        "Compare repo-a's router.py against ../repo-b's router.py.",
        requested_paths=["router.py"],
    )
    requested = [
        item for item in evidence.items if item.role == ROLE_REQUESTED_PATH
    ]

    assert {item.repository_display for item in requested} == {"repo-a", "repo-b"}
    assert all(item.path == "router.py" for item in requested)


def test_allocation_takes_turns_and_stops_at_the_global_budget():
    left = [(f"a/{index}.py", ROLE_IMPLEMENTATION_SOURCE) for index in range(20)]
    right = [(f"b/{index}.py", ROLE_IMPLEMENTATION_SOURCE) for index in range(20)]

    allocated = allocate_root_balanced_selections(
        [(0, left), (1, right)],
        max_files=MAX_EVIDENCE_FILES,
        requested_role=ROLE_REQUESTED_PATH,
    )

    assert len(allocated) == MAX_EVIDENCE_FILES
    assert [ordinal for ordinal, _, _ in allocated] == [0, 1] * (MAX_EVIDENCE_FILES // 2)


def test_allocation_hoists_requested_paths_before_it_rotates():
    left = [("a/keep.py", ROLE_REQUESTED_PATH)] + [
        (f"a/{index}.py", ROLE_IMPLEMENTATION_SOURCE) for index in range(20)
    ]
    right = [("b/keep.py", ROLE_REQUESTED_PATH)] + [
        (f"b/{index}.py", ROLE_IMPLEMENTATION_SOURCE) for index in range(20)
    ]

    allocated = allocate_root_balanced_selections(
        [(0, left), (1, right)],
        max_files=MAX_EVIDENCE_FILES,
        requested_role=ROLE_REQUESTED_PATH,
    )

    assert [path for _, path, _ in allocated[:2]] == ["a/keep.py", "b/keep.py"]


def test_root_order_follows_the_task_and_is_never_alphabetised(tmp_path):
    workspace = tmp_path / "workspace"
    primary = make_repo(workspace / "zeta")
    make_repo(workspace / "alpha")

    resolution = resolve_analysis_subjects(
        str(primary), obligations=["Compare this repository against ../alpha."]
    )

    assert [subject.repository_display for subject in resolution.accepted] == [
        "zeta",
        "alpha",
    ]


# ══════════════════════════════════════════════════════════════════════════════
# 5. Provenance and citations — which repository said what
# ══════════════════════════════════════════════════════════════════════════════

def test_the_same_relative_path_in_both_roots_stays_disambiguated(tmp_path):
    workspace = tmp_path / "workspace"
    primary = make_repo(workspace / "repo-a", sources=0, docs=1)
    secondary = make_repo(workspace / "repo-b", sources=0, docs=1)
    _write(primary / "src" / "index.ts", "export const side = 'a';\n")
    _write(secondary / "src" / "index.ts", "export const side = 'b';\n")

    evidence = analysis(
        primary,
        "Compare the implementation of this repository against ../repo-b.",
    )
    index_items = [item for item in evidence.items if item.path == "src/index.ts"]

    # Two entries with the same relative path, not one deduped entry.
    assert len(index_items) == 2
    assert {item.repository_display for item in index_items} == {"repo-a", "repo-b"}
    assert {item.citation for item in index_items} == {
        "repo-a::src/index.ts",
        "repo-b::src/index.ts",
    }
    assert "side = 'a'" in "".join(
        item.text for item in index_items if item.repository_display == "repo-a"
    )


def test_every_evidence_entry_carries_its_repository(tmp_path):
    primary, _ = make_workspace(tmp_path)
    evidence = analysis(primary, "Compare this repository against ../repo-b.")

    for item in evidence.items:
        assert item.repository_id
        assert item.repository_display
        assert item.as_dict()["repository_id"] == item.repository_id


def test_a_single_root_item_carries_no_repository_key(tmp_path):
    primary, _ = make_workspace(tmp_path)
    evidence = analysis(primary, "Summarise this project.")

    assert all("repository_id" not in item.as_dict() for item in evidence.items)


def test_the_rendered_evidence_block_names_the_repository(tmp_path):
    primary, _ = make_workspace(tmp_path)
    evidence = analysis(primary, "Compare this repository against ../repo-b.")
    block = render_analysis_evidence_block(evidence)

    assert "repository=repo-a" in block
    assert "repository=repo-b" in block
    assert "cite=repo-b::" in block


def test_the_prompt_states_which_repositories_were_read(tmp_path):
    primary, _ = make_workspace(tmp_path)
    evidence = analysis(primary, "Compare this repository against ../repo-b.")
    prompt = build_analysis_answer_prompt(
        user_query="Compare this repository against ../repo-b.",
        evidence=evidence,
        obligations=["Compare this repository against ../repo-b."],
        repo_path=str(primary),
    )

    assert "[REPOSITORIES" in prompt
    assert "repo-b" in prompt
    assert "read-only" in prompt
    assert "Do not open by saying you cannot access it" in prompt
    assert "repository::path" in prompt


def test_a_requested_but_unreadable_root_is_reported_as_a_partial_comparison(tmp_path):
    primary, _ = make_workspace(tmp_path)
    evidence = analysis(
        primary, "Compare this repository against ../does-not-exist."
    )
    prompt = build_analysis_answer_prompt(
        user_query="Compare this repository against ../does-not-exist.",
        evidence=evidence,
        repo_path=str(primary),
    )

    # The available half is still analysed; the missing half is named.
    assert evidence.items
    assert any("does-not-exist" in gap for gap in evidence.gaps)
    assert "NOT READ" in prompt
    assert "does-not-exist" in prompt


def test_the_single_root_prompt_keeps_its_repository_header(tmp_path):
    primary, _ = make_workspace(tmp_path)
    evidence = analysis(primary, "Summarise this project.")
    prompt = build_analysis_answer_prompt(
        user_query="Summarise this project.", evidence=evidence, repo_path=str(primary)
    )

    assert "[REPOSITORY]" in prompt
    assert "[REPOSITORIES" not in prompt
    assert "More than one repository was read" not in prompt


# ══════════════════════════════════════════════════════════════════════════════
# 6. Grounding — symbol universes stay separate
# ══════════════════════════════════════════════════════════════════════════════

class _State:
    """The minimum an answer-grounding call reads off a run."""

    def __init__(self, repo_path, evidence):
        self.repo_path = str(repo_path)
        self.analysis_evidence = evidence
        self.user_input = ""
        self.validation_output = ""
        self.control_result = None
        self.repository_inventory = None
        self.repository_graph = None
        self.project_tag = ""


def _repositories_for(primary, evidence):
    from core.answer_entity_grounding import _state_repository_evidence

    return _state_repository_evidence(_State(primary, evidence))


def test_each_accepted_root_gets_its_own_membership_record(tmp_path):
    primary, _ = make_workspace(tmp_path)
    evidence = analysis(primary, "Compare this repository against ../repo-b.")
    repositories = _repositories_for(primary, evidence)

    assert len(repositories) == 2
    assert {repo.display_name for repo in repositories} == {"repo-a", "repo-b"}
    assert len({repo.repository_id for repo in repositories}) == 2


def test_a_file_read_from_one_root_never_enters_the_other_universe(tmp_path):
    workspace = tmp_path / "workspace"
    primary = make_repo(workspace / "repo-a", sources=0, docs=1)
    secondary = make_repo(workspace / "repo-b", sources=0, docs=1)
    _write(primary / "src" / "only_in_a.py", "def only_in_a():\n    return 1\n")
    _write(secondary / "src" / "only_in_b.py", "def only_in_b():\n    return 2\n")

    evidence = analysis(
        primary, "Compare the implementation of this repository against ../repo-b."
    )
    repositories = {repo.display_name: repo for repo in _repositories_for(primary, evidence)}

    assert "src/only_in_a.py" in repositories["repo-a"].analysis_paths
    assert "src/only_in_a.py" not in repositories["repo-b"].analysis_paths
    assert "src/only_in_b.py" in repositories["repo-b"].analysis_paths
    assert "src/only_in_b.py" not in repositories["repo-a"].analysis_paths


def test_a_symbol_only_root_a_defines_cannot_ground_a_claim_about_root_b(tmp_path):
    from core.answer_entity_grounding import ground_answer_text

    workspace = tmp_path / "workspace"
    primary = make_repo(workspace / "repo-a", sources=0, docs=1)
    make_repo(workspace / "repo-b", sources=0, docs=1)
    _write(
        primary / "src" / "loop.py",
        "class Foo:\n    def run(self):\n        return 1\n",
    )

    evidence = analysis(
        primary, "Compare the implementation of this repository against ../repo-b."
    )
    repositories = _repositories_for(primary, evidence)

    grounded_a, findings_a = ground_answer_text(
        "repo-a::src/loop.py::Foo.run drives the loop.", repositories, user_input=""
    )
    grounded_b, findings_b = ground_answer_text(
        "repo-b::src/loop.py::Foo.run drives the loop.", repositories, user_input=""
    )

    assert [finding.status for finding in findings_a] == ["grounded_existing"]
    assert findings_b and all(
        finding.status != "grounded_existing" for finding in findings_b
    )
    assert grounded_a != grounded_b


def test_a_comparative_claim_needs_evidence_from_both_sides(tmp_path):
    from core.answer_entity_grounding import ground_answer_text

    workspace = tmp_path / "workspace"
    primary = make_repo(workspace / "repo-a", sources=0, docs=1)
    secondary = make_repo(workspace / "repo-b", sources=0, docs=1)
    _write(primary / "src" / "registry.py", "def register_a():\n    return 1\n")
    _write(secondary / "src" / "registry.py", "def register_b():\n    return 2\n")

    evidence = analysis(
        primary, "Compare the implementation of this repository against ../repo-b."
    )
    repositories = _repositories_for(primary, evidence)

    _, supported = ground_answer_text(
        "repo-a::src/registry.py registers eagerly while "
        "repo-b::src/registry.py registers lazily.",
        repositories,
        user_input="",
    )
    _, half = ground_answer_text(
        "repo-a::src/registry.py registers eagerly while "
        "repo-b::src/plugins.py registers lazily.",
        repositories,
        user_input="",
    )

    assert {finding.status for finding in supported} == {"grounded_existing"}
    assert any(finding.status != "grounded_existing" for finding in half)


# ══════════════════════════════════════════════════════════════════════════════
# 7. The exact T5 task
# ══════════════════════════════════════════════════════════════════════════════

def _t5_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    primary = make_repo(workspace / "deepseek-harness", sources=12, docs=6)
    _write(
        primary / "src" / "agent_loop.py",
        "class AgentLoop:\n    def step(self):\n        return 'harness'\n",
    )
    secondary = make_repo(workspace / "C.A.T.T.U.S", sources=12, docs=6)
    _write(
        secondary / "src" / "pipeline.py",
        "class Pipeline:\n    def run_draft(self):\n        return 'cattus'\n",
    )
    return primary


def test_the_exact_t5_task_accepts_both_roots(tmp_path):
    primary = _t5_workspace(tmp_path)
    resolution = resolve_analysis_subjects(str(primary), obligations=[T5_TASK])

    assert resolution.accepted_repository_count == 2
    assert [subject.repository_display for subject in resolution.accepted] == [
        "deepseek-harness",
        "C.A.T.T.U.S",
    ]
    assert len({subject.repository_id for subject in resolution.accepted}) == 2


def test_the_exact_t5_task_reads_source_and_documentation_from_both_roots(tmp_path):
    primary = _t5_workspace(tmp_path)
    evidence = analysis(primary, T5_TASK)
    roles = evidence.roles_by_repository()

    assert evidence.is_multi_root
    assert len(roles) == 2
    for repository, counts in roles.items():
        assert counts.get(ROLE_IMPLEMENTATION_SOURCE, 0) > 0, repository
        assert counts.get(ROLE_PROJECT_DOCUMENT, 0) > 0, repository


def test_the_exact_t5_task_stays_inside_the_global_budget(tmp_path):
    primary = _t5_workspace(tmp_path)
    evidence = analysis(primary, T5_TASK)
    receipt = evidence.as_dict()["multi_root"]

    assert receipt["global_files_selected"] <= MAX_EVIDENCE_FILES
    assert receipt["global_chars_selected"] <= MAX_TOTAL_CHARS
    assert receipt["accepted_repository_count"] == 2
    assert receipt["membership_traversals_added"] == 1


def test_the_exact_t5_task_no_longer_reports_the_second_root_inaccessible(tmp_path):
    primary = _t5_workspace(tmp_path)
    evidence = analysis(primary, T5_TASK)

    assert "C.A.T.T.U.S" in displays(evidence)
    assert not any(
        "C.A.T.T.U.S" in gap and "not read" in gap.lower() for gap in evidence.gaps
    )
    prompt = build_analysis_answer_prompt(
        user_query=T5_TASK, evidence=evidence, obligations=[T5_TASK], repo_path=str(primary)
    )
    assert "C.A.T.T.U.S [additional, read-only]" in prompt
    assert "NOT READ" not in prompt


def test_the_exact_t5_task_is_deterministic(tmp_path):
    primary = _t5_workspace(tmp_path)
    first = analysis(primary, T5_TASK)
    second = analysis(primary, T5_TASK)

    assert [(item.repository_id, item.path, item.role) for item in first.items] == [
        (item.repository_id, item.path, item.role) for item in second.items
    ]
    assert first.gaps == second.gaps


# ══════════════════════════════════════════════════════════════════════════════
# 8. Route and authority boundaries
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("analysis_only", [False])
def test_only_the_analysis_route_may_read_a_second_repository(tmp_path, analysis_only):
    primary, _ = make_workspace(tmp_path)
    evidence = collect_analysis_evidence(
        str(primary),
        obligations=["Compare this repository against ../repo-b."],
        analysis_only=analysis_only,
    )

    assert evidence.is_multi_root is False
    assert evidence.repositories == ()
    assert displays(evidence) == {""}


@pytest.mark.parametrize(
    "task",
    [
        # T1/T2/T3 shape: a defect claim.
        "subtract() returns the wrong number in src/module_0.py; it is broken. "
        "Fix it the way ../repo-b does it.",
        # T4 shape: an explicit change.
        "Add a priority field to the CLI in src/module_0.py, matching "
        "../repo-b's implementation.",
    ],
)
def test_a_change_requesting_task_never_reaches_a_second_repository(tmp_path, task):
    """Stronger than replaying T1-T4: these tasks *do* name a sibling root."""
    from core.live_task_routing import route_from_live_shape
    from core.live_task_shape import derive_live_task_shape

    primary, _ = make_workspace(tmp_path)
    route = route_from_live_shape(
        derive_live_task_shape(task), repository_available=True
    )

    assert route.analysis_only is False
    evidence = collect_analysis_evidence(
        str(primary),
        requested_paths=route.requested_paths,
        subjects=route.subjects,
        obligations=route.obligations,
        analysis_only=route.analysis_only,
    )

    assert evidence.is_multi_root is False
    assert evidence.repositories == ()
    assert all(item.repository_id == "" for item in evidence.items)


def test_a_read_scope_grants_reading_and_nothing_else():
    scope = AnalysisReadScope(repository_id="r", canonical_root=os.getcwd())

    assert scope.evidence_read_allowed is True
    assert scope.write_authority is False
    assert scope.patch_application_authority is False
    assert scope.execution_authority is False
    assert scope.human_review_eligible is False
    assert scope.approval_ready is False

    for attribute in (
        "write_authority",
        "patch_application_authority",
        "execution_authority",
        "human_review_eligible",
        "approval_ready",
    ):
        with pytest.raises(AttributeError):
            setattr(scope, attribute, True)


def test_the_receipt_reports_no_authority_of_any_kind(tmp_path):
    primary, _ = make_workspace(tmp_path)
    evidence = analysis(primary, "Compare this repository against ../repo-b.")
    authority = evidence.as_dict()["multi_root"]["authority"]

    assert authority["evidence_read_allowed"] is True
    assert authority["write_authority"] is False
    assert authority["patch_application_authority"] is False
    assert authority["execution_authority"] is False
    assert authority["human_review_eligible"] is False
    assert authority["approval_ready"] is False


def test_the_receipt_carries_no_source_and_no_absolute_paths(tmp_path):
    primary, secondary = make_workspace(tmp_path)
    _write(secondary / "src" / "module_0.py", "SECRET_MARKER = 'do-not-leak'\n")
    evidence = analysis(primary, "Compare this repository against ../repo-b.")
    serialized = json.dumps(evidence.as_dict()["multi_root"])

    assert "do-not-leak" not in serialized
    assert str(secondary.resolve()).replace("\\", "/") not in serialized.replace(
        "\\\\", "/"
    )
    assert "confidence" not in serialized


def test_the_role_coverage_receipt_became_root_aware_additively(tmp_path):
    primary, _ = make_workspace(tmp_path)
    payload = analysis(
        primary, "Compare the implementation of this repository against ../repo-b."
    ).as_dict()

    for field in (
        "selected_files_by_repository",
        "selected_chars_by_repository",
        "roles_by_repository",
        "unmet_role_requirements_by_repository",
    ):
        assert field in payload, field
        assert len(payload[field]) == 2, field
    # The single-root fields keep their names and their meanings.
    for field in (
        "selected_files_by_role",
        "selected_chars_by_role",
        "role_coverage",
        "unmet_role_requirements",
        "inventory_file_count",
    ):
        assert field in payload, field


def test_a_single_root_run_reports_empty_per_repository_coverage(tmp_path):
    primary, _ = make_workspace(tmp_path)
    payload = analysis(primary, "Summarise this project.").as_dict()

    assert payload["unmet_role_requirements_by_repository"] == {}
    assert set(payload["selected_files_by_repository"]) == {""}


def test_the_receipt_is_json_serialisable_and_bounded(tmp_path):
    primary, _ = make_workspace(tmp_path)
    evidence = analysis(primary, "Compare this repository against ../repo-b.")
    receipt = evidence.as_dict()["multi_root"]

    json.dumps(receipt)
    assert receipt["phase_id"] == PHASE_ID
    assert receipt["root_count_limit"] == MAX_ANALYSIS_ROOTS
    assert set(receipt["selected_files_by_repository"]) == {
        subject.repository_id for subject in evidence.accepted_repositories
    }


# ══════════════════════════════════════════════════════════════════════════════
# 9. Compatibility
# ══════════════════════════════════════════════════════════════════════════════

def test_single_root_analysis_is_behaviourally_unchanged(tmp_path):
    primary, _ = make_workspace(tmp_path)
    task = "Explain the architecture and implementation of this project."

    before = collect_analysis_evidence(str(primary), obligations=[task])
    after = collect_analysis_evidence(
        str(primary), obligations=[task], analysis_only=True
    )

    assert [(item.path, item.role) for item in before.items] == [
        (item.path, item.role) for item in after.items
    ]
    assert before.gaps == after.gaps
    assert before.profile == after.profile
    assert before.selection_reason == after.selection_reason
    assert before.unmet_role_requirements == after.unmet_role_requirements


def test_a_documentation_only_task_stays_documentation_centric(tmp_path):
    primary, _ = make_workspace(tmp_path)
    evidence = analysis(primary, "Summarise the README of this project.")

    assert evidence.is_multi_root is False
    assert any(item.role == ROLE_PROJECT_DOCUMENT for item in evidence.items)


def test_a_sibling_repository_that_merely_exists_changes_nothing(tmp_path):
    primary, _ = make_workspace(tmp_path)
    task = "Summarise the README of this project."

    evidence = analysis(primary, task)

    assert evidence.is_multi_root is False
    assert evidence.repositories == ()


def test_historical_single_root_artifacts_stay_loadable():
    legacy = AnalysisEvidence(
        items=(
            AnalysisEvidenceItem(path="README.md", role=ROLE_PROJECT_DOCUMENT, text="hi"),
        )
    )
    payload = legacy.as_dict()

    assert payload["multi_root"]["status"] == MULTIROOT_SINGLE_ROOT_LEGACY
    assert payload["multi_root"]["accepted_repository_count"] == 1
    assert "repository_id" not in payload["files_read"][0]
    assert legacy.is_multi_root is False


def test_the_role_balance_contract_still_holds_within_a_single_root(tmp_path):
    workspace = tmp_path / "workspace"
    primary = make_repo(workspace / "repo-a", sources=30, docs=30)
    evidence = collect_analysis_evidence(
        str(primary),
        obligations=["Explain the architecture and implementation of this project."],
        analysis_only=True,
    )
    roles = evidence.files_by_role()

    assert roles.get(ROLE_IMPLEMENTATION_SOURCE, 0) > 0
    assert roles.get(ROLE_PROJECT_DOCUMENT, 0) > 0
    assert roles.get(ROLE_PACKAGE_MANIFEST, 0) > 0


def test_the_call_sites_pass_the_analysis_only_gate():
    for module in (
        "core/pipeline.py",
        "web/runner.py",
        "web/app.py",
        "cli/interactive.py",
    ):
        text = Path(module).read_text(encoding="utf-8")
        assert "analysis_only=" in text, module


# ══════════════════════════════════════════════════════════════════════════════
# 10. Static boundaries
# ══════════════════════════════════════════════════════════════════════════════

def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


@pytest.mark.parametrize(
    "forbidden",
    [
        "core.indexer",
        "core.index_manifest",
        "core.retriever",
        "core.executor",
        "core.validator",
        "core.validation_execution",
        "core.validation_command",
        "core.preflight",
        "core.embedding_providers",
        "core.control_engine",
        "core.patch_safety",
        "graph.builder",
        "agents.gemini_client",
        "agents.ollama_client",
        "patching.patch_gates",
        "requests",
        "httpx",
        "openai",
    ],
)
def test_the_root_resolver_imports_no_model_index_or_execution_machinery(forbidden):
    assert forbidden not in _imported_modules(_MULTIROOT_SOURCE)


def _referenced_names(path: Path) -> set[str]:
    """Every identifier the module's *code* names, prose excluded.

    Read off the syntax tree rather than the file text, so a docstring that
    explains what the module refuses to do cannot be mistaken for it doing it.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.alias):
            names.add(node.asname or node.name.rsplit(".", 1)[-1])
    return names


@pytest.mark.parametrize(
    "forbidden",
    [
        "index_repository",
        "build_program_graph",
        "build_graph",
        "embed_texts",
        "get_embedding",
        "subprocess",
        "system",
        "popen",
        "run_validation",
        "apply_patch",
        "write_text",
        "mkdir",
        "unlink",
        "rmtree",
        "call_model",
        "generate",
    ],
)
def test_the_root_resolver_contains_no_write_execute_or_index_call(forbidden):
    assert forbidden not in _referenced_names(_MULTIROOT_SOURCE)


def test_the_resolver_never_discovers_a_root_on_its_own(tmp_path):
    """Every accepted root traces back to a literal in preserved user input."""
    workspace = tmp_path / "workspace"
    primary = make_repo(workspace / "repo-a")
    for name in ("repo-b", "repo-c"):
        make_repo(workspace / name)

    resolution = resolve_analysis_subjects(str(primary), obligations=["Explain this."])

    assert resolution.accepted_repository_count == 1
    assert resolution.multi_root_requested is False


def test_root_literals_are_only_read_from_authoritative_input():
    """A path with a file role is a requested path, not a repository root."""
    assert extract_requested_root_literals(["compare ../repo-b/src/index.ts"]) == ()
    assert extract_requested_root_literals(["tool/plugin registration"]) == ()
    assert extract_requested_root_literals([".."]) == ()
    assert extract_requested_root_literals(["../repo-b"]) == ("../repo-b",)


# ══════════════════════════════════════════════════════════════════════════════
# 11. Registration
# ══════════════════════════════════════════════════════════════════════════════

def _registry_entry() -> dict:
    data = json.loads(
        Path("docs/roadmap/phase_registry.json").read_text(encoding="utf-8")
    )
    return {phase["phase_id"]: phase for phase in data["phases"]}[PHASE_ID]


def test_the_phase_is_registered_on_the_waiter_track():
    phase = _registry_entry()

    assert phase["title"] == "Explicit Read-Only Multi-Repository Evidence Contract"
    assert phase["track"] == "WAITER"
    assert phase["status"] == "complete"
    assert phase["prerequisites"] == ["INPUT.PRESERVE.LIVE.1"]


def test_the_registry_entry_claims_no_model_network_or_sandbox_authority():
    phase = _registry_entry()

    assert phase["model_calls_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["requires_sandbox"] is False
    assert phase["merge_allowed"] is False
    assert phase["human_approval_required"] is True


def test_the_registry_entry_records_the_phase_characteristics():
    phase = _registry_entry()
    text = phase["summary"] + " " + " ".join(phase["notes"])

    for term in (
        "read scope",
        "explicitly requested",
        "MAX_ANALYSIS_ROOTS",
        "one canonical membership traversal",
        "no ProgramGraph",
        "no index",
        "no embedding",
        "12 files",
        "60,000 characters",
        "symbol universes",
        "single_root_legacy",
        "1 draft / 0 review",
        "not report-only",
    ):
        assert term.lower() in text.lower(), term


def test_no_plan_readiness_or_close_siblings_were_registered():
    data = json.loads(
        Path("docs/roadmap/phase_registry.json").read_text(encoding="utf-8")
    )
    ids = {phase["phase_id"] for phase in data["phases"]}

    for forbidden_phase in (
        "ANALYSIS.MULTIROOT.LIVE.1.PLAN",
        "ANALYSIS.MULTIROOT.LIVE.1.READINESS",
        "ANALYSIS.MULTIROOT.LIVE.1.CLOSE",
        "ANALYSIS.MULTIROOT.LIVE.2",
    ):
        assert forbidden_phase not in ids


def test_the_expected_artifacts_exist_on_disk():
    for artifact in _registry_entry()["expected_artifacts"]:
        assert Path(artifact).is_file(), artifact
