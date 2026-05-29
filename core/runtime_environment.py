from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Callable, Mapping


RUNTIME_ENVIRONMENT_OPTIONS = {
    "auto",
    "local_windows",
    "local_linux",
    "local_macos",
    "docker",
    "codespaces",
    "custom",
}

RUNTIME_ENVIRONMENT_LABELS = {
    "auto": "Auto-detect",
    "local_windows": "Local Windows",
    "local_linux": "Local Ubuntu/Linux",
    "local_macos": "Local macOS",
    "docker": "Docker container",
    "codespaces": "GitHub Codespaces",
    "custom": "Custom / other",
}

MAX_CUSTOM_ENVIRONMENT_NAME_LENGTH = 80
MAX_RUNTIME_ENVIRONMENT_NOTES_LENGTH = 1000


def normalize_runtime_environment(value: object) -> str:
    """Normalize a dropdown value without trusting caller input."""
    raw = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "": "auto",
        "windows": "local_windows",
        "win32": "local_windows",
        "linux": "local_linux",
        "ubuntu": "local_linux",
        "macos": "local_macos",
        "mac": "local_macos",
        "darwin": "local_macos",
        "github_codespaces": "codespaces",
        "codespace": "codespaces",
        "other": "custom",
        "custom_other": "custom",
        "unknown": "custom",
    }
    normalized = aliases.get(raw, raw)
    return normalized if normalized in RUNTIME_ENVIRONMENT_OPTIONS else "auto"


def _clean_text(value: object, max_length: int) -> str:
    text = str(value or "").strip()
    if len(text) > max_length:
        return text[:max_length]
    return text


def detect_runtime_environment(
    *,
    env: Mapping[str, str] | None = None,
    dockerenv_exists: Callable[[], bool] | None = None,
    platform: str | None = None,
) -> str:
    """Detect the process runtime without shelling out or mutating files."""
    env_map = os.environ if env is None else env
    if env_map.get("CODESPACES"):
        return "codespaces"

    exists = dockerenv_exists or (lambda: Path("/.dockerenv").exists())
    if exists():
        return "docker"

    platform_name = platform if platform is not None else sys.platform
    if platform_name == "win32":
        return "local_windows"
    if platform_name == "darwin":
        return "local_macos"
    if platform_name.startswith("linux"):
        return "local_linux"
    return "custom"


def build_runtime_environment_state(
    value: object,
    *,
    custom_name: object = "",
    notes: object = "",
    env: Mapping[str, str] | None = None,
    dockerenv_exists: Callable[[], bool] | None = None,
    platform: str | None = None,
) -> dict[str, str]:
    """Return the stable runtime-environment payload stored with a run."""
    normalized = normalize_runtime_environment(value)
    runtime_environment = (
        detect_runtime_environment(
            env=env,
            dockerenv_exists=dockerenv_exists,
            platform=platform,
        )
        if normalized == "auto"
        else normalized
    )

    if runtime_environment == "custom":
        clean_name = _clean_text(custom_name, MAX_CUSTOM_ENVIRONMENT_NAME_LENGTH)
        clean_notes = _clean_text(notes, MAX_RUNTIME_ENVIRONMENT_NOTES_LENGTH)
    else:
        clean_name = ""
        clean_notes = ""

    return {
        "runtime_environment": runtime_environment,
        "runtime_environment_custom_name": clean_name,
        "runtime_environment_notes": clean_notes,
    }


def describe_runtime_environment(
    value: object,
    custom_name: object = "",
    notes: object = "",
) -> str:
    """Render a compact human-readable runtime environment description."""
    runtime_environment = normalize_runtime_environment(value)
    label = RUNTIME_ENVIRONMENT_LABELS.get(runtime_environment, RUNTIME_ENVIRONMENT_LABELS["custom"])

    if runtime_environment != "custom":
        return label

    clean_name = _clean_text(custom_name, MAX_CUSTOM_ENVIRONMENT_NAME_LENGTH)
    clean_notes = _clean_text(notes, MAX_RUNTIME_ENVIRONMENT_NOTES_LENGTH)
    parts = [label]
    if clean_name:
        parts.append(clean_name)
    if clean_notes:
        parts.append(clean_notes)
    return ": ".join(parts[:2]) + (f" - {clean_notes}" if clean_name and clean_notes else "")
