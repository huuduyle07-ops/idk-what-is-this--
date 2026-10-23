"""Effect denial for PREFLIGHT.RUNTIME.1, installed before fixture construction.

The outer guard may permit pytest's collection/cache I/O (strict=False). It
still denies every process, console, network, provider, compiler, reflection
render and runtime-receipt path before project modules are imported. The
focused suite and replay use strict=True for their whole fixture/test lifetime.
This is verification machinery, not a candidate-runtime sandbox or executor.
"""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field
import importlib
import os
from pathlib import Path
import sys
from unittest.mock import patch


@dataclass
class EffectDenialEvidence:
    """Record attempted effects; successful execution is never possible here."""

    denied_attempts: dict[str, int] = field(default_factory=dict)

    def deny(self, effect):
        def forbidden(*args, **kwargs):
            self.denied_attempts[effect] = self.denied_attempts.get(effect, 0) + 1
            raise AssertionError("PREFLIGHT.RUNTIME.1 effect denied: " + effect)
        return forbidden


@contextmanager
def no_runtime_effects(*, strict=True):
    """Deny effects before imports; strict mode also forbids writes/traversal."""
    evidence = EffectDenialEvidence()
    with ExitStack() as guards:
        guards.enter_context(patch.object(sys, "dont_write_bytecode", True))
        active = [True]

        def audit_denial(event, args):
            if active[0] and (event in {"subprocess.Popen", "os.system", "os.exec",
                    "os.posix_spawn", "os.spawn", "pty.spawn", "os.startfile"}
                    or event.startswith("os.startfile/")):
                evidence.deny("audit:" + event)(*args)

        # Unlike a mock, an audit hook survives a test temporarily replacing
        # subprocess.Popen. Its active flag is cleared on context exit.
        sys.addaudithook(audit_denial)
        guards.callback(active.__setitem__, 0, False)
        # These denials are installed first: project import and all fixture
        # construction are already unable to launch a compiler or Java.
        for target in (
                "subprocess.Popen", "subprocess.run", "subprocess.call",
                "subprocess.check_call", "subprocess.check_output",
                "os.system", "os.popen", "multiprocessing.Process.start",
                "asyncio.create_subprocess_exec", "asyncio.create_subprocess_shell",
                "socket.create_connection", "socket.socket.connect",
                "socket.socket.connect_ex", "builtins.input"):
            guards.enter_context(patch(target, side_effect=evidence.deny(target)))
        for name in dir(os):
            if name.startswith(("spawn", "exec")) or name in {
                    "startfile", "fork", "forkpty", "openpty", "posix_spawn", "posix_spawnp"}:
                target = "os." + name
                guards.enter_context(patch(target, side_effect=evidence.deny(target)))
        if sys.platform == "win32":
            import _winapi
            import msvcrt
            guards.enter_context(patch.object(_winapi, "CreateProcess",
                side_effect=evidence.deny("_winapi.CreateProcess")))
            for name in ("getch", "getwch", "kbhit"):
                guards.enter_context(patch.object(msvcrt, name,
                    side_effect=evidence.deny("msvcrt." + name)))
        else:
            guards.enter_context(patch("pty.openpty", side_effect=evidence.deny("pty.openpty")))
            guards.enter_context(patch("pty.spawn", side_effect=evidence.deny("pty.spawn")))

        # Import only after process and network effects have been denied.
        # A future implementation cannot gain permission by merely importing
        # a frozen adapter or calling its trusted receipt issuer.
        for target in (
                "core.pipeline.run_gemini_request", "core.pipeline.run_deepseek_review",
                "core.structural_patch_author.StructuralAuthorInvocation.run",
                "core.structural_compile_validation.compile_materialized_structural_candidate",
                "core.structural_compile_validation._run_javac",
                "core.read_only_reflection_java.render_read_only_reflection_adapter",
                "core.read_only_reflection._issue_adapter_observation",
                "web.preflight_request._start"):
            guards.enter_context(patch(target, side_effect=evidence.deny(target)))

        semantic = importlib.import_module("core.semantic_waiter_adapter")
        original_complete = semantic.SemanticWaiterModelAdapter._complete

        def guarded_complete(adapter, *args, **kwargs):
            # Adjacent authority regressions replay frozen canned semantic
            # input through the adapter. The focused phase denies even that;
            # the collector/bootstrap mode permits only the exact pure class.
            if not strict and type(adapter._client) is semantic.ScriptedSemanticModelClient:
                return original_complete(adapter, *args, **kwargs)
            return evidence.deny("core.semantic_waiter_adapter.SemanticWaiterModelAdapter._complete")(
                adapter, *args, **kwargs)

        guards.enter_context(patch.object(semantic.SemanticWaiterModelAdapter,
            "_complete", guarded_complete))

        # No adapter execution entry point currently exists. Also deny any
        # conventional run/execute entry point if the frozen module grows one.
        for module_name in ("core.read_only_reflection", "core.read_only_reflection_java"):
            module = importlib.import_module(module_name)
            for name in dir(module):
                if name.startswith(("execute_", "run_")) and callable(getattr(module, name)):
                    target = module_name + "." + name
                    guards.enter_context(patch.object(module, name,
                        side_effect=evidence.deny(target)))

        if strict:
            for target in (
                    "os.walk", "os.scandir", "os.listdir", "pathlib.Path.glob",
                    "pathlib.Path.rglob", "pathlib.Path.iterdir",
                    "pathlib.Path.write_bytes", "pathlib.Path.write_text",
                    "os.rename", "os.replace", "os.remove", "os.unlink",
                    "os.mkdir", "os.makedirs", "os.rmdir"):
                guards.enter_context(patch(target, side_effect=evidence.deny(target)))

            original_os_open = os.open

            def read_only_os_open(path, flags, *args, **kwargs):
                if str(path).replace("\\", "/").split("/")[-1].upper() in {"CON", "CONIN$", "CONOUT$"}:
                    return evidence.deny("console_handle")(path, flags)
                write_flags = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
                if flags & write_flags:
                    return evidence.deny("filesystem_write")(path, flags)
                return original_os_open(path, flags, *args, **kwargs)

            guards.enter_context(patch("os.open", read_only_os_open))

            original_open = open

            def read_only_open(file, mode="r", *args, **kwargs):
                if str(file).replace("\\", "/").split("/")[-1].upper() in {"CON", "CONIN$", "CONOUT$"}:
                    return evidence.deny("console_handle")(file, mode)
                if any(flag in mode for flag in ("w", "a", "x", "+")):
                    return evidence.deny("filesystem_write")(file, mode)
                return original_open(file, mode, *args, **kwargs)

            guards.enter_context(patch("builtins.open", read_only_open))
            guards.enter_context(patch("io.open", read_only_open))
            original_path_open = Path.open

            def read_only_path_open(path, mode="r", *args, **kwargs):
                if str(path).replace("\\", "/").split("/")[-1].upper() in {"CON", "CONIN$", "CONOUT$"}:
                    return evidence.deny("console_handle")(path, mode)
                if any(flag in mode for flag in ("w", "a", "x", "+")):
                    return evidence.deny("filesystem_write")(path, mode)
                return original_path_open(path, mode, *args, **kwargs)

            guards.enter_context(patch.object(Path, "open", read_only_path_open))
        yield evidence
