"""Guarded binding controls. Fabricated ladders never count as live proof."""
from copy import copy, deepcopy
from dataclasses import FrozenInstanceError, fields, replace
import inspect
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from core import sandbox_backend_binding as owner
from core import sandbox_backend_provenance as provenance
from tests._preflight_runtime1_guard import no_runtime_effects
from tests.test_runtime_java1c import capture, sandbox_pair


@pytest.fixture(autouse=True)
def guarded():
    with no_runtime_effects(strict=True) as effects:
        yield
    assert effects.denied_attempts == {}


@pytest.fixture
def control():
    descriptor, receipt = sandbox_pair()
    live = {'status': owner.sandbox2.COMPLETE, 'cleanup_verified': True,
        'temporary_workspace_removed': True, 'phase_container_count_after_teardown': 0,
        'javac_version_count': 1, 'java_version_count': 1, 'compile_count': 0,
        'jvm_fixture_count': 0,
        'stages': [{'mode': m, 'verdict': owner.sandbox2.PASSED} for m in owner.sandbox2.LADDER],
        'descriptor': descriptor.as_dict(), 'verification_receipt': receipt.as_dict()}
    endpoint = owner.sandbox._local_endpoint()
    state = SimpleNamespace(live=live, calls=[], order=[],
        prefix=('fixed-docker.exe', '--config', 'absent', '--host', endpoint),
        captures=[capture(stdout=b'{"Server":{"Os":"linux","Version":" Exact.01 "}}')]*2,
        after_control=None)

    def measured(argv, **kwargs):
        state.calls.append((argv, kwargs))
        state.order.append('version')
        result = state.captures[len(state.calls)-1]
        if state.after_control:
            state.after_control(len(state.calls))
        return result

    def fresh():
        state.order.append('sandbox2')
        return state.live

    with patch.object(owner.sandbox, '_docker_prefix', return_value=state.prefix), \
            patch.object(owner.sandbox, '_bounded_process', measured), \
            patch.object(owner.sandbox2, 'replay', fresh):
        yield state


@pytest.fixture
def issued(control):
    return owner.issue_sandbox_backend_binding()


def test_exact_pre_fresh_post_order_and_effects_then_stop(control):
    report = owner.replay()
    assert report['status'] == owner.COMPLETE
    assert control.order == ['version', 'sandbox2', 'version']
    assert control.calls == [(control.prefix + ('version', '--format', '{{json .}}'),
        {'timeout_ms': 8000, 'stdout_limit': 65536})]*2
    assert report['fresh_sandbox2_invocations'] == 1
    assert report['fresh_sandbox2_authenticated'] is report['exact_live_pair_revalidated'] is True
    assert report['attachment_authentication'] is report['pair_binding'] is True
    assert report['route_version_bracket_equal'] is True
    assert report['canonical_backend_version'] == ' Exact.01 '
    assert report['sandbox_receipt_evidence_sha256'] == owner.sandbox._hash(control.live['stages'])
    assert report['binding_only_effects']['docker_calls'] == 2
    assert report['binding_only_effects']['version_calls'] == 2
    assert all(v == 0 for k,v in report['binding_only_effects'].items()
        if k not in ('docker_calls','version_calls'))
    assert report['sandbox2_infrastructure_effects']['docker_calls'] == 0  # fixture
    assert report['cleanup_verified'] is True
    assert report['remaining_phase_containers'] == 0
    assert report['pre_control_reaped_and_pipes_closed'] is True
    assert report['post_control_reaped_and_pipes_closed'] is True
    assert report['copy_json_process_hmac_negatives_rejected'] is True
    assert all(report['negative_authentication_matrix'].values())
    assert report['controlled_discovery_comparison'] is True
    assert report['discovery_comparison_is_authenticated_discovery_evidence'] is False
    assert set(report['prohibited_effects'].values()) == {0}
    assert all(report[k] is False for k in owner.AUTHORITIES + (
        'daemon_instance_identity_available', 'daemon_continuity_proven', 'aba_resistance_proven'))


