from __future__ import annotations

import json
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


# ── OPS.VALIDATE.1 — shared, bounded repository-evidence helpers ─────────────
#
# Every check below reads the repository *root* only: named files, one
# non-recursive glob per pattern, and at most one small config read.  Choosing a
# validation command must stay orders of magnitude cheaper than indexing, so
# nothing here walks the tree, builds a graph, parses source or touches a DB.

#: The pytest invocation production emits.  Never bare ``pytest``: on Windows a
#: virtualenv's pytest is frequently absent from PATH while its interpreter is
#: the one running C.A.T.T.U.S, so ``'pytest' is not recognized`` was the field
#: test's very first failure.  ``python -m pytest`` resolves the runner *inside*
#: the interpreter that executes it, and the validation runners map a leading
#: bare ``python`` token to the current ``sys.executable``.
PYTHON_PYTEST_COMMAND = "python -m pytest"
PYTHON_UNITTEST_COMMAND = "python -m unittest"

#: pytest's own default ``python_files`` patterns, applied to the root only.
_ROOT_PYTEST_FILE_GLOBS: tuple[str, ...] = ("test_*.py", "*_test.py")

#: Deterministic script preference for a Node/TypeScript repository.  ``test``
#: comes first because it is the strongest evidence a patch is correct and it is
#: the script the existing JavaScript branch already selected; ``build`` comes
#: last because compiling is the weakest of the four.  There is no retry: the
#: first script that exists is the command, and no script means no command.
NODE_SCRIPT_PRIORITY: tuple[str, ...] = ("test", "typecheck", "check", "build")

#: Root lockfiles, in the order they are consulted.
_PACKAGE_MANAGER_LOCKFILES: tuple[tuple[str, str], ...] = (
    ("pnpm-lock.yaml", "pnpm"),
    ("yarn.lock", "yarn"),
    ("package-lock.json", "npm"),
)

DEFAULT_PACKAGE_MANAGER = "npm"


def _read_root_text(project_root: Path, name: str) -> str:
    try:
        return (project_root / name).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _root_glob_matches(project_root: Path, pattern: str) -> bool:
    """One non-recursive glob over the repository root."""
    try:
        return any(project_root.glob(pattern))
    except OSError:
        return False


def repo_uses_pytest(project_root: Path) -> bool:
    """True when bounded root evidence says this repository is pytest-shaped.

    The absence of ``pytest.ini`` is not proof that a repository uses unittest,
    which is exactly what the field test's flat ``solution.py`` /
    ``test_solution.py`` repository demonstrated: it had pytest-style test
    functions, no ``tests/`` directory and no config file, and fell through to
    ``python -m unittest``, which collected nothing at all.
    """
    if (project_root / "pytest.ini").exists():
        return True
    if (project_root / "conftest.py").exists():
        return True
    if "[tool.pytest" in _read_root_text(project_root, "pyproject.toml"):
        return True
    if "[tool:pytest]" in _read_root_text(project_root, "setup.cfg"):
        return True
    if (project_root / "tests").exists():
        return True
    return any(
        _root_glob_matches(project_root, pattern)
        for pattern in _ROOT_PYTEST_FILE_GLOBS
    )


def detect_python_validation_command(project_root: Path) -> str:
    """Select one Python validation command from deterministic root markers."""
    if repo_uses_pytest(project_root):
        return PYTHON_PYTEST_COMMAND

    if (project_root / "test.py").exists():
        return "python test.py"

    if (project_root / "main.py").exists():
        return "python main.py"

    # Web app entry point (Flask/FastAPI/etc.) - use import check so we
    # validate module load without starting a server that would hang.
    if (project_root / "app.py").exists():
        return 'python -c "import app"'

    return PYTHON_UNITTEST_COMMAND


def resolve_node_package_manager(project_root: Path) -> str:
    """The package manager this repository's own lockfile names."""
    for lockfile, manager in _PACKAGE_MANAGER_LOCKFILES:
        if (project_root / lockfile).exists():
            return manager
    return DEFAULT_PACKAGE_MANAGER


def package_json_scripts(project_root: Path) -> dict[str, str]:
    """The repository's declared scripts, or an empty mapping."""
    raw = _read_root_text(project_root, "package.json")
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    scripts = data.get("scripts") if isinstance(data, dict) else None
    if not isinstance(scripts, dict):
        return {}
    return {
        str(name): str(body)
        for name, body in scripts.items()
        if isinstance(name, str) and isinstance(body, (str, int, float))
    }


def detect_typescript_validation_command(project_root: Path) -> str:
    """Run a script the repository already declares, or nothing at all.

    Only ``<manager> run <script>`` is ever emitted.  No ``install``, no ``npx``
    and no tool the repository did not already commit to: if the declared script
    needs a package that is not present, the command fails at execution and is
    classified as tool-unavailable, which is inconclusive.  Fabricating a build
    command for a repository that declares none would be worse than saying so.
    """
    scripts = package_json_scripts(project_root)
    for name in NODE_SCRIPT_PRIORITY:
        if str(scripts.get(name) or "").strip():
            return f"{resolve_node_package_manager(project_root)} run {name}"
    return ""


def get_default_validation_command(language: str, project_root: Path) -> str:
    lang = (language or "").lower().strip()

    if lang in {"python", "py"}:
        return detect_python_validation_command(project_root)

    if lang in {"typescript", "ts"}:
        return detect_typescript_validation_command(project_root)

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
