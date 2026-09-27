"""AUTH.WEB.1 real-Chromium integration: production Flask app, template and JS.

Requires requirements_browser.txt and an installed Playwright Chromium. The app
and a synthetic cross-origin page run on loopback listeners; every other browser
request is intercepted (Mermaid gets a local stub). No model, database or
external network is used.
"""
from __future__ import annotations

import html
import http.client
import json
import os
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest

from tests.test_auth_web1 import TOKEN, _tree, configure_offline_web

COOKIE = "cattus_ui_session"
FORM_ANSWER = "AUTH.WEB.1 native form fixture answer"
IMPORT_PATH = "/dream/references/import"
ATTACKER_PAGE = """<!doctype html>
<html><head><title>synthetic cross-origin page</title></head><body>
<iframe name="sink" title="sink"></iframe>
<form id="forged" method="POST" action="{action}" target="sink">
<input name="repo_path" value="{repo}">
<input name="topic" value="forged form">
<input name="raw_input" value="forged form">
<input name="csrf_token" value="{csrf}">
</form>
<script>
window.fetchResult = fetch({action_js}, {{method: "POST", mode: "no-cors", credentials: "include",
  body: new URLSearchParams({{repo_path: {repo_js}, topic: "forged fetch", raw_input: "forged fetch", csrf_token: {csrf_js}}})}})
  .then(response => response.type, error => "error:" + error);
document.getElementById("forged").submit();
</script>
</body></html>
"""


class _Listener:
    def __init__(self, wsgi_app):
        from werkzeug.serving import make_server

        self.server = make_server("127.0.0.1", 0, wsgi_app, threaded=True)
        self.port = self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


@pytest.fixture(scope="module")
def chromium():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as driver:
        browser = driver.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def live(tmp_path, monkeypatch, chromium):
    state = configure_offline_web(tmp_path, monkeypatch, allow_loopback=True)
    original_gate = state.wa._should_allow_mutation
    decisions: list[SimpleNamespace] = []

    def recording_gate(**kwargs):
        decision = original_gate(**kwargs)
        decisions.append(SimpleNamespace(
            path=kwargs.get("path"),
            code=decision.code,
            origin=kwargs["headers"].get("Origin"),
            session=kwargs["browser_session"].status,
            csrf_submissions=len(kwargs.get("csrf_submissions") or ()),
        ))
        return decision

    monkeypatch.setattr(state.wa, "_should_allow_mutation", recording_gate)
    monkeypatch.setattr(
        state.wa,
        "_run_mode",
        lambda **kwargs: ({"answer": FORM_ANSWER, "context": "", "graph": "", "state": "",
                           "patch": "", "validation": ""}, kwargs["project_tag"]),
    )
    attacker_pages: dict[str, str] = {}

    def attacker_app(environ, start_response):
        body = attacker_pages.get(environ.get("PATH_INFO", "/"), "<!doctype html><title>empty</title>")
        data = body.encode("utf-8")
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(data)))])
        return [data]

    app_listener = _Listener(state.app)
    attacker_listener = _Listener(attacker_app)
    base = f"http://127.0.0.1:{app_listener.port}"
    attacker_base = f"http://127.0.0.1:{attacker_listener.port}"
    alias_base = f"http://localhost:{app_listener.port}"
    external: list[str] = []
    errors: list[str] = []
    context = chromium.new_context(service_workers="block")

    def route(request_route):
        url = request_route.request.url
        if url.startswith("https://cdn.jsdelivr.net/npm/mermaid@10/"):
            request_route.fulfill(
                status=200,
                content_type="application/javascript",
                body='window.mermaid={initialize(){},render(){throw new Error("graph outside AUTH.WEB.1");}};',
            )
        elif url.startswith((base + "/", attacker_base + "/", alias_base + "/")):
            request_route.continue_()
        else:
            external.append(url)
            request_route.abort()

    context.route("**/*", route)
    page = context.new_page()
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("dialog", lambda dialog: dialog.dismiss())
    state.__dict__.update(
        page=page, context=context, base=base, attacker_base=attacker_base, alias_base=alias_base,
        port=app_listener.port, decisions=decisions, attacker_pages=attacker_pages, errors=errors,
    )
    try:
        yield state
    finally:
        context.close()
        app_listener.close()
        attacker_listener.close()
    assert external == []
    assert errors == []
    assert state.calls == []


def _meta(page, name):
    return page.locator(f'meta[name="{name}"]').get_attribute("content")


def _wait_meta(page, name, value):
    page.wait_for_function(
        "([name, value]) => document.querySelector(`meta[name=\"${name}\"]`).content === value",
        arg=[name, value],
    )


def _wait_panel_reason(page, reason):
    page.wait_for_function(
        "(reason) => document.getElementById('cattusAuthPanel')?.dataset.reason === reason",
        arg=reason,
    )


