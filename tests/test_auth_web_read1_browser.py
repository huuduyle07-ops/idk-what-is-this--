"""AUTH.WEB.READ.1 real-Chromium integration: rebound, alias and published hosts.

Chromium resolves evil.example to 127.0.0.1 through --host-resolver-rules, so
no system DNS or hosts file changes. The production app runs on a loopback
listener. A dispatcher on that listener serves the attacker's page, the way the
attacker's own server answered before its name was rebound; every other path
goes to the app. An in-process TCP forwarder publishes the listener on a second
port (the Docker 5056->5000 model). Every other browser request is intercepted:
no model, database or external network.
"""
from __future__ import annotations

import json
import socket
import threading
from urllib.parse import urlsplit

import pytest

from tests.test_auth_web1 import _tree, configure_offline_web
from tests.test_auth_web1_browser import _Listener, _import_via_ui, _meta, _prepare_reference
from tests.test_auth_web_read1 import MARKER, SESSION_ID, _seed, _spy_data_access, _spy_view

ATTACKER_PATH = "/__rebinding_attacker__"
ATTACKER_PAGE = """<!doctype html>
<html><head><title>rebinding page</title></head><body>
<script>
window.stolen = (async () => {
  const results = [];
  for (const path of %s) {
    try {
      const response = await fetch(path, {credentials: "include", cache: "no-store"});
      results.push({path, status: response.status, body: await response.text()});
    } catch (error) {
      results.push({path, status: 0, body: "error:" + error});
    }
  }
  return results;
})();
</script>
</body></html>
"""


class _Forwarder:
    """Publishes 127.0.0.1:<upstream> on another loopback port, bytes unchanged."""

    def __init__(self, upstream_port: int):
        self.upstream_port = upstream_port
        self.listener = socket.socket()
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(16)
        self.port = self.listener.getsockname()[1]
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self):
        while True:
            try:
                client, _ = self.listener.accept()
            except OSError:
                return
            upstream = socket.create_connection(("127.0.0.1", self.upstream_port))
            for source, target in ((client, upstream), (upstream, client)):
                threading.Thread(target=self._pump, args=(source, target), daemon=True).start()

    @staticmethod
    def _pump(source, target):
        try:
            while data := source.recv(65536):
                target.sendall(data)
        except OSError:
            pass
        finally:
            for sock in (source, target):
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

    def close(self):
        self.listener.close()


@pytest.fixture(scope="module")
def chromium():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as driver:
        browser = driver.chromium.launch(headless=True, args=["--host-resolver-rules=MAP evil.example 127.0.0.1"])
        yield browser
        browser.close()


@pytest.fixture
def live(tmp_path, monkeypatch, chromium):
    state = _seed(configure_offline_web(tmp_path, monkeypatch, allow_loopback=True))
    state.reached, state.touched = [], []
    for endpoint, _ in state.sensitive.values():
        _spy_view(monkeypatch, state.app, endpoint, state.reached)
    _spy_data_access(monkeypatch, state, state.touched)
    paths = [path for _, path in state.sensitive.values()] + ["/", "/auth/session", "/static/request_integrity.js"]
    page_body = (ATTACKER_PAGE % json.dumps(paths)).encode("utf-8")

    def dispatcher(environ, start_response):
        if environ.get("PATH_INFO") == ATTACKER_PATH:
            start_response("200 OK", [("Content-Type", "text/html; charset=utf-8"),
                                      ("Content-Length", str(len(page_body)))])
            return [page_body]
        return state.app(environ, start_response)

    listener = _Listener(dispatcher)
    forwarder = _Forwarder(listener.port)
    port, published = listener.port, forwarder.port
    allowed = tuple(f"http://{host}:{number}/" for host in ("127.0.0.1", "localhost", "evil.example")
                    for number in (port, published))
    external: list[str] = []
    errors: list[str] = []
    context = chromium.new_context(service_workers="block")

    def route(request_route):
        url = request_route.request.url
        if url.startswith("https://cdn.jsdelivr.net/npm/mermaid@10/"):
            request_route.fulfill(status=200, content_type="application/javascript",
                                  body="window.mermaid={initialize(){},render(){}};")
        elif url.startswith(allowed):
            request_route.continue_()
        else:
            external.append(url)
            request_route.abort()

    context.route("**/*", route)
    page = context.new_page()
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("dialog", lambda dialog: dialog.dismiss())
    state.__dict__.update(page=page, context=context, port=port, published=published, paths=paths)
    try:
        yield state
    finally:
        context.close()
        forwarder.close()
        listener.close()
    assert external == [] and errors == [] and state.calls == []


