"""Record one exact original-semantics SANDBOX.BIND.1 attachment proof."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.sandbox_backend_binding import COMPLETE, replay

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = replay()
    if args.output:
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n',
            encoding='utf-8', newline='\n')
    print(json.dumps({key: value for key, value in result.items()
        if key not in ('live_sandbox2', 'docker_control_calls', 'attachment')}, indent=2))
    sys.exit(0 if result['status'] == COMPLETE else 1)
