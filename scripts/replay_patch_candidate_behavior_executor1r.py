"""Record EXECUTOR.1R's exact synthetic authorization compatibility stop."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.behavioral_diagnostic_executor_refresh import verify

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    receipt, report = verify()
    if args.output:
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({'phase_id': report['phase_id'], 'status': report['status'],
        'reason': report['reason'], 'compatibility_findings': receipt.compatibility_findings,
        'positive_runtime_receipt_issued': False,
        'synthetic_behavioral_execution_count': 0}, indent=2, sort_keys=True))
