# AUTH.WEB.1 — Same-Origin Request Integrity & Usable Local UI Authentication

Date: 2026-09-17  
Findings: SEC-02, UX-01 (2026-09-11 security and UI/UX audit)  
Track: HARDEN

## Scope and invariant

A state-changing browser request is accepted only when authentication
requirements **and** request-origin integrity requirements are both satisfied,
and the local C.A.T.T.U.S UI can satisfy both without anyone editing headers.
Neither proof substitutes for the other.

This phase changes the mutation gate, adds a browser sign-in and CSRF
transport, and documents the configuration. It does not change any route's own
mutation authority: DATA.UNDO.1, EXEC.PLAN.1, AUTH.DREAM.1, DATA.ROLLBACK.1,
SEC.UI.1 and Track A are frozen, and UX-02 through UX-06, PREFLIGHT.REQUEST.1
and T6 Round 11 are out of scope.

## Measured entry state

SEC-02. `web/auth_gate.py` (sha256 `38ebbf1a…`, identical to the audited file)
compared only the Origin hostname with the request's `Host` header, and treated
any two of `localhost`, `127.0.0.1` and `::1` as equal. Scheme and port were
ignored, `Referer` stood in for a missing Origin, and a missing Origin was
accepted. Against `http://localhost:5000` with WEB_AUTH_TOKEN unset, the audited
Dream reference import from `http://localhost:7999` and `http://127.0.0.1:7999`
returned 200 and wrote reference files; `http://attacker.invalid:7999` returned
403. `tests/test_auth_web1.py` replays exactly that experiment on the audited
bytes (reconstructed from the reversal receipt and digest-checked against the
audit) and reproduces all four outcomes. The audit did not show that an
arbitrary Internet site can attack the local app, and this phase makes no such
claim.

Two further entry facts: comparing against the request's `Host` header let a
DNS-rebound hostname match itself, and a non-ASCII token header raised
`TypeError` inside `hmac.compare_digest` (an HTML 500).

UX-01. With WEB_AUTH_TOKEN set, `GET /` rendered the UI, but no browser path
could attach the token. Native form and fetch POSTs received 401, while a
hand-supplied header succeeded.

## Origin model (owner: `web/request_origin.py`)

An origin is one `Origin(scheme, host, port)` tuple, compared as a whole:

- scheme: `http` or `https`, case-insensitive;
- host: lowercase DNS name (labels of `[a-z0-9_-]`, no trailing dot, at most
  253 characters), canonical dotted-quad IPv4, or IPv6 in WHATWG serialization
  (bracketed, compressed, hex pieces only);
- port: the effective port; an absent port is 80 or 443.

The canonical representation is the browser's ASCII serialization
(`http://localhost:5000`, `https://localhost`, `http://[::1]:5000`). Paths,
queries, fragments, userinfo, wildcards, empty or zero ports, whitespace,
non-ASCII text, number-like hostnames that browsers would reparse as IPv4, and
anything over 300 characters do not parse.

`localhost`, `127.0.0.1` and `::1` are different hosts. `https://localhost:5000`
differs from `http://localhost:5000`, and `http://localhost:5001` differs from
both.

## Allowed origins

Default: the one origin of the listening socket, from the PEP 3333 fields
the bundled Werkzeug server fills from its bound socket (`wsgi.url_scheme`,
`SERVER_NAME`, `SERVER_PORT`). The `Host` and `Origin` headers are never
consulted, so a DNS-rebound hostname is not an allowed origin. A wildcard bind
(`0.0.0.0` or `::`) names no origin a browser can use and yields an empty set.
`python main.py --web` and `python -m web.app` listen on `127.0.0.1:5000`, the
address `launch_web` prints and opens, so the default is
`http://127.0.0.1:5000`.

No reverse-proxy or public-origin configuration existed to reuse. The one
explicit mechanism is `WEB_ALLOWED_ORIGINS`, a comma-separated list of complete
origins that **replaces** the default:

- entries are trimmed and normalized like Origin headers; empty entries are
  skipped;
- an invalid entry is dropped, printed once as a warning (ASCII-escaped,
  truncated to 80 characters), never widened into a pattern, and never replaced
  by the default. If every entry is invalid, no browser origin is allowed;
- only the first 16 non-empty entries are read; the rest are ignored and
  counted in the same warning;
- no wildcard scheme, wildcard port or substring host match exists.

Use it for local aliases (`http://localhost:5000` alongside
`http://127.0.0.1:5000`), published Docker ports (`http://localhost:5056`),
reverse proxies and TLS termination, and for any WSGI server that derives
`SERVER_NAME` from the `Host` header.

## Browser context, missing Origin, null Origin, Referer

Audit of existing non-browser clients: the Flask test clients in the HTTP
harness, route and phase suites, `scripts/*` test-client users and CLI/API
callers send no Origin. Header-token clients (`X-CATTUS-Web-Token`,
`Authorization: Bearer`) are documented in the README. The AUTH.DREAM.1 browser
test proxies Chromium requests through a Flask test client carrying the token
header and no Origin.

