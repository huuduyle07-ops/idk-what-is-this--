# RUNTIME.SANDBOX.2.PRELADDER.DIAG.1

**SANDBOX2_PRELADDER_DIAG_COMPLETE** · **PRELADDER_COMPLETE**

This retained diagnostic used the unchanged SANDBOX.2 public owner. No remediation, JAVA.1C continuation, SYNTH retry, or runtime authority was issued.

## Outcome

Pre-ladder result: **PRELADDER_COMPLETE**. First container create attempted: **True**. The frozen owner continued naturally; its final status was **RUNTIME_SANDBOX_2_COMPLETE_WITH_WARNINGS**.

| Fact | Measured result |
| --- | --- |
| SANDBOX.2 operational issuances | 1 |
| Linux Server.Version retrieved | True |
| Endpoint | npipe:////./pipe/dockerDesktopLinuxEngine |
| Server.Version | 29.6.1 |
| Exact frozen image | sha256:f6d7dc31a15bb37a618ebed6772beda3de95fdcc3394eb5a1def9b1d20673f7a |
| First create attempted | True |
| First ladder mode | clone3 |
| SANDBOX.2 final / descriptor / receipt status | ["RUNTIME_SANDBOX_2_COMPLETE_WITH_WARNINGS", "RUNTIME_SANDBOX_2_COMPLETE_WITH_WARNINGS", "RUNTIME_SANDBOX_2_COMPLETE_WITH_WARNINGS"] |
| Receipt / descriptor HMAC results | {"descriptor": true, "receipt": true} |
| Semantic eligibility | True |
| Ladder stage count | 11 |
| JAVA.1C invoked | False |
| SYNTH retried | False |
| Runtime authority issued | False |

## Source bytes and ordered pre-ladder ledger

| Source | SHA256 |
| --- | --- |
| core/candidate_runtime_sandbox.py | ebe409e7e798ec1e8f48c4bd2c49e5cd8b282906251f7c2c38c2933d1ef51913 |
| core/thread_compatible_runtime_sandbox.py | 8eea18d16c330dc7d116065ac9d23833bb2a0af58448b02438c26526141b1d45 |
| core/thread_compatible_runtime_sandbox_probe.py | be45d3a0106186d84a0464234f701140df6e90e99107477af358886cf5568075 |

Frozen source hashes preserved: **True**. Every row below follows the recovered frozen source order. Detailed inputs, possible exceptions/statuses, termination behavior and container effects are retained in the JSON report and [static audit](static_pre_ladder_audit.json).