def _prepare_reference(page, repo, label):
    page.locator("#repoPathInput").fill(str(repo))
    page.evaluate(
        """([topic, raw]) => {
            document.getElementById('dreamResearchTopic').value = topic;
            document.getElementById('dreamResearchRawInput').value = raw;
        }""",
        ["AUTH.WEB.1 " + label, "Synthetic browser import: " + label],
    )


def _import_via_ui(page):
    with page.expect_response(
        lambda response: urlsplit(response.url).path == IMPORT_PATH and response.request.method == "POST"
    ) as info:
        page.evaluate("importDreamReference()")
    return info.value


def _sign_in(page, token):
    page.locator("#cattusAuthToken").fill(token)
    with page.expect_response(lambda response: urlsplit(response.url).path == "/auth/login") as info:
        page.locator("#cattusAuthSignIn").click()
    return info.value


def _session_cookies(live, base=None):
    return [cookie for cookie in live.context.cookies(base or live.base) if cookie["name"] == COOKIE]


def _wait_until(predicate, timeout=15.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("condition not reached before timeout")


def _import_decisions(live, origin):
    return [d for d in live.decisions if d.path == IMPORT_PATH and d.origin == origin]


def _read_alias_page_from_base(live, route):
    if route.request.method != "GET":
        route.continue_()
        return
    route.fulfill(response=live.context.request.get(live.base + route.request.url[len(live.alias_base):]))


def _run_cross_origin_page(live, csrf):
    action = live.base + IMPORT_PATH
    live.attacker_pages["/"] = ATTACKER_PAGE.format(
        action=html.escape(action, quote=True),
        repo=html.escape(str(live.repo), quote=True),
        csrf=html.escape(csrf, quote=True),
        action_js=json.dumps(action),
        repo_js=json.dumps(str(live.repo)),
        csrf_js=json.dumps(csrf),
    )
    attacker = live.context.new_page()
    attacker.on("pageerror", lambda error: live.errors.append(str(error)))
    attacker.goto(live.attacker_base + "/")
    _wait_until(lambda: len(_import_decisions(live, live.attacker_base)) >= 2)
    assert attacker.evaluate("window.fetchResult") == "opaque"
    attacker.close()
    return _import_decisions(live, live.attacker_base)


def test_auth_on_ui_signs_in_and_mutates_through_production_transport(live, monkeypatch):
    monkeypatch.setenv("WEB_AUTH_TOKEN", TOKEN)
    page = live.page
    first = page.goto(live.base + "/")
    assert first.status == 200 and TOKEN not in first.text()
    panel = page.locator("#cattusAuthPanel")
    panel.wait_for(state="visible")
    assert panel.get_attribute("data-state") == "signed_out"
    assert _meta(page, "cattus-auth-state") == "signed_out"
    anonymous_csrf = _meta(page, "cattus-csrf-token")

    login = _sign_in(page, TOKEN)
    assert login.status == 200
    request = login.request
    assert request.method == "POST" and urlsplit(request.url).query == ""
    assert parse_qs(request.post_data) == {"web_auth_token": [TOKEN]}
    login_headers = request.all_headers()
    assert login_headers["origin"] == live.base and login_headers["x-csrf-token"] == anonymous_csrf
    _wait_meta(page, "cattus-auth-state", "signed_in")
    csrf = _meta(page, "cattus-csrf-token")
    assert csrf != anonymous_csrf and panel.get_attribute("data-state") == "signed_in"
    assert page.locator("#cattusAuthToken").count() == 0
    cookies = _session_cookies(live)
    assert len(cookies) == 1 and cookies[0]["httpOnly"] is True and cookies[0]["sameSite"] == "Lax"
    assert cookies[0]["secure"] is False and TOKEN not in cookies[0]["value"]
    assert page.evaluate("document.cookie") == ""

    _prepare_reference(page, live.repo, "happy")
    mutation = _import_via_ui(page)
    headers = mutation.request.all_headers()
    assert headers["origin"] == live.base and headers["x-csrf-token"] == csrf
    assert "authorization" not in headers and "x-cattus-web-token" not in headers
    assert TOKEN not in json.dumps(headers) and TOKEN not in (mutation.request.post_data or "")
    assert mutation.status == 200 and mutation.json()["ok"] is True
    assert Path(mutation.json()["json_path"]).is_file()
    page.wait_for_function("document.getElementById('dreamReferencesStatus').textContent.startsWith('Imported ')")
    decision = _import_decisions(live, live.base)[-1]
    assert (decision.code, decision.session, decision.csrf_submissions) == ("browser_session_authenticated", "valid", 1)

    page.locator("textarea[name='query']").fill("Explain the AUTH.WEB.1 fixture")
    with page.expect_response(
        lambda response: urlsplit(response.url).path == "/" and response.request.method == "POST"
    ) as info:
        page.locator("#primarySubmit").click()
    form = info.value
    assert form.status == 200
    assert parse_qs(form.request.post_data)["csrf_token"] == [csrf]
    page.wait_for_load_state("load")
    assert TOKEN not in form.text()
    assert TOKEN not in form.request.post_data and "csrf" not in page.url and TOKEN not in page.url
    page.wait_for_function("(text) => document.getElementById('answer')?.textContent.includes(text)", arg=FORM_ANSWER)
    _wait_meta(page, "cattus-auth-state", "signed_in")

    exposure = page.evaluate(
        """(token) => ({
            html: document.documentElement.outerHTML.includes(token),
            attributes: [...document.querySelectorAll('*')].some(e => [...e.attributes].some(a => a.value.includes(token))),
            values: [...document.querySelectorAll('input, textarea')].some(e => e.value.includes(token)),
            storage: JSON.stringify([Object.entries(localStorage), Object.entries(sessionStorage)]).includes(token),
            history: location.href.includes(token),
        })""",
        TOKEN,
    )
    assert exposure == {"html": False, "attributes": False, "values": False, "storage": False, "history": False}
    scripts = [src for src in page.evaluate("[...document.scripts].map(s => s.src).filter(Boolean)")
               if src.startswith(live.base + "/")]
    assert any(src.endswith("/static/request_integrity.js") for src in scripts)
    for src in scripts:
        assert TOKEN not in live.context.request.get(src).text(), src


def test_auth_on_signed_out_and_expired_sessions_show_auth_required_without_retry(live, monkeypatch):
    from web import browser_session

    monkeypatch.setenv("WEB_AUTH_TOKEN", TOKEN)
    page = live.page
    posts: list[str] = []
    page.on("request", lambda request: posts.append(urlsplit(request.url).path) if request.method == "POST" else None)
    page.goto(live.base + "/")
    _prepare_reference(page, live.repo, "signed_out")
    before = _tree(live.root)
    response = _import_via_ui(page)
    assert response.status == 401 and response.headers["x-cattus-request-integrity"] == "auth_required"
    _wait_panel_reason(page, "auth_required")
    panel = page.locator("#cattusAuthPanel")
    assert panel.is_visible() and panel.get_attribute("data-state") == "signed_out"
    assert page.locator("#cattusAuthToken").is_visible()
    assert _tree(live.root) == before and posts.count(IMPORT_PATH) == 1

    page.locator("textarea[name='query']").fill("held back while signed out")
    page.locator("#primarySubmit").click()
    _wait_panel_reason(page, "sign_in_required_for_form")
    page.wait_for_timeout(500)
    assert "/" not in posts and not (live.root / "sessions.json").exists()

    assert _sign_in(page, TOKEN).status == 200
    _wait_meta(page, "cattus-auth-state", "signed_in")
    assert _import_via_ui(page).status == 200

    monkeypatch.setattr(browser_session, "_PROCESS_SECRET", os.urandom(32))
    posts.clear()
    before = _tree(live.root)
    response = _import_via_ui(page)
    assert response.status == 403 and response.headers["x-cattus-request-integrity"] == "browser_session_invalid"
    assert response.json()["auth_required"] is True
    _wait_panel_reason(page, "browser_session_invalid")
    _wait_meta(page, "cattus-auth-state", "signed_out")
    assert page.locator("#cattusAuthToken").is_visible()
    page.wait_for_timeout(300)
    assert _tree(live.root) == before and posts.count(IMPORT_PATH) == 1

    assert _sign_in(page, TOKEN).status == 200
    _wait_meta(page, "cattus-auth-state", "signed_in")
    assert _import_via_ui(page).status == 200


def test_wrong_web_token_establishes_no_browser_session(live, monkeypatch):
    monkeypatch.setenv("WEB_AUTH_TOKEN", TOKEN)
    page = live.page
    page.goto(live.base + "/")
    anonymous = [cookie["value"] for cookie in _session_cookies(live)]
    csrf = _meta(page, "cattus-csrf-token")
    assert len(anonymous) == 1
    response = _sign_in(page, TOKEN + "-wrong")
    assert response.status == 401 and response.json()["error_code"] == "web_auth_token_invalid"
    assert TOKEN not in response.text()
    _wait_panel_reason(page, "web_auth_token_invalid")
    assert _meta(page, "cattus-auth-state") == "signed_out" and _meta(page, "cattus-csrf-token") == csrf
    assert [cookie["value"] for cookie in _session_cookies(live)] == anonymous
    _prepare_reference(page, live.repo, "wrong_token")
    before = _tree(live.root)
    assert _import_via_ui(page).status == 401
    assert _tree(live.root) == before


def test_cross_origin_page_with_valid_session_and_copied_csrf_is_rejected(live, monkeypatch):
    monkeypatch.setenv("WEB_AUTH_TOKEN", TOKEN)
    page = live.page
    page.goto(live.base + "/")
    assert _sign_in(page, TOKEN).status == 200
    _wait_meta(page, "cattus-auth-state", "signed_in")
    csrf = _meta(page, "cattus-csrf-token")
    before = _tree(live.root)
    decisions = _run_cross_origin_page(live, csrf)
    assert [(d.code, d.session, d.csrf_submissions) for d in decisions] == [("origin_not_allowed", "valid", 1)] * 2
    assert _tree(live.root) == before
    _prepare_reference(page, live.repo, "still_valid")
    assert _import_via_ui(page).status == 200


def test_auth_off_browser_mutations_remain_exact_origin_and_csrf_protected(live):
    page = live.page
    page.goto(live.base + "/")
    assert _meta(page, "cattus-auth-state") == "not_required"
    assert page.locator("#cattusAuthPanel").is_hidden()
    _prepare_reference(page, live.repo, "auth_off")
    response = _import_via_ui(page)
    assert response.status == 200 and response.request.all_headers()["x-csrf-token"] == _meta(page, "cattus-csrf-token")
    assert _import_decisions(live, live.base)[-1].code == "loopback_allowed"

    before = _tree(live.root)
    decisions = _run_cross_origin_page(live, _meta(page, "cattus-csrf-token"))
    assert [(d.code, d.session, d.csrf_submissions) for d in decisions] == [("origin_not_allowed", "valid", 1)] * 2
    assert _tree(live.root) == before

    alias = live.context.new_page()
    alias.on("pageerror", lambda error: live.errors.append(str(error)))
    alias.on("dialog", lambda dialog: dialog.dismiss())
    # AUTH.WEB.READ.1: the unconfigured alias host no longer serves the page.
    assert alias.goto(live.alias_base + "/").status == 421
    # The same page executing at the alias origin still cannot mutate: its reads
    # come from the configured address, and its POST goes to the alias host.
    alias.route(live.alias_base + "/**", lambda route: _read_alias_page_from_base(live, route))
    assert alias.goto(live.alias_base + "/").status == 200
    _prepare_reference(alias, live.repo, "localhost_alias")
    response = _import_via_ui(alias)
    assert response.status == 403 and response.headers["x-cattus-request-integrity"] == "origin_not_allowed"
    assert response.request.all_headers()["origin"] == live.alias_base
    _wait_panel_reason(alias, "origin_not_allowed")
    assert _tree(live.root) == before
    alias.close()


def test_real_server_duplicate_and_non_ascii_origin_headers_fail_closed(live):
    body = urlencode({"repo_path": str(live.repo), "topic": "raw", "raw_input": "raw"}).encode()
    before = _tree(live.root)
    for headers, code in (
        ([("Origin", live.base), ("Origin", live.base)], "origin_ambiguous"),
        ([("Origin", live.base + "é")], "origin_malformed"),
        ([("Origin", "null")], "origin_null"),
    ):
        connection = http.client.HTTPConnection("127.0.0.1", live.port, timeout=10)
        try:
            connection.putrequest("POST", IMPORT_PATH)
            for name, value in headers:
                connection.putheader(name, value)
            connection.putheader("Content-Type", "application/x-www-form-urlencoded")
            connection.putheader("Content-Length", str(len(body)))
            connection.endheaders(body)
            response = connection.getresponse()
            payload = json.loads(response.read())
        finally:
            connection.close()
        assert response.status == 403 and payload["error_code"] == code
        assert response.getheader("X-CATTUS-Request-Integrity") == code
    assert _tree(live.root) == before


def test_browser_transport_owner_overhead_is_bounded(live):
    page = live.page
    page.goto(live.base + "/")
    per_request_us = page.evaluate(
        """() => {
            const samples = [];
            for (let batch = 0; batch < 15; batch++) {
                const started = performance.now();
                for (let index = 0; index < 2000; index++) {
                    CattusRequestIntegrity.prepare('/dream/apply', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                        body: 'repo_path=x',
                    });
                }
                samples.push((performance.now() - started) * 1000 / 2000);
            }
            samples.sort((a, b) => a - b);
            return samples[Math.floor(samples.length / 2)];
        }"""
    )
    result = {"protected_request_preparation_us": round(per_request_us, 3)}
    print("AUTH_WEB1_BROWSER_PERFORMANCE=" + json.dumps(result))
    if os.environ.get("AUTH_WEB1_BROWSER_PERFORMANCE_FILE"):
        Path(os.environ["AUTH_WEB1_BROWSER_PERFORMANCE_FILE"]).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    assert per_request_us < 1000
