from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath
from typing import Any


MODE_NORMAL_PATCH = "normal_patch"
MODE_PROPOSAL_ONLY = "proposal_only"
MODE_SOURCE_MISSING = "source_missing"
MODE_PATH_OUTSIDE_REPO = "path_outside_repo"
MODE_CODESPACES_LOCAL_PATH_MISMATCH = "codespaces_local_path_mismatch"
MODE_UNGROUNDED_PATCH_BLOCKED = "ungrounded_patch_blocked"
MODE_DEGRADED_CONTEXT = "degraded_context"

_WINDOWS_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:[\\/]")
_WINDOWS_ABSOLUTE_ANYWHERE_RE = re.compile(r"[A-Za-z]:[\\/]")
_HARD_DENY_MODES = {
    MODE_CODESPACES_LOCAL_PATH_MISMATCH,
    MODE_PATH_OUTSIDE_REPO,
}
_ENVIRONMENT_LABELS = {
    "auto": "Auto-detect",
    "local_windows": "Local Windows",
    "local_linux": "Local Ubuntu/Linux",
    "local_macos": "Local macOS",
    "docker": "Docker container",
    "codespaces": "GitHub Codespaces",
    "custom": "Custom / other",
    "repo_relative_or_unknown": "Repo-relative or unknown",
    "unknown": "Unknown",
}


@dataclass(frozen=True)
class HarnessModeDecision:
    mode: str
    can_generate_patch: bool
    can_apply_patch: bool
    reason: str
    warnings: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "can_generate_patch": self.can_generate_patch,
            "can_apply_patch": self.can_apply_patch,
            "reason": self.reason,
            "warnings": list(self.warnings),
            "evidence": dict(self.evidence),
        }


def looks_like_windows_absolute_path(value: object) -> bool:
    text = str(value or "").strip().strip('"').strip("'")
    return bool(_WINDOWS_ABSOLUTE_RE.match(text))


def contains_windows_absolute_path(value: object) -> bool:
    text = str(value or "").strip().strip('"').strip("'")
    return bool(_WINDOWS_ABSOLUTE_ANYWHERE_RE.search(text))


def detect_path_environment(value: object) -> str:
    text = str(value or "").strip().strip('"').strip("'")
    if not text:
        return "unknown"
    if contains_windows_absolute_path(text):
        return "local_windows"
    normalized = text.replace("\\", "/")
    if normalized.startswith("/workspaces/"):
        return "codespaces"
    if normalized.startswith("/Users/"):
        return "local_macos"
    if normalized.startswith("/"):
        return "local_linux"
    return "repo_relative_or_unknown"


