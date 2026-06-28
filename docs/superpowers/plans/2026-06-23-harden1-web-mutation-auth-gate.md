# HARDEN.1 Web Mutation Auth / CSRF Gate — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a centralized Flask `before_request` security gate to CATTUS's web app that blocks unauthenticated or cross-origin mutating HTTP requests (POST/PUT/PATCH/DELETE).

**Architecture:** A single new module `web/auth_gate.py` contains pure, easily-testable helper functions (`is_loopback_host`, `extract_web_auth_token`, `origin_matches_request`, `should_allow_mutation`) and a `GateDecision` dataclass. `web/app.py` registers one `@app.before_request` hook that calls `should_allow_mutation` and aborts on deny. Registry entry for HARDEN.1 is added to `docs/roadmap/phase_registry.json`; picker/registry seed tests are updated to confirm the new phase is registered.

**Tech Stack:** Python 3.x, Flask (before_request), dataclasses (stdlib), os.environ, pytest

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| **Create** | `web/auth_gate.py` | Pure gate helpers + GateDecision |
| **Modify** | `web/app.py` | Wire `@app.before_request` + `app.secret_key` + remove `debug=True` |
| **Create** | `tests/test_web_mutation_auth_gate.py` | 15-test suite |
| **Modify** | `docs/roadmap/phase_registry.json` | Add HARDEN.1 entry |
| **Modify** | `tests/test_phase_registry.py` | Add HARDEN.1 to seed test |
| **Modify** | `tests/test_phase_picker.py` | Add HARDEN.1 to seed test |
| **Modify** | `docs/AI_Coding_Agent_Mentor_Operating_Roadmap_2026-06-Next.md` | Document HARDEN track + HARDEN.1 |
| **Modify** | `README.md` | Document WEB_AUTH_TOKEN, WEB_SECRET_KEY, local-dev / network behavior |

---

## Task 1: Create `web/auth_gate.py` — Pure Gate Helpers

**Files:**
- Create: `web/auth_gate.py`

- [ ] **Step 1: Write the module**

```python
from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse


_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


@dataclass
class GateDecision:
    allowed: bool
    status_code: int
    reason: str


def is_loopback_host(value: str) -> bool:
    """Return True if value is a loopback hostname or IP."""
    if not value:
        return False
    host = value.split(":")[0].strip().lower()
    return host in _LOOPBACK_HOSTS


def extract_web_auth_token(headers) -> str:
    """Return the bearer token from headers or empty string."""
    x_token = (headers.get("X-CATTUS-Web-Token") or "").strip()
    if x_token:
        return x_token
    auth = (headers.get("Authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


def origin_matches_request(origin: str, host: str) -> bool:
    """Return True when origin host equals request host (allows same-origin)."""
    if not origin or not host:
        return True
    try:
        origin_host = urlparse(origin).hostname or ""
    except Exception:
        return False
    request_host = host.split(":")[0].strip().lower()
    origin_host = origin_host.strip().lower()
    if not origin_host:
        return True
    if origin_host == request_host:
        return True
    if origin_host in _LOOPBACK_HOSTS and request_host in _LOOPBACK_HOSTS:
        return True
    return False


def should_allow_mutation(
    method: str,
    remote_addr: str,
    headers,
    host: str,
    configured_token: str | None,
) -> GateDecision:
    """Decide whether a request should be allowed through the mutation gate.

    Args:
        method: HTTP method string (e.g. "POST").
        remote_addr: Client IP address string.
        headers: Mapping-like object with HTTP headers (e.g. flask.request.headers).
        host: Request Host header value (e.g. "localhost:5000").
        configured_token: Value of WEB_AUTH_TOKEN env var, or None/empty if unset.

    Returns:
        GateDecision with allowed, status_code, reason.
    """
    if method.upper() not in _MUTATING_METHODS:
        return GateDecision(allowed=True, status_code=200, reason="safe method")

    # CSRF / Origin check — runs before auth so cross-origin is always rejected.
    origin = (headers.get("Origin") or "").strip()
    referer = (headers.get("Referer") or "").strip()
    check_origin = origin or referer
    if check_origin and not origin_matches_request(check_origin, host):
        return GateDecision(
            allowed=False,
            status_code=403,
            reason=f"cross-origin mutation rejected: origin={check_origin!r} host={host!r}",
        )

    token = configured_token.strip() if configured_token else ""

    if token:
        # Token is configured — require a matching bearer on all mutating requests.
        provided = extract_web_auth_token(headers)
        if not provided:
            return GateDecision(
                allowed=False,
                status_code=401,
                reason="mutation requires WEB_AUTH_TOKEN; no token provided",
            )
        if provided != token:
            return GateDecision(
                allowed=False,
                status_code=403,
                reason="mutation token mismatch",
            )
        return GateDecision(allowed=True, status_code=200, reason="token authenticated")
    else:
        # No token configured — allow only loopback clients.
        if is_loopback_host(remote_addr):
            return GateDecision(
                allowed=True,
                status_code=200,
                reason="loopback client allowed (no WEB_AUTH_TOKEN configured)",
            )
        return GateDecision(
            allowed=False,
            status_code=403,
            reason=(
                "mutation from non-loopback address rejected; "
                "set WEB_AUTH_TOKEN to allow network-exposed mutations"
            ),
        )
```

