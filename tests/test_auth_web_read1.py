"""AUTH.WEB.READ.1: trusted Host identity before any safe-method read.

DNS rebinding: a page at http://evil.example:<port> whose name resolves to this
server reaches it with ``Host: evil.example:<port>`` and, for a plain-HTTP name,
without Origin or Fetch Metadata. The boundary refuses every GET, HEAD and
OPTIONS request whose Host is not a projection of the AUTH.WEB.1 allowed
origins, before Flask routes it. Mutations keep the AUTH.WEB.1 gate unchanged.

Direct Flask/WSGI and real loopback-listener checks against synthetic files:
no model, database or external network. Real Chromium coverage lives in
tests/test_auth_web_read1_browser.py.
"""
from __future__ import annotations

import ast
import builtins
import hashlib
import json
import os
import re
import socket
import statistics
import time
from pathlib import Path
from urllib.parse import urlencode

import pytest
from werkzeug.test import EnvironBuilder, TestResponse, run_wsgi_app
from werkzeug.wrappers import Request

from tests.test_auth_web1 import _definitions, configure_offline_web

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
TRUSTED = "http://127.0.0.1:5000"
TRUSTED_HOST = "127.0.0.1:5000"
ATTACKER_HOST = "evil.example:5000"
MARKER = "auth_web_read1_marker_7f3c9a"
TOKEN = "auth-web-read1-distinctive-token-Qm4Z8"
SESSION_ID = "20260917120000"
DREAM_DATE, DREAM_RUN = "2026-09-17", "120000-run"
CSRF_META = re.compile(r'<meta name="cattus-csrf-token" content="([A-Za-z0-9_-]{43})">')
REFUSAL_CODES = {"host_missing", "host_malformed", "host_ambiguous", "host_not_allowed"}
SAFE_METHODS = ("GET", "HEAD", "OPTIONS")
UNTRUSTED_FOR_DEFAULT_SOCKET = (
    ATTACKER_HOST, "localhost:5000", "[::1]:5000", "127.0.0.1:7999", "127.0.0.1", "user@127.0.0.1:5000",
)

SHELL_STATIC = "public_shell_static"
OPERATIONAL = "health_operational"
AUTH_BOOTSTRAP = "auth_bootstrap"
PROJECT = "project_repository_data"
REPORTS = "source_evidence_report_history"
DREAM = "dream_reports_artifacts"
INTERNAL = "session_run_debug_internal"

# Bounded GET/HEAD inventory (every rule in app.url_map). Every category needs
# a trusted Host; NON_SENSITIVE and AUTH_DEPENDENT only record the read policy.
GET_ROUTE_CLASSIFICATION = {
    "/": SHELL_STATIC,
    "/new": SHELL_STATIC,
    "/static/<path:filename>": SHELL_STATIC,
    "/help": SHELL_STATIC,
    "/health": OPERATIONAL,
    "/tools/registry": OPERATIONAL,
    "/dream/taxonomy": OPERATIONAL,
    "/auth/session": AUTH_BOOTSTRAP,
    "/benchmarks/cases": PROJECT,
    "/benchmarks/case-defaults": PROJECT,
    "/graph/evidence_spread": PROJECT,
    "/graph/explainability/view": PROJECT,
    "/lessons/list": PROJECT,
    "/lessons/duplicates": PROJECT,
    "/lessons/anti/report": PROJECT,
    "/lessons/anti/reverse-dream-plan": PROJECT,
    "/lessons/anti/shadow-retrieval": PROJECT,
    "/lessons/anti/control-preview": PROJECT,
    "/lessons/anti/control-preview-report": PROJECT,
    "/project-evolution/approval-panel": PROJECT,
    "/handoffs/list": PROJECT,
    "/presentation/evidence/list": REPORTS,
    "/presentation/evidence/file": REPORTS,
    "/eval/evidence-quality/report/<path:report_id>": REPORTS,
    "/mirror-tunnel/preview/<path:preview_id>": REPORTS,
    "/benchmarks/list": REPORTS,
    "/benchmarks/report": REPORTS,
    "/benchmarks/prompt-cost": REPORTS,
    "/proposals/list": REPORTS,
    "/proposals/view": REPORTS,
    "/lessons/proposal": REPORTS,
    "/dream/queue": DREAM,
    "/dream/list": DREAM,
    "/dream/reports": DREAM,
    "/dream/report": DREAM,
    "/dream/plan/latest": DREAM,
    "/dream/references/list": DREAM,
    "/dream/references/file": DREAM,
    "/dream/trials/list": DREAM,
    "/dream/trials/file": DREAM,
    "/history/sessions": INTERNAL,
    "/session/<session_id>": INTERNAL,
    "/replays": INTERNAL,
    "/replays/<replay_id>": INTERNAL,
    "/replays/<replay_id>/compare": INTERNAL,
    "/replays/<replay_id>/artifact/<artifact_name>": INTERNAL,
    "/replays/janitor": INTERNAL,
    "/ux/run-progress/snapshot/<path:snapshot_id>": INTERNAL,
    "/worker-runs/list": INTERNAL,
    "/worker-runs/view": INTERNAL,
    "/dream/status": INTERNAL,
    "/dream/proposals/status": INTERNAL,
    "/benchmarks/status": INTERNAL,
    "/mcp/audit": INTERNAL,
    "/harness/controls": INTERNAL,
}
NON_SENSITIVE_CATEGORIES = {SHELL_STATIC, OPERATIONAL}
AUTH_DEPENDENT_READS = {"/", "/session/<session_id>", "/auth/session"}


def _read_host_module():
    from web import read_host

    return read_host


def _origin_module():
    from web import request_origin

    return request_origin


def _before_auth_web_read1(relative: str) -> bytes:
    from tests._auth_web_read1_maintenance import before_auth_web_read1

    return before_auth_web_read1(relative)


def _before_ux_state1(relative: str) -> bytes:
    # Later phases edit some pinned files; their receipts are undone first.
    from tests._ux_state1_maintenance import before_ux_state1

    return before_ux_state1(relative)


@pytest.fixture
def web(tmp_path, monkeypatch):
    state = configure_offline_web(tmp_path, monkeypatch)
    yield state
    assert state.calls == []


