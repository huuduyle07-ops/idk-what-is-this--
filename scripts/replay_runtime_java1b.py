"""Run JAVA.1B gates, continuing JAVA.1 only after captured javac success."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.sandboxed_java_capture_recovery import replay


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = replay()
    if args.output:
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n',
            encoding='utf-8', newline='\n')
    summary = {key: result.get(key) for key in ('phase_id', 'status',
        'java_version_launch_count', 'compile_count', 'jvm_fixture_count',
        'phase_container_count_after_teardown', 'controller_error')}
    summary['gates'] = [{'mode': gate['mode'], 'status': gate['status'],
        'container_cleanup_verified': gate['container_cleanup_verified'],
        'stages': {name: {key: stage[key] for key in ('status', 'pid', 'exit_code',
            'cleanup_verified', 'threads_before', 'threads_after', 'stdout_b64', 'stderr_b64')}
            for name, stage in gate['facts'].get('stages', {}).items()}}
        for gate in result['gates']]
    print(json.dumps(summary, indent=2, sort_keys=True))