- [ ] **Step 2: Compile-check the new module**

```
python -m py_compile web/auth_gate.py
```

Expected: no output (success).

- [ ] **Step 3: Commit**

```bash
git add web/auth_gate.py
git commit -m "feat(harden1): add web/auth_gate.py with pure mutation gate helpers"
```

---

## Task 2: Write Failing Tests for `web/auth_gate.py`

**Files:**
- Create: `tests/test_web_mutation_auth_gate.py`

- [ ] **Step 1: Write the test file**

```python
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
10. Same-origin POST is allowed
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
from unittest.mock import MagicMock

import pytest

from web.auth_gate import (
    GateDecision,
    extract_web_auth_token,
    is_loopback_host,
    origin_matches_request,
    should_allow_mutation,
)


# ── helpers ────────────────────────────────────────────────────────────────────

def _headers(**kw):
    """Return a dict of headers (case-insensitive via MagicMock.get)."""
    data = {k: v for k, v in kw.items()}

    mock = MagicMock()
    mock.get = lambda key, default=None: data.get(key, default)
    return mock


def _allow(method="POST", remote_addr="127.0.0.1", headers=None, host="localhost", token=""):
    return should_allow_mutation(
        method=method,
        remote_addr=remote_addr,
        headers=headers or _headers(),
        host=host,
        configured_token=token,
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
    d = _allow(method="POST", remote_addr="127.0.0.1", headers=h, host="127.0.0.1:5000", token="")
    assert d.allowed is True


def test_same_origin_post_allowed_with_token():
    h = _headers(Origin="http://localhost:5000", **{"X-CATTUS-Web-Token": "tok"})
    d = _allow(method="POST", remote_addr="127.0.0.1", headers=h, host="localhost:5000", token="tok")
    assert d.allowed is True


# ── 11. Missing Origin/Referer does not block token-authenticated API request ──

def test_no_origin_no_referer_token_auth_allowed():
    h = _headers(**{"X-CATTUS-Web-Token": "apitoken"})
    d = _allow(method="POST", remote_addr="10.0.0.1", headers=h, host="api.example.com", token="apitoken")
    assert d.allowed is True


# ── 12. Route blocked without auth under configured token ─────────────────────

def test_apply_patch_route_blocked_without_auth(monkeypatch):
    monkeypatch.setenv("WEB_AUTH_TOKEN", "secret")
    # Import the Flask app; the gate reads WEB_AUTH_TOKEN at request time.
    from web.app import app
    app.config["TESTING"] = True
    with app.test_client() as client:
        resp = client.post("/apply_patch", data={"repo_path": "/tmp", "patch": "{}"})
    assert resp.status_code in {401, 403}


# ── 13. Route allowed with correct auth token (route body is mocked) ───────────

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
    # Gate passes — route itself may return 400/500 due to invalid patch data,
    # but it must NOT be 401 or 403.
    assert resp.status_code not in {401, 403}


# ── 14. debug=True is not used in web/app.py main entry ──────────────────────

def test_no_debug_true_in_app_main():
    src = Path("web/app.py").read_text(encoding="utf-8")
    # Check that the __main__ block does not pass debug=True
    assert 'debug=True' not in src, (
        "web/app.py must not use debug=True in the __main__ block"
    )


# ── 15. Source contains no new model/network/patch/validation/benchmark behavior

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
```

