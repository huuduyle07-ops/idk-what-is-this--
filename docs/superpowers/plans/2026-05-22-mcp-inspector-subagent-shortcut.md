# MCP Inspector Sub-agent Shortcut Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Sub-agent header shortcut that launches MCP Inspector for either existing C.A.T.T.U.S MCP server without accepting arbitrary Inspector commands from the browser.

**Architecture:** Keep the UI compact in the Sub-agent header and send one explicit server id to a local Flask launch route. The route owns a fixed target map for the existing read-only and artifact-write stdio scripts, builds the Inspector command from that map, starts the local process through a small helper, and returns a narrow JSON result for UI status text.

**Tech Stack:** Flask, vanilla HTML/JavaScript, Python `subprocess`, pytest

---

## File Map

- `tests/test_mcp_inspector_route.py`: route tests for fixed target selection, unknown-target rejection, and launch-error reporting without running Inspector.
- `tests/test_mayor_mode_ui.py`: template contract for the Sub-agent Inspector control labels.
- `web/app.py`: fixed Inspector target map, launch helper, and POST route.
- `web/templates/index.html`: compact Inspector menu/control and launch status updates in the Sub-agent header.
- `web/static/style.css`: header shortcut grouping and compact Inspector menu styling.

### Task 1: Lock Inspector Route Safety

**Files:**
- Create: `tests/test_mcp_inspector_route.py`
- Modify: `web/app.py`
- Test: `tests/test_mcp_inspector_route.py`

- [ ] **Step 1: Write failing route tests for approved targets and unknown target rejection**

```python
"""Route tests for local MCP Inspector launch shortcuts."""
from __future__ import annotations

import pytest


@pytest.fixture
def client():
    from web import app as web_app

    web_app.app.config["TESTING"] = True
    with web_app.app.test_client() as c:
        yield c


@pytest.mark.parametrize(
    ("target", "script_name"),
    [
        ("read_only", "mcp_readonly_server.py"),
        ("artifact_write", "mcp_artifact_write_server.py"),
    ],
)
def test_mcp_inspector_launch_uses_fixed_server_targets(
    client, monkeypatch, target, script_name
):
    from web import app as web_app

    launched = {}

    def fake_launch(cmd):
        launched["cmd"] = cmd

    monkeypatch.setattr(web_app, "_launch_mcp_inspector", fake_launch)

    response = client.post("/mcp/inspector/launch", data={"target": target})
    body = response.get_json()

    assert response.status_code == 200
    assert body == {"ok": True, "target": target}
    assert launched["cmd"][:3] == ["npx", "-y", "@modelcontextprotocol/inspector"]
    assert launched["cmd"][3] == "python"
    assert launched["cmd"][4].endswith(script_name)


def test_mcp_inspector_launch_rejects_unknown_target(client, monkeypatch):
    from web import app as web_app

    monkeypatch.setattr(
        web_app,
        "_launch_mcp_inspector",
        lambda _cmd: (_ for _ in ()).throw(AssertionError("must not launch")),
    )

    response = client.post("/mcp/inspector/launch", data={"target": "anything"})
    body = response.get_json()

    assert response.status_code == 400
    assert body["ok"] is False
    assert "target" in body["error"]
```

- [ ] **Step 2: Run the route tests to verify they fail**

```powershell
python -m pytest tests/test_mcp_inspector_route.py -q
```

Expected: FAIL because `/mcp/inspector/launch` and `_launch_mcp_inspector` do not exist yet.

- [ ] **Step 3: Add the fixed Inspector route and launch helper**

Add imports near the top of `web/app.py`:

```python
import subprocess
```

Add the fixed map and launch route near the existing `/mcp/audit` route:

```python
_MCP_INSPECTOR_TARGETS = {
    "read_only": PROJECT_ROOT / "scripts" / "mcp_readonly_server.py",
    "artifact_write": PROJECT_ROOT / "scripts" / "mcp_artifact_write_server.py",
}


def _mcp_inspector_command(target: str) -> list[str] | None:
    script_path = _MCP_INSPECTOR_TARGETS.get(target)
    if script_path is None:
        return None
    return [
        "npx",
        "-y",
        "@modelcontextprotocol/inspector",
        "python",
        str(script_path),
    ]


def _launch_mcp_inspector(command: list[str]) -> None:
    subprocess.Popen(
        command,
        cwd=PROJECT_ROOT,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )


@app.route("/mcp/inspector/launch", methods=["POST"])
def mcp_inspector_launch_route():
    target = (request.form.get("target") or "").strip()
    command = _mcp_inspector_command(target)
    if command is None:
        return {"ok": False, "error": "unknown MCP Inspector target"}, 400
    try:
        _launch_mcp_inspector(command)
    except Exception as e:
        return {
            "ok": False,
            "target": target,
            "error": f"failed to launch MCP Inspector for {target}: {type(e).__name__}: {e}",
        }, 500
    return {"ok": True, "target": target}
```

- [ ] **Step 4: Add launch-error coverage**

Append to `tests/test_mcp_inspector_route.py`:

```python
def test_mcp_inspector_launch_reports_target_on_launch_error(client, monkeypatch):
    from web import app as web_app

    def raise_missing(_cmd):
        raise FileNotFoundError("npx")

    monkeypatch.setattr(web_app, "_launch_mcp_inspector", raise_missing)

    response = client.post("/mcp/inspector/launch", data={"target": "read_only"})
    body = response.get_json()

    assert response.status_code == 500
    assert body["ok"] is False
    assert body["target"] == "read_only"
    assert "read_only" in body["error"]
```

- [ ] **Step 5: Run the route tests to verify they pass**

