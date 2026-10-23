"""One fixed read-only exact-image metadata check, with no owner issuance."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE.parents[3]))
from core import candidate_runtime_sandbox as baseline
from core import sandboxed_java_positive_continuation as java

if len(sys.argv) != 1:
    raise SystemExit('No caller inputs permitted.')
prefix = baseline._docker_prefix()
config = Path(prefix[2])
absent_before = not config.exists() and not config.is_symlink()
template = '{"Id":{{json .Id}},"Os":{{json .Os}},"Architecture":{{json .Architecture}},"Volumes":{{json (index .Config "Volumes")}}}'
observed = subprocess.run((*prefix, 'image', 'inspect', java.IMAGE, '--format', template),
    capture_output=True, timeout=8, shell=False,
    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
result = {'observed_utc': datetime.now(timezone.utc).isoformat(), 'context': 'host',
          'standalone_owner_invocations': 0, 'provider_issuance': 0,
          'read_only_Docker_controls': 1, 'private_config_path': str(config),
          'config_absent_before': absent_before,
          'config_absent_after': not config.exists() and not config.is_symlink(),
          'identity': java.IMAGE, 'exit_code': observed.returncode,
          'metadata': json.loads(observed.stdout) if observed.returncode == 0 else None,
          'stderr': observed.stderr.decode(errors='replace')[:2000],
          'process_reaped_and_pipes_closed': True,
          'provenance': 'Separate post-attempt read-only observation; no live attempt repeated.',
          'format_correction': 'Use index for the optional Volumes key; preserve prior template error artifact.'}
(HERE / 'post_exact_image_observation.json').write_text(
    json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
print(json.dumps(result, indent=2))
