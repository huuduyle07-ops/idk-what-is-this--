"""Pure SANDBOX.2 policy, authentication and stop-gate regressions."""
from copy import deepcopy
from dataclasses import replace
import json
from types import SimpleNamespace

import pytest

from core import thread_compatible_runtime_sandbox as owner
from core import thread_compatible_runtime_sandbox_probe as probe
from tests._preflight_runtime1_guard import no_runtime_effects
from tests.test_runtime_sandbox1 import _safe_config, _boundary_facts, _capture
from tests.test_runtime_java1b import stage_facts


@pytest.fixture(autouse=True)
def guarded():
    with no_runtime_effects(strict=False): yield


@pytest.fixture
def safe_patch(guarded):
    with pytest.MonkeyPatch.context() as patch: yield patch


def test_only_clone3_errno_changes_and_baseline_bytes_remain_pinned():
    original = deepcopy(owner.baseline._SECCOMP)
    assert owner.validate_policy_bytes(owner.POLICY_PATH.read_bytes())
    restored = deepcopy(owner.POLICY)
    assert restored['syscalls'].pop() == {'names': ['clone3'], 'action': 'SCMP_ACT_ERRNO', 'errnoRet': 38}
    restored['syscalls'][0]['names'].append('clone3')
    assert restored == original
    assert owner.baseline._hash(original) == owner.BASELINE_POLICY_SHA256
    assert owner.POLICY_SHA256 != owner.BASELINE_POLICY_SHA256
    assert owner.POLICY['syscalls'][1:8] == original['syscalls'][1:8]
    assert owner.policy_diff()['thread_only_clone_enforced'] is False


@pytest.mark.parametrize('mutation', ['newline', 'allow_clone3', 'missing_clone_rule', 'allow_socket', 'default_errno'])
def test_policy_rejects_any_other_bytes_or_semantic_change(mutation):
    changed = deepcopy(owner.POLICY)
    if mutation == 'newline': raw = owner.POLICY_BYTES + b'\n'
    else:
        if mutation == 'allow_clone3': changed['syscalls'][-1] = {'names': ['clone3'], 'action': 'SCMP_ACT_ALLOW'}
        if mutation == 'missing_clone_rule': changed['syscalls'].pop(1)
        if mutation == 'allow_socket': changed['syscalls'][0]['names'].remove('socket')
        if mutation == 'default_errno': changed['defaultAction'] = 'SCMP_ACT_ERRNO'
        raw = owner.baseline._json(changed).encode()
    with pytest.raises(ValueError, match='canonical_policy'): owner.validate_policy_bytes(raw)


def pair(status=owner.UNRESOLVED):
    stages = [{'mode': mode, 'verdict': owner.PASSED} for mode in owner.LADDER] if status == owner.COMPLETE else []
    return owner._evidence_pair({'status': status, 'stages': stages, 'cleanup_verified': status == owner.COMPLETE})


def test_authentication_is_new_epoch_bound_and_report_json_has_no_authority():
    descriptor, receipt = pair(owner.COMPLETE)
    assert owner.validate_descriptor(descriptor, receipt) is descriptor
    assert descriptor.eligible_for_java1_continuation
    assert receipt.seccomp_policy_sha256 == owner.POLICY_SHA256
    for value in (descriptor, receipt):
        assert value.phase_id == 'RUNTIME.SANDBOX.2'
        assert all(value.as_dict()[key] is False for key in owner.AUTHORITIES)
        assert '_signature' not in value.as_dict()
    assert not owner.baseline.sandbox_satisfies_executor_boundary(descriptor)
    with pytest.raises(ValueError, match='unauthenticated'): owner.validate_receipt(receipt.as_dict())


@pytest.mark.parametrize('target', ['receipt_status', 'receipt_policy', 'descriptor_eligible', 'descriptor_receipt', 'unsigned'])
def test_tampered_or_unsigned_evidence_is_rejected(target):
    descriptor, receipt = pair()
    if target == 'receipt_status': receipt = replace(receipt, status=owner.COMPLETE)
    if target == 'receipt_policy': object.__setattr__(receipt, 'seccomp_policy_sha256', owner.BASELINE_POLICY_SHA256)
    if target == 'descriptor_eligible': descriptor = replace(descriptor, eligible_for_java1_continuation=True)
    if target == 'descriptor_receipt': descriptor = replace(descriptor, verification_receipt_fingerprint='0' * 64)
    if target == 'unsigned': receipt = replace(receipt, _signature='')
    with pytest.raises(ValueError, match='unauthenticated'): owner.validate_descriptor(descriptor, receipt)


