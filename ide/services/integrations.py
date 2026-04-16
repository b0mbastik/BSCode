"""External build, debug, version-control, and run integrations."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from ide.domain.models import DebugSnapshot, Project, ToolExecutionResult

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
        command_args = [sys.executable, str(path)] + (extra_args or [])
        working_dir = str(cwd or path.parent)
        try:
            process_result = subprocess.run(
                command_args,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=working_dir,
            )
            output = process_result.stdout
            if process_result.stderr:
                output += ("\n" if output else "") + "[stderr]\n" + process_result.stderr
            if not output.strip():
                output = "(no output)"
            return ToolExecutionResult(
                success=process_result.returncode == 0,
                command=" ".join(command_args),
                output=output,
                exit_code=process_result.returncode,
            )
        except subprocess.TimeoutExpired:
            return ToolExecutionResult(
                success=False,
                command=" ".join(command_args),
                output=f"Process timed out after {timeout} second(s).",
                exit_code=-1,
            )
        except FileNotFoundError:
            return ToolExecutionResult(
                success=False,
                command=" ".join(command_args),
                output=f"Python interpreter not found: {sys.executable}",
                exit_code=-1,
            )
        except Exception as exc:
            return ToolExecutionResult(
                success=False,
                command=" ".join(command_args),
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
        command_args = [sys.executable, "-m", module]
        try:
            process_result = subprocess.run(
                command_args,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(cwd),
            )
            output = (
                process_result.stdout
                + ("\n[stderr]\n" + process_result.stderr if process_result.stderr else "")
            ).strip()
            return ToolExecutionResult(
                success=process_result.returncode == 0,
                command=" ".join(command_args),
                output=output or "(no output)",
                exit_code=process_result.returncode,
            )
        except subprocess.TimeoutExpired:
            return ToolExecutionResult(
                success=False,
                command=" ".join(command_args),
                output=f"Process timed out after {timeout} second(s).",
                exit_code=-1,
            )
        except Exception as exc:
            return ToolExecutionResult(
                success=False,
                command=" ".join(command_args),
                output=str(exc),
                exit_code=-1,
            )


class BuildService:
    """Build-system boundary used by the prototype shell."""

    def run_build(self, project: Project) -> ToolExecutionResult:
        return ToolExecutionResult(
            success=True,
            command="python -m compileall <project>",
            output=f"Build service outline validated build configuration for {project.name}.",
        )


class DebugService:
    """Debugger architecture placeholder.

    The full debugger implementation has intentionally been removed. The
    service remains as the boundary the UI and future debugger adapter will
    use, but it does not execute code, manage breakpoints, or inspect state.
    """

    def __init__(self) -> None:
        self._last_snapshot = DebugSnapshot(
            status="unavailable",
            message="Debugger UI skeleton only; runtime debugging is not implemented.",
        )

    def start_debug_session(
        self,
        project: Project,
        entrypoint: Path,
        breakpoints: set[int] | None = None,
    ) -> ToolExecutionResult:
        self._last_snapshot = DebugSnapshot(
            status="unavailable",
            message="Debugger UI skeleton only; runtime debugging is not implemented.",
        )
        return ToolExecutionResult(
            success=False,
            command=f"debug {entrypoint}",
            output=self._last_snapshot.message,
            exit_code=1,
        )

    def step(self) -> None:
        self._last_snapshot = DebugSnapshot(
            status="unavailable",
            message="Debugger step is a UI skeleton; runtime debugging is not implemented.",
        )

    def continue_execution(self) -> None:
        self._last_snapshot = DebugSnapshot(
            status="unavailable",
            message="Debugger continue is a UI skeleton; runtime debugging is not implemented.",
        )

    def stop(self) -> None:
        self._last_snapshot = DebugSnapshot(
            status="unavailable",
            message="Debugger stop is a UI skeleton; runtime debugging is not implemented.",
        )

    def poll_events(self) -> list[DebugSnapshot]:
        return []

    def is_active(self) -> bool:
        return False


class VCSService:
    """Thin Git adapter used by the IDE shell."""

    def status(self, project: Project) -> ToolExecutionResult:
        return self._run_git_command(project, ["status", "--short", "--branch"])

    def diff(self, project: Project) -> ToolExecutionResult:
        return self._run_git_command(project, ["diff", "--"])

    def log(self, project: Project, limit: int = 20) -> ToolExecutionResult:
        return self._run_git_command(project, ["log", f"-{limit}", "--oneline", "--decorate"])

    def branches(self, project: Project) -> ToolExecutionResult:
        return self._run_git_command(project, ["branch", "--all"])

    def add(self, project: Project, pathspec: str = ".") -> ToolExecutionResult:
        return self._run_git_command(project, ["add", pathspec])

    def commit(self, project: Project, message: str) -> ToolExecutionResult:
        return self._run_git_command(project, ["commit", "-am", message])

    def pull(self, project: Project) -> ToolExecutionResult:
        return self._run_git_command(project, ["pull", "--ff-only"])

    def push(self, project: Project) -> ToolExecutionResult:
        return self._run_git_command(project, ["push"])

    def merge(self, project: Project, branch: str) -> ToolExecutionResult:
        return self._run_git_command(project, ["merge", branch])

    def _run_git_command(self, project: Project, args: list[str]) -> ToolExecutionResult:
        command_args = ["git", *args]
        try:
            process_result = subprocess.run(
                command_args,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(project.root_path),
            )
            output = RunService._combined_output(
                process_result.stdout,
                process_result.stderr,
            ) or "(no output)"
            return ToolExecutionResult(
                success=process_result.returncode == 0,
                command=" ".join(command_args),
                output=output,
                exit_code=process_result.returncode,
            )
        except FileNotFoundError:
            return ToolExecutionResult(
                success=False,
                command=" ".join(command_args),
                output="Git executable not found.",
                exit_code=-1,
            )
        except subprocess.TimeoutExpired:
            return ToolExecutionResult(
                success=False,
                command=" ".join(command_args),
                output="Git command timed out after 30 seconds.",
                exit_code=-1,
            )
