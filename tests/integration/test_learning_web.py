"""Teacher pilot over the actual Flask/auth boundary, without providers/network."""
from __future__ import annotations

import re
import uuid

import pytest

from tests.test_auth_web1 import configure_offline_web

BASE = "http://localhost:5000"
CSRF = re.compile(r'<meta name="cattus-csrf-token" content="([A-Za-z0-9_-]{43})">')


@pytest.fixture
def pilot(tmp_path, monkeypatch):
    state = configure_offline_web(tmp_path, monkeypatch)
    monkeypatch.setitem(state.app.config, "LEARNING_STORE_PATH", tmp_path / "learning" / "sessions.sqlite3")
    yield state
    assert state.calls == []


def page(client):
    response = client.get("/learn", base_url=BASE)
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    return CSRF.search(response.get_data(as_text=True)).group(1)


def send(client, csrf, path, data=None, method="POST", origin=BASE):
    return client.open(path, method=method, base_url=BASE, json=data,
                       headers={"Origin": origin, "X-CSRF-Token": csrf})


def create(client, csrf):
    response = send(client, csrf, "/learn/api/sessions", {})
    assert response.status_code == 201, response.get_data(as_text=True)
    return response.get_json()["session"]


def action(client, csrf, session, name, payload=None, request_id=None):
    return send(client, csrf, f"/learn/api/sessions/{session['id']}/actions", {
        "action": name, "payload": payload or {},
        "expected_revision": session["revision"], "request_id": request_id or str(uuid.uuid4()),
    })


def test_real_teacher_flow_preserves_assistance_and_resumes(pilot):
    client = pilot.app.test_client()
    csrf = page(client)
    session = create(client, csrf)
    assert session["total_items"] == 3
    assert session["item"]["solution"] is None
    assert "correct_option" not in session["item"]
    response = action(client, csrf, session, "answer", {"option_id": "b", "reflection": "Theo đối tượng Cat."})
    assert response.status_code == 200
    session = response.get_json()["session"]
    assert session["item"]["feedback"]["correct"] is True
    assert session["summary"]["independent_successes"] == 1
    session = action(client, csrf, session, "next").get_json()["session"]
    session = action(client, csrf, session, "hint").get_json()["session"]
    session = action(client, csrf, session, "answer", {"option_id": "c"}).get_json()["session"]
    assert session["item"]["feedback"]["correct"] is True
    assert session["summary"]["independent_successes"] == 1
    assert session["summary"]["assisted_successes"] == 1
    page(client)
    resumed = client.get("/learn/api/session", base_url=BASE).get_json()["session"]
    assert resumed == session
    session = action(client, csrf, session, "next").get_json()["session"]
    session = action(client, csrf, session, "answer", {"option_id": "a"}).get_json()["session"]
    session = action(client, csrf, session, "next").get_json()["session"]
    assert session["status"] == "completed"
    assert session["summary"]["independent_successes"] == 2
    assert session["summary"]["assisted_successes"] == 1
    assert not list(pilot.repo.iterdir())


def test_records_and_exports_are_scoped_to_durable_learner_cookie(pilot):
    first = pilot.app.test_client()
    csrf = page(first)
    session = create(first, csrf)
    from web.routes.learning_routes import LEARNER_COOKIE
    cookie = first.get_cookie(LEARNER_COOKIE, domain="localhost", path="/learn")
    assert cookie.http_only and cookie.same_site == "Strict"
    other = pilot.app.test_client()
    other_csrf = page(other)
    assert other.get("/learn/api/session", base_url=BASE).get_json()["session"] is None
    for suffix in ("", "/export"):
        assert other.get(f"/learn/api/sessions/{session['id']}{suffix}", base_url=BASE).status_code == 404
    assert send(other, other_csrf, f"/learn/api/sessions/{session['id']}", method="DELETE").status_code == 404
    # A fresh browser auth/CSRF session can resume the same durable learner.
    resumed = pilot.app.test_client()
    resumed.set_cookie(LEARNER_COOKIE, cookie.value, domain="localhost", path="/learn")
    page(resumed)
    assert resumed.get("/learn/api/session", base_url=BASE).get_json()["session"]["id"] == session["id"]


