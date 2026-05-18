from __future__ import annotations

import re
from pathlib import Path

_VALIDATION_CMD_RE = re.compile(
    r"(?im)^\s*validation\s+command\s*:\s*(.+?)\s*$"
)

_DANGEROUS_VALIDATION_CMD_RE = re.compile(
    r"(?i)(?:^|[;&|]\s*)("
    r"rm\s+-(?:r|f|rf|fr)\b|"
    r"del\s+(?:/s|/q|/f)\b|"
    r"erase\s+(?:/s|/q|/f)\b|"
    r"rmdir\s+(?:/s|/q)\b|"
    r"rd\s+(?:/s|/q)\b|"
    r"remove-item\b|"
    r"format\b|"
    r"mkfs\b|"
    r"shutdown\b|"
    r"reboot\b|"
    r"git\s+reset\s+--hard\b|"
    r"git\s+clean\b[^\n]*\s-[^\n]*f"
    r")"
)


def validation_command_safety_issue(command: str) -> str:
    if not command.strip():
        return ""
    if _DANGEROUS_VALIDATION_CMD_RE.search(command):
        return "Validation command contains a destructive shell operation."
    return ""


def extract_user_validation_command(text: str) -> str:
    m = _VALIDATION_CMD_RE.search(text or "")
    if not m:
        return ""
    command = m.group(1).strip()
    issue = validation_command_safety_issue(command)
    if issue:
        print(f"Validation command ignored: {issue}")
        return ""
    return command


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
