"""Pure contract negatives, never mocked evidence of local OS enforcement.

Actual hostile integration belongs to the verifier replay. These tests exercise
closed policies, evidence authenticity, and the predicates that fail a measured
probe. No test in this module launches a container or candidate workload.
"""
from dataclasses import FrozenInstanceError, fields, replace
from hashlib import sha256
from pathlib import Path

import pytest

from core import candidate_runtime_sandbox as owner


def _unavailable_backend(version=''):
    return owner.SandboxBackendObservation('Windows-AMD64', '', version, '', False,
        False, 'sandbox_backend_unavailable')


def _capture(status='sandbox_completed', *, stdout=b'', stderr=b'', exit_code=0,
             deadline=False, termination=True, within_deadline=True):
    return owner._Capture(status, exit_code, stdout, stderr, deadline, termination, within_deadline)


def _boundary_facts():
    return {
        'manifest': [{'path': 'projection.txt', 'sha256': sha256(owner._FIXTURE).hexdigest(),
                      'size_bytes': len(owner._FIXTURE)}],
        'workspace_write': True,
        'external_read_denied': True, 'external_write_denied': True,
        'root_write_denied': True,
        'socket_denials': dict.fromkeys(('ipv4_tcp', 'ipv6_tcp', 'dns_udp', 'unix_socket'), True),
        'local_connect_denied': True, 'socketpair_denied': True,
        'host_secret_absent': True,
        'environment': dict(owner._WORKLOAD_ENVIRONMENT),
        'uid': 65534, 'pid_is_one': True, 'no_new_privileges': True,
        'capabilities_zero': True,
    }


def _passed(facts, *, capture=None, cleanup=True, host_unchanged=True, quiet=True):
    return owner._facts_passed('boundary', capture or _capture(), facts,
        cleanup, host_unchanged, quiet)


def _safe_config():
    return {
        'Image': 'sha256:' + '1' * 64,
        'Mounts': [],
        'HostConfig': {
            'Privileged': False, 'NetworkMode': 'none', 'PidMode': '',
            'IpcMode': 'none', 'CgroupnsMode': 'private', 'ReadonlyRootfs': True,
            'Binds': None, 'Mounts': None, 'CapDrop': ['ALL'], 'CapAdd': None,
            'LogConfig': {'Type': 'none'}, 'PidsLimit': 128,
            'Memory': 134217728, 'NanoCpus': 1000000000,
            'Tmpfs': {'/work': 'rw,nosuid,nodev,size=32m,mode=1777',
                      '/tmp': 'rw,nosuid,nodev,noexec,size=16m,mode=1777'},
            'SecurityOpt': ['no-new-privileges=true', 'seccomp=' + owner._json(owner._SECCOMP)],
        },
        'Config': {
            'User': '65534:65534', 'WorkingDir': '/work',
            'Entrypoint': ['/usr/local/bin/python'],
            'Cmd': ['-I', '-S', '-B', '-c', owner.PROBE_SOURCE, 'boundary'],
            'Env': [key + '=' + value for key, value in owner._WORKLOAD_ENVIRONMENT.items()],
        },
    }