def _seed(state):
    """Unique marker content in a session, evidence, a Dream report and source."""
    from core import dream_artifacts

    repo = state.repo
    (repo / "marker_module.py").write_text(f"def {MARKER}():\n    return '{MARKER}'\n", encoding="utf-8")
    evidence = repo / ".agent" / "presentation_evidence"
    evidence.mkdir(parents=True)
    (evidence / "report.md").write_text(f"# Evidence {MARKER}\n", encoding="utf-8")
    run = dream_artifacts.dreams_root(str(repo)) / DREAM_DATE / DREAM_RUN
    run.mkdir(parents=True)
    (run / "list.json").write_text(
        json.dumps({"items": [], "completed_at": "2026-09-17T12:00:00"}), encoding="utf-8"
    )
    (run / "dream_run_summary.md").write_text(f"Dream summary {MARKER}\n", encoding="utf-8")
    (state.root / "sessions.json").write_text(json.dumps([{
        "id": SESSION_ID,
        "title": f"{MARKER} title",
        "query": f"{MARKER} query",
        "repo_path": str(repo),
        "mode": "retrieve",
        "web_mode": "instant",
        "result": {"answer": f"{MARKER} answer", "context": f"def {MARKER}(): ..."},
        "created_at": "2026-09-17T12:00:00",
    }]), encoding="utf-8")
    state.sensitive = {
        "repository_source": (
            "graph_evidence_spread_route",
            "/graph/evidence_spread?" + urlencode({"repo_path": str(repo), "query": MARKER}),
        ),
        "evidence_report": (
            "presentation_evidence_file_route",
            "/presentation/evidence/file?" + urlencode({"repo_path": str(repo), "name": "report.md"}),
        ),
        "session_history": ("history_routes.history_sessions", "/history/sessions"),
        "session_page": ("load_session", f"/session/{SESSION_ID}"),
        "dream_report": (
            "dream_report_route",
            "/dream/report?" + urlencode({"repo_path": str(repo), "date": DREAM_DATE, "run": DREAM_RUN}),
        ),
    }
    return state


@pytest.fixture
def seeded(web):
    return _seed(web)


def _read(client, path, host=None, *, method="GET", base_url=TRUSTED, headers=None, **kwargs):
    sent = dict(headers or {})
    if host is not None:
        sent["Host"] = host
    return client.open(path, method=method, base_url=base_url, headers=sent, **kwargs)


def _assert_refused(response, status, code):
    assert response.status_code == status, (response.status_code, response.get_data(as_text=True))
    assert response.headers["X-CATTUS-Request-Integrity"] == code
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "Set-Cookie" not in response.headers and "Location" not in response.headers
    assert not [name for name in response.headers.keys() if name.lower().startswith("access-control-")]
    body = response.get_data(as_text=True)
    assert "<" not in body and MARKER not in body
    if response.request.method == "HEAD":
        assert body == ""
    elif response.mimetype == "application/json":
        payload = response.get_json()
        assert set(payload) == {"ok", "success", "error", "error_code"}
        assert payload["ok"] is False and payload["success"] is False and payload["error_code"] == code
    else:
        assert response.mimetype == "text/plain"
    return body


# -- host owner ----------------------------------------------------------------

@pytest.mark.parametrize(
    ("raw", "expected", "serialized"),
    [
        ("127.0.0.1:5000", ("127.0.0.1", 5000), "127.0.0.1:5000"),
        ("LOCALHOST:5000", ("localhost", 5000), "localhost:5000"),
        ("localhost", ("localhost", None), "localhost"),
        ("localhost:80", ("localhost", 80), "localhost:80"),
        ("[::1]:5000", ("::1", 5000), "[::1]:5000"),
        ("[0:0:0:0:0:0:0:1]:5000", ("::1", 5000), "[::1]:5000"),
        ("[::FFFF:127.0.0.1]:5000", ("::ffff:7f00:1", 5000), "[::ffff:7f00:1]:5000"),
        ("[::1]", ("::1", None), "[::1]"),
        ("cattus.example", ("cattus.example", None), "cattus.example"),
        ("dev_box.local:5056", ("dev_box.local", 5056), "dev_box.local:5056"),
    ],
)
def test_host_header_is_one_normalized_host_and_optional_port(raw, expected, serialized):
    identity = _read_host_module().parse_host(raw)
    assert (identity.host, identity.port) == expected
    assert identity.serialize() == serialized


@pytest.mark.parametrize(
    "raw",
    [
        "", " ", "localhost:", "localhost:abc", "localhost:0", "localhost:65536", "localhost:123456",
        "user@localhost:5000", "localhost:5000@evil.example", "user:pass@127.0.0.1:5000",
        "local host:5000", "localhost:5000 ", " localhost:5000", "localhost\t:5000", "localhost\x00:5000",
        "localhost\x01:5000", "localhost\x7f:5000", "lócalhost:5000", "localhost:5000/", "localhost/x",
        "http://localhost:5000", "localhost?x", "localhost#x", "local\\host", "*", "*.example:5000",
        "::1", "::1:5000", "[::1", "::1]:5000", "[::1]]:5000", "[[::1]]:5000", "[::1]:", "[127.0.0.1]:5000",
        "[fe80::1%25eth0]:5000", "[zz::1]:5000", "localhost.:5000", "127.1:5000", "0127.0.0.1:5000",
        "2130706433:5000", "0x7f.0.0.1:5000", "evil.example.123:5000", "a" * 64 + ".example:5000",
        "x" * 300, "localhost:5000,localhost:5000", None, 5000, b"localhost:5000",
    ],
)
def test_malformed_host_values_do_not_parse(raw):
    assert _read_host_module().parse_host(raw) is None


def test_trusted_hosts_are_an_exact_projection_of_allowed_origins():
    rh, ro = _read_host_module(), _origin_module()
    origins = frozenset(ro.parse_origin(value) for value in (
        "http://127.0.0.1:5000", "https://cattus.example", "http://localhost", "http://[::1]:5000",
    ))
    trusted = rh.trusted_hosts(origins)
    assert sorted(identity.serialize() for identity in trusted) == sorted([
        "127.0.0.1:5000", "cattus.example:443", "cattus.example", "localhost:80", "localhost", "[::1]:5000",
    ])
    assert rh.trusted_hosts(frozenset()) == frozenset()


