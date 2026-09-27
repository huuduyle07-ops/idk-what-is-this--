"""PATCH.AUTHOR.LIVE.3: stateless prompt contract and frozen real lifecycle."""
from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import json
import statistics
import time
from dataclasses import replace
from pathlib import Path

import pytest

from core import pipeline, control_engine
from core.authoritative_binding_context import build_authoritative_binding_context
from core.behavioral_matrix import (
    build_behavioral_matrix, resolve_matrix_case, ProbeObservation,
)
from core.candidate_authoring_context import CandidateAuthoringContext, MAX_SCOPE_BYTES
from core.candidate_revision import (
    assess_candidate_revision, revision_evidence_is_current, build_revision_prompt,
    MAX_CONCRETE_CASES, MAX_CONCRETE_INPUT_BYTES, MAX_REVISION_CALLS_PER_RUN,
    parse_revised_candidate,
)
from core.control_engine import authoring_context_for_control_result, build_control_prompt
from core.defect_probe import execute_defect_probe
from core.patch_authoring_contract import (
    render_patch_authoring_contract, PATCH_RESPONSE_SCHEMA, patch_output_format_block,
)
from test_patch_minimal_binding_context_live3 import (
    ROOT, TARGET_FILE, TARGET_SYMBOL, TARGET_FUNCTION, TARGET_BODY, CORRECT_BODY,
    _gate, _accepted,
)
from test_patch_minimal_novelty_live import _t6_contract, _t6_lifecycle_state, _t6_behavior_fact

OUT = ROOT / '.tmp/author-live3'
CASE_FIXTURE = json.loads((ROOT/'tests/fixtures/patch_author_live3_round10.json').read_text(encoding='utf-8'))
ROUND10 = json.loads((ROOT/'tests/fixtures/answer_coherence_live1_round10.json').read_text(encoding='utf-8'))


def scope_data(prompt):
    start = prompt.index('AUTHORITATIVE AUTHORING SCOPE:\n') + len('AUTHORITATIVE AUTHORING SCOPE:\n')
    return json.JSONDecoder().raw_decode(prompt[start:])[0]


class StatelessAuthor:
    """Test-only: recognizes information classes, not a model-intelligence claim."""
    def __init__(self, cases):
        self.cases = cases

    def __call__(self, prompt):
        if (PATCH_RESPONSE_SCHEMA not in prompt
                or patch_output_format_block("safe_minimal") not in prompt):
            raise ValueError("missing complete wire schema")
        for field in ('"patch_candidate"', '"target_snippet"', '"patched_snippet"',
                      '"relative_path"', '"target_node_name"', '"confidence"'):
            if field not in prompt:
                raise ValueError('missing wire schema')
        scope = scope_data(prompt)
        bindings = {b['name']: b for b in scope['available_baseline_bindings']}
        if bindings.get('language', {}).get('kind') != 'parameter':
            raise ValueError('missing parameter')
        for name in ('observe_source_indentation', 'assess_indentation_observation'):
            if bindings.get(name, {}).get('kind') != 'repository_local_direct_import':
                raise ValueError('missing callable')
        fields = bindings['assess_indentation_observation'].get('result', {}).get('readable_declared_fields', [])
        if 'value' not in fields:
            raise ValueError('missing field proof')
        for case in self.cases:
            if case['input_text'] not in prompt:
                raise ValueError('missing concrete case')
            if f"input_language={case['input_language']}" not in prompt:
                raise ValueError('missing language')
        return json.dumps({
            'summary': 'Candidate1 contract-stub response', 'issues': [],
            'confidence': 0.4, 'needs_escalation': False,
            'patch_candidate': {
                'file': TARGET_FILE, 'relative_path': TARGET_FILE,
                'target_node_name': TARGET_SYMBOL, 'target_node_kind': 'function',
                'target_snippet': TARGET_BODY.rstrip('\n'),
                'patched_snippet': CORRECT_BODY.rstrip('\n'),
            },
        })


