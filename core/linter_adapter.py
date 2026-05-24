"""core/linter_adapter.py — Phase 12.5j

Read-only adapter that normalizes external linter JSON output into uniform
project-local findings. Downstream consumers (Phantom Limb, CONTROL, graph
ranking) treat all sources the same way once they pass through here.

v1 supports ESLint and Pylint. The adapter never executes the linter, never
installs anything, never calls a model, and never modifies the patching
pipeline — it is purely a JSON → JSON transform.

Normalized finding shape:
    {
        "tool": "eslint" | "pylint",
        "file": "relative/path",
        "line": int,
        "column": int,
        "severity": "error" | "warning" | "info",
        "rule_id": "...",
        "message": "...",
        "symbol": None,
        "source": "external_linter"
    }
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ESLint encodes severity as a small int: 0 = off (filtered out by --format
# json anyway), 1 = warn, 2 = error.
_ESLINT_SEVERITY = {1: "warning", 2: "error"}

# Pylint's "type" field is a string. convention/refactor/info all collapse to
# our advisory "info" bucket because they are stylistic, not bugs.
_PYLINT_SEVERITY = {
    "error": "error",
    "fatal": "error",
    "warning": "warning",
    "refactor": "info",
    "convention": "info",
    "info": "info",
}


@dataclass
class NormalizeResult:
    findings: list[dict] = field(default_factory=list)
    skipped: int = 0


def _is_inside(child: Path, parent: Path) -> bool:
    """True iff `child` is the same as or nested below `parent`."""
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _normalize_path(raw: Any, repo_root: Path) -> str | None:
    """Resolve `raw` against `repo_root` and return a slash-style relative path.

    Returns None when:
      - the input is empty or non-string-like,
      - the path resolves outside `repo_root` (path-traversal guard),
      - any step of resolution raises.

    Backslashes are converted to forward slashes up front so a Windows-style
    ESLint report (e.g. `C:\\repo\\src\\foo.js`) normalizes consistently on any
    host OS.
    """
    if raw is None:
        return None
    raw_str = str(raw).strip()
    if not raw_str:
        return None
    # Windows reports use `\`; normalize before handing to pathlib so the same
    # input works the same on Linux/macOS hosts too.
    raw_str = raw_str.replace("\\", "/")
    try:
        p = Path(raw_str)
    except Exception:
        return None
    try:
        if p.is_absolute():
            abs_p = p.resolve()
        else:
            abs_p = (repo_root / p).resolve()
    except Exception:
        return None
    if not _is_inside(abs_p, repo_root):
        return None
    try:
        rel = abs_p.relative_to(repo_root)
    except ValueError:
        return None
    return rel.as_posix()


def _coerce_int(value: Any, default: int = 1) -> int:
    """Coerce to a positive int. Falls back to `default` for None/garbage.

    Linters sometimes emit `null` or `0` for line/column on file-level issues;
    we always emit at least 1 so consumers never have to special-case it.
    """
    try:
        n = int(value)
        return n if n > 0 else default
    except (TypeError, ValueError):
        return default


def _to_finding(
    *,
    tool: str,
    file_rel: str,
    line: int,
    column: int,
    severity: str,
    rule_id: str,
    message: str,
    symbol: str | None,
) -> dict:
    return {
        "tool": tool,
        "file": file_rel,
        "line": line,
        "column": column,
        "severity": severity,
        "rule_id": rule_id,
        "message": message,
        "symbol": symbol,
        "source": "external_linter",
    }


def normalize_eslint_report(report: Any, repo_root: Path) -> NormalizeResult:
    """Normalize an ESLint JSON report (list of file entries with messages).

    Each ESLint file entry looks like:
        {"filePath": "...", "messages": [{"ruleId", "severity", "message",
         "line", "column", ...}, ...]}
    """
    result = NormalizeResult()
    if not isinstance(report, list):
        result.skipped += 1
        return result
    for entry in report:
        if not isinstance(entry, dict):
            result.skipped += 1
            continue
        messages = entry.get("messages")
        if not isinstance(messages, list):
            # An entry with no messages list is a "clean file" — silently skip
            # without counting (it's expected, not malformed).
            if messages is None:
                continue
            result.skipped += 1
            continue
        rel = _normalize_path(entry.get("filePath"), repo_root)
        if rel is None:
            # File is outside the repo (or path is malformed). Count each
            # message we drop so the operator can see real attrition.
            result.skipped += len(messages)
            continue
        for msg in messages:
            if not isinstance(msg, dict):
                result.skipped += 1
                continue
            severity = _ESLINT_SEVERITY.get(msg.get("severity"))
            if severity is None:
                result.skipped += 1
                continue
            rule_id = msg.get("ruleId")
            if rule_id is None:
                rule_id = ""
            elif not isinstance(rule_id, str):
                result.skipped += 1
                continue
            message = msg.get("message")
            if not isinstance(message, str):
                result.skipped += 1
                continue
            result.findings.append(_to_finding(
                tool="eslint",
                file_rel=rel,
                line=_coerce_int(msg.get("line"), 1),
                column=_coerce_int(msg.get("column"), 1),
                severity=severity,
                rule_id=rule_id,
                message=message,
                symbol=None,
            ))
    return result


def normalize_pylint_report(report: Any, repo_root: Path) -> NormalizeResult:
    """Normalize a Pylint JSON report (flat list of findings).

    Each Pylint entry looks like:
        {"type": "warning", "path": "src/foo.py", "line": 10, "column": 4,
         "symbol": "unused-import", "message-id": "W0611", "message": "...",
         "module": "src.foo", "obj": ""}
    """
    result = NormalizeResult()
    if not isinstance(report, list):
        result.skipped += 1
        return result
    for entry in report:
        if not isinstance(entry, dict):
            result.skipped += 1
            continue
        rel = _normalize_path(entry.get("path"), repo_root)
        if rel is None:
            result.skipped += 1
            continue
        ptype = entry.get("type")
        if not isinstance(ptype, str):
            result.skipped += 1
            continue
        severity = _PYLINT_SEVERITY.get(ptype.strip().lower())
        if severity is None:
            result.skipped += 1
            continue
        # Prefer the stable numeric code (W0611) over the symbolic name
        # (unused-import) because the latter can vary across Pylint versions.
        rule_id = entry.get("message-id") or entry.get("symbol") or ""
        if not isinstance(rule_id, str):
            result.skipped += 1
            continue
        message = entry.get("message")
        if not isinstance(message, str):
            result.skipped += 1
            continue
        result.findings.append(_to_finding(
            tool="pylint",
            file_rel=rel,
            line=_coerce_int(entry.get("line"), 1),
            column=_coerce_int(entry.get("column"), 1),
            severity=severity,
            rule_id=rule_id,
            message=message,
            symbol=None,
        ))
    return result


def _default_output_path(repo_root: Path) -> Path:
    return repo_root / ".agent" / "linter" / "findings.json"


def write_findings(
    repo_root: Path,
    findings: list[dict],
    *,
    output_path: Path | None = None,
) -> Path:
    """Write `findings` to .agent/linter/findings.json under `repo_root`.

    Creates the output directory if it does not exist yet. Returns the
    resolved output path so the caller can echo it back to the user.
    """
    if output_path is None:
        output_path = _default_output_path(repo_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(findings, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def _load_report(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"{label} report is not valid JSON ({path}): {e}") from e
    except OSError as e:
        raise FileNotFoundError(f"{label} report could not be read ({path}): {e}") from e


def import_linter_findings(
    repo_path: str | Path,
    *,
    eslint_json: str | Path | None = None,
    pylint_json: str | Path | None = None,
    output_path: str | Path | None = None,
) -> dict:
    """Top-level entry point shared by the CLI and tests.

    Reads the requested JSON reports, normalizes their findings against
    `repo_path`, writes `.agent/linter/findings.json`, and returns a summary
    dict suitable for printing.

    Raises:
        FileNotFoundError: when `repo_path` is not a directory or an explicitly
            requested report file is missing.
        ValueError: when a report file does not contain valid JSON.
    """
    repo_root = Path(repo_path).resolve()
    if not repo_root.is_dir():
        raise FileNotFoundError(f"repo_path is not a directory: {repo_path}")

    all_findings: list[dict] = []
    total_skipped = 0

    if eslint_json is not None:
        eslint_p = Path(eslint_json)
        if not eslint_p.is_file():
            raise FileNotFoundError(f"eslint report not found: {eslint_json}")
        data = _load_report(eslint_p, "eslint")
        res = normalize_eslint_report(data, repo_root)
        all_findings.extend(res.findings)
        total_skipped += res.skipped

    if pylint_json is not None:
        pylint_p = Path(pylint_json)
        if not pylint_p.is_file():
            raise FileNotFoundError(f"pylint report not found: {pylint_json}")
        data = _load_report(pylint_p, "pylint")
        res = normalize_pylint_report(data, repo_root)
        all_findings.extend(res.findings)
        total_skipped += res.skipped

    if eslint_json is None and pylint_json is None:
        # Caller-side check ensures this branch isn't reached from the CLI;
        # the library API still gives a sane response when invoked directly.
        out_path = write_findings(repo_root, [], output_path=Path(output_path) if output_path else None)
        return {"imported": 0, "skipped": 0, "output": str(out_path)}

    out_path = write_findings(
        repo_root,
        all_findings,
        output_path=Path(output_path) if output_path else None,
    )
    return {
        "imported": len(all_findings),
        "skipped": total_skipped,
        "output": str(out_path),
    }
