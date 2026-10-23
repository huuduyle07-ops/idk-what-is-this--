"""Local adversarial sandbox verification. No BANK, runtime consent or Java."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import candidate_runtime_sandbox as owner


def replay(repetitions=1):
    if type(repetitions) is not int or not 1 <= repetitions <= 3:
        raise ValueError('one to three bounded infrastructure repetitions required')
    samples, records, diagnostics = [], [], []
    for _ in range(repetitions):
        timing, diagnostic = {}, {}
        descriptor, receipt = owner.verify_candidate_runtime_sandbox(timings=timing, diagnostics=diagnostic)
        owner.validate_sandbox_descriptor(descriptor, receipt)
        samples.append(timing); records.append(receipt); diagnostics.append(diagnostic)
        # No repeat of a failed or unavailable boundary; retain diagnostic evidence.
        if not descriptor.verified: break
    return {'phase_id': owner.PHASE_ID, 'status': receipt.status,
        'descriptor': descriptor.as_dict(), 'verification_receipt': receipt.as_dict(),
        'executor_boundary_compatible': owner.sandbox_satisfies_executor_boundary(descriptor),
        'semantic_fingerprints': [record.fingerprint for record in records],
        'deterministic': len({record.fingerprint for record in records}) == 1,
        'repetitions_measured': len(records),
        'determinism_scope': 'same backend image/version, contract, canonical facts and bounds; excludes durations/temp/PID IDs',
        'performance': {name: {'median_ms': round(statistics.median(s[name] for s in samples) * 1000, 3),
                              'max_ms': round(max(s[name] for s in samples) * 1000, 3)}
                        for name in owner.TIMING_FIELDS},
        'operational_diagnostics': diagnostics,
        'effect_claim_scope': 'configured OS/backend effect boundary passed these V1 synthetic probes only',
        'java_runtime_in_image': False, 'candidate_java_containment_executed': False,
        'backend_policy': {'local_image_only': True, 'pull': 'never', 'shell_surface': False,
            'host_mounts': [], 'repository_exposure': 'none', 'privileged': False,
            'host_network': False, 'host_pid': False, 'uid': '65534:65534',
            'cap_drop': 'ALL', 'no_new_privileges': True, 'network': 'none',
            'socket_syscalls': 'fixed_seccomp_deny', 'log_driver': 'none',
            'root_filesystem': 'read_only', 'workspace': '32MiB tmpfs, removed after each probe',
            'environment': 'closed explicitly supplied values; unknown image defaults rejected',
            'descendants': 'private PID/mount/network/ipc/cgroup namespaces, bounded cgroup, destroyed at teardown',
            'resource_settings': {'memory_bytes': 134217728, 'cpus': 1, 'pids': 128},
            'resource_limit_exhaustion_verified': False},
        'bank_execution_count': 0, 'java_candidate_execution_count': 0,
        'behavioral_scenario_count': 0, 'model_calls': 0, 'author_calls': 0,
        'repository_traversals': 0, 'source_mutation_count': 0,
        'runtime_authority': False, 'write_authority': False, 'apply_authority': False,
        'first_remaining_blocker': receipt.missing_requirements[0] if receipt.missing_requirements else
            'executor_refresh_and_exact_java_runtime_integration_not_in_this_phase'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repetitions', type=int, default=1)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = replay(args.repetitions)
    if args.output:
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({key: result[key] for key in ('phase_id', 'status', 'descriptor',
        'operational_diagnostics', 'performance', 'first_remaining_blocker')}, indent=2))