@pytest.fixture(scope='module')
def replay():
    patch = pytest.MonkeyPatch()
    patch.setattr(pipeline, 'AUTO_PATCH_ENABLED', False)
    def refuse(*args, **kwargs):
        pytest.fail('real provider forbidden in LIVE.3')
    patch.setattr(pipeline, 'run_gemini_request', refuse)
    patch.setattr(pipeline, 'run_deepseek_review', refuse)
    contract = _t6_contract()
    pre = execute_defect_probe(contract, repo_path=ROOT)
    assert pre.probe_result == 'reproduced'
    before = (ROOT / TARGET_FILE).read_bytes()
    state = _t6_lifecycle_state(TARGET_FUNCTION, (contract, pre))
    # Keep Round 10's exact body-only Candidate0 bytes and author envelope.
    # CONTROL quotes the same authoritative body rather than the full signature.
    state.control_result['patch_intent']['source_snippet'] = TARGET_BODY.rstrip('\n')
    pipeline.finalize_answer(state, ROUND10['candidate0_response'])
    state.json_block['patch_basis'] = 'grounded_defect'
    state.json_block['target_source_grounded'] = True
    assert state.json_block.get('candidate_novelty_admitted') is not False
    assert state.json_block['patch_candidate'] is not None
    authoring = state.candidate_authoring_context
    # As in LIVE.2, isolate prompt rendering from target-handoff recomputation.
    # The real gate/probe/verification path below remains fully active.
    with pytest.MonkeyPatch.context() as prompt_patch:
        prompt_patch.setattr(control_engine, 'refresh_control_safety', lambda result: result)
        control = dict(state.control_result, patch_candidate_state={
            'eligible_for_patch_safety_handoff': True, 'defect_grounded': True,
            'defect_established': True, 'patch_basis': 'grounded_defect'})
        initial = build_control_prompt(control, state.user_input,
                                       repo_path=str(ROOT), authoring_context=authoring)
    captured = {}
    real_assess = pipeline.assess_candidate_revision
    def assess(data):
        result = real_assess(data)
        captured['assessment_inputs'] = copy.deepcopy(data)
        captured['evidence'] = result.evidence
        return result
    patch.setattr(pipeline, 'assess_candidate_revision', assess)
    def adapter(active, prompt):
        captured['prompt'] = prompt
        captured['candidate0'] = copy.deepcopy(active.json_block)
        cases = active.json_block['behavioral_matrix_cases']
        assert len(cases) == 8 and all(c['input_text'] is not None for c in cases)
        # The stub only sees a prompt. Its case assertions are fixed test data.
        for actual, frozen in zip(cases, CASE_FIXTURE['cases'], strict=True):
            assert {key: actual[key] for key in frozen} == frozen
        return StatelessAuthor(CASE_FIXTURE['cases'])(prompt)
    patch.setattr(pipeline, '_call_revision_provider', adapter)
    try:
        pipeline.maybe_run_auto_patch(state, interactive=False)
        assert (ROOT/TARGET_FILE).read_bytes() == before
    finally:
        patch.undo()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'replay.json').write_text(json.dumps({
        'candidate0': captured.get('candidate0'), 'candidate1': state.json_block,
        'revision_prompt': captured.get('prompt'), 'initial_prompt': initial,
    }, ensure_ascii=False, indent=2)+'\n',encoding='utf-8')
    assert 'prompt' in captured, state.json_block
    return state, authoring, initial, captured, contract