| Order | Step | State | Source / function | Input | Possible failure | Creates container |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | report_initialization | PASS | core/thread_compatible_runtime_sandbox.py:318 replay | frozen constants, policy_diff() | initialization exception | False |
| 2 | docker_binary_endpoint_lookup | PASS | core/candidate_runtime_sandbox.py:364 _docker_prefix | shutil.which('docker'), _local_endpoint() | lookup exception; empty prefix if unavailable | False |
| 3 | docker_binary_endpoint_availability_branch | PASS | core/candidate_runtime_sandbox.py:365 _docker_prefix | binary and endpoint | returns empty tuple if missing (no exception) | False |
| 4 | docker_binary_resolution | PASS | core/candidate_runtime_sandbox.py:366 _docker_prefix | binary path | OSError/path resolution error | False |
| 5 | docker_owner_root_resolution | PASS | core/candidate_runtime_sandbox.py:367 _docker_prefix | baseline __file__ | OSError/path resolution error | False |
| 6 | docker_binary_boundary_branch | PASS | core/candidate_runtime_sandbox.py:368 _docker_prefix | resolved path, owner root, Windows .exe suffix | returns empty tuple when rejected | False |
| 7 | private_config_path_construction | PASS | core/candidate_runtime_sandbox.py:371 _docker_prefix | tempfile.gettempdir(), secrets.token_hex(16) | temporary-root/path/random exception; no mkdir or absence check | False |
| 8 | docker_prefix_return | PASS | core/candidate_runtime_sandbox.py:372 _docker_prefix | binary, absent_config, endpoint | returns exact tuple | False |
| 9 | policy_file_read | PASS | core/thread_compatible_runtime_sandbox.py:328 replay | POLICY_PATH.read_bytes() | OSError | False |
| 10 | policy_baseline_identity | PASS | core/thread_compatible_runtime_sandbox.py:59 validate_policy_bytes | baseline policy hash == historical baseline digest | ValueError historical_policy_identity_changed | False |
| 11 | policy_expected_copy | PASS | core/thread_compatible_runtime_sandbox.py:61 validate_policy_bytes | deepcopy baseline policy | copy exception | False |
| 12 | policy_clone3_remove | PASS | core/thread_compatible_runtime_sandbox.py:62 validate_policy_bytes | remove clone3 from first names list | ValueError/KeyError/TypeError | False |
| 13 | policy_errno38_append | PASS | core/thread_compatible_runtime_sandbox.py:63 validate_policy_bytes | append fixed clone3 errno 38 denial | list access/append exception | False |
| 14 | policy_raw_type | PASS | core/thread_compatible_runtime_sandbox.py:64 validate_policy_bytes | type(raw) is bytes | ValueError canonical policy required | False |
| 15 | policy_exact_bytes | PASS | core/thread_compatible_runtime_sandbox.py:64 validate_policy_bytes | raw == baseline._json(expected).encode() | ValueError canonical policy required | False |
| 16 | policy_exact_hash | PASS | core/thread_compatible_runtime_sandbox.py:65 validate_policy_bytes | sha256(raw) == POLICY_SHA256 | ValueError canonical policy required | False |
| 17 | exact_image_control | PASS | core/thread_compatible_runtime_sandbox.py:329 replay | prefix + image inspect exact IMAGE --format {{json .}} | Popen OSError; nonzero exit or bounded capture failure | False |
| 18 | image_control_environment | PASS | core/candidate_runtime_sandbox.py:294 _bounded_process | minimal frozen environment and host-only sentinel | environment construction exception | False |
| 19 | image_control_deadlines | PASS | core/candidate_runtime_sandbox.py:296 _bounded_process | monotonic start, timeout and abort deadlines | clock/arithmetic exception | False |
| 20 | image_control_process_launch | PASS | core/candidate_runtime_sandbox.py:299 _bounded_process | Popen shell=False, hidden Windows child, stdin/stdout/stderr pipes | OSError before control try | False |
| 21 | image_control_capture_preparation | PASS | core/candidate_runtime_sandbox.py:302 _bounded_process | Event, two bytearrays, read closure, two bounded reader Threads | thread/event/buffer construction exception | False |
| 22 | image_control_reader_start | PASS | core/candidate_runtime_sandbox.py:316 _bounded_process | start both daemon readers | RuntimeError/OSError | False |
| 23 | image_control_stdin_write | PASS | core/candidate_runtime_sandbox.py:322 _bounded_process | original empty input bytes | OSError becomes control failure | False |
| 24 | image_control_stdin_close | PASS | core/candidate_runtime_sandbox.py:323 _bounded_process | close original stdin pipe | OSError becomes control failure | False |
| 25 | image_control_process_completion | PASS | core/candidate_runtime_sandbox.py:324 _bounded_process | poll with output/timeout limits and wait; kill on abort | timeout/output bound/control failure | False |
| 26 | image_control_reader_join | PASS | core/candidate_runtime_sandbox.py:345 _bounded_process | join both reader threads (2 seconds each) | surviving reader => sandbox_control_failure | False |
| 27 | image_control_pipe_close | PASS | core/candidate_runtime_sandbox.py:348 _bounded_process | close stdout and stderr | OSError | False |
| 28 | image_control_capture_return | PASS | core/candidate_runtime_sandbox.py:353 _bounded_process | original _Capture with bounded bytes and original return code | capture construction exception | False |
| 29 | image_capture_status_requirement | PASS | core/thread_compatible_runtime_sandbox.py:331 replay | image.status == sandbox_completed | other status selects {}, no parsing | False |
| 30 | image_capture_exit_requirement | PASS | core/thread_compatible_runtime_sandbox.py:331 replay | image.exit_code == 0 | nonzero exit selects {}, no parsing | False |
| 31 | image_output_parse | PASS | core/thread_compatible_runtime_sandbox.py:331 replay | json.loads(original capture.stdout) only on completed exit 0 | ValueError/JSONDecodeError; failed control supplies {} without parsing | False |
| 32 | metadata_prefix_requirement | PASS | core/thread_compatible_runtime_sandbox.py:332 replay | not prefix | ValueError exact_local_java_image_required | False |
| 33 | metadata_id_requirement | PASS | core/thread_compatible_runtime_sandbox.py:332 replay | metadata.get('Id') == IMAGE | AttributeError on non-.get receiver; identity rejection | False |
| 34 | metadata_os_requirement | PASS | core/thread_compatible_runtime_sandbox.py:332 replay | metadata.get('Os') == 'linux' | OS rejection | False |
| 35 | metadata_arch_requirement | PASS | core/thread_compatible_runtime_sandbox.py:333 replay | metadata.get('Architecture') == 'amd64' | architecture rejection | False |
| 36 | metadata_volumes_requirement | PASS | core/thread_compatible_runtime_sandbox.py:333 replay | not metadata.get('Config', {}).get('Volumes') | AttributeError if Config lacks .get; truthy volumes rejected | False |
| 37 | temporary_workspace_create | PASS | core/thread_compatible_runtime_sandbox.py:335 replay | TemporaryDirectory(prefix='runtime-sandbox2-').__enter__() | OSError | False |
| 38 | workspace_path_construction | PASS | core/thread_compatible_runtime_sandbox.py:336 replay | root/seccomp.json, root/host-sentinel.txt | path exception | False |
| 39 | policy_workspace_write | PASS | core/thread_compatible_runtime_sandbox.py:337 replay | POLICY_BYTES to seccomp.json | OSError | False |
| 40 | sentinel_workspace_write | PASS | core/thread_compatible_runtime_sandbox.py:338 replay | fixed sentinel bytes to host-sentinel.txt | OSError | False |
| 41 | host_tcp_socket_construction | PASS | core/thread_compatible_runtime_sandbox.py:339 replay | default TCP socket construction | OSError | False |
| 42 | host_tcp_socket_enter | PASS | core/thread_compatible_runtime_sandbox.py:339 replay | TCP socket context entry | context entry exception | False |
| 43 | host_udp_socket_construction | PASS | core/thread_compatible_runtime_sandbox.py:339 replay | AF_INET/SOCK_DGRAM socket construction | OSError | False |
| 44 | host_udp_socket_enter | PASS | core/thread_compatible_runtime_sandbox.py:339 replay | UDP socket context entry | context entry exception | False |
| 45 | host_tcp_bind | PASS | core/thread_compatible_runtime_sandbox.py:340 replay | 127.0.0.1 ephemeral port | OSError | False |
| 46 | host_tcp_listen | PASS | core/thread_compatible_runtime_sandbox.py:341 replay | listen(1) | OSError | False |
| 47 | host_port_read | PASS | core/thread_compatible_runtime_sandbox.py:342 replay | endpoint.getsockname()[1] | OSError | False |
| 48 | host_udp_bind | PASS | core/thread_compatible_runtime_sandbox.py:343 replay | 127.0.0.1 same port | OSError | False |
| 49 | ladder_first_mode | PASS | core/thread_compatible_runtime_sandbox.py:344 replay | first frozen LADDER element clone3 | iterator exception | False |
| 50 | invoke_mode_requirement | PASS | core/thread_compatible_runtime_sandbox.py:257 invoke | mode in LADDER | ValueError fixed_sandbox2_probe_required | False |
| 51 | invoke_original_probe_selection | PASS | core/thread_compatible_runtime_sandbox.py:258 invoke | clone3 in baseline.PROBE_IDS (false) | selection exception | False |
| 52 | invoke_probe_spec_selection | PASS | core/thread_compatible_runtime_sandbox.py:259 invoke | None for clone3; no baseline synthetic spec call | selection exception | False |
| 53 | invoke_fixed_source_selection | PASS | core/thread_compatible_runtime_sandbox.py:260 invoke | probe.source_for('clone3') | ValueError; fixed NS_FLAGS/BPF/header/body construction | False |
| 54 | invoke_fixed_command_construction | PASS | core/thread_compatible_runtime_sandbox.py:261 invoke | -I -S -B -c fixed source | command construction exception | False |
| 55 | invoke_container_name_construction | PASS | core/thread_compatible_runtime_sandbox.py:262 invoke | runtime-sandbox2- + secrets.token_hex(12) | random/name exception | False |
| 56 | invoke_control_callable_construction | PASS | core/thread_compatible_runtime_sandbox.py:263 invoke | frozen lambda forwarding prefix and bounded limits | initialization exception | False |
| 57 | invoke_capture_initialization | PASS | core/thread_compatible_runtime_sandbox.py:264 invoke | _Capture sandbox_launch_failed, facts {}, cleanup false | initialization exception | False |
| 58 | first_create_argv_construction | PASS | core/thread_compatible_runtime_sandbox.py:266 invoke | frozen create flags/environment/entrypoint/exact image/source | argument expansion exception before bounded-process call | False |

