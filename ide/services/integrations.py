"""External build, debug, version-control, and run integrations."""

from __future__ import annotations

import bdb
import contextlib
import io
import os
import queue
import subprocess
import sys
import tempfile
import threading
import traceback
from pathlib import Path

from ide.domain.models import DebugFrameSnapshot, DebugSnapshot, Project, ToolExecutionResult

_DEFAULT_RUN_TIMEOUT = 30  # seconds


class RunService:
    """Executes supported source files in subprocesses and captures output.

    stdout and stderr are both captured and returned in the result so the
    IDE shell can display them in the Output panel.
    """

    def run_file(
        self,
        path: Path,
        *,
        cwd: Path | None = None,
        timeout: int = _DEFAULT_RUN_TIMEOUT,
        extra_args: list[str] | None = None,
    ) -> ToolExecutionResult:
        cmd = [sys.executable, str(path)] + (extra_args or [])
        working_dir = str(cwd or path.parent)
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=working_dir,
            )
            output = proc.stdout
            if proc.stderr:
                output += ("\n" if output else "") + "[stderr]\n" + proc.stderr
            if not output.strip():
                output = "(no output)"
            return ToolExecutionResult(
                success=proc.returncode == 0,
                command=" ".join(cmd),
                output=output,
                exit_code=proc.returncode,
            )
        except subprocess.TimeoutExpired:
            return ToolExecutionResult(
                success=False,
                command=" ".join(cmd),
                output=f"Process timed out after {timeout} second(s).",
                exit_code=-1,
            )
        except FileNotFoundError:
            return ToolExecutionResult(
                success=False,
                command=" ".join(cmd),
                output=f"Python interpreter not found: {sys.executable}",
                exit_code=-1,
            )
        except Exception as exc:  # noqa: BLE001
            return ToolExecutionResult(
                success=False,
                command=" ".join(cmd),
                output=f"Failed to start process: {exc}",
                exit_code=-1,
            )

    def run_java_file(
        self,
        path: Path,
        *,
        cwd: Path | None = None,
        timeout: int = _DEFAULT_RUN_TIMEOUT,
    ) -> ToolExecutionResult:
        """Compile and run a Java file using ``javac`` and ``java`` if available."""
        source = path.read_text(encoding="utf-8", errors="replace")
        package = self._java_package(source)
        class_name = f"{package}.{path.stem}" if package else path.stem
        working_dir = str(cwd or path.parent)
        with tempfile.TemporaryDirectory(prefix="bscode-java-") as build_dir:
            compile_cmd = ["javac", "-d", build_dir, str(path)]
            run_cmd = ["java", "-cp", build_dir, class_name]
            try:
                compile_proc = subprocess.run(
                    compile_cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=working_dir,
                )
                if compile_proc.returncode != 0:
                    return ToolExecutionResult(
                        success=False,
                        command=" ".join(compile_cmd),
                        output=self._combined_output(compile_proc.stdout, compile_proc.stderr)
                        or "Java compilation failed.",
                        exit_code=compile_proc.returncode,
                    )
                run_proc = subprocess.run(
                    run_cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=working_dir,
                )
                return ToolExecutionResult(
                    success=run_proc.returncode == 0,
                    command=" ".join(compile_cmd) + " && " + " ".join(run_cmd),
                    output=self._combined_output(run_proc.stdout, run_proc.stderr) or "(no output)",
                    exit_code=run_proc.returncode,
                )
            except FileNotFoundError as exc:
                tool = exc.filename or "javac/java"
                return ToolExecutionResult(
                    success=False,
                    command=" ".join(compile_cmd) + " && " + " ".join(run_cmd),
                    output=f"Java tool not found: {tool}. Install a JDK to run Java files.",
                    exit_code=-1,
                )
            except subprocess.TimeoutExpired:
                return ToolExecutionResult(
                    success=False,
                    command=" ".join(compile_cmd) + " && " + " ".join(run_cmd),
                    output=f"Java process timed out after {timeout} second(s).",
                    exit_code=-1,
                )

    @staticmethod
    def _java_package(source: str) -> str:
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith("package ") and stripped.endswith(";"):
                return stripped.removeprefix("package ").removesuffix(";").strip()
        return ""

    @staticmethod
    def _combined_output(stdout: str, stderr: str) -> str:
        output = stdout
        if stderr:
            output += ("\n" if output else "") + "[stderr]\n" + stderr
        return output.strip()

    def run_module(
        self,
        module: str,
        *,
        cwd: Path,
        timeout: int = _DEFAULT_RUN_TIMEOUT,
    ) -> ToolExecutionResult:
        """Run ``python -m <module>`` inside *cwd*."""
        cmd = [sys.executable, "-m", module]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(cwd),
            )
            output = (proc.stdout + ("\n[stderr]\n" + proc.stderr if proc.stderr else "")).strip()
            return ToolExecutionResult(
                success=proc.returncode == 0,
                command=" ".join(cmd),
                output=output or "(no output)",
                exit_code=proc.returncode,
            )
        except subprocess.TimeoutExpired:
            return ToolExecutionResult(
                success=False,
                command=" ".join(cmd),
                output=f"Process timed out after {timeout} second(s).",
                exit_code=-1,
            )
        except Exception as exc:  # noqa: BLE001
            return ToolExecutionResult(
                success=False,
                command=" ".join(cmd),
                output=str(exc),
                exit_code=-1,
            )