def test_exact_round10_revision_reaches_verified_without_authority(replay):
    state, authoring, initial, captured, contract = replay
    old, block = captured['candidate0'], state.json_block
    assert old['candidate_verification_status'] == 'rejected'
    from core.json_utils import extract_json_block
    assert old['patch_candidate']['patched_snippet'] == extract_json_block(ROUND10['candidate0_response'])['patch_candidate']['patched_snippet']
    assert block['patch_candidate']['patched_snippet'] == CORRECT_BODY.rstrip('\n')
    assert block['candidate_effect_status'] == 'mutating'
    assert block['candidate_novelty_admitted'] is True
    assert block['candidate_probe_apply_status'] == 'applied'
    assert block['behavioral_matrix_status'] == 'fixed_and_preserved'
    assert len(block['behavioral_matrix_cases']) == 8
    assert block['candidate_verification_status'] == 'verified'
    assert block['candidate_revision_attempt_count'] == 1
    assert block['execution_authorized'] is False
    assert block['final_repository_changed'] is False
    assert block['candidate_presentation_coherent'] is True
    assert block['summary'] == 'Candidate1 contract-stub response'
    assert block['final_candidate_generation'] == 'revision'
    assert block['final_candidate_fingerprint'] == block['candidate_verification_candidate_fingerprint']
    assert parse_revised_candidate(StatelessAuthor(old['behavioral_matrix_cases'])(captured['prompt']), captured['evidence']).accepted


def test_shared_scope_initial_revision_and_body_parameters(replay):
    state, authoring, initial, captured, _ = replay
    assert 'def ' not in authoring.source_snippet
    assert scope_data(initial) == scope_data(captured['prompt'])
    assert authoring.scope_text in initial and authoring.scope_text in captured['prompt']
    assert state.json_block['candidate_revision_receipt']['authoring_scope_fingerprint'] == authoring.scope_fingerprint
    assert authoring.contract.version == 'patch_authoring_contract_v3'
    for section in authoring.contract.sections:
        assert section in initial and section in captured['prompt']
    names = {b['name']: b for b in scope_data(initial)['available_baseline_bindings']}
    assert names['language']['kind'] == names['text']['kind'] == 'parameter'
    assert names['counts']['kind'] == names['line']['kind'] == 'existing_local'
    assert names['assess_indentation_observation']['result']['readable_declared_fields']
    for excluded in ('Counter', 'ast', 'Path', 'some_unrelated_repository_symbol'):
        assert excluded not in names
    assert 'Cases the rejected candidate' not in initial
    assert 'END INPUT' not in initial


def test_exact_inputs_languages_and_probe_identities(replay):
    _, _, _, captured, contract = replay
    matrix = build_behavioral_matrix(probe_contract=contract, behavior_fact=_t6_behavior_fact())
    cases = {c.case_id: c for c in matrix}
    evidence = captured['evidence']
    assert len(evidence.failed_cases) == 3
    assert len(evidence.preserved_cases) == 5
    assert evidence.concrete_counterexample_count == 8
    assert evidence.concrete_counterexample_bytes <= MAX_CONCRETE_INPUT_BYTES
    for item in evidence.failed_cases + evidence.preserved_cases:
        executed = cases[item.case_id]
        assert item.input_text == executed.contract.structured_input['args'][0]
        assert item.input_language == executed.input_language
        assert item.case_probe_fingerprint == executed.contract.fingerprint
        assert item.input_text in captured['prompt']
        assert item.expected == executed.expected
    assert 'input_language=go' in captured['prompt']
    assert 'input_language=python' in captured['prompt']


@pytest.mark.parametrize('missing', ['language', 'helpers', 'fields', 'preservation', 'failed', 'schema'])
def test_stateless_stub_refuses_missing_information(replay, missing):
    _, _, _, captured, _ = replay
    prompt = captured['prompt']
    scope = scope_data(prompt)
    bindings = scope['available_baseline_bindings']
    if missing == 'language':
        scope['available_baseline_bindings'] = [b for b in bindings if b['name'] != 'language']
    elif missing == 'helpers':
        scope['available_baseline_bindings'] = [b for b in bindings if b['kind'] != 'repository_local_direct_import']
    elif missing == 'fields':
        for b in bindings:
            b.pop('result', None)
    elif missing in {'preservation', 'failed'}:
        cases = captured['evidence'].preserved_cases if missing == 'preservation' else captured['evidence'].failed_cases
        for c in cases:
            prompt = prompt.replace(c.input_text, '<omitted>')
    elif missing == 'schema':
        prompt = prompt.replace('"patched_snippet"', '"invalid_alias"')
    if missing in {'language', 'helpers', 'fields'}:
        prompt = prompt.replace(json.dumps(scope_data(prompt),ensure_ascii=False,sort_keys=True,indent=2), json.dumps(scope,ensure_ascii=False,sort_keys=True,indent=2))
    with pytest.raises(ValueError):
        StatelessAuthor(captured['candidate0']['behavioral_matrix_cases'])(prompt)


