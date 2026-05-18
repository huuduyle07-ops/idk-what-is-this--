import json
import shutil
import subprocess
from pathlib import Path

import pytest

from core import benchmark_web


def _write_case(root: Path, language: str = "python", name: str = "python_demo_case") -> Path:
    case_dir = root / language / name
    buggy = case_dir / "buggy_repo"
    buggy.mkdir(parents=True)
    (buggy / "main.py").write_text("print('ok')\n", encoding="utf-8")
    case_file = case_dir / "case.json"
    case_file.write_text(
        json.dumps(
            {
                "name": name,
                "language": language,
                "category": "logic_validation",
                "difficulty": "easy",
                "validation_command": "python main.py",
                "expected_changed_files": ["main.py"],
                "forbidden_changed_files": [],
                "prompt": "Fix the demo bug.\n\nValidation command: python main.py",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return case_file


def _write_dirty_git_repo(tmp_path: Path) -> Path:
    if shutil.which("git") is None:
        pytest.skip("git is not available")
    source = tmp_path / "dirty_repo"
    source.mkdir()
    (source / "main.py").write_text("print('before')\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=source, check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "main.py"], cwd=source, check=True, capture_output=True, text=True)
    (source / "main.py").write_text("print('after')\n", encoding="utf-8")
    return source


def test_list_benchmark_cases_uses_cases_root(tmp_path, monkeypatch):
    cases_root = tmp_path / "cases"
    _write_case(cases_root)
    monkeypatch.setattr(benchmark_web, "CASES_ROOT", cases_root)

    cases = benchmark_web.list_benchmark_cases()

    assert len(cases) == 1
    assert cases[0]["name"] == "python_demo_case"
    assert cases[0]["language"] == "python"
    assert cases[0]["category"] == "logic_validation"


def test_create_benchmark_case_from_repo_without_llm(tmp_path, monkeypatch):
    source = tmp_path / "source_repo"
    source.mkdir()
    (source / "main.py").write_text("print('broken')\n", encoding="utf-8")
    (source / ".agent").mkdir()
    (source / ".agent" / "ignored.txt").write_text("ignore me", encoding="utf-8")

    cases_root = tmp_path / "cases"
    monkeypatch.setattr(benchmark_web, "CASES_ROOT", cases_root)

    result = benchmark_web.create_benchmark_case_from_repo(
        source_repo_path=str(source),
        case_name="Python Demo Case",
        user_prompt="Fix the printed output.",
        validation_command="python main.py",
        expected_changed_files="main.py",
        forbidden_changed_files="README.md",
        use_llm=False,
    )

    assert result["ok"] is True
    case_file = Path(result["case_file"])
    assert case_file.is_file()
    case = json.loads(case_file.read_text(encoding="utf-8"))
    assert case["name"] == "python_demo_case"
    assert case["language"] == "python"
    assert case["difficulty"] == "medium"
    assert case["expected_changed_files"] == ["main.py"]
    assert case["forbidden_changed_files"] == ["README.md"]
    assert (case_file.parent / "buggy_repo" / "main.py").is_file()
    assert not (case_file.parent / "buggy_repo" / ".agent").exists()


def test_infer_case_defaults_uses_git_dirty_file(tmp_path):
    source = _write_dirty_git_repo(tmp_path)

    result = benchmark_web.infer_case_defaults(str(source), user_prompt="Fix the output.")

    assert result["ok"] is True
    assert result["language"] == "python"
    assert result["validation_command"] == "python main.py"
    assert result["expected_changed_files"] == ["main.py"]
    assert result["expected_changed_files_source"] == "git_diff"


def test_create_benchmark_case_uses_inferred_expected_when_blank(tmp_path, monkeypatch):
    source = _write_dirty_git_repo(tmp_path)
    cases_root = tmp_path / "cases"
    monkeypatch.setattr(benchmark_web, "CASES_ROOT", cases_root)

    result = benchmark_web.create_benchmark_case_from_repo(
        source_repo_path=str(source),
        case_name="Dirty Repo Case",
        user_prompt="Fix the dirty repo output.",
        validation_command="",
        expected_changed_files="",
        forbidden_changed_files="",
        use_llm=False,
    )

    assert result["ok"] is True
    case = json.loads(Path(result["case_file"]).read_text(encoding="utf-8"))
    assert case["expected_changed_files"] == ["main.py"]
    assert case["validation_command"] == "python main.py"


def test_benchmark_routes_list_cases_and_reject_empty_selection(tmp_path, monkeypatch):
    from web import app as web_app

    cases_root = tmp_path / "cases"
    _write_case(cases_root)
    monkeypatch.setattr(benchmark_web, "CASES_ROOT", cases_root)

    client = web_app.app.test_client()

    list_resp = client.get("/benchmarks/cases")
    assert list_resp.status_code == 200
    body = list_resp.get_json()
    assert body["ok"] is True
    assert body["cases"][0]["name"] == "python_demo_case"

    repo = tmp_path / "repo"
    repo.mkdir()
    run_resp = client.post(
        "/benchmarks/run",
        data={"repo_path": str(repo), "selection": "selected", "cases": "[]"},
    )
    assert run_resp.status_code == 400
    assert "choose at least one" in run_resp.get_json()["error"]


def test_benchmark_create_case_route_without_llm(tmp_path, monkeypatch):
    from web import app as web_app

    source = tmp_path / "source_repo"
    source.mkdir()
    (source / "main.py").write_text("print('broken')\n", encoding="utf-8")

    cases_root = tmp_path / "cases"
    monkeypatch.setattr(benchmark_web, "CASES_ROOT", cases_root)

    resp = web_app.app.test_client().post(
        "/benchmarks/create-case",
        data={
            "source_repo_path": str(source),
            "case_name": "Route Demo Case",
            "prompt": "Fix the route demo.",
            "validation_command": "python main.py",
            "expected_changed_files": "main.py",
            "forbidden_changed_files": "",
            "use_llm": "false",
        },
    )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["case"]["name"] == "route_demo_case"
    assert Path(body["case_file"]).is_file()


def test_benchmark_case_defaults_route(tmp_path):
    from web import app as web_app

    source = _write_dirty_git_repo(tmp_path)

    resp = web_app.app.test_client().get(
        "/benchmarks/case-defaults",
        query_string={"source_repo_path": str(source), "prompt": "Fix output."},
    )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["expected_changed_files"] == ["main.py"]
    assert body["validation_command"] == "python main.py"