class BuildService:
    def run_build(self, project: Project) -> ToolExecutionResult:
        return ToolExecutionResult(
            success=True,
            command="python -m compileall <project>",
            output=f"BuildService stub: validated build configuration for {project.name}.",
        )


class _PythonDebugger(bdb.Bdb):
    def __init__(
        self,
        path: Path,
        breakpoints: set[int],
        commands: "queue.Queue[str]",
        events: "queue.Queue[DebugSnapshot]",
        cwd: Path,
    ) -> None:
        super().__init__()
        self.path = path.resolve()
        self.breakpoints = breakpoints
        self.commands = commands
        self.events = events
        self.cwd = cwd
        self._output = io.StringIO()

    def run_script(self) -> None:
        for line in self.breakpoints:
            self.set_break(str(self.path), line)
        self.set_step()

        old_cwd = Path.cwd()
        globals_dict = {
            "__name__": "__main__",
            "__file__": str(self.path),
            "__package__": None,
        }
        try:
            os.chdir(self.cwd)
            source = self.path.read_text(encoding="utf-8", errors="replace")
            code = compile(source, str(self.path), "exec")
            with contextlib.redirect_stdout(self._output), contextlib.redirect_stderr(self._output):
                self.run(code, globals_dict, globals_dict)
            self.events.put(
                DebugSnapshot(
                    status="finished",
                    output=self._output.getvalue(),
                    message="Debug session finished.",
                )
            )
        except bdb.BdbQuit:
            self.events.put(
                DebugSnapshot(
                    status="stopped",
                    output=self._output.getvalue(),
                    message="Debug session stopped.",
                )
            )
        except Exception:  # noqa: BLE001 - debugger reports user-code exceptions
            self.events.put(
                DebugSnapshot(
                    status="error",
                    output=self._output.getvalue(),
                    message=traceback.format_exc(),
                )
            )
        finally:
            os.chdir(old_cwd)

    def user_line(self, frame) -> None:  # noqa: ANN001, N802 - bdb callback
        filename = Path(frame.f_code.co_filename).resolve()
        if filename != self.path:
            return
        if self.breakpoints and frame.f_lineno not in self.breakpoints:
            self.set_continue()
            return
        self.events.put(self._snapshot(frame, "paused", "Paused in debugger."))
        command = self.commands.get()
        if command == "step":
            self.set_step()
        elif command == "continue":
            self.set_continue()
        elif command == "stop":
            self.set_quit()
        else:
            self.set_step()

    def user_exception(self, frame, exc_info) -> None:  # noqa: ANN001, N802 - bdb callback
        exc_type, exc_value, _ = exc_info
        self.events.put(
            self._snapshot(
                frame,
                "paused",
                f"Exception: {exc_type.__name__}: {exc_value}",
            )
        )
        command = self.commands.get()
        if command == "continue":
            self.set_continue()
        elif command == "stop":
            self.set_quit()
        else:
            self.set_step()

    def _snapshot(self, frame, status: str, message: str) -> DebugSnapshot:  # noqa: ANN001
        stack: list[DebugFrameSnapshot] = []
        current = frame
        while current is not None:
            stack.append(
                DebugFrameSnapshot(
                    file=current.f_code.co_filename,
                    line=current.f_lineno,
                    function=current.f_code.co_name,
                )
            )
            current = current.f_back
        variables = {
            name: self._safe_repr(value)
            for name, value in frame.f_locals.items()
            if not name.startswith("__")
        }
        return DebugSnapshot(
            status=status,
            file=frame.f_code.co_filename,
            line=frame.f_lineno,
            function=frame.f_code.co_name,
            stack=stack,
            variables=variables,
            output=self._output.getvalue(),
            message=message,
        )

    @staticmethod
    def _safe_repr(value: object) -> str:
        try:
            text = repr(value)
        except Exception:  # noqa: BLE001
            text = "<unrepresentable>"
        return text if len(text) <= 160 else text[:157] + "..."