def fixture_context(tmp_path, *, field='payload', source=None):
    helper = ('from dataclasses import dataclass\n@dataclass(frozen=True)\nclass Record:\n'
              f'    {field}: str\ndef local_helper() -> Record:\n    return Record("ok")\n'
              'raise AssertionError("must never execute")\n')
    source = source or ('from helper import local_helper\nfrom pathlib import Path\n'
                        'from absent_third_party import alien\nunrelated = 12\n'
                        'def target(text, language):\n    local = text\n    return local\n')
    (tmp_path/'helper.py').write_text(helper,encoding='utf-8')
    (tmp_path/'target.py').write_text(source,encoding='utf-8')
    control = {'patch_style':'safe_minimal','patch_intent':{
        'relative_path':'target.py','target_symbol':'target','source_snippet':'    return local'}}
    return authoring_context_for_control_result(control,repo_path=str(tmp_path)),control


@pytest.mark.parametrize('field', ['payload','value','data'])
def test_generic_static_projection_excludes_nonlocal_capabilities(tmp_path,field):
    context, _ = fixture_context(tmp_path,field=field)
    names = {b['name']: b for b in scope_data(context.scope_text)['available_baseline_bindings']}
    assert set(names) == {'local_helper','text','language','local'}
    assert names['local_helper']['result']['readable_declared_fields'] == [field]
    assert len(context.scope_text.encode()) < MAX_SCOPE_BYTES


@pytest.mark.parametrize('change', ['target_source','helper_source','target','snippet','source_digest'])
def test_stale_scope_omits_expansion(tmp_path,change):
    context, control = fixture_context(tmp_path)
    if change.endswith('_source'):
        path=tmp_path/('target.py' if change=='target_source' else 'helper.py')
        path.write_text(path.read_text()+'\n# changed\n')
    elif change=='target':
        context=replace(context,target_symbol='other')
    elif change=='snippet':
        context=replace(context,source_snippet='    return made_up')
    else:
        context=replace(context,authoritative_source='different')
        assert scope_data(context.scope_text)['available_baseline_bindings']==[]
        return
    binding,source=context.binding_inputs(tmp_path)
    assert binding is None
    assert scope_data(replace(context,binding_context=binding,authoritative_source=source).scope_text)['available_baseline_bindings']==[]


@pytest.mark.parametrize('change', ['candidate','matrix_case','probe','task','source','target','run'])
def test_revision_freshness_rejects_mixed_evidence(replay,change):
    _,_,_,captured,_=replay
    e=captured['evidence']; payload=copy.deepcopy(captured['candidate0'])
    args=dict(candidate_fingerprint=e.rejected_candidate_fingerprint, original_source=e.original_source,
              target_file=e.target_file,target_symbol=e.target_symbol,preserved_task=e.preserved_task,payload=payload,run_identity=e.run_identity)
    assert revision_evidence_is_current(e,**args)
    if change=='candidate': args['candidate_fingerprint']='a'*64
    elif change=='matrix_case': payload['behavioral_matrix_cases'][0]['input_text']='different executed run'
    elif change=='probe': payload['probe_fingerprint']='b'*64
    elif change=='task': args['preserved_task']='other task'
    elif change=='source': args['original_source']+='\n'
    elif change=='target': args['target_symbol']='other'
    elif change=='run': args['run_identity']='another run'
    assert not revision_evidence_is_current(e,**args)