## Original controls and image metadata

### Host preflight

```json
{
  "argv": [
    "C:\\Program Files\\Docker\\Docker\\resources\\bin\\docker.EXE",
    "--config",
    "C:\\Users\\Admin\\AppData\\Local\\Temp\\runtime-sandbox1-no-config-03349bce44000e5f832806b8ed2a7b26",
    "--host",
    "npipe:////./pipe/dockerDesktopLinuxEngine",
    "version",
    "--format",
    "{{json .}}"
  ],
  "scope": "diagnostic_read_only_control",
  "status": "sandbox_completed",
  "exit_code": 0,
  "process_reaped": true,
  "pipes_closed": true
}
```

Original stdout retention: **complete_original_bounded_capture**; bytes: 1139; SHA256: `07f9631d57d066a3a72385de3b936738e917b0bcc62e2cad687dab22d282b564`.

```text
{"Client":{"Version":"29.6.1","ApiVersion":"1.55","DefaultAPIVersion":"1.55","GitCommit":"8900f1d","GoVersion":"go1.26.4","Os":"windows","Arch":"amd64","BuildTime":"Fri Jun 26 11:43:32 2026","Context":"default"},"Server":{"Platform":{"Name":"Docker Desktop 4.82.0 (233772)"},"Version":"29.6.1","ApiVersion":"1.55","MinAPIVersion":"1.40","Os":"linux","Arch":"amd64","Components":[{"Name":"Engine","Version":"29.6.1","Details":{"ApiVersion":"1.55","Arch":"amd64","BuildTime":"Fri Jun 26 11:41:04 2026","Experimental":"false","GitCommit":"8ec5ab3","GoVersion":"go1.26.4","KernelVersion":"6.18.33.2-microsoft-standard-WSL2","MinAPIVersion":"1.40","Module":"github.com/moby/moby/v2","ModuleVersion":"v2.0.0+unknown","Os":"linux"}},{"Name":"containerd","Version":"v2.2.5","Details":{"GitCommit":"e53c7c1516c3b2bff98eb76f1f4117477e6f4e66"}},{"Name":"runc","Version":"1.3.6","Details":{"GitCommit":"v1.3.6-0-g491b69ba"}},{"Name":"docker-init","Version":"0.19.0","Details":{"GitCommit":"de40ad0"}}],"GitCommit":"8ec5ab3","GoVersion":"go1.26.4","KernelVersion":"6.18.33.2-microsoft-standard-WSL2","BuildTime":"2026-06-26T11:41:04.000000000+00:00"}}
```

Original stderr retention: **complete_original_bounded_capture**; bytes: 0; SHA256: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

```text

```


### Control relevant to the first failure

No relevant original Docker control was retained for this operation, or no pre-ladder failure occurred.

No relevant original Docker control is available.

### Exact image inspection

