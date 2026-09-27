from __future__ import annotations

from pathlib import Path
from typing import Any
import json
from core.validator import (
    classify_validation_output,
    detect_no_tests_collected,
    run_validation_command_detailed,
)
from core.diagnostics import extract_locations_from_preflight
from core.validation_command import (
    detect_python_validation_command,
    detect_typescript_validation_command,
)
from core.validation_outcome import (
    CATEGORY_NO_VALIDATION_COMMAND,
    CATEGORY_NO_TESTS_COLLECTED,
    CATEGORY_VALIDATION_BUDGET_EXHAUSTED,
    VALIDATION_INCONCLUSIVE,
    VALIDATION_PASSED,
    outcome_reason,
    validation_outcome,
)

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


#: What a repository would have to add for validation to become possible.  The
#: field test received C#/Python advice for a large TypeScript repository, which
#: is worse than no advice: it points at the wrong ecosystem entirely.
_NO_COMMAND_HINTS: dict[str, str] = {
    "python": (
        "Add tests pytest can collect (a tests/ directory or root test_*.py "
        "files), or supply an explicit validation command."
    ),
    "typescript": (
        "Add or configure an existing package.json script (test, typecheck, "
        "check or build), or supply an explicit validation command. "
        "Dependencies are never installed automatically."
    ),
    "javascript": (
        "Add a package.json test script or a test.js entry point, or supply an "
        "explicit validation command."
    ),
    "csharp": "Add a .csproj/.sln file, or supply an explicit validation command.",
    "cpp": "Add a main.cpp entry point, or supply an explicit validation command.",
    "go": "Add *_test.go files, a main.go or a go.mod, or supply an explicit validation command.",
    "rust": "Add a Cargo.toml, or supply an explicit validation command.",
}

_NO_COMMAND_HINT_ALIASES: dict[str, str] = {
    "py": "python",
    "ts": "typescript",
    "js": "javascript",
    "node": "javascript",
    "nodejs": "javascript",
    "cs": "csharp",
    "c#": "csharp",
    "c++": "cpp",
    "cxx": "cpp",
    "cplusplus": "cpp",
    "golang": "go",
    "rs": "rust",
}


def no_validation_command_hint(language: str) -> str:
    """A hint about the repository's own ecosystem, or a neutral one."""
    lang = (language or "").lower().strip()
    lang = _NO_COMMAND_HINT_ALIASES.get(lang, lang)
    return _NO_COMMAND_HINTS.get(
        lang,
        "Supply an explicit validation command for this repository.",
    )


def detect_default_preflight_command(
    language: str,
    project_root: Path,
    *,
    inventory=None,
) -> str:
    lang = (language or "").lower().strip()
    inventory_paths: tuple[Path, ...] | None = None
    if inventory is not None:
        from core.repository_inventory import (
            validate_repository_inventory,
        )

        validated = validate_repository_inventory(
            project_root,
            inventory,
        )
        inventory_paths = tuple(
            entry.relative_path
            for entry in validated.entries_for_query(None)
        )

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
            has_rust_tests = (
                any(
                    path.match("*_test.rs")
                    for path in inventory_paths
                )
                if inventory_paths is not None
                else any(project_root.rglob("*_test.rs"))
            )
            if has_rust_tests or "tests" in [p.name for p in project_root.iterdir() if p.is_dir()]:
                return "cargo test"
            return "cargo run && echo OK"
        return ""

    # TypeScript
    if lang in {"typescript", "ts"}:
        return detect_typescript_validation_command(project_root)

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
        has_go_tests = (
            any(
                path.match("*_test.go")
                for path in inventory_paths
            )
            if inventory_paths is not None
            else any(project_root.rglob("*_test.go"))
        )
        if has_go_tests:
            return "go test ./..."

        if (project_root / "main.go").exists():
            return "go run ."

        if (project_root / "go.mod").exists():
            return "go test ./..."
        return ""

    # Python
    if lang in {"python", "py"}:
        return detect_python_validation_command(project_root)

    return ""


def run_preflight_validation(
    repo_path: str,
    language: str,
    command: str | None = None,
    *,
    inventory=None,
) -> dict[str, Any]:
    project_root = Path(repo_path).resolve()

    validation_command = command or detect_default_preflight_command(
        language,
        project_root,
        inventory=inventory,
    )

    if not validation_command:
        return {
            "ran": False,
            "ok": None,
            "outcome": VALIDATION_INCONCLUSIVE,
            "command": "",
            "category": CATEGORY_NO_VALIDATION_COMMAND,
            "reason": outcome_reason(CATEGORY_NO_VALIDATION_COMMAND),
            "hint": no_validation_command_hint(language),
            "output": "",
            "locations":[],
            # OPS.VALIDATE.2 - nothing was started, so nothing timed out.
            "timed_out": False,
            "timeout_seconds": None,
            "validation_budget_exhausted": False,
            "python_bytecode_cache_isolated": False,
        }

    run = run_validation_command_detailed(
        validation_command,
        cwd=str(project_root),
    )
    output = run.output

    # A runner that exits 0 having collected nothing has proved nothing.  It is
    # checked here rather than through the full classifier because a *passing*
    # pytest run also prints "collected N items", and running the failure
    # taxonomy over successful output would misread it.
    # OPS.VALIDATE.2 - a run stopped at its budget is ``ok=False``, so it takes
    # the classifier branch below and is settled there.  This asserts the fact
    # up front because it is the one the whole phase turns on: the baseline is
    # inconclusive, and a DEFECT task therefore gets no defect out of it.
    if run.ok:
        if detect_no_tests_collected(
            output,
            exit_code=run.exit_code,
            command=validation_command,
        ):
            category = CATEGORY_NO_TESTS_COLLECTED
            reason = outcome_reason(CATEGORY_NO_TESTS_COLLECTED)
            hint = (
                "No test was collected, so this run says nothing about the "
                "code. Point the validation command at real tests."
            )
        else:
            category = VALIDATION_PASSED
            reason = "Validation passed."
            hint = ""
    else:
        info = classify_validation_output(
            output,
            exit_code=run.exit_code,
            command=validation_command,
            timed_out=run.timed_out,
            timeout_seconds=run.timeout_seconds,
        )
        category = info.get("category", "unknown")
        reason = info.get("reason", "")
        hint = info.get("hint", "")

    outcome = validation_outcome(category=category, ok=run.ok)
    inconclusive = outcome == VALIDATION_INCONCLUSIVE

    return {
        "ran": True,
        # Compatibility: every existing consumer reads a boolean here, and only
        # a genuine pass may be true.  The categorical fact above is what
        # separates a real failure from an inconclusive one.
        "ok": outcome == VALIDATION_PASSED,
        "outcome": outcome,
        "command": validation_command,
        "category": category,
        "reason": reason,
        "hint": hint,
        "output": output[:6000],
        # OPS.VALIDATE.2 - bounded facts about the attempt itself.  No score,
        # no confidence, and no claim about what the checks would have decided.
        "timed_out": bool(run.timed_out),
        "timeout_seconds": run.timeout_seconds,
        "validation_budget_exhausted": (
            category == CATEGORY_VALIDATION_BUDGET_EXHAUSTED
        ),
        "python_bytecode_cache_isolated": bool(
            run.python_bytecode_cache_isolated
        ),
        # Locations are defect evidence.  A validation that established nothing
        # has none to give, and handing CONTROL file:line pairs scraped out of
        # a toolchain error would manufacture exactly the false grounding this
        # phase exists to remove.
        "locations": (
            []
            if inconclusive
            else extract_locations_from_preflight(
                output, repo_path=str(project_root)
            )
        ),
    }