def test_caps_and_missing_concrete_data_never_invent_fixtures(replay):
    _,_,_,captured,_=replay
    data=copy.deepcopy(captured['assessment_inputs'])
    rows=data['payload']['behavioral_matrix_cases']
    data['payload']['behavioral_matrix']['cases']=rows
    for c in rows:
        c['input_text']='é'*1500
    rows.extend(copy.deepcopy(rows))
    evidence=assess_candidate_revision(data).evidence
    assert len(evidence.failed_cases+evidence.preserved_cases)<=8
    assert evidence.concrete_counterexample_bytes<=16_384
    assert all(c.input_text in (None,'é'*1500) for c in evidence.failed_cases+evidence.preserved_cases)
    for c in rows: c.pop('input_text')
    evidence=assess_candidate_revision(data).evidence
    assert evidence.concrete_counterexample_count==0
    assert 'END INPUT' not in build_revision_prompt(evidence,render_patch_authoring_contract(style='safe_minimal',source_snippet=evidence.original_source))
    assert MAX_REVISION_CALLS_PER_RUN==1


def test_probe_mismatch_and_unexecuted_inputs_are_not_materialized(replay):
    *_,contract=replay
    case=build_behavioral_matrix(probe_contract=contract,behavior_fact=_t6_behavior_fact())[0]
    baseline=ProbeObservation('reproduced','4space')
    for candidate in (None,ProbeObservation('reproduced','4space',probe_fingerprint='f'*64)):
        assert resolve_matrix_case(case,baseline,candidate).input_text is None
    # A deliberately unusual exact contract input proves the reducer does not
    # reconstruct a fixture from the case ID or current generator code.
    fixture='if True:\r\n  marker = "é"\r\n'
    data=case.contract.structured_input; data['args']=[fixture]
    contract=replace(case.contract,structured_input_json=json.dumps(data))
    case=replace(case,contract=contract)
    measured=resolve_matrix_case(case,baseline,ProbeObservation('reproduced','4space',probe_fingerprint=contract.fingerprint))
    assert measured.input_text==fixture


def test_no_production_solution_prose_and_frozen_policy(replay):
    paths=['core/candidate_authoring_context.py','core/patch_authoring_contract.py','core/candidate_revision.py']
    for path in paths:
        tree=ast.parse((ROOT/path).read_text(encoding='utf-8'))
        constants='\n'.join(n.value for n in ast.walk(tree) if isinstance(n,ast.Constant) and isinstance(n.value,str))
        assert CORRECT_BODY not in constants
        for advice in ('Call observe_source_indentation first','Then call assess_indentation_observation','Return .value','Use the structural observer'):
            assert advice not in constants
    frozen=['core/code_dna.py','core/authoritative_binding_context.py','core/immutable_result_fields.py',
            'core/local_binding_novelty.py','patching/patch_gates.py','core/candidate_verification.py',
            'core/targeted_repository_validation.py','core/live_execution_authorization.py']
    manifest=json.loads((ROOT/'tests/fixtures/patch_author_live3_frozen_boundaries.json').read_text())
    for path in frozen:
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==manifest['files'][path],path


def test_prompt_rendering_cost_and_sizes(replay):
    _,context,initial,captured,_=replay
    scope=[];concrete=[]
    for _ in range(31):
        t=time.perf_counter();context.scope_text;scope.append(time.perf_counter()-t)
        t=time.perf_counter();context.revision_prompt(captured['evidence']);concrete.append(time.perf_counter()-t)
    data={'scope_render_median_ms':statistics.median(scope)*1000,
          'revision_render_median_ms':statistics.median(concrete)*1000,
          'initial_prompt_bytes':len(initial.encode()),'revision_prompt_bytes':len(captured['prompt'].encode()),
          'scope_bytes':len(context.scope_text.encode()),
          'concrete_counterexample_bytes':captured['evidence'].concrete_counterexample_bytes}
    (OUT/'performance.json').write_text(json.dumps(data,indent=2)+'\n')
    assert max(scope+concrete)<0.5
