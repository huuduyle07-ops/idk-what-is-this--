from __future__ import annotations

from pathlib import Path
from typing import Any
import json
from core.validator import run_validation_command, classify_validation_output
from core.diagnostics import extract_locations_from_preflight

def _has_package_test_script(project_root: Path) -> bool:
    package_json = project_root / "package.json"
    if not package_json.exists():
        return False

    try:
        data = json.loads(package_json.read_text(encoding="utf-8", errors="replace"))
        scripts = data.get("scripts") or {}
        return bool(scripts.get("test"))
    except Exception:
        return False


def detect_default_preflight_command(language: str, project_root: Path) -> str:
    lang = (language or "").lower().strip()

    # C#
    if lang in {"csharp", "cs", "c#"}:
        has_project = (
            any(project_root.glob("*.csproj"))
            or any(project_root.glob("*.sln"))
        )

        if not has_project:
            return ""

        return "dotnet build"

    # C / C++
    if lang in {"cpp", "c++", "cxx", "cplusplus"}:
        if (project_root / "main.cpp").exists():
            return "g++ main.cpp -std=c++17 -static -static-libgcc -static-libstdc++ -o validation_test.exe && validation_test.exe && echo OK"
        return ""

    # Rust
    if lang in {"rust", "rs"}:
        if (project_root / "Cargo.toml").exists():
            if list(project_root.rglob("*_test.rs")) or "tests" in [p.name for p in project_root.iterdir() if p.is_dir()]:
                return "cargo test"
            return "cargo run && echo OK"
        return ""

    # JavaScript / Node
    if (
        lang in {"javascript", "js", "node", "nodejs", "unknown"}
        and (project_root / "package.json").exists()
    ):
        if _has_package_test_script(project_root):
            return "npm test"
        if (project_root / "test.js").exists():
            return "node test.js"
        return ""

    if lang in {"javascript", "js", "node", "nodejs"}:
        return "node test.js" if (project_root / "test.js").exists() else ""

    # Go
    if lang in {"go", "golang"}:
        if list(project_root.rglob("*_test.go")):
            return "go test ./..."

        if (project_root / "main.go").exists():
            return "go run ."

        if (project_root / "go.mod").exists():
            return "go test ./..."
        return ""

    # Python
    if lang == "python":
        if (project_root / "pytest.ini").exists() or (project_root / "tests").exists():
            return "pytest"

        if (project_root / "test.py").exists():
            return "python test.py"

        if (project_root / "main.py").exists():
            return "python main.py"

        # Web app entry point (Flask/FastAPI/etc.) — use import check so we
        # validate module load without starting a server that would hang.
        if (project_root / "app.py").exists():
            return 'python -c "import app"'

        return "python -m unittest"

    return ""


def run_preflight_validation(
    repo_path: str,
    language: str,
    command: str | None = None,
) -> dict[str, Any]:
    project_root = Path(repo_path).resolve()

    validation_command = command or detect_default_preflight_command(
        language,
        project_root,
    )

    if not validation_command:
        return {
            "ran": False,
            "ok": None,
            "command": "",
            "category": "no_validation_command",
            "reason": "No suitable build/test command was detected.",
            "hint": "For C#, add a .csproj/.sln file. For Python, add tests or configure a command.",
            "output": "",
            "locations":[],
        }

    ok, output = run_validation_command(validation_command, cwd=str(project_root))
    info = classify_validation_output(output)

    return {
        "ran": True,
        "ok": ok,
        "command": validation_command,
        "category": "passed" if ok else info.get("category", "unknown"),
        "reason": "Validation passed." if ok else info.get("reason", ""),
        "hint": "" if ok else info.get("hint", ""),
        "output": output[:6000],
        "locations": extract_locations_from_preflight(output, repo_path=str(project_root)),
    }