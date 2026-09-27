# AUTH.WEB.READ.1 — Trusted Host & Sensitive Read Boundary

Date: 2026-09-17  
Gap: the read-side Host/DNS-rebinding gap recorded by AUTH.WEB.1 ("Read routes
(decision)" and "Limitations")  
Track: HARDEN

## Scope and invariant

A browser must not reach C.A.T.T.U.S read data merely because the request's
`Host` header, or an attacker's hostname resolved to this server, names
something the server does not serve. Trusted Host identity is derived from the
server's own configuration (the listening socket, or `WEB_ALLOWED_ORIGINS`),
never from the request.

This phase adds one owner, `web/read_host.py`, and wires it in front of the
Flask app. AUTH.WEB.1's mutation contract (exact Origin, browser session, CSRF,
`WEB_AUTH_TOKEN` bootstrap, header-token API clients) is frozen, as are
SEC.UI.1, DATA.UNDO.1, EXEC.PLAN.1, AUTH.DREAM.1, DATA.ROLLBACK.1 and Track A.
UX-02 through UX-06, UI redesign, PREFLIGHT.REQUEST.1 and T6 Round 11 are out
of scope.

## Measured entry state

Entry bytes are AUTH.WEB.1's post-state (`web/app.py` sha256 `fc2195c2…`).
Against a server configured as `127.0.0.1:5000`, with synthetic files carrying a
unique marker, GET requests with `Host: evil.example:5000`, `localhost:5000` and
`127.0.0.1:7999` each returned 200 and the marker from `/history/sessions`,
`/session/<id>`, `/presentation/evidence/file`, `/dream/report` and
`/graph/evidence_spread`. `/`, `/auth/session` and `/static/*` were served too,
and `/` minted a browser session cookie under the attacker host. `//new`
answered `308` with `Location: http://evil.example:5000/`, an absolute redirect
built from the untrusted Host.

In real Chromium (with `evil.example` mapped to 127.0.0.1), a page at
`http://evil.example:<port>` read the same marker through same-origin `fetch`.
Those requests carried `Host: evil.example:<port>` and neither `Origin` nor
Fetch Metadata, so no AUTH.WEB.1 proof could see them. Both measurements are
kept as executable tests that remove only the boundary
(`test_entry_app_without_the_boundary_served_marker_data_under_an_attacker_host`,
`test_entry_app_without_the_boundary_leaks_to_a_rebound_page`).

## Threat boundary

Pinned attack: an attacker controls `evil.example`. The browser loads
`http://evil.example:<port>`, the name then resolves to 127.0.0.1, and the
page's same-origin reads reach C.A.T.T.U.S with `Host: evil.example:<port>`.
CORS is not a defense here: the browser considers the rebound name same-origin.
The Host check is the boundary.

Claim: the audited C.A.T.T.U.S read paths no longer serve data for untrusted
Host identities under the tested local deployment contract (bundled Werkzeug
server; loopback, published-port and explicitly configured origins). This phase
does not claim that DNS rebinding is impossible everywhere, and Host validation
is not authentication (see "Reads and authentication").

## Owner and choke point

`web/read_host.py`:

- `parse_host(value)`: strict Host parsing through the AUTH.WEB.1 origin owner.
  A Host value is the authority of an `http` origin, so it is parsed as
  `request_origin.parse_origin("http://" + value)`. The one addition is whether
  a port was written.
- `trusted_hosts(origins)`: the projection from allowed origins to Host
  identities.
- `evaluate_host(value, trusted)` and
  `should_allow_read_host(method, environ, setting)`: the deterministic
  decision.
- `ReadHostBoundary`: WSGI middleware.

`web/app.py` changes by two statements, after the AUTH.WEB.1 gate:
`from web.read_host import ReadHostBoundary as _ReadHostBoundary` and
`app.wsgi_app = _ReadHostBoundary(app.wsgi_app)`. No definition in `web/app.py`
changed. The boundary runs before Flask builds a request context, so a refused
request never reaches URL routing (and its redirects), the session interface,
before-request hooks, view functions or static files. `_web_mutation_gate`
stays the only before-request function.

