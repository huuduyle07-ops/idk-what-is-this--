"""Measure the JAVA.1D backend-provenance stop gate; issue no provider receipt.

The frozen SANDBOX.2 API lacks backend identity/version witnesses. The live
replay authenticates its existing owner objects, records that blocker and stops
before artifact discovery or JAVA.1C positive verification.
"""
import argparse
from dataclasses import fields
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core import candidate_runtime_sandbox as baseline
from core import sandboxed_java_positive_continuation as java1c
from core import sandboxed_java_toolchain_discovery as discovery
from core import thread_compatible_runtime_sandbox as sandbox2

PHASE_ID = 'RUNTIME.JAVA.1D'
SCHEMA_VERSION = 'runtime_java_1d_v1'
BACKEND_BINDING = 'RUNTIME_JAVA_1D_BLOCKED_BACKEND_BINDING'
BACKEND_FRESHNESS = 'RUNTIME_JAVA_1D_BLOCKED_BACKEND_FRESHNESS'
UNRESOLVED = 'RUNTIME_JAVA_1D_BLOCKED_UNRESOLVED'
CLEANUP = 'RUNTIME_JAVA_1D_BLOCKED_CLEANUP'
POLICY_SHA256 = '5a36bdf1676c4b0d7b4bef489f5e90b5c8fb201b5194be48baf61f4206a81f75'
BACKEND_FIELDS = ('backend_identity', 'backend_version')


def assess_authenticated_backend(descriptor, receipt):
    """Pure stop gate. Authentic owner objects alone can reach API inspection."""
    java1c.authenticate_sandbox2(descriptor, receipt)
    if (descriptor.phase_id != 'RUNTIME.SANDBOX.2'
            or descriptor.schema_version != 'runtime_sandbox_2_v1'
            or receipt.schema_version != 'runtime_sandbox_2_v1'
            or receipt.seccomp_policy_sha256 != POLICY_SHA256):
        raise ValueError('java1d_exact_sandbox2_identity_required')
    names = {role: tuple(f.name for f in fields(value) if f.name != '_signature')
        for role, value in (('descriptor', descriptor), ('receipt', receipt))}
    missing = [role + '.' + key for role in names for key in BACKEND_FIELDS
        if key not in names[role]]
    return {
        'status': BACKEND_BINDING if missing else BACKEND_FRESHNESS,
        'reason': ('sandbox2_authenticated_backend_identity_and_version_unavailable'
            if missing else 'sandbox2_backend_freshness_protocol_unproven'),
        'sandbox2_authenticated': True,
        'sandbox_descriptor_fingerprint': descriptor.fingerprint,
        'sandbox_receipt_fingerprint': receipt.fingerprint,
        'sandbox2_public_authenticated_fields': names,
        'missing_backend_witnesses': missing,
        'sandbox_backend_identity': None,
        'sandbox_backend_version': None,
        'backend_binding_result': 'unproven',
        'backend_freshness_result': 'unproven',
    }


