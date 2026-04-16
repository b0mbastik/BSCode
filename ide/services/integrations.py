"""External tool integration boundaries.

This module keeps tool integrations behind service boundaries.  File execution
is intentionally the one real integration retained so users can run Python and
Java files from the IDE.  Build, debug, and version-control operations remain
explicit outline boundaries.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from ide.domain.models import DebugSnapshot, DebugStatus, Project, ToolExecutionResult


class RunService:
    """Interpreter/compiler execution adapter for Python and Java files.

    This is a deliberately narrow real implementation: it runs a single Python
    file with the active interpreter, or compiles and runs a single Java source
    file through local ``javac``/``java``.  Build systems, project classpaths and
    language-specific debugging remain separate outline services.
    """

    def run_file(
        self,
        path: Path,
        *,
        cwd: Path | None = None,
        timeout: int = 30,
        extra_args: list[str] | None = None,
    ) -> ToolExecutionResult:
        command_args = [sys.executable, str(path), *(extra_args or [])]
        try:
            result = subprocess.run(
                command_args,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(cwd or path.parent),
            )
            return ToolExecutionResult(
                success=result.returncode == 0,
                command=" ".join(command_args),
                output=self._combined_output(result.stdout, result.stderr) or "(no output)",
                exit_code=result.returncode,
            )
        except FileNotFoundError:
            return ToolExecutionResult(
                success=False,
                command=" ".join(command_args),
                output=f"Python interpreter not found: {sys.executable}",
                exit_code=-1,
            )
        except subprocess.TimeoutExpired:
            return ToolExecutionResult(
                success=False,
                command=" ".join(command_args),
                output=f"Process timed out after {timeout} second(s).",
                exit_code=-1,
            )
        except OSError as exc:
            return ToolExecutionResult(
                success=False,
                command=" ".join(command_args),
                output=f"Failed to start Python process: {exc}",
                exit_code=-1,
            )

    def run_java_file(
        self,
        path: Path,
        *,
        cwd: Path | None = None,
        timeout: int = 30,
    ) -> ToolExecutionResult:
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return ToolExecutionResult(
                success=False,
                command=f"javac/java {path}",
                output=f"Could not read Java source: {exc}",
                exit_code=-1,
            )

        package = self._java_package(source)
        class_name = f"{package}.{path.stem}" if package else path.stem
        with tempfile.TemporaryDirectory(prefix="bscode-java-") as build_dir:
            compile_cmd = ["javac", "-d", build_dir, str(path)]
            run_cmd = ["java", "-cp", build_dir, class_name]
            try:
                compile_result = subprocess.run(
                    compile_cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=str(cwd or path.parent),
                )
                if compile_result.returncode != 0:
                    return ToolExecutionResult(
                        success=False,
                        command=" ".join(compile_cmd),
                        output=self._combined_output(compile_result.stdout, compile_result.stderr)
                        or "Java compilation failed.",
                        exit_code=compile_result.returncode,
                    )

                run_result = subprocess.run(
                    run_cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=str(cwd or path.parent),
                )
                return ToolExecutionResult(
                    success=run_result.returncode == 0,
                    command=" ".join(compile_cmd) + " && " + " ".join(run_cmd),
                    output=self._combined_output(run_result.stdout, run_result.stderr) or "(no output)",
                    exit_code=run_result.returncode,
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

    def run_module(
        self,
        module: str,
        *,
        cwd: Path,
        timeout: int = 30,
    ) -> ToolExecutionResult:
        return ToolExecutionResult(
            success=True,
            command=f"python -m {module}",
            output="Module execution boundary only: subprocess execution is not implemented.",
        )

    @staticmethod
    def _java_package(source: str) -> str:
        """Return the declared Java package name, if present."""
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


class BuildService:
    """Build-system boundary for Maven/Gradle/Make/etc. integrations."""

    def run_build(self, project: Project) -> ToolExecutionResult:
        return ToolExecutionResult(
            success=True,
            command="build <project>",
            output=f"BuildService boundary only for {project.name}; build automation is not implemented.",
        )


class _PythonDebugger:
    """Placeholder adapter documenting where a Python debugger would live."""

    def __init__(self, path: Path, breakpoints: set[int]) -> None:
        self.path = path
        self.breakpoints = breakpoints


class DebugService:
    """Python debugger service boundary with skeletal state transitions."""

    def __init__(self) -> None:
        self._active = False
        self._last_snapshot = DebugSnapshot(
            status=DebugStatus.IDLE,
            message="Debugger idle; runtime control is not implemented.",
        )
        self._pending_events: list[DebugSnapshot] = []

    def start_debug_session(
        self,
        project: Project,
        entrypoint: Path,
        breakpoints: set[int] | None = None,
    ) -> ToolExecutionResult:
        if entrypoint.suffix.lower() != ".py":
            self._last_snapshot = DebugSnapshot(
                status=DebugStatus.UNSUPPORTED,
                file=str(entrypoint),
                message="Debugger boundary supports Python only; Java debugging is not implemented.",
            )
            return ToolExecutionResult(
                success=False,
                command=f"debug {entrypoint.name}",
                output=self._last_snapshot.message,
                exit_code=1,
            )

        self._active = True
        _PythonDebugger(entrypoint, breakpoints or set())
        self._last_snapshot = DebugSnapshot(
            status=DebugStatus.PAUSED,
            file=str(entrypoint),
            line=next(iter(sorted(breakpoints or {1}))),
            function="<outline>",
            variables={},
            message="DebugService boundary started; execution is not actually running.",
        )
        self._pending_events.append(self._last_snapshot)
        return ToolExecutionResult(
            success=True,
            command=f"debug {entrypoint.name}",
            output=self._last_snapshot.message,
        )

    def step(self) -> None:
        self._last_snapshot = DebugSnapshot(
            status=DebugStatus.PAUSED,
            file=self._last_snapshot.file,
            line=max(1, self._last_snapshot.line + 1),
            function="<outline>",
            message="Step requested at debugger boundary; no program state changed.",
        )
        self._pending_events.append(self._last_snapshot)

    def continue_execution(self) -> None:
        self._active = False
        self._last_snapshot = DebugSnapshot(
            status=DebugStatus.FINISHED,
            file=self._last_snapshot.file,
            message="Continue requested; outline debug session marked finished.",
        )
        self._pending_events.append(self._last_snapshot)

    def stop(self) -> None:
        self._active = False
        self._last_snapshot = DebugSnapshot(
            status=DebugStatus.STOPPED,
            file=self._last_snapshot.file,
            message="Outline debug session stopped.",
        )
        self._pending_events.append(self._last_snapshot)

    def poll_events(self) -> list[DebugSnapshot]:
        events = list(self._pending_events)
        self._pending_events.clear()
        return events

    def is_active(self) -> bool:
        return self._active

    @property
    def last_snapshot(self) -> DebugSnapshot:
        return self._last_snapshot


class VCSService:
    """Version-control service boundary.

    Real Git commands are intentionally not executed in the outline
    implementation.  Each method returns a typed placeholder result.
    """

    def status(self, project: Project) -> ToolExecutionResult:
        return self._placeholder(project, "git status")

    def diff(self, project: Project) -> ToolExecutionResult:
        return self._placeholder(project, "git diff")

    def log(self, project: Project, limit: int = 20) -> ToolExecutionResult:
        return self._placeholder(project, f"git log -{limit}")

    def branches(self, project: Project) -> ToolExecutionResult:
        return self._placeholder(project, "git branch")

    def add(self, project: Project, pathspec: str = ".") -> ToolExecutionResult:
        return self._placeholder(project, f"git add {pathspec}")

    def commit(self, project: Project, message: str) -> ToolExecutionResult:
        return self._placeholder(project, f"git commit -m {message!r}")

    def pull(self, project: Project) -> ToolExecutionResult:
        return self._placeholder(project, "git pull")

    def push(self, project: Project) -> ToolExecutionResult:
        return self._placeholder(project, "git push")

    def merge(self, project: Project, branch: str) -> ToolExecutionResult:
        return self._placeholder(project, f"git merge {branch}")

    @staticmethod
    def _placeholder(project: Project, command: str) -> ToolExecutionResult:
        return ToolExecutionResult(
            success=True,
            command=command,
            output=f"VCSService boundary only for {project.name}; command not executed.",
        )