- [ ] **Step 2: Run tests to confirm they fail (auth gate functions exist but gate is not wired)**

```
python -m pytest tests/test_web_mutation_auth_gate.py -q
```

Expected: Tests 12 and 13 may pass or fail depending on whether app has the gate — but unit tests (1–11, 14, 15) should pass if `web/auth_gate.py` was written in Task 1. Tests 12/13 will fail (no before_request yet → route body runs, no 401/403 for test 12). Run as a baseline check.

- [ ] **Step 3: Commit test file**

```bash
git add tests/test_web_mutation_auth_gate.py
git commit -m "test(harden1): add web mutation auth gate test suite (15 cases)"
```

---

## Task 3: Wire the Gate into `web/app.py`

**Files:**
- Modify: `web/app.py` (lines ~80-93 where the app is created and blueprints registered, and line ~3599 `__main__` block)

- [ ] **Step 1: Add secret key config and before_request hook in `web/app.py`**

Find the block after `app = Flask(__name__)` (around line 80) and add:

```python
import os as _os

# Secret key — read from env; safe placeholder for local-only dev.
app.secret_key = _os.environ.get("WEB_SECRET_KEY") or "dev-insecure-local-only-do-not-use-in-prod"

from web.auth_gate import should_allow_mutation as _should_allow_mutation

@app.before_request
def _web_mutation_gate():
    from flask import request as _req, abort as _abort
    configured_token = _os.environ.get("WEB_AUTH_TOKEN", "")
    decision = _should_allow_mutation(
        method=_req.method,
        remote_addr=(_req.remote_addr or ""),
        headers=_req.headers,
        host=(_req.host or ""),
        configured_token=configured_token,
    )
    if not decision.allowed:
        _abort(decision.status_code, decision.reason)
```

Place these additions directly after the blueprint registrations (after line ~87 `app.register_blueprint(history_routes_bp)`).

- [ ] **Step 2: Fix the `__main__` block to remove `debug=True`**

The current `__main__` block at the bottom of `web/app.py` is:

```python
if __name__ == "__main__":
    from web.runner import run_web_app

    run_web_app(app, debug=True)
```

Change it to:

```python
if __name__ == "__main__":
    from web.runner import run_web_app

    run_web_app(app, debug=False)
```

- [ ] **Step 3: Compile-check `web/app.py`**

```
python -m py_compile web/app.py
```

Expected: no output.

- [ ] **Step 4: Run the gate tests to confirm all pass**

```
python -m pytest tests/test_web_mutation_auth_gate.py -q
```

Expected: 15+ test items, all pass (or skip).

- [ ] **Step 5: Commit**

```bash
git add web/app.py
git commit -m "feat(harden1): wire web mutation auth gate into app.before_request; fix debug=True"
```

---

## Task 4: Add HARDEN.1 to Phase Registry

**Files:**
- Modify: `docs/roadmap/phase_registry.json`

- [ ] **Step 1: Append HARDEN.1 entry to the phases array**

Add as the last entry in the `"phases"` array in `docs/roadmap/phase_registry.json`:

