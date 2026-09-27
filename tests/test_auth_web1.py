"""AUTH.WEB.1: same-origin request integrity and usable local UI authentication.

SEC-02 (exact origin identity) and UX-01 (browser auth transport) only. These
are direct Flask/unit checks against the production gate, routes and synthetic
files: no model, database or external network. Real Chromium integration lives
in tests/test_auth_web1_browser.py.
"""
from __future__ import annotations

import ast
import difflib
import hashlib
import json
import os
import re
import socket
import statistics
import sys
import time
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from werkzeug.datastructures import Headers

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
AUDIT = ROOT / "docs/audits/2026-09-11-security-and-ui-ux-results.json"
TARGET = "http://localhost:5000"
AUDIT_ORIGINS = {
    "same_origin": "http://localhost:5000",
    "different_port": "http://localhost:7999",
    "different_loopback_host": "http://127.0.0.1:7999",
    "unrelated_host": "http://attacker.invalid:7999",
}
TOKEN = "auth-web1-distinctive-token-7Q2vXk"
CSRF_META = re.compile(r'<meta name="cattus-csrf-token" content="([A-Za-z0-9_-]{43})">')
STATE_META = re.compile(r'<meta name="cattus-auth-state" content="([a-z_]+)">')
MUTATING = {"POST", "PUT", "PATCH", "DELETE"}


def _origin_module():
    from web import request_origin

    return request_origin


def _session_module():
    from web import browser_session

    return browser_session


def _gate_module():
    from web import auth_gate

    return auth_gate


def _tree(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def configure_offline_web(tmp_path, monkeypatch, *, allow_loopback: bool = False):
    """Production Flask app on synthetic locations; providers and network denied."""
    for key, value in {
        "DB_ENABLED": "false",
        "DATABASE_URL": "",
        "DATABASE_URL_LOCAL": "",
        "DATABASE_URL_DOCKER": "",
        "INDEX_USE_EMBEDDINGS": "false",
        "ROUTER_USE_EMBEDDINGS": "false",
        "RETRIEVER_USE_DB": "false",
        "EMBEDDING_PROVIDER": "off",
        "WEB_AUTH_TOKEN": "",
        "RUN_PROGRESS_POLLING_ENABLED": "false",
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("WEB_ALLOWED_ORIGINS", raising=False)
    import config

    for name in ("AGENT_DIR", "STORAGE_PATH"):
        path = tmp_path / name.lower()
        path.mkdir()
        monkeypatch.setattr(config, name, path)
    monkeypatch.setattr(config, "OUTPUT_FILE", tmp_path / "session_log.txt")
    monkeypatch.setattr(config, "DB_ENABLED", False)
    monkeypatch.setattr(config, "DATABASE_URL", "")
    monkeypatch.chdir(tmp_path)
    from web import app as wa, session_store
    from web.routes import patch_routes

    monkeypatch.setattr(session_store, "SESSION_FILE", tmp_path / "sessions.json")
    backups = tmp_path / "backups"
    backups.mkdir()
    monkeypatch.setattr(wa, "BACKUP_DIR", backups)
    monkeypatch.setattr(patch_routes, "BACKUP_DIR", backups)
    monkeypatch.setitem(wa.app.config, "TESTING", True)
    calls: list[str] = []

    def provider(*args, **kwargs):
        calls.append("provider")
        raise AssertionError("AUTH.WEB.1 forbids model calls")

    for module in tuple(sys.modules.values()):
        name = getattr(module, "__name__", "") or ""
        if name == "database.memory":
            monkeypatch.setattr(module, "DB_ENABLED", False)
            monkeypatch.setattr(module, "DATABASE_URL", "")
        if name.startswith(("agents.", "core.", "web.", "reasoning.")):
            for attribute in ("run_gemini_request", "run_gemini_request_2", "run_deepseek_review"):
                if hasattr(module, attribute):
                    monkeypatch.setattr(module, attribute, provider)
    connect = socket.socket.connect

    def local_only(sock, address):
        if allow_loopback and isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1", "localhost"):
            return connect(sock, address)
        raise AssertionError(f"AUTH.WEB.1 forbids network: {address!r}")

    monkeypatch.setattr(socket.socket, "connect", local_only)
    if not allow_loopback:
        def deny(*args, **kwargs):
            raise AssertionError("AUTH.WEB.1 forbids network")

        monkeypatch.setattr(socket, "create_connection", deny)
    repo = tmp_path / "repo"
    repo.mkdir()
    return SimpleNamespace(wa=wa, app=wa.app, repo=repo, root=tmp_path, calls=calls)


@pytest.fixture
def web(tmp_path, monkeypatch):
    state = configure_offline_web(tmp_path, monkeypatch)
    yield state
    assert state.calls == []


def _page(client, base_url=TARGET):
    response = client.get("/", base_url=base_url)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    return CSRF_META.search(html).group(1), STATE_META.search(html).group(1), response


def _import_reference(client, web, *, origin=None, csrf=None, headers=None, label="x",
                      remote="127.0.0.1", base_url=TARGET):
    sent = dict(headers or {})
    if origin is not None:
        sent["Origin"] = origin
    if csrf is not None:
        sent["X-CSRF-Token"] = csrf
    return client.post(
        "/dream/references/import",
        base_url=base_url,
        headers=sent,
        data={
            "repo_path": str(web.repo),
            "topic": "AUTH.WEB.1 " + label,
            "raw_input": "Synthetic import: " + label,
        },
        environ_base={"REMOTE_ADDR": remote},
    )


def _login(client, csrf, token=TOKEN, origin=TARGET):
    return client.post(
        "/auth/login",
        base_url=TARGET,
        headers={"Origin": origin, "X-CSRF-Token": csrf},
        data={"web_auth_token": token},
    )


def _cookie(client):
    cookie = client.get_cookie(_session_module().COOKIE_NAME, domain="localhost")
    return None if cookie is None else cookie.value


def _assert_rejected(response, status, code):
    assert response.status_code == status, response.get_data(as_text=True)
    assert response.is_json
    body = response.get_json()
    assert body["ok"] is False and body["success"] is False
    assert body["error_code"] == code
    assert response.headers["X-CATTUS-Request-Integrity"] == code
    return body


# -- exact SEC-02 red/green --------------------------------------------------

def _entry_gate_module():
    from tests._auth_web1_maintenance import before_auth_web1

    # Executes only this repository's own audited gate bytes, reconstructed
    # from the pinned reversal receipt and digest-checked against the audit.
    source = before_auth_web1("web/auth_gate.py")
    name = "_auth_web1_entry_auth_gate"
    module = ModuleType(name)
    sys.modules[name] = module  # dataclasses resolve their defining module
    try:
        exec(compile(source, "entry:web/auth_gate.py", "exec"), module.__dict__)
    finally:
        sys.modules.pop(name, None)
    return module, source


def _entry_before_request(gate_module):
    """The audited web/app.py gate function, bound to the audited gate."""
    import flask
    from tests._auth_web1_maintenance import before_auth_web1

    tree = ast.parse(before_auth_web1("web/app.py").decode("utf-8"))
    node = next(
        item for item in tree.body
        if isinstance(item, ast.FunctionDef) and item.name == "_web_mutation_gate"
    )
    node.decorator_list = []
    namespace = {
        "request": flask.request,
        "_os_gate": os,
        "_should_allow_mutation": gate_module.should_allow_mutation,
    }
    exec(compile(ast.Module(body=[node], type_ignores=[]), "entry:web/app.py", "exec"), namespace)
    return namespace["_web_mutation_gate"]


def test_exact_sec02_pre_audited_gate_accepts_cross_port_and_cross_host_mutation(web, monkeypatch):
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))["web_boundaries"]
    gate, source = _entry_gate_module()
    assert hashlib.sha256(source).hexdigest() == audit["source_hashes"]["web/auth_gate.py"]
    monkeypatch.setitem(web.app.before_request_funcs, None, [_entry_before_request(gate)])
    client = web.app.test_client()
    observed = {}
    for case, origin in AUDIT_ORIGINS.items():
        response = _import_reference(client, web, origin=origin, label=case)
        body = response.get_json(silent=True) or {}
        created = bool(body.get("json_path")) and Path(body["json_path"]).is_file()
        observed[case] = (response.status_code, created)
    expected = {
        case["case"]: (case["status"], case["created_json_exists"])
        for case in audit["origin_cases"]
    }
    assert observed == expected
    assert observed["different_port"] == (200, True)
    assert observed["different_loopback_host"] == (200, True)