```json
{
  "argv": [
    "C:\\Program Files\\Docker\\Docker\\resources\\bin\\docker.EXE",
    "--config",
    "C:\\Users\\Admin\\AppData\\Local\\Temp\\runtime-sandbox1-no-config-4e5f0e8a26a65d6dfa8c02dd870bfd36",
    "--host",
    "npipe:////./pipe/dockerDesktopLinuxEngine",
    "image",
    "inspect",
    "sha256:f6d7dc31a15bb37a618ebed6772beda3de95fdcc3394eb5a1def9b1d20673f7a",
    "--format",
    "{{json .}}"
  ],
  "scope": "SANDBOX2_pre_ladder",
  "status": "sandbox_completed",
  "exit_code": 0,
  "process_reaped": true,
  "pipes_closed": true
}
```

Original stdout retention: **complete_original_bounded_capture**; bytes: 1369; SHA256: `0a6ee60c5dbc1eb6ef670acbc38450902f38bfbfba628d39ba3091be42fd6f91`.

```text
{"Id":"sha256:f6d7dc31a15bb37a618ebed6772beda3de95fdcc3394eb5a1def9b1d20673f7a","RepoTags":["cattus-java26-offline:26.0.2.1"],"RepoDigests":["cattus-java26-offline@sha256:f6d7dc31a15bb37a618ebed6772beda3de95fdcc3394eb5a1def9b1d20673f7a"],"Created":"2026-10-07T04:33:48.196545563Z","Config":{"User":"65534:65534","Env":["PATH=/usr/local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin","LANG=C.UTF-8","GPG_KEY=7169605F62C751356D054A26A821E680E5FA6305","PYTHON_VERSION=3.12.13","PYTHON_SHA256=c08bc65a81971c1dd5783182826503369466c7e67374d1646519adf05207b684"],"Cmd":["true"],"Labels":{"desktop.docker.io/ports.scheme":"v2","desktop.docker.io/wsl-distro":"Ubuntu"}},"Architecture":"amd64","Os":"linux","Size":188948499,"RootFS":{"Type":"layers","Layers":["sha256:f2ec4de84f559f5c7be4233b589cdbdbb5507807e05621b77320edd55a1f2a0f","sha256:ccbaccfc0388284959cf106031557105fad2067d6c4435937b3414ce90760167","sha256:83fdf57f71f28b640f11d5072c284c81eadefc5ea538050fedcedba6149879bd","sha256:b80f3ed1ee6de85c788d9ae7203207c44724eab4baac8697390ca1412954ad2f","sha256:14f30704d84b4a3f0bea90e2bcc2b3a6f210e333a732ed217610fbf6a0e1dd01"]},"Metadata":{"LastTagTime":"2026-10-07T04:33:50.341319153Z"},"Descriptor":{"mediaType":"application/vnd.oci.image.manifest.v1+json","digest":"sha256:f6d7dc31a15bb37a618ebed6772beda3de95fdcc3394eb5a1def9b1d20673f7a","size":1403}}
```

Original stderr retention: **complete_original_bounded_capture**; bytes: 0; SHA256: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

```text

```


Parsed image metadata:

```json
{
  "Architecture": "amd64",
  "Config": {
    "Cmd": [
      "true"
    ],
    "Env": [
      "PATH=/usr/local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
      "LANG=C.UTF-8",
      "GPG_KEY=7169605F62C751356D054A26A821E680E5FA6305",
      "PYTHON_VERSION=3.12.13",
      "PYTHON_SHA256=c08bc65a81971c1dd5783182826503369466c7e67374d1646519adf05207b684"
    ],
    "Labels": {
      "desktop.docker.io/ports.scheme": "v2",
      "desktop.docker.io/wsl-distro": "Ubuntu"
    },
    "User": "65534:65534"
  },
  "Created": "2026-10-07T04:33:48.196545563Z",
  "Descriptor": {
    "digest": "sha256:f6d7dc31a15bb37a618ebed6772beda3de95fdcc3394eb5a1def9b1d20673f7a",
    "mediaType": "application/vnd.oci.image.manifest.v1+json",
    "size": 1403
  },
  "Id": "sha256:f6d7dc31a15bb37a618ebed6772beda3de95fdcc3394eb5a1def9b1d20673f7a",
  "Metadata": {
    "LastTagTime": "2026-10-07T04:33:50.341319153Z"
  },
  "Os": "linux",
  "RepoDigests": [
    "cattus-java26-offline@sha256:f6d7dc31a15bb37a618ebed6772beda3de95fdcc3394eb5a1def9b1d20673f7a"
  ],
  "RepoTags": [
    "cattus-java26-offline:26.0.2.1"
  ],
  "RootFS": {
    "Layers": [
      "sha256:f2ec4de84f559f5c7be4233b589cdbdbb5507807e05621b77320edd55a1f2a0f",
      "sha256:ccbaccfc0388284959cf106031557105fad2067d6c4435937b3414ce90760167",
      "sha256:83fdf57f71f28b640f11d5072c284c81eadefc5ea538050fedcedba6149879bd",
      "sha256:b80f3ed1ee6de85c788d9ae7203207c44724eab4baac8697390ca1412954ad2f",
      "sha256:14f30704d84b4a3f0bea90e2bcc2b3a6f210e333a732ed217610fbf6a0e1dd01"
    ],
    "Type": "layers"
  },
  "Size": 188948499
}
```

