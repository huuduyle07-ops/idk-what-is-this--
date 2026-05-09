from __future__ import annotations

import re
from pathlib import Path

_VALIDATION_CMD_RE = re.compile(
    r"(?im)^\s*validation\s+command\s*:\s*(.+?)\s*$"
)


def extract_user_validation_command(text: str) -> str:
    m = _VALIDATION_CMD_RE.search(text or "")
    if not m:
        return ""
    return m.group(1).strip()


def get_default_validation_command(language: str, project_root: Path) -> str:
    lang = (language or "").lower().strip()

    if lang == "python":
        if (project_root / "pytest.ini").exists() or (project_root / "tests").exists():
            return "pytest"

        if (project_root / "test.py").exists():
            return "python test.py"

        if (project_root / "main.py").exists():
            return "python main.py"

        return "python -m unittest"

    if lang in {"csharp", "cs", "c#"}:
        has_project = (
            any(project_root.glob("*.csproj"))
            or any(project_root.glob("*.sln"))
        )
        if not has_project:
            return ""

        has_tests = (
            any(project_root.rglob("*Tests.csproj"))
            or any(project_root.rglob("*Test.csproj"))
        )

        return "dotnet test" if has_tests else "dotnet build"

    # C / C++
    if lang in {"cpp", "c++", "cxx", "cplusplus"}:
        if (project_root / "main.cpp").exists():
            return "g++ main.cpp -std=c++17 -static -static-libgcc -static-libstdc++ -o validation_test.exe && validation_test.exe && echo OK"
        return ""

    if lang in {"javascript", "js", "node", "nodejs"}:
        if (project_root / "package.json").exists():
            return "npm test"
        if (project_root / "test.js").exists():
            return "node test.js"
        return ""

    if lang in {"go", "golang"}:
        if list(project_root.rglob("*_test.go")):
            return "go test ./..."
        if (project_root / "main.go").exists():
            return "go run ."
        if (project_root / "go.mod").exists():
            return "go test ./..."
        return ""

    if lang in {"rust", "rs"}:
        if (project_root / "Cargo.toml").exists():
            if list(project_root.rglob("*_test.rs")) or "tests" in [p.name for p in project_root.iterdir() if p.is_dir()]:
                return "cargo test"
            return "cargo run && echo OK"
        return ""

    return ""
