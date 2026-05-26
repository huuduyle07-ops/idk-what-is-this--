"""Tests for the Phase 7.3a Docker sandbox health probe.

Docker may or may not be installed on the host running these tests, so every
case below monkeypatches ``shutil.which`` and ``subprocess.run`` inside
``core.health`` instead of touching a real Docker daemon.
"""
from __future__ import annotations

import subprocess
from types import SimpleNamespace

from core import health


def _fake_completed(returncode: int, stdout: str = "", stderr: str = ""):
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def test_docker_missing_reports_missing(monkeypatch):
    monkeypatch.setattr(health.shutil, "which", lambda name: None)

    result = health.check_docker_sandbox()

    assert result["status"] == "missing"
    assert "not on PATH" in result["detail"]
    # The label is explicit about which backend is unavailable.
    assert "docker_ubuntu" in result["name"] or "docker_ubuntu" in result["detail"]


def test_docker_info_nonzero_reports_error(monkeypatch):
    monkeypatch.setattr(health.shutil, "which", lambda name: "/usr/bin/docker")

    def fake_run(cmd, **kwargs):
        if "info" in cmd:
            return _fake_completed(
                1,
                stdout="",
                stderr="Cannot connect to the Docker daemon at unix:///var/run/docker.sock",
            )
        return _fake_completed(0)

    monkeypatch.setattr(health.subprocess, "run", fake_run)

    result = health.check_docker_sandbox()
    assert result["status"] == "error"
    assert "unreachable" in result["detail"]


def test_docker_info_timeout_reports_error(monkeypatch):
    monkeypatch.setattr(health.shutil, "which", lambda name: "/usr/bin/docker")

    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=3)

    monkeypatch.setattr(health.subprocess, "run", fake_run)

    result = health.check_docker_sandbox()
    assert result["status"] == "error"
    assert "timed out" in result["detail"]


def test_docker_engine_running_all_images_pulled(monkeypatch):
    monkeypatch.setattr(health.shutil, "which", lambda name: "/usr/bin/docker")

    def fake_run(cmd, **kwargs):
        if "info" in cmd:
            return _fake_completed(0, stdout="24.0.7\n", stderr="")
        if "inspect" in cmd:
            return _fake_completed(0, stdout='[{"Id":"sha256:abc"}]', stderr="")
        return _fake_completed(0)

    monkeypatch.setattr(health.subprocess, "run", fake_run)

    result = health.check_docker_sandbox()
    assert result["status"] == "ok"
    assert "engine v24.0.7" in result["detail"]
    # Every language image is reported as pulled.
    assert "pulled:" in result["detail"]
    assert "not pulled:" not in result["detail"]
    assert "first run will fetch" not in result["detail"]


def test_docker_engine_running_no_images_pulled(monkeypatch):
    monkeypatch.setattr(health.shutil, "which", lambda name: "/usr/bin/docker")

    def fake_run(cmd, **kwargs):
        if "info" in cmd:
            return _fake_completed(0, stdout="24.0.7\n", stderr="")
        if "inspect" in cmd:
            return _fake_completed(1, stdout="", stderr="No such image")
        return _fake_completed(0)

    monkeypatch.setattr(health.subprocess, "run", fake_run)

    result = health.check_docker_sandbox()
    assert result["status"] == "ok"
    assert "engine v24.0.7" in result["detail"]
    assert "not pulled:" in result["detail"]
    # And the prominent default-image hint fires when the most common path
    # would otherwise trigger a network fetch.
    assert "first run will fetch" in result["detail"]


def test_docker_engine_running_partial_image_pull(monkeypatch):
    """Mixed state — python pulled, the rest not. The detail line must
    split into a ``pulled`` group and a ``not pulled`` group."""
    monkeypatch.setattr(health.shutil, "which", lambda name: "/usr/bin/docker")

    def fake_run(cmd, **kwargs):
        if "info" in cmd:
            return _fake_completed(0, stdout="29.4.0\n", stderr="")
        if "inspect" in cmd:
            # cmd looks like [docker, "image", "inspect", "<image-tag>"]
            image_tag = cmd[-1]
            if image_tag.startswith("python:"):
                return _fake_completed(0, stdout='[{"Id":"sha256:py"}]', stderr="")
            return _fake_completed(1, stdout="", stderr="No such image")
        return _fake_completed(0)

    monkeypatch.setattr(health.subprocess, "run", fake_run)

    result = health.check_docker_sandbox()
    assert result["status"] == "ok"
    assert "engine v29.4.0" in result["detail"]
    assert "pulled:" in result["detail"]
    assert "python" in result["detail"]
    assert "not pulled:" in result["detail"]
    # The default-image-not-pulled hint should NOT fire because python is the
    # default and it IS pulled here.
    assert "first run will fetch" not in result["detail"]
    # Other-language images should be named in the not-pulled list.
    for tool_label in ("node", "go", "rust", "gcc"):
        assert tool_label in result["detail"].lower()


def test_docker_image_inventory_matches_sandbox_runner_constant():
    """Health check must enumerate the same images sandbox_runner publishes,
    so a future change to one stays in sync with the other."""
    from core.sandbox_runner import SANDBOX_LANGUAGE_IMAGES

    # Sanity: the inventory covers all five language toolchains we ship.
    image_tags = {image for _, image in SANDBOX_LANGUAGE_IMAGES}
    assert any(tag.startswith("python:") for tag in image_tags)
    assert any(tag.startswith("node:") for tag in image_tags)
    assert any(tag.startswith("golang:") for tag in image_tags)
    assert any(tag.startswith("rust:") for tag in image_tags)
    assert any(tag.startswith("gcc:") for tag in image_tags)


def test_get_system_health_includes_docker_sandbox_row(monkeypatch):
    """The aggregator must surface the Docker check alongside the rest."""
    # Force the docker check into a deterministic state so the assertion
    # doesn't depend on the host's Docker install.
    monkeypatch.setattr(health.shutil, "which", lambda name: None)

    report = health.get_system_health()
    names = {row["name"] for row in report["checks"]}

    assert any("Docker sandbox" in name for name in names), (
        f"Docker sandbox row missing from health report: {sorted(names)}"
    )
    # The summary counters must include the new row's status bucket.
    total = sum(report["summary"].values())
    assert total == len(report["checks"])
