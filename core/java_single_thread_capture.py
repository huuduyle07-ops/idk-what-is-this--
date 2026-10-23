"""JAVA.1B Linux pipe capture; used only by the fixed sandbox controller.

The Windows Docker-control capture and frozen historical controllers are not
changed. Importing this module performs no process or filesystem operation.
"""
import inspect
import os
import selectors
import signal
import subprocess
import time


def capture_process(argv, limit, *, deadline, on_start=None):
    """Read two nonblocking pipes with one thread and bounded working memory."""
    if type(limit) is not int or not 0 <= limit <= 2048:
        raise ValueError('fixed_stage_capture_limit_required')
    outputs = [bytearray(), bytearray()]
    result = {'status': 'completed', 'pid': None, 'exit_code': None,
        'overflow': False, 'timed_out': False, 'cleanup_verified': False,
        'cleanup_errors': [], 'controller_error': '', 'eof': [False, False],
        'read_bytes': [0, 0]}
    child = poller = None
    try:
        if time.monotonic() >= deadline:
            result.update(status='timeout', timed_out=True)
        else:
            child = subprocess.Popen(argv, shell=False, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                env=dict(os.environ), cwd='/work', start_new_session=True)
            result['pid'] = child.pid
            if on_start is not None: on_start(child)
            poller = selectors.DefaultSelector()
            for index, stream in enumerate((child.stdout, child.stderr)):
                os.set_blocking(stream.fileno(), False)
                poller.register(stream, selectors.EVENT_READ, index)
            while poller.get_map() or child.poll() is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    result.update(status='timeout', timed_out=True)
                    break
                for key, _ in poller.select(min(.01, remaining)):
                    index = key.data
                    available = limit - len(outputs[index])
                    try:
                        data = os.read(key.fd, min(256, available + 1))
                    except (BlockingIOError, InterruptedError):
                        continue
                    if not data:
                        result['eof'][index] = True
                        poller.unregister(key.fileobj)
                        continue
                    result['read_bytes'][index] += len(data)
                    outputs[index].extend(data[:available])
                    if len(data) > available:
                        result.update(status='output_limit', overflow=True)
                        break
                if result['overflow']: break
    except Exception as error:
        result.update(status='controller_exception',
            controller_error=type(error).__name__ + ': ' + str(error)[:200])
    finally:
        if child is not None:
            # Every fixed child gets its own session/process group. Kill the
            # group even after parent exit, so descendants cannot hold pipes.
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except Exception as error:
                result['cleanup_errors'].append('kill_group:' + type(error).__name__)
                try:
                    if child.poll() is None: child.kill()
                except Exception:
                    result['cleanup_errors'].append('kill_child_failed')
            try:
                child.wait(timeout=1)
            except Exception as error:
                result['cleanup_errors'].append('wait:' + type(error).__name__)
            # PID 1 adopts orphaned children inside this private container.
            # Reap only this phase child's process group, with a bounded wait.
            reap_deadline = time.monotonic() + .25
            for _ in range(128):
                try:
                    pid, _ = os.waitpid(-child.pid, os.WNOHANG)
                    if pid: continue
                except ChildProcessError:
                    break
                except Exception as error:
                    result['cleanup_errors'].append('reap:' + type(error).__name__)
                    break
                if time.monotonic() >= reap_deadline:
                    result['cleanup_errors'].append('descendant_reap_timeout')
                    break
                time.sleep(.001)
            else:
                result['cleanup_errors'].append('descendant_reap_budget_exhausted')
            try:
                os.killpg(child.pid, 0)
                result['cleanup_errors'].append('process_group_survived')
            except ProcessLookupError:
                pass
            except Exception as error:
                result['cleanup_errors'].append('group_check:' + type(error).__name__)
        if poller is not None:
            try:
                for key in list(poller.get_map().values()):
                    try:
                        poller.unregister(key.fileobj)
                    except Exception:
                        result['cleanup_errors'].append('unregister_failed')
            except Exception:
                result['cleanup_errors'].append('selector_map_failed')
            finally:
                try: poller.close()
                except Exception: result['cleanup_errors'].append('selector_close_failed')
        if child is not None:
            for stream in (child.stdout, child.stderr):
                try: stream.close()
                except Exception: result['cleanup_errors'].append('pipe_close_failed')
            result['exit_code'] = child.returncode
            result['child_waited'] = child.returncode is not None
            result['pipes_closed'] = all(s.closed for s in (child.stdout, child.stderr))
        else:
            result.update(child_waited=True, pipes_closed=True)
        result['cleanup_verified'] = (not result['cleanup_errors']
            and result['child_waited'] and result['pipes_closed'])
    result['stdout'], result['stderr'] = map(bytes, outputs)
    return result


def capture_source():
    """Embed only the reviewed function and its standard-library imports."""
    return ('import os, selectors, signal, subprocess, time\n'
        + inspect.getsource(capture_process))