```json
{
  "phase_id": "HARDEN.1",
  "title": "Web Mutation Auth / CSRF Gate",
  "track": "HARDEN",
  "status": "complete",
  "summary": "Adds a centralized Flask before_request security gate that blocks unauthenticated or cross-origin mutating HTTP requests (POST/PUT/PATCH/DELETE). Token via WEB_AUTH_TOKEN; loopback-only fallback when unset.",
  "automation_level": "LOCAL_0_OBSERVE",
  "budget_tier": "local_only",
  "risk_level": "medium",
  "allowed_files": [
    "web/auth_gate.py",
    "web/app.py",
    "tests/test_web_mutation_auth_gate.py",
    "docs/roadmap/phase_registry.json",
    "tests/test_phase_registry.py",
    "tests/test_phase_picker.py",
    "README.md",
    "docs/AI_Coding_Agent_Mentor_Operating_Roadmap_2026-06-Next.md"
  ],
  "forbidden_files": [
    ".env",
    ".git",
    ".agent/private",
    "secrets",
    "credentials"
  ],
  "validation": [
    "python -m compileall -q core scripts web tests benchmarks",
    "python -m pytest tests/test_web_mutation_auth_gate.py -q",
    "python scripts/validate_phase_registry.py --registry docs/roadmap/phase_registry.json --json",
    "python -m pytest -q",
    "python benchmarks/run_benchmarks.py --check"
  ],
  "human_approval_required": true,
  "merge_allowed": false,
  "network_allowed": false,
  "model_calls_allowed": false,
  "writes_real_repo": false,
  "requires_sandbox": false,
  "prerequisites": [
    "ROAD.4"
  ],
  "expected_artifacts": [
    ".agent/hardening/web_mutation_auth_gate_report.json",
    ".agent/hardening/web_mutation_auth_gate_report.md"
  ],
  "notes": [
    "HARDEN.1 adds the web mutation auth gate. No model/network/patch/validation/benchmark/worker/DB/merge power added. Token reads WEB_AUTH_TOKEN env var at request time; loopback fallback when unset. Cross-origin mutations are always rejected."
  ]
}
```

- [ ] **Step 2: Validate registry**

```
python scripts/validate_phase_registry.py --registry docs/roadmap/phase_registry.json --json
```

Expected: `{"ok": true, ...}` (or equivalent success output).

- [ ] **Step 3: Commit**

```bash
git add docs/roadmap/phase_registry.json
git commit -m "feat(harden1): add HARDEN.1 to phase registry"
```

---

## Task 5: Update Phase Registry and Picker Seed Tests

**Files:**
- Modify: `tests/test_phase_registry.py`
- Modify: `tests/test_phase_picker.py`

- [ ] **Step 1: Find the seed-registry test in `test_phase_registry.py`**

Search for `seed registry validates` or `SEED_REGISTRY` or a test that calls `load_phase_registry` with the actual `docs/roadmap/phase_registry.json` path. The test at approximately line 300+ should load the seed JSON. The existing pattern looks like:

```python
def test_seed_registry_validates():
    registry_path = Path("docs/roadmap/phase_registry.json")
    registry = load_phase_registry(registry_path)
    errors = validate_phase_registry(registry)
    assert errors == []
```

This test already passes once HARDEN.1 is in the JSON, because the registry format is valid. **No change needed** — just confirm it passes.

Run:
```
python -m pytest tests/test_phase_registry.py -q -k "seed"
```

Expected: pass.

- [ ] **Step 2: Check picker seed test in `test_phase_picker.py`**

Find the seed-registry test, typically something like:

```python
def test_seed_registry_produces_expected_buckets():
    registry_path = Path("docs/roadmap/phase_registry.json")
    ...
```

This test classifies all phases from the real JSON. HARDEN.1 is `complete` → it should land in `complete_or_history`. The test may assert a hardcoded count or list — if so, update it to include HARDEN.1.

Run:
```
python -m pytest tests/test_phase_picker.py -q -k "seed"
```