The full original bounded stdout/stderr bytes are retained as Base64 with byte counts and SHA256 where available in [controls](observed_controls.json). Decoded text is for reading; Base64 preserves the original bytes.

## Workspace and private Docker config

The frozen Docker prefix constructs a random private config path; it does not create that path or validate its absence. Absence is an independent observed fact. Workspace creation and all inherent frozen owner effects were allowed to continue.

```json
{
  "private_config_paths": [
    {
      "created_by_owner": false,
      "exists_after": false,
      "exists_at_generation": false,
      "is_symlink_after": false,
      "is_symlink_at_generation": false,
      "owner_requires_absence": false,
      "path": "C:\\Users\\Admin\\AppData\\Local\\Temp\\runtime-sandbox1-no-config-03349bce44000e5f832806b8ed2a7b26",
      "prefix": [
        "C:\\Program Files\\Docker\\Docker\\resources\\bin\\docker.EXE",
        "--config",
        "C:\\Users\\Admin\\AppData\\Local\\Temp\\runtime-sandbox1-no-config-03349bce44000e5f832806b8ed2a7b26",
        "--host",
        "npipe:////./pipe/dockerDesktopLinuxEngine"
      ]
    },
    {
      "created_by_owner": false,
      "exists_after": false,
      "exists_at_generation": false,
      "is_symlink_after": false,
      "is_symlink_at_generation": false,
      "owner_requires_absence": false,
      "path": "C:\\Users\\Admin\\AppData\\Local\\Temp\\runtime-sandbox1-no-config-4e5f0e8a26a65d6dfa8c02dd870bfd36",
      "prefix": [
        "C:\\Program Files\\Docker\\Docker\\resources\\bin\\docker.EXE",
        "--config",
        "C:\\Users\\Admin\\AppData\\Local\\Temp\\runtime-sandbox1-no-config-4e5f0e8a26a65d6dfa8c02dd870bfd36",
        "--host",
        "npipe:////./pipe/dockerDesktopLinuxEngine"
      ]
    }
  ],
  "temporary_workspaces": [
    {
      "exists_at_entry": true,
      "path": "C:\\Users\\Admin\\AppData\\Local\\Temp\\runtime-sandbox2-t_fsepvy",
      "profile": {
        "exists_before_sockets": true,
        "path": "C:\\Users\\Admin\\AppData\\Local\\Temp\\runtime-sandbox2-t_fsepvy\\seccomp.json",
        "sha256": "5a36bdf1676c4b0d7b4bef489f5e90b5c8fb201b5194be48baf61f4206a81f75"
      },
      "removed_after": true,
      "sentinel": {
        "exists_before_sockets": true,
        "path": "C:\\Users\\Admin\\AppData\\Local\\Temp\\runtime-sandbox2-t_fsepvy\\host-sentinel.txt",
        "sha256": "362bbfc98dff30e9435510c7fd792a91829df4503f548d42f4eaafd6f09c51f6"
      }
    }
  ]
}
```

## Authentication, semantic eligibility and cleanup

Original descriptor and receipt objects were retained at the issuer return and independently checked by unchanged SANDBOX.2 public validators. Exported fields contain no HMAC secret or signature and do not grant authority.

| Cleanup fact | Result |
| --- | --- |
| Original owner cleanup | {"remaining_containers": 0, "verified": true} |
| Independent final zero containers | True |
| Independent final cleanup verified | True |
| Remaining phase containers | [] |
| Control children reaped | True |
| Control pipes closed | True |
| Control readers stopped | True |
| Observer restored | True |
| Private config paths absent | True |
| Created temporary workspaces removed | True |

The original owner cleanup result is preserved exactly. A later zero-container observation does not change that result.

## Historical nested comparison

**DIFFERS_FROM_HISTORICAL_FAILURE_SHAPE**

