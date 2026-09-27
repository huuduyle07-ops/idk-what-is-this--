"""HARDEN.1 — Web Mutation Auth / CSRF Gate tests.

Covers:
1.  GET is allowed without token
2.  HEAD/OPTIONS are allowed without token
3.  POST from loopback is allowed when WEB_AUTH_TOKEN unset
4.  POST from non-loopback is rejected when WEB_AUTH_TOKEN unset
5.  POST without token is rejected when WEB_AUTH_TOKEN is set
6.  POST with wrong token is rejected
7.  POST with X-CATTUS-Web-Token correct token is allowed
8.  POST with Authorization: Bearer <token> correct token is allowed
9.  Cross-origin POST is rejected
10. Same-origin POST with its session-bound CSRF token is allowed (AUTH.WEB.1)
11. Missing Origin/Referer does not block token-authenticated API request
12. Existing mutation route is blocked without auth under configured token
13. Existing mutation route is allowed with correct auth token
14. debug=True is not used in web/app.py main entry
15. source contains no new model/network/patch/validation/benchmark/worker/DB/merge behavior
"""
from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest
from werkzeug.datastructures import Headers

from web.auth_gate import (
    GateDecision,
    extract_web_auth_token,
    is_loopback_host,
    should_allow_mutation,
)
from web.browser_session import csrf_token_for, mint_session, read_session
from web.request_origin import parse_origin


# ── helpers ────────────────────────────────────────────────────────────────────

def _headers(**kw):
    """Return real request headers (case-insensitive, multi-valued)."""
    return Headers(list(kw.items()))


def _allow(method="POST", remote_addr="127.0.0.1", headers=None, host="localhost", token="", csrf=False):
    """``host`` is the one allowed origin; ``csrf`` adds a valid session-bound CSRF proof."""
    allowed = parse_origin(host if "://" in host else f"http://{host}")
    session, cookie = mint_session(authenticated=False, configured_token=token)
    return should_allow_mutation(
        method=method,
        remote_addr=remote_addr,
        headers=headers or _headers(),
        configured_token=token,
        allowed_origins=frozenset({allowed}) if allowed else frozenset(),
        browser_session=read_session([cookie], configured_token=token),
        csrf_submissions=(csrf_token_for(session),) if csrf else (),
    )


# ── 1. GET is allowed without token ───────────────────────────────────────────

def test_get_allowed_without_token():
    d = _allow(method="GET", remote_addr="10.0.0.1", token="")
    assert d.allowed is True


# ── 2. HEAD/OPTIONS are allowed without token ─────────────────────────────────

def test_head_allowed_without_token():
    d = _allow(method="HEAD", remote_addr="10.0.0.1", token="")
    assert d.allowed is True


def test_options_allowed_without_token():
    d = _allow(method="OPTIONS", remote_addr="10.0.0.1", token="")
    assert d.allowed is True


# ── 3. POST from loopback is allowed when WEB_AUTH_TOKEN unset ────────────────

def test_post_loopback_allowed_no_token_127():
    d = _allow(method="POST", remote_addr="127.0.0.1", token="")
    assert d.allowed is True


def test_post_loopback_allowed_no_token_ipv6():
    d = _allow(method="POST", remote_addr="::1", token="")
    assert d.allowed is True


def test_post_loopback_allowed_no_token_localhost():
    d = _allow(method="POST", remote_addr="localhost", token="")
    assert d.allowed is True


# ── 4. POST from non-loopback is rejected when WEB_AUTH_TOKEN unset ───────────

def test_post_non_loopback_rejected_no_token():
    d = _allow(method="POST", remote_addr="192.168.1.50", token="")
    assert d.allowed is False
    assert d.status_code == 403


def test_put_non_loopback_rejected_no_token():
    d = _allow(method="PUT", remote_addr="10.0.0.5", token="")
    assert d.allowed is False
    assert d.status_code == 403


# ── 5. POST without token is rejected when WEB_AUTH_TOKEN is set ──────────────

def test_post_no_token_header_rejected_when_token_configured():
    d = _allow(method="POST", remote_addr="127.0.0.1", token="secret123")
    assert d.allowed is False
    assert d.status_code == 401


# ── 6. POST with wrong token is rejected ──────────────────────────────────────

def test_post_wrong_token_rejected():
    h = _headers(**{"X-CATTUS-Web-Token": "wrong"})
    d = _allow(method="POST", headers=h, token="correct")
    assert d.allowed is False
    assert d.status_code == 403


# ── 7. POST with X-CATTUS-Web-Token correct token is allowed ──────────────────