Flask 3.1's `TRUSTED_HOSTS` was not used. Werkzeug's `host_is_trusted` ignores
the port, accepts suffix matches, and runs only when `request.host` is read.
Rewriting route decorators was not needed, because one WSGI boundary covers
every route.

## Trusted-host model

- **Data source.** `request_origin.allowed_origins_for(environ, WEB_ALLOWED_ORIGINS)`,
  unchanged from AUTH.WEB.1: the origin of the listening socket from
  `wsgi.url_scheme`, `SERVER_NAME` and `SERVER_PORT`, or the explicit list,
  which replaces it. There is no second hostname allowlist. The setting is read
  per request, as for mutations.
- **Canonical representation.** `HostIdentity(host, port)`. `host` is the
  AUTH.WEB.1 normalized host: a lowercase DNS name, a dotted-quad IPv4 address,
  or IPv6 in WHATWG form. `port` is the written port, or `None` when the header
  omits it. It serializes as `127.0.0.1:5000`, `[::1]:5000` or `cattus.example`.
- **Projection and ports.** Each allowed origin `(scheme, host, port)` trusts
  `host:port`. When `port` is the scheme's default, it also trusts the bare
  `host`, because browsers and HTTP clients omit a default port.
  `http://127.0.0.1:5000` trusts only `127.0.0.1:5000`: `127.0.0.1`,
  `127.0.0.1:80` and `127.0.0.1:7999` are refused. `https://cattus.example`
  trusts `cattus.example` and `cattus.example:443`, but not
  `cattus.example:80`. A Host carries no scheme, so the scheme itself stays
  part of the mutation Origin check only.
- **Loopback aliases.** `localhost`, `127.0.0.1` and `::1` are compared as
  different hosts; no alias is collapsed. Only spellings of the same address
  are equal: `[0:0:0:0:0:0:0:1]` is `[::1]`, while `[::ffff:127.0.0.1]` is a
  different address from `127.0.0.1`.
- **WEB_ALLOWED_ORIGINS.** `http://localhost:5056` trusts `localhost:5056`
  only, not `localhost:5000` and not `127.0.0.1:5056`. Invalid entries (paths,
  wildcards, bare `host:port`) add nothing, exactly as for mutations.
- **Wildcard bind.** `0.0.0.0` or `::` without `WEB_ALLOWED_ORIGINS` projects
  to no trusted host, so every page and read is refused. Trust is never learned
  from a first request.
- **Headers never consulted for identity:** `Host` (it is the value checked),
  `Origin`, `Referer`, `X-Forwarded-Host`, `X-Forwarded-Proto`,
  `X-Forwarded-Port`, `Forwarded`, `X-Original-Host`, `X-Host`. The app has no
  trusted-proxy configuration.

## Refusals

| Case | Status | `error_code` |
| --- | --- | --- |
| Well-formed Host this server is not configured for | 421 Misdirected Request | `host_not_allowed` |
| Missing or empty Host (HTTP/1.0 without Host, empty value) | 400 | `host_missing` |
| More than one Host value (servers join repeated lines with `,`) | 400 | `host_ambiguous` |
| Anything else that does not parse | 400 | `host_malformed` |

Malformed values include userinfo (`user@127.0.0.1:5000`, also from an
absolute-form request target), paths, schemes, whitespace, control and
non-ASCII characters, empty, zero or out-of-range ports, unbracketed or broken
IPv6, zone identifiers, number-like or non-canonical IPv4 (`127.1`,
`0x7f.0.0.1`), trailing dots, wildcards and values over the origin length
limit. Names are compared exactly after parsing, so `attacker-localhost`,
`localhost.attacker.example` and `127.0.0.1.evil.example` never match
`localhost` or `127.0.0.1`.