def test_default_trusted_host_comes_from_the_socket_and_the_setting_never_from_the_request(capsys):
    rh = _read_host_module()
    environ = {
        "REQUEST_METHOD": "GET",
        "wsgi.url_scheme": "http",
        "SERVER_NAME": "127.0.0.1",
        "SERVER_PORT": "5000",
        "HTTP_HOST": ATTACKER_HOST,
        "HTTP_ORIGIN": TRUSTED,
        "HTTP_REFERER": TRUSTED + "/",
        "HTTP_X_FORWARDED_HOST": TRUSTED_HOST,
        "HTTP_FORWARDED": "host=127.0.0.1:5000;proto=http",
    }
    decision = rh.should_allow_read_host("GET", environ, None)
    assert (decision.allowed, decision.status_code, decision.code) == (False, 421, "host_not_allowed")
    assert rh.should_allow_read_host("GET", {**environ, "HTTP_HOST": TRUSTED_HOST}, None).allowed
    for setting, host, allowed in (
        ("http://localhost:5056", "localhost:5056", True),
        ("http://localhost:5056", TRUSTED_HOST, False),
        ("http://localhost:5056/", "localhost:5056", False),
        (" , ", TRUSTED_HOST, True),
    ):
        assert rh.should_allow_read_host("GET", {**environ, "HTTP_HOST": host}, setting).allowed is allowed
    for wildcard in ("0.0.0.0", "::", "[::]"):
        for host in (TRUSTED_HOST, "0.0.0.0:5000", "[::]:5000", "localhost:5000", ATTACKER_HOST):
            decision = rh.should_allow_read_host("GET", {**environ, "SERVER_NAME": wildcard, "HTTP_HOST": host}, None)
            assert (decision.allowed, decision.code) == (False, "host_not_allowed")
    assert "evil" not in capsys.readouterr().out


def test_mutating_methods_are_left_to_the_frozen_auth_web1_gate():
    rh = _read_host_module()
    environ = {"wsgi.url_scheme": "http", "SERVER_NAME": "127.0.0.1", "SERVER_PORT": "5000"}
    for method in ("POST", "PUT", "PATCH", "DELETE", "post"):
        for host in (ATTACKER_HOST, "", None, "a,b"):
            decision = rh.should_allow_read_host(method, {**environ, "HTTP_HOST": host}, None)
            assert (decision.allowed, decision.code) == (True, "mutation_gate")
    for method in ("GET", "HEAD", "OPTIONS", "TRACE", "PROPFIND", ""):
        assert rh.should_allow_read_host(method, {**environ, "HTTP_HOST": ATTACKER_HOST}, None).allowed is False


# -- exact DNS-rebinding regression (§18), handler-not-called (§34), marker (§35)

def _spy_view(monkeypatch, app, endpoint, reached):
    original = app.view_functions[endpoint]

    def spy(*args, **kwargs):
        reached.append(endpoint)
        return original(*args, **kwargs)

    monkeypatch.setitem(app.view_functions, endpoint, spy)


def _spy_data_access(monkeypatch, state, touched):
    from core import dream_artifacts
    from web.routes import history_routes

    def spy(owner, name):
        original = getattr(owner, name)

        def recorded(*args, **kwargs):
            touched.append(name)
            return original(*args, **kwargs)

        monkeypatch.setattr(owner, name, recorded)

    spy(state.wa, "build_graph_from_repo")
    spy(state.wa, "_evidence_output_dir")
    spy(state.wa, "load_sessions")
    spy(state.wa, "find_session")
    spy(history_routes, "list_sessions")
    spy(dream_artifacts, "read_report")


@pytest.mark.parametrize("host", [ATTACKER_HOST, "localhost:5000", "127.0.0.1:7999"])
def test_dns_rebinding_regression_sensitive_reads_refused_before_handler_and_data(seeded, monkeypatch, host):
    reached, touched = [], []
    for endpoint, _ in seeded.sensitive.values():
        _spy_view(monkeypatch, seeded.app, endpoint, reached)
    _spy_data_access(monkeypatch, seeded, touched)
    client = seeded.app.test_client()
    for label, (endpoint, path) in seeded.sensitive.items():
        for method in ("GET", "HEAD"):
            _assert_refused(_read(client, path, host, method=method), 421, "host_not_allowed")
        assert reached == [] and touched == [], label
    for label, (endpoint, path) in seeded.sensitive.items():
        response = _read(client, path, TRUSTED_HOST)
        assert response.status_code == 200, label
        assert MARKER in response.get_data(as_text=True), label
        assert reached == [endpoint] and touched, label
        reached.clear()
        touched.clear()


def test_entry_app_without_the_boundary_served_marker_data_under_an_attacker_host(seeded, monkeypatch):
    rh = _read_host_module()
    boundary = seeded.app.wsgi_app
    assert isinstance(boundary, rh.ReadHostBoundary)
    # Entry behavior, executed: the same app and fixtures with only the boundary removed.
    monkeypatch.setattr(seeded.app, "wsgi_app", boundary.wsgi_app)
    client = seeded.app.test_client()
    for label, (_, path) in seeded.sensitive.items():
        response = _read(client, path, ATTACKER_HOST)
        assert response.status_code == 200 and MARKER in response.get_data(as_text=True), label
    assert _read(client, "//new", ATTACKER_HOST).headers["Location"] == "http://evil.example:5000/"
    # ...and those two statements are the whole production delta in web/app.py.
    old, old_statements = _definitions(_before_auth_web_read1("web/app.py"))
    new, new_statements = _definitions(_before_ux_state1("web/app.py"))
    assert old == new
    assert [statement for statement in old_statements if statement not in new_statements] == []
    added = [statement for statement in new_statements if statement not in old_statements]
    assert len(added) == 2
    assert added[0].startswith("ImportFrom(module='web.read_host', names=[alias(name='ReadHostBoundary'")
    assert added[1].startswith("Assign(targets=[Attribute(value=Name(id='app', ctx=Load()), attr='wsgi_app'")


# -- host matrix over HTTP -------------------------------------------------------

@pytest.mark.parametrize(
    ("host", "status", "code"),
    [
        (TRUSTED_HOST, 200, None),
        (ATTACKER_HOST, 421, "host_not_allowed"),
        ("localhost:5000", 421, "host_not_allowed"),
        ("[::1]:5000", 421, "host_not_allowed"),
        ("127.0.0.1:7999", 421, "host_not_allowed"),
        ("127.0.0.1", 421, "host_not_allowed"),
        ("127.0.0.1:80", 421, "host_not_allowed"),
        ("127.0.0.1.evil.example:5000", 421, "host_not_allowed"),
        ("evil-127.0.0.1.example:5000", 421, "host_not_allowed"),
        ("[::ffff:127.0.0.1]:5000", 421, "host_not_allowed"),
        ("user@127.0.0.1:5000", 400, "host_malformed"),
        ("127.0.0.1:5000@evil.example", 400, "host_malformed"),
        ("127.0.0.1:abc", 400, "host_malformed"),
        ("127.0.0.1:", 400, "host_malformed"),
        ("127.0.0.1:0", 400, "host_malformed"),
        ("[::1", 400, "host_malformed"),
        ("::1:5000", 400, "host_malformed"),
        ("127.1:5000", 400, "host_malformed"),
        ("127.0.0.1:5000, 127.0.0.1:5000", 400, "host_ambiguous"),
    ],
)
def test_default_socket_trusts_only_its_exact_host_and_port(seeded, host, status, code):
    client = seeded.app.test_client()
    path = seeded.sensitive["session_history"][1]
    response = _read(client, path, host)
    if code is None:
        assert response.status_code == 200 and MARKER in response.get_data(as_text=True)
    else:
        _assert_refused(response, status, code)


