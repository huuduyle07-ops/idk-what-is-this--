# SEC.UI.1 — Untrusted Evidence Active-Content Boundary

Started 2026-09-13; report finalized 2026-09-14. SEC-01 is closed for the audited rendering paths. This is new remediation evidence; the 2026-09-11 audit is unchanged. Track A remains frozen. DATA-01, EXEC-01, AUTH-01 and DATA-02 have not begun.

**Exact phase file inventory**

These 22 files are attributable to SEC.UI.1: 12 existing files changed and 10 files added. Differences are measured against the working tree at entry, which already contained unrelated UI and Track-A work. The reversal fixture records exact entry bytes for every changed existing file.

| File | Attribution |
| --- | --- |
| `core/phase_registry.py` | Modified from entry |
| `docs/designs/2026-09-13-untrusted-evidence-active-content-boundary.md` | Added |
| `docs/roadmap/phase_registry.json` | Modified from entry |
| `requirements_browser.txt` | Added |
| `tests/fixtures/sec_ui1_completion.json` | Added |
| `tests/fixtures/sec_ui1_frozen_boundaries.json` | Added |
| `tests/fixtures/sec_ui1_reversal.json` | Added |
| `tests/test_help_route.py` | Modified from entry |
| `tests/test_phase_picker.py` | Modified from entry |
| `tests/test_phase_registry.py` | Modified from entry |
| `tests/test_sec_ui1.py` | Added |
| `tests/test_web_ui_command_hierarchy.py` | Modified from entry |
| `tests/test_web_ui_cutoff_1.py` | Modified from entry |
| `tests/test_web_ui_demo_flow.py` | Modified from entry |
| `tests/test_web_ui_information_architecture.py` | Modified from entry |
| `tests/test_web_ui_result_readability.py` | Modified from entry |
| `web/app.py` | Modified from entry |
| `web/static/safe_content.js` | Added |
| `web/static/vendor/dompurify/LICENSE` | Added |
| `web/static/vendor/dompurify/README.md` | Added |
| `web/static/vendor/dompurify/purify.min.js` | Added |
| `web/templates/index.html` | Modified from entry |

**Required report, in request order**

