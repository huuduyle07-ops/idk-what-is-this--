"""PATCH.AUTHOR.SCOPE.1 contract expressibility; no provider or network."""
from __future__ import annotations

import copy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import socket
import statistics
import time

import pytest

from core.authoring_repair_scope import AuthoringScopeError, consume_repair_scope, enforce_authoring_scope
from core.control_engine import authoring_context_for_control_result, build_control_prompt
from core.patch_authoring_contract import render_patch_authoring_contract
from core.repair_scope import build_repair_scope
from tests.test_patch_basis_scope1 import JAVA, _write, _receipt, _locations, _control_fingerprint


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError('Focused author-scope tests must not call a live provider or network')
    monkeypatch.setattr(socket.socket, 'connect', refuse)
    monkeypatch.setattr(socket, 'create_connection', refuse)
    import core.pipeline as pipeline
    monkeypatch.setattr(pipeline, 'run_gemini_request', refuse)
    monkeypatch.setattr(pipeline, 'run_deepseek_review', refuse)


def prepared(tmp_path, members=(1, 2, 3), source=JAVA):
    repo = _write(tmp_path, source)
    control = {
        'repo_path': str(repo), 'query': 'fix compiler errors',
        'top_hypothesis': {'symbol': 'MainApp.java::m1', 'likely_issue': 'compile_error'},
        'hypotheses': [{'symbol': 'MainApp.java::m1', 'likely_issue': 'compile_error'}],
        'related_snippets': [{'file': 'MainApp.java', 'symbol': 'readonly', 'snippet': source}],
        'patch_style': 'safe_minimal',
    }
    needles = {1: ['missingOne'], 2: ['missingTwo'], 3: ['missingThree', 'missingFour', 'missingFive']}
    control['preflight_validation'] = _receipt(repo, source, _locations(source, *[n for m in members for n in needles[m]]), control_fingerprint=_control_fingerprint(control))
    prompt = build_control_prompt(control, 'Generate patch', repo_path=str(repo))
    context = authoring_context_for_control_result(control, repo_path=str(repo))
    return control, context, prompt


class StatelessRepairAuthor:
    """Expressibility only. Fixed substitutions are test fixture data."""
    def __call__(self, prompt):
        marker = 'AUTHORITATIVE AUTHORING SCOPE:\n'
        data = json.JSONDecoder().raw_decode(prompt.split(marker, 1)[1])[0]
        repair = data.get('authoring_repair_scope')
        if repair is None or '[MEASURED REPAIR-SET AUTHORING CONTRACT]' not in prompt:
            return {'patch_candidate': None, 'needs_escalation': True}
        source = repair['replacement_source']
        patched = source
        substitutions = {'missingOne': '1', 'missingTwo': '2', 'missingThree': '3', 'missingFour': '4', 'missingFive': '5'}
        for member in repair['members']:
            exact = member['source_snippet']
            replacement = exact
            for old, new in substitutions.items():
                replacement = replacement.replace(old, new)
            patched = patched.replace(exact, replacement, 1)
        return {'patch_candidate': {'file': repair['file'], 'relative_path': repair['file'],
                'target_node_name': repair['primary_symbol'], 'target_node_kind': 'function',
                'target_snippet': source, 'patched_snippet': patched},
                'patch_plan': None, 'confidence': 0.4, 'needs_escalation': False}


def test_primary_red_green(tmp_path):
    control, context, prompt = prepared(tmp_path)
    legacy = render_patch_authoring_contract(style='safe_minimal', source_snippet=context.source_snippet)
    legacy_context = replace(context, contract=legacy, authoring_repair_scope=None)
    stub = StatelessRepairAuthor()
    assert stub(legacy.text + '\n' + legacy_context.scope_text)['patch_candidate'] is None
    candidate = stub(prompt)
    assert enforce_authoring_scope(context, candidate)
    assert candidate['authoring_scope_touched_definitions'] == ['m1', 'm2', 'm3']
    assert len(candidate['authoring_scope_candidate_fingerprint']) == 64
    assert control['patch_intent']['target_symbol'] == 'm1'
    assert control['repair_scope']['authority'] == {'write_authority': False, 'execution_authorized': False, 'auto_apply': False}
    assert '[USER]\nGenerate patch' in prompt
    assert json.dumps(control['preflight_validation'], ensure_ascii=False, indent=2) in prompt