A request is a **browser request** when it carries any of `Origin`,
`Sec-Fetch-Site`, `Sec-Fetch-Mode`, `Sec-Fetch-Dest` or `Referer`. Current
browsers attach `Origin` to every POST, and Fetch Metadata to requests for
localhost. User-Agent is not consulted, and a session cookie alone never selects
the browser path.

- Browser request without Origin (only Fetch Metadata or Referer): rejected,
  `origin_missing`.
- `Origin: null` (sandboxed documents, `file:`, cross-origin redirects): rejected,
  `origin_null`, in every mode.
- More than one Origin value (Werkzeug joins repeats with a comma): rejected,
  `origin_ambiguous`. Malformed values: `origin_malformed`.
- Referer is never trust evidence. It only marks a request as browser-originated,
  which makes the stricter contract apply.
- A request with no browser metadata is a non-browser client and keeps the API
  contract below. An engine that omits Origin and Fetch Metadata on a cross-site
  POST (pre-2019 browsers) would be treated as such a client. With a token
  configured it still needs the token header; in auth-off mode it has the
  pre-existing loopback contract.

## Gate order (owner: `web/auth_gate.py::should_allow_mutation`)

Safe methods pass. For POST, PUT, PATCH and DELETE:

Browser request, three independent proofs in order:

1. exact origin (403 `origin_*`);
2. CSRF: a valid browser session (403 `browser_session_missing` or
   `browser_session_invalid`, the latter covering tampered, expired, ambiguous
   and rotated sessions), then exactly one matching token (403 `csrf_missing`,
   `csrf_ambiguous`, `csrf_invalid`);
3. authentication. With WEB_AUTH_TOKEN set: an authenticated session, or a
   valid token header (401 `auth_required`, 403 `web_auth_token_mismatch`);
   `/auth/login` alone is exempt, because it performs authentication. Without
   WEB_AUTH_TOKEN: a loopback client (403 `non_loopback_rejected`).

Non-browser request: `/auth/login` is refused (403 `browser_context_required`).
Otherwise the existing contract applies unchanged in meaning: a valid token
header when WEB_AUTH_TOKEN is set, else a loopback client. A session cookie
authenticates nothing on this path, and no CSRF token is required.

Consequences, each pinned by tests: a valid token cannot make a wrong origin
acceptable; a correct origin cannot replace the token; a valid session and a
copied, valid CSRF value cannot pass a wrong origin; auth-off browser mutations
still require the exact origin and CSRF.

The before-request hook `web/app.py::_web_mutation_gate` stays the only
before-request function. It computes the allowed origins, the verified session
read and the submitted CSRF values: one `X-CSRF-Token` header, or else
`csrf_token` form fields of a form-encoded or multipart body, read only for
browser requests. A refusal is JSON with `error_code`, `auth_required` and an
`X-CATTUS-Request-Integrity` header naming the failed proof, or `text/plain` for
top-level navigations. Refusals carry `nosniff` and `no-store`, never HTML, and
never echo the token, the session, the CSRF value or the offered origin.
Token comparison runs HMAC fingerprints through `hmac.compare_digest`, so odd
input cannot raise.

## CSRF and browser session (owner: `web/browser_session.py`)

Chosen model: WEB_AUTH_TOKEN bootstraps a server-issued browser session. No
second permanent secret was introduced, and the token is never put in a page.

- Session cookie `cattus_ui_session` = `v1.<id>.<a|u>.<issued>.<mac>`. The id is
  `secrets.token_urlsafe(32)`. The MAC is HMAC-SHA256 under a per-process
  `secrets.token_bytes(32)` secret over the fields, plus a fingerprint of
  WEB_AUTH_TOKEN for authenticated (`a`) sessions. Verification compares the
  MAC text in constant time and rejects future (more than 60 s) and expired
  (more than 12 h) sessions. The cookie is 128 characters at most and holds no
  secret.
- CSRF token = HMAC-SHA256(secret, "cattus-csrf", id): unguessable, bound to one
  session, not derived from repository path, time or a constant. It travels
  separately from the cookie and is verified server-side. Sign-in rotates the
  session id, so an anonymous page's token is stale for the signed-in session.
- Rendering the UI (`/`, `/session/<id>`) or `GET /auth/session` reuses a valid
  session or mints an anonymous one. The page gets the token in
  `<meta name="cattus-csrf-token">` and the state (`not_required`,
  `signed_out`, `signed_in`) in `<meta name="cattus-auth-state">`. Such
  responses are `Cache-Control: no-store`.
- `POST /auth/login` (browser only, exact origin and CSRF) reads
  `web_auth_token` from the form body. Query strings are ignored. On a match it
  mints an authenticated session and returns the new CSRF token. A wrong token
  returns 401 and leaves the existing anonymous session unchanged. Auth-off
  returns 409.