| Fact | Frozen nested SYNTH attempt | Fresh standalone diagnostic |
| --- | --- | --- |
| exact image inspection success | True | True |
| parsed image metadata | UNAVAILABLE | {"Architecture": "amd64", "Config": {"Cmd": ["true"], "Env": ["PATH=/usr/local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin", "LANG=C.UTF-8", "GPG_KEY=7169605F62C751356D054A26A821E680E5FA6305", "PYTHON_VERSION=3.12.13", "PYTHON_SHA256=c08bc65a81971c1dd5783182826503369466c7e67374d1646519adf05207b684"], "Labels": {"desktop.docker.io/ports.scheme": "v2", "desktop.docker.io/wsl-distro": "Ubuntu"}, "User": "65534:65534"}, "Created": "2026-10-07T04:33:48.196545563Z", "Descriptor": {"digest": "sha256:f6d7dc31a15bb37a618ebed6772beda3de95fdcc3394eb5a1def9b1d20673f7a", "mediaType": "application/vnd.oci.image.manifest.v1+json", "size": 1403}, "Id": "sha256:f6d7dc31a15bb37a618ebed6772beda3de95fdcc3394eb5a1def9b1d20673f7a", "Metadata": {"LastTagTime": "2026-10-07T04:33:50.341319153Z"}, "Os": "linux", "RepoDigests": ["cattus-java26-offline@sha256:f6d7dc31a15bb37a618ebed6772beda3de95fdcc3394eb5a1def9b1d20673f7a"], "RepoTags": ["cattus-java26-offline:26.0.2.1"], "RootFS": {"Layers": ["sha256:f2ec4de84f559f5c7be4233b589cdbdbb5507807e05621b77320edd55a1f2a0f", "sha256:ccbaccfc0388284959cf106031557105fad2067d6c4435937b3414ce90760167", "sha256:83fdf57f71f28b640f11d5072c284c81eadefc5ea538050fedcedba6149879bd", "sha256:b80f3ed1ee6de85c788d9ae7203207c44724eab4baac8697390ca1412954ad2f", "sha256:14f30704d84b4a3f0bea90e2bcc2b3a6f210e333a732ed217610fbf6a0e1dd01"], "Type": "layers"}, "Size": 188948499} |
| private config behavior | argv path retained; absence not measured | [{"created_by_owner": false, "exists_after": false, "exists_at_generation": false, "is_symlink_after": false, "is_symlink_at_generation": false, "owner_requires_absence": false, "path": "C:\\Users\\Admin\\AppData\\Local\\Temp\\runtime-sandbox1-no-config-03349bce44000e5f832806b8ed2a7b26", "prefix": ["C:\\Program Files\\Docker\\Docker\\resources\\bin\\docker.EXE", "--config", "C:\\Users\\Admin\\AppData\\Local\\Temp\\runtime-sandbox1-no-config-03349bce44000e5f832806b8ed2a7b26", "--host", "npipe:////./pipe/dockerDesktopLinuxEngine"]}, {"created_by_owner": false, "exists_after": false, "exists_at_generation": false, "is_symlink_after": false, "is_symlink_at_generation": false, "owner_requires_absence": false, "path": "C:\\Users\\Admin\\AppData\\Local\\Temp\\runtime-sandbox1-no-config-4e5f0e8a26a65d6dfa8c02dd870bfd36", "prefix": ["C:\\Program Files\\Docker\\Docker\\resources\\bin\\docker.EXE", "--config", "C:\\Users\\Admin\\AppData\\Local\\Temp\\runtime-sandbox1-no-config-4e5f0e8a26a65d6dfa8c02dd870bfd36", "--host", "npipe:////./pipe/dockerDesktopLinuxEngine"]}] |
| workspace behavior | not retained | [{"exists_at_entry": true, "path": "C:\\Users\\Admin\\AppData\\Local\\Temp\\runtime-sandbox2-t_fsepvy", "profile": {"exists_before_sockets": true, "path": "C:\\Users\\Admin\\AppData\\Local\\Temp\\runtime-sandbox2-t_fsepvy\\seccomp.json", "sha256": "5a36bdf1676c4b0d7b4bef489f5e90b5c8fb201b5194be48baf61f4206a81f75"}, "removed_after": true, "sentinel": {"exists_before_sockets": true, "path": "C:\\Users\\Admin\\AppData\\Local\\Temp\\runtime-sandbox2-t_fsepvy\\host-sentinel.txt", "sha256": "362bbfc98dff30e9435510c7fd792a91829df4503f548d42f4eaafd6f09c51f6"}}] |
| first create attempted | False | True |
| SANDBOX2 final status | blocked pair inferred by frozen context; original report absent | RUNTIME_SANDBOX_2_COMPLETE_WITH_WARNINGS |
| eligibility | false per frozen diagnostic context; original descriptor absent | True |
| SANDBOX2 owner cleanup | not retained | True |
| ladder stage count | no ladder create; original stage list absent | 11 |

Historical own SANDBOX.2 inspection succeeded and no container create was attempted. Its original live report, pair and deeper pre-ladder evidence were not retained. Matching blocked outcomes or matching partial failure shapes do not establish the same root cause. **The historical nested root cause remains unresolved.**

The restricted standalone AUTH.DIAG Docker permission denial is separate evidence and is never attributed to the older nested failure.

A successful fresh standalone run supports possible context sensitivity but identifies no causal outer component.

## Operational effects

| Effect | Count |
| --- | --- |
| Apply | 0 |
| BANK | 0 |
| BIND1 | 0 |
| Docker_version_preflight | 1 |
| EXECUTOR1R | 0 |
| JAVA1C | 0 |
| JVM_fixture | 0 |
| Java_compile_outside_frozen_version_probes | 0 |
| PINNED1A_export | 0 |
| PINNED1B | 0 |
| PINNED1C | 0 |
| SANDBOX2_Docker_controls | 74 |
| SANDBOX2_container_create_attempts | 11 |
| SANDBOX2_container_start_attempts | 11 |
| SANDBOX2_host_control_sockets | 2 |
| SANDBOX2_operational_issuances | 1 |
| SYNTH | 0 |
| SyntheticStateBox | 0 |
| alternative_provider_inspection | 0 |
| builds | 0 |
| caller_shell_workload | 0 |
| generic_image_inventory | 0 |
| host_mounts | 0 |
| independent_cleanup_Docker_controls | 1 |
| java_version_probes | 1 |
| javac_version_probes | 1 |
| outbound_workload_network | 0 |
| pulls | 0 |
| reflection | 0 |
| reflection_lease_consumption | 0 |
| repository_runtime_writes | 0 |
| runtime_lease_consumption | 0 |
| total_Docker_controls | 76 |

These counts reflect frozen source and retained original control argv/scope plus owner reports. They do not claim OS-wide event tracing.

## Preservation and validation

Historical byte preservation: **True**, **2126** files checked. No historical baseline was repinned; existing worktree changes were retained.