@pytest.mark.parametrize('members', [(1, 2), (1, 2, 3), (1, 3)])
def test_exact_sources_diagnostics_order_and_admission(tmp_path, members):
    control, context, prompt = prepared(tmp_path, members)
    scope = context.authoring_repair_scope.as_dict()
    assert [m['symbol'] for m in scope['members']] == [f'm{i}' for i in members]
    for authored, measured in zip(scope['members'], control['repair_scope']['members']):
        assert authored['source_snippet'] == measured['source_snippet']
        assert authored['diagnostics'] == measured['diagnostics']
        assert authored['bindings']['target_symbol'] == authored['symbol']
    assert context.scope_text == context.scope_text
    assert enforce_authoring_scope(context, StatelessRepairAuthor()(prompt))


def test_one_member_and_absent_scope_keep_live3_contract(tmp_path):
    control, context, prompt = prepared(tmp_path, (1,))
    legacy = replace(context, authoring_repair_scope=None)
    assert context.contract == render_patch_authoring_contract(style='safe_minimal', source_snippet=context.source_snippet)
    assert context.scope_text == legacy.scope_text
    assert context.as_telemetry() == legacy.as_telemetry()
    assert '[MEASURED REPAIR-SET AUTHORING CONTRACT]' not in prompt
    control.pop('repair_scope')
    assert authoring_context_for_control_result(control, repo_path=str(tmp_path)).contract == legacy.contract


@pytest.mark.parametrize('target', ['missingTwo', 'helper', 'unrelated'])
def test_visible_outside_member_is_not_editable(tmp_path, target):
    _, context, prompt = prepared(tmp_path, (1, 3))
    block = StatelessRepairAuthor()(prompt)
    candidate = block['patch_candidate']
    if target == 'missingTwo':
        candidate['patched_snippet'] = candidate['target_snippet'].replace(target, '2')
    else:
        candidate['target_snippet'] = JAVA
        candidate['patched_snippet'] = JAVA.replace(target, 'renamed')
    assert not enforce_authoring_scope(context, block)
    assert block['authoring_scope_status'] == 'authoring_scope_violation'
    assert block['patch_candidate'] is None


@pytest.mark.parametrize('path', ['Twosum.java', '../MainApp.java', 'other/MainApp.java'])
def test_cross_file_rejected_before_minimality(tmp_path, path):
    _, context, prompt = prepared(tmp_path)
    block = StatelessRepairAuthor()(prompt)
    block['patch_candidate']['file'] = path
    assert not enforce_authoring_scope(context, block)
    assert block['authoring_scope_status'] == 'author_scope_cross_file'


@pytest.mark.parametrize('alter,reason', [
    (lambda d: d.update(status='repair_scope_incomplete'), 'author_scope_incomplete'),
    (lambda d: d.update(evidence_fingerprint='f'*64), 'author_scope_receipt_mismatch'),
    (lambda d: d.update(control_fingerprint='f'*64), 'author_scope_receipt_mismatch'),
    (lambda d: d.update(source_fingerprint='f'*64), 'author_scope_receipt_mismatch'),
    (lambda d: d.update(repository_id='different'), 'author_scope_receipt_mismatch'),
    (lambda d: d['members'][1].update(file='Twosum.java'), 'author_scope_cross_file'),
    (lambda d: d['members'].pop(), 'author_scope_incomplete'),
    (lambda d: d['members'].extend([d['members'][0]]*7), 'author_scope_budget_exceeded'),
    (lambda d: d['members'][0].update(source_snippet='x'*16385), 'author_scope_budget_exceeded'),
    (lambda d: d['members'].insert(1, d['members'][0]), 'author_scope_overlapping_members'),
    (lambda d: d['members'][1].update(symbol='m1'), 'author_scope_ambiguous'),
])
def test_malformed_repair_scope_fails_closed(tmp_path, alter, reason):
    control, _, _ = prepared(tmp_path)
    alter(control['repair_scope'])
    with pytest.raises(AuthoringScopeError, match=reason):
        authoring_context_for_control_result(control, repo_path=str(tmp_path))


def test_stale_source_is_not_combined_with_old_evidence(tmp_path):
    control, context, prompt = prepared(tmp_path)
    (tmp_path/'MainApp.java').write_text(JAVA.replace('missingOne', 'changed'))
    for action in (lambda: context.scope_text, lambda: context.authoring_repair_scope.validate_candidate(StatelessRepairAuthor()(prompt)),
                   lambda: authoring_context_for_control_result(control, repo_path=str(tmp_path))):
        with pytest.raises(AuthoringScopeError, match='stale_source'):
            action()