def test_exact_sec02_post_cross_port_and_cross_host_origins_rejected_before_mutation(web):
    client = web.app.test_client()
    for case in ("different_port", "different_loopback_host", "unrelated_host"):
        before = _tree(web.root)
        response = _import_reference(client, web, origin=AUDIT_ORIGINS[case], label=case)
        _assert_rejected(response, 403, "origin_not_allowed")
        assert _tree(web.root) == before
    before = _tree(web.root)
    _assert_rejected(
        _import_reference(client, web, origin=TARGET, label="no_session"),
        403,
        "browser_session_missing",
    )
    assert _tree(web.root) == before
    csrf, state, _ = _page(client)
    assert state == "not_required"
    for case in ("different_port", "different_loopback_host"):
        before = _tree(web.root)
        response = _import_reference(client, web, origin=AUDIT_ORIGINS[case], csrf=csrf, label=case)
        _assert_rejected(response, 403, "origin_not_allowed")
        assert _tree(web.root) == before
    response = _import_reference(client, web, origin=TARGET, csrf=csrf, label="same_origin")
    assert response.status_code == 200 and response.get_json()["ok"] is True
    assert Path(response.get_json()["json_path"]).is_file()


@pytest.mark.parametrize(
    ("origin", "code"),
    [
        ("https://localhost:5000", "origin_not_allowed"),
        ("http://localhost:5001", "origin_not_allowed"),
        ("http://127.0.0.1:5000", "origin_not_allowed"),
        ("http://[::1]:5000", "origin_not_allowed"),
        ("http://localhost", "origin_not_allowed"),
        ("null", "origin_null"),
        ("", "origin_malformed"),
        ("http://localhost:5000/", "origin_malformed"),
        ("localhost:5000", "origin_malformed"),
        ("http://localhost:5000,http://localhost:5000", "origin_ambiguous"),
    ],
)
def test_scheme_host_and_effective_port_all_compared_with_valid_csrf(web, origin, code):
    client = web.app.test_client()
    csrf, _, _ = _page(client)
    before = _tree(web.root)
    _assert_rejected(_import_reference(client, web, origin=origin, csrf=csrf), 403, code)
    assert _tree(web.root) == before


def test_origin_normalization_accepts_equivalent_case_and_default_port(web):
    client = web.app.test_client()
    csrf, _, _ = _page(client)
    assert _import_reference(client, web, origin="HTTP://LOCALHOST:5000", csrf=csrf).status_code == 200
    client = web.app.test_client()
    csrf, _, _ = _page(client, base_url="http://localhost")
    for origin in ("http://localhost", "http://localhost:80"):
        response = _import_reference(client, web, origin=origin, csrf=csrf, base_url="http://localhost")
        assert response.status_code == 200, origin


def test_explicit_allowlist_replaces_the_default_with_exact_origins(web, monkeypatch):
    client = web.app.test_client()
    # AUTH.WEB.READ.1: read the page while its host is still trusted; the
    # allowlist below no longer names that host.
    csrf, _, _ = _page(client)
    monkeypatch.setenv("WEB_ALLOWED_ORIGINS", " http://localhost:7999 , http://localhost:5000/bad ")
    assert _import_reference(client, web, origin="http://localhost:7999", csrf=csrf).status_code == 200
    for origin in (TARGET, "http://127.0.0.1:7999", "https://localhost:7999"):
        _assert_rejected(_import_reference(client, web, origin=origin, csrf=csrf), 403, "origin_not_allowed")
    monkeypatch.setenv("WEB_ALLOWED_ORIGINS", "http://localhost:5000/,*")
    _assert_rejected(_import_reference(client, web, origin=TARGET, csrf=csrf), 403, "origin_not_allowed")


# -- origin owner ------------------------------------------------------------

@pytest.mark.parametrize(
    ("raw", "expected", "serialized"),
    [
        ("http://localhost:5000", ("http", "localhost", 5000), "http://localhost:5000"),
        ("HTTP://LocalHost:5000", ("http", "localhost", 5000), "http://localhost:5000"),
        ("http://localhost:80", ("http", "localhost", 80), "http://localhost"),
        ("http://localhost", ("http", "localhost", 80), "http://localhost"),
        ("https://localhost", ("https", "localhost", 443), "https://localhost"),
        ("https://localhost:8443", ("https", "localhost", 8443), "https://localhost:8443"),
        ("http://127.0.0.1:5000", ("http", "127.0.0.1", 5000), "http://127.0.0.1:5000"),
        ("http://[::1]:5000", ("http", "::1", 5000), "http://[::1]:5000"),
        ("http://[0:0:0:0:0:0:0:1]:5000", ("http", "::1", 5000), "http://[::1]:5000"),
        ("http://[::FFFF:7F00:1]", ("http", "::ffff:7f00:1", 80), "http://[::ffff:7f00:1]"),
        ("http://cattus.example:5000", ("http", "cattus.example", 5000), "http://cattus.example:5000"),
        ("http://dev_box.local:5000", ("http", "dev_box.local", 5000), "http://dev_box.local:5000"),
    ],
)
def test_origin_is_one_normalized_scheme_host_port_tuple(raw, expected, serialized):
    origin = _origin_module().parse_origin(raw)
    assert (origin.scheme, origin.host, origin.port) == expected
    assert origin.serialize() == serialized
    assert _origin_module().parse_origin(serialized) == origin


@pytest.mark.parametrize(
    "raw",
    [
        None, 5000, b"http://localhost:5000", "", " ", "null", "NULL",
        "localhost:5000", "//localhost:5000", "http:/localhost:5000", "http://",
        "http://localhost:5000/", "http://localhost:5000/path", "http://localhost:5000?x=1",
        "http://localhost:5000#f", "http://user@localhost:5000", "http://user:pw@localhost:5000",
        "http://localhost:", "http://localhost:0", "http://localhost:65536", "http://localhost:99999",
        "http://localhost:50a0", "http://localhost:+500", "ftp://localhost:21", "file://", "file:///C:/x",
        "javascript:alert(1)", "data:text/html,x", "ws://localhost:5000", "http://local host:5000",
        " http://localhost:5000", "http://localhost:5000 ", "\thttp://localhost:5000",
        "http://localhost:5000\r\n", "http://localhost.:5000", "http://.localhost:5000",
        "http://a..b:5000", "http://-a.example:5000", "http://a-.example:5000", "http://*.example:5000",
        "http://localhost:*", "*", "http://[::1:5000", "http://::1:5000", "http://[::1%251]:5000",
        "http://[fe80::1%eth0]:5000", "http://[127.0.0.1]:5000", "http://127.0.0.01:5000",
        "http://0x7f.0.0.1:5000", "http://2130706433:5000", "http://1.2.3:5000",
        "http://ex\u00e4mple.com", "http://xn--exmple-cua.com\u00e4", "http://localhost\\@evil.example",
        "http://localhost:5000,http://localhost:5000", "http://localhost:5000 http://localhost:5000",
        "http://" + "a" * 64 + ".example", "http://" + ".".join(["a" * 60] * 5) + ":5000",
        "http://" + "a" * 400,
    ],
)
def test_malformed_or_ambiguous_origins_do_not_parse(raw):
    assert _origin_module().parse_origin(raw) is None


