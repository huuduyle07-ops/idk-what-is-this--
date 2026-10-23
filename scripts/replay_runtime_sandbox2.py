"""Verify the fixed SANDBOX.2 candidate; stop at the first measured blocker."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.thread_compatible_runtime_sandbox import replay

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = replay()
    if args.output:
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    summary = {k: result.get(k) for k in ('phase_id', 'profile_id', 'status', 'policy_sha256',
        'javac_version_count', 'java_version_count', 'cleanup_verified', 'controller_error')}
    summary['stages'] = [{k: s[k] for k in ('mode', 'verdict', 'capture_status', 'exit_code',
        'stdout_size', 'stderr_size', 'cleanup_verified')} for s in result['stages']]
    print(json.dumps(summary, indent=2, sort_keys=True))