@pytest.mark.parametrize('version', ['29.6.1',' Exact.01\n','0',123,True,['exact']])
def test_original_server_semantics_match_frozen_2p_without_normalization(version):
    endpoint = 'npipe:////./pipe/dockerDesktopLinuxEngine'
    raw = json.dumps({'Server': {'Os':'linux','Version':version,'ApiVersion':'substitute'},
        'Client': {'Version':'substitute'}, 'Context':'desktop-linux'})
    identity, measured = owner._backend_witness(raw, endpoint)
    legacy = provenance._backend_witness(raw, endpoint)
    assert identity == legacy['backend_identity'] == 'local-docker:' + endpoint
    assert measured == legacy['backend_version'] == str(version)


@pytest.mark.parametrize('value', [[],None,{}, {'Server':[]}, {'Server':'alias'},
    {'Server':{'Version':'1'}}, {'Server':{'Os':'Linux','Version':'1'}},
    {'Server':{'Os':'windows','Version':'1'}},
    *({'Server':{'Os':'linux','Version':v}} for v in ('',0,False,None,[],{})),
    {'Client':{'Os':'linux','Version':'1'}}, {'Server':{'Os':'linux','ApiVersion':'1'}},
    {'Context':'desktop-linux'}, {'backend_identity':'caller-alias','backend_version':'1'}])
def test_client_api_context_alias_or_missing_linux_version_rejected(value):
    with pytest.raises(ValueError): owner._backend_witness(json.dumps(value), 'fixed')


@pytest.mark.parametrize('raw', [b'not json',b'\xff',b'{'])
def test_invalid_backend_metadata_blocks_before_sandbox(control, raw):
    control.captures[0] = capture(stdout=raw)
    result = owner.replay()
    assert result['status'] == owner.PRE_MEASUREMENT
    assert result['fresh_sandbox2_invocations'] == 0
    assert result['attachment_issued'] is False


@pytest.mark.parametrize('part', ['identity','version'])
def test_pre_post_mismatch_never_registers_attachment(control, part):
    before = set(owner._LIVE)
    identity = 'local-docker:' + owner.sandbox._local_endpoint()
    pre = identity, '1'
    post = (identity+'changed','1') if part == 'identity' else (identity,'1 ')
    with patch.object(owner, '_backend_witness', side_effect=[pre,post]):
        result = owner.replay()
    assert result['status'] == owner.ROUTE_VERSION_CHANGED
    assert result['attachment_issued'] is result['route_version_bracket_equal'] is False
    assert result['canonical_backend_identity'] is result['canonical_backend_version'] is None
    assert set(owner._LIVE) == before
    assert control.order == ['version','sandbox2','version']


@pytest.mark.parametrize('prefix', [(),('docker',),
    ('docker','--config','absent','--context','desktop-linux'),
    ('docker','--config','absent','--host','tcp://caller')])
def test_nonfrozen_route_blocks_before_any_control(control, prefix):
    with patch.object(owner.sandbox, '_docker_prefix', return_value=prefix):
        result = owner.replay()
    assert result['status'] == owner.PRE_MEASUREMENT
    assert control.order == []


@pytest.mark.parametrize('index', [0,1])
@pytest.mark.parametrize('changes,expected', [({'status':'sandbox_control_failure'},owner.CLEANUP),
    ({'status':'sandbox_timeout'},owner.CLEANUP),
    ({'status':'sandbox_output_limit_exceeded'},owner.CLEANUP),
    ({'exit_code':1},None), ({'termination_within_deadline':False},None)])
def test_failed_pre_or_post_control_blocks_issuance(control, index, changes, expected):
    control.captures[index] = capture(**changes)
    result = owner.replay()
    assert result['status'] == (expected or (owner.PRE_MEASUREMENT if index==0 else owner.UNRESOLVED))
    assert result['attachment_issued'] is False
    assert result['fresh_sandbox2_invocations'] == index