If it fails due to count assertions, find and update the count. For example if the test says:
```python
assert len(report["buckets"]["complete_or_history"]) == 17
```
Change 17 → 18 (or whatever the new count is).

- [ ] **Step 3: Run full picker and registry test suites**

```
python -m pytest tests/test_phase_registry.py tests/test_phase_picker.py -q
```

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add tests/test_phase_registry.py tests/test_phase_picker.py
git commit -m "test(harden1): update seed tests for HARDEN.1 in picker/registry"
```

---

## Task 6: Update Roadmap Doc

**Files:**
- Modify: `docs/AI_Coding_Agent_Mentor_Operating_Roadmap_2026-06-Next.md`

- [ ] **Step 1: Add HARDEN track section**

Open the roadmap doc. After the CMD track entries, add a new section. The exact location will depend on the current doc structure, but it should be inserted after the last CMD section. Add:

```markdown
## HARDEN Track

HARDEN phases add defensive hardening to the CATTUS web app. They do not redesign the app, add new automation power, call models, contact network services, run validation, apply patches, push, merge, or open PRs.

### HARDEN.1 — Web Mutation Auth / CSRF Gate

**Status:** Complete  
**Prerequisite:** ROAD.4  
**Risk:** Medium (modifies web/app.py before_request behavior)

Adds a centralized `@app.before_request` security gate to the Flask web app. For safe HTTP methods (GET, HEAD, OPTIONS), all requests are allowed. For mutating methods (POST, PUT, PATCH, DELETE):

- If `WEB_AUTH_TOKEN` is set: all mutating requests require a matching token in `X-CATTUS-Web-Token` or `Authorization: Bearer <token>`.
- If `WEB_AUTH_TOKEN` is not set: mutating requests are allowed only from loopback addresses (127.0.0.1, ::1, localhost); all others receive 403.
- Cross-origin mutating requests are always rejected (Origin/Referer CSRF check).

**New env vars:**
- `WEB_AUTH_TOKEN` — token for web mutation auth; unset means loopback-only
- `WEB_SECRET_KEY` — Flask secret key; generates a dev-only placeholder if unset

**New files:**
- `web/auth_gate.py` — pure gate helpers, GateDecision dataclass
- `tests/test_web_mutation_auth_gate.py` — 15-case test suite

**No new automation power.** Does not run models, apply patches, validate, benchmark, contact network services, push, merge, or open PRs.
```

- [ ] **Step 2: Commit**

```bash
git add docs/AI_Coding_Agent_Mentor_Operating_Roadmap_2026-06-Next.md
git commit -m "docs(harden1): add HARDEN track + HARDEN.1 to roadmap doc"
```

---

## Task 7: Update README.md

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add a Web Security section**

Find the existing environment variable documentation section in `README.md`. Add a new subsection (or new section if not present):

```markdown
## Web App Security

### `WEB_AUTH_TOKEN` (optional)

When set, all mutating HTTP requests to the web app (POST, PUT, PATCH, DELETE) require this token in one of:

- Header: `X-CATTUS-Web-Token: <token>`
- Header: `Authorization: Bearer <token>`

If `WEB_AUTH_TOKEN` is **not set**, mutating requests are allowed only from loopback addresses (127.0.0.1, ::1, localhost). Any non-loopback client receives `403 Forbidden`.

> **Warning:** If you expose the web app beyond localhost (e.g., `host=0.0.0.0`), you **must** set `WEB_AUTH_TOKEN` to prevent unauthenticated remote access to mutation routes such as `/apply_patch`, `/dream/apply`, `/mcp/inspector/launch`, and `/harness/controls/apply-env`.

### `WEB_SECRET_KEY` (optional)

Flask secret key. If not set, a dev-only insecure placeholder is used. This is safe for local development but **must** be set to a strong random value for any network-exposed deployment.

### Cross-Origin Mutation

Cross-origin mutating requests are always rejected (403) regardless of token. If your deployment sends `Origin` or `Referer` headers that do not match the request host, ensure the client is on the same host or configure a reverse proxy that strips/rewrites origin headers appropriately.