1. **Exact files changed:** the inventory above is exhaustive. Temporary pytest XML, startup logs and measurements live under `.tmp/sec-ui1/`; durable results are in `tests/fixtures/sec_ui1_completion.json`.
2. **Old Evidence Viewer flow:** repository `.agent/presentation_evidence/*.md` → `web.app.presentation_evidence_file_route` (`/presentation/evidence/file?as=html`) → Python-Markdown with `fenced_code`, `tables`, `toc`, retaining raw HTML → JSON `data.html` → `openPresentationEvidenceFile` → `evidencePackViewer.innerHTML`. All file names, including the index and historical files, used this handler.
3. **Old Local Critique flow:** `agents.ollama_client.run_local_critique` → `/local_critique` → `localCritique()` → model verdict, summary, risk flags and must-fix fields interpolated into `localCritiqueMain.innerHTML`. The error field also had a direct interpolation. Thought text was already plain text.
4. **New authoritative boundary:** existing Markdown rendering, when applicable → `CattusSafeContent.renderHTML(target, untrustedHTML, rawFallback)` → private DOMPurify instance with one allowlist → detached `DocumentFragment` → safe DOM operations → `replaceChildren`. Plain fields use the same module's `renderText` (`textContent`). Application-owned layout stays outside the sanitizer.
5. **Implementation:** `web/static/safe_content.js`, policy `sec_ui1_v1`. Positive HTML/attribute allowlists; HTML-only tag selection; DOM clobbering protection; platform URL parsing; fragment type validation; safe failure branch. There is no home-grown HTML parser, payload-specific replacement, or raw-HTML fallback.
6. **Dependency:** locally vendored, unmodified DOMPurify 3.4.11 browser distribution, 28,438 bytes, with upstream license and provenance/digest. Copied from an existing local npm installation. The project had Python-Markdown and a specialized Dream Markdown renderer, but no established general HTML sanitizer. No download, CDN, npm dependency resolution or new build system was needed.
7. **Raw HTML policy:** raw HTML inside Markdown is untrusted and passes through the same allowlist. Safe formatting can survive; excluded markup is removed, with safe text retained where DOMPurify permits. Existing Dream escaping remains a formatting producer, not a second independently configured sanitizer.
8. **Allowed Markdown:** paragraphs, headings, bold/italic/strikethrough, lists, blockquotes, inline/fenced code, ordinary links, horizontal rules and tables remain readable. Local Critique preserves its existing safe HTML formatting; it does not gain a new Markdown parser. Verdict/error/risk-code/thought fields are literal text.
9. **Dangerous elements:** script, iframe, object, embed, base, meta, style, forms and other non-allowlisted elements cannot reach the live content DOM as active elements. Embedded documents and script-capable namespaces are excluded.
10. **Event attributes:** none are allowed. All attributes must pass a positive per-element allowlist, so blocking covers every event name rather than a short `onerror` list.
11. **URL protocols:** only values resolving to `http:` or `https:` are admitted in links. Ordinary relative links, fragments and protocol-relative HTTP(S) links are supported. `javascript:`, `data:`, `vbscript:` and other schemes are removed. Encoded and tab-obfuscated JavaScript schemes are tested. Markdown link syntax grants no additional trust.
12. **SVG/MathML:** neither namespace is admitted; SVG load/animation/xlink payloads, MathML payloads and a malformed namespace/mutation-XSS regression are inert.
13. **Styles:** untrusted inline styles, style elements, CSS classes and arbitrary data/ARIA attributes are excluded. Existing application styles and classes are unchanged.
14. **Links:** retained anchors receive `rel="noopener noreferrer"`. Only `_blank` and `_self` targets are retained. Heading IDs are prefixed by DOMPurify (`user-content-`) to prevent clobbering; local fragment links receive the matching prefix. Relative source links remain unchanged.
15. **Images:** untrusted images never load in the live DOM. `src`/`srcset` are forbidden; sanitized image placeholders become text such as `[Image: diagram]` or `[Image: omitted]` before insertion. This deliberately prevents evidence-triggered external image requests.
16. **Code fidelity:** inline/fenced code containing HTML and JavaScript is literal, with original characters recoverable through `textContent`. Quoted code, context evidence and the existing diff renderer are checked. No code content is interpreted as markup. Python-Markdown's existing final newline in fenced code is preserved.
17. **Failure behavior:** missing/unsupported sanitizer, thrown exceptions or a non-fragment result produce a `<pre>` whose content is assigned using `textContent`. Evidence uses the original Markdown fallback. Local Critique uses the original field. Server Markdown exceptions also lead to literal source. Nothing falls back to raw HTML.
18. **Persisted raw data:** no report or session is rewritten by this fix. Backend JSON may retain raw source and unsanitized rendered HTML for existing consumers; those values remain untrusted. Safety is enforced each time the UI renders them.
19. **History reload:** an actual persisted session contains the audit payload and source excerpts; an actual on-disk report contains the malicious fixture. Two browser reloads plus report reopens remain inert. Session and report bytes are checked unchanged. Historical Dream summary rendering also crosses the boundary.
20. **Exact SEC-01 PRE:** the existing audit records `executed=true`. The actual entry Evidence Viewer handler is preserved in the reversal fixture and executed in Chromium against the real route; the same marker becomes `data-audit-executed="true"` on the synthetic image. No credentials, exfiltration or mutation endpoints are involved.
21. **Exact SEC-01 POST:** reloading restores the shipped handler. The same payload renders `[Image: omitted]`, with no image, handler or executed marker in the viewer. Reloading again gives the same inert result.
22. **Script test:** a script marker plus safe trailing paragraph leaves no script node and never sets the marker.
23. **Event tests:** `onerror`, `onload`, `onclick`, `onmouseover` and SVG `onbegin` are removed along with other non-allowlisted attributes. Browser tests dispatch error/load/click/mouseover/focus events and observe no execution.
24. **JavaScript URL tests:** Markdown, raw HTML, entity-encoded and tab-obfuscated forms lose active href values. Data and VBScript schemes are also negative cases.
25. **SVG test:** SVG onload, xlink JavaScript and animation handlers are inert; MathML and malformed namespace cases pass too.
26. **Local Critique result:** the real browser handler and real Flask route consume a fixture adapter. The audit-style image is inert in the summary; verdict, errors, risk-code and thought preserve literal payload text; must-fix HTML is sanitized. Safe strong/emphasis formatting survives. Live model calls: zero.
27. **Safe Markdown positive:** headings, bold/emphasis, ordered/unordered lists, blockquotes, tables, links and exact code text pass DOM assertions. A second evidence file opens through the existing navigation function. Application diff rendering and context display remain usable.
28. **Browser integration:** 24 browser tests and 6 deterministic source/governance tests pass in Chromium 151.0.7922.34 using Playwright 1.62.0. They load the production Flask template, local assets and actual handlers. No CSP is installed. No tests are skipped.
29. **Direct-innerHTML regression:** the bounded source test inventories every HTML assignment in Evidence, Critique, Help and Dream handlers, rejects direct untrusted interpolations and alternate raw sinks, and pins calls to the shared helper. The helper itself has no `innerHTML` use. Static application literals and closed verdict-class selection remain permitted.
30. **CSP:** unchanged and not the primary defense. This UI has extensive inline scripts and event handlers; a compatible CSP is deferred rather than widening this phase. The browser security assertions explicitly run without a CSP header.
31. **Performance:** warm median insertion timings for three sizes appear below, with Markdown time and browser startup measured separately. These are bounded local measurements, not a throughput or worst-case guarantee.
32. **Model calls:** zero. No T6 authoring run, authoring rerun, live revision or provider smoke was added or executed.
33. **External network:** zero external network calls required for implementation, startup or tests. Sanitizer bytes were available locally. Browser tests intercept the existing Mermaid URL with a local test stub; other nonlocal requests are aborted and asserted absent. Python networking is limited to loopback in the security fixture. This does not resolve the pre-existing production Mermaid/CDN availability issue (UX-05).
34. **Backend mutation delta:** zero Apply/Undo/Dream mutation changes. The only `web/app.py` delta is the presentation response type for `/help`: `text/plain` plus `nosniff`, so direct navigation cannot execute its untrusted HTML fragment. The modal still renders through the shared sanitizer.
35. **Auth delta:** zero token, origin, CSRF or authorization changes.
36. **UI redesign delta:** zero theme/framework/layout redesign. Existing wrappers, headings, controls and styles remain; content nodes are populated safely. Direct `/help` displays fragment text rather than an active HTML document; the normal Help modal retains formatting.
37. **Track-A delta:** zero semantics changed in PATCH.MINIMAL.LIVE.3, PATCH.AUTHOR.LIVE.3, INDENT.SEMANTICS.1, INDENT.RUNTIME.1, DEFECT.PROBE, CANDIDATE.VERIFY, ANSWER.COHERENCE, targeted validation or execution authority. A 452-file entry manifest pins unchanged production and original audit bytes. Candidate fingerprints, receipts, grounding and presentation identity are untouched. The registry gains only the SEC namespace/record.
38. **Focused tests:** all 30 SEC.UI.1 checks pass, zero failures/errors/skips; wall time 71.724 seconds, including browser startup, servers, reloads and the performance probe.
39. **Adjacent web tests:** evidence routes/pack, Dream Markdown, Help, all existing `test_web_ui_*.py` modules, evidence UI loaders, benchmark UI, runtime modes, web runner/helpers and auth/mutation surface checks pass.
40. **Persisted/session tests:** included both in the real browser history test and existing web history controls. Raw session/report equality is asserted after reload; no destructive migration occurs.
41. **Browser tests:** 24 pass, zero skips, including 14 Evidence negative vectors, PRE/POST/history, Markdown/diff compatibility, Local Critique, three sanitizer failures, parser failure, Help/Dream and policy isolation/output checks plus performance.
42. **Broad affected suite:** 559 passed, zero failures/errors/skips, 16.361 seconds. This is the affected suite, not every repository test. Frozen T6/authoring logic was not rerun. Existing Google SDK deprecation warning only.
43. **Build/startup:** actual `web.runner.launch_web(host='127.0.0.1', open_browser=False)` startup returned HTTP 200 for `/` and all four local assets checked. Time to first HTTP success: 2977.236 ms. Python compilation, registry/picker CLIs, all 54 benchmark fixture checks and `git diff --check` passed.
44. **Dependency/build impact:** Flask still serves ordinary static JavaScript. Existing `package.json`, lockfile and runtime requirements are unchanged. `requirements_browser.txt` is test-only; Chromium/Playwright were already installed. No runtime build step, CDN security dependency or package-manager startup is added.
45. **Governance:** exactly one phase, SEC.UI.1, in the existing HARDEN track; no separate audit-ID registry. Registry has 181 phases, 177 complete/history, HARDEN has 10. Picker recommendation remains DOGFOOD.1B. Existing script-count tests now admit the two local security assets while preserving the one-external-script check. The original audit remains historical.
46. **Known limitations:** closure is bounded to these rendering paths, not a whole-frontend XSS audit. The sanitizer must be maintained on dependency upgrades. External links can navigate when deliberately activated. Images, arbitrary styles, non-HTTP schemes and some raw HTML formatting intentionally no longer render. Browser proof is Chromium, not all browser engines. Existing Mermaid availability and broader CSP work remain separate.
47. **Remaining Track-B findings:** DATA-01 cross-repository Undo backups; EXEC-01 malformed-plan partial writes; AUTH-01 Dream review/apply identity; DATA-02 rollback truthfulness; SEC-02 origin handling; UX-01 token transport; UX-02 response races; UX-03 Undo state; UX-04 mode restoration; UX-05 Mermaid availability; UX-06 keyboard/focus behavior. None is claimed fixed here.
48. **Concurrent-work attribution:** all pre-existing work is preserved. The twelve edited entry files can be reversed in memory to their recorded entry SHA-256, without touching the tree. All other entry-file hashes remained unchanged. Historical audit/Track-A fixtures were not repinned or rewritten. No stash/reset/clean was used.
49. **Readiness for next phases:** SEC.UI.1's stop condition is satisfied; DATA-01, EXEC-01, AUTH-01 and DATA-02 may be scoped separately. No implementation of those phases has begun and their findings remain open.
50. **SEC-01 closure:** yes, for both audited untrusted-content paths. The browser-proven marker and equivalent active-content vectors are inert, historical reload is safe, useful Markdown/code remains, and sanitizer failure renders literal source.