@pytest.mark.parametrize('key,value', [('cleanup_verified',False),
    ('temporary_workspace_removed',False), ('phase_container_count_after_teardown',1),
    ('phase_container_count_after_teardown',False), ('phase_container_count_after_teardown',None)])
def test_cleanup_failure_blocks_before_post(control, key, value):
    control.live[key] = value
    result = owner.replay()
    assert result['status'] == owner.CLEANUP
    assert result['attachment_issued'] is False
    assert control.order == ['version','sandbox2']


@pytest.mark.parametrize('kind', ['descriptor','receipt','stage_evidence','cleanup','workspace','containers'])
def test_live_evidence_or_cleanup_changed_during_post_blocks(control, kind):
    def changed(index):
        if index != 2: return
        if kind == 'descriptor': control.live['descriptor']['sandbox_descriptor_fingerprint'] = '0'*64
        elif kind == 'receipt': control.live['verification_receipt']['verification_receipt_fingerprint'] = '0'*64
        elif kind == 'stage_evidence': control.live['stages'][0]['extra'] = 'changed'
        elif kind == 'cleanup': control.live['cleanup_verified'] = False
        elif kind == 'workspace': control.live['temporary_workspace_removed'] = False
        else: control.live['phase_container_count_after_teardown'] = 1
    control.after_control = changed
    result = owner.replay()
    assert result['status'] == (owner.CLEANUP if kind in ('cleanup','workspace','containers') else owner.SANDBOX_AUTH)
    assert result['attachment_issued'] is False


def test_failed_fresh_ladder_does_not_invent_pair_or_post(control):
    control.live['status'] = owner.sandbox2.UNRESOLVED
    result = owner.replay()
    assert result['status'] == owner.SANDBOX_AUTH
    assert result['fresh_sandbox2_authenticated'] is result['attachment_issued'] is False
    assert control.order == ['version','sandbox2']


def test_factory_has_no_caller_witness_endpoint_config_context_or_method(control):
    for operation in (owner.issue_sandbox_backend_binding,owner.replay):
        assert not inspect.signature(operation).parameters
        for value in ('alias', {'backend_version':'1'}, {'endpoint':'tcp://caller'}, control.live):
            with pytest.raises(TypeError): operation(value)
    assert control.order == []


def test_factory_failure_is_typed_and_issues_nothing(control):
    control.captures[0] = capture(exit_code=1)
    with pytest.raises(owner.BindingBlocked) as error: owner.issue_sandbox_backend_binding()
    assert error.value.status == owner.PRE_MEASUREMENT


def test_live_immutable_pair_bound_evidence_and_separate_domain(issued):
    attachment, descriptor, receipt = issued
    assert owner.validate_sandbox_backend_binding(attachment,descriptor,receipt) is attachment
    assert attachment.sandbox_descriptor_fingerprint == descriptor.fingerprint
    assert attachment.sandbox_receipt_fingerprint == receipt.fingerprint
    assert attachment.sandbox_receipt_evidence_sha256 == receipt.evidence_sha256
    assert attachment.image_identity == descriptor.image_identity == receipt.image_identity
    assert attachment.binding_semantics == owner.BINDING_SEMANTICS
    assert attachment.issuing_pid == owner.os.getpid()
    assert len(attachment.attachment_id) == 64
    assert owner._SECRET != owner.sandbox2._SECRET
    assert owner._SECRET != owner.sandbox._SECRET
    assert all(getattr(attachment,k) is False for k in owner.AUTHORITIES)
    with pytest.raises(FrozenInstanceError): attachment.backend_version_pre = 'changed'
    assert not hasattr(attachment, 'backend_continuity_proven')
    assert not hasattr(attachment, 'consume')


