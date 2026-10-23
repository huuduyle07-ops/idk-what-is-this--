"""Run fixed controller diagnostics only; no Java verifier or executor resume."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.runtime_java_controller_diagnostic import replay


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = replay()
    if args.output:
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n',
            encoding='utf-8', newline='\n')
    print(json.dumps(result, indent=2, sort_keys=True))