def _steal(live):
    page = live.page
    response = page.goto(f"http://evil.example:{live.port}{ATTACKER_PATH}")
    assert response.status == 200 and urlsplit(page.url).hostname == "evil.example"
    return page.evaluate("window.stolen")


def _trusted_reads(live):
    page = live.page
    assert page.goto(f"http://127.0.0.1:{live.port}/").status == 200
    return page.evaluate(
        """async (paths) => {
            const results = [];
            for (const path of paths) {
                const response = await fetch(path, {cache: "no-store"});
                results.push({path, status: response.status, body: await response.text()});
            }
            return results;
        }""",
        live.paths,
    )


def test_rebound_page_reads_nothing_while_the_trusted_host_reads_the_same_data(live):
    stolen = _steal(live)
    assert [item["path"] for item in stolen] == live.paths
    for item in stolen:
        assert item["status"] == 421, item
        assert json.loads(item["body"])["error_code"] == "host_not_allowed", item
        assert MARKER not in item["body"], item["path"]
    assert live.reached == [] and live.touched == []
    top = live.page.goto(f"http://evil.example:{live.port}/session/{SESSION_ID}")
    assert top.status == 421 and MARKER not in top.text()
    assert [cookie for cookie in live.context.cookies() if cookie["domain"] == "evil.example"] == []

    trusted = _trusted_reads(live)
    assert [item["status"] for item in trusted] == [200] * len(live.paths)
    for item in trusted[:len(live.sensitive)]:
        assert MARKER in item["body"], item["path"]
    assert set(live.reached) == {endpoint for endpoint, _ in live.sensitive.values()} and live.touched


def test_entry_app_without_the_boundary_leaks_to_a_rebound_page(live, monkeypatch):
    from web.read_host import ReadHostBoundary

    assert isinstance(live.app.wsgi_app, ReadHostBoundary)
    monkeypatch.setattr(live.app, "wsgi_app", live.app.wsgi_app.wsgi_app)
    stolen = _steal(live)
    for item in stolen[:len(live.sensitive)]:
        assert item["status"] == 200 and MARKER in item["body"], item["path"]
    assert live.touched


def test_unconfigured_alias_and_wrong_port_are_refused_in_the_browser(live):
    page = live.page
    for url in (f"http://localhost:{live.port}/", f"http://localhost:{live.port}/history/sessions",
                f"http://127.0.0.1:{live.published}/", f"http://localhost:{live.published}/"):
        response = page.goto(url)
        assert response.status == 421, url
        assert MARKER not in response.text() and "<" not in response.text()
    assert live.reached == [] and live.touched == []
    assert page.goto(f"http://127.0.0.1:{live.port}/").status == 200
    assert len(_meta(page, "cattus-csrf-token")) == 43


def test_published_origin_reads_and_mutates_while_the_socket_address_is_refused(live, monkeypatch):
    published = f"http://localhost:{live.published}"
    monkeypatch.setenv("WEB_ALLOWED_ORIGINS", published)
    page = live.page
    assert page.goto(published + "/").status == 200
    assert _meta(page, "cattus-auth-state") == "not_required"
    page.wait_for_function("(marker) => document.getElementById('sessionList')?.textContent.includes(marker)",
                           arg=MARKER)
    _prepare_reference(page, live.repo, "published_origin")
    response = _import_via_ui(page)
    assert response.status == 200 and response.request.all_headers()["origin"] == published
    before = _tree(live.root)
    for url in (f"http://127.0.0.1:{live.port}/", f"http://localhost:{live.port}/",
                f"http://127.0.0.1:{live.published}/"):
        refused = page.goto(url)
        assert refused.status == 421 and MARKER not in refused.text(), url
    assert _tree(live.root) == before
