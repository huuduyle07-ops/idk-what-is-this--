from __future__ import annotations

import ast
import io
import json
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def client():
    from web.app import app

    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


def test_successful_upload_returns_managed_temp_repo_with_metadata(client):
    from core.upload_temp_repos import (
        METADATA_FILENAME,
        MANAGED_UPLOAD_TEMP_PREFIX,
        cleanup_managed_upload_temp_repo,
    )

    resp = client.post(
        "/upload_folder",
        data={
            "files": [
                (io.BytesIO(b"def hello():\n    return 'world'\n"), "demo/app.py"),
            ],
        },
        content_type="multipart/form-data",
    )
    body = resp.get_json()
    repo_path = Path(body["repo_path"])

    try:
        assert resp.status_code == 200, body
        assert repo_path.is_dir()
        assert repo_path.parent.name.startswith(MANAGED_UPLOAD_TEMP_PREFIX)
        metadata_path = repo_path / METADATA_FILENAME
        assert metadata_path.is_file()
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert metadata["source_route"] == "/upload_folder"
        assert metadata["repo_path"] == str(repo_path)
        assert metadata["status"] == "active"
        assert metadata["cleanup_policy"] == "failed_upload_cleanup_ttl_eligible"
        assert body["upload_temp_repo"]["managed"] is True
        assert body["upload_temp_repo"]["status"] == "active"
        assert body["indexable_count"] == 1
        assert body["saved_count"] == 1
        assert body["sample_files"] == ["app.py"]
    finally:
        cleanup_managed_upload_temp_repo(repo_path)


def test_zero_indexable_upload_cleans_managed_temp_repo_and_reports_cleanup(client):
    resp = client.post(
        "/upload_folder",
        data={
            "files": [
                (io.BytesIO(b"\x89PNG\r\n"), "demo/image.png"),
            ],
        },
        content_type="multipart/form-data",
    )
    body = resp.get_json()
    repo_path = Path(body["repo_path"])

    assert resp.status_code == 400
    assert body["error"] == "Upload created a repo with 0 indexable files."
    assert body["upload_temp_repo"]["status"] == "failed_upload"
    cleanup = body["upload_temp_repo_cleanup"]
    assert cleanup["ok"] is True
    assert cleanup["action"] in {"deleted", "missing"}
    assert cleanup["managed"] is True
    assert not repo_path.exists()
    assert not repo_path.parent.exists()


def test_cleanup_helper_deletes_only_managed_temp_repo_paths(tmp_path):
    from core.upload_temp_repos import (
        MANAGED_UPLOAD_TEMP_PREFIX,
        cleanup_managed_upload_temp_repo,
        write_upload_temp_repo_metadata,
    )

    temp_root = tmp_path / f"{MANAGED_UPLOAD_TEMP_PREFIX}unit"
    repo_path = temp_root / "repo"
    repo_path.mkdir(parents=True)
    (repo_path / "app.py").write_text("print('ok')\n", encoding="utf-8")
    write_upload_temp_repo_metadata(repo_path, temp_root=temp_root, status="active")

    result = cleanup_managed_upload_temp_repo(repo_path, temp_base=tmp_path)

    assert result["ok"] is True
    assert result["action"] == "deleted"
    assert result["managed"] is True
    assert not temp_root.exists()


def test_cleanup_helper_refuses_unmanaged_arbitrary_path(tmp_path):
    from core.upload_temp_repos import cleanup_managed_upload_temp_repo

    arbitrary = tmp_path / "ordinary-repo"
    arbitrary.mkdir()
    (arbitrary / "app.py").write_text("print('keep')\n", encoding="utf-8")

    result = cleanup_managed_upload_temp_repo(arbitrary, temp_base=tmp_path)

    assert result["ok"] is False
    assert result["action"] == "refused"
    assert result["managed"] is False
    assert arbitrary.exists()


@pytest.mark.parametrize(
    "path_factory",
    [
        lambda: PROJECT_ROOT,
        lambda: PROJECT_ROOT / ".git",
        lambda: Path.home(),
        lambda: Path(Path.home().anchor),
    ],
)
def test_cleanup_helper_refuses_project_git_home_and_drive_root(path_factory, tmp_path):
    from core.upload_temp_repos import cleanup_managed_upload_temp_repo

    result = cleanup_managed_upload_temp_repo(path_factory(), temp_base=tmp_path)

    assert result["ok"] is False
    assert result["action"] == "refused"


def test_cleanup_helper_handles_missing_managed_dir_idempotently(tmp_path):
    from core.upload_temp_repos import MANAGED_UPLOAD_TEMP_PREFIX, cleanup_managed_upload_temp_repo

    missing_repo = tmp_path / f"{MANAGED_UPLOAD_TEMP_PREFIX}gone" / "repo"

    result = cleanup_managed_upload_temp_repo(missing_repo, temp_base=tmp_path)

    assert result["ok"] is True
    assert result["action"] == "missing"
    assert result["managed"] is True


def test_docs_describe_upload_temp_repo_lifecycle_policy():
    text = (
        (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        + "\n"
        + (
            PROJECT_ROOT / "docs" / "AI_Coding_Agent_Mentor_Operating_Roadmap_2026-06-07.md"
        ).read_text(encoding="utf-8")
    ).lower()

    assert "upload temp repo lifecycle" in text
    assert "managed temp repos" in text
    assert "failed upload temp dirs" in text
    assert "cleanup is constrained to managed temp roots" in text
    assert "a.21" in text


def test_upload_lifecycle_scope_has_no_forbidden_execution_power():
    helper_source = (PROJECT_ROOT / "core" / "upload_temp_repos.py").read_text(
        encoding="utf-8"
    )
    app_source = (PROJECT_ROOT / "web" / "app.py").read_text(encoding="utf-8")
    route_start = app_source.index('@app.route("/upload_folder"')
    route_end = app_source.index("# --- Phase 7.1", route_start)
    route_source = app_source[route_start:route_end]

    imports, calls = _imports_and_calls(helper_source + "\n" + route_source)
    forbidden_import_roots = {
        "agents",
        "benchmarks",
        "database",
        "docker",
        "google",
        "openai",
        "requests",
        "httpx",
        "socket",
        "subprocess",
    }
    forbidden_calls = {
        "ChatCompletion",
        "generate_content",
        "run_gemini",
        "run_ollama",
        "run_benchmark",
        "run_benchmarks",
        "launch_worker",
        "trigger_dream",
        "run_project_evolution",
        "promote_lesson",
        "import_proposal",
        "auto_merge",
        "Popen",
        "check_call",
        "check_output",
        "system",
    }

    assert {name.split(".", 1)[0] for name in imports}.isdisjoint(forbidden_import_roots)
    assert forbidden_calls.isdisjoint(calls)


def _imports_and_calls(source: str) -> tuple[set[str], set[str]]:
    tree = ast.parse(source)
    imports: set[str] = set()
    calls: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)
    return imports, calls