**Exact benign browser payload**

```html
<img src="missing-audit-image" onerror="this.setAttribute('data-audit-executed','true')">
```

PRE: `executed=true`. POST: no active image or event attribute, visible `[Image: omitted]`; marker absent. Raw stored evidence retains the original payload.

**Performance, milliseconds**

| Report | Source bytes | HTML bytes | Markdown | Baseline insert | Safe render | Added render time |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| small | 449 | 812 | 1.956 | 0 | 0.3 | 0.3 |
| medium | 8,980 | 16,307 | 32.337 | 0.7 | 3.5 | 2.8 |
| large | 89,800 | 163,287 | 329.221 | 6.9 | 30.7 | 23.8 |

Browser startup: 1931.57 ms, excluded from every rendering column. Browser samples use 3 warmups and 7 measured iterations, taking medians; Markdown uses 5 iterations. Insertion includes sanitization, safe fragment postprocessing and DOM replacement, without a forced paint/layout. A zero baseline entry means below the timer's measured resolution. The legacy insertion baseline uses only the safe Markdown fixture. These figures vary with load.

**Explicit answers**

| Question | Answer |
| --- | --- |
| Can repository/report HTML execute JavaScript in Evidence Viewer? | No, through the repaired boundary. |
| Can Local Critique model output execute active HTML? | No. |
| Are event attributes preserved? | No. |
| Are `javascript:` URLs active? | No. |
| Can fenced code containing HTML execute? | No; it displays literally. |
| Is raw historical evidence destroyed? | No; source/session bytes remain unchanged. |
| Does sanitizer failure ever fall back to raw HTML? | No; it renders literal text in a preformatted element. |
| Is CSP the primary defense? | No; sanitization is the primary boundary, and tests run without CSP. |
| Were Apply/Undo/Dream semantics changed? | No mutation or authority semantics changed. |
| Was auth changed? | No. |
| Was Track A changed? | No semantic changes. |
| Were live model calls added? | No; zero live calls. |