def test_origin_decisions_fail_closed_for_missing_null_multiple_and_malformed():
    ro = _origin_module()
    allowed = frozenset({ro.parse_origin(TARGET)})
    cases = {
        (): "origin_missing",
        ("null",): "origin_null",
        ("NULL",): "origin_malformed",
        ("",): "origin_malformed",
        (TARGET, TARGET): "origin_ambiguous",
        (TARGET + "," + TARGET,): "origin_ambiguous",
        ("http://localhost:5000/",): "origin_malformed",
        ("http://localhost:7999",): "origin_not_allowed",
        ("http://127.0.0.1:5000",): "origin_not_allowed",
        ("https://localhost:5000",): "origin_not_allowed",
        ("http://localhost:5001",): "origin_not_allowed",
        ("http://LOCALHOST:5000",): "origin_allowed",
        (TARGET,): "origin_allowed",
    }
    for values, code in cases.items():
        decision = ro.evaluate_origin(values, allowed)
        assert decision.code == code, values
        assert decision.allowed is (code == "origin_allowed")
    assert ro.evaluate_origin((TARGET,), frozenset()).code == "origin_not_allowed"


def test_localhost_loopback_aliases_are_distinct_origins():
    ro = _origin_module()
    aliases = [ro.parse_origin(value) for value in (
        "http://localhost:5000", "http://127.0.0.1:5000", "http://[::1]:5000",
    )]
    assert len(set(aliases)) == 3
    for index, origin in enumerate(aliases):
        others = frozenset(aliases[:index] + aliases[index + 1:])
        assert ro.evaluate_origin((origin.serialize(),), others).code == "origin_not_allowed"


@pytest.mark.parametrize(
    ("scheme", "name", "port", "expected"),
    [
        ("http", "127.0.0.1", "5000", "http://127.0.0.1:5000"),
        ("http", "localhost", "5000", "http://localhost:5000"),
        ("https", "localhost", "443", "https://localhost"),
        ("http", "::1", "5000", "http://[::1]:5000"),
        ("http", "[::1]", "5000", "http://[::1]:5000"),
        ("http", "0.0.0.0", "5000", None),
        ("http", "::", "5000", None),
        ("http", "", "5000", None),
        ("http", "127.0.0.1", "", None),
        ("http", "127.0.0.1", "0", None),
        ("gopher", "127.0.0.1", "70", None),
    ],
)
def test_default_origin_comes_from_listening_socket_fields(scheme, name, port, expected):
    origin = _origin_module().listening_origin(scheme, name, port)
    assert (origin.serialize() if origin else None) == expected


def test_default_allowlist_ignores_host_header_and_explicit_setting_replaces_it(capsys):
    ro = _origin_module()
    environ = {
        "wsgi.url_scheme": "http",
        "SERVER_NAME": "localhost",
        "SERVER_PORT": "5000",
        "HTTP_HOST": "rebound.attacker.invalid:5000",
    }
    assert ro.allowed_origins_for(environ, None) == frozenset({ro.parse_origin(TARGET)})
    assert ro.allowed_origins_for(environ, " , ") == frozenset({ro.parse_origin(TARGET)})
    assert ro.allowed_origins_for(environ, "http://localhost:7999") == frozenset(
        {ro.parse_origin("http://localhost:7999")}
    )
    assert ro.allowed_origins_for(environ, "http://localhost:5000/") == frozenset()
    wildcard = {**environ, "SERVER_NAME": "0.0.0.0"}
    assert ro.allowed_origins_for(wildcard, None) == frozenset()
    assert "rebound" not in capsys.readouterr().out


def test_allowed_origins_setting_normalization_bounds_and_invalid_entries():
    ro = _origin_module()
    parsed = ro.parse_allowed_origins_setting(
        "HTTP://LOCALHOST:5000, http://127.0.0.1:5000 ,http://localhost:5000,,http://[::1]:5000"
    )
    assert parsed.configured is True
    assert parsed.origins == frozenset(
        ro.parse_origin(value)
        for value in ("http://localhost:5000", "http://127.0.0.1:5000", "http://[::1]:5000")
    )
    assert parsed.invalid_entries == () and parsed.ignored_over_limit == 0
    parsed = ro.parse_allowed_origins_setting(
        "http://localhost:5000/,http://*.local:5000,http://localhost:*,*,localhost:5000,null,http://localhost:5000"
    )
    assert parsed.origins == frozenset({ro.parse_origin(TARGET)})
    assert parsed.invalid_entries == (
        "http://localhost:5000/", "http://*.local:5000", "http://localhost:*", "*", "localhost:5000", "null",
    )
    many = ",".join(f"http://localhost:{5000 + index}" for index in range(ro.MAX_CONFIGURED_ORIGINS + 4))
    parsed = ro.parse_allowed_origins_setting(many)
    assert len(parsed.origins) == ro.MAX_CONFIGURED_ORIGINS == 16
    assert parsed.ignored_over_limit == 4
    assert ro.parse_origin("http://localhost:5016") not in parsed.origins
    assert ro.parse_allowed_origins_setting(None).configured is False
    assert ro.parse_allowed_origins_setting(" ,, ").configured is False
    long_entry = "http://" + "x" * 500
    assert all(len(entry) <= 80 for entry in ro.parse_allowed_origins_setting(long_entry).invalid_entries)


# -- browser session and CSRF owner ------------------------------------------

def test_browser_session_cookie_is_derived_signed_bounded_and_tamper_evident():
    bs = _session_module()
    session, cookie = bs.mint_session(authenticated=False, configured_token="", now=1_000_000)
    assert len(cookie) <= 128 and re.fullmatch(r"[A-Za-z0-9._-]+", cookie)
    read = bs.read_session([cookie], configured_token="", now=1_000_010)
    assert read.status == "valid" and read.session == session and session.authenticated is False
    assert bs.read_session([], configured_token="", now=1_000_010).status == "missing"
    assert bs.read_session([cookie, cookie], configured_token="", now=1_000_010).status == "ambiguous"
    for index, character in enumerate(cookie):
        for replacement in "A-.a":
            if replacement == character:
                continue
            tampered = cookie[:index] + replacement + cookie[index + 1:]
            assert bs.read_session([tampered], configured_token="", now=1_000_010).status != "valid"
    expired = 1_000_000 + bs.SESSION_TTL_SECONDS + 1
    assert bs.read_session([cookie], configured_token="", now=expired).status == "expired"
    _, future = bs.mint_session(authenticated=False, configured_token="", now=2_000_000)
    assert bs.read_session([future], configured_token="", now=1_000_000).status == "invalid"
    for junk in ("", "v1", "v1." + "A" * 5000, cookie + " ", cookie + "\n", cookie.replace(".", ":"),
                 "v2" + cookie[2:], cookie.encode()):
        assert bs.read_session([junk], configured_token="", now=1_000_010).status == "invalid"


