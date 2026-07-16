from pathlib import Path

from core.repo_ignore import RepoIgnorePolicy
from core.repo_librarian import build_repo_manifest, iter_repo_files, inspect_repo_inventory

def test_tmp_is_hard_excluded(tmp_path):
    policy = RepoIgnorePolicy.load(tmp_path)

    decision = policy.classify(
        Path(".tmp/generated.py"),
        is_dir=False,
    )

    assert decision.ignored is True
    assert decision.source == "hard_exclude"

def test_cattusignore_excludes_file(tmp_path):
    (tmp_path / ".cattusignore").write_text(
        "docs/archive/\n",
        encoding="utf-8",
    )

    policy = RepoIgnorePolicy.load(tmp_path)

    decision = policy.classify(
        Path("docs/archive/old.md"),
        is_dir=False,
    )

    assert decision.ignored is True
    assert decision.source == ".cattusignore"


def test_directory_pattern_is_ignored(tmp_path):
    (tmp_path / ".gitignore").write_text(
        "generated/\n",
        encoding="utf-8",
    )

    policy = RepoIgnorePolicy.load(tmp_path)

    decision = policy.classify(
        Path("generated"),
        is_dir=True,
    )

    assert decision.ignored is True


def test_outside_repository_is_rejected(tmp_path):
    policy = RepoIgnorePolicy.load(tmp_path)

    decision = policy.classify(
        tmp_path.parent / "outside.py",
        is_dir=False,
    )

    assert decision.ignored is True
    assert decision.source == "repository_boundary"


def test_gitignore_file_pattern(tmp_path):
    (tmp_path / ".gitignore").write_text(
        "*.generated.py\n",
        encoding="utf-8",
    )

    policy = RepoIgnorePolicy.load(tmp_path)

    decision = policy.classify(
        Path("core/model.generated.py"),
        is_dir=False,
    )

    assert decision.ignored is True
    assert decision.source == ".gitignore"


def test_gitignore_negation(tmp_path):
    (tmp_path / ".gitignore").write_text(
        "*.log\n!important.log\n",
        encoding="utf-8",
    )

    policy = RepoIgnorePolicy.load(tmp_path)

    assert policy.classify(
        Path("debug.log"),
        is_dir=False,
    ).ignored is True

    assert policy.classify(
        Path("important.log"),
        is_dir=False,
    ).ignored is False


def test_hard_exclude_cannot_be_reincluded(tmp_path):
    (tmp_path / ".gitignore").write_text(
        "!.tmp/keep.py\n",
        encoding="utf-8",
    )

    policy = RepoIgnorePolicy.load(tmp_path)

    decision = policy.classify(
        Path(".tmp/keep.py"),
        is_dir=False,
    )

    assert decision.ignored is True
    assert decision.source == "hard_exclude"

def _iter_relative_paths(repo_path: Path, query: str | None = None) -> set[str]:
    return {
        rel.as_posix()
        for _, rel in iter_repo_files(
            str(repo_path),
            query=query,
        )
    }


def test_iterator_prunes_hard_excluded_directories(tmp_path):
    source = tmp_path / "src" / "main.py"
    source.parent.mkdir()
    source.write_text("print('kept')\n", encoding="utf-8")

    temporary = tmp_path / ".tmp" / "generated.py"
    temporary.parent.mkdir()
    temporary.write_text("print('ignored')\n", encoding="utf-8")

    paths = _iter_relative_paths(tmp_path)

    assert "src/main.py" in paths
    assert ".tmp/generated.py" not in paths


def test_iterator_honors_gitignore_and_cattusignore(tmp_path):
    (tmp_path / ".gitignore").write_text(
        "generated/\n",
        encoding="utf-8",
    )
    (tmp_path / ".cattusignore").write_text(
        "docs/archive/\n",
        encoding="utf-8",
    )

    kept = tmp_path / "src" / "main.py"
    kept.parent.mkdir()
    kept.write_text("print('kept')\n", encoding="utf-8")

    generated = tmp_path / "generated" / "code.py"
    generated.parent.mkdir()
    generated.write_text("print('ignored')\n", encoding="utf-8")

    archived = tmp_path / "docs" / "archive" / "old.md"
    archived.parent.mkdir(parents=True)
    archived.write_text("old\n", encoding="utf-8")

    paths = _iter_relative_paths(tmp_path)

    assert "src/main.py" in paths
    assert "generated/code.py" not in paths
    assert "docs/archive/old.md" not in paths


def test_iterator_and_manifest_share_membership(tmp_path):
    source = tmp_path / "src" / "main.py"
    source.parent.mkdir()
    source.write_text("print('kept')\n", encoding="utf-8")

    ignored = tmp_path / ".temp" / "generated.py"
    ignored.parent.mkdir()
    ignored.write_text("print('ignored')\n", encoding="utf-8")

    iterator_paths = _iter_relative_paths(tmp_path)
    manifest = build_repo_manifest(str(tmp_path))

    assert set(manifest["files"]) == iterator_paths


def test_infra_query_behavior_is_preserved(tmp_path):
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text("FROM python:3.13\n", encoding="utf-8")

    normal_paths = _iter_relative_paths(tmp_path)
    docker_paths = _iter_relative_paths(
        tmp_path,
        query="Please inspect the Docker container",
    )

    assert "Dockerfile" not in normal_paths
    assert "Dockerfile" in docker_paths

def test_invalid_repo_inventory_is_graceful(tmp_path):
    missing = tmp_path / "missing"

    inventory = inspect_repo_inventory(str(missing))

    assert inventory["ok"] is False
    assert inventory["saved_count"] == 0
    assert inventory["indexable_count"] == 0
    assert inventory["sample_files"] == []
    assert inventory["sample_indexable_files"] == []

def test_repo_librarian_has_no_legacy_skip_policy():
    source = Path("core/repo_librarian.py").read_text(encoding="utf-8")

    assert "should_skip_relative_path" not in source
    assert "EXTRA_SKIP_DIRS" not in source
    assert "FOLDER_BLACKLIST" not in source

def test_repo_walker_prunes_directories_before_descent():
    source = Path("core/repo_librarian.py").read_text(encoding="utf-8")

    assert "os.walk(" in source
    assert "topdown=True" in source
    assert "dir_names[:] = kept_dirs" in source

def test_root_build_directory_is_hard_excluded(tmp_path):
    policy = RepoIgnorePolicy.load(tmp_path)

    decision = policy.classify(
        Path("build/generated.py"),
        is_dir=False,
    )

    assert decision.ignored is True
    assert decision.source == "hard_exclude"


def test_nested_build_directory_is_allowed(tmp_path):
    policy = RepoIgnorePolicy.load(tmp_path)

    decision = policy.classify(
        Path("src/build/parser.py"),
        is_dir=False,
    )

    assert decision.ignored is False

def test_nested_node_modules_is_hard_excluded(tmp_path):
    policy = RepoIgnorePolicy.load(tmp_path)

    decision = policy.classify(
        Path("frontend/vendor/node_modules/pkg/index.js"),
        is_dir=False,
    )

    assert decision.ignored is True
    assert decision.source == "hard_exclude"