class DebugService:
    """Runs a real Python debugger session with breakpoints and stepping."""

    def __init__(self) -> None:
        self._commands: queue.Queue[str] | None = None
        self._events: queue.Queue[DebugSnapshot] | None = None
        self._thread: threading.Thread | None = None

    def start_debug_session(
        self,
        project: Project,
        entrypoint: Path,
        breakpoints: set[int] | None = None,
    ) -> ToolExecutionResult:
        if self.is_active():
            return ToolExecutionResult(
                success=False,
                command=f"debug {entrypoint}",
                output="A debug session is already active.",
                exit_code=1,
            )
        if entrypoint.suffix.lower() != ".py":
            return ToolExecutionResult(
                success=False,
                command=f"debug {entrypoint}",
                output="Debugger currently supports Python files only.",
                exit_code=1,
            )
        self._commands = queue.Queue()
        self._events = queue.Queue()
        debugger = _PythonDebugger(
            path=entrypoint,
            breakpoints=breakpoints or set(),
            commands=self._commands,
            events=self._events,
            cwd=project.root_path,
        )
        self._thread = threading.Thread(target=debugger.run_script, daemon=True)
        self._thread.start()
        return ToolExecutionResult(
            success=True,
            command=f"debug {entrypoint}",
            output=f"Debug session started for {entrypoint.name}.",
        )

    def step(self) -> None:
        self._send("step")

    def continue_execution(self) -> None:
        self._send("continue")

    def stop(self) -> None:
        self._send("stop")

    def poll_events(self) -> list[DebugSnapshot]:
        if self._events is None:
            return []
        events: list[DebugSnapshot] = []
        while True:
            try:
                events.append(self._events.get_nowait())
            except queue.Empty:
                break
        if events and events[-1].status in {"finished", "stopped", "error"}:
            self._thread = None
            self._commands = None
        return events

    def is_active(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _send(self, command: str) -> None:
        if self._commands is not None:
            self._commands.put(command)


class VCSService:
    """Thin Git adapter used by the IDE shell."""

    def status(self, project: Project) -> ToolExecutionResult:
        return self._git(project, ["status", "--short", "--branch"])

    def diff(self, project: Project) -> ToolExecutionResult:
        return self._git(project, ["diff", "--"])

    def log(self, project: Project, limit: int = 20) -> ToolExecutionResult:
        return self._git(project, ["log", f"-{limit}", "--oneline", "--decorate"])

    def branches(self, project: Project) -> ToolExecutionResult:
        return self._git(project, ["branch", "--all"])

    def commit(self, project: Project, message: str) -> ToolExecutionResult:
        return self._git(project, ["commit", "-am", message])

    def merge(self, project: Project, branch: str) -> ToolExecutionResult:
        return self._git(project, ["merge", branch])

    def _git(self, project: Project, args: list[str]) -> ToolExecutionResult:
        cmd = ["git", *args]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(project.root_path),
            )
            output = RunService._combined_output(proc.stdout, proc.stderr) or "(no output)"
            return ToolExecutionResult(
                success=proc.returncode == 0,
                command=" ".join(cmd),
                output=output,
                exit_code=proc.returncode,
            )
        except FileNotFoundError:
            return ToolExecutionResult(
                success=False,
                command=" ".join(cmd),
                output="Git executable not found.",
                exit_code=-1,
            )
        except subprocess.TimeoutExpired:
            return ToolExecutionResult(
                success=False,
                command=" ".join(cmd),
                output="Git command timed out after 30 seconds.",
                exit_code=-1,
            )