@pytest.fixture
def blocked(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('pure unavailable path attempted a runtime effect')
    monkeypatch.setattr(owner, 'discover_local_sandbox_backend',
        lambda **kwargs: _unavailable_backend())
    for name in ('_bounded_process', '_docker_prefix', '_invoke_probe'):
        monkeypatch.setattr(owner, name, forbidden)
    monkeypatch.setattr(owner.tempfile, 'TemporaryDirectory', forbidden)
    monkeypatch.setattr(owner.socket, 'socket', forbidden)
    return owner.verify_candidate_runtime_sandbox()


def test_missing_backend_is_authenticated_typed_block_with_zero_workloads(blocked):
    descriptor, receipt = blocked
    assert receipt.status == 'RUNTIME_SANDBOX_1_BLOCKED_BACKEND_UNAVAILABLE'
    assert receipt.missing_requirements == owner.MANDATORY_REQUIREMENTS
    assert receipt.outcomes == ()
    assert receipt.cleanup_outcome == 'not_required_no_workload_launched'
    assert descriptor.available is descriptor.verified is False
    assert descriptor.enforced_requirements == ()
    assert owner.validate_sandbox_verification_receipt(receipt) is receipt
    assert owner.validate_sandbox_descriptor(descriptor, receipt) is descriptor
    assert owner.get_verified_candidate_runtime_sandbox(descriptor, receipt) is None
    assert owner.sandbox_satisfies_executor_boundary(descriptor) is False
    payload = receipt.as_dict()
    for name in ('candidate_execution_count', 'java_execution_count', 'bank_execution_count',
                 'behavioral_scenario_count', 'model_calls', 'author_calls',
                 'repository_traversals', 'source_mutation'):
        assert payload[name] == 0
    for name in ('runtime_authority', 'repository_write_authority', 'apply_authority'):
        assert payload[name] is False


def test_no_argument_lookup_is_pure_and_cannot_implicitly_verify(blocked):
    assert owner.get_verified_candidate_runtime_sandbox() is None


def test_reporting_is_deterministic_and_omits_authentication_secrets(blocked):
    first_descriptor, first_receipt = blocked
    measured = {'total_seconds': 999999.0}
    second_descriptor, second_receipt = owner.verify_candidate_runtime_sandbox(timings=measured)
    assert first_descriptor.fingerprint == second_descriptor.fingerprint
    assert first_receipt.fingerprint == second_receipt.fingerprint
    assert set(measured) == set(owner.TIMING_FIELDS)
    assert measured['total_seconds'] >= 0
    assert all(measured[key] == 0 for key in owner.TIMING_FIELDS if key != 'total_seconds')
    for value in (first_descriptor, first_receipt):
        report = value.as_dict()
        assert '_signature' not in report
        assert not any('seconds' in key for key in report)


@pytest.mark.parametrize('report', (False, True))
def test_caller_forged_descriptor_cannot_create_capability(blocked, report):
    descriptor, receipt = blocked
    forged = replace(descriptor, available=True, verified=True,
        enforced_requirements=owner.MANDATORY_REQUIREMENTS)
    supplied = forged.as_dict() if report else forged
    assert owner.sandbox_satisfies_executor_boundary(supplied) is False
    with pytest.raises(owner.CandidateRuntimeSandboxError) as error:
        owner.get_verified_candidate_runtime_sandbox(supplied, receipt)
    assert error.value.code == 'sandbox_descriptor_unauthenticated'
    assert error.value.candidate_execution_count == 0


def test_caller_receipt_json_is_report_only(blocked):
    descriptor, receipt = blocked
    with pytest.raises(owner.CandidateRuntimeSandboxError) as error:
        owner.validate_sandbox_verification_receipt(receipt.as_dict())
    assert error.value.code == 'sandbox_receipt_unauthenticated'
    with pytest.raises(owner.CandidateRuntimeSandboxError):
        owner.validate_sandbox_descriptor(descriptor, receipt.as_dict())


def test_internal_descriptor_builder_cannot_sign_a_caller_crafted_receipt(blocked):
    _, receipt = blocked
    forged = replace(receipt, status='RUNTIME_SANDBOX_1_COMPLETE_WITH_WARNINGS',
        missing_requirements=())
    with pytest.raises(owner.CandidateRuntimeSandboxError) as error:
        owner._descriptor(forged)
    assert error.value.code == 'sandbox_receipt_unauthenticated'


@pytest.mark.parametrize('change', (
    {'status': 'RUNTIME_SANDBOX_1_COMPLETE_WITH_WARNINGS', 'missing_requirements': ()},
    {'cleanup_outcome': 'all_phase_resources_removed'},
    {'backend': _unavailable_backend('altered-version')},
))
def test_receipt_tampering_cannot_reuse_signature(blocked, change):
    _, receipt = blocked
    altered = replace(receipt, **change)
    with pytest.raises(owner.CandidateRuntimeSandboxError) as error:
        owner.validate_sandbox_verification_receipt(altered)
    assert error.value.code == 'sandbox_receipt_unauthenticated'


def test_exact_descriptor_receipt_pair_is_required(blocked, monkeypatch):
    descriptor, _ = blocked
    monkeypatch.setattr(owner, 'discover_local_sandbox_backend',
        lambda **kwargs: _unavailable_backend('different-installed-version'))
    _, receipt = owner.verify_candidate_runtime_sandbox()
    with pytest.raises(owner.CandidateRuntimeSandboxError) as error:
        owner.validate_sandbox_descriptor(descriptor, receipt)
    assert error.value.code == 'sandbox_descriptor_unauthenticated'


@pytest.mark.parametrize('requirements', ((), ['candidate_network_isolation'],
    ('candidate_network_isolation',), (*owner.MANDATORY_REQUIREMENTS, 'unknown_requirement')))
def test_consumer_cannot_shrink_or_extend_executor_contract(blocked, requirements):
    descriptor, _ = blocked
    assert owner.sandbox_satisfies_executor_boundary(descriptor, requirements) is False


def test_records_are_frozen_and_public_surface_has_no_authority_controls(blocked):
    descriptor, receipt = blocked
    spec = owner.synthetic_probe_spec('boundary')
    for record, name, value in ((descriptor, 'verified', True),
                               (receipt, 'status', 'green'), (spec, 'timeout_ms', 999)):
        with pytest.raises(FrozenInstanceError):
            setattr(record, name, value)
    for kind in (owner.CandidateRuntimeSandboxExecutionSpec,
                 owner.CandidateRuntimeSandboxDescriptor, owner.CandidateRuntimeSandboxAdapter):
        assert not ({'command', 'shell', 'repository_root', 'mounts', 'namespaces',
                     'privileged', 'host_network', 'seccomp_profile'} & {f.name for f in fields(kind)})
    assert descriptor.shell_available is False
    assert descriptor.arbitrary_command_authority is False
    assert descriptor.runtime_authority is descriptor.apply_authority is False


@pytest.mark.parametrize('probe', owner.PROBE_IDS)
def test_closed_synthetic_requests_accept_only_exact_owned_inputs(probe):
    spec = owner.synthetic_probe_spec(probe)
    assert spec.executable_identity == owner.EXECUTABLE_ID
    assert spec.argv == (probe,)
    assert spec.inputs == (owner.ExactSandboxInput('projection.txt', owner._FIXTURE),)
    assert spec.environment == ()


@pytest.mark.parametrize('change,code', (
    ({'executable_identity': '/bin/sh'}, 'sandbox_executable_policy_denied'),
    ({'argv': ('-c', 'touch /host/file')}, 'sandbox_executable_policy_denied'),
    ({'argv': ('bank',)}, 'sandbox_executable_policy_denied'),
    ({'argv': ['boundary']}, 'sandbox_executable_policy_denied'),
    ({'inputs': []}, 'sandbox_input_not_phase_owned'),
    ({'inputs': ()}, 'sandbox_input_not_phase_owned'),
    ({'environment': (('CATTUS_SANDBOX_HOST_ONLY', 'secret'),)}, 'sandbox_environment_policy_denied'),
    ({'environment': []}, 'sandbox_environment_policy_denied'),
    ({'timeout_ms': True}, 'sandbox_bound_invalid'),
    ({'timeout_ms': 249}, 'sandbox_bound_invalid'),
    ({'timeout_ms': 10001}, 'sandbox_bound_invalid'),
    ({'timeout_ms': float('inf')}, 'sandbox_bound_invalid'),
    ({'stdout_limit_bytes': 255}, 'sandbox_bound_invalid'),
    ({'stdout_limit_bytes': 16385}, 'sandbox_bound_invalid'),
    ({'stderr_limit_bytes': False}, 'sandbox_bound_invalid'),
    ({'stderr_limit_bytes': 16385}, 'sandbox_bound_invalid'),
))
def test_closed_request_rejects_arbitrary_effect_surfaces(change, code):
    with pytest.raises(owner.CandidateRuntimeSandboxError) as error:
        replace(owner.synthetic_probe_spec('boundary'), **change)
    assert error.value.code == code


@pytest.mark.parametrize('path,content', (
    ('../projection.txt', owner._FIXTURE), ('/work/projection.txt', owner._FIXTURE),
    ('C:\\host.txt', owner._FIXTURE), ('projection.txt', b'caller-owned-code'),
    ('projection.txt', bytearray(owner._FIXTURE)),
))
def test_exact_input_rejects_host_paths_and_caller_bytes(path, content):
    with pytest.raises(owner.CandidateRuntimeSandboxError) as error:
        owner.ExactSandboxInput(path, content)
    assert error.value.code == 'sandbox_input_not_phase_owned'


@pytest.mark.parametrize('fact,dimension', (
    ('workspace_write', 'ephemeral_working_directory'),
    ('external_read_denied', 'candidate_filesystem_isolation'),
    ('external_write_denied', 'candidate_filesystem_isolation'),
    ('root_write_denied', 'candidate_filesystem_isolation'),
    ('local_connect_denied', 'candidate_network_isolation'),
    ('socketpair_denied', 'candidate_network_isolation'),
    ('host_secret_absent', 'candidate_environment_isolation'),
))
def test_measured_boundary_leak_revokes_its_dimension(fact, dimension):
    facts = _boundary_facts()
    assert dimension in _passed(facts)  # Predicate control only, no evidence issuance.
    facts[fact] = False
    assert dimension not in _passed(facts)


@pytest.mark.parametrize('kind', ('ipv4_tcp', 'ipv6_tcp', 'dns_udp', 'unix_socket'))
def test_any_usable_network_socket_revokes_network_claim(kind):
    facts = _boundary_facts()
    facts['socket_denials'][kind] = False
    assert 'candidate_network_isolation' not in _passed(facts)


def test_environment_must_equal_closed_allowlist_and_sentinel_must_be_absent():
    facts = _boundary_facts()
    facts['environment']['UNAPPROVED_IMAGE_ENV'] = 'extra'
    assert 'candidate_environment_isolation' not in _passed(facts)
    facts = _boundary_facts()
    facts['environment']['CATTUS_SANDBOX_HOST_ONLY'] = 'synthetic-host-only-secret'
    assert 'candidate_environment_isolation' not in _passed(facts)


def test_external_sentinel_change_and_endpoint_activity_fail_measured_claims():
    facts = _boundary_facts()
    assert 'candidate_filesystem_isolation' not in _passed(facts, host_unchanged=False)
    assert 'candidate_network_isolation' not in _passed(facts, quiet=False)


@pytest.mark.parametrize('fact,value', (
    ('uid', 0), ('pid_is_one', False), ('no_new_privileges', False), ('capabilities_zero', False),
))
def test_unprivileged_private_pid_boundary_is_mandatory(fact, value):
    facts = _boundary_facts()
    facts[fact] = value
    assert _passed(facts) == ()


def test_exact_projection_manifest_is_measured():
    for field, value in (('path', '../host'), ('sha256', '0' * 64), ('size_bytes', 0)):
        facts = _boundary_facts()
        facts['manifest'][0][field] = value
        passed = _passed(facts)
        assert 'exact_source_and_classpath' not in passed
        assert 'fixed_executable_and_arguments' not in passed


@pytest.mark.parametrize('probe', owner.PROBE_IDS)
def test_unverified_teardown_revokes_every_probe_claim(probe):
    assert owner._facts_passed(probe, _capture(), _boundary_facts(), False, True, True) == ()


@pytest.mark.parametrize('probe', ('descendant', 'timeout'))
@pytest.mark.parametrize('missing', ('child_spawned', 'child_alive', 'same_namespaces', 'same_cgroup', 'pid_is_one'))
def test_uncontained_or_missing_descendant_proof_never_passes(probe, missing):
    facts = dict.fromkeys(('child_spawned', 'child_alive', 'same_namespaces', 'same_cgroup', 'pid_is_one'), True)
    facts[missing] = False
    captured = _capture('sandbox_timeout', deadline=True) if probe == 'timeout' else _capture()
    assert owner._facts_passed(probe, captured, facts, True, True, True) == ()


@pytest.mark.parametrize('status,deadline', (
    ('sandbox_completed', False), ('sandbox_timeout', False), ('sandbox_control_failure', True),
))
def test_timeout_requires_measured_hard_deadline_and_termination_status(status, deadline):
    facts = dict.fromkeys(('child_spawned', 'child_alive', 'same_namespaces', 'same_cgroup', 'pid_is_one'), True)
    assert 'hard_wall_clock_timeout' not in owner._facts_passed('timeout',
        _capture(status, deadline=deadline), facts, True, True, True)


def test_deadline_event_without_backend_termination_proof_is_incomplete():
    facts = dict.fromkeys(('child_spawned', 'child_alive', 'same_namespaces', 'same_cgroup', 'pid_is_one'), True)
    assert 'hard_wall_clock_timeout' not in owner._facts_passed('timeout',
        _capture('sandbox_timeout', deadline=True, termination=False), facts, True, True, True)


def test_eventual_kill_after_requested_deadline_does_not_prove_hard_timeout():
    facts = dict.fromkeys(('child_spawned', 'child_alive', 'same_namespaces', 'same_cgroup', 'pid_is_one'), True)
    control = owner._facts_passed('timeout',
        _capture('sandbox_timeout', deadline=True), facts, True, True, True)
    assert 'hard_wall_clock_timeout' in control  # Predicate control only.
    passed = owner._facts_passed('timeout',
        _capture('sandbox_timeout', deadline=True, within_deadline=False), facts, True, True, True)
    assert 'hard_wall_clock_timeout' not in passed


@pytest.mark.parametrize('probe', ('stdout', 'stderr'))
@pytest.mark.parametrize('size,status', (
    (8191, 'sandbox_output_limit_exceeded'), (8193, 'sandbox_output_limit_exceeded'),
    (8192, 'sandbox_completed'), (8192, 'sandbox_control_failure'),
))
def test_output_limit_requires_typed_overflow_and_bounded_capture(probe, size, status):
    captured = _capture(status, **{probe: b'X' * size})
    assert 'hard_stdout_stderr_bounds' not in owner._facts_passed(probe,
        captured, {}, True, True, True)


@pytest.mark.parametrize('probe', ('stdout', 'stderr'))
def test_oversized_companion_stream_cannot_pass_combined_output_bound(probe):
    streams = {probe: b'X' * 8192, ('stderr' if probe == 'stdout' else 'stdout'): b'X' * 8193}
    control = owner._facts_passed(probe,
        _capture('sandbox_output_limit_exceeded', **{probe: b'X' * 8192}), {}, True, True, True)
    assert 'hard_stdout_stderr_bounds' in control  # Predicate control, no local backend claim.
    assert 'hard_stdout_stderr_bounds' not in owner._facts_passed(probe,
        _capture('sandbox_output_limit_exceeded', **streams), {}, True, True, True)


@pytest.mark.parametrize('probe', ('stdout', 'stderr'))
def test_output_capture_bound_requires_cleanup_even_if_cutoff_kill_is_unconfirmed(probe):
    captured = _capture('sandbox_output_limit_exceeded', termination=False, **{probe: b'X' * 8192})
    assert 'hard_stdout_stderr_bounds' in owner._facts_passed(probe,
        captured, {}, True, True, True)  # Bounded-memory predicate only, no OS verification claim.
    assert 'hard_stdout_stderr_bounds' not in owner._facts_passed(probe,
        _capture('sandbox_output_limit_exceeded', termination=False, **{probe: b'X' * 8192}),
        {}, False, True, True)


@pytest.mark.parametrize('section,key,value', (
    ('HostConfig', 'Privileged', True), ('HostConfig', 'NetworkMode', 'host'),
    ('HostConfig', 'PidMode', 'host'), ('HostConfig', 'IpcMode', 'host'),
    ('HostConfig', 'CgroupnsMode', 'host'), ('HostConfig', 'ReadonlyRootfs', False),
    ('HostConfig', 'Binds', ['C:/repo:/work']), ('HostConfig', 'Mounts', [{'Source': '/host'}]),
    ('HostConfig', 'CapAdd', ['SYS_ADMIN']), ('HostConfig', 'CapDrop', []),
    ('HostConfig', 'SecurityOpt', ['no-new-privileges=false', 'seccomp=unconfined']),
    ('HostConfig', 'SecurityOpt', ['no-new-privileges=true', 'seccomp=unconfined']),
    ('HostConfig', 'SecurityOpt', ['no-new-privileges=true', 'seccomp=' + owner._json(owner._SECCOMP),
                                 'no-new-privileges=false']),
    ('HostConfig', 'SecurityOpt', ['no-new-privileges=true', 'seccomp=' + owner._json(owner._SECCOMP),
                                 'seccomp=unconfined']),
    ('HostConfig', 'LogConfig', {'Type': 'json-file'}), ('HostConfig', 'PidsLimit', -1),
    ('HostConfig', 'Memory', 0), ('HostConfig', 'NanoCpus', 0),
    ('HostConfig', 'Tmpfs', {'/work': 'rw', '/tmp': 'rw', '/host': 'rw'}),
    ('Config', 'User', '0:0'), ('Config', 'WorkingDir', '/repo'),
    ('Config', 'Entrypoint', ['/bin/sh']), ('Config', 'Cmd', ['-c', 'caller-code']),
    ('Config', 'Env', ['LANG=C.UTF-8', 'CATTUS_SANDBOX_HOST_ONLY=secret']),
))
def test_unsafe_inspected_configuration_is_ineligible_before_launch(section, key, value):
    config = _safe_config()
    config[section][key] = value
    assert owner._safe_configuration(config, config['Image']) is False


def test_image_identity_and_mount_inspection_cannot_be_spoofed_by_flags():
    config = _safe_config()
    assert owner._safe_configuration(config, 'sha256:' + '2' * 64) is False
    config['Mounts'] = [{'Type': 'bind', 'Source': 'C:/repo', 'Destination': '/work'}]
    assert owner._safe_configuration(config, config['Image']) is False


def test_exact_inspected_configuration_is_only_a_prelaunch_eligibility_predicate():
    config = _safe_config()
    assert owner._safe_configuration(config, config['Image']) is True


@pytest.mark.parametrize('probe', owner.PROBE_IDS)
def test_configuration_binds_the_exact_selected_probe(probe):
    config = _safe_config()
    config['Config']['Cmd'][-1] = probe
    assert owner._safe_configuration(config, config['Image'], probe) is True
    config['Config']['Cmd'][-1] = 'caller-probe'
    assert owner._safe_configuration(config, config['Image'], probe) is False


def test_absent_backend_detection_never_launches_fallback(monkeypatch):
    monkeypatch.setattr(owner, '_docker_prefix', lambda: ())
    monkeypatch.setattr(owner.shutil, 'which', lambda name: None)
    def forbidden(*args, **kwargs):
        raise AssertionError('missing Docker must not launch a fallback')
    monkeypatch.setattr(owner, '_bounded_process', forbidden)
    observed = owner.discover_local_sandbox_backend()
    assert observed.cli_present is False
    assert observed.backend_available is False
    assert observed.reason == 'sandbox_backend_unavailable'


def test_detection_uses_fixed_local_endpoint_and_ignores_remote_docker_preferences(monkeypatch):
    monkeypatch.setattr(owner.shutil, 'which', lambda name: 'C:/fixed/docker.exe')
    monkeypatch.setattr(owner, '_local_endpoint', lambda: 'npipe:////./pipe/phase-owned-test')
    monkeypatch.setenv('DOCKER_HOST', 'tcp://remote-host:2375')
    monkeypatch.setenv('DOCKER_CONTEXT', 'remote-context')
    monkeypatch.setenv('DOCKER_CONFIG', 'C:/caller-config')
    prefix = owner._docker_prefix()
    assert prefix[0] == 'C:/fixed/docker.exe'
    assert prefix[-2:] == ('--host', 'npipe:////./pipe/phase-owned-test')
    assert 'C:/caller-config' not in prefix
    assert 'tcp://remote-host:2375' not in prefix
    assert '--config' in prefix


@pytest.mark.parametrize('name', ('docker.exe', 'docker.cmd', 'docker.bat'))
def test_repository_local_docker_cannot_mint_backend_evidence(monkeypatch, name):
    repo = Path(__file__).resolve().parents[1]
    monkeypatch.setattr(owner.shutil, 'which', lambda tool: str(repo / name))
    monkeypatch.setattr(owner, '_local_endpoint', lambda: 'npipe:////./pipe/phase-owned-test')
    assert owner._docker_prefix() == ()


@pytest.mark.skipif(owner.os.name != 'nt', reason='Windows executable suffix policy')
@pytest.mark.parametrize('binary', ('C:/fixed/docker.cmd', 'C:/fixed/docker.bat'))
def test_windows_batch_cli_is_not_a_fixed_native_backend_executable(monkeypatch, binary):
    monkeypatch.setattr(owner.shutil, 'which', lambda tool: binary)
    monkeypatch.setattr(owner, '_local_endpoint', lambda: 'npipe:////./pipe/phase-owned-test')
    assert owner._docker_prefix() == ()


def test_installed_exact_local_image_is_available_without_becoming_verified(monkeypatch):
    prefix = ('C:/fixed/docker.exe', '--host', 'npipe:////./pipe/phase-owned-test')
    monkeypatch.setattr(owner, '_docker_prefix', lambda: prefix)
    monkeypatch.setattr(owner.shutil, 'which', lambda name: prefix[0])
    monkeypatch.setattr(owner, '_local_endpoint', lambda: prefix[-1])
    replies = iter((
        _capture(stdout=b'{"Server":{"Os":"linux","Version":"phase-owned-test"}}'),
        _capture(stdout=owner._json({'Os': 'linux', 'Id': 'sha256:' + 'a' * 64}).encode()),
    ))
    calls = []
    def metadata_only(argv, **kwargs):
        calls.append(tuple(argv))
        return next(replies)
    monkeypatch.setattr(owner, '_bounded_process', metadata_only)
    observed = owner.discover_local_sandbox_backend()
    assert observed.backend_available is True
    assert observed.reason == 'backend_available_not_verified'
    assert observed.image_identity == 'sha256:' + 'a' * 64
    assert observed.backend_version == 'phase-owned-test'
    assert len(calls) == 2
    assert calls[0][len(prefix)] == 'version'
    assert calls[1][len(prefix):len(prefix) + 3] == ('image', 'inspect', owner.LOCAL_IMAGE)
    assert not any(token in ('run', 'start', 'pull', 'build', 'login') for call in calls for token in call)


@pytest.mark.parametrize('failure,reason', (
    ('unreachable', 'sandbox_backend_unavailable_local_engine_unreachable'),
    ('windows', 'backend_not_eligible_non_linux_engine'),
    ('image_missing', 'sandbox_backend_unavailable_exact_local_image_missing'),
    ('mutable_tag', 'backend_not_eligible_image_identity_invalid'),
    ('malformed_metadata', 'sandbox_backend_unavailable_detection_failed'),
))
def test_backend_detection_rejects_missing_or_ineligible_metadata(monkeypatch, failure, reason):
    monkeypatch.setattr(owner, '_docker_prefix', lambda: ('C:/fixed/docker.exe',))
    monkeypatch.setattr(owner.shutil, 'which', lambda name: 'C:/fixed/docker.exe')
    server = _capture(stdout=owner._json({'Server': {'Os': 'windows' if failure == 'windows' else 'linux',
                                                    'Version': 'test'}}).encode())
    image = _capture(stdout=owner._json({'Os': 'linux', 'Id': 'sha256:' + 'a' * 64}).encode())
    if failure == 'unreachable': server = _capture('sandbox_control_failure', exit_code=1)
    if failure == 'image_missing': image = _capture(exit_code=1)
    if failure == 'mutable_tag': image = _capture(stdout=b'{"Os":"linux","Id":"python:latest"}')
    if failure == 'malformed_metadata': server = _capture(stdout=b'caller-authored-not-json')
    replies = iter((server, image))
    monkeypatch.setattr(owner, '_bounded_process', lambda *args, **kwargs: next(replies))
    observed = owner.discover_local_sandbox_backend()
    assert observed.backend_available is False
    assert observed.reason == reason


@pytest.mark.parametrize('metadata', (b'[]', b'null', b'42', b'{"Server":[]}',
    b'{"Server":{"Os":"linux"}}', b'{"Server":{"Os":"linux","Version":""}}'))
def test_valid_json_without_exact_backend_object_and_version_is_unavailable(monkeypatch, metadata):
    monkeypatch.setattr(owner, '_docker_prefix', lambda: ('C:/fixed/docker.exe',))
    monkeypatch.setattr(owner.shutil, 'which', lambda name: 'C:/fixed/docker.exe')
    monkeypatch.setattr(owner, '_bounded_process', lambda *args, **kwargs: _capture(stdout=metadata))
    observed = owner.discover_local_sandbox_backend()
    assert observed.backend_available is False
    assert observed.reason == 'sandbox_backend_unavailable_detection_failed'


@pytest.mark.parametrize('metadata', (b'[]', b'null', b'42'))
def test_valid_json_without_exact_image_object_is_unavailable(monkeypatch, metadata):
    monkeypatch.setattr(owner, '_docker_prefix', lambda: ('C:/fixed/docker.exe',))
    monkeypatch.setattr(owner.shutil, 'which', lambda name: 'C:/fixed/docker.exe')
    replies = iter((_capture(stdout=b'{"Server":{"Os":"linux","Version":"test"}}'),
                    _capture(stdout=metadata)))
    monkeypatch.setattr(owner, '_bounded_process', lambda *args, **kwargs: next(replies))
    observed = owner.discover_local_sandbox_backend()
    assert observed.backend_available is False
    assert observed.reason == 'sandbox_backend_unavailable_detection_failed'


@pytest.mark.parametrize('flood', ('stdout', 'stderr', 'both'))
def test_collectors_bound_infinite_fake_streams_and_disconnect_before_backend_kill(monkeypatch, flood):
    """Exercise readers with an in-memory fake, never issue sandbox evidence."""
    import io
    events = []
    launches = []

    class FakeStream:
        def __init__(self, flooding):
            self.flooding = flooding
            self.read_sizes = []
            self.closed = False
        def read(self, count):
            self.read_sizes.append(count)
            return b'X' * count if self.flooding else b''
        def close(self):
            self.closed = True

    class FakeProcess:
        def __init__(self):
            self.stdin = io.BytesIO()
            self.stdout = FakeStream(flood in ('stdout', 'both'))
            self.stderr = FakeStream(flood in ('stderr', 'both'))
            self.returncode = None
        def poll(self):
            return self.returncode
        def kill(self):
            events.append('disconnect-attached-client')
            self.returncode = -9
        def wait(self, timeout):
            assert self.returncode == -9
            return self.returncode

    process = FakeProcess()
    def fake_launch(argv, **kwargs):
        launches.append((argv, kwargs))
        return process
    def backend_kill():
        assert process.returncode == -9
        events.append('kill-contained-workload')
        return True
    monkeypatch.setattr(owner.subprocess, 'Popen', fake_launch)
    monkeypatch.setenv('UNAPPROVED_SYNTHETIC_HOST_SECRET', 'phase-owned-test-secret')
    captured = owner._bounded_process(('phase-owned-fake-cli',), timeout_ms=1000,
        stdout_limit=256, stderr_limit=384, on_abort=backend_kill)
    assert captured.status == 'sandbox_output_limit_exceeded'
    assert captured.stdout == (b'X' * 256 if flood in ('stdout', 'both') else b'')
    assert captured.stderr == (b'X' * 384 if flood in ('stderr', 'both') else b'')
    assert events == ['disconnect-attached-client', 'kill-contained-workload']
    assert len(launches) == 1
    assert launches[0][1]['shell'] is False
    assert 'UNAPPROVED_SYNTHETIC_HOST_SECRET' not in launches[0][1]['env']
    assert set(launches[0][1]['env']) <= {'SystemRoot', 'WINDIR', 'CATTUS_SANDBOX_HOST_ONLY'}
    assert captured.termination_verified is True
    assert process.stdout.closed and process.stderr.closed
    for stream in (process.stdout, process.stderr):
        assert max(stream.read_sizes) == 256
        assert len(stream.read_sizes) <= 2


def test_natural_completion_within_original_bound_does_not_require_cutoff_kill(monkeypatch):
    import io
    class FinishedProcess:
        returncode = 0
        stdin = io.BytesIO()
        stdout = io.BytesIO(b'phase-owned-result')
        stderr = io.BytesIO()
        def poll(self):
            return 0
        def wait(self, timeout):
            return 0
        def kill(self):
            raise AssertionError('completed process must not be killed')
    def forbidden_abort():
        raise AssertionError('completed process must not enter cutoff cleanup')
    monkeypatch.setattr(owner.subprocess, 'Popen', lambda *args, **kwargs: FinishedProcess())
    captured = owner._bounded_process(('phase-owned-fake-cli',), timeout_ms=1000,
        stdout_limit=256, stderr_limit=256, on_abort=forbidden_abort)
    assert captured.status == 'sandbox_completed'
    assert captured.stdout == b'phase-owned-result'
    assert captured.deadline_triggered is False
    assert captured.termination_within_deadline is True


def test_maintenance_reverses_only_exact_additive_bookkeeping():
    from tests._runtime_sandbox1_maintenance import before_runtime_sandbox1
    import json
    base = Path(__file__).resolve().parents[1]
    fixture = json.loads((base / 'tests/fixtures/runtime_sandbox1_reversal.json').read_text(encoding='utf-8'))
    for record in fixture['reversals']:
        content = (base / record['path']).read_bytes()
        restored = before_runtime_sandbox1(record['path'], content)
        assert sha256(restored).hexdigest() == record['entry_sha256']
        with pytest.raises(AssertionError):
            before_runtime_sandbox1(record['path'], content + b'\n# unattributed mutation\n')
    untouched = b'untouched-history'
    assert before_runtime_sandbox1('core/behavioral_diagnostic_executor.py', untouched) == untouched