The body is JSON `{"ok": false, "success": false, "error", "error_code"}`, or
`text/plain` for `Sec-Fetch-Mode: navigate`. A HEAD refusal has no body. The
refusal carries `X-CATTUS-Request-Integrity: <code>`,
`X-Content-Type-Options: nosniff` and `Cache-Control: no-store`, and never sets
a cookie, a redirect, CORS headers, the offered host, the trusted-host
inventory, repository paths, session details or secrets.
`web/static/request_integrity.js` reads that header only for its own protected
(mutating) requests, and the boundary never refuses those.

## Read route inventory

All 55 GET/HEAD rules in `app.url_map` were classified. The receipt is
`tests/fixtures/auth_web_read1_completion.json` (`route_inventory`), and
`test_route_inventory_classification_is_complete_and_recorded` fails when a rule
is added or removed without classification.

| Category | Rules | Sensitivity |
| --- | --- | --- |
| Public application shell / static | `/`, `/new`, `/static/<path:filename>`, `/help` | not sensitive data; `/` bootstraps the browser session |
| Health / non-sensitive operational | `/health`, `/tools/registry`, `/dream/taxonomy` | low (local tool paths and provider status) |
| Auth / bootstrap | `/auth/session` | mints a session and returns its CSRF token |
| Project / repository data | `/benchmarks/cases`, `/benchmarks/case-defaults`, `/graph/evidence_spread`, `/graph/explainability/view`, `/lessons/list`, `/lessons/duplicates`, `/lessons/anti/report`, `/lessons/anti/reverse-dream-plan`, `/lessons/anti/shadow-retrieval`, `/lessons/anti/control-preview`, `/lessons/anti/control-preview-report`, `/project-evolution/approval-panel`, `/handoffs/list` | sensitive |
| Source / evidence / report / history | `/presentation/evidence/list`, `/presentation/evidence/file`, `/eval/evidence-quality/report/<id>`, `/mirror-tunnel/preview/<id>`, `/benchmarks/list`, `/benchmarks/report`, `/benchmarks/prompt-cost`, `/proposals/list`, `/proposals/view`, `/lessons/proposal` | sensitive |
| Dream reports / artifacts | `/dream/queue`, `/dream/list`, `/dream/reports`, `/dream/report`, `/dream/plan/latest`, `/dream/references/list`, `/dream/references/file`, `/dream/trials/list`, `/dream/trials/file` | sensitive |
| Session / run / debug / internal state | `/history/sessions`, `/session/<session_id>`, `/replays`, `/replays/<id>`, `/replays/<id>/compare`, `/replays/<id>/artifact/<name>`, `/replays/janitor`, `/ux/run-progress/snapshot/<id>`, `/worker-runs/list`, `/worker-runs/view`, `/dream/status`, `/dream/proposals/status`, `/benchmarks/status`, `/mcp/audit`, `/harness/controls` | sensitive |

Auth-dependent reads, whose output depends on the browser session: `/`,
`/session/<session_id>` and `/auth/session`.

Policy: a trusted Host is required for all 55 rules, for 404s, and for OPTIONS.
Classification decides which proofs the tests demand (spied handlers, spied data
access, marker content). It does not add a login requirement.

## Decisions

- **Application shell.** A trusted Host is required. The shell exposes the
  application's structure, bootstraps browser security state (CSRF token, auth
  state and session cookie), and runs the scripts that read everything else.
  Deployments that open the UI on another address list that origin, as they
  already must for mutations.
- **Static assets.** A trusted Host is required, the same as everything else.
  They are low-sensitivity, but one rule for every application-owned request
  is simpler, and serving the app's scripts under an attacker host only helps
  the attacker.
- **Redirects.** `/new` answers with a relative `Location`. The only absolute
  redirects come from Werkzeug routing (for example `//new`), which builds them
  from the Host header. Under an untrusted Host they are refused before routing.
  Under a trusted Host they name that Host, and forwarded headers are ignored.