def test_learning_mutations_keep_origin_and_csrf_gates(pilot):
    client = pilot.app.test_client()
    csrf = page(client)
    missing = client.post("/learn/api/sessions", base_url=BASE, json={}, headers={"Origin": BASE})
    assert missing.status_code == 403
    foreign = send(client, csrf, "/learn/api/sessions", {}, origin="http://localhost:7999")
    assert foreign.status_code == 403
    assert client.get("/learn/api/session", base_url=BASE).get_json()["session"] is None
    session = create(client, csrf)
    assert client.delete(f"/learn/api/sessions/{session['id']}", base_url=BASE,
                         headers={"Origin": BASE}).status_code == 403


def test_configured_auth_protects_learning_reads_too(pilot, monkeypatch):
    client = pilot.app.test_client()
    csrf = page(client)
    session = create(client, csrf)
    monkeypatch.setenv("WEB_AUTH_TOKEN", "teacher-test-token")
    for path in ("/learn/api/session", f"/learn/api/sessions/{session['id']}/export"):
        response = client.get(path, base_url=BASE)
        assert response.status_code == 401
        assert response.get_json()["error_code"] == "auth_required"
    login = client.post("/auth/login", base_url=BASE,
                        headers={"Origin": BASE, "X-CSRF-Token": csrf},
                        data={"web_auth_token": "teacher-test-token"})
    assert login.status_code == 200
    assert client.get("/learn/api/session", base_url=BASE).get_json()["session"]["id"] == session["id"]


def test_http_retry_is_idempotent_and_stale_tab_cannot_overwrite(pilot):
    client = pilot.app.test_client()
    csrf = page(client)
    session = create(client, csrf)
    first = action(client, csrf, session, "hint", request_id="stable-request")
    assert first.status_code == 200
    second = action(client, csrf, session, "hint", request_id="stable-request")
    assert second.get_json() == first.get_json()
    assert action(client, csrf, session, "solution", request_id="stable-request").status_code == 409
    assert action(client, csrf, session, "hint").status_code == 409
    current = client.get("/learn/api/session", base_url=BASE).get_json()["session"]
    assert current["item"]["hint_count"] == 1


def test_export_and_delete_cover_session_events(pilot):
    client = pilot.app.test_client()
    csrf = page(client)
    session = create(client, csrf)
    session = action(client, csrf, session, "hint").get_json()["session"]
    path = f"/learn/api/sessions/{session['id']}"
    exported = client.get(path + "/export", base_url=BASE)
    assert exported.status_code == 200
    assert "attachment" in exported.headers["Content-Disposition"]
    assert exported.get_json()["events"]
    assert send(client, csrf, path, method="DELETE").status_code == 200
    assert client.get(path + "/export", base_url=BASE).status_code == 404
    assert client.get("/learn/api/session", base_url=BASE).get_json()["session"] is None


def test_wrong_prediction_gets_guidance_before_explicit_solution(pilot):
    client = pilot.app.test_client()
    csrf = page(client)
    session = create(client, csrf)
    session = action(client, csrf, session, "answer", {"option_id": "a"}).get_json()["session"]
    assert session["item"]["feedback"]["correct"] is False
    assert "meow" not in session["item"]["feedback"]["body"]
    assert session["item"]["solution"] is None
    session = action(client, csrf, session, "solution").get_json()["session"]
    assert "meow" in session["item"]["solution"]["body"]
    session = action(client, csrf, session, "answer", {"option_id": "b"}).get_json()["session"]
    assert session["summary"]["independent_successes"] == 0
    assert session["summary"]["independent_failures"] == 1
    assert session["summary"]["assisted_successes"] == 1


@pytest.mark.parametrize("body", [[], {"repo_path": "../../private"}, {"action": "apply_patch"}])
def test_create_rejects_non_lesson_payloads(pilot, body):
    client = pilot.app.test_client()
    csrf = page(client)
    assert send(client, csrf, "/learn/api/sessions", body).status_code == 400
    assert not list(pilot.repo.iterdir())


def test_oversize_and_unknown_actions_are_structured_failures(pilot):
    client = pilot.app.test_client()
    csrf = page(client)
    assert send(client, csrf, "/learn/api/sessions", {"text": "x" * 17000}).status_code == 413
    session = create(client, csrf)
    assert action(client, csrf, session, "run_shell", {"command": "anything"}).status_code == 400
    assert client.get("/learn/api/session", base_url=BASE).get_json()["session"] == session