@pytest.mark.parametrize(
    ("host", "allowed"),
    [
        ("localhost:5000", True),
        ("LOCALHOST:5000", True),
        ("localhost:7999", False),
        ("localhost", False),
        ("127.0.0.1:5000", False),
        ("[::1]:5000", False),
        ("attacker-localhost:5000", False),
        ("localhost.attacker.example:5000", False),
        ("localhostx:5000", False),
        ("xlocalhost:5000", False),
    ],
)
def test_configured_localhost_is_exact_about_port_alias_and_name(seeded, host, allowed):
    client = seeded.app.test_client()
    response = _read(client, seeded.sensitive["session_history"][1], host, base_url="http://localhost:5000")
    if allowed:
        assert response.status_code == 200 and MARKER in response.get_data(as_text=True)
    else:
        _assert_refused(response, 421, "host_not_allowed")


def test_web_allowed_origins_publish_exact_hosts_for_docker_and_proxies(seeded, monkeypatch):
    client = seeded.app.test_client()
    path = seeded.sensitive["session_history"][1]
    docker = {"SERVER_NAME": "0.0.0.0", "SERVER_PORT": "5000"}

    def read(host, **kwargs):
        return _read(client, path, host, environ_overrides=docker, **kwargs)

    for host in ("localhost:5000", "127.0.0.1:5000", "0.0.0.0:5000", "localhost:5056"):
        _assert_refused(read(host), 421, "host_not_allowed")
    monkeypatch.setenv("WEB_ALLOWED_ORIGINS", "http://localhost:5056")
    assert read("localhost:5056").status_code == 200
    for host in ("localhost:5000", "127.0.0.1:5056", "localhost", "0.0.0.0:5000", "localhost:50560"):
        _assert_refused(read(host), 421, "host_not_allowed")
    # Explicit origins replace the socket default, exactly as for mutations.
    monkeypatch.setenv("WEB_ALLOWED_ORIGINS", "http://localhost:5000")
    _assert_refused(_read(client, path, TRUSTED_HOST), 421, "host_not_allowed")
    monkeypatch.setenv("WEB_ALLOWED_ORIGINS", "http://127.0.0.1:5000,http://localhost:5000")
    for host in (TRUSTED_HOST, "localhost:5000"):
        assert _read(client, path, host).status_code == 200
    # TLS-terminating proxy that forwards the public Host: default ports are omitted.
    monkeypatch.setenv("WEB_ALLOWED_ORIGINS", "https://cattus.example")
    for host in ("cattus.example", "cattus.example:443", "CATTUS.EXAMPLE"):
        assert read(host).status_code == 200, host
    for host in ("cattus.example:80", "cattus.example:5000", "evil.cattus.example", "cattus.example.evil.example"):
        _assert_refused(read(host), 421, "host_not_allowed")
    monkeypatch.setenv("WEB_ALLOWED_ORIGINS", "http://*.example,*,localhost:5056")
    _assert_refused(read("localhost:5056"), 421, "host_not_allowed")


def test_ipv6_listener_trusts_only_its_canonical_literal(seeded):
    client = seeded.app.test_client()
    path = seeded.sensitive["session_history"][1]
    ipv6 = {"SERVER_NAME": "::1", "SERVER_PORT": "5000"}
    for host in ("[::1]:5000", "[0:0:0:0:0:0:0:1]:5000"):
        assert _read(client, path, host, environ_overrides=ipv6).status_code == 200, host
    for host in ("localhost:5000", TRUSTED_HOST, "[::ffff:127.0.0.1]:5000", "[::1]:5001", "[::1]"):
        _assert_refused(_read(client, path, host, environ_overrides=ipv6), 421, "host_not_allowed")


def test_wildcard_bind_without_public_origin_fails_closed_and_never_learns(seeded):
    client = seeded.app.test_client()
    path = seeded.sensitive["session_history"][1]
    for server_name in ("0.0.0.0", "::"):
        wildcard = {"SERVER_NAME": server_name, "SERVER_PORT": "5000"}
        for _ in range(2):
            for host in (TRUSTED_HOST, "localhost:5000", "0.0.0.0:5000", "[::]:5000", "[::1]:5000", ATTACKER_HOST):
                _assert_refused(_read(client, path, host, environ_overrides=wildcard), 421, "host_not_allowed")
        _assert_refused(_read(client, "/", "localhost:5000", environ_overrides=wildcard), 421, "host_not_allowed")


def _environ_without_host(path="/history/sessions", method="GET"):
    environ = EnvironBuilder(path=path, method=method, base_url=TRUSTED).get_environ()
    environ.pop("HTTP_HOST")
    return environ


@pytest.mark.parametrize(
    ("value", "code"),
    [
        ("", "host_missing"),
        (" ", "host_malformed"),
        ("127.0.0.1:5000 ", "host_malformed"),
        ("127.0.0.1\t:5000", "host_malformed"),
        ("127.0.0.1\x00:5000", "host_malformed"),
        ("127.0.0.1\x01:5000", "host_malformed"),
        ("127.0.0.1:5000\r", "host_malformed"),
        ("127.0.0.1é:5000", "host_malformed"),
        ("[::1]]:5000", "host_malformed"),
        ("[fe80::1%25eth0]:5000", "host_malformed"),
        ("127.0.0.1:65536", "host_malformed"),
        ("127.0.0.1:5000/history", "host_malformed"),
        ("x" * 4000, "host_malformed"),
        ("127.0.0.1:5000,127.0.0.1:5000", "host_ambiguous"),
        ("127.0.0.1:5000,evil.example:5000", "host_ambiguous"),
    ],
)
def test_malformed_empty_and_ambiguous_hosts_are_structured_400s(seeded, value, code):
    # Straight into the WSGI app: the test client cannot build a URL from some of these values.
    for method in SAFE_METHODS:
        environ = EnvironBuilder(path="/history/sessions", method=method, base_url=TRUSTED).get_environ()
        environ["HTTP_HOST"] = value
        app_iter, status, headers = run_wsgi_app(seeded.app, environ, buffered=True)
        response = TestResponse(b"".join(app_iter), status, headers, request=Request(environ))
        _assert_refused(response, 400, code)


