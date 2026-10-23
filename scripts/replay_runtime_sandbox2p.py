"""Measure SANDBOX.2P's freshness stop, without issuing provenance capability."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.sandbox_backend_provenance import replay

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = replay()
    if args.output:
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n',
            encoding='utf-8', newline='\n')
    print(json.dumps({key: result.get(key) for key in ('phase_id', 'status', 'reason',
        'fresh_sandbox2_authenticated', 'exact_live_pair_revalidated',
        'backend_identity', 'backend_version', 'attachment_issued',
        'sandbox2_infrastructure_effects', 'additional_provenance_effects',
        'cleanup_verified')}, indent=2))
    sys.exit(1)
