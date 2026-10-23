"""Measure local RUNTIME.JAVA.1 infrastructure only; no candidate execution."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import candidate_runtime_sandbox as sandbox
from core import sandboxed_java_toolchain as owner


def replay(repetitions=1):
    if type(repetitions) is not int or not 1 <= repetitions <= 2:
        raise ValueError('one_or_two_infrastructure_repetitions_required')
    # Process-local authentication cannot be restored from historical JSON.
    # Re-measure the frozen implementation without rewriting its old report.
    total = perf_counter(); tick = perf_counter()
    sandbox_timings, sandbox_diagnostics = {}, {}
    sandbox_descriptor, sandbox_receipt = sandbox.verify_candidate_runtime_sandbox(
        timings=sandbox_timings, diagnostics=sandbox_diagnostics)
    sandbox.validate_sandbox_descriptor(sandbox_descriptor, sandbox_receipt)
    authentication_seconds = perf_counter() - tick
    samples, receipts = [], []
    for _ in range(repetitions):
        timings, diagnostics = {}, {}
        descriptor, receipt = owner.verify_sandboxed_java_toolchain(sandbox_descriptor,
            sandbox_receipt, timings=timings, diagnostics=diagnostics)
        owner.validate_java_descriptor(descriptor, receipt)
        samples.append(timings); receipts.append(receipt)
        # No repeat of acquisition, failed Java launch or an incomplete inventory.
        if receipt.status == owner.INCOMPATIBLE or not receipt.discovery_complete: break
    return {
        'phase_id': owner.PHASE_ID, 'status': receipt.status, 'report_only': True,
        'descriptor': descriptor.as_dict(), 'verification_receipt': receipt.as_dict(),
        'sandbox_authentication': {'descriptor': sandbox_descriptor.as_dict(),
            'verification_receipt_fingerprint': sandbox_receipt.fingerprint,
            'status': sandbox_receipt.status, 'historical_receipt_modified': False,
            'seconds': authentication_seconds, 'performance': sandbox_timings,
            'operational_diagnostics': sandbox_diagnostics},
        'discovery_sources': ['fixed_local_docker_image_inventory_including_untagged_images',
            'immutable_local_image_inspect', 'bounded_stopped_container_filesystem_export'],
        'offline_artifact_route': 'none_explicitly_supplied_or_configured; no_host_disk_search',
        'remote_registry_discovery': False, 'local_java_artifact_available': descriptor.available,
        'executor_java_requirements_satisfied': owner.java_toolchain_satisfies_executor_runtime(descriptor, sandbox_descriptor),
        'executor_refreshed_or_resumed': False, 'runtime_policy_authorizations_consumed': 0,
        'java_candidate_execution_count': 0, 'bank_execution_count': 0,
        'behavioral_scenario_count': 0, 'reflection_count': 0, 'console_count': 0,
        'model_calls': 0, 'author_calls': 0, 'repository_traversals': 0,
        'product_source_projected': False, 'source_mutation_count': 0,
        'runtime_authority': False, 'repository_write_authority': False, 'apply_authority': False,
        'image_pulls': 0, 'downloads': 0, 'installations': 0,
        'host_java_fallback': False, 'plain_subprocess_candidate_fallback': False,
        'maven_or_gradle': False, 'sandbox_requirements_weakened': False,
        'semantic_fingerprints': [r.fingerprint for r in receipts],
        'deterministic': len({r.fingerprint for r in receipts}) == 1,
        'determinism_measured_repetitions': len(receipts),
        'determinism_scope': 'same sandbox/artifact/source/compiler/runtime/canonical results; excludes timing/temp/container IDs',
        'performance': {name: {'median_ms': round(statistics.median(s[name] for s in samples) * 1000, 3),
            'max_ms': round(max(s[name] for s in samples) * 1000, 3)} for name in owner.TIMING_FIELDS},
        'total_replay_seconds_including_authentication': perf_counter() - total,
        'operational_diagnostics': diagnostics,
        'persistent_footprint': {'new_images_bytes': 0, 'new_workers_or_services': 0,
            'persistent_source_or_class_outputs': 0,
            'existing_inventory_image_size_bytes': sum(a.image_size_bytes for a in receipt.artifact_inventory),
            'scope': 'image inspect logical sizes; existing Docker/WSL cost measured separately'},
        'first_remaining_blocker': receipt.reason if not descriptor.verified else
            'executor_java_integration_and_runtime_authority_outside_this_phase',
        'warnings': ['Docker/WSL startup and memory cost remain; no always-on worker added',
            'Java compile/runtime/selected-image seccomp compatibility unmeasured without a suitable local artifact',
            'Exported JSON is report-only; signatures and authority cannot be restored from it'],
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repetitions', type=int, default=1)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = replay(args.repetitions)
    if args.output:
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({key: result[key] for key in ('phase_id', 'status', 'descriptor',
        'performance', 'persistent_footprint', 'first_remaining_blocker')}, indent=2))