def replay():
    """Only the frozen SANDBOX.2 infrastructure ladder may run, with no inputs."""
    report = {
        'phase_id': PHASE_ID, 'schema_version': SCHEMA_VERSION,
        'status': UNRESOLVED, 'reason': 'fresh_sandbox2_not_authenticated',
        'seccomp_policy_sha256': POLICY_SHA256,
        'sandbox2_authenticated': False, 'fresh_sandbox2_authenticated': False,
        'fresh_java1c_authenticated': False, 'java1c_verification_attempted': False,
        'complete_inventory': None, 'inventory_count': None,
        'inventory_sha256': None, 'artifact_inventory': None,
        'discovery_backend_identity': None, 'discovery_backend_version': None,
        'sandbox_backend_identity': None, 'sandbox_backend_version': None,
        'backend_binding_result': 'unproven', 'backend_freshness_result': 'unproven',
        'selected_image_membership': None, 'inventory_java1c_coherence': 'unproven',
        'java1d_receipt_fingerprint': None, 'provider_receipt_issued': False,
        'runtime_java_1_v1_identity_asserted': False, 'compatibility_asserted': False,
        'compatibility_relation_count': 0, 'exported_json_is_report_only': True,
        **dict.fromkeys(sandbox2.AUTHORITIES, False),
        'discovery_attempted': False,
        'discovery_domain': {
            'owner': 'core/sandboxed_java_toolchain_discovery.py:discover_local_java_artifacts',
            'endpoint': 'frozen owner fixed local Docker endpoint only',
            'inventory_command': ['image', 'ls', '--all', '--no-trunc', '--quiet'],
            'identity_semantics': 'sorted unique immutable sha256 image IDs; no tag requirement',
            'sources': list(discovery.LocalJavaDiscovery((), False, True, '').discovery_sources),
            'inspection': 'all local image metadata; bounded stopped-container exports for linux/amd64 images without declared volumes',
            'max_archive_bytes': discovery.MAX_ARCHIVE_BYTES,
            'max_archive_entries': discovery.MAX_ARCHIVE_ENTRIES,
            'max_executable_bytes': discovery.MAX_EXECUTABLE_BYTES,
            'export_timeout_ms': discovery.EXPORT_TIMEOUT_MS,
            'docker_control_stdout_limit_bytes': 65536,
            'performed': False,
        },
        'required_java1c_identity': {
            'phase_id': java1c.PHASE_ID, 'schema_version': java1c.SCHEMA_VERSION,
            'image_identity': java1c.IMAGE,
            'java_path': java1c.probe.JAVA_PATH, 'java_sha256': java1c.probe.JAVA_SHA256,
            'javac_path': java1c.probe.JAVAC_PATH, 'javac_sha256': java1c.probe.JAVAC_SHA256,
            'freshly_verified': False,
        },
    }
    calls = []
    invoke = baseline._bounded_process

    def observed(argv, **kwargs):
        # Observe only. Forward unchanged argv/options to the frozen owner.
        row = {'command': list(argv[5:7]), 'completed': False, 'exit_code': None}
        calls.append(row)
        result = invoke(argv, **kwargs)
        row.update(completed=result.status == 'sandbox_completed', exit_code=result.exit_code)
        return result

    live = None
    try:
        with patch.object(baseline, '_bounded_process', observed):
            # Existing JAVA.1C owner helper obtains SANDBOX.2 live, reissues
            # through its original issuer, and calls the public validator.
            # It performs no JAVA.1C compile/run and accepts no report input.
            descriptor, receipt, live = java1c._obtain_live_sandbox2()
            report.update(assess_authenticated_backend(descriptor, receipt))
            report['fresh_sandbox2_authenticated'] = True
    except (OSError, ValueError, TypeError, AttributeError, KeyError) as error:
        report['controller_error'] = type(error).__name__ + ': ' + str(error)[:250]
    report['docker_control_calls'] = calls
    report['effects'] = {
        'docker_calls': len(calls),
        'docker_discovery_calls': sum(r['command'][:1] == ['version']
            or r['command'] == ['image', 'ls'] for r in calls),
        'docker_inspect_calls': sum(r['command'][:1] == ['inspect']
            or r['command'] == ['image', 'inspect'] for r in calls),
        'container_create_attempts': sum(r['command'][:1] == ['create'] for r in calls),
        'containers_created': sum(r['command'][:1] == ['create']
            and r['completed'] and r['exit_code'] == 0 for r in calls),
        'host_docker_child_process_calls': len(calls),
        **dict.fromkeys(('source_projections', 'java1c_compile_executions',
            'java1c_fixture_executions', 'synth_runtime_lease_consumptions',
            'reflection_lease_consumptions', 'bank_executions', 'executor1r_retries',
            'repository_runtime_writes', 'apply_actions', 'shell_calls', 'host_mounts',
            'network_calls', 'outbound_network_calls', 'artifact_pulls', 'artifact_builds'), 0),
    }
    if live is not None:
        report['live_sandbox2'] = live
        report['cleanup_verified'] = live['cleanup_verified']
        report['remaining_phase_containers'] = live['phase_container_count_after_teardown']
        report['effects'].update(
            javac_executions=live['javac_version_count'],
            java_executions=live['java_version_count'],
            compile_executions=live['compile_count'],
            java_fixture_executions=live['jvm_fixture_count'],
            sandbox_projected_data_fixtures=sum(s['mode'] in ('boundary', 'controller')
                and s['verdict'] == sandbox2.PASSED for s in live['stages']),
            container_child_processes=sum(
                int(s['facts'].get('child_spawned') is True)
                + s['facts'].get('toolchain_launch_count', 0) for s in live['stages']),
            host_local_listener_sockets=2)
        report['effects']['sandbox_controller_processes'] = sum(
            r['command'][:1] == ['start'] for r in calls)
        report['effects']['child_processes'] = (len(calls)
            + report['effects']['sandbox_controller_processes']
            + report['effects']['container_child_processes'])
        report['effects']['child_process_count_scope'] = (
            'host Docker CLI calls + sandbox controller starts + measured in-sandbox descendants; '
            'development validation processes excluded')
        if live['cleanup_verified'] is not True:
            report['status'], report['reason'] = CLEANUP, 'fresh_sandbox2_cleanup_not_verified'
    else:
        # The owner may have failed after effects; never invent cleanup/counts.
        report['cleanup_verified'] = None
        report['remaining_phase_containers'] = None
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = replay()
    if args.output:
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n',
            encoding='utf-8', newline='\n')
    print(json.dumps({key: result.get(key) for key in ('phase_id', 'status', 'reason',
        'fresh_sandbox2_authenticated', 'missing_backend_witnesses',
        'provider_receipt_issued', 'cleanup_verified', 'effects')}, indent=2))
    sys.exit(1)