def test_authenticated_session_is_bound_to_current_token_and_process_secret(monkeypatch):
    bs = _session_module()
    session, cookie = bs.mint_session(authenticated=True, configured_token=TOKEN)
    assert TOKEN not in cookie
    assert bs.read_session([cookie], configured_token=TOKEN).session.authenticated is True
    assert bs.read_session([cookie], configured_token=TOKEN + "-rotated").status == "invalid"
    assert bs.read_session([cookie], configured_token="").status == "invalid"
    with pytest.raises(ValueError):
        bs.mint_session(authenticated=True, configured_token="")
    _, anonymous = bs.mint_session(authenticated=False, configured_token=TOKEN)
    assert bs.read_session([anonymous], configured_token=TOKEN + "-rotated").session.authenticated is False
    monkeypatch.setattr(bs, "_PROCESS_SECRET", os.urandom(32))
    assert bs.read_session([cookie], configured_token=TOKEN).status == "invalid"
    assert bs.read_session([anonymous], configured_token=TOKEN).status == "invalid"


def test_csrf_proof_is_server_issued_session_bound_and_verified():
    bs = _session_module()
    a, a_cookie = bs.mint_session(authenticated=False, configured_token="", now=1_000_000)
    b, _ = bs.mint_session(authenticated=False, configured_token="", now=1_000_000)
    token = bs.csrf_token_for(a)
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", token)
    assert token == bs.csrf_token_for(a) and token != bs.csrf_token_for(b)
    assert token not in a_cookie and a.session_id not in token
    read = bs.read_session([a_cookie], configured_token="", now=1_000_001)
    valid = bs.evaluate_csrf(read, [token])
    assert (valid.allowed, valid.code) == (True, "csrf_valid")
    for submissions, code in (
        ([], "csrf_missing"),
        ([token, token], "csrf_ambiguous"),
        ([bs.csrf_token_for(b)], "csrf_invalid"),
        (["A" * 43], "csrf_invalid"),
        ([token + " "], "csrf_invalid"),
        ([token[:-1]], "csrf_invalid"),
        ([""], "csrf_invalid"),
        ([token + "," + token], "csrf_invalid"),
    ):
        decision = bs.evaluate_csrf(read, submissions)
        assert (decision.allowed, decision.code) == (False, code), submissions
    missing = bs.read_session([], configured_token="")
    invalid = bs.read_session(["v1.bad"], configured_token="")
    assert bs.evaluate_csrf(missing, [token]).code == "browser_session_missing"
    assert bs.evaluate_csrf(invalid, [token]).code == "browser_session_invalid"
    source = (ROOT / "web/browser_session.py").read_text(encoding="utf-8")
    assert "secrets.token_bytes(32)" in source and "hmac.compare_digest" in source


def test_web_auth_token_comparison_is_exact_and_never_raises():
    bs = _session_module()
    assert bs.web_auth_token_matches(TOKEN, TOKEN) is True
    for supplied in ("", TOKEN + " ", TOKEN[:-1], TOKEN.upper(), "tok\u00e9n", "\ud800", None, 7, TOKEN.encode()):
        assert bs.web_auth_token_matches(supplied, TOKEN) is False
    assert bs.web_auth_token_matches("tok\u00e9n", "tok\u00e9n") is True
    assert bs.web_auth_token_matches("", "") is False


# -- authoritative gate --------------------------------------------------------

def _decide(headers=(), *, token="", remote="127.0.0.1", path="/dream/references/import",
            session=None, csrf=(), allowed=None, method="POST"):
    ro, bs, gate = _origin_module(), _session_module(), _gate_module()
    allowed = frozenset({ro.parse_origin(TARGET)}) if allowed is None else allowed
    read = session if session is not None else bs.read_session([], configured_token=token)
    return gate.should_allow_mutation(
        method=method,
        remote_addr=remote,
        headers=Headers(list(headers)),
        configured_token=token,
        path=path,
        allowed_origins=allowed,
        browser_session=read,
        csrf_submissions=tuple(csrf),
    )


def test_browser_context_is_origin_or_fetch_metadata_never_user_agent_or_cookie():
    gate = _gate_module()
    for headers in ([], [("User-Agent", "Mozilla/5.0 Chrome/140")],
                    [("Cookie", "cattus_ui_session=x")], [("Authorization", "Bearer x")]):
        assert gate.is_browser_request(Headers(headers)) is False
    for name in ("Origin", "Sec-Fetch-Site", "Sec-Fetch-Mode", "Sec-Fetch-Dest", "Referer"):
        assert gate.is_browser_request(Headers([(name, "")])) is True
    for owner in ("web/auth_gate.py", "web/request_origin.py", "web/browser_session.py"):
        tree = ast.parse((ROOT / owner).read_text(encoding="utf-8"))
        constants = [node.value.lower() for node in ast.walk(tree)
                     if isinstance(node, ast.Constant) and isinstance(node.value, str)]
        assert not any("user-agent" in value or "user_agent" in value for value in constants), owner
    assert gate.is_mutating_method("post") and not gate.is_mutating_method("OPTIONS")


def test_auth_off_browser_mutations_still_require_exact_origin_and_csrf():
    bs = _session_module()
    session, cookie = bs.mint_session(authenticated=False, configured_token="")
    read = bs.read_session([cookie], configured_token="")
    csrf = bs.csrf_token_for(session)
    browser = [("Origin", TARGET), ("Sec-Fetch-Site", "same-origin")]
    assert _decide(browser, session=read, csrf=[csrf]).code == "loopback_allowed"
    assert _decide(browser, session=read).code == "csrf_missing"
    assert _decide(browser, csrf=[csrf]).code == "browser_session_missing"
    assert _decide(browser, session=read, csrf=["A" * 43]).code == "csrf_invalid"
    assert _decide([("Origin", "http://localhost:7999")], session=read, csrf=[csrf]).code == "origin_not_allowed"
    assert _decide([("Sec-Fetch-Site", "cross-site")], session=read, csrf=[csrf]).code == "origin_missing"
    assert _decide([("Referer", TARGET + "/")], session=read, csrf=[csrf]).code == "origin_missing"
    assert _decide(browser, session=read, csrf=[csrf], remote="192.168.1.20").code == "non_loopback_rejected"
    assert _decide([]).code == "loopback_allowed"
    assert _decide([], remote="10.0.0.9").code == "non_loopback_rejected"
    assert _decide([("Origin", "http://attacker.invalid")], method="GET").code == "safe_method"


