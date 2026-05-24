"""core/linter_fusion.py — Phase 12.5k

Fuse normalized linter findings (from `.agent/linter/findings.json`) into
Phantom Limb output as read-only evidence. Adds a small suspicion boost per
Phantom Limb candidate when linter findings touch the same file, and emits a
strictly budgeted prompt block for downstream LLM context.

Strict prompt-size controls:
    MAX_LINTER_FINDINGS_IN_PROMPT = 5
    MAX_LINTER_PROMPT_CHARS       = 800
    MAX_LINTER_BOOST              = 0.40

Read-only by design: this module never executes a linter, never installs
packages, never calls a model, and never creates patches.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# Public knobs — kept as module constants so tests can introspect.
MAX_LINTER_FINDINGS_IN_PROMPT = 5
MAX_LINTER_PROMPT_CHARS = 800
MAX_LINTER_BOOST = 0.40

# Per-severity contribution to a phantom candidate's suspicion score.
# Total is capped at MAX_LINTER_BOOST.
_SEVERITY_BOOST: dict[str, float] = {
    "error": 0.25,
    "warning": 0.10,
    "info": 0.05,
}

# Sort precedence for linter findings. Lower number = higher priority.
_SEVERITY_RANK: dict[str, int] = {"error": 0, "warning": 1, "info": 2}

_LINTER_HEADER = "[LINTER HINTS — relevant static-analysis evidence]"


# ---------------- helpers ----------------

def _is_inside(child: Path, parent: Path) -> bool:
    """True iff `child` is the same as or nested below `parent`."""
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _coerce_int(value: Any, default: int = 1) -> int:
    """Coerce a JSON value to a positive int, falling back to `default`."""
    try:
        n = int(value)
        return n if n > 0 else default
    except (TypeError, ValueError):
        return default


def _norm_path(raw: Any) -> str:
    """Normalize a raw path-like value to a forward-slash relative string.

    Returns "" for empty / non-string input. Backslashes (Windows-style) are
    flipped so equality checks across phantom and linter records succeed
    regardless of which host produced each side.
    """
    if not isinstance(raw, str):
        return ""
    s = raw.strip().replace("\\", "/")
    return s


def _linter_sort_key(finding: dict) -> tuple:
    """Sort by (severity, file, line, rule_id) — most actionable first."""
    sev_rank = _SEVERITY_RANK.get(finding.get("severity"), 99)
    line = finding.get("line")
    if not isinstance(line, int) or line < 0:
        line = 10**9  # push line-less findings to the end of their bucket
    return (sev_rank, finding.get("file") or "", line, finding.get("rule_id") or "")


def _format_finding_line(finding: dict) -> str:
    """Render a single finding as one bullet in the prompt block.

    Format mirrors the spec example:
        - pricing.ts:12 eslint/no-undef error: multiplyCents is not defined
    """
    file = finding.get("file") or "?"
    line = finding.get("line") if isinstance(finding.get("line"), int) else 1
    tool = finding.get("tool") or "?"
    rule = finding.get("rule_id") or "?"
    sev = finding.get("severity") or "info"
    message = finding.get("message") or ""
    return f"- {file}:{line} {tool}/{rule} {sev}: {message}"


# ---------------- loader ----------------

def load_linter_findings(repo_path: str | Path) -> list[dict]:
    """Read and validate `.agent/linter/findings.json` under `repo_path`.

    Returns [] when:
      - the repo path is invalid,
      - the findings file does not exist,
      - the file is not valid JSON,
      - the top-level value is not a list,
      - every entry is malformed.

    Malformed entries are silently skipped (logged via skipped_count in the
    adapter; here we just drop them). Path safety: refuses to read anything
    that resolves outside `repo_path`.
    """
    try:
        repo_root = Path(repo_path).resolve()
    except Exception:
        return []
    if not repo_root.is_dir():
        return []

    findings_path = repo_root / ".agent" / "linter" / "findings.json"
    try:
        resolved = findings_path.resolve()
    except Exception:
        return []
    if not _is_inside(resolved, repo_root):
        return []
    if not resolved.is_file():
        return []

    try:
        data = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    if not isinstance(data, list):
        return []

    out: list[dict] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        file_rel = _norm_path(entry.get("file"))
        if not file_rel:
            continue
        severity = entry.get("severity")
        if severity not in _SEVERITY_BOOST:
            continue
        message = entry.get("message")
        if message is not None and not isinstance(message, str):
            continue
        rule_id = entry.get("rule_id")
        if rule_id is not None and not isinstance(rule_id, str):
            continue
        tool = entry.get("tool")
        if tool is not None and not isinstance(tool, str):
            continue
        out.append({
            "tool": tool or "",
            "file": file_rel,
            "line": _coerce_int(entry.get("line"), 1),
            "column": _coerce_int(entry.get("column"), 1),
            "severity": severity,
            "rule_id": rule_id or "",
            "message": message or "",
            "symbol": entry.get("symbol"),
            "source": entry.get("source", "external_linter"),
        })
    return out


# ---------------- fusion ----------------

def fuse_into_phantom(
    phantom_findings: list[dict],
    linter_findings: list[dict],
) -> dict:
    """Annotate `phantom_findings` with linter evidence and emit a prompt block.

    Returns a dict with three keys:
      - "findings": phantom findings copied into new dicts, each annotated
        with `linter_evidence` (sorted by severity/line) and
        `linter_suspicion_boost` (capped at MAX_LINTER_BOOST).
      - "prompt_block": a string ≤ MAX_LINTER_PROMPT_CHARS containing at
        most MAX_LINTER_FINDINGS_IN_PROMPT bullets, or "" when no relevant
        findings exist. Only findings whose file matches a phantom candidate
        are eligible — irrelevant files are never injected.
      - "linter_summary": {"total_linter_findings", "matched_files"}.

    Input dicts are NOT mutated.
    """
    phantom_in = [f for f in (phantom_findings or []) if isinstance(f, dict)]
    linter_in = [f for f in (linter_findings or []) if isinstance(f, dict)]

    by_file: dict[str, list[dict]] = {}
    for lf in linter_in:
        key = _norm_path(lf.get("file"))
        if not key:
            continue
        if lf.get("severity") not in _SEVERITY_BOOST:
            continue
        by_file.setdefault(key, []).append(lf)

    fused: list[dict] = []
    matched_files: set[str] = set()
    for finding in phantom_in:
        new = dict(finding)
        key = _norm_path(new.get("file"))
        matches = by_file.get(key, []) if key else []
        if matches:
            matches_sorted = sorted(matches, key=_linter_sort_key)
            boost = 0.0
            for m in matches_sorted:
                boost += _SEVERITY_BOOST.get(m.get("severity"), 0.0)
                if boost >= MAX_LINTER_BOOST:
                    boost = MAX_LINTER_BOOST
                    break
            new["linter_evidence"] = [
                {
                    "tool": m.get("tool"),
                    "rule_id": m.get("rule_id"),
                    "severity": m.get("severity"),
                    "line": m.get("line"),
                    "message": m.get("message"),
                }
                for m in matches_sorted
            ]
            new["linter_suspicion_boost"] = round(min(boost, MAX_LINTER_BOOST), 4)
            matched_files.add(key)
        fused.append(new)

    # Build the prompt block from linter findings whose file is touched by a
    # phantom candidate. Files no phantom rule cares about are NOT injected —
    # Phantom Limb is the routing layer; linter is supporting evidence.
    relevant: list[dict] = []
    phantom_files = {_norm_path(f.get("file")) for f in phantom_in}
    phantom_files.discard("")
    for f in phantom_files:
        relevant.extend(by_file.get(f, []))
    relevant.sort(key=_linter_sort_key)

    prompt_block = _build_prompt_block(relevant)

    return {
        "findings": fused,
        "prompt_block": prompt_block,
        "linter_summary": {
            "total_linter_findings": len(linter_in),
            "matched_files": len(matched_files),
        },
    }


def _build_prompt_block(findings: list[dict]) -> str:
    """Render a budgeted prompt block. Returns "" when nothing fits."""
    if not findings:
        return ""
    lines: list[str] = [_LINTER_HEADER]
    char_count = len(_LINTER_HEADER)
    used = 0
    for finding in findings:
        if used >= MAX_LINTER_FINDINGS_IN_PROMPT:
            break
        bullet = _format_finding_line(finding)
        # +1 for the newline separating this bullet from the previous line.
        projected = char_count + 1 + len(bullet)
        if projected > MAX_LINTER_PROMPT_CHARS:
            break
        lines.append(bullet)
        char_count = projected
        used += 1
    if used == 0:
        return ""
    return "\n".join(lines)


def fuse_for_repo(
    repo_path: str | Path,
    phantom_findings: list[dict],
) -> dict:
    """Convenience: load `.agent/linter/findings.json` and fuse it in one call.

    Always returns the standard fusion dict; on any load failure it falls back
    to an empty linter list so callers never have to special-case "no linter".
    """
    linter = load_linter_findings(repo_path)
    return fuse_into_phantom(phantom_findings, linter)