def test_incomplete_stage_list_cannot_issue_completion():
    with pytest.raises(ValueError, match='evidence_incomplete'):
        owner._evidence_pair({'status': owner.COMPLETE, 'stages': [], 'cleanup_verified': True})


@pytest.mark.parametrize('mode', owner.LADDER)
def test_inspected_candidate_configuration_preserves_every_frozen_setting(mode):
    config = _safe_config()
    config['Image'] = owner.IMAGE
    config['HostConfig']['SecurityOpt'] = ['no-new-privileges=true', 'seccomp=' + owner.POLICY_BYTES.decode()]
    config['Config']['Cmd'] = (['-I','-S','-B','-c',owner.baseline.PROBE_SOURCE,mode]
        if mode in owner.baseline.PROBE_IDS else ['-I','-S','-B','-c',probe.source_for(mode)])
    assert owner.safe_configuration(config, mode)
    config['HostConfig']['PidsLimit'] = 129
    assert not owner.safe_configuration(config, mode)


@pytest.mark.parametrize('section,key,value', [
    ('HostConfig','SecurityOpt',['seccomp=unconfined']), ('HostConfig','Privileged',True),
    ('HostConfig','CapAdd',['SYS_ADMIN']), ('HostConfig','NetworkMode','host'),
    ('HostConfig','Memory',268435456), ('HostConfig','Binds',['/host:/work']),
    ('Config','User','0:0'), ('Config','Env',['PATH=/bin']), ('Config','Cmd',['/bin/sh'])])
def test_configuration_rejects_authority_or_boundary_expansion(section,key,value):
    config = _safe_config()
    config['Image'] = owner.IMAGE
    config['HostConfig']['SecurityOpt'] = ['no-new-privileges=true','seccomp=' + owner.POLICY_BYTES.decode()]
    config['Config']['Cmd'] = ['-I','-S','-B','-c',probe.source_for('clone3')]
    config[section][key] = value
    assert not owner.safe_configuration(config, 'clone3')


def state(threads=1):
    return {'pid':1,'ppid':0,'tid':1 if threads==1 else 7,'uid':65534,'gid':65534,
        'processes':[1],'os_threads':threads,'pids_max':'128','memory_max':'134217728',
        'capabilities_zero':True,'no_new_privileges':True,
        'namespaces':dict.fromkeys(probe.NAMESPACE_FLAGS,'same'), 'cgroup':'same'}


def native_facts():
    record = {'create_return_code':0,'join_return_code':0,'before':state(),
        'thread':state(2),'after':state(),'socket_errno':1}
    return {'namespace_probes':{n:dict.fromkeys(('clone','unshare','setns'),{'result':-1,'errno':1})
        for n in probe.NAMESPACE_FLAGS},'pthreads':[deepcopy(record),deepcopy(record)],
        'before':state(),'after':state(),'witness_filter':{'result':0,'errno':0},
        'witness_rejects_other_flags':{'result':-1,'errno':1},'witness_flags':probe.PTHREAD_CLONE_FLAGS}


def test_clone3_requires_enosys_and_no_created_process():
    facts = {'clone3':{'result':-1,'errno':38},'before':state(),'after':state()}
    assert owner.classify('clone3',_capture(),facts,True)==owner.PASSED
    facts['clone3']['errno']=1
    assert owner.classify('clone3',_capture(),facts,True)==owner.UNRESOLVED


def test_bounded_pthread_with_exact_flag_witness_and_shared_boundary_passes():
    assert owner.classify('pthread',_capture(),native_facts(),True)==owner.PASSED


@pytest.mark.parametrize('operation', ['clone','unshare','setns'])
@pytest.mark.parametrize('namespace', list(probe.NAMESPACE_FLAGS))
def test_every_namespace_creation_or_join_success_stops_candidate(namespace,operation):
    facts=native_facts()
    facts['namespace_probes'][namespace][operation]={'result':0,'errno':0}
    assert owner.classify('pthread',_capture(),facts,True)==owner.CONTAINMENT_BLOCKED