def test_post_x_cattus_token_correct_allowed():
    h = _headers(**{"X-CATTUS-Web-Token": "mytoken"})
    d = _allow(method="POST", remote_addr="10.0.0.1", headers=h, token="mytoken")
    assert d.allowed is True


# ── 8. POST with Authorization: Bearer <token> correct token is allowed ────────

def test_post_bearer_token_correct_allowed():
    h = _headers(Authorization="Bearer mytoken")
    d = _allow(method="POST", remote_addr="10.0.0.1", headers=h, token="mytoken")
    assert d.allowed is True


# ── 9. Cross-origin POST is rejected ──────────────────────────────────────────

def test_cross_origin_post_rejected_no_token():
    h = _headers(Origin="http://evil.example.com")
    d = _allow(method="POST", remote_addr="127.0.0.1", headers=h, host="localhost", token="")
    assert d.allowed is False
    assert d.status_code == 403


def test_cross_origin_post_rejected_even_with_token():
    h = _headers(Origin="http://evil.example.com", **{"X-CATTUS-Web-Token": "tok"})
    d = _allow(method="POST", remote_addr="10.0.0.1", headers=h, host="localhost", token="tok")
    assert d.allowed is False
    assert d.status_code == 403


# ── 10. Same-origin POST is allowed ───────────────────────────────────────────

def test_same_origin_post_allowed_no_token():
    h = _headers(Origin="http://127.0.0.1:5000")
    d = _allow(method="POST", remote_addr="127.0.0.1", headers=h, host="127.0.0.1:5000", token="", csrf=True)
    assert d.allowed is True
    d = _allow(method="POST", remote_addr="127.0.0.1", headers=h, host="127.0.0.1:5000", token="")
    assert d.allowed is False and d.code == "csrf_missing"


def test_same_origin_post_allowed_with_token():
    h = _headers(Origin="http://localhost:5000", **{"X-CATTUS-Web-Token": "tok"})
    d = _allow(method="POST", remote_addr="127.0.0.1", headers=h, host="localhost:5000", token="tok", csrf=True)
    assert d.allowed is True
    d = _allow(method="POST", remote_addr="127.0.0.1", headers=h, host="localhost:5000", token="tok")
    assert d.allowed is False and d.code == "csrf_missing"


# ── 11. Missing Origin/Referer does not block token-authenticated API request ──

def test_no_origin_no_referer_token_auth_allowed():
    h = _headers(**{"X-CATTUS-Web-Token": "apitoken"})
    d = _allow(method="POST", remote_addr="10.0.0.1", headers=h, host="api.example.com", token="apitoken")
    assert d.allowed is True


# ── 12. Route blocked without auth under configured token ─────────────────────

def test_apply_patch_route_blocked_without_auth(monkeypatch):
    monkeypatch.setenv("WEB_AUTH_TOKEN", "secret")
    from web.app import app
    app.config["TESTING"] = True
    with app.test_client() as client:
        resp = client.post("/apply_patch", data={"repo_path": "/tmp", "patch": "{}"})
    assert resp.status_code in {401, 403}


# ── 13. Route allowed with correct auth token (route body mocked) ──────────────

def test_apply_patch_route_allowed_with_correct_token(monkeypatch):
    monkeypatch.setenv("WEB_AUTH_TOKEN", "secret")
    from web.app import app
    app.config["TESTING"] = True
    with app.test_client() as client:
        resp = client.post(
            "/apply_patch",
            data={"repo_path": "/tmp", "patch": "{}"},
            headers={"X-CATTUS-Web-Token": "secret"},
        )
    # Gate passes — route may return 400/500 due to invalid patch data,
    # but must NOT be 401 or 403 (that would mean the gate blocked it).
    assert resp.status_code not in {401, 403}


# ── 14. debug=True is not used in web/app.py main entry ──────────────────────

def test_no_debug_true_in_app_main():
    src = Path("web/app.py").read_text(encoding="utf-8")
    assert "debug=True" not in src, (
        "web/app.py must not use debug=True in the __main__ block"
    )


# ── 15. Source contains no forbidden model/network/patch/benchmark calls ──────

def test_auth_gate_source_no_forbidden_calls():
    src = Path("web/auth_gate.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    call_names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                call_names.append(node.func.attr)
            elif isinstance(node.func, ast.Name):
                call_names.append(node.func.id)

    forbidden_patterns = [
        "run_gemini_request", "run_deepseek_review", "run_agent_web",
        "run_patch_plan_with_artifacts", "apply_patch", "run_benchmarks",
        "start_benchmark_run_async", "start_overnight_async", "launch_worker",
        "call_model", "consolidate_all", "subprocess",
    ]
    hits = [p for p in forbidden_patterns if p in call_names]
    assert not hits, f"web/auth_gate.py must not call: {hits}"