def _environment_label(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return "Unknown"
    return _ENVIRONMENT_LABELS.get(text, text.replace("_", " ").title())


def _path_values(*values: object) -> list[str]:
    paths = []
    for value in values:
        text = str(value or "").strip()
        if text:
            paths.append(text)
    return paths


def _is_inside_repo(repo_root: Path, path_value: str) -> bool:
    if looks_like_windows_absolute_path(path_value):
        if not looks_like_windows_absolute_path(str(repo_root)):
            return False
        path = Path(PureWindowsPath(path_value))
    else:
        path = Path(path_value)

    try:
        candidate = path.resolve() if path.is_absolute() else (repo_root / path).resolve()
        candidate.relative_to(repo_root)
        return True
    except (OSError, ValueError):
        return False


def decide_harness_mode(
    *,
    repo_root: str | Path | None,
    runtime_environment: str = "auto",
    request_path: str | None = None,
    target_path: str | None = None,
    source_text: str | None = None,
    source_context_present: bool | None = None,
    grounding_failed: bool = False,
    index_degraded: bool = False,
    patch_gates_passed: bool = True,
) -> HarnessModeDecision:
    repo = Path(repo_root or ".").resolve()
    paths = _path_values(request_path, target_path)
    source_present = (
        bool(source_context_present)
        if source_context_present is not None
        else bool(str(source_text or "").strip())
    )
    evidence = {
        "repo_root": str(repo),
        "runtime_environment": runtime_environment,
        "request_path": request_path or "",
        "target_path": target_path or "",
        "detected_path_environment": detect_path_environment(
            request_path or target_path or ""
        ),
        "source_context_present": source_present,
        "grounding_failed": bool(grounding_failed),
        "index_degraded": bool(index_degraded),
        "patch_gates_passed": bool(patch_gates_passed),
    }

    # Codespaces mismatch is a more useful diagnosis than generic
    # path_outside_repo for pasted local Windows paths.
    if runtime_environment == "codespaces" and any(
        contains_windows_absolute_path(path) for path in paths
    ):
        warning = "Codespaces can only patch files inside the Codespaces workspace."
        return HarnessModeDecision(
            mode=MODE_CODESPACES_LOCAL_PATH_MISMATCH,
            can_generate_patch=False,
            can_apply_patch=False,
            reason=(
                "Codespaces is selected, but the requested path looks like a "
                "local Windows absolute path."
            ),
            warnings=[warning],
            evidence=evidence,
        )

    outside_paths = [path for path in paths if not _is_inside_repo(repo, path)]
    if outside_paths:
        evidence["outside_paths"] = outside_paths
        return HarnessModeDecision(
            mode=MODE_PATH_OUTSIDE_REPO,
            can_generate_patch=False,
            can_apply_patch=False,
            reason="Requested patch target is outside the configured repo root.",
            warnings=[],
            evidence=evidence,
        )

    if not source_present:
        return HarnessModeDecision(
            mode=MODE_SOURCE_MISSING,
            can_generate_patch=False,
            can_apply_patch=False,
            reason="Required source context is missing or empty.",
            warnings=["C.A.T.T.U.S will not guess a patch without source text."],
            evidence=evidence,
        )

    if grounding_failed:
        return HarnessModeDecision(
            mode=MODE_UNGROUNDED_PATCH_BLOCKED,
            can_generate_patch=False,
            can_apply_patch=False,
            reason="Patch candidate grounding failed; existing gates blocked it.",
            warnings=["Patch candidate was not quote-grounded in real source."],
            evidence=evidence,
        )

    if index_degraded:
        return HarnessModeDecision(
            mode=MODE_DEGRADED_CONTEXT,
            can_generate_patch=True,
            can_apply_patch=bool(patch_gates_passed),
            reason="Index/context is degraded, but source text is available.",
            warnings=["Proceeding with source-grounded context only."],
            evidence=evidence,
        )

    return HarnessModeDecision(
        mode=MODE_NORMAL_PATCH,
        can_generate_patch=True,
        can_apply_patch=bool(patch_gates_passed),
        reason="Runtime, path, source, and grounding evidence allow normal patch flow.",
        warnings=[],
        evidence=evidence,
    )


def _decision_requested_path(decision: HarnessModeDecision) -> str:
    evidence = decision.evidence or {}
    for key in ("request_path", "target_path"):
        value = str(evidence.get(key) or "").strip()
        if value:
            return value
    outside_paths = evidence.get("outside_paths")
    if isinstance(outside_paths, list) and outside_paths:
        return str(outside_paths[0])
    return ""


def _deny_reason(decision: HarnessModeDecision, current_env: str, path_env: str) -> str:
    current_label = _environment_label(current_env)
    path_label = _environment_label(path_env)

    if current_env == "codespaces" and path_env == "local_windows":
        return "GitHub Codespaces cannot access files on your Windows computer."
    if path_env == "local_windows" and current_env != "local_windows":
        return f"{current_label} cannot access a {path_label} absolute path."
    if decision.mode == MODE_PATH_OUTSIDE_REPO:
        return "The requested path is outside the active repo root."
    return decision.reason


def _deny_fix(decision: HarnessModeDecision, current_env: str, path_env: str) -> str:
    if current_env == "codespaces" and path_env == "local_windows":
        return (
            "Open/copy the repo inside /workspaces/... or run C.A.T.T.U.S "
            "locally on Windows."
        )
    if path_env == "local_windows" and current_env != "local_windows":
        return (
            "Use a path under the active repo root in this runtime, or run "
            "C.A.T.T.U.S on Windows with the matching repo path."
        )
    if decision.mode == MODE_PATH_OUTSIDE_REPO:
        return (
            "Use a file under the active repo root, or change the repo root "
            "to the project C.A.T.T.U.S should patch."
        )
    return "Use a path that exists inside the active repo root for this runtime."


def format_harness_deny_message(
    decision: HarnessModeDecision,
    *,
    runtime_environment: str | None = None,
    repo_root: str | Path | None = None,
    requested_path: str | None = None,
) -> str:
    if decision.mode not in _HARD_DENY_MODES:
        return ""

    evidence = decision.evidence or {}
    current_env = runtime_environment or str(
        evidence.get("runtime_environment") or "unknown"
    )
    active_repo_root = (
        str(repo_root)
        if repo_root is not None
        else str(evidence.get("repo_root") or "unknown")
    )
    path_value = requested_path or _decision_requested_path(decision) or "unknown"
    path_environment = detect_path_environment(path_value)
    reason = _deny_reason(decision, current_env, path_environment)
    fix = _deny_fix(decision, current_env, path_environment)

    lines = [
        "Cannot run: environment/path mismatch.",
        "",
        f"C.A.T.T.U.S is running in: {_environment_label(current_env)}",
        f"Requested path looks like: {_environment_label(path_environment)}",
        "",
        "Active repo root:",
        active_repo_root,
        "",
        "Requested path:",
        path_value,
        "",
        "Reason:",
        reason,
        "",
        "How to fix:",
        fix,
        "",
        "Gemini was not called. C.A.T.T.U.S will not guess across runtime boundaries.",
    ]
    return "\n".join(lines)