**Reproduction**

Run with database/embeddings disabled, no web token, and local test dependencies already installed. The security suite requires Chromium; it does not silently skip browser proof. Installing those test dependencies on a fresh machine is a separate setup operation and is not performed by the tests.

```powershell
$env:DB_ENABLED = 'false'
$env:DATABASE_URL = ''
$env:DATABASE_URL_LOCAL = ''
$env:DATABASE_URL_DOCKER = ''
$env:INDEX_USE_EMBEDDINGS = 'false'
$env:ROUTER_USE_EMBEDDINGS = 'false'
$env:RETRIEVER_USE_DB = 'false'
$env:EMBEDDING_PROVIDER = 'off'
$env:WEB_AUTH_TOKEN = ''
python -m pytest tests/test_sec_ui1.py -q -p no:cacheprovider --basetemp=.tmp/sec-ui1/recheck
python -m pytest tests/test_phase_registry.py tests/test_phase_picker.py -q -p no:cacheprovider --basetemp=.tmp/sec-ui1/governance-recheck
python -m compileall -q web tests/test_sec_ui1.py core/phase_registry.py
python benchmarks/run_benchmarks.py --check
git diff --check
```

The completion JSON records every affected test module, every focused case, source digests, exact PRE/POST behavior, startup results and the measurements above. Full browser runtime was local; the unrelated Mermaid test stub does not alter production code.
