from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from web.runner import run_agent_web
from core.validator import run_validation_command


IGNORE_DIRS = {
    ".git",
    ".agent",
    "target",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "dist",
    "build",
    ".venv",
    "venv",
}
IGNORE_FILES = {
    "Cargo.lock",
}

def discover_case_files(cases_root: Path) -> list[Path]:
    """
    Supports both:
    benchmarks/cases/go_wallet_transfer/case.json
    benchmarks/cases/go/go_wallet_transfer/case.json
    """
    return sorted(cases_root.rglob("case.json"))


def load_case(case_file: Path) -> dict:
    with case_file.open("r", encoding="utf-8") as f:
        case = json.load(f)

    case.setdefault("category", "uncategorized")
    case.setdefault("difficulty", "unknown")

    # Useful for report/debug
    case["_case_file"] = str(case_file)
    case["_case_dir"] = str(case_file.parent)

    return case

def _ignore_patterns(dir_path: str, names: list[str]):
    ignored = []
    for name in names:
        if name in IGNORE_DIRS:
            ignored.append(name)
        if name.endswith(".exe"):
            ignored.append(name)
    return ignored


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def snapshot_files(repo: Path) -> dict[str, str]:
    out: dict[str, str] = {}

    for p in repo.rglob("*"):
        if not p.is_file():
            continue

        rel = p.relative_to(repo).as_posix()
        parts = set(rel.split("/"))

        if parts & IGNORE_DIRS or p.name in IGNORE_FILES:
            continue

        if p.name.endswith(".exe"):
            continue

        try:
            out[rel] = file_hash(p)
        except Exception:
            pass

    return out


def changed_files(before: dict[str, str], after: dict[str, str]) -> list[str]:
    keys = set(before) | set(after)
    return sorted(
        k for k in keys
        if before.get(k) != after.get(k)
    )

def run_case(case_file: Path) -> dict[str, Any]:
    case = load_case(case_file)
    case_dir = case_file.parent

    name = case.get("name") or case_dir.name
    buggy_repo = case_dir / "buggy_repo"
    if not buggy_repo.exists():
        raise FileNotFoundError(f"Missing buggy_repo: {buggy_repo}")

    validation_command = case.get("validation_command", "").strip()
    patch_style = case.get("patch_style", "balanced")
    agent_mode = case.get("agent_mode", "reviewer")
    prompt = case.get("prompt", "").strip()

    if validation_command and "Validation command:" not in prompt:
        prompt += f"\n\nValidation command: {validation_command}"

    started = time.time()

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        temp_repo = Path(tmp) / "repo"
        shutil.copytree(
            buggy_repo,
            temp_repo,
            ignore=_ignore_patterns,
        )

        before = snapshot_files(temp_repo)

        result = run_agent_web(
            query=prompt,
            repo_path=str(temp_repo),
            agent_mode=agent_mode,
            project_tag=f"bench-{name}",
            patch_style=patch_style,
            ignore_repo_dna=False,
        )

        after = snapshot_files(temp_repo)
        changed = changed_files(before, after)

        ok = None
        validation_output = ""
        if validation_command:
            ok, validation_output = run_validation_command(
                validation_command,
                cwd=str(temp_repo),
            )

        expected_changed = set(case.get("expected_changed_files", []))
        forbidden_changed = set(case.get("forbidden_changed_files", []))

        missing_expected = sorted(expected_changed - set(changed))
        touched_forbidden = sorted(forbidden_changed & set(changed))

        success = bool(ok)
        if missing_expected:
            success = False
        if touched_forbidden:
            success = False

        return {
            "name": name,
            "success": success,
            "validation_ok": ok,
            "patch_style": patch_style,
            "language": case.get("language"),
            "case_file": str(case_file),            
            "duration_sec": round(time.time() - started, 2),
            "difficulty": case.get("difficulty"),
            "category": case.get("category", "uncategorized"),
            "changed_files": changed,
            "missing_expected_files": missing_expected,
            "touched_forbidden_files": touched_forbidden,
            "validation_output": validation_output[-4000:],
            "agent_answer": result.get("answer", ""),
            "agent_validation": result.get("validation", ""),
        }


def discover_cases(root: Path) -> list[Path]:
    cases_root = root / "cases"
    if not cases_root.exists():
        return []

    return discover_case_files(cases_root)

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", help="Run one case by folder name")
    parser.add_argument("--json", action="store_true", help="Print full JSON report")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    cases = discover_cases(root)
    seen_names = set()
    if args.case:
        filtered = []
        for case_file in cases:
            try:
                case = load_case(case_file)
                case_name = case.get("name") or case_file.parent.name
                if case_name == args.case or case_file.parent.name == args.case:
                    filtered.append(case_file)
            except Exception:
                continue
        cases = filtered

    if not cases:
        print("No benchmark cases found.")
        return 1

    results = []
    for case_file in cases:
        case_label = case_file.parent.name

        try:
            case = load_case(case_file)
            case_name = case.get("name") or case_label

            if case_name in seen_names:
                raise ValueError(f"Duplicate benchmark case name: {case_name}")
            seen_names.add(case_name)

            print(f"\n🧪 Running benchmark: {case_name}")
            res = run_case(case_file)
        except Exception as e:
            res = {
                "name": case_file.parent.name,
                "success": False,
                "error": repr(e),
            }

        results.append(res)

        status = "✅ PASS" if res.get("success") else "❌ FAIL"
        print(f"{status} {res.get('name')}")
        if res.get("changed_files"):
            print("Changed:", ", ".join(res["changed_files"]))
        if res.get("missing_expected_files"):
            print("Missing expected:", res["missing_expected_files"])
        if res.get("touched_forbidden_files"):
            print("Touched forbidden:", res["touched_forbidden_files"])
        if res.get("error"):
            print("Error:", res["error"])

    passed = sum(1 for r in results if r.get("success"))
    total = len(results)

    report = {
        "passed": passed,
        "total": total,
        "success_rate": passed / total if total else 0,
        "results": results,
    }

    out_dir = PROJECT_ROOT / ".agent" / "benchmarks"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"benchmark_report_{int(time.time())}.json"
    out_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"\n📊 Benchmark: {passed}/{total} passed")
    print(f"Report written to: {out_path}")

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))

    return 0 if passed == total else 2


if __name__ == "__main__":
    raise SystemExit(main())