"""Fixed read-only infrastructure/cleanup observations; zero owner issuance.

This cannot retry JAVA.1C, issue a SANDBOX.2 receipt, inspect an alternative
image, list the image inventory, or create/start/remove a container.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
from core import candidate_runtime_sandbox as baseline
from core import sandboxed_java_positive_continuation as java

if len(sys.argv) != 2 or sys.argv[1] not in ('restricted', 'host'):
    raise SystemExit('Fixed read-only observation requires a context label.')
label = sys.argv[1]
prefix = baseline._docker_prefix()
if not prefix:
    raise SystemExit('Frozen local Docker route unavailable.')
config = Path(prefix[2])
result = {'observed_utc': datetime.now(timezone.utc).isoformat(), 'context': label,
          'standalone_owner_invocations': 0, 'provider_issuance': 0,
          'read_only_Docker_controls': 2, 'private_config_path': str(config),
          'config_absent_before': not config.exists() and not config.is_symlink(),
          'scope': 'Post-attempt read-only observations, not original standalone measurements.'}
image = subprocess.run((*prefix, 'image', 'inspect', java.IMAGE, '--format',
    '{"Id":{{json .Id}},"Os":{{json .Os}},"Architecture":{{json .Architecture}},"Volumes":{{json .Config.Volumes}}}'),
    capture_output=True, timeout=8, shell=False,
    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
result['exact_image'] = {'identity': java.IMAGE, 'exit_code': image.returncode,
                         'stdout': image.stdout.decode(errors='replace')[:2000],
                         'stderr': image.stderr.decode(errors='replace')[:2000]}
remaining = subprocess.run((*prefix, 'ps', '-a', '--format', '{{.Names}}',
    '--filter', 'name=runtime-java1c-', '--filter', 'name=runtime-sandbox2-'),
    capture_output=True, timeout=8, shell=False,
    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
result['phase_containers'] = {'exit_code': remaining.returncode,
    'names': remaining.stdout.decode().splitlines() if remaining.returncode == 0 else None,
    'count': len(remaining.stdout.splitlines()) if remaining.returncode == 0 else None,
    'stderr': remaining.stderr.decode(errors='replace')[:2000]}
result['config_absent_after'] = not config.exists() and not config.is_symlink()
result['processes_reaped_and_pipes_closed'] = True
(HERE / ('post_observation_' + label + '.json')).write_text(
    json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
print(json.dumps(result, indent=2))