- **CORS.** None added. A rebound name is same-origin to the browser, so CORS
  cannot help. Refusals and reads carry no `Access-Control-*` headers.
- **Mutations.** POST, PUT, PATCH and DELETE are not host-gated, and
  `should_allow_read_host` returns `mutation_gate` for them. Every browser
  mutation already needs an exact allowed Origin, and a rebound page's Origin is
  the attacker's name (`origin_not_allowed`). Host-gating mutations would have
  changed the frozen non-browser API contract. The HTTP tests show identical
  AUTH.WEB.1 decisions under trusted, attacker, wrong-port and empty Hosts.

## Reads and authentication

Measured before deciding:

- README and the AUTH.WEB.1 design state that `WEB_AUTH_TOKEN` covers
  mutations and that reads stay public ("Read routes (decision) Unchanged").
- The shell's own scripts read `/history/sessions`, `/dream/status`,
  `/dream/proposals/status`, `/dream/taxonomy`, Dream runs and more on page load.
  `request_integrity.js` signs in without a reload, and it neither re-fetches
  reads nor inspects safe-method refusals. Requiring authentication for reads
  in auth-on mode would therefore leave a signed-out page broken, and still
  stale after sign-in. Fixing that is UI state work this phase must not begin.

Contract, therefore:

- **Auth off:** a trusted Host is required. An attacker Host gets nothing.
- **Auth on:** a trusted Host is required. A valid token header, an
  authenticated session cookie, a copied CSRF token or a trusted `Origin` never
  makes an untrusted Host acceptable. Reads under a trusted Host remain
  unauthenticated, unchanged from the documented contract and now stated
  explicitly in README.
- **API read clients:** only the configured Host is needed. There is no CSRF
  token, `Origin` or token requirement; `Authorization` is ignored for reads and
  never echoed. A client that used to send an arbitrary Host must use a
  configured address.

Host validation stops browsers that visit other sites. It does not stop
clients that can reach the socket, because they can send a configured Host.
Read authentication for network-exposed deployments remains Track-B work (see
below).

## Deployment requirements

- `python main.py --web` / `python -m web.app`: `127.0.0.1:5000`, nothing to
  configure.
- `WEB_HOST=localhost`: Werkzeug binds the resolved address, so `SERVER_NAME`
  is `127.0.0.1` and the `http://localhost:5000` address `launch_web` opens is
  refused (421) until `WEB_ALLOWED_ORIGINS=http://localhost:5000` is set.
- Docker Compose `5056:5000` with `WEB_HOST=0.0.0.0`: the wildcard bind trusts
  nothing, so set `WEB_ALLOWED_ORIGINS=http://localhost:5056`. Port publishing
  preserves the browser's `Host: localhost:5056`, and the Chromium forwarder
  test reproduces this model. In-container probes send that Host.
- Reverse proxy / TLS termination: list the public origin
  (`https://cattus.example`) and forward the public Host (nginx
  `proxy_set_header Host $host;`). A proxy that rewrites Host to the upstream
  address makes every read 421 unless that upstream origin is also listed.
  `X-Forwarded-*` is never trusted.
- WSGI servers that fill `SERVER_NAME`/`SERVER_PORT` from the Host header (for
  example Apache mod_wsgi with `UseCanonicalName Off`) make the default
  projection follow the request. Such deployments must set
  `WEB_ALLOWED_ORIGINS`, as AUTH.WEB.1 already requires.

## Evidence