@pytest.mark.parametrize('change', ['namespace','cgroup','uid','capability','threads','socket','process','cleanup'])
def test_thread_containment_regressions_are_blocked(change):
    facts=native_facts()
    during=facts['pthreads'][0]['thread']
    if change=='namespace': during['namespaces']['user']='new'
    if change=='cgroup': during['cgroup']='other'
    if change=='uid': during['uid']=0
    if change=='capability': during['capabilities_zero']=False
    if change=='threads': during['os_threads']=3
    if change=='process': during['processes']=[1,2]
    if change=='socket': facts['pthreads'][0]['socket_errno']=0
    assert owner.classify('pthread',_capture(),facts,change!='cleanup')==owner.CONTAINMENT_BLOCKED


@pytest.mark.parametrize('code,status', [(1,owner.FALLBACK_BLOCKED),(11,owner.FALLBACK_BLOCKED)])
def test_native_failure_is_distinct_from_java_failure(code,status):
    facts=native_facts()
    facts['pthreads']=[{'create_return_code':code}]
    assert owner.classify('pthread',_capture(),facts,True)==status


def bpf_action(nr, flags, arch=0xC000003E):
    pc=acc=0
    data={0:nr,4:arch,16:flags & 0xFFFFFFFF,20:flags >> 32}
    while True:
        code,jt,jf,k=probe.CLONE_WITNESS_BPF[pc]
        if code==0x20: acc=data[k]
        elif code==0x15:
            pc+=jt if acc==k else jf
        elif code==0x06: return k
        else: pytest.fail('unknown filter instruction')
        pc+=1


def test_witness_filter_allows_only_exact_full_clone_flags_and_cannot_change_parent_policy():
    assert bpf_action(56,probe.PTHREAD_CLONE_FLAGS)==0x7FFF0000
    for flags in (17,probe.PTHREAD_CLONE_FLAGS | (1<<32),probe.PTHREAD_CLONE_FLAGS | 0x10000000):
        assert bpf_action(56,flags)==0x50001
    assert bpf_action(56,probe.PTHREAD_CLONE_FLAGS,arch=0)==0x50001
    assert bpf_action(435,0)==0x7FFF0000  # outer Docker filter still returns ENOSYS
    assert owner.POLICY['syscalls'][-1]['errnoRet']==38


def test_fixed_sources_compile_and_do_not_include_compilation_or_java_fixture():
    for mode in owner.LADDER:
        if mode not in owner.baseline.PROBE_IDS: compile(probe.source_for(mode),'<sandbox2-fixed>','exec')
    with pytest.raises(ValueError): probe.source_for('arbitrary')
    assert 'reader.start()' not in probe.source_for('controller')
    assert 'JavaSandboxProbe.java' not in probe.source_for('javac_version')
    assert repr(probe.JAVA_PATH) in probe.source_for('java_version')


def test_java_failure_stops_after_native_success_without_compilation():
    facts=stage_facts(exit_code=1)
    assert owner.classify('javac_version',_capture(),facts,True)==owner.JAVA_BLOCKED
    assert owner.classify('javac_version',_capture(),stage_facts(),True)==owner.PASSED


@pytest.mark.parametrize('stop_at', ['clone3','pthread','boundary','controller','javac_version','java_version'])
def test_ladder_stops_at_first_failure_and_never_invokes_java1(safe_patch,stop_at):
    calls=[]
    safe_patch.setattr(owner.baseline,'_docker_prefix',lambda:('fixed-docker',))
    def control(argv,**kwargs):
        if 'image' in argv:
            return _capture(stdout=json.dumps({'Id':owner.IMAGE,'Os':'linux','Architecture':'amd64','Config':{}}).encode())
        return _capture()
    safe_patch.setattr(owner.baseline,'_bounded_process',control)
    class Endpoint:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def bind(self,*args): pass
        def listen(self,*args): pass
        def getsockname(self): return ('127.0.0.1',1)
    safe_patch.setattr(owner.socket,'socket',lambda *args:Endpoint())
    safe_patch.setattr(owner.select,'select',lambda *args:([],[],[]))
    safe_patch.setattr(owner,'invoke',lambda prefix,profile,mode,*args:
        (calls.append(mode) or _capture(),{},True))
    safe_patch.setattr(owner,'classify',lambda mode,*args,**kwargs:
        owner.JAVA_BLOCKED if mode==stop_at else owner.PASSED)
    result=owner.replay()
    assert calls==list(owner.LADDER[:owner.LADDER.index(stop_at)+1])
    assert result['status']==owner.JAVA_BLOCKED
    assert result['compile_count']==result['jvm_fixture_count']==result['runtime_policy_authorizations_consumed']==0
    assert all(result[key] is False for key in owner.AUTHORITIES)
    assert not result['java1_completed'] and not result['executor_refreshed_or_resumed']