def test_changed_receipt_and_wrong_repository_refused(tmp_path):
    control, context, _ = prepared(tmp_path)
    control['preflight_validation']['receipt_fingerprint'] = 'f'*64
    with pytest.raises(AuthoringScopeError, match='receipt_mismatch'):
        context.authoring_repair_scope.assert_current(control['preflight_validation'])
    other = tmp_path/'other'; other.mkdir(); (other/'MainApp.java').write_bytes((tmp_path/'MainApp.java').read_bytes())
    with pytest.raises(AuthoringScopeError, match='repository_mismatch'):
        replace(context.authoring_repair_scope, repo_path=str(other)).assert_current()


def test_overlapping_existing_replace_operations_rejected(tmp_path):
    _, context, prompt = prepared(tmp_path)
    candidate = StatelessRepairAuthor()(prompt)['patch_candidate']
    op = {**candidate, 'op': 'replace_snippet'}
    with pytest.raises(AuthoringScopeError, match='overlapping_operations'):
        context.authoring_repair_scope.validate_candidate({'patch_plan': [op, op]})


def test_subset_coverage_and_no_prose_completeness(tmp_path):
    _, context, _ = prepared(tmp_path)
    member = context.authoring_repair_scope.measured.members[0]
    block = {'summary': 'this fixes all errors', 'patch_candidate': {'file': member.file,
             'target_node_name': 'm1', 'target_snippet': member.source_snippet,
             'patched_snippet': member.source_snippet.replace('missingOne','1')}}
    assert enforce_authoring_scope(context, block)
    assert block['authoring_scope_touched_definitions'] == ['m1']
    assert 'complete' not in block and 'verified' not in block


def test_extra_definition_inside_member_is_refused(tmp_path):
    _, context, prompt = prepared(tmp_path)
    block = StatelessRepairAuthor()(prompt)
    block['patch_candidate']['patched_snippet'] = block['patch_candidate']['target_snippet'].replace('int a = missingOne;', 'int a = 1; } void extra() {')
    assert not enforce_authoring_scope(context, block)
    assert block['authoring_scope_status'] == 'author_scope_definition_change'


def test_member_local_bindings_imports_and_fields_stay_separate(tmp_path):
    source = 'from record import make\n\ndef m1(x):\n    first = missingOne\n    return make(x)\n\ndef m2(x):\n    second = missingTwo\n    return make(x)\n'
    (tmp_path/'subject.py').write_text(source)
    (tmp_path/'record.py').write_text('from dataclasses import dataclass\n@dataclass(frozen=True)\nclass Result:\n    value: int\ndef make(x) -> Result:\n    return Result(x)\n')
    from core.repository_identity import derive_repository_id
    locations = [{**d, 'file': 'subject.py', 'language': 'python'} for d in _locations(source,'missingOne','missingTwo')]
    receipt = {'ran': True, 'ok': False, 'measured': True, 'category':'build_error',
               'evidence_source':'PREFLIGHT.REQUEST.1','evidence_kind':'compile_evidence',
               'receipt_fingerprint':'b'*64,'control_sha256':'a'*64,'repository_id':derive_repository_id(tmp_path),
               'source_fingerprints':[{'path':'subject.py','sha256':hashlib.sha256((tmp_path/'subject.py').read_bytes()).hexdigest()}],
               'locations':locations,'targets':[{'path':'subject.py','errors':2}]}
    scope = build_repair_scope(repo_path=tmp_path, primary_file='subject.py', primary_symbol='m1', primary_kind='function', language='python',preflight=receipt,receipt_control_fingerprint='a'*64)
    repair = consume_repair_scope(scope.as_dict(),repo_path=str(tmp_path),primary_file='subject.py',primary_symbol='m1',primary_source=scope.members[0].source_snippet,preflight=receipt,language='python')
    members = repair.as_dict()['members']
    bindings = [{b['name']: b for b in m['bindings']['available_baseline_bindings']} for m in members]
    assert bindings[0]['x']['kind'] == bindings[1]['x']['kind'] == 'parameter'
    assert 'first' in bindings[0] and 'first' not in bindings[1]
    assert 'second' in bindings[1] and 'second' not in bindings[0]
    for names in bindings:
        assert names['make']['kind'] == 'repository_local_direct_import'
        assert names['make']['result']['readable_declared_fields'] == ['value']


