"""SEC.UI.1: real Chromium, production Flask routes/handlers, fixtures only.

Requires requirements_browser.txt and an already installed Playwright Chromium.
All external browser requests are intercepted; Mermaid is a local test stub only.
No CSP is installed. No live provider, database, mutation or authoring run is used.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import socket
import statistics
import sys
import threading
import time
from types import SimpleNamespace
from urllib.parse import urlsplit

import markdown
import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests' / 'fixtures'
TEMPLATE = ROOT / 'web' / 'templates' / 'index.html'
POLICY = ROOT / 'web' / 'static' / 'safe_content.js'
AUDIT = ROOT / 'docs' / 'audits' / '2026-09-11-security-and-ui-ux-results.json'
# Exact browser-proven SEC-01 payload (the historical artifact remains untouched).
AUDIT_PAYLOAD = '<img src="missing-audit-image" onerror="this.setAttribute(\'data-audit-executed\',\'true\')">'
MARK = 'window.__secUi1Executed=true'
PAYLOADS = {
    'audit_onerror': AUDIT_PAYLOAD,
    'script': f'<script>{MARK}</script><p>safe tail</p>',
    'events': f'<p onclick="{MARK}" onmouseover="{MARK}">click me</p><img onload="{MARK}" onerror="{MARK}" src="/missing">',
    'javascript_markdown': f'[unsafe](javascript:{MARK})',
    'javascript_html': f'<a href="java&#x73;cript:{MARK}" target="_blank">unsafe</a>',
    'control_url': f'<a href="java&#x09;script:{MARK}">unsafe</a>',
    'data_url': '<a href="data:text/html,%3Cscript%3Ealert(1)%3C/script%3E">unsafe</a>',
    'vbscript': '<a href="vbscript:msgbox(1)">unsafe</a>',
    'svg': f'<svg onload="{MARK}"><a xlink:href="javascript:{MARK}"><text>svg</text></a><animate onbegin="{MARK}"/></svg>',
    'mathml': f'<math><mtext><img src="/missing" onerror="{MARK}"></mtext></math>',
    'documents': f'<iframe srcdoc="&lt;script&gt;{MARK}&lt;/script&gt;"></iframe><object data="data:text/html,active"></object><embed src="/missing"><base href="https://blocked.invalid/"><meta http-equiv="refresh" content="0;url=https://blocked.invalid/">',
    'style': '<style>body{display:none}</style><p style="background:url(https://blocked.invalid/a)" class="app-owned" id="repoPathInput">text</p>',
    'image': '![diagram](https://blocked.invalid/image.png)\n\n<img src="https://blocked.invalid/other.png" srcset="https://blocked.invalid/third.png" alt="raw image">',
    'mutation_xss': f'<math><mtext><table><mglyph><style><!--</style><img title="--><img src=/missing onerror={MARK}>">',
}
CODE = '<img src=x onerror="window.__secUi1Executed=true">\nconst value = "<&>";'
SAFE = '''# Evidence heading

**bold text** and *emphasis* with `a < b && b > 0`.

> quoted evidence & text

- one
- two

Ordered evidence:

1. first
2. second

[safe](https://example.invalid/source) and [relative](./source.md) and [heading](#evidence-heading).

<a href="https://example.invalid/new" target="_blank">new context</a>

| key | value |
| --- | --- |
| a | b |

```html
''' + CODE + '\n```\n'


def _function(source, start, end):
    begin = source.index(start)
    return source[begin:source.index(end, begin)]


def test_exact_audit_payload_is_historical_and_pre_was_executed():
    audit = json.loads(AUDIT.read_text(encoding='utf-8'))
    browser = audit['browser']
    proof = next(value for value in browser.values() if isinstance(value, dict) and 'executed' in value)
    assert proof['executed'] == 'true'
    assert AUDIT_PAYLOAD[:-1] in proof['viewer']


def test_bounded_sink_ownership():
    source = TEMPLATE.read_text(encoding='utf-8')
    evidence = _function(source, 'function openPresentationEvidenceFile(', 'function openPresentationEvidenceIndex(')
    critique = _function(source, 'async function localCritique()', 'const repoInput =')
    help_view = _function(source, 'function openHelpModal()', '// ── Keybinding editor')
    dream = _function(source, 'function viewDreamRun(', 'function applyDream(')
    assert 'CattusSafeContent.renderHTML(content, data.html, data.content)' in evidence
    assert '.innerHTML' not in evidence
    assert 'CattusSafeContent.renderHTML(main.querySelector(".critique-summary"), c.critic_summary' in critique
    assert 'CattusSafeContent.renderHTML(item, fix)' in critique
    assert 'CattusSafeContent.renderText(code, flag)' in critique
    assert 'CattusSafeContent.renderHTML(content, html)' in help_view
    assert 'CattusSafeContent.renderHTML(report, data.morning_report_html, morning)' in dream
    # Inventory ALL assignments on these bounded handlers. Only app-owned literals
    # (and the closed verdict-class enum) may remain. New direct sinks fail here.
    assignments = re.findall(r'\.innerHTML\s*=\s*([\s\S]*?);', evidence + critique + help_view + dream)
    assert len(assignments) == 5
    for assignment in assignments:
        assert assignment.lstrip().startswith(('"', "'", '`'))
        assert not re.search(r'\$\{(?!verdictClass\}|escapeHtml\(String\(err\)\)\})', assignment)
    for handler in (evidence, critique, help_view, dream):
        assert not re.search(r'outerHTML\s*=|insertAdjacentHTML|document\.write', handler)
    assert '.innerHTML' not in POLICY.read_text(encoding='utf-8')
    assert source.index("filename='vendor/dompurify/purify.min.js'") < source.index("filename='safe_content.js'") < source.index('<script>')


def test_vendored_dependency_pin_and_no_build_dependency():
    dep = ROOT / 'web/static/vendor/dompurify/purify.min.js'
    assert hashlib.sha256(dep.read_bytes()).hexdigest() == 'dbabb5b205a333ec49c8c09e7fca30ef66df0523bb8bc0fa9ea843841f111dbd'
    assert '3.4.11' in dep.read_text(encoding='utf-8')[:300]
    assert (dep.parent / 'LICENSE').is_file()
    assert 'motion' in json.loads((ROOT / 'package.json').read_text())['dependencies']


def test_frozen_entry_bytes_and_original_audit_preserved():
    from tests._data_undo1_maintenance import before_data_undo1
    manifest = json.loads((FIXTURES / 'sec_ui1_frozen_boundaries.json').read_text())
    changed = [name for name, digest in manifest['sha256'].items() if hashlib.sha256(before_data_undo1(name)).hexdigest() != digest]
    assert changed == []


def test_reversal_reconstructs_entry_without_repinning_history():
    from tests._data_undo1_maintenance import before_data_undo1
    manifest = json.loads((FIXTURES / 'sec_ui1_reversal.json').read_text(encoding='utf-8'))
    for name, record in manifest['files'].items():
        text = before_data_undo1(name).decode('utf-8')
        for hunk in reversed(record['hunks']):
            assert text.count(hunk['after']) == 1, name
            text = text.replace(hunk['after'], hunk['before'], 1)
        assert hashlib.sha256(text.encode('utf-8')).hexdigest() == record['entry_sha256'], name


def test_one_registered_remediation_phase_and_picker_history():
    from core.phase_registry import load_phase_registry, validate_phase_registry
    from core.phase_picker import pick_phase_candidates
    data = load_phase_registry(str(ROOT / 'docs/roadmap/phase_registry.json'))
    assert validate_phase_registry(data)['is_valid']
    phases = [p for p in data['phases'] if p['phase_id'].startswith('SEC.')]
    assert [p['phase_id'] for p in phases] == ['SEC.UI.1']
    assert phases[0]['track'] == 'HARDEN'
    assert phases[0]['status'] == 'complete'
    assert not phases[0]['model_calls_allowed'] and not phases[0]['network_allowed']
    report = pick_phase_candidates(data)
    assert 'SEC.UI.1' in {p['phase_id'] for p in report['buckets']['complete_or_history']}
    assert report['top_recommendation']['phase_id'] == 'DOGFOOD.1B'


@pytest.fixture(scope='module')
def chromium():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as driver:
        started = time.perf_counter()
        browser = driver.chromium.launch(headless=True)
        browser.sec_ui1_startup_ms = (time.perf_counter() - started) * 1000
        yield browser
        browser.close()


@pytest.fixture
def ui(tmp_path, monkeypatch, chromium):
    for key, value in {
        'DB_ENABLED': 'false', 'DATABASE_URL': '', 'DATABASE_URL_LOCAL': '', 'DATABASE_URL_DOCKER': '',
        'INDEX_USE_EMBEDDINGS': 'false', 'ROUTER_USE_EMBEDDINGS': 'false', 'RETRIEVER_USE_DB': 'false',
        'EMBEDDING_PROVIDER': 'off', 'WEB_AUTH_TOKEN': '', 'RUN_PROGRESS_POLLING_ENABLED': 'false',
        'OLLAMA_ENABLED': 'true', 'SHOW_LOCAL_THOUGHT': 'true',
    }.items():
        monkeypatch.setenv(key, value)
    import config
    for key in ('AGENT_DIR', 'STORAGE_PATH'):
        path = tmp_path / key.lower()
        path.mkdir()
        monkeypatch.setattr(config, key, path)
    monkeypatch.setattr(config, 'DB_ENABLED', False)
    monkeypatch.setattr(config, 'DATABASE_URL', '')
    monkeypatch.setattr(config, 'OUTPUT_FILE', tmp_path / 'session_log.txt')
    monkeypatch.chdir(tmp_path)
    from web import app as wa, session_store
    from agents import ollama_client
    monkeypatch.setitem(wa.app.config, 'TESTING', True)
    monkeypatch.setattr(session_store, 'SESSION_FILE', tmp_path / 'sessions.json')
    state = SimpleNamespace(critic={'critic': {'verdict': 'accept', 'confidence': 0.9, 'critic_summary': '', 'risk_flags': [], 'must_fix': []}}, external=[], requests=[], errors=[], provider_calls=[])
    monkeypatch.setattr(ollama_client, 'run_local_critique', lambda *a, **k: state.critic)
    def no_provider(*a, **k):
        state.provider_calls.append('unexpected')
        raise AssertionError('SEC.UI.1 must not call a model')
    for module in tuple(sys.modules.values()):
        name = getattr(module, '__name__', '')
        if name == 'database.memory':
            monkeypatch.setattr(module, 'DB_ENABLED', False)
            monkeypatch.setattr(module, 'DATABASE_URL', '')
        if name.startswith(('agents.', 'core.', 'web.', 'reasoning.')):
            for attr in ('run_gemini_request', 'run_gemini_request_2', 'run_deepseek_review'):
                if hasattr(module, attr):
                    monkeypatch.setattr(module, attr, no_provider)
    connect = socket.socket.connect
    def local_connect(sock, address):
        if isinstance(address, tuple) and address[0] in ('127.0.0.1', '::1', 'localhost'):
            return connect(sock, address)
        raise AssertionError(f'External Python network blocked: {address}')
    monkeypatch.setattr(socket.socket, 'connect', local_connect)
    repo = tmp_path / 'repo'
    evidence = repo / '.agent/presentation_evidence'
    evidence.mkdir(parents=True)
    report = evidence / '00_evidence_index.md'
    report.write_text(SAFE, encoding='utf-8')
    (evidence / 'second.md').write_text('# Second report\n\nsource navigation', encoding='utf-8')
    session_store.save_sessions([{
        'id': 'sec-ui1-history', 'repo_path': str(repo), 'query': 'Historical evidence',
        'web_mode': 'instant', 'project_tag': 'sec-ui1-fixture',
        'result': {'answer': AUDIT_PAYLOAD, 'context': CODE, 'patch': '{}', 'diff': '+ ' + CODE, 'validation': 'fixture'},
    }])
    session_bytes = session_store.SESSION_FILE.read_bytes()
    from werkzeug.serving import make_server
    server = make_server('127.0.0.1', 0, wa.app, threaded=True)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f'http://127.0.0.1:{server.server_port}'
    context = chromium.new_context(service_workers='block')
    def route(request_route):
        url = request_route.request.url
        if url == 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js':
            # UX-05 intentionally unchanged. Stub only this unrelated graph asset.
            request_route.fulfill(status=200, content_type='application/javascript', body='window.mermaid={initialize(){},render(){throw new Error("Graph outside SEC.UI.1");}};')
        elif url.startswith(base + '/'):
            state.requests.append(url)
            request_route.continue_()
        else:
            state.external.append(url)
            request_route.abort()
    context.route('**/*', route)
    page = context.new_page()
    page.on('pageerror', lambda err: state.errors.append(str(err)))
    response = page.goto(base + '/session/sec-ui1-history')
    assert response.status == 200
    assert 'content-security-policy' not in response.headers
    page.wait_for_function('typeof CattusSafeContent !== "undefined" && typeof openPresentationEvidenceFile === "function"')
    assert page.locator('#repoPathInput').input_value() == str(repo)
    state.page, state.context, state.report, state.repo, state.base, state.client = page, context, report, repo, base, wa.app.test_client()
    state.session_bytes, state.sessions = session_bytes, session_store
    try:
        yield state
    finally:
        assert state.provider_calls == []
        assert state.external == []
        context.close()
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


def _open(ui, text=None, name='00_evidence_index.md'):
    if text is not None:
        ui.report.write_text(text, encoding='utf-8', newline='')
    with ui.page.expect_response(lambda r: '/presentation/evidence/file?' in r.url):
        ui.page.evaluate('(name) => openPresentationEvidenceFile(name)', name)
    ui.page.wait_for_function('(name) => document.getElementById("evidencePackStatus").textContent.startsWith("Showing " + name)', arg=name)
    # Flush promise callbacks and deferred browser events; no external fetches.
    ui.page.evaluate('() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
    return ui.page.locator('#evidencePackViewer')


def _inert(page, selector):
    result = page.locator(selector).evaluate('''root => {
        // The target is application-owned; inspect all inserted descendants.
        const elements = [...root.querySelectorAll('*')];
        const active = elements.filter(e => ['SCRIPT','IFRAME','OBJECT','EMBED','BASE','META','SVG','MATH','STYLE','IMG','FORM','INPUT'].includes(e.tagName));
        const attrs = elements.flatMap(e => [...e.attributes].filter(a => /^on/i.test(a.name) || ['style','src','srcset','srcdoc'].includes(a.name)).map(a => a.name));
        const urls = elements.flatMap(e => [...e.attributes].filter(a => ['href','xlink:href'].includes(a.name)).map(a => a.value));
        for (const e of elements) for (const type of ['error','load','click','mouseover','focus']) e.dispatchEvent(new Event(type));
        return {active: active.map(e => e.tagName), attrs, urls, executed: !!window.__secUi1Executed || !!window.__cattusAuditXss || !!window.__uiAuditMarker || !!root.querySelector('[data-audit-executed="true"]')};
    }''')
    assert result['active'] == []
    assert result['attrs'] == []
    assert not result['executed']
    assert all(not re.match(r'\s*(javascript|data|vbscript):', url, re.I) for url in result['urls'])


@pytest.mark.parametrize('case', PAYLOADS)
def test_evidence_security_matrix(ui, case):
    _open(ui, PAYLOADS[case])
    _inert(ui.page, '#evidencePackViewer')
    assert ui.report.read_text(encoding='utf-8') == PAYLOADS[case]
    if case == 'audit_onerror':
        assert ui.page.locator('#evidencePackViewer').inner_text() == '[Image: omitted]'
    if case == 'image':
        assert '[Image: diagram]' in ui.page.locator('#evidencePackViewer').inner_text()
        assert '[Image: raw image]' in ui.page.locator('#evidencePackViewer').inner_text()


def test_real_browser_exact_audit_pre_then_post_and_reload(ui):
    reversal = json.loads((FIXTURES / 'sec_ui1_reversal.json').read_text(encoding='utf-8'))
    # Run the actual entry handler, then reload the shipped handler for POST.
    ui.page.add_script_tag(content=reversal['evidence_handler_before'])
    _open(ui, '# Synthetic audit evidence\n\n' + AUDIT_PAYLOAD)
    ui.page.wait_for_function('document.querySelector("#evidencePackViewer [data-audit-executed=true]") !== null')
    assert ui.page.locator('#evidencePackViewer img').get_attribute('data-audit-executed') == 'true'
    raw = ui.report.read_bytes()
    for _ in range(2):
        ui.page.reload()
        _open(ui)
        _inert(ui.page, '#evidencePackViewer')
        assert '[Image: omitted]' in ui.page.locator('#evidencePackViewer').inner_text()
        assert ui.report.read_bytes() == raw
        assert ui.sessions.SESSION_FILE.read_bytes() == ui.session_bytes
        assert ui.page.locator('#answer').inner_text().strip() == AUDIT_PAYLOAD
    assert ui.errors == []


def test_safe_markdown_fidelity_navigation_diff_and_local_assets(ui):
    viewer = _open(ui, SAFE)
    assert viewer.locator('h1').inner_text() == 'Evidence heading'
    assert viewer.locator('strong').inner_text() == 'bold text'
    assert viewer.locator('em').inner_text() == 'emphasis'
    assert viewer.locator('blockquote').inner_text().strip() == 'quoted evidence & text'
    assert viewer.locator('ul li').count() == 2
    assert viewer.locator('ol li').count() == 2
    assert viewer.locator('table tbody td').all_text_contents() == ['a', 'b']
    assert viewer.locator('pre code').text_content() == CODE + '\n'
    assert viewer.locator('p code').text_content() == 'a < b && b > 0'
    assert viewer.locator('a', has_text='relative').get_attribute('href') == './source.md'
    assert viewer.locator('h1').get_attribute('id') == 'user-content-evidence-heading'
    assert viewer.locator('a', has_text='heading').get_attribute('href') == '#user-content-evidence-heading'
    assert viewer.locator('a[target="_blank"]').get_attribute('rel') == 'noopener noreferrer'
    assert ui.page.locator('#context').inner_text().strip() == CODE
    ui.page.evaluate('(text) => { document.getElementById("diff").innerHTML = renderDiff(text); }', '+ ' + CODE)
    assert ui.page.locator('#diff > div').all_text_contents() == ['+ ' + CODE.splitlines()[0], CODE.splitlines()[1]]
    _inert(ui.page, '#diff')
    _inert(ui.page, '#evidencePackViewer')
    _open(ui, name='second.md')
    assert viewer.locator('h1').inner_text() == 'Second report'
    for name in ('safe_content.js', 'vendor/dompurify/purify.min.js'):
        response = ui.client.get('/static/' + name)
        assert response.status_code == 200
    assert ui.errors == []


def test_local_critique_all_model_fields_and_error_are_untrusted(ui):
    payload = '<img src="x" onerror="window.__uiAuditMarker=1">'
    ui.critic = {'critic': {'verdict': payload, 'confidence': 0.9,
        'critic_summary': '<strong>Safe summary</strong>' + payload + PAYLOADS['svg'] + PAYLOADS['javascript_html'],
        'risk_flags': [CODE], 'must_fix': ['<em>Safe fix</em>' + PAYLOADS['events']]}, 'thought': CODE}
    ui.page.evaluate('() => localCritique()')
    assert ui.page.locator('#localCritiqueMain .critique-verdict').text_content() == payload
    assert ui.page.locator('#localCritiqueMain .critique-summary strong').inner_text() == 'Safe summary'
    assert ui.page.locator('#localCritiqueMain code').text_content() == CODE
    assert ui.page.locator('#localCritiqueMain li em').inner_text() == 'Safe fix'
    assert ui.page.locator('#localCritiqueThought').text_content() == CODE
    _inert(ui.page, '#localCritiqueMain')
    ui.critic = {'error': payload}
    ui.page.evaluate('() => localCritique()')
    assert payload in ui.page.locator('#localCritiqueMain').inner_text()
    _inert(ui.page, '#localCritiqueMain')
    assert ui.errors == []


@pytest.mark.parametrize('failure', ['missing', 'throws', 'wrong_type'])
def test_sanitizer_failure_never_falls_back_to_html(ui, failure):
    replacement = {
        'missing': 'window.DOMPurify=undefined;',
        'throws': 'window.DOMPurify=()=>({isSupported:true,addHook(){},sanitize(){throw new Error("fixture");}});',
        'wrong_type': 'window.DOMPurify=()=>({isSupported:true,addHook(){},sanitize(){return "<img onerror=alert(1)>";}});',
    }[failure]
    ui.page.evaluate(replacement)
    ui.page.add_script_tag(content=POLICY.read_text(encoding='utf-8'))
    text = '# Raw fallback\n\n' + AUDIT_PAYLOAD
    viewer = _open(ui, text)
    assert viewer.locator('pre').text_content() == text
    _inert(ui.page, '#evidencePackViewer')
    ui.critic['critic']['critic_summary'] = PAYLOADS['events']
    ui.page.evaluate('() => localCritique()')
    assert ui.page.locator('.critique-summary pre').text_content() == PAYLOADS['events']
    _inert(ui.page, '#localCritiqueMain')


def test_server_markdown_failure_uses_literal_source(ui, monkeypatch):
    from web import app as wa
    def fail(*a, **k):
        raise ValueError('fixture parser failure')
    monkeypatch.setattr(wa._markdown_lib, 'markdown', fail)
    viewer = _open(ui, AUDIT_PAYLOAD)
    assert viewer.locator('pre').text_content() == AUDIT_PAYLOAD
    _inert(ui.page, '#evidencePackViewer')


def test_same_policy_help_modal_and_historical_dream_report(ui, monkeypatch):
    from web import app as wa
    from core import dream_artifacts
    readme_key = str(wa.PROJECT_ROOT / 'README.md')
    monkeypatch.setitem(wa._help_cache, readme_key, '<h1>Help</h1>' + PAYLOADS['events'])
    response = ui.client.get('/help')
    assert response.mimetype == 'text/plain'
    assert response.headers['X-Content-Type-Options'] == 'nosniff'
    ui.page.evaluate('() => openHelpModal()')
    ui.page.wait_for_selector('.help-body h1')
    _inert(ui.page, '.help-body')
    dreams = ui.repo / '.agent/dreams'
    report = dreams / '2026-09-11' / '020304-run'
    report.mkdir(parents=True)
    (report / 'dream_run_summary.md').write_text('# Historical summary\n\n' + AUDIT_PAYLOAD, encoding='utf-8')
    (report / 'list.json').write_text('{"items": []}', encoding='utf-8')
    monkeypatch.setattr(dream_artifacts, 'dreams_root', lambda repo: dreams)
    # Assert the frontend boundary even if a stored/upstream rendered fragment
    # contains raw HTML. The raw report file and actual route are still real.
    monkeypatch.setattr(wa, 'render_dream_report_markdown', lambda source: '<h1>Historical summary</h1>' + AUDIT_PAYLOAD)
    ui.page.evaluate('() => viewDreamRun("2026-09-11", "020304-run")')
    ui.page.wait_for_selector('#dreamMorningReport h1')
    _inert(ui.page, '#dreamMorningReport')
    assert '[Image: omitted]' in ui.page.locator('#dreamMorningReport').inner_text()
    assert AUDIT_PAYLOAD in (report / 'dream_run_summary.md').read_text(encoding='utf-8')
    assert ui.errors == []


def test_rendering_overhead_without_browser_startup(ui, chromium):
    measurements = []
    for label, count in [('small', 1), ('medium', 20), ('large', 200)]:
        source = SAFE * count
        markdown_times = []
        for _ in range(5):
            start = time.perf_counter()
            rendered = markdown.markdown(source, extensions=['fenced_code', 'tables', 'toc'])
            markdown_times.append((time.perf_counter() - start) * 1000)
        result = ui.page.evaluate('''html => {
            const safe = [], baseline = [];
            const target = document.createElement('div');
            document.body.append(target);
            for (let i=0; i<10; i++) {
                let start = performance.now();
                CattusSafeContent.renderHTML(target, html);
                if(i>=3) safe.push(performance.now()-start);
                start = performance.now();
                // Safe fixture ONLY, for a comparable historical insertion baseline.
                target.innerHTML = html;
                if(i>=3) baseline.push(performance.now()-start);
            }
            target.remove();
            return {safe, baseline};
        }''', rendered)
        safe_ms, baseline_ms = statistics.median(result['safe']), statistics.median(result['baseline'])
        measurements.append({'size': label, 'source_bytes': len(source.encode()), 'html_bytes': len(rendered.encode()),
            'markdown_ms': round(statistics.median(markdown_times), 3), 'safe_render_ms': round(safe_ms, 3),
            'baseline_insert_ms': round(baseline_ms, 3), 'overhead_ms': round(safe_ms - baseline_ms, 3)})
    result = {'browser': chromium.version, 'browser_startup_ms': round(chromium.sec_ui1_startup_ms, 3), 'reports': measurements}
    print('SEC_UI1_PERFORMANCE=' + json.dumps(result))
    if os.environ.get('SEC_UI1_PERFORMANCE_FILE'):
        Path(os.environ['SEC_UI1_PERFORMANCE_FILE']).write_text(json.dumps(result, indent=2) + '\n')
    assert measurements[-1]['source_bytes'] < 150_000

def test_deterministic_dom_output_and_private_sanitizer_policy(ui):
    output = ui.page.evaluate('''() => {
        // A different library's configuration must not relax our private instance.
        DOMPurify.setConfig({ADD_TAGS: ['iframe'], ADD_ATTR: ['onclick']});
        const target = document.createElement('div');
        const ok = CattusSafeContent.renderHTML(target,
            '<p style="color:red" onclick="window.__secUi1Executed=true"><strong>safe</strong><a href="javascript:alert(1)">unsafe</a><img alt="&lt;icon&gt;" src="https://blocked.invalid/a"><iframe></iframe></p>');
        return {ok, html: target.innerHTML, text: target.textContent};
    }''')
    assert output == {
        'ok': True,
        'html': '<p><strong>safe</strong><a rel="noopener noreferrer">unsafe</a>[Image: &lt;icon&gt;]</p>',
        'text': 'safeunsafe[Image: <icon>]',
    }
    viewer = _open(ui, '> `'+AUDIT_PAYLOAD+'`\n')
    assert viewer.locator('blockquote code').text_content() == AUDIT_PAYLOAD
    _inert(ui.page, '#evidencePackViewer')
