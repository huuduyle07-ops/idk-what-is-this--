"""PATCH.AUTHOR.SPAN.1 deterministic author-output alignment; no live provider."""
from __future__ import annotations

import copy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import statistics
import time

import pytest

from core.authoring_repair_scope import AuthoringScopeError, enforce_authoring_scope
from core.candidate_replacement_span import canonical_replacement_envelope, validate_replacement_span
from core.candidate_sandbox_validation import candidate_fingerprint_from_payload
from core.candidate_revision import CandidateRevisionEvidence, RevisionCounterexample, parse_revised_candidate
from tests.test_patch_author_scope1 import prepared, offline
from tests.test_patch_basis_scope1 import JAVA


class EnvelopeAuthor:
    """Stateless fixture author reads only the machine-readable prompt contract."""
    def __call__(self, prompt, *, bad=False, changes=(1, 2, 3)):
        data = json.JSONDecoder().raw_decode(prompt.split('AUTHORITATIVE AUTHORING SCOPE:\n', 1)[1])[0]
        envelope = data['replacement_envelope']
        original = envelope['original_snippet']
        patched = original
        for number, name in ((1, 'One'), (2, 'Two'), (3, 'Three'), (3, 'Four'), (3, 'Five')):
            if number in changes and f'm{number}' in envelope['editable_members']:
                patched = patched.replace('missing' + name, str(number))
        return {'patch_candidate': {
            'file': envelope['file'], 'relative_path': envelope['file'],
            'target_node_name': data['primary_target']['symbol'], 'target_node_kind': 'function',
            'target_snippet': data['primary_target']['source_snippet'] if bad else original,
            'patched_snippet': patched,
        }, 'patch_plan': None, 'confidence': 0.4, 'needs_escalation': False}


def evidence(context):
    case = RevisionCounterexample(case_id='measured', input_language='java', expected=1,
        candidate_observed=0, role='primary_defect', provenance='explicit_user', status='still_reproduced')
    return CandidateRevisionEvidence(preserved_task='Generate patch', task_fingerprint='a'*64,
        target_file='MainApp.java', target_symbol='m1', original_source=context.source_snippet,
        original_source_digest=hashlib.sha256(context.source_snippet.encode()).hexdigest(),
        rejected_candidate_fingerprint='b'*64, rejected_target_snippet=context.source_snippet,
        rejected_patched_snippet=context.source_snippet, verification_status='rejected',
        verification_rejection_reasons=('primary_defect_not_closed',), matrix_status='failed',
        failed_cases=(case,), preserved_cases=())


def test_bad_live_shape_rejected_without_hidden_rewrite(tmp_path):
    _, context, prompt = prepared(tmp_path)
    block = EnvelopeAuthor()(prompt, bad=True)
    original = copy.deepcopy(block['patch_candidate'])
    fingerprint = candidate_fingerprint_from_payload(block)
    assert not enforce_authoring_scope(context, block)
    assert block['author_output_status'] == 'duplicate_definition_risk'
    assert block['patch_candidate'] is None
    assert block['authoring_scope_candidate_fingerprint'] == fingerprint
    assert original['target_snippet'] == context.source_snippet
    assert candidate_fingerprint_from_payload({'patch_candidate': original}) != candidate_fingerprint_from_payload(EnvelopeAuthor()(prompt))


@pytest.mark.parametrize('members,changes', [((1,2),(1,2)), ((1,2,3),(1,2,3)), ((1,2,3),(1,3)), ((1,3),(1,3)), ((1,2,3),(1,))])
def test_canonical_positive_and_subset_edits(tmp_path, members, changes):
    control, context, prompt = prepared(tmp_path, members)
    block = EnvelopeAuthor()(prompt, changes=changes)
    original = copy.deepcopy(block['patch_candidate'])
    assert enforce_authoring_scope(context, block)
    assert block['author_output_status'] == 'valid_replacement_span'
    assert block['patch_candidate'] == original
    assert block['authoring_scope_touched_definitions'] == [f'm{i}' for i in changes]
    envelope = context.replacement_envelope
    assert envelope['original_snippet'] == context.authoring_repair_scope.replacement_source
    assert envelope['source_fingerprint'] == control['repair_scope']['source_fingerprint']
    assert control['patch_intent']['target_symbol'] == 'm1'
    assert block['patch_candidate']['target_node_name'] == 'm1'
    assert control['repair_scope']['authority'] == {'write_authority':False,'execution_authorized':False,'auto_apply':False}