def test_missing_host_is_refused_as_host_missing(seeded):
    app_iter, status, headers = run_wsgi_app(seeded.app, _environ_without_host(), buffered=True)
    body = b"".join(app_iter).decode("utf-8")
    assert status.startswith("400 ") and headers["X-CATTUS-Request-Integrity"] == "host_missing"
    assert json.loads(body)["error_code"] == "host_missing" and MARKER not in body


# -- shell, static, redirects, auth bootstrap ------------------------------------

def test_application_shell_static_assets_and_redirects_require_a_trusted_host(seeded, monkeypatch):
    client = seeded.app.test_client()
    for path in ("/", "/new", "/new?web_mode=chat", "//new", "/static/request_integrity.js",
                 "/static/style.css", "/help", "/health", "/no-such-route", "/static/../app.py"):
        for method in SAFE_METHODS:
            _assert_refused(_read(client, path, ATTACKER_HOST, method=method), 421, "host_not_allowed")
    page = _read(client, "/", TRUSTED_HOST)
    assert page.status_code == 200 and CSRF_META.search(page.get_data(as_text=True))
    assert _read(client, "/static/request_integrity.js", TRUSTED_HOST).status_code == 200
    assert _read(client, "/help", TRUSTED_HOST).status_code == 200
    redirect = _read(client, "/new?web_mode=chat", TRUSTED_HOST, headers={"X-Forwarded-Host": ATTACKER_HOST})
    assert redirect.status_code == 302 and redirect.headers["Location"] == "/?web_mode=chat"
    merged = _read(client, "//new", TRUSTED_HOST, headers={"X-Forwarded-Host": ATTACKER_HOST})
    assert merged.status_code == 308 and merged.headers["Location"].startswith(TRUSTED + "/")
    options = _read(client, "/history/sessions", TRUSTED_HOST, method="OPTIONS")
    assert options.status_code == 200 and "GET" in options.headers["Allow"]
    assert not [name for name in options.headers.keys() if name.lower().startswith("access-control-")]


@pytest.mark.parametrize("auth_on", [False, True])
def test_auth_bootstrap_reads_mint_nothing_under_an_untrusted_host(seeded, monkeypatch, auth_on):
    from web import browser_session

    if auth_on:
        monkeypatch.setenv("WEB_AUTH_TOKEN", TOKEN)
    minted = []
    original = browser_session.mint_session

    def spy(**kwargs):
        minted.append(kwargs["authenticated"])
        return original(**kwargs)

    monkeypatch.setattr(browser_session, "mint_session", spy)
    attacker = seeded.app.test_client()
    for path in ("/auth/session", "/", f"/session/{SESSION_ID}"):
        for host in (ATTACKER_HOST, "localhost:5000", "127.0.0.1:7999"):
            _assert_refused(_read(attacker, path, host), 421, "host_not_allowed")
    assert minted == []
    trusted = seeded.app.test_client()
    session = _read(trusted, "/auth/session", TRUSTED_HOST)
    assert session.status_code == 200 and minted == [False]
    assert session.get_json()["auth_state"] == ("signed_out" if auth_on else "not_required")
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", session.get_json()["csrf_token"])
    assert TOKEN not in session.get_data(as_text=True)


def test_authenticated_session_cookie_or_token_never_makes_an_untrusted_host_acceptable(seeded, monkeypatch):
    from web import browser_session

    monkeypatch.setenv("WEB_AUTH_TOKEN", TOKEN)
    client = seeded.app.test_client()
    csrf = CSRF_META.search(_read(client, "/", TRUSTED_HOST).get_data(as_text=True)).group(1)
    login = client.post(
        "/auth/login", base_url=TRUSTED, headers={"Origin": TRUSTED, "X-CSRF-Token": csrf},
        data={"web_auth_token": TOKEN},
    )
    assert login.status_code == 200 and login.get_json()["authenticated"] is True
    cookie = next(
        value.split(";", 1)[0] for value in login.headers.getlist("Set-Cookie")
        if value.startswith(browser_session.COOKIE_NAME + "=")
    )
    # Sent explicitly: a browser never attaches this host's cookie to another host.
    replay = seeded.app.test_client(use_cookies=False)
    for label, (_, path) in seeded.sensitive.items():
        for headers in ({"Cookie": cookie}, {"Authorization": f"Bearer {TOKEN}"}, {"X-CATTUS-Web-Token": TOKEN},
                        {"Cookie": cookie, "Origin": TRUSTED, "X-CSRF-Token": login.get_json()["csrf_token"]}):
            body = _assert_refused(_read(replay, path, ATTACKER_HOST, headers=headers), 421, "host_not_allowed")
            assert TOKEN not in body, label
        trusted = _read(replay, path, TRUSTED_HOST, headers={"Cookie": cookie})
        assert trusted.status_code == 200 and MARKER in trusted.get_data(as_text=True), label


# -- auth modes and API read clients ------------------------------------------------

@pytest.mark.parametrize("auth_on", [False, True])
def test_both_auth_modes_share_the_host_boundary_and_keep_reads_unauthenticated(seeded, monkeypatch, auth_on):
    """Product contract (documented): WEB_AUTH_TOKEN authenticates mutations only."""
    if auth_on:
        monkeypatch.setenv("WEB_AUTH_TOKEN", TOKEN)
    client = seeded.app.test_client()
    for label, (_, path) in seeded.sensitive.items():
        _assert_refused(_read(client, path, ATTACKER_HOST), 421, "host_not_allowed")
        response = _read(client, path, TRUSTED_HOST)
        assert response.status_code == 200 and MARKER in response.get_data(as_text=True), label
        assert "X-CATTUS-Request-Integrity" not in response.headers