def test_auth_on_browser_requires_origin_csrf_and_authentication_independently():
    bs = _session_module()
    anonymous, anonymous_cookie = bs.mint_session(authenticated=False, configured_token=TOKEN)
    signed_in, signed_in_cookie = bs.mint_session(authenticated=True, configured_token=TOKEN)
    anon_read = bs.read_session([anonymous_cookie], configured_token=TOKEN)
    auth_read = bs.read_session([signed_in_cookie], configured_token=TOKEN)
    auth_csrf = bs.csrf_token_for(signed_in)
    anon_csrf = bs.csrf_token_for(anonymous)
    browser = [("Origin", TARGET), ("Sec-Fetch-Mode", "cors")]
    cases = [
        (browser, auth_read, [auth_csrf], (True, 200, "browser_session_authenticated")),
        (browser, auth_read, [], (False, 403, "csrf_missing")),
        (browser, auth_read, [anon_csrf], (False, 403, "csrf_invalid")),
        (browser, anon_read, [anon_csrf], (False, 401, "auth_required")),
        (browser, bs.read_session([], configured_token=TOKEN), [], (False, 403, "browser_session_missing")),
        ([("Origin", "http://localhost:7999")], auth_read, [auth_csrf], (False, 403, "origin_not_allowed")),
        ([("Origin", "http://127.0.0.1:7999")], auth_read, [auth_csrf], (False, 403, "origin_not_allowed")),
        ([("Origin", "null")], auth_read, [auth_csrf], (False, 403, "origin_null")),
        ([("Origin", "http://localhost:7999"), ("X-CATTUS-Web-Token", TOKEN)], auth_read, [auth_csrf],
         (False, 403, "origin_not_allowed")),
        (browser + [("X-CATTUS-Web-Token", TOKEN)], anon_read, [], (False, 403, "csrf_missing")),
        (browser + [("X-CATTUS-Web-Token", TOKEN)], anon_read, [anon_csrf], (True, 200, "token_authenticated")),
        (browser + [("Authorization", "Bearer wrong")], anon_read, [anon_csrf],
         (False, 403, "web_auth_token_mismatch")),
    ]
    for headers, read, csrf, expected in cases:
        decision = _decide(headers, token=TOKEN, session=read, csrf=csrf, remote="10.0.0.5")
        assert (decision.allowed, decision.status_code, decision.code) == expected, (headers, csrf)
        for secret in (TOKEN, auth_csrf, anon_csrf, signed_in_cookie, anonymous_cookie, "7999", "null"):
            assert secret not in decision.reason


def test_non_browser_header_clients_keep_the_existing_api_contract():
    bs = _session_module()
    signed_in, cookie = bs.mint_session(authenticated=True, configured_token=TOKEN)
    auth_read = bs.read_session([cookie], configured_token=TOKEN)
    for headers, expected in (
        ([("X-CATTUS-Web-Token", TOKEN)], (True, "token_authenticated")),
        ([("Authorization", f"Bearer {TOKEN}")], (True, "token_authenticated")),
        ([], (False, "auth_required")),
        ([("X-CATTUS-Web-Token", "wrong")], (False, "web_auth_token_mismatch")),
        ([("X-CATTUS-Web-Token", "tok\u00e9n")], (False, "web_auth_token_mismatch")),
    ):
        decision = _decide(headers, token=TOKEN, remote="10.0.0.1")
        assert (decision.allowed, decision.code) == expected
    cookie_only = _decide([], token=TOKEN, session=auth_read, csrf=[bs.csrf_token_for(signed_in)])
    assert (cookie_only.allowed, cookie_only.status_code, cookie_only.code) == (False, 401, "auth_required")


def test_login_is_browser_scoped_and_exempt_only_from_authentication():
    bs = _session_module()
    anonymous, cookie = bs.mint_session(authenticated=False, configured_token=TOKEN)
    read = bs.read_session([cookie], configured_token=TOKEN)
    csrf = bs.csrf_token_for(anonymous)
    login = "/auth/login"
    assert _decide([("Origin", TARGET)], token=TOKEN, session=read, csrf=[csrf], path=login).code == "login_bootstrap"
    assert _decide([("Origin", TARGET)], token=TOKEN, session=read, path=login).code == "csrf_missing"
    assert _decide([("Origin", "http://localhost:7999")], token=TOKEN, session=read, csrf=[csrf],
                   path=login).code == "origin_not_allowed"
    assert _decide([], token=TOKEN, path=login).code == "browser_context_required"
    assert _decide([("X-CATTUS-Web-Token", TOKEN)], token=TOKEN, path=login).code == "browser_context_required"


# -- HTTP bootstrap, session auth and CSRF ------------------------------------

def test_auth_on_bootstrap_session_csrf_rotation_and_restart_http(web, monkeypatch):
    bs = _session_module()
    monkeypatch.setenv("WEB_AUTH_TOKEN", TOKEN)
    client = web.app.test_client()
    anon_csrf, state, _ = _page(client)
    assert state == "signed_out"
    anon_cookie = _cookie(client)
    before = _tree(web.root)
    body = _assert_rejected(_import_reference(client, web, origin=TARGET, csrf=anon_csrf), 401, "auth_required")
    assert body["auth_required"] is True and _tree(web.root) == before

    wrong = _login(client, anon_csrf, token=TOKEN + "x")
    assert wrong.status_code == 401 and wrong.get_json()["error_code"] == "web_auth_token_invalid"
    assert "Set-Cookie" not in wrong.headers and _cookie(client) == anon_cookie
    assert TOKEN not in wrong.get_data(as_text=True)
    _assert_rejected(_import_reference(client, web, origin=TARGET, csrf=anon_csrf), 401, "auth_required")
    assert _tree(web.root) == before

    login = _login(client, anon_csrf)
    assert login.status_code == 200 and login.get_json()["authenticated"] is True
    assert login.headers["Cache-Control"] == "no-store"
    csrf = login.get_json()["csrf_token"]
    cookie = _cookie(client)
    assert cookie != anon_cookie and csrf != anon_csrf
    assert TOKEN not in cookie and TOKEN not in login.get_data(as_text=True)
    assert _page(client)[:2] == (csrf, "signed_in")
    session_view = client.get("/auth/session", base_url=TARGET).get_json()
    assert session_view == {
        "ok": True, "auth_required": True, "authenticated": True,
        "auth_state": "signed_in", "csrf_token": csrf,
    }

    for supplied, code in ((anon_csrf, "csrf_invalid"), (None, "csrf_missing"), ("A" * 43, "csrf_invalid")):
        before = _tree(web.root)
        _assert_rejected(_import_reference(client, web, origin=TARGET, csrf=supplied), 403, code)
        assert _tree(web.root) == before
    for origin, code in ((AUDIT_ORIGINS["different_port"], "origin_not_allowed"),
                         (AUDIT_ORIGINS["different_loopback_host"], "origin_not_allowed"),
                         ("null", "origin_null")):
        before = _tree(web.root)
        _assert_rejected(_import_reference(client, web, origin=origin, csrf=csrf), 403, code)
        assert _tree(web.root) == before

    response = _import_reference(client, web, origin=TARGET, csrf=csrf, label="signed_in")
    assert response.status_code == 200 and response.get_json()["ok"] is True

    monkeypatch.setenv("WEB_AUTH_TOKEN", TOKEN + "-rotated")
    body = _assert_rejected(_import_reference(client, web, origin=TARGET, csrf=csrf), 403, "browser_session_invalid")
    assert body["auth_required"] is True
    monkeypatch.setenv("WEB_AUTH_TOKEN", TOKEN)
    assert _import_reference(client, web, origin=TARGET, csrf=csrf, label="restored").status_code == 200
    monkeypatch.setattr(bs, "_PROCESS_SECRET", os.urandom(32))
    before = _tree(web.root)
    _assert_rejected(_import_reference(client, web, origin=TARGET, csrf=csrf), 403, "browser_session_invalid")
    assert _tree(web.root) == before
    fresh_csrf, state, _ = _page(client)
    assert state == "signed_out" and fresh_csrf != csrf


