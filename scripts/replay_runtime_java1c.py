"""Verify the exact JAVA.1 fixture on live-authenticated SANDBOX.2, then stop."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.sandboxed_java_positive_continuation import verify


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    _, _, report = verify()
    if args.output:
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({k: report.get(k) for k in ('phase_id', 'status', 'reason',
        'sandbox_authentication', 'compile_count', 'jvm_fixture_count',
        'decoded_stages', 'phase_container_count_after_teardown', 'cleanup_verified',
        'pure_executor_compatibility', 'controller_error')}, indent=2, sort_keys=True))
    sys.exit(0 if report['status'] == 'RUNTIME_JAVA_1_COMPLETE_WITH_WARNINGS' else 1)