def test_api_read_clients_need_only_the_configured_host(seeded, monkeypatch):
    monkeypatch.setenv("WEB_AUTH_TOKEN", TOKEN)
    path = seeded.sensitive["evidence_report"][1]
    for headers in (
        {},
        {"Authorization": f"Bearer {TOKEN}"},
        {"X-CATTUS-Web-Token": "wrong-token"},
        {"Sec-Fetch-Mode": "navigate", "Sec-Fetch-Site": "none"},
        {"Origin": "http://evil.example:5000"},
        {"Referer": "http://evil.example:5000/"},
    ):
        client = seeded.app.test_client(use_cookies=False)
        response = _read(client, path, TRUSTED_HOST, headers=headers)
        assert response.status_code == 200 and response.get_json()["content"] == f"# Evidence {MARKER}\n"
        assert TOKEN not in response.get_data(as_text=True)
        assert not [name for name in response.headers.keys() if name.lower().startswith("access-control-")]
    for headers in ({"Origin": TRUSTED}, {"Referer": TRUSTED + "/"}, {"Authorization": f"Bearer {TOKEN}"}):
        client = seeded.app.test_client(use_cookies=False)
        _assert_refused(_read(client, path, ATTACKER_HOST, headers=headers), 421, "host_not_allowed")


@pytest.mark.parametrize(
    "headers",
    [
        {"X-Forwarded-Host": TRUSTED_HOST},
        {"X-Forwarded-Host": TRUSTED_HOST, "X-Forwarded-Proto": "http", "X-Forwarded-Port": "5000"},
        {"Forwarded": "host=127.0.0.1:5000;proto=http"},
        {"X-Original-Host": TRUSTED_HOST},
        {"X-Host": TRUSTED_HOST},
    ],
)
def test_forwarded_headers_are_never_host_authority(seeded, headers):
    client = seeded.app.test_client()
    path = seeded.sensitive["dream_report"][1]
    _assert_refused(_read(client, path, ATTACKER_HOST, headers=headers), 421, "host_not_allowed")
    swapped = {name: ATTACKER_HOST if value == TRUSTED_HOST else value for name, value in headers.items()}
    assert _read(client, path, TRUSTED_HOST, headers=swapped).status_code == 200


def test_refusal_is_minimal_and_never_echoes_host_inventory_paths_or_secrets(seeded, monkeypatch):
    monkeypatch.setenv("WEB_AUTH_TOKEN", TOKEN)
    monkeypatch.setenv("WEB_ALLOWED_ORIGINS", "http://127.0.0.1:5000,http://cattus-internal.example:5056")
    client = seeded.app.test_client()
    path = seeded.sensitive["evidence_report"][1]
    json_body = _assert_refused(_read(client, path, "rebound-marker.evil.example:5000"), 421, "host_not_allowed")
    navigation = _read(client, path, "rebound-marker.evil.example:5000", headers={"Sec-Fetch-Mode": "navigate"})
    text_body = _assert_refused(navigation, 421, "host_not_allowed")
    assert navigation.mimetype == "text/plain" and text_body.endswith("\n")
    head = _read(client, path, "rebound-marker.evil.example:5000", method="HEAD")
    assert head.status_code == 421 and head.get_data() == b""
    malformed = _assert_refused(_read(client, path, "user@rebound-marker:5000"), 400, "host_malformed")
    for body in (json_body, text_body, malformed):
        for secret in ("rebound-marker", "evil", "127.0.0.1", "cattus-internal", "5056", str(seeded.repo),
                       str(seeded.root), TOKEN, "report.md", "Traceback"):
            assert secret not in body, secret


# -- inventory, ownership and composition ---------------------------------------------

def _get_rules(app):
    return [rule for rule in app.url_map.iter_rules() if {"GET", "HEAD"} & set(rule.methods)]


def test_every_safe_method_route_is_refused_before_its_handler(web, monkeypatch):
    from flask import url_for

    reached: list[str] = []
    routes = []
    with web.app.test_request_context(base_url=TRUSTED):
        for rule in _get_rules(web.app):
            url = url_for(rule.endpoint, **{name: "fixture" for name in rule.arguments})
            routes.append((rule.rule, rule.endpoint, url))
    for _, endpoint, _ in routes:
        def spy(*args, _endpoint=endpoint, **kwargs):
            reached.append(_endpoint)
            return {"ok": True, "spy": _endpoint}

        monkeypatch.setitem(web.app.view_functions, endpoint, spy)
    assert {rule for rule, *_ in routes} == set(GET_ROUTE_CLASSIFICATION)
    client = web.app.test_client()
    count = 0
    for rule, endpoint, url in routes:
        for method in SAFE_METHODS:
            for host in UNTRUSTED_FOR_DEFAULT_SOCKET:
                response = _read(client, url, host, method=method)
                assert response.status_code in (400, 421), (rule, method, host)
                assert response.headers["X-CATTUS-Request-Integrity"] in REFUSAL_CODES
                count += 1
            assert reached == [], (rule, method)
        positive = _read(client, url, TRUSTED_HOST)
        assert positive.status_code == 200 and reached == [endpoint], rule
        reached.clear()
    assert count == len(routes) * len(SAFE_METHODS) * len(UNTRUSTED_FOR_DEFAULT_SOCKET)
    assert len(routes) == len(GET_ROUTE_CLASSIFICATION) == 55


def test_route_inventory_classification_is_complete_and_recorded(web):
    assert {rule.rule for rule in _get_rules(web.app)} == set(GET_ROUTE_CLASSIFICATION)
    receipt = json.loads((FIXTURES / "auth_web_read1_completion.json").read_text(encoding="utf-8"))
    inventory = receipt["route_inventory"]
    assert inventory["classification"] == GET_ROUTE_CLASSIFICATION
    assert set(inventory["non_sensitive"]) == {
        rule for rule, category in GET_ROUTE_CLASSIFICATION.items() if category in NON_SENSITIVE_CATEGORIES
    }
    assert set(inventory["sensitive"]) == set(GET_ROUTE_CLASSIFICATION) - set(inventory["non_sensitive"])
    assert set(inventory["auth_dependent"]) == AUTH_DEPENDENT_READS
    assert inventory["trusted_host_required"] == "all"
    assert inventory["authentication_required"] == []
    counts = {category: list(GET_ROUTE_CLASSIFICATION.values()).count(category)
              for category in sorted(set(GET_ROUTE_CLASSIFICATION.values()))}
    assert inventory["counts"] == counts and sum(counts.values()) == 55


