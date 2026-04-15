"""External build, debug, version-control, and run integration stubs."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from ide.domain.models import Project, ToolExecutionResult

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


class DebugService:
    def start_debug_session(self, project: Project, entrypoint: str) -> ToolExecutionResult:
        return ToolExecutionResult(
            success=True,
            command=f"python -m debugpy {entrypoint}",
            output=f"DebugService stub: debug session prepared for {project.name}.",
        )


class VCSService:
    def commit(self, project: Project, message: str) -> ToolExecutionResult:
        return ToolExecutionResult(
            success=True,
            command='git commit -m "<message>"',
            output=f'VCSService stub: would commit {project.name} with message "{message}".',
        )
