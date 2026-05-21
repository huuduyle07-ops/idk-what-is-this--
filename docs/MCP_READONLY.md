# Phase 8.1 — Read-only MCP server

Local MCP server that exposes a strict read-only subset of the
C.A.T.T.U.S tool registry over stdio. External agents (Claude Desktop,
Claude Code, any MCP-aware client) can query workspace health, browse
benchmark/Dream reports, list lessons, and inspect worker runs without
ever being able to write files, run subagents, apply patches, or promote
lessons.

The single source of truth is [core/tool_registry.py](../core/tool_registry.py).
The server's allowlist is derived live from
`tool_registry.is_tool_allowed(name, "read_only")` — there is no
hardcoded tool list, no MCP-specific override, and no escape hatch into
`unsafe_dev`.

---

## What the server CAN do

Exposed MCP tools (10 total):

| Tool | Returns |
|------|---------|
| `get_health` | Cheap non-blocking checks for API keys, DB, embeddings, Ollama, etc. |
| `list_benchmark_reports` | Recent benchmark report JSON files under `.agent/benchmarks/` |
| `read_benchmark_report` | One benchmark report by filename |
| `list_dream_reports` | Dream run artifacts under `.agent/dreams/` |
| `read_dream_report` | One Dream report by date (+ optional run id) |
| `list_lessons` | Lesson candidates / active / blocked records |
| `read_lesson_proposal` | The `proposal.md` backing a lesson by id |
| `list_worker_runs` | Phase 7.1 worker run artifacts under `.agent/worker_runs/` |
| `read_worker_run` | One worker run by id, with `raw_output_preview` capped at 2000 chars |
| `list_tool_registry` | The full tool registry as metadata — every tool's category, flags, route, notes |

Every wrapper is path-traversal guarded and reads metadata or artifacts
only.

## What the server CANNOT do

Enforced by `core.tool_registry.is_tool_allowed(...)`:

- Write files to the real repo
- Apply patches (`apply_patch`, `apply_patch_plan`, `dream_apply`)
- Run subagents (`run_subagent_handoff`)
- Create / import / validate proposals
- Promote or block lessons
- Expose any tool whose `mcp_exposable=False`
- Operate in `unsafe_dev` mode — that mode is for internal dashboards
  only and is unreachable from this server

If a future commit adds a new write tool to the registry with
`mcp_exposable=True`, the read-only server still will not expose it: its
allowlist is the intersection of `_IMPLS` (hand-curated read-only
wrappers in `mcp_server/read_only.py`) and the registry's `read_only`
mode — both gates must agree.

---

## Install

The `mcp` Python SDK is an optional dependency. The server module
imports cleanly without it; only `build_server()` and the running
server need it.

```bash
pip install mcp
```

**On machines with AVG/SSL MITM** (the AV intercepts HTTPS with its own
CA), pip's bundled certifi bundle won't trust the proxy. Use
truststore:

```bash
pip install mcp --use-feature=truststore
```

To verify the install:

```bash
python -c "from mcp.server.fastmcp import FastMCP; print('FastMCP OK')"
```

---

## Running the server

stdio transport (default — what MCP clients expect):

```bash
python scripts/mcp_readonly_server.py
```

The process blocks on stdin/stdout speaking the MCP protocol. Wire it
into an MCP client by adding an entry to the client's `mcpServers`
config — for example, in `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "cattus-readonly": {
      "command": "python",
      "args": ["C:/Users/Admin/Documents/Code/day 14/AI project/scripts/mcp_readonly_server.py"]
    }
  }
}
```

If the `mcp` package is not installed, the script exits with code 2 and
prints to stderr:

```
MCP package not installed. Install optional MCP dependencies to run this server.
```

---

## Listing exposed tools without starting the server

For shell scripts, audits, or sanity checks before wiring into an MCP
client:

```bash
python scripts/mcp_readonly_server.py --list-tools
```

Prints one tool name per line and exits 0. This mode is a
registry-only query — it does NOT import `mcp`, construct a FastMCP
instance, or open stdio. It works even on machines without the optional
dependency installed.

Sample output:

```
get_health
list_benchmark_reports
read_benchmark_report
list_dream_reports
read_dream_report
list_lessons
read_lesson_proposal
list_worker_runs
read_worker_run
list_tool_registry
```

---

## Security model

1. **Registry is the gate.** The server calls
   `tool_registry.is_tool_allowed(name, "read_only")` on startup for
   every candidate tool. Tools that fail this check are silently
   skipped — no fallback, no override.
2. **`CAPABILITY_MODE = "read_only"` is a constant.** It is never read
   from the environment, CLI flag, or MCP request. There is no code
   path that promotes the server into `artifact_write`, `operator`, or
   `unsafe_dev`.
3. **Path-traversal guards** on every wrapper that takes a filename,
   date, run id, or lesson id. Filenames may not contain `/`, `\`, or
   start with `.`; dates must match `YYYY-MM-DD`; run ids must match
   `HHMMSS-run(-N)?`; resolved paths must stay inside their advertised
   roots.
4. **Lazy MCP import.** The `mcp` SDK is imported inside `build_server()`
   only. Importing `mcp_server.read_only` has no side effects:
   no server starts, no stdio opens, no network listens.
5. **Tests pin the contract.** `tests/test_mcp_readonly_server.py`
   asserts the exposed name set equals
   `tool_registry.is_tool_allowed(..., "read_only")` results, and
   parametrizes over every forbidden tool (`apply_patch`,
   `apply_patch_plan`, `dream_apply`, `run_subagent_handoff`,
   `promote_lesson`, `block_lesson`, `create_handoff_note`,
   `import_worker_run_as_proposal`, `validate_imported_worker_proposal`)
   to verify none ever appear.

---

## Files

- [scripts/mcp_readonly_server.py](../scripts/mcp_readonly_server.py) —
  thin CLI shim
- [mcp_server/read_only.py](../mcp_server/read_only.py) —
  the server module: allowlist, lazy `mcp` import, tool wrappers,
  `build_server`, `main`
- [mcp_server/__init__.py](../mcp_server/__init__.py) —
  package marker (no side effects)
- [core/tool_registry.py](../core/tool_registry.py) —
  the source of truth for what's exposable
- [tests/test_mcp_readonly_server.py](../tests/test_mcp_readonly_server.py) —
  allowlist contract + CLI tests