def test_boundary_is_the_single_wsgi_choke_point_and_before_request_is_unchanged(web):
    from flask import Flask

    rh = _read_host_module()
    boundary = web.app.wsgi_app
    assert type(boundary) is rh.ReadHostBoundary
    assert boundary.wsgi_app.__func__ is Flask.wsgi_app and boundary.wsgi_app.__self__ is web.app
    names = {key: [function.__name__ for function in functions]
             for key, functions in web.app.before_request_funcs.items()}
    assert names == {None: ["_web_mutation_gate"]}
    assert web.app.url_value_preprocessors == {} or not any(web.app.url_value_preprocessors.values())
    wrapping, host_readers = [], []
    for path in sorted((ROOT / "web").rglob("*.py")):
        relative = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Attribute) and target.attr == "wsgi_app"
                and not (isinstance(target.value, ast.Name) and target.value.id == "self")
                for target in node.targets
            ):
                wrapping.append(relative)
        if re.search(r"HTTP_HOST|request\.host\b|X-Forwarded|HTTP_X_FORWARDED", text):
            host_readers.append(relative)
    assert wrapping == ["web/app.py"]
    assert host_readers == ["web/read_host.py"]


def test_mutations_under_any_host_are_decided_only_by_the_frozen_auth_web1_gate(web, monkeypatch):
    decisions, reached = [], []
    original_gate = web.wa._should_allow_mutation

    def recording_gate(**kwargs):
        decision = original_gate(**kwargs)
        decisions.append(decision.code)
        return decision

    monkeypatch.setattr(web.wa, "_should_allow_mutation", recording_gate)

    def spy(*args, **kwargs):
        reached.append("import")
        return {"ok": True}

    monkeypatch.setitem(web.app.view_functions, "dream_references_routes.dream_references_import", spy)
    client = web.app.test_client()
    csrf = CSRF_META.search(_read(client, "/", TRUSTED_HOST).get_data(as_text=True)).group(1)
    for host in (TRUSTED_HOST, ATTACKER_HOST, "localhost:7999", ""):
        response = client.post(
            "/dream/references/import", base_url=TRUSTED,
            headers={"Host": host, "Origin": "http://evil.example:5000", "X-CSRF-Token": csrf},
            data={"repo_path": str(web.repo)},
        )
        assert response.status_code == 403
        assert response.headers["X-CATTUS-Request-Integrity"] == "origin_not_allowed"
    assert decisions == ["origin_not_allowed"] * 4 and reached == []
    decisions.clear()
    for host in (TRUSTED_HOST, ATTACKER_HOST):
        response = client.post("/dream/references/import", base_url=TRUSTED, headers={"Host": host},
                               data={"repo_path": str(web.repo)})
        assert response.status_code == 200
    assert decisions == ["loopback_allowed"] * 2 and reached == ["import", "import"]


def test_read_host_boundary_does_no_traversal_model_or_network_work(web, monkeypatch):
    client = web.app.test_client()
    touched = []

    def forbid(name):
        def forbidden(*args, **kwargs):
            touched.append(name)
            raise AssertionError(f"AUTH.WEB.READ.1 boundary must not call {name}")

        return forbidden

    with monkeypatch.context() as patch:
        for owner, name in ((os, "scandir"), (os, "listdir"), (os, "walk"), (os, "stat"), (builtins, "open"),
                            (Path, "iterdir"), (Path, "rglob"), (Path, "glob"), (Path, "read_text"),
                            (Path, "read_bytes"), (Path, "exists"), (socket.socket, "connect")):
            patch.setattr(owner, name, forbid(f"{getattr(owner, '__name__', owner)}.{name}"))
        responses = [_read(client, "/history/sessions", ATTACKER_HOST),
                     _read(client, "/", "user@x:1", method="HEAD")]
    assert [response.status_code for response in responses] == [421, 400]
    assert touched == []


def test_real_listener_refuses_rebound_duplicate_absolute_form_and_hostless_requests(tmp_path, monkeypatch):
    from tests.test_auth_web1_browser import _Listener

    state = _seed(configure_offline_web(tmp_path, monkeypatch, allow_loopback=True))
    listener = _Listener(state.app)
    port = listener.port
    trusted_host = f"127.0.0.1:{port}"

    def raw(request: bytes) -> tuple[int, dict[str, str], bytes]:
        with socket.create_connection(("127.0.0.1", port), timeout=15) as sock:
            sock.sendall(request)
            chunks = []
            while True:
                data = sock.recv(65536)
                if not data:
                    break
                chunks.append(data)
        head, _, body = b"".join(chunks).partition(b"\r\n\r\n")
        lines = head.decode("latin-1").split("\r\n")
        headers = dict(line.split(": ", 1) for line in lines[1:])
        return int(lines[0].split()[1]), headers, body

    def get(target: str, *host_lines: bytes, version: bytes = b"HTTP/1.1") -> tuple[int, dict[str, str], bytes]:
        request = b"GET " + target.encode() + b" " + version + b"\r\n"
        for line in host_lines:
            request += b"Host: " + line + b"\r\n"
        return raw(request + b"Connection: close\r\n\r\n")

    try:
        cases = [
            (get("/history/sessions", trusted_host.encode()), 200, None),
            (get("/history/sessions", f"evil.example:{port}".encode()), 421, "host_not_allowed"),
            (get("/history/sessions", f"localhost:{port}".encode()), 421, "host_not_allowed"),
            (get("/history/sessions", b"127.0.0.1:1"), 421, "host_not_allowed"),
            (get("/history/sessions", trusted_host.encode(), trusted_host.encode()), 400, "host_ambiguous"),
            (get("/history/sessions", version=b"HTTP/1.0"), 400, "host_missing"),
            (get(f"http://evil.example:{port}/history/sessions", trusted_host.encode()), 421, "host_not_allowed"),
            (get(f"http://user@127.0.0.1:{port}/history/sessions", trusted_host.encode()), 400, "host_malformed"),
            (get("/history/sessions", f"127.0.0.1\xc3\xa9:{port}".encode("latin-1")), 400, "host_malformed"),
            (get("/history/sessions", f"127.0.0.1\x01:{port}".encode()), 400, "host_malformed"),
            (get("/static/request_integrity.js", f"evil.example:{port}".encode()), 421, "host_not_allowed"),
            (get("/auth/session", f"evil.example:{port}".encode()), 421, "host_not_allowed"),
        ]
    finally:
        listener.close()
    for (status, headers, body), expected_status, code in cases:
        assert status == expected_status, (status, body[:200])
        if code is None:
            assert MARKER.encode() in body
        else:
            assert headers["X-CATTUS-Request-Integrity"] == code
            assert MARKER.encode() not in body and b"<" not in body and "Set-Cookie" not in headers
    assert state.calls == []


# -- performance ------------------------------------------------------------------