- Cookie attributes: `HttpOnly` (no script needs the session), `SameSite=Lax`,
  `Path=/`, no `Domain`, no `Max-Age` (the server enforces expiry). `Secure`
  only when the server sees HTTPS, because a `Secure` cookie on
  `http://127.0.0.1` would make the local UI unusable. SameSite is defense in
  depth only: other ports on the same host are same-site, which is exactly why
  the origin check is the primary control.

Restart and rotation: there is no durable session secret, so a restart
invalidates every browser session and CSRF token. Changing WEB_AUTH_TOKEN
invalidates authenticated sessions, whose MAC binds the old token's
fingerprint. Anonymous sessions only carry CSRF and survive rotation. The UI
then shows the authentication-required state; nothing retries silently.

## Frontend transport (owner: `web/static/request_integrity.js`)

The helper loads before every other script in `index.html` and replaces
`window.fetch` with one bounded wrapper, so the 62 existing POST call sites
need no edits. For same-origin POST, PUT, PATCH and DELETE it sets
`X-CSRF-Token` and `credentials: "same-origin"`. Safe methods and cross-origin
requests pass through untouched, so the token never leaves the origin. JSON
defaults are not applicable: every call site already sets its own body and
content type, and the helper changes neither.

On a refusal header it dispatches `cattus:request-integrity`, refreshes the
session state from `GET /auth/session` for session and CSRF codes, and shows
one in-flow panel (`#cattusAuthPanel`, text rendered via
`CattusSafeContent.renderText`) with a sign-in form when signed out. For origin
codes it shows guidance instead. The failed request is never retried.

Forms: a capture-phase `submit` listener adds or refreshes a hidden
`csrf_token` field on every same-origin POST form. It also runs at
DOMContentLoaded, so programmatic submission carries it. While signed out it
holds the form back and asks for sign-in. The sign-in form posts the token in a
body to `/auth/login` and clears the input. The helper never uses
localStorage, sessionStorage, `document.cookie` or query strings, and it never
writes HTML.

Template delta: two meta tags and one script tag in `<head>`; the page body and
every handler are byte-identical. `safe_content.js` and the DOMPurify policy are
unchanged.

## Mutation route inventory

Every Flask rule with POST, PUT, PATCH or DELETE (65 POST rules: the 64
existing ones plus `/auth/login`; none use PUT, PATCH or DELETE), including `/`,
patch apply and test, patch-plan apply and test, generate patch and candidates,
Undo, Dream apply/run/stop/queue/references/trials/promote, history session
archive and delete, harness controls, MCP inspector launch, uploads, replay
janitor apply, lessons, proposals, benchmarks, worker imports and
`/auth/login`) goes through the one before-request gate. The inventory test
replaces every handler with a spy. It asserts cross-origin, alias-host,
missing-CSRF, stale-CSRF, unauthenticated-API and anonymous-browser requests are
refused before the handler for each method, and that an exact, authenticated,
CSRF-valid request reaches the handler, so the inventory cannot pass vacuously.

## Read routes (decision)

Unchanged. GET routes were public before, and the audit's UX-01 statement
("UI GET remains reachable") describes the existing WEB_AUTH_TOKEN contract,
which covers mutations only. Some GET routes return sensitive repository
content (evidence files, reports, replays, sessions). With the server bound to
loopback they are readable by local processes, and by a DNS-rebinding page,
since reads do not check the Host header. This remains an open read-auth
concern for a separate phase. Mutations are not affected: a rebound Origin is
never an allowed origin.

## Performance

Median per-operation cost on the development machine (Python 3.14, Chromium
151), measured by `tests/test_auth_web1.py::test_request_integrity_overhead_is_bounded`
and `tests/test_auth_web1_browser.py::test_browser_transport_owner_overhead_is_bounded`:

| Operation | Median |
| --- | --- |
| Origin parse and exact check | 6.8 µs |
| Allowed-origin derivation | 10.7 µs |
| Session cookie verification | 17.6 µs |
| CSRF verification | 4.6 µs |
| Full gate decision (browser, authenticated) | 17.3 µs |
| Browser protected-request preparation | 3.2 µs |

This is trivial beside any mutation: a single-file patch apply, Dream apply or
reference import performs file I/O measured in milliseconds.

## Limitations

- Browser sessions live in a per-process secret: a restart, a second worker
  process or a token change requires signing in again.
- There is no sign-out control and no server-side revocation list. A captured
  cookie is valid until restart, token rotation or 12-hour expiry.
- A page on another port of the same host can overwrite (toss) the session
  cookie. It cannot forge one (unknown secret), so the effect is limited to
  signing the user out; duplicate cookies fail closed as ambiguous.
- Two C.A.T.T.U.S servers on one host share the cookie name and sign each other
  out.
- `Secure` is not inferred behind a TLS-terminating proxy; such deployments
  should serve HTTPS end to end or accept a non-Secure cookie.
- Engines that send neither Origin nor Fetch Metadata on cross-site POSTs are
  treated as non-browser clients (see above).
- Read routes and DNS rebinding for reads remain open (see Read routes).
- No rate limiting on `/auth/login`; header-token brute force was already
  possible on every mutation route.