```json
{
  "pre_live_gates_passed": true,
  "preservation": {
    "baseline_rewritten": false,
    "changed_or_missing": [],
    "historical_file_count": 2126,
    "method": "SHA256 of every original file named by the exclusive new-phase baseline",
    "passed": true
  },
  "registry_picker_baseline_vs_after": {
    "passed": true,
    "picker_equal": true,
    "registry_equal": true
  },
  "validation_checks": {
    "auth-artifacts": {
      "command": [
        "C:\\Python314\\python.exe",
        "-B",
        "C:\\Users\\Admin\\Documents\\Code\\J.A.R.V.I.S\\districts\\C.A.T.T.U.S\\docs\\roadmap\\phases\\RUNTIME_SANDBOX_2_PRELADDER_DIAG_1\\validation.py",
        "worker",
        "auth-artifacts"
      ],
      "exit_code": 0,
      "passed": true,
      "stderr_retained": "auth-artifacts.stderr.txt",
      "stdout_retained": "auth-artifacts.stdout.txt",
      "worker_result": {
        "Docker_controls": 0,
        "JSON_artifacts_parsed": 16,
        "Java_effects": 0,
        "all_historical_assertions_executed": true,
        "audit_guard": {
          "allowed_pure_domain_children": 0,
          "forbidden_process_attempts": 0,
          "forbidden_socket_attempts": 0,
          "forbidden_write_attempts": 0
        },
        "authored_whitespace_passed": true,
        "captured_original_stdout": "{\"passed\": true, \"historical_files_preserved\": 1828, \"diagnostic_python_sources_compiled_in_memory\": 6, \"JSON_artifacts_parsed\": 16, \"markdown_links_checked\": 18, \"authored_whitespace_passed\": true, \"live_owner_invocations\": 0, \"Docker_controls\": 0, \"Java_effects\": 0, \"evidence_consistency_passed\": true, \"single_effectful_call_site_and_exclusive_marker\": true}\n",
        "diagnostic_python_sources_compiled_in_memory": 6,
        "evidence_consistency_passed": true,
        "historical_files_preserved": 1828,
        "live_owner_invocations": 0,
        "markdown_links_checked": 18,
        "original_frozen_source_sha256": "8c764d5f98ba297f8d335f796442e3f9f1d13c14589fb5a6ccaaba77dbf616f6",
        "passed": true,
        "removed_statement_source_line": 105,
        "single_effectful_call_site_and_exclusive_marker": true,
        "sole_final_historical_write_removed_in_memory": true
      }
    },
    "auth-matrix": {
      "command": [
        "C:\\Python314\\python.exe",
        "-B",
        "C:\\Users\\Admin\\Documents\\Code\\J.A.R.V.I.S\\districts\\C.A.T.T.U.S\\docs\\roadmap\\phases\\RUNTIME_SANDBOX_2_PRELADDER_DIAG_1\\validation.py",
        "worker",
        "auth-matrix"
      ],
      "exit_code": 0,
      "passed": true,
      "stderr_retained": "auth-matrix.stderr.txt",
      "stdout_retained": "auth-matrix.stdout.txt",
      "worker_result": {
        "audit_guard": {
          "allowed_pure_domain_children": 1,
          "forbidden_process_attempts": 0,
          "forbidden_socket_attempts": 0,
          "forbidden_write_attempts": 0
        },
        "case_count": 57,
        "effect_counts": {
          "caller_shell": 0,
          "docker": 0,
          "forbidden_attempts": 0,
          "java": 0,
          "other_process": 0,
          "python_domain_child": 1,
          "socket": 0
        },
        "original_child_command_preserved": true,
        "original_frozen_source_sha256": "e0455b4eb9b5328bf1484dad08a6f57733e93d9e54bc10e84154ba2e7993bab6",
        "output_only_rebound_to_new_phase": true,
        "passed": true
      }
    },
    "benchmark": {
      "command": [
        "C:\\Python314\\python.exe",
        "-S",
        "-B",
        "C:\\Users\\Admin\\Documents\\Code\\J.A.R.V.I.S\\districts\\C.A.T.T.U.S\\docs\\roadmap\\phases\\RUNTIME_SANDBOX_2_PRELADDER_DIAG_1\\validation.py",
        "worker",
        "benchmark"
      ],
      "exit_code": 0,
      "passed": true,
      "stderr_retained": "benchmark.stderr.txt",
      "stdout_retained": "benchmark.stdout.txt",
      "worker_result": {
        "arguments": [
          "benchmarks/run_benchmarks.py",
          "--check"
        ],
        "audit_guard": {
          "allowed_pure_domain_children": 0,
          "forbidden_process_attempts": 0,
          "forbidden_socket_attempts": 0,
          "forbidden_write_attempts": 0
        },
        "exit_code": 0,
        "passed": true
      }
    },
    "historical_byte_preservation": {
      "changed_or_missing": [],
      "historical_file_count": 2126,
      "passed": true,
      "unexpected_new_files_outside_phase": []
    },
    "pytest": {
      "command": [
        "C:\\Python314\\python.exe",
        "-B",
        "C:\\Users\\Admin\\Documents\\Code\\J.A.R.V.I.S\\districts\\C.A.T.T.U.S\\docs\\roadmap\\phases\\RUNTIME_SANDBOX_2_PRELADDER_DIAG_1\\validation.py",
        "worker",
        "pytest"
      ],
      "exit_code": 0,
      "passed": true,
      "stderr_retained": "pytest.stderr.txt",
      "stdout_retained": "pytest.stdout.txt",
      "worker_result": {
        "args": [
          "-q",
          "-p",
          "no:cacheprovider",
          "-o",
          "addopts=",
          "-o",
          "log_file=C:\\Users\\Admin\\Documents\\Code\\J.A.R.V.I.S\\districts\\C.A.T.T.U.S\\docs\\roadmap\\phases\\RUNTIME_SANDBOX_2_PRELADDER_DIAG_1\\validation_tmp\\pytest-log-sandbox2.txt",
          "--basetemp=C:\\Users\\Admin\\Documents\\Code\\J.A.R.V.I.S\\districts\\C.A.T.T.U.S\\docs\\roadmap\\phases\\RUNTIME_SANDBOX_2_PRELADDER_DIAG_1\\validation_tmp\\pytest-basetemp-sandbox2-11660",
          "tests/test_runtime_sandbox2.py",
          "C:\\Users\\Admin\\Documents\\Code\\J.A.R.V.I.S\\districts\\C.A.T.T.U.S\\docs\\roadmap\\phases\\RUNTIME_SANDBOX_2_PRELADDER_DIAG_1\\test_classifier.py"
        ],
        "audit_guard": {
          "allowed_pure_domain_children": 0,
          "forbidden_process_attempts": 0,
          "forbidden_socket_attempts": 0,
          "forbidden_write_attempts": 0
        },
        "exit_code": 0,
        "failed_test_count": 0,
        "failed_test_ids": [],
        "passed": true,
        "passed_test_count": 230,
        "skipped_test_ids": [],
        "temporary_root_confined_to_new_phase": true
      }
    },
    "registry_picker_baseline_vs_after": {
      "passed": true,
      "picker_equal": true,
      "registry_equal": true
    },
    "registry_picker_pure_test_baseline_vs_after": {
      "after": {
        "exit_code": 1,
        "failed_test_count": 7,
        "failed_test_ids": [
          {
            "nodeid": "tests/test_phase_picker.py::test_behavioral_runtime_executor_is_blocked_and_never_recommended_without_isolation",
            "when": "call"
          },
          {
            "nodeid": "tests/test_phase_picker.py::test_seed_registry_produces_expected_buckets",
            "when": "call"
          },
          {
            "nodeid": "tests/test_phase_picker.py::test_verified_runtime_sandbox_is_history_and_executor_stays_blocked",
            "when": "call"
          },
          {
            "nodeid": "tests/test_phase_registry.py::test_live_strict_envelope_dogfood_is_the_first_phase_to_declare_a_model_call",
            "when": "call"
          },
          {
            "nodeid": "tests/test_phase_registry.py::test_seed_registry_has_expected_phases",
            "when": "call"
          },
          {
            "nodeid": "tests/test_phase_registry.py::test_seed_registry_is_conservative",
            "when": "call"
          },
          {
            "nodeid": "tests/test_phase_registry.py::test_seed_registry_summary_counts",
            "when": "call"
          }
        ],
        "passed_test_count": 292,
        "skipped_test_ids": []
      },
      "after_retained": "worker_registry-picker-after.json",
      "audit_guards_no_effect_attempts": true,
      "baseline": {
        "exit_code": 1,
        "failed_test_count": 7,
        "failed_test_ids": [
          {
            "nodeid": "tests/test_phase_picker.py::test_behavioral_runtime_executor_is_blocked_and_never_recommended_without_isolation",
            "when": "call"
          },
          {
            "nodeid": "tests/test_phase_picker.py::test_seed_registry_produces_expected_buckets",
            "when": "call"
          },
          {
            "nodeid": "tests/test_phase_picker.py::test_verified_runtime_sandbox_is_history_and_executor_stays_blocked",
            "when": "call"
          },
          {
            "nodeid": "tests/test_phase_registry.py::test_live_strict_envelope_dogfood_is_the_first_phase_to_declare_a_model_call",
            "when": "call"
          },
          {
            "nodeid": "tests/test_phase_registry.py::test_seed_registry_has_expected_phases",
            "when": "call"
          },
          {
            "nodeid": "tests/test_phase_registry.py::test_seed_registry_is_conservative",
            "when": "call"
          },
          {
            "nodeid": "tests/test_phase_registry.py::test_seed_registry_summary_counts",
            "when": "call"
          }
        ],
        "passed_test_count": 292,
        "skipped_test_ids": []
      },
      "baseline_retained": "registry_picker_pure_test_baseline.json",
      "passed": true,
      "same_failure_ids_and_outcome_counts": true,
      "unchanged_historical_failures_preserved": true
    },
    "source_json_whitespace_diff_checks": {
      "authored_text_files_checked": 26,
      "bytecode_emission": false,
      "failures": [],
      "git_diff_check_exit_code": 0,
      "new_json_files_parsed": 18,
      "new_python_sources_compiled_in_memory": 4,
      "passed": true
    }
  },
  "validation_passed": true
}
```

[Full measured report](RUNTIME_SANDBOX_2_PRELADDER_DIAG_1_REPORT.json) · [Live result](live_result.json) · [Validation](validation_summary.json) · [Post-live artifact checks](post_live_validation.json) · [Preservation baseline](preservation_baseline.json)

**STOP:** one authorized standalone diagnostic only. No remediation, further issuance, JAVA.1C continuation, SYNTH retry, lease consumption, reflection, SyntheticStateBox, BANK, EXECUTOR or Apply follows.