def test_login_bootstrap_is_post_body_only_and_browser_scoped_http(web, monkeypatch):
    monkeypatch.setenv("WEB_AUTH_TOKEN", TOKEN)
    client = web.app.test_client()
    csrf, _, _ = _page(client)
    anon_cookie = _cookie(client)
    assert client.get("/auth/login", base_url=TARGET).status_code == 405
    response = client.post(
        "/auth/login?web_auth_token=" + TOKEN,
        base_url=TARGET,
        headers={"Origin": TARGET, "X-CSRF-Token": csrf},
    )
    assert response.status_code == 401 and _cookie(client) == anon_cookie
    _assert_rejected(client.post("/auth/login", base_url=TARGET, data={"web_auth_token": TOKEN}),
                     403, "browser_context_required")
    _assert_rejected(_login(client, csrf, origin="http://localhost:7999"), 403, "origin_not_allowed")
    _assert_rejected(client.post("/auth/login", base_url=TARGET, headers={"Origin": TARGET},
                                 data={"web_auth_token": TOKEN}), 403, "csrf_missing")
    assert _cookie(client) == anon_cookie
    monkeypatch.setenv("WEB_AUTH_TOKEN", "")
    off = web.app.test_client()
    off_csrf, state, _ = _page(off)
    assert state == "not_required"
    response = _login(off, off_csrf)
    assert response.status_code == 409 and response.get_json()["error_code"] == "web_auth_not_enabled"


def test_authorization_header_api_clients_are_unchanged_http(web, monkeypatch):
    monkeypatch.setenv("WEB_AUTH_TOKEN", TOKEN)
    client = web.app.test_client()
    for headers, status, code in (({}, 401, "auth_required"),
                                  ({"Authorization": "Bearer wrong"}, 403, "web_auth_token_mismatch"),
                                  ({"X-CATTUS-Web-Token": "wrong"}, 403, "web_auth_token_mismatch")):
        before = _tree(web.root)
        _assert_rejected(_import_reference(client, web, headers=headers), status, code)
        assert _tree(web.root) == before
    for headers in ({"Authorization": f"Bearer {TOKEN}"}, {"X-CATTUS-Web-Token": TOKEN}):
        response = _import_reference(client, web, headers=headers, remote="10.1.2.3")
        assert response.status_code == 200 and response.get_json()["ok"] is True
    csrf, _, _ = _page(client)
    csrf = _login(client, csrf).get_json()["csrf_token"]
    _assert_rejected(_import_reference(client, web, csrf=csrf), 401, "auth_required")
    _assert_rejected(_import_reference(client, web, origin="http://localhost:7999",
                                       headers={"X-CATTUS-Web-Token": TOKEN}), 403, "origin_not_allowed")
    monkeypatch.setenv("WEB_AUTH_TOKEN", "")
    cli = web.app.test_client()
    assert _import_reference(cli, web, label="loopback_cli").status_code == 200
    _assert_rejected(_import_reference(cli, web, remote="10.0.0.9"), 403, "non_loopback_rejected")


def test_session_cookie_attributes_and_no_secret_or_query_string_exposure(web, monkeypatch, capsys):
    bs = _session_module()
    monkeypatch.setenv("WEB_AUTH_TOKEN", TOKEN)
    client = web.app.test_client()
    page = client.get("/", base_url=TARGET)
    assert page.headers["Cache-Control"] == "no-store"
    cookies = page.headers.getlist("Set-Cookie")
    assert len(cookies) == 1 and cookies[0].startswith(bs.COOKIE_NAME + "=")
    attributes = [part.strip().lower() for part in cookies[0].split(";")[1:]]
    assert {"httponly", "samesite=lax", "path=/"} <= set(attributes)
    assert "secure" not in attributes
    assert not any(item.startswith(("max-age", "expires", "domain")) for item in attributes)
    html = page.get_data(as_text=True)
    csrf = CSRF_META.search(html).group(1)
    for url in re.findall(r'(?:href|src|action)="([^"]*)"', html):
        assert TOKEN not in url and "web_auth_token" not in url and csrf not in url and "csrf" not in url.lower()
    responses = [
        page,
        client.get("/auth/session", base_url=TARGET),
        client.get("/static/request_integrity.js", base_url=TARGET),
        _import_reference(client, web, headers={"X-CATTUS-Web-Token": TOKEN + "x"}),
        _import_reference(client, web, origin="http://localhost:7999", csrf=csrf),
        _import_reference(client, web, origin=TARGET),
        _login(client, csrf, token=TOKEN + "x"),
        client.post("/auth/login", base_url=TARGET, headers={"Origin": TARGET, "X-CSRF-Token": csrf},
                    data={"web_auth_token": TOKEN}),
    ]
    session_cookie = _cookie(client)
    for response in responses:
        text = response.get_data(as_text=True)
        assert TOKEN not in text
        for name, value in response.headers.items():
            assert TOKEN not in value, name
        assert session_cookie not in text
    output = capsys.readouterr()
    assert TOKEN not in output.out + output.err and session_cookie not in output.out + output.err
    secure = web.app.test_client().get("/", base_url="https://localhost:5443")
    secure_attributes = [part.strip().lower() for part in secure.headers["Set-Cookie"].split(";")[1:]]
    assert "secure" in secure_attributes