def test_read_host_check_overhead_is_bounded():
    rh, ro = _read_host_module(), _origin_module()
    environ = {"REQUEST_METHOD": "GET", "wsgi.url_scheme": "http", "SERVER_NAME": "127.0.0.1",
               "SERVER_PORT": "5000", "HTTP_HOST": TRUSTED_HOST}
    attacker = {**environ, "HTTP_HOST": ATTACKER_HOST}
    trusted = rh.trusted_hosts(ro.allowed_origins_for(environ, None))

    def unreachable(environ, start_response):
        raise AssertionError("refused requests never reach the application")

    boundary = rh.ReadHostBoundary(unreachable)

    def refused_request():
        for _ in boundary(dict(attacker), lambda status, headers, exc_info=None: None):
            pass

    def per_operation_us(function, batches=15, size=400):
        samples = []
        for _ in range(batches):
            started = time.perf_counter_ns()
            for _ in range(size):
                function()
            samples.append((time.perf_counter_ns() - started) / size / 1000)
        return round(statistics.median(samples), 3)

    result = {
        "host_parse_us": per_operation_us(lambda: rh.parse_host(TRUSTED_HOST)),
        "host_parse_and_check_us": per_operation_us(lambda: rh.evaluate_host(ATTACKER_HOST, trusted)),
        "trusted_host_derivation_us": per_operation_us(
            lambda: rh.trusted_hosts(ro.allowed_origins_for(environ, None))
        ),
        "full_read_host_decision_us": per_operation_us(lambda: rh.should_allow_read_host("GET", attacker, None)),
        "refused_request_wsgi_us": per_operation_us(refused_request, size=100),
    }
    print("AUTH_WEB_READ1_PERFORMANCE=" + json.dumps(result, sort_keys=True))
    if os.environ.get("AUTH_WEB_READ1_PERFORMANCE_FILE"):
        Path(os.environ["AUTH_WEB_READ1_PERFORMANCE_FILE"]).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    assert all(value < 1000 for value in result.values()), result


# -- frozen boundaries, receipts and registry ------------------------------------------

def test_reversal_receipt_reconstructs_every_entry_file_on_the_auth_web1_post_state():
    receipt = json.loads((FIXTURES / "auth_web_read1_reversal.json").read_text(encoding="utf-8"))
    assert receipt["phase"] == "AUTH.WEB.READ.1"
    assert {"web/app.py", "tests/_auth_web1_maintenance.py", "tests/test_auth_web1.py",
            "tests/test_auth_web1_browser.py", "docs/roadmap/phase_registry.json"} <= set(receipt["files"])
    auth_web1_post = {
        relative: record["post_sha256"]
        for relative, record in json.loads(
            (FIXTURES / "auth_web1_reversal.json").read_text(encoding="utf-8")
        )["files"].items()
    }
    auth_web1_sources = json.loads(
        (FIXTURES / "auth_web1_completion.json").read_text(encoding="utf-8")
    )["source_sha256"]
    for relative, record in receipt["files"].items():
        restored = _before_auth_web_read1(relative)
        assert hashlib.sha256(restored).hexdigest() == record["entry_sha256"], relative
        assert hashlib.sha256(_before_ux_state1(relative)).hexdigest() == record["post_sha256"], relative
        anchor = auth_web1_post.get(relative, auth_web1_sources.get(relative))
        if anchor is not None:
            assert record["entry_sha256"] == anchor, relative


def test_frozen_phase_boundaries_are_byte_exact():
    manifest = json.loads((FIXTURES / "auth_web_read1_frozen_boundaries.json").read_text(encoding="utf-8"))
    assert manifest["phase"] == "AUTH.WEB.READ.1"
    for relative, digest in manifest["sha256"].items():
        assert hashlib.sha256(_before_ux_state1(relative)).hexdigest() == digest, relative
    groups = manifest["groups"]
    for group in ("AUTH.WEB.1", "AUTH.WEB.1_evidence", "SEC.UI.1", "DATA.UNDO.1", "EXEC.PLAN.1", "AUTH.DREAM.1",
                  "DATA.ROLLBACK.1", "Track_A", "routes_and_templates", "audit"):
        assert groups[group] and set(groups[group]) <= set(manifest["sha256"]), group
    assert {"web/auth_gate.py", "web/request_origin.py", "web/browser_session.py",
            "web/static/request_integrity.js"} <= set(groups["AUTH.WEB.1"])
    current, _ = _definitions(_before_ux_state1("web/app.py"))
    entry, _ = _definitions(_before_auth_web_read1("web/app.py"))
    assert manifest["web_app_definitions"] == current == entry


def test_registry_has_one_complete_harden_phase_and_picker_is_unchanged():
    from core.phase_picker import pick_phase_candidates
    from core.phase_registry import load_phase_registry, validate_phase_registry

    registry = load_phase_registry(str(ROOT / "docs/roadmap/phase_registry.json"))
    assert validate_phase_registry(registry)["is_valid"]
    ids = [phase["phase_id"] for phase in registry["phases"]]
    phases = [phase for phase in registry["phases"] if phase["phase_id"] == "AUTH.WEB.READ.1"]
    assert len(phases) == 1
    phase = phases[0]
    assert phase["track"] == "HARDEN" and phase["status"] == "complete"
    assert phase["prerequisites"] == ["AUTH.WEB.1"]
    assert ids.index("AUTH.WEB.READ.1") == ids.index("AUTH.WEB.1") + 1
    assert phase["network_allowed"] is False and phase["model_calls_allowed"] is False
    assert phase["human_approval_required"] is True and phase["merge_allowed"] is False
    assert phase["budget_tier"] == "local_only"
    assert pick_phase_candidates(registry)["top_recommendation"]["phase_id"] == "DOGFOOD.1B"


def test_completion_receipt_pins_every_phase_source():
    receipt = json.loads((FIXTURES / "auth_web_read1_completion.json").read_text(encoding="utf-8"))
    assert receipt["phase"] == "AUTH.WEB.READ.1"
    assert receipt["remaining_findings"] == ["UX-02", "UX-03", "UX-04", "UX-05", "UX-06"]
    assert receipt["model_calls"] == 0 and receipt["external_network_requests"] == 0
    assert set(receipt["frozen_production_deltas"].values()) == {0}
    expected = set(receipt["existing_files_changed"] + receipt["new_files"])
    expected.remove("tests/fixtures/auth_web_read1_completion.json")
    assert set(receipt["source_sha256"]) == expected
    for relative, digest in receipt["source_sha256"].items():
        assert hashlib.sha256(_before_ux_state1(relative)).hexdigest() == digest, relative