def test_initial_revision_boundary_and_wire_parity(tmp_path):
    from core.candidate_revision import CandidateRevisionEvidence, RevisionCounterexample, parse_revised_candidate
    _, context, prompt = prepared(tmp_path)
    case = RevisionCounterexample(case_id='measured', input_language='java', expected=1, candidate_observed=0, role='primary_defect', provenance='explicit_user', status='still_reproduced')
    evidence = CandidateRevisionEvidence(preserved_task='Generate patch',task_fingerprint='a'*64,target_file='MainApp.java',target_symbol='m1',original_source=context.source_snippet,original_source_digest=hashlib.sha256(context.source_snippet.encode()).hexdigest(),rejected_candidate_fingerprint='b'*64,rejected_target_snippet=context.source_snippet,rejected_patched_snippet=context.source_snippet,verification_status='rejected',verification_rejection_reasons=('primary_defect_not_closed',),matrix_status='failed',failed_cases=(case,),preserved_cases=())
    revision = context.revision_prompt(evidence)
    assert context.scope_text in prompt and context.scope_text in revision
    for section in context.contract.sections:
        assert section in prompt and section in revision
    block = StatelessRepairAuthor()(revision)
    parsed = parse_revised_candidate(json.dumps(block), evidence, authoring_context=context)
    assert parsed.accepted
    assert context.authoring_repair_scope.validate_candidate({'patch_candidate':parsed.candidate}) == ('m1','m2','m3')
    (tmp_path/'MainApp.java').write_text(JAVA+'\n')
    with pytest.raises(AuthoringScopeError, match='stale_source'):
        context.revision_prompt(evidence)


def test_performance_without_model_latency(tmp_path):
    control, context, prompt = prepared(tmp_path)
    block = StatelessRepairAuthor()(prompt)
    times = {key:[] for key in ('construction_ms','render_ms','full_prompt_ms','validation_ms')}
    for _ in range(15):
        for key, action in (
            ('construction_ms',lambda:authoring_context_for_control_result(control,repo_path=str(tmp_path))),
            ('render_ms',lambda:context.contract.text + context.scope_text),
            ('full_prompt_ms',lambda:build_control_prompt(copy.deepcopy(control),'Generate patch',repo_path=str(tmp_path))),
            ('validation_ms',lambda:context.authoring_repair_scope.validate_candidate(block)),
        ):
            start=time.perf_counter();action();times[key].append((time.perf_counter()-start)*1000)
    output={key:{'median':statistics.median(values),'max':max(values)} for key,values in times.items()}
    out=Path('.tmp/patch-author-scope1/performance.json');out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(output,indent=2)+'\n')
    assert all(max(values)<1000 for values in times.values())

def test_member_selection_is_not_recomputed_and_no_traversal(tmp_path, monkeypatch):
    import os
    import core.control_engine as engine
    control, context, _ = prepared(tmp_path)
    def forbidden(*args, **kwargs):
        raise AssertionError('Authoring must consume measured membership without traversal')
    with monkeypatch.context() as patch:
        patch.setattr(engine, 'build_repair_scope', forbidden)
        for name in ('walk', 'scandir', 'listdir'):
            patch.setattr(os, name, forbidden)
        for name in ('glob', 'rglob', 'iterdir'):
            patch.setattr(Path, name, forbidden)
        consumed = authoring_context_for_control_result(control, repo_path=str(tmp_path))
        assert consumed.scope_text == context.scope_text


def test_model_target_list_cannot_expand_scope(tmp_path):
    _, context, prompt = prepared(tmp_path, (1, 3))
    block = StatelessRepairAuthor()(prompt)
    block['authoring_repair_scope'] = {'members':['m1','m2','m3']}
    block['patch_candidate']['patched_snippet'] = block['patch_candidate']['target_snippet'].replace('missingTwo', '2')
    assert not enforce_authoring_scope(context, block)
    assert block['authoring_scope_status'] == 'authoring_scope_violation'


@pytest.mark.parametrize('symbol', ['a', 'longDescriptiveRepairMethod'])
def test_short_and_long_secondary_symbols_have_same_scope_semantics(tmp_path, symbol):
    _, context, prompt = prepared(tmp_path, source=JAVA.replace('m2()', symbol+'()'))
    assert [m.symbol for m in context.authoring_repair_scope.measured.members] == ['m1',symbol,'m3']
    assert enforce_authoring_scope(context, StatelessRepairAuthor()(prompt))


def test_main_and_sibling_class_never_become_editable(tmp_path):
    source = JAVA.replace('    void helper()', '    public static void main(String[] args) {}\n\n    void helper()')+'\nclass Other {}\n'
    _, context, prompt = prepared(tmp_path, source=source)
    for original, replacement in [('main','renamedMain'),('Other','Extra')]:
        block = StatelessRepairAuthor()(prompt)
        block['patch_candidate']['target_snippet'] = source
        block['patch_candidate']['patched_snippet'] = source.replace(original,replacement)
        assert not enforce_authoring_scope(context, block)