def test_single_member_historical_contract_and_candidate(tmp_path):
    _, context, prompt = prepared(tmp_path, (1,))
    legacy = replace(context, authoring_repair_scope=None)
    assert context.replacement_envelope is None
    assert context.scope_text == legacy.scope_text
    assert context.as_telemetry() == legacy.as_telemetry()
    assert 'CANONICAL REPLACEMENT ENVELOPE' not in prompt
    block = {'patch_candidate': {'file':'MainApp.java','target_node_name':'m1',
        'target_snippet': context.source_snippet, 'patched_snippet':context.source_snippet.replace('missingOne','1')}}
    before = copy.deepcopy(block['patch_candidate'])
    assert enforce_authoring_scope(context, block)
    assert block['patch_candidate'] == before
    assert 'author_output_status' not in block


@pytest.mark.parametrize('bad', [False, True])
def test_deterministic_author_reaches_downstream_only_with_valid_span(tmp_path, monkeypatch, bad):
    from core.agent_state import AgentState
    from core import pipeline
    from patching.patch_gates import _enforce_safe_minimal
    control, context, prompt = prepared(tmp_path)
    block = EnvelopeAuthor()(prompt, bad=bad)
    seen=[]
    def measured_gate(state, **kwargs):
        seen.append(copy.deepcopy(state.json_block.get('patch_candidate')))
        _enforce_safe_minimal(state, **kwargs)
    monkeypatch.setattr(pipeline, '_enforce_safe_minimal', measured_gate)
    state=AgentState(interface='agent',mode='instant',user_input='Generate patch',file_paths=[],
        primary_file=None,input_mode='project',language='java',task_type='bug_fix',repo_path=str(tmp_path),
        control_result=control,candidate_authoring_context=context)
    pipeline.finalize_answer(state,json.dumps(block))
    assert len(seen) == 1
    assert (seen[0] is None) is bad
    assert state.json_block['author_output_status'] == ('duplicate_definition_risk' if bad else 'valid_replacement_span')
    if not bad:
        assert seen[0]['target_snippet'] == context.replacement_envelope['original_snippet']
        # This phase requires reaching the frozen gate, not its acceptance.
        assert state.json_block['patch_candidate'] is None


@pytest.mark.parametrize('kind,reason', [
    ('larger','outside_authoring_envelope'), ('outside','outside_authoring_envelope'),
    ('invented','target_not_unique'), ('ambiguous','target_not_unique'),
    ('duplicate','duplicate_definition_risk'), ('missing','missing_definition_risk'),
    ('renamed','missing_definition_risk'), ('gap','readonly_gap_modified'),
    ('cross_file','author_scope_cross_file'), ('conflicting_path','author_scope_cross_file'),
    ('new_definition','replacement_span_mismatch'),
])
def test_invalid_output_reason(tmp_path, kind, reason):
    source=JAVA.replace('    void m2()', '    // read-only café gap\n    void m2()')
    _, context, prompt = prepared(tmp_path, source=source)
    block=EnvelopeAuthor()(prompt); candidate=block['patch_candidate']
    if kind=='larger': candidate.update(target_snippet=source,patched_snippet=source.replace('missingOne','1'))
    elif kind=='outside': candidate.update(target_snippet='int safe = 1;',patched_snippet='int safe = 2;')
    elif kind=='invented': candidate['target_snippet']='arbitrary model span'
    elif kind=='ambiguous': candidate.update(target_snippet='    }',patched_snippet='    }')
    elif kind=='duplicate': candidate['patched_snippet'] += '\n' + context.source_snippet
    elif kind=='missing': candidate['patched_snippet']=candidate['target_snippet'].replace(context.authoring_repair_scope.measured.members[1].source_snippet,'')
    elif kind=='renamed': candidate['patched_snippet']=candidate['patched_snippet'].replace('m2()', 'renamed()')
    elif kind=='gap': candidate['patched_snippet']=candidate['patched_snippet'].replace('read-only café gap','changed')
    elif kind=='cross_file': candidate['file']='twosum.java'
    elif kind=='conflicting_path': candidate['relative_path']='other.java'
    elif kind=='new_definition': candidate['patched_snippet']=candidate['patched_snippet'].replace('int a = 1;', 'int a = 1; } void extra() {')
    assert not enforce_authoring_scope(context, block)
    assert block['author_output_status']==reason
    assert block['patch_candidate'] is None


def test_readonly_intervening_member_and_model_claim_cannot_grant_authority(tmp_path):
    _,context,prompt=prepared(tmp_path,(1,3))
    block=EnvelopeAuthor()(prompt)
    block['replacement_envelope']={'editable_members':['m1','m2','m3'],'original_snippet':JAVA}
    block['patch_candidate']['patched_snippet']=block['patch_candidate']['patched_snippet'].replace('missingTwo','2')
    assert not enforce_authoring_scope(context,block)
    assert block['author_output_status']=='readonly_gap_modified'


