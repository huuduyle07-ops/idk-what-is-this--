"""Record an additive JAVA.1D retry, preserving the historical blocked attempt."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.sandboxed_java_discovery_continuation import COMPLETE, verify


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.output and args.output.exists():
        raise ValueError('additive_retry_output_already_exists')
    _, result = verify()
    if args.output:
        with args.output.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({k: result.get(k) for k in ('phase_id', 'status', 'reason',
        'binding_attachment_authenticated', 'complete_inventory', 'inventory_count',
        'inventory_sha256', 'backend_binding_result', 'exact_pinned_image_membership',
        'fresh_java1c_authenticated', 'positive_receipt_issued', 'java1d_receipt_fingerprint',
        'cleanup', 'effects')}, indent=2))
    sys.exit(0 if result['status'] == COMPLETE else 1)