- `tests/test_auth_web_read1.py`: host parsing and projection; the §18
  regression under `evil.example:5000`, `localhost:5000` and `127.0.0.1:7999`
  with spied view functions and spied data access
  (`build_graph_from_repo`, `_evidence_output_dir`, `load_sessions`,
  `find_session`, `list_sessions`, `dream_artifacts.read_report`) and marker
  non-exposure. It also covers the default-socket, configured-localhost,
  WEB_ALLOWED_ORIGINS/Docker/TLS, IPv6 and wildcard matrices; malformed,
  empty, missing and repeated Hosts straight through WSGI; the shell, static
  files, redirects and OPTIONS; session minting; auth-on cookie and token
  replay; both auth modes; API clients; forwarded headers; minimal refusals; all
  55 GET/HEAD rules under six untrusted Hosts and three methods with spies; the
  single-choke-point AST check; mutation composition; a no-traversal/network
  check; a real loopback listener (duplicate Host, HTTP/1.0 without Host,
  absolute-form attacker authority and userinfo, non-ASCII and control bytes);
  and performance.
- `tests/test_auth_web_read1_browser.py` (Chromium,
  `--host-resolver-rules=MAP evil.example 127.0.0.1`, no DNS or hosts-file
  change): a rebound page reads nothing, with no handler or data access and no
  cookie for the attacker host, while the trusted host reads the same marker.
  The entry app leaks to that page. An unconfigured alias and a wrong port get
  421. A published origin through a TCP forwarder reads and mutates, while the
  socket address is refused.

## Performance

Median per-operation cost (Python 3.14; median of three runs of
`test_read_host_check_overhead_is_bounded`, each 15 batches):

| Operation | Median |
| --- | --- |
| Host parse | 5.9 µs |
| Host parse and trusted check | 5.6 µs |
| Trusted-host derivation (allowed origins + projection) | 9.9 µs |
| Full read-host decision | 16.4 µs |
| Whole refused request through the WSGI boundary | 46.9 µs |

The boundary does no filesystem traversal, graph, embedding, model or network
work. A test forbids `open`, `os.scandir`, `os.walk`, `os.stat`, path globbing,
reads and `socket.connect` during refused requests.

## Governance

One HARDEN registry entry (`AUTH.WEB.READ.1`, prerequisite `AUTH.WEB.1`). The
reversal chain head moves: `before_auth_web1` now calls
`tests/_auth_web_read1_maintenance.py::before_auth_web_read1` first, so every
older receipt still verifies against its own bytes. AUTH.WEB.1's tests changed
only where they pinned bytes this phase edits, or asserted the old read
behavior:

- raw-byte completion and definition pins now go through the new helper;
- the registry check asserts that AUTH.WEB.1 directly follows DATA.ROLLBACK.1,
  not that it is the last entry;
- the explicit-allowlist test reads its page before the allowlist stops
  trusting that host;
- the Chromium alias test asserts the alias host now gets 421, then proves a
  page executing at the alias origin still gets `origin_not_allowed`.

Every hunk is in `tests/fixtures/auth_web_read1_reversal.json`.

## Limitations

- Host validation is not authentication: any client that can reach the socket
  can send a configured Host, and reads stay unauthenticated in both modes.
- Mutating-method responses rely on AUTH.WEB.1's Origin proof. An engine that
  sends neither Origin nor Fetch Metadata on POST is still treated as a
  non-browser client (the AUTH.WEB.1 limitation).
- The browser session cookie is still host-scoped, not port-scoped. Another
  port on the same host can still overwrite it (sign-out nuisance), which this
  phase does not change.
- `WEB_HOST=localhost` and Docker need `WEB_ALLOWED_ORIGINS`, and pages without
  it return 421. `launch_web` still opens the configured `WEB_HOST` address.
- A trailing-dot name (`localhost.`) is refused as malformed.
- WSGI servers that derive `SERVER_NAME` from Host need `WEB_ALLOWED_ORIGINS`.

## Remaining Track-B work

- Read authentication for network-exposed deployments: sensitive reads
  requiring a session or token in auth-on mode, together with a UI that
  re-fetches its reads after sign-in.
- A sign-out control and server-side session revocation (AUTH.WEB.1
  limitations).
- UX-02 through UX-06.