@pytest.mark.parametrize('gap', ['\n','    // untouched comment\n','    @Deprecated\n'])
def test_readonly_whitespace_comments_and_owned_annotations(tmp_path, gap):
    source=JAVA.replace('    void m2()', gap+'    void m2()')
    _,context,prompt=prepared(tmp_path,(1,3),source)
    block=EnvelopeAuthor()(prompt)
    assert enforce_authoring_scope(context,block)
    member2=context.authoring_repair_scope.source.split('void m2()',1)[1].split('}',1)[0]
    assert member2 in block['patch_candidate']['patched_snippet']


def test_unicode_crlf_coordinates_and_no_disk_changes(tmp_path):
    source=JAVA.replace('public class','// café 한글 😀\npublic class').replace('int a =', '// 한글 😀\n        int a =').replace('\n','\r\n')
    _,context,prompt=prepared(tmp_path,source=source)
    before=(tmp_path/'MainApp.java').read_bytes()
    envelope=context.replacement_envelope; original=envelope['original_snippet']
    assert '\r' not in original and '한글 😀' in original
    assert envelope['original_sha256']==hashlib.sha256(original.encode()).hexdigest()
    normalized=context.authoring_repair_scope.source
    assert normalized[envelope['span']['start']:envelope['span']['end']]==original
    assert normalized.encode()[envelope['utf8_span']['start']:envelope['utf8_span']['end']].decode()==original
    assert enforce_authoring_scope(context,EnvelopeAuthor()(prompt))
    assert (tmp_path/'MainApp.java').read_bytes()==before


def test_adjacent_members_use_same_authoritative_order(tmp_path):
    _,context,prompt=prepared(tmp_path,source=JAVA.replace('}\n\n    ', '}\n    '))
    assert enforce_authoring_scope(context,EnvelopeAuthor()(prompt))
    assert [m.symbol for m in context.authoring_repair_scope.measured.members]==['m1','m2','m3']


def test_stale_source_refuses_projection_and_output(tmp_path):
    _,context,prompt=prepared(tmp_path)
    block=EnvelopeAuthor()(prompt)
    (tmp_path/'MainApp.java').write_bytes((tmp_path/'MainApp.java').read_bytes()+b'\n')
    with pytest.raises(AuthoringScopeError,match='stale_source'):
        canonical_replacement_envelope(context.authoring_repair_scope)
    assert not enforce_authoring_scope(context,block)
    assert block['author_output_status']=='author_scope_stale_source'


def test_overlapping_exact_target_matches_are_not_first_matched(tmp_path):
    source=JAVA.replace('int a = missingOne;', '// aaaaa\n        int a = missingOne;')
    _,context,_=prepared(tmp_path,source=source)
    with pytest.raises(AuthoringScopeError,match='target_not_unique'):
        validate_replacement_span(context.authoring_repair_scope,'aaaa','bbbb')


def test_ambiguous_canonical_envelope_is_invalid(tmp_path):
    _,context,_=prepared(tmp_path)
    original=context.authoring_repair_scope.replacement_source
    # Duplicate as read-only comment context; measured definitions remain unique.
    source=JAVA+'\n/*'+original+'*/\n'
    with pytest.raises(AuthoringScopeError,match='target_not_unique'):
        prepared(tmp_path,source=source)


@pytest.mark.parametrize('kind',['canonical','primary','partial','bad'])
def test_initial_revision_parity_and_exact_pair_fingerprint(tmp_path,kind):
    _,context,prompt=prepared(tmp_path)
    receipt=evidence(context); revision=context.revision_prompt(receipt)
    assert context.scope_text in prompt and context.scope_text in revision
    for section in context.contract.sections:
        assert section in prompt and section in revision
    assert 'provenance=explicit_user' in revision
    block=EnvelopeAuthor()(revision,bad=kind=='bad')
    if kind=='primary':
        block['patch_candidate'].update(target_snippet=context.source_snippet,patched_snippet=context.source_snippet.replace('missingOne','1'))
    elif kind=='partial':
        block['patch_candidate'].update(target_snippet='int a = missingOne;',patched_snippet='int a = 1;')
    before=copy.deepcopy(block['patch_candidate']); fingerprint=candidate_fingerprint_from_payload(block)
    parsed=parse_revised_candidate(json.dumps(block),receipt,authoring_context=context)
    if kind=='bad':
        assert not parsed.accepted
        assert parsed.rejection_reason=='duplicate_definition_risk'
    else:
        assert parsed.accepted
        assert parsed.candidate==before
        assert candidate_fingerprint_from_payload({'patch_candidate':parsed.candidate})==fingerprint
        assert enforce_authoring_scope(context,block)