def test_readonly_gap_representation_budget_does_not_truncate(tmp_path):
    source=JAVA.replace('    void m2()', '    // '+('x'*17000)+'\n    void m2()')
    with pytest.raises(AuthoringScopeError, match='author_scope_budget_exceeded'):
        prepared(tmp_path, (1,3), source)


def test_guard_is_before_minimality_in_both_consumers(tmp_path, monkeypatch):
    from core.agent_state import AgentState
    from core import pipeline
    from core.control_engine import enforce_control_grounding_on_payload
    control, context, prompt = prepared(tmp_path, (1,3))
    block = StatelessRepairAuthor()(prompt)
    block['patch_candidate']['patched_snippet'] = block['patch_candidate']['target_snippet'].replace('missingTwo','2')
    state=AgentState(interface='agent',mode='instant',user_input='Generate patch',file_paths=[],primary_file=None,input_mode='project',language='java',task_type='bug_fix',repo_path=str(tmp_path),control_result=control,candidate_authoring_context=context)
    seen=[]
    def minimal(state, **kwargs):
        seen.append(state.json_block.get('patch_candidate'))
    monkeypatch.setattr(pipeline,'_enforce_safe_minimal',minimal)
    pipeline.finalize_answer(state,json.dumps(block))
    assert seen==[None]
    assert state.json_block['authoring_scope_status']=='authoring_scope_violation'
    direct=copy.deepcopy(block)
    enforce_control_grounding_on_payload(control,direct)
    assert direct['patch_candidate'] is None
    assert direct['authoring_scope_status']=='authoring_scope_violation'


def test_real_minimality_gate_is_still_free_to_reject(tmp_path):
    from core.agent_state import AgentState
    from patching.patch_gates import _enforce_safe_minimal
    _, context, prompt = prepared(tmp_path)
    block=StatelessRepairAuthor()(prompt)
    assert enforce_authoring_scope(context,block)
    state=AgentState(interface='agent',mode='instant',user_input='Generate patch',file_paths=[],primary_file=None,input_mode='project',language='java',task_type='bug_fix',json_block=block)
    _enforce_safe_minimal(state)
    # This fixture measures the frozen gate, rather than weakening its cap.
    assert state.json_block['patch_candidate'] is None
    assert state.json_block['needs_escalation'] is True


def test_frozen_attribution_and_registry():
    from tests._patch_author_scope1_maintenance import before_patch_author_scope1
    from tests._repair_intent1_maintenance import before_repair_intent1
    root=Path(__file__).resolve().parents[1]
    frozen=json.loads((root/'tests/fixtures/patch_author_scope1_frozen.json').read_text())
    for path,digest in frozen['files'].items():
        assert hashlib.sha256(before_repair_intent1(path, (root/path).read_bytes())).hexdigest()==digest,path
    reversal=json.loads((root/'tests/fixtures/patch_author_scope1_reversal.json').read_text())
    for path,record in reversal['files'].items():
        restored=before_patch_author_scope1(path,(root/path).read_bytes())
        assert hashlib.sha256(restored).hexdigest()==record['entry_sha256']
    registry=json.loads((root/'docs/roadmap/phase_registry.json').read_text())
    phases=[p for p in registry['phases'] if p['phase_id']=='PATCH.AUTHOR.SCOPE.1']
    assert len(phases)==1 and phases[0]['status']=='complete'
    assert phases[0]['human_approval_required'] is True
    assert phases[0]['merge_allowed'] is False

def test_crlf_unicode_source_fidelity_without_disk_normalization(tmp_path):
    source=JAVA.replace('int a = missingOne;', '// café — exact source\n        int a = missingOne;').replace('\n','\r\n')
    _, context, prompt=prepared(tmp_path,source=source)
    before=(tmp_path/'MainApp.java').read_bytes()
    assert b'\r\n' in before
    assert '\r' not in context.authoring_repair_scope.replacement_source
    assert 'café — exact source' in context.scope_text
    assert enforce_authoring_scope(context,StatelessRepairAuthor()(prompt))
    assert (tmp_path/'MainApp.java').read_bytes()==before


def test_repeated_render_consumes_the_same_receipt_without_reselection(tmp_path,monkeypatch):
    import core.control_engine as engine
    control, context, first=prepared(tmp_path)
    def forbidden(**kwargs):
        raise AssertionError('An existing measured membership must not be recomputed')
    monkeypatch.setattr(engine,'build_repair_scope',forbidden)
    second=build_control_prompt(control,'Generate patch',repo_path=str(tmp_path))
    assert second==first
    assert context.scope_text in second
