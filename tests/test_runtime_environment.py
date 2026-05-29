from __future__ import annotations

import pytest

from core.runtime_environment import (
    MAX_CUSTOM_ENVIRONMENT_NAME_LENGTH,
    MAX_RUNTIME_ENVIRONMENT_NOTES_LENGTH,
    build_runtime_environment_state,
    describe_runtime_environment,
    detect_runtime_environment,
    normalize_runtime_environment,
)


def test_auto_detect_codespaces_from_env_var():
    assert detect_runtime_environment(
        env={"CODESPACES": "true"},
        dockerenv_exists=lambda: False,
        platform="linux",
    ) == "codespaces"


def test_auto_detect_docker_from_injected_dockerenv_probe():
    assert detect_runtime_environment(
        env={},
        dockerenv_exists=lambda: True,
        platform="linux",
    ) == "docker"


@pytest.mark.parametrize(
    ("platform_name", "expected"),
    [
        ("win32", "local_windows"),
        ("darwin", "local_macos"),
        ("linux", "local_linux"),
        ("linux2", "local_linux"),
    ],
)
def test_auto_detect_local_platforms(platform_name, expected):
    assert detect_runtime_environment(
        env={},
        dockerenv_exists=lambda: False,
        platform=platform_name,
    ) == expected


@pytest.mark.parametrize(
    "value",
    [
        "auto",
        "local_windows",
        "local_linux",
        "local_macos",
        "docker",
        "codespaces",
        "custom",
    ],
)
def test_normalize_valid_dropdown_values(value):
    assert normalize_runtime_environment(value) == value


def test_custom_environment_preserves_sanitized_custom_name_and_notes():
    state = build_runtime_environment_state(
        "custom",
        custom_name="  Remote Linux VM  ",
        notes="  Runs over SSH with repo mounted at /workspace  ",
    )

    assert state == {
        "runtime_environment": "custom",
        "runtime_environment_custom_name": "Remote Linux VM",
        "runtime_environment_notes": "Runs over SSH with repo mounted at /workspace",
    }
    description = describe_runtime_environment(
        state["runtime_environment"],
        state["runtime_environment_custom_name"],
        state["runtime_environment_notes"],
    )
    assert "Remote Linux VM" in description
    assert "repo mounted at /workspace" in description


def test_custom_environment_name_and_notes_are_length_limited():
    state = build_runtime_environment_state(
        "custom",
        custom_name="n" * (MAX_CUSTOM_ENVIRONMENT_NAME_LENGTH + 20),
        notes="x" * (MAX_RUNTIME_ENVIRONMENT_NOTES_LENGTH + 20),
    )

    assert len(state["runtime_environment_custom_name"]) == MAX_CUSTOM_ENVIRONMENT_NAME_LENGTH
    assert len(state["runtime_environment_notes"]) == MAX_RUNTIME_ENVIRONMENT_NOTES_LENGTH


def test_invalid_environment_value_safely_normalizes_to_auto_detected_value():
    state = build_runtime_environment_state(
        "surprise_os",
        custom_name="ignored",
        notes="ignored",
        env={},
        dockerenv_exists=lambda: False,
        platform="darwin",
    )

    assert normalize_runtime_environment("surprise_os") == "auto"
    assert state == {
        "runtime_environment": "local_macos",
        "runtime_environment_custom_name": "",
        "runtime_environment_notes": "",
    }
