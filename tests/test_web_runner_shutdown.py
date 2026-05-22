"""Web runner lifecycle tests."""
from __future__ import annotations

import pytest


def test_web_runner_requests_inspector_cleanup_after_ctrl_c(monkeypatch):
    from web import runner

    calls = []

    class FakeApp:
        def run(self, **kwargs):
            calls.append(("run", kwargs))
            raise KeyboardInterrupt

    monkeypatch.setattr(
        runner,
        "stop_mcp_inspectors",
        lambda: calls.append(("cleanup", {})) or 1,
    )

    with pytest.raises(KeyboardInterrupt):
        runner.run_web_app(FakeApp(), host="127.0.0.1", port=5000)

    assert calls == [
        ("run", {"host": "127.0.0.1", "port": 5000}),
        ("cleanup", {}),
    ]