@pytest.mark.parametrize(
    ("headers", "status", "code"),
    [
        ({"Origin": "http://" + "a" * 5000}, 403, "origin_malformed"),
        ({"Origin": "http://ex\u00e4mple.com:5000"}, 403, "origin_malformed"),
        ({"Origin": "http://localhost:5000, http://localhost:5000"}, 403, "origin_ambiguous"),
        ({"Origin": "null"}, 403, "origin_null"),
        ({"Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "no-cors"}, 403, "origin_missing"),
        ({"Origin": TARGET, "X-CSRF-Token": "\u00e9" * 43}, 403, "browser_session_missing"),
        ({"X-CATTUS-Web-Token": "tok\u00e9n"}, 403, "web_auth_token_mismatch"),
        ({"Authorization": "Bearer \u00ff\u00fe"}, 403, "web_auth_token_mismatch"),
    ],
)
def test_malformed_transport_is_a_structured_rejection_not_an_exception(web, monkeypatch, headers, status, code):
    monkeypatch.setenv("WEB_AUTH_TOKEN", TOKEN)
    before = _tree(web.root)
    _assert_rejected(_import_reference(web.app.test_client(), web, headers=headers), status, code)
    assert _tree(web.root) == before


def test_navigation_rejections_are_plain_text_and_never_html(web, monkeypatch):
    def handler_reached(**kwargs):
        raise AssertionError("cross-origin navigation reached the index handler")

    monkeypatch.setattr(web.wa, "_run_mode", handler_reached)
    client = web.app.test_client()
    response = client.post(
        "/",
        base_url=TARGET,
        headers={"Origin": "http://localhost:7999", "Sec-Fetch-Mode": "navigate"},
        data={"query": "x", "repo_path": str(web.repo)},
    )
    assert response.status_code == 403 and response.mimetype == "text/plain"
    assert response.headers["X-CATTUS-Request-Integrity"] == "origin_not_allowed"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "<" not in response.get_data(as_text=True)


def test_native_form_post_carries_csrf_in_its_body(web, monkeypatch):
    client = web.app.test_client()
    csrf, _, _ = _page(client)
    monkeypatch.setattr(web.wa, "_run_mode", lambda **kwargs: ({"answer": "AUTH.WEB.1 form fixture"}, kwargs["project_tag"]))
    form = {"query": "Explain app.py", "repo_path": str(web.repo), "web_mode": "chat"}
    browser = {"Origin": TARGET, "Sec-Fetch-Mode": "navigate"}
    missing = client.post("/", base_url=TARGET, headers=browser, data=form)
    assert missing.status_code == 403 and missing.headers["X-CATTUS-Request-Integrity"] == "csrf_missing"
    assert not (web.root / "sessions.json").exists()
    response = client.post("/", base_url=TARGET, headers=browser, data={**form, "csrf_token": csrf})
    assert response.status_code == 200 and "AUTH.WEB.1 form fixture" in response.get_data(as_text=True)


# -- mutation route inventory -------------------------------------------------

REQUIRED_MUTATION_ROUTES = {
    "/", "/apply_patch", "/apply_patch_plan", "/test_patch", "/test_patch_plan", "/undo_patch",
    "/generate_patch", "/dream/apply", "/dream/run", "/dream/references/import",
    "/dream/promote-artifact", "/history/session/archive", "/history/session/delete",
    "/harness/controls/apply-env", "/mcp/inspector/launch", "/upload_folder",
    "/replays/janitor/apply", "/consolidate_memory", "/auth/login",
}


def test_every_mutating_route_is_decided_by_the_gate_before_its_handler(web, monkeypatch):
    from flask import url_for

    monkeypatch.setenv("WEB_AUTH_TOKEN", TOKEN)
    client = web.app.test_client()
    anon_csrf, _, _ = _page(client)
    signed_in = web.app.test_client()
    csrf = _login(signed_in, _page(signed_in)[0]).get_json()["csrf_token"]
    reached: list[str] = []
    routes = []
    with web.app.test_request_context(base_url=TARGET):
        for rule in web.app.url_map.iter_rules():
            methods = sorted(set(rule.methods) & MUTATING)
            if not methods:
                continue
            url = url_for(rule.endpoint, **{name: "fixture" for name in rule.arguments})
            routes.append((rule.rule, rule.endpoint, url, methods))
    for _, endpoint, _, _ in routes:
        def spy(*args, _endpoint=endpoint, **kwargs):
            reached.append(_endpoint)
            return {"ok": True, "spy": _endpoint}

        monkeypatch.setitem(web.app.view_functions, endpoint, spy)
    assert REQUIRED_MUTATION_ROUTES <= {rule for rule, *_ in routes}
    count = 0
    for rule, endpoint, url, methods in routes:
        login = rule == "/auth/login"
        for method in methods:
            def send(target, headers):
                return target.open(url, method=method, base_url=TARGET, headers=headers, data={"repo_path": "x"})

            expectations = [
                (signed_in, {"Origin": "http://localhost:7999", "X-CSRF-Token": csrf}, 403, "origin_not_allowed"),
                (signed_in, {"Origin": "http://127.0.0.1:5000", "X-CSRF-Token": csrf}, 403, "origin_not_allowed"),
                (signed_in, {"Origin": TARGET}, 403, "csrf_missing"),
                (signed_in, {"Origin": TARGET, "X-CSRF-Token": anon_csrf}, 403, "csrf_invalid"),
                (web.app.test_client(), {}, (403 if login else 401),
                 "browser_context_required" if login else "auth_required"),
            ]
            if not login:
                expectations.append((client, {"Origin": TARGET, "X-CSRF-Token": anon_csrf}, 401, "auth_required"))
            for target, headers, status, code in expectations:
                response = send(target, headers)
                assert response.status_code == status, (rule, method, headers)
                assert response.headers["X-CATTUS-Request-Integrity"] == code, (rule, method)
                count += 1
            assert reached == [], (rule, method)
            positive = send(signed_in, {"Origin": TARGET, "X-CSRF-Token": csrf})
            assert positive.status_code == 200 and reached == [endpoint], (rule, method)
            reached.clear()
    assert count >= 6 * len(REQUIRED_MUTATION_ROUTES)
    names = [function.__name__ for function in web.app.before_request_funcs[None]]
    assert names == ["_web_mutation_gate"]


# -- frontend transport ownership and secret exposure (static) ----------------

def test_frontend_protected_requests_and_forms_share_one_transport_owner():
    template = (ROOT / "web/templates/index.html").read_text(encoding="utf-8")
    helper = (ROOT / "web/static/request_integrity.js").read_text(encoding="utf-8")
    head = template[: template.index("</head>")]
    first_script = re.search(r"<script\b[^>]*>", template).group(0)
    assert "filename='request_integrity.js'" in first_script
    assert '<meta name="cattus-csrf-token" content="{{ cattus_csrf_token() }}">' in head
    assert '<meta name="cattus-auth-state" content="{{ cattus_auth_state() }}">' in head
    assert len(re.findall(r"<form\b", template)) == 1
    for bypass in ("XMLHttpRequest", "sendBeacon", "EventSource", "new WebSocket", ".submit()", "requestSubmit",
                   "X-CSRF-Token", 'name="csrf_token"', "X-CATTUS-Web-Token", '"Authorization"', "web_auth_token",
                   "WEB_AUTH_TOKEN"):
        assert bypass not in template, bypass
    for required in ("global.fetch = protectedFetch", '"X-CSRF-Token"', '"csrf_token"', '"/auth/login"',
                     '"/auth/session"', 'credentials: "same-origin"', '"X-CATTUS-Request-Integrity"',
                     "CattusSafeContent.renderText"):
        assert required in helper, required
    for forbidden in ("localStorage", "sessionStorage", "document.cookie", "innerHTML", "outerHTML",
                      "insertAdjacentHTML", "eval(", "new Function", "?web_auth_token", "Authorization",
                      "X-CATTUS-Web-Token", "location.search"):
        assert forbidden not in helper, forbidden
    for other in ("web/static/keybindings.js", "web/static/safe_content.js"):
        text = (ROOT / other).read_text(encoding="utf-8")
        assert "fetch(" not in text and "XMLHttpRequest" not in text


def test_generated_page_never_renders_the_web_auth_token(web, monkeypatch):
    monkeypatch.setenv("WEB_AUTH_TOKEN", TOKEN)
    client = web.app.test_client()
    for path in ("/", "/new", "/auth/session", "/static/request_integrity.js", "/help"):
        response = client.get(path, base_url=TARGET, follow_redirects=True)
        assert response.status_code == 200, path
        assert TOKEN not in response.get_data(as_text=True), path
    csrf, _, _ = _page(client)
    csrf = _login(client, csrf).get_json()["csrf_token"]
    html = client.get("/", base_url=TARGET).get_data(as_text=True)
    assert TOKEN not in html and csrf in html


# -- frozen boundaries, receipts and registry ----------------------------------

def _definitions(raw: bytes) -> tuple[dict[str, str], list[str]]:
    tree = ast.parse(raw.decode("utf-8"))
    definitions: dict[str, list[str]] = {}
    statements: list[str] = []
    for node in tree.body:
        dump = ast.dump(node, include_attributes=False)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            definitions.setdefault(node.name, []).append(hashlib.sha256(dump.encode()).hexdigest())
        else:
            statements.append(dump)
    return {name: "|".join(values) for name, values in definitions.items()}, statements


APP_DEFINITIONS_ADDED = {
    "_configured_web_auth_token",
    "_submitted_csrf_tokens",
    "_request_integrity_rejection",
    "_set_browser_session_cookie",
    "_browser_session_for_page",
    "_browser_auth_state",
    "_browser_request_integrity_template_context",
    "_browser_session_response_headers",
    "auth_session_route",
    "auth_login_route",
}


def test_existing_web_app_definitions_and_page_body_are_unchanged():
    from tests._auth_web1_maintenance import before_auth_web1
    from tests._auth_web_read1_maintenance import before_auth_web_read1

    old, old_statements = _definitions(before_auth_web1("web/app.py"))
    new, new_statements = _definitions(before_auth_web_read1("web/app.py"))
    assert {name for name in old.keys() & new.keys() if old[name] != new[name]} == {"_web_mutation_gate"}
    assert set(old) - set(new) == set()
    assert set(new) - set(old) == APP_DEFINITIONS_ADDED
    removed = [statement for statement in old_statements if statement not in new_statements]
    added = [statement for statement in new_statements if statement not in old_statements]
    assert removed == []
    assert added and all(statement.startswith("ImportFrom(") for statement in added)
    assert all(re.search(r"module='(web|web\.auth_gate|flask)'", statement) for statement in added)

    entry = before_auth_web1("web/templates/index.html").decode("utf-8")
    current = before_auth_web_read1("web/templates/index.html").decode("utf-8")
    assert entry[entry.index("</head>"):] == current[current.index("</head>"):]
    delta = [line for line in difflib.ndiff(entry[: entry.index("</head>")].splitlines(True),
                                            current[: current.index("</head>")].splitlines(True))
             if line[:2] in {"+ ", "- "}]
    assert [line[:2] for line in delta] == ["+ ", "+ ", "+ "]


def test_reversal_receipt_reconstructs_every_entry_file():
    from tests._auth_web1_maintenance import before_auth_web1

    receipt = json.loads((FIXTURES / "auth_web1_reversal.json").read_text(encoding="utf-8"))
    assert receipt["phase"] == "AUTH.WEB.1"
    assert {"web/auth_gate.py", "web/app.py", "web/templates/index.html"} <= set(receipt["files"])
    for relative, record in receipt["files"].items():
        restored = before_auth_web1(relative)
        assert hashlib.sha256(restored).hexdigest() == record["entry_sha256"], relative
    rollback = json.loads((FIXTURES / "data_rollback1_frozen_boundaries.json").read_text(encoding="utf-8"))
    for relative in ("web/app.py", "web/templates/index.html"):
        assert receipt["files"][relative]["entry_sha256"] == rollback["sha256"][relative]


def test_frozen_phase_and_track_a_boundaries_are_byte_exact():
    manifest = json.loads((FIXTURES / "auth_web1_frozen_boundaries.json").read_text(encoding="utf-8"))
    assert manifest["phase"] == "AUTH.WEB.1"
    # AUTH.WEB.1's post-state bytes: later phases' receipts are undone first (PREFLIGHT.REQUEST.1
    # added an ID prefix to core/phase_registry.py).
    post_state = __import__("tests._auth_web_read1_maintenance", fromlist=["x"]).before_auth_web_read1
    for relative, digest in manifest["sha256"].items():
        assert hashlib.sha256(post_state(relative)).hexdigest() == digest, relative
    groups = manifest["groups"]
    for group in ("SEC.UI.1", "DATA.UNDO.1", "EXEC.PLAN.1", "AUTH.DREAM.1", "DATA.ROLLBACK.1", "Track_A", "audit"):
        assert groups[group] and set(groups[group]) <= set(manifest["sha256"]), group
    old, _ = _definitions(__import__("tests._auth_web1_maintenance", fromlist=["x"]).before_auth_web1("web/app.py"))
    # AUTH.WEB.1's post-state definitions: later phases' receipts are undone first.
    new, _ = _definitions(__import__("tests._auth_web_read1_maintenance", fromlist=["x"]).before_auth_web_read1(
        "web/app.py"))
    for name, digest in manifest["web_app_definitions"].items():
        assert new[name] == digest == old[name], name


def test_registry_has_one_complete_harden_phase_and_picker_is_unchanged():
    from core.phase_picker import pick_phase_candidates
    from core.phase_registry import load_phase_registry, validate_phase_registry

    registry = load_phase_registry(str(ROOT / "docs/roadmap/phase_registry.json"))
    assert validate_phase_registry(registry)["is_valid"]
    phases = [phase for phase in registry["phases"] if phase["phase_id"] == "AUTH.WEB.1"]
    assert len(phases) == 1
    phase = phases[0]
    assert phase["track"] == "HARDEN" and phase["status"] == "complete"
    assert phase["prerequisites"] == ["DATA.ROLLBACK.1"]
    assert phase["network_allowed"] is False and phase["model_calls_allowed"] is False
    assert phase["human_approval_required"] is True and phase["merge_allowed"] is False
    ids = [entry["phase_id"] for entry in registry["phases"]]
    assert ids.index("AUTH.WEB.1") == ids.index("DATA.ROLLBACK.1") + 1
    assert pick_phase_candidates(registry)["top_recommendation"]["phase_id"] == "DOGFOOD.1B"


def test_completion_receipt_pins_every_phase_source():
    from tests._auth_web_read1_maintenance import before_auth_web_read1

    receipt = json.loads((FIXTURES / "auth_web1_completion.json").read_text(encoding="utf-8"))
    assert receipt["phase"] == "AUTH.WEB.1"
    assert receipt["closed_findings"] == ["SEC-02", "UX-01"]
    assert receipt["remaining_findings"] == ["UX-02", "UX-03", "UX-04", "UX-05", "UX-06"]
    assert receipt["model_calls"] == 0 and receipt["external_network_requests"] == 0
    expected = set(receipt["existing_files_changed"] + receipt["new_files"])
    expected.remove("tests/fixtures/auth_web1_completion.json")
    assert set(receipt["source_sha256"]) == expected
    for relative, digest in receipt["source_sha256"].items():
        assert hashlib.sha256(before_auth_web_read1(relative)).hexdigest() == digest, relative


# -- performance ----------------------------------------------------------------

def test_request_integrity_overhead_is_bounded():
    ro, bs, gate = _origin_module(), _session_module(), _gate_module()
    environ = {"wsgi.url_scheme": "http", "SERVER_NAME": "localhost", "SERVER_PORT": "5000"}
    allowed = ro.allowed_origins_for(environ, None)
    session, cookie = bs.mint_session(authenticated=True, configured_token=TOKEN)
    csrf = bs.csrf_token_for(session)
    read = bs.read_session([cookie], configured_token=TOKEN)
    headers = Headers([("Origin", TARGET), ("Sec-Fetch-Mode", "cors"), ("X-CSRF-Token", csrf)])

    def per_operation_us(function, batches=15, size=400):
        samples = []
        for _ in range(batches):
            started = time.perf_counter_ns()
            for _ in range(size):
                function()
            samples.append((time.perf_counter_ns() - started) / size / 1000)
        return round(statistics.median(samples), 3)

    result = {
        "origin_parse_and_check_us": per_operation_us(lambda: ro.evaluate_origin((TARGET,), allowed)),
        "allowed_origin_derivation_us": per_operation_us(lambda: ro.allowed_origins_for(environ, None)),
        "session_verification_us": per_operation_us(lambda: bs.read_session([cookie], configured_token=TOKEN)),
        "csrf_verification_us": per_operation_us(lambda: bs.evaluate_csrf(read, (csrf,))),
        "full_gate_decision_us": per_operation_us(lambda: gate.should_allow_mutation(
            method="POST", remote_addr="127.0.0.1", headers=headers, configured_token=TOKEN,
            path="/dream/apply", allowed_origins=allowed, browser_session=read, csrf_submissions=(csrf,),
        )),
    }
    print("AUTH_WEB1_PERFORMANCE=" + json.dumps(result, sort_keys=True))
    if os.environ.get("AUTH_WEB1_PERFORMANCE_FILE"):
        Path(os.environ["AUTH_WEB1_PERFORMANCE_FILE"]).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    assert all(value < 1000 for value in result.values()), result