@pytest.mark.parametrize('kind', ['copy','deepcopy','replace','json','json_dataclass','wrapper','subclass'])
def test_copies_reconstructions_and_wrappers_cannot_recreate_live_provenance(issued, kind):
    attachment, descriptor, receipt = issued
    if kind == 'copy': candidate = copy(attachment)
    elif kind == 'deepcopy': candidate = deepcopy(attachment)
    elif kind == 'replace': candidate = replace(attachment)
    elif kind == 'json': candidate = json.loads(json.dumps(attachment.as_dict()))
    elif kind == 'wrapper': candidate = SimpleNamespace(**attachment.as_dict())
    else:
        cls = owner.SandboxBackendBindingAttachment
        if kind == 'subclass':
            class Subclass(cls): pass
            cls = Subclass
        candidate = cls(**{f.name:getattr(attachment,f.name) for f in fields(attachment) if f.init})
    with pytest.raises(ValueError): owner.validate_sandbox_backend_binding(candidate,descriptor,receipt)
    assert not owner.sandbox_backend_binding_satisfies_java1_discovery(candidate,
        attachment.canonical_backend_identity,attachment.canonical_backend_version)


@pytest.mark.parametrize('role', ['descriptor','receipt'])
def test_same_fingerprint_different_sandbox_object_is_not_the_bound_live_pair(issued, role):
    attachment, descriptor, receipt = issued
    if role == 'descriptor': descriptor = deepcopy(descriptor)
    else: receipt = deepcopy(receipt)
    # Frozen authentication accepts copies; the attachment tightens exact pair binding.
    owner.sandbox2.validate_descriptor(descriptor,receipt)
    with pytest.raises(ValueError,match='exact_pair'): owner.validate_sandbox_backend_binding(attachment,descriptor,receipt)


@pytest.mark.parametrize('role', ['descriptor','receipt'])
@pytest.mark.parametrize('key', ['phase_id','schema_version','seccomp_policy_sha256','image_identity'])
def test_even_owner_signed_wrong_sandbox_contract_rejected(issued, role, key):
    attachment, descriptor, receipt = issued
    target = descriptor if role == 'descriptor' else receipt
    original, signature = getattr(target,key), target._signature
    try:
        object.__setattr__(target,key,'changed')
        object.__setattr__(target,'_signature',owner.sandbox2._sign(target))
        with pytest.raises(ValueError): owner.validate_sandbox_backend_binding(attachment,descriptor,receipt)
    finally:
        object.__setattr__(target,key,original)
        object.__setattr__(target,'_signature',signature)


@pytest.mark.parametrize('key,value', [
    *[(k,'changed') for k in ('backend_identity_pre','backend_version_pre',
        'backend_identity_post','backend_version_post','canonical_backend_identity',
        'canonical_backend_version','sandbox_descriptor_fingerprint','sandbox_receipt_fingerprint',
        'sandbox_receipt_evidence_sha256','sandbox_policy_sha256','image_identity','phase_id',
        'schema_version','sandbox_phase_id','sandbox_schema_version','binding_semantics',
        'measurement_method_id','attachment_id')],
    ('_signature','0'*64), ('issuing_pid',-1), ('route_version_bracket_equal',False),
    ('sandbox_cleanup_verified',False), ('pre_control_reaped_and_pipes_closed',False),
    ('post_control_reaped_and_pipes_closed',False), ('temporary_workspace_removed',False),
    ('remaining_phase_containers',1), ('daemon_instance_identity_available',True),
    ('daemon_continuity_proven',True), ('aba_resistance_proven',True),
    *[(k,True) for k in owner.AUTHORITIES]])
def test_modified_live_object_fails_closed_in_both_public_operations(issued, key, value):
    attachment, descriptor, receipt = issued
    original = getattr(attachment,key)
    try:
        object.__setattr__(attachment,key,value)
        with pytest.raises(ValueError): owner.validate_sandbox_backend_binding(attachment,descriptor,receipt)
        assert not owner.sandbox_backend_binding_satisfies_java1_discovery(attachment,
            attachment.canonical_backend_identity,attachment.canonical_backend_version)
    finally:
        object.__setattr__(attachment,key,original)
    assert owner.validate_sandbox_backend_binding(attachment,descriptor,receipt) is attachment