### Local Development

With default settings (no `WEB_AUTH_TOKEN`), the web app accepts mutating requests only from localhost. This is the expected behavior for local development.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs(harden1): document WEB_AUTH_TOKEN, WEB_SECRET_KEY, mutation security"
```

---

## Task 8: Full Validation

- [ ] **Step 1: Compile-check everything**

```
python -m compileall -q core scripts web tests benchmarks
```

Expected: no output / no errors.

- [ ] **Step 2: Run HARDEN.1 test suite**

```
python -m pytest tests/test_web_mutation_auth_gate.py -q
```

Expected: all 15+ tests pass.

- [ ] **Step 3: Run registry validation**

```
python scripts/validate_phase_registry.py --registry docs/roadmap/phase_registry.json --json
```

Expected: `{"ok": true, ...}`.

- [ ] **Step 4: Run full test suite**

```
python -m pytest -q
```

Expected: all tests pass (or pre-existing failures only — no new failures).

- [ ] **Step 5: Run benchmark check**

```
python benchmarks/run_benchmarks.py --check
```

Expected: no errors.

- [ ] **Step 6: Final confirmation checklist**

- [ ] `web/auth_gate.py` exists and compiles
- [ ] `web/app.py` has `before_request` gate wired
- [ ] `web/app.py` `__main__` uses `debug=False`
- [ ] `app.secret_key` is set from `WEB_SECRET_KEY` env var
- [ ] All 15 tests pass in `tests/test_web_mutation_auth_gate.py`
- [ ] HARDEN.1 is in `docs/roadmap/phase_registry.json` and validates
- [ ] Picker/registry seed tests pass
- [ ] README.md documents `WEB_AUTH_TOKEN`, `WEB_SECRET_KEY`, local/network behavior
- [ ] Roadmap doc has HARDEN track + HARDEN.1
- [ ] No model/network/patch/validation/benchmark/worker/DB/merge code added

---

## Self-Review

### Spec Coverage

| Spec requirement | Task |
|-----------------|------|
| `is_loopback_host`, `extract_web_auth_token`, `origin_matches_request`, `should_allow_mutation` helper functions | Task 1 |
| `GateDecision` with `allowed`, `status_code`, `reason` | Task 1 |
| GET/HEAD/OPTIONS pass through | Task 1 + Task 2 test 1/2 |
| POST from loopback allowed when no token | Task 1 + test 3 |
| POST from non-loopback rejected when no token | Task 1 + test 4 |
| POST without token rejected when token configured | Task 1 + test 5 |
| Wrong token rejected | Task 1 + test 6 |
| `X-CATTUS-Web-Token` accepted | Task 1 + test 7 |
| `Authorization: Bearer` accepted | Task 1 + test 8 |
| Cross-origin rejected | Task 1 + test 9 |
| Same-origin allowed | Task 1 + test 10 |
| Missing Origin/Referer doesn't block API client | Task 1 + test 11 |
| Route blocked without auth | Task 3 + test 12 |
| Route allowed with correct auth | Task 3 + test 13 |
| `debug=True` not used | Task 3 + test 14 |
| No forbidden calls in gate source | Task 2 test 15 |
| `app.secret_key` from `WEB_SECRET_KEY` | Task 3 |
| HARDEN.1 in phase registry | Task 4 |
| Picker/registry seed tests updated | Task 5 |
| Roadmap doc updated | Task 6 |
| README updated | Task 7 |
| Full validation suite passes | Task 8 |

### Type Consistency

- `GateDecision` is defined in Task 1 and used in Task 2 tests (imported from `web.auth_gate`). ✓
- `should_allow_mutation` signature is consistent between Task 1 (definition) and Task 2 (test helper `_allow`). ✓
- `_headers()` in tests uses `.get()` matching the `headers.get(...)` calls in `should_allow_mutation`. ✓

### No Placeholders

Reviewed — all code blocks are complete.