```powershell
python -m pytest tests/test_mcp_inspector_route.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit the route implementation**

```powershell
git add tests/test_mcp_inspector_route.py web/app.py
git commit -m "add MCP Inspector launch route"
```

### Task 2: Add The Sub-agent Inspector Control

**Files:**
- Modify: `tests/test_mayor_mode_ui.py`
- Modify: `web/templates/index.html`
- Modify: `web/static/style.css`
- Test: `tests/test_mayor_mode_ui.py`

- [ ] **Step 1: Extend the template contract test**

Add these assertions to `test_subagent_ui_copy_and_dark_surface_hooks()` in
`tests/test_mayor_mode_ui.py`:

```python
    assert "MCP Inspector" in template
    assert "Inspect read-only MCP" in template
    assert "Inspect artifact-write MCP" in template
    assert '"/mcp/inspector/launch"' in template
```

- [ ] **Step 2: Run the template test to verify it fails**

```powershell
python -m pytest tests/test_mayor_mode_ui.py -q
```

Expected: FAIL because the Sub-agent header does not expose Inspector controls yet.

- [ ] **Step 3: Add the compact header control and status line**

Replace the current Sub-agent header markup in `web/templates/index.html`:

```html
<div class="subagent-group__header">
  <h3 class="subagent-group__title">Sub-agent</h3>
  <div class="subagent-group__links">
    <a class="subagent-group__audit-link" href="/mcp/audit?limit=10">View MCP audit</a>
    <details class="subagent-inspector">
      <summary>MCP Inspector</summary>
      <div class="subagent-inspector__menu">
        <button type="button" onclick="launchMcpInspector('read_only')">Inspect read-only MCP</button>
        <button type="button" onclick="launchMcpInspector('artifact_write')">Inspect artifact-write MCP</button>
      </div>
    </details>
  </div>
</div>
<div id="mcpInspectorStatus" class="subagent-inspector__status"></div>
```

Add the UI helper in the template script:

```javascript
async function launchMcpInspector(target) {
    const status = document.getElementById("mcpInspectorStatus");
    const label = target === "artifact_write" ? "artifact-write" : "read-only";
    if (status) status.textContent = `Launching MCP Inspector for ${label}...`;
    try {
        const fd = new FormData();
        fd.append("target", target);
        const resp = await fetch("/mcp/inspector/launch", { method: "POST", body: fd });
        const body = await resp.json();
        if (!body.ok) {
            if (status) status.textContent = body.error || "MCP Inspector launch failed.";
            return;
        }
        if (status) status.textContent = `MCP Inspector launch requested for ${label}.`;
    } catch (e) {
        if (status) status.textContent = "MCP Inspector launch failed: " + e.message;
    }
}
```

- [ ] **Step 4: Add compact header/menu styling**

Add near the existing Sub-agent styles in `web/static/style.css`:

```css
.subagent-group__links {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
}

.subagent-inspector {
    position: relative;
    font-size: 12px;
}

.subagent-inspector summary {
    color: #93c5fd;
    cursor: pointer;
    list-style: none;
}

.subagent-inspector summary::-webkit-details-marker {
    display: none;
}

.subagent-inspector__menu {
    position: absolute;
    top: calc(100% + 6px);
    right: 0;
    z-index: 2;
    display: grid;
    gap: 4px;
    min-width: 190px;
    padding: 6px;
    border: 1px solid #334155;
    border-radius: 4px;
    background: #0f172a;
}

.subagent-inspector__menu button {
    width: 100%;
    padding: 5px 8px;
    border: 1px solid #334155;
    border-radius: 4px;
    background: #111827;
    color: #cbd5e1;
    cursor: pointer;
    font-size: 12px;
    text-align: left;
}

.subagent-inspector__menu button:hover {
    background: #1e293b;
}

.subagent-inspector__status {
    min-height: 16px;
    color: #94a3b8;
    font-size: 12px;
}
```

- [ ] **Step 5: Run the focused template test**

```powershell
python -m pytest tests/test_mayor_mode_ui.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit the Sub-agent control**

```powershell
git add tests/test_mayor_mode_ui.py web/templates/index.html web/static/style.css
git commit -m "add MCP Inspector Sub-agent shortcut"
```

### Task 3: Verify MCP Surface And UI Behavior

**Files:**
- Verify: `tests/test_mcp_inspector_route.py`
- Verify: `tests/test_mayor_mode_ui.py`
- Verify: `tests/test_mcp_audit_route.py`
- Verify: `tests/test_mcp_readonly_server.py`
- Verify: `tests/test_mcp_artifact_write_server.py`
- Inspect: `web/templates/index.html`

- [ ] **Step 1: Run focused route and UI tests**

```powershell
python -m pytest tests/test_mcp_inspector_route.py tests/test_mayor_mode_ui.py tests/test_mcp_audit_route.py -q
```

Expected: PASS.

- [ ] **Step 2: Run MCP allowlist guardrails**

```powershell
python -m pytest tests/test_mcp_readonly_server.py tests/test_mcp_artifact_write_server.py -q
```

Expected: PASS with no new exposed MCP tool names.

- [ ] **Step 3: Inspect the local UI**

Run the Flask UI if needed, open the Memory tab, and verify:

- `View MCP audit` remains visible.
- `MCP Inspector` opens a compact menu.
- The menu spells out `Inspect read-only MCP` and `Inspect artifact-write MCP`.
- The launch status line names the selected target after clicking a menu item.

- [ ] **Step 4: Review the diff against scope**

```powershell
git diff --stat HEAD~2
git diff -- web/app.py web/templates/index.html web/static/style.css tests/test_mcp_inspector_route.py tests/test_mayor_mode_ui.py
```

Expected: only Inspector route, Sub-agent UI, and focused test changes for the shortcut.
