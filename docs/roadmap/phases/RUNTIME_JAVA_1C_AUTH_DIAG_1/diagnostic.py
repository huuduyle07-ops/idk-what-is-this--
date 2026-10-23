"""One diagnostic observation of frozen JAVA.1C; never an authority adapter.

The profile callback reads only original arguments/return frames. It never
assigns owner functions, frame locals, arguments, receipts, or return values.
Original objects remain in this interpreter and exports omit signatures.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
from types import FunctionType

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
from core import candidate_runtime_sandbox as baseline
from core import sandboxed_java_positive_continuation as java
from core import thread_compatible_runtime_sandbox as sandbox

PHASE = 'RUNTIME.JAVA.1C.AUTH.DIAG.1'


def write_json(name, value):
    (HERE / name).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n',
                            encoding='utf-8', newline='\n')


def instrumentation():
    hooks = {'sys_profile': sys.getprofile(), 'sys_trace': sys.gettrace(),
             'thread_profile': threading.getprofile(),
             'thread_trace': threading.gettrace()}
    if hasattr(sys, 'monitoring'):
        hooks.update({f'monitoring_{i}': sys.monitoring.get_tool(i) for i in range(6)})
    return {name: value is not None for name, value in hooks.items()}


def owner_snapshot():
    # Keep identities, not key material; detect namespace replacement too.
    return {module.__name__: {
        name: {'object_id': id(value), 'code_id': id(value.__code__) if isinstance(value, FunctionType) else None,
               'public_policy_digest': hashlib.sha256(baseline._json(value).encode()).hexdigest()
                   if name in ('POLICY', '_SECCOMP') else None}
        for name, value in vars(module).items()
        if isinstance(value, (FunctionType, type)) or name in
        ('_SECRET', 'POLICY', '_SECCOMP', 'POLICY_BYTES', 'POLICY_SHA256', 'IMAGE', 'LADDER', 'AUTHORITIES')
    } for module in (baseline, sandbox, java)}


def process_state():
    return {'current_pid': os.getpid(), 'instrumentation': instrumentation(),
            'tempfile_tempdir_global': tempfile.tempdir,
            'owner_modules': {m.__name__: {'module_id': id(m), 'file': str(Path(m.__file__).resolve())}
                              for m in (baseline, sandbox, java)},
            'owner_entry_points': {m.__name__ + '.' + name: {
                'function_id': id(value), 'code_id': id(value.__code__),
                'qualified_name': value.__qualname__, 'code_file': value.__code__.co_filename}
                for m in (baseline, sandbox, java) for name, value in vars(m).items()
                if isinstance(value, FunctionType) and name in ('verify', 'replay', 'authenticate_sandbox2',
                    '_docker_prefix', '_bounded_process', 'validate_descriptor', 'validate_receipt')},
            'authentication_domain': {
                'owner': sandbox.__name__, 'identity_class': type(sandbox._SECRET).__name__,
                'algorithm': 'HMAC-SHA256', 'lifetime': 'module import in this interpreter',
                'key_material_exported': False},
            'registry': {'present': False, 'public_membership_api': False,
                         'size': None, 'identities': None,
                         'reason': 'Frozen SANDBOX.2 has no live pair registry.'}}


def preserved():
    original = json.loads((HERE / 'preservation_baseline.json').read_text(encoding='utf-8'))['files']
    changed = []
    for name, expected in original.items():
        path = ROOT / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            changed.append(name)
    return {'files_checked': len(original), 'changed_or_missing': changed, 'passed': not changed}


class ObservationUnavailable(RuntimeError):
    pass


class PairObserver:
    def __init__(self):
        self.pairs = []
        self.live = None
        self.controls = []
        self.prefixes = []
        self.workspaces = []
        self.java_invocations = []
        self.instrumentation_restored = False
        self.callback_errors = []
        self.forbidden_owner_calls = []
        self._active_controls = {}
        self._codes = {
            'authenticate': java.authenticate_sandbox2.__code__,
            'replay': sandbox.replay.__code__,
            'prefix': baseline._docker_prefix.__code__,
            'control': baseline._bounded_process.__code__,
            'invoke': java._invoke.__code__,
            'verify': java.verify.__code__,
        }

    def __enter__(self):
        if any(instrumentation().values()):
            raise ObservationUnavailable('diagnostic-observation-unavailable:instrumentation_already_owned')
        self.before = instrumentation()
        self._previous = sys.getprofile()
        sys.setprofile(self._observe)
        return self

    def _scope(self, frame):
        codes = []
        while frame is not None:
            codes.append(frame.f_code)
            frame = frame.f_back
        if self._codes['invoke'] in codes:
            return 'JAVA1C_fixed_controller'
        if sandbox.invoke.__code__ in codes or self._codes['replay'] in codes:
            return 'JAVA1C_SANDBOX2_infrastructure'
        return 'JAVA1C_controls'

    def _observe(self, frame, event, result):
        code = frame.f_code
        if event == 'call' and frame.f_globals.get('__name__') in (
                'core.synthetic_runtime_authorization', 'core.synthetic_runtime_authorization_pinned',
                'core.synthetic_runtime_authorization_lifecycle', 'core.synthetic_read_only_reflection',
                'core.synthetic_reflection_execution_admission', 'core.synthetic_reflection_execution_lifecycle',
                'core.behavioral_diagnostic_executor', 'core.behavioral_diagnostic_executor_retry',
                'core.behavioral_diagnostic_executor_lifecycle_retry', 'core.runtime_java_pinned_provider',
                'core.runtime_java_pinned_target_archive', 'core.runtime_java_pinned_backend_target_binding',
                'core.sandbox_backend_binding'):
            self.forbidden_owner_calls.append(frame.f_globals['__name__'] + '.' + code.co_name)
        if code not in self._codes.values():
            return
        # Failure of observation is reported without replacing owner behavior.
        try:
            if code is self._codes['authenticate'] and event == 'call':
                if not self.pairs:
                    self.pairs.append((frame.f_locals['descriptor'], frame.f_locals['receipt']))
            elif code is self._codes['prefix'] and event == 'return' and result:
                self.prefixes.append({'prefix': result,
                    'absent_at_generation': not Path(result[2]).exists() and not Path(result[2]).is_symlink()})
            elif code is self._codes['control'] and event == 'call':
                argv = frame.f_locals['argv']
                row = {'argv': argv, 'scope': self._scope(frame),
                       'config_absent_before': not Path(argv[2]).exists() and not Path(argv[2]).is_symlink()}
                self.controls.append(row)
                self._active_controls[id(frame)] = row
            elif code is self._codes['control'] and event == 'return':
                row = self._active_controls.pop(id(frame))
                process = frame.f_locals.get('process')
                streams = [getattr(process, name, None) for name in ('stdin', 'stdout', 'stderr')]
                row.update(status=getattr(result, 'status', None),
                           exit_code=getattr(result, 'exit_code', None),
                           process_reaped=process is not None and process.returncode is not None,
                           pipes_closed=all(s is not None and s.closed for s in streams),
                           readers_surviving=sum(r.is_alive() for r in frame.f_locals.get('readers', ())))
            elif code is self._codes['replay'] and event == 'return':
                self.live = result if result is not None else frame.f_locals.get('result')
                if 'root' in frame.f_locals:
                    self.workspaces.append(frame.f_locals['root'])
            elif code is self._codes['invoke'] and event == 'return':
                self.java_invocations.append({name: frame.f_locals.get(name) for name in
                    ('name', 'cleanup', 'inspected_ok')})
            elif code is self._codes['verify'] and event == 'return':
                if 'root' in frame.f_locals:
                    self.workspaces.append(frame.f_locals['root'])
        except Exception as error:
            self.callback_errors.append(type(error).__name__ + ':' + str(error)[:200])

    def __exit__(self, exc_type, exc, traceback):
        sys.setprofile(self._previous)
        self.instrumentation_restored = instrumentation() == self.before
        return False

    def export_controls(self):
        rows = []
        for row in self.controls:
            argv = row['argv']
            command = argv[5] if len(argv) > 5 else None
            exported = {key: value for key, value in row.items() if key != 'argv'}
            exported.update(command=command, private_config_path=argv[2], shell=False)
            # Never export the complete command's inline sources or environment.
            if command == 'create':
                exported.update(container_name=argv[argv.index('--name') + 1],
                    network_none=argv[argv.index('--network') + 1] == 'none',
                    pull_never=argv[argv.index('--pull') + 1] == 'never',
                    host_mounts=any(a in ('--mount', '--volume', '-v') for a in argv))
            elif command in ('inspect', 'start', 'kill', 'rm'):
                exported['container_name'] = next((a for a in argv if a.startswith(('runtime-sandbox2-', 'runtime-java1c-'))), None)
            elif command == 'image':
                exported.update(image_subcommand=argv[6], image_identity=argv[7])
            rows.append(exported)
        return rows


def check_observer():
    import pure_matrix as pure
    before = owner_snapshot()
    sd, sr = sandbox._evidence_pair({'status': sandbox.COMPLETE,
        'stages': [{'mode': m, 'verdict': sandbox.PASSED} for m in sandbox.LADDER],
        'cleanup_verified': True})
    with PairObserver() as observer:
        assert java.authenticate_sandbox2(sd, sr) == (sd, sr)
    assert observer.pairs[0][0] is sd and observer.pairs[0][1] is sr
    assert observer.instrumentation_restored and not observer.callback_errors
    original_profile = sys.getprofile()
    original_trace = sys.gettrace()
    rejected = []
    try:
        sys.setprofile(lambda *args: None)
        try:
            with PairObserver():
                raise AssertionError('preexisting profile was accepted')
        except ObservationUnavailable:
            rejected.append('profile')
    finally:
        sys.setprofile(original_profile)
    try:
        sys.settrace(lambda *args: None)
        try:
            with PairObserver():
                raise AssertionError('preexisting trace was accepted')
        except ObservationUnavailable:
            rejected.append('trace')
    finally:
        sys.settrace(original_trace)
    assert before == owner_snapshot()
    result = {'passed': True, 'exact_original_pair_retained': True,
              'preexisting_instrumentation_rejected': rejected,
              'restoration_passed': instrumentation() == observer.before,
              'owner_mutation_occurred': False, 'Docker_effects': 0, 'Java_effects': 0,
              'historical_preservation': preserved()}
    assert result['historical_preservation']['passed']
    write_json('observer_checks.json', result)
    write_json('predicate_ledger.json', pure.predicate_ledger())
    print(json.dumps(result))


def original_pair_export(sd, sr):
    def value(obj):
        return {'exact_type': type(obj).__module__ + '.' + type(obj).__qualname__,
                'object_id_decimal': id(obj), 'object_id_hex': hex(id(obj)),
                'issuing_pid_exposed': getattr(obj, 'issuing_pid', None),
                'signed_public_fields': obj.as_dict()}
    public_result = {}
    for name, operation in (
        ('receipt', lambda: sandbox.validate_receipt(sr)),
        ('descriptor_and_pair', lambda: sandbox.validate_descriptor(sd, sr)),
        ('JAVA1C_semantic_gate', lambda: java.authenticate_sandbox2(sd, sr))):
        try:
            operation()
            public_result[name] = {'result': 'PASS'}
        except (ValueError, TypeError, AttributeError) as error:
            public_result[name] = {'result': 'FAIL', 'error': str(error)}
    # HMAC checks are separately observable in the retained issuing process.
    import hmac
    hmac_results = {'receipt': hmac.compare_digest(sr._signature, sandbox._sign(sr)),
                    'descriptor': hmac.compare_digest(sd._signature, sandbox._sign(sd))}
    return {'descriptor': value(sd), 'receipt': value(sr),
            'observed_pid': os.getpid(), 'public_validators': public_result,
            'HMAC_results': hmac_results,
            'demonstrated_HMAC_failure': not all(hmac_results.values()),
            'semantic_eligibility': sd.eligible_for_java1_continuation,
            'registry_membership': 'NOT_APPLICABLE:no registry in frozen owner'}


def live_attempt():
    import pure_matrix as pure
    matrix = json.loads((HERE / 'pure_matrix.json').read_text(encoding='utf-8'))
    observer_check = json.loads((HERE / 'observer_checks.json').read_text(encoding='utf-8'))
    assert matrix['passed'] and observer_check['passed'], 'pure gates must pass before live effects'
    assert preserved()['passed'], 'historical drift from diagnostic baseline'
    assert not any(instrumentation().values()), 'diagnostic-observation-unavailable'
    marker = HERE / 'LIVE_ATTEMPT_STARTED.json'
    # Exclusive marker survives failure and prevents a second invocation.
    with marker.open('x', encoding='utf-8') as stream:
        json.dump({'phase_id': PHASE, 'utc': datetime.now(timezone.utc).isoformat(),
                   'pid': os.getpid(), 'maximum_standalone_invocations': 1}, stream)
        stream.write('\n')
    before = owner_snapshot()
    state_before = process_state()
    observer = PairObserver()
    with observer:
        jd, jr, report = java.verify()  # The sole effectful owner invocation.
    state_after = process_state()
    # Retain the observation before any downstream diagnostic formatting.
    write_json('JAVA1C_standalone_report.json', report)
    write_json('SANDBOX2_observed_report.json', observer.live)
    controls = observer.export_controls()
    write_json('observed_controls.json', controls)
    pair = None
    decomposition = None
    diagnostic_errors = []
    if observer.pairs:
        sd, sr = observer.pairs[0]
        pair = original_pair_export(sd, sr)
        write_json('fresh_pair_observation.json', pair)
        try:
            decomposition = pure.decompose_pair(sd, sr, observer.live)
        except Exception as error:
            diagnostic_errors.append(type(error).__name__ + ':' + str(error)[:300])
    creates = [row for row in controls if row['command'] == 'create']
    sandbox_stages = observer.live.get('stages', []) if isinstance(observer.live, dict) else []
    failed_stage = next((row for row in sandbox_stages if row['verdict'] != sandbox.PASSED), None)
    configs = [{'path': row['prefix'][2], 'absent_at_generation': row['absent_at_generation'],
                'absent_after': not Path(row['prefix'][2]).exists() and not Path(row['prefix'][2]).is_symlink()}
               for row in observer.prefixes]
    cleanup = {'owner_cleanup_verified': report['cleanup_verified'],
               'remaining_phase_containers': report['phase_container_count_after_teardown'],
               'SANDBOX2_cleanup_verified': observer.live.get('cleanup_verified') if isinstance(observer.live, dict) else None,
               'all_host_controls_reaped': bool(controls) and all(c.get('process_reaped') for c in controls),
               'all_host_control_pipes_closed': bool(controls) and all(c.get('pipes_closed') for c in controls),
               'surviving_host_readers': sum(c.get('readers_surviving', 0) for c in controls),
               'observer_restored': observer.instrumentation_restored,
               'private_config_paths': configs,
               'all_private_config_paths_absent': bool(configs) and all(c['absent_at_generation'] and c['absent_after'] for c in configs)
                   and all(c['config_absent_before'] for c in controls),
               'temporary_workspaces': [{'path': str(p), 'removed': not Path(p).exists()} for p in observer.workspaces],
               'temporary_workspace_removed': all(not Path(p).exists() for p in observer.workspaces)
                   and report['temporary_workspace_removed']}
    cleanup['passed'] = all(cleanup[k] is True for k in ('owner_cleanup_verified',
        'SANDBOX2_cleanup_verified', 'all_host_controls_reaped', 'all_host_control_pipes_closed',
        'observer_restored', 'all_private_config_paths_absent', 'temporary_workspace_removed'))
    cleanup['passed'] = cleanup['passed'] and cleanup['remaining_phase_containers'] == 0 and cleanup['surviving_host_readers'] == 0
    passed = report['status'] == java.COMPLETE
    preservation = preserved()
    classification = 'STANDALONE_PASS_CONTEXT_SENSITIVE' if passed else (
        'SEMANTIC_ELIGIBILITY_FAILURE' if pair and all(pair['HMAC_results'].values())
        and pair['public_validators']['descriptor_and_pair']['result'] == 'PASS'
        and pair['public_validators']['JAVA1C_semantic_gate']['result'] == 'FAIL'
        else 'UNRESOLVED')
    result = {'phase_id': PHASE, 'diagnostic_only': True,
        'status': 'JAVA1C_AUTH_DIAG_COMPLETE_WITH_FINDING' if pair and not observer.callback_errors else 'diagnostic-observation-unavailable',
        'classification': classification, 'standalone_JAVA1C_status': report['status'],
        'standalone_JAVA1C_passed': passed, 'nested_context_sensitivity_implicated': passed,
        'standalone_invocations': 1, 'fresh_SANDBOX2_pair': pair,
        'predicate_decomposition': decomposition, 'first_failed_SANDBOX2_stage': failed_stage,
        'SANDBOX2_status': observer.live.get('status') if isinstance(observer.live, dict) else None,
        'process_state_before': state_before, 'process_state_after': state_after,
        'observer_callback_errors': observer.callback_errors,
        'diagnostic_errors': diagnostic_errors,
        'forbidden_owner_calls_observed': observer.forbidden_owner_calls,
        'owner_mutation_occurred': before != owner_snapshot(),
        'JAVA1C_source_changed': 'core/sandboxed_java_positive_continuation.py' in preservation['changed_or_missing'],
        'SANDBOX2_source_changed': 'core/thread_compatible_runtime_sandbox.py' in preservation['changed_or_missing'],
        'SYNTH_authorization_retried': False, 'provider_root_issued': False,
        'operational_effects': {
            **dict.fromkeys(('SyntheticStateBox', 'reflection', 'BANK', 'EXECUTOR.1R', 'Apply',
                'repository_runtime_writes', 'runtime_lease_consumption', 'reflection_lease_consumption',
                'arbitrary_Java', 'caller_shell', 'host_mounts', 'outbound_workload_network',
                'generic_image_inventory', 'alternative_provider_inspection', 'PINNED1A_export', 'BIND1'), 0),
            'SANDBOX2_fixed_probe_containers': sum(c['scope'] == 'JAVA1C_SANDBOX2_infrastructure' for c in creates),
            'JAVA1C_fixed_controller_containers': sum(c['scope'] == 'JAVA1C_fixed_controller' for c in creates),
            'SANDBOX2_javac_version_probes': observer.live.get('javac_version_count', 0) if isinstance(observer.live, dict) else None,
            'SANDBOX2_java_version_probes': observer.live.get('java_version_count', 0) if isinstance(observer.live, dict) else None,
            'JAVA1C_compile_count': report['compile_count'], 'JAVA1C_JVM_probe_count': report['jvm_fixture_count'],
            'Docker_controls': len(controls)},
        'zero_effect_counter_basis': 'Frozen source hashes, standalone call graph, original Docker argv observations, '
            'shell=False controls, and zero observed forbidden owner calls; these are infrastructure observations, '
            'not a claim of OS-wide event tracing.',
        'all_authority_fields': dict.fromkeys(sandbox.AUTHORITIES, False),
        'cleanup': cleanup, 'cleanup_failure_separate_from_diagnosis': not cleanup['passed'],
        'historical_preservation': preservation, 'stop_after_diagnosis': True}
    if (result['owner_mutation_occurred'] or result['observer_callback_errors']
            or observer.forbidden_owner_calls or not observer.instrumentation_restored
            or not preservation['passed'] or diagnostic_errors):
        result['classification'] = 'OBSERVATION_INTERFERENCE'
        result['status'] = 'diagnostic-observation-unavailable'
    if pair is None:
        result['failure_before_pair_capture'] = report.get('controller_error')
    write_json('JAVA1C_standalone_report.json', report)
    write_json('SANDBOX2_observed_report.json', observer.live)
    write_json('observed_controls.json', controls)
    write_json('RUNTIME_JAVA_1C_AUTH_DIAG_1_REPORT.json', result)
    print(json.dumps({key: result[key] for key in ('status', 'classification',
        'standalone_JAVA1C_status', 'SANDBOX2_status', 'owner_mutation_occurred',
        'cleanup_failure_separate_from_diagnosis', 'operational_effects')}))
    # No originals are exported as an authenticated root, and interpreter exits.


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('check-observer', 'live'))
    args = parser.parse_args()
    if args.mode == 'check-observer':
        check_observer()
    else:
        live_attempt()