def test_signed_projection_snapshot_is_independent_of_current_signature(issued):
    attachment, descriptor, receipt = issued
    original, signature = attachment.canonical_backend_version, attachment._signature
    try:
        object.__setattr__(attachment,'canonical_backend_version','changed')
        object.__setattr__(attachment,'_signature',owner._sign(attachment))
        with pytest.raises(ValueError,match='projection_changed'):
            owner.validate_sandbox_backend_binding(attachment,descriptor,receipt)
    finally:
        object.__setattr__(attachment,'canonical_backend_version',original)
        object.__setattr__(attachment,'_signature',signature)


def test_wrong_process_rejected_without_spawning_a_process(issued):
    attachment, descriptor, receipt = issued
    with patch.object(owner.os,'getpid',return_value=attachment.issuing_pid+1):
        with pytest.raises(ValueError,match='process_provenance'):
            owner.validate_sandbox_backend_binding(attachment,descriptor,receipt)
        assert not owner.sandbox_backend_binding_satisfies_java1_discovery(attachment,
            attachment.canonical_backend_identity,attachment.canonical_backend_version)


def test_changed_receipt_digest_cannot_be_rebound_even_with_owner_signature(issued):
    attachment, descriptor, receipt = issued
    other_receipt = replace(receipt,evidence_sha256='0'*64)
    other_receipt = replace(other_receipt,_signature=owner.sandbox2._sign(other_receipt))
    other_descriptor = replace(descriptor,verification_receipt_fingerprint=other_receipt.fingerprint)
    other_descriptor = replace(other_descriptor,_signature=owner.sandbox2._sign(other_descriptor))
    owner.sandbox2.validate_descriptor(other_descriptor,other_receipt)
    with pytest.raises(ValueError): owner.validate_sandbox_backend_binding(attachment,other_descriptor,other_receipt)
    with pytest.raises(ValueError): owner.validate_sandbox_backend_binding(attachment,descriptor,other_receipt)
    with pytest.raises(ValueError): owner.validate_sandbox_backend_binding(attachment,other_descriptor,receipt)


@pytest.mark.parametrize('change', ['identity','version','identity_strip','version_strip','version_case','context','alias','nonstring'])
def test_discovery_predicate_uses_exact_strings_only(issued, change):
    attachment, _, _ = issued
    identity, version = attachment.canonical_backend_identity, attachment.canonical_backend_version
    if change == 'identity': identity += ' '
    elif change == 'version': version += ' '
    elif change == 'identity_strip': identity = identity.upper()
    elif change == 'version_strip': version = version.strip()
    elif change == 'version_case': version = version.lower()
    elif change == 'context': identity = 'desktop-linux'
    elif change == 'alias': identity = 'caller-backend-alias'
    else: version = SimpleNamespace(__eq__=lambda other:True)
    assert not owner.sandbox_backend_binding_satisfies_java1_discovery(attachment,identity,version)


def test_validation_comparison_repeat_without_io_mutation_or_consumption(issued, control):
    attachment, descriptor, receipt = issued
    before = deepcopy((attachment.as_dict(),descriptor.as_dict(),receipt.as_dict()))
    call_count = len(control.calls)
    with patch.object(owner.sandbox,'_bounded_process',side_effect=AssertionError('validator Docker IO')), \
            patch.object(owner.sandbox2,'replay',side_effect=AssertionError('validator fresh ladder')):
        for _ in range(3):
            assert owner.validate_sandbox_backend_binding(attachment,descriptor,receipt) is attachment
            assert owner.sandbox_backend_binding_satisfies_java1_discovery(attachment,
                attachment.canonical_backend_identity,attachment.canonical_backend_version)
    assert before == (attachment.as_dict(),descriptor.as_dict(),receipt.as_dict())
    assert len(control.calls) == call_count


def test_historical_2p_still_refuses_freshness(issued):
    _, descriptor, receipt = issued
    result = provenance.assess_backend_freshness(descriptor,receipt)
    assert result['status'] == provenance.FRESHNESS
    assert result['attachment_issued'] is False