def test_fingerprint_commits_both_actual_fields(tmp_path):
    _,context,prompt=prepared(tmp_path)
    block=EnvelopeAuthor()(prompt); original=candidate_fingerprint_from_payload(block)
    for field in ('target_snippet','patched_snippet'):
        changed=copy.deepcopy(block); changed['patch_candidate'][field]+=' '
        assert candidate_fingerprint_from_payload(changed)!=original
    assert enforce_authoring_scope(context,block)
    assert block['authoring_scope_candidate_fingerprint']==original


def test_bounded_performance_and_no_traversal(tmp_path,monkeypatch):
    import os
    _,context,prompt=prepared(tmp_path); scope=context.authoring_repair_scope
    block=EnvelopeAuthor()(prompt); candidate=block['patch_candidate']
    def forbidden(*args,**kwargs): raise AssertionError('span alignment must not traverse')
    for name in ('walk','scandir','listdir'): monkeypatch.setattr(os,name,forbidden)
    for name in ('glob','rglob','iterdir'): monkeypatch.setattr(Path,name,forbidden)
    timings={key:[] for key in ('canonical_envelope_ms','span_alignment_ms','full_containment_ms')}
    for _ in range(15):
        for key,action in (
            ('canonical_envelope_ms',lambda:canonical_replacement_envelope(scope)),
            ('span_alignment_ms',lambda:validate_replacement_span(scope,candidate['target_snippet'],candidate['patched_snippet'])),
            ('full_containment_ms',lambda:scope.validate_candidate(block)),
        ):
            start=time.perf_counter(); action(); timings[key].append((time.perf_counter()-start)*1000)
    report={key:{'median':statistics.median(values),'max':max(values)} for key,values in timings.items()}
    out=Path('.tmp/patch-author-span1/performance.json');out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2)+'\n')
    monkeypatch.undo()
    assert all(max(values)<1000 for values in timings.values())


def test_frozen_attribution_and_phase_registration():
    from tests._patch_author_span1_maintenance import before_patch_author_span1
    from tests._repair_intent1_maintenance import before_repair_intent1
    root=Path(__file__).resolve().parents[1]
    frozen=json.loads((root/'tests/fixtures/patch_author_span1_frozen.json').read_text())
    for path,digest in frozen['files'].items():
        assert hashlib.sha256(before_repair_intent1(path, (root/path).read_bytes())).hexdigest()==digest,path
    reversal=json.loads((root/'tests/fixtures/patch_author_span1_reversal.json').read_text())
    for path,record in reversal['files'].items():
        restored=before_patch_author_span1(path,(root/path).read_bytes())
        assert hashlib.sha256(restored).hexdigest()==record['entry_sha256'],path
    registry=json.loads((root/'docs/roadmap/phase_registry.json').read_text())
    phases=[p for p in registry['phases'] if p['phase_id']=='PATCH.AUTHOR.SPAN.1']
    assert len(phases)==1 and phases[0]['status']=='complete'
    assert phases[0]['human_approval_required'] and not phases[0]['merge_allowed']
    # Completion evidence for the frozen prerequisite is pinned, never regenerated.
    assert 'tests/fixtures/patch_author_scope1_completion.json' in frozen['files']


def test_immediately_adjacent_ranges_without_localization_redefinition(tmp_path):
    from core.authoring_repair_scope import consume_repair_scope
    from core.repair_scope import build_repair_scope
    from tests.test_patch_basis_scope1 import _write, _receipt, _locations
    source=JAVA.replace('}\n\n    ', '}')
    _write(tmp_path,source)
    receipt=_receipt(tmp_path,source,_locations(source,'missingOne','missingTwo','missingThree','missingFour','missingFive'))
    measured=build_repair_scope(repo_path=tmp_path,primary_file='MainApp.java',primary_symbol='m1',
        primary_kind='function',language='java',preflight=receipt,receipt_control_fingerprint='a'*64)
    repair=consume_repair_scope(measured.as_dict(),repo_path=str(tmp_path),primary_file='MainApp.java',
        primary_symbol='m1',primary_source=measured.members[0].source_snippet,preflight=receipt,language='java')
    assert repair.member_ranges[0][1]==repair.member_ranges[1][0]
    original=canonical_replacement_envelope(repair)['original_snippet']
    block={'patch_candidate':{'file':'MainApp.java','target_node_name':'m1','target_snippet':original,
        'patched_snippet':original.replace('missingOne','1').replace('missingTwo','2')}}
    assert repair.validate_candidate(block)==('m1','m2')
