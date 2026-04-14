"""External build, debug, version-control, and run integration stubs."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from ide.domain.models import Project, ToolExecutionResult

_DEFAULT_RUN_TIMEOUT = 30  # seconds


class RunService:
    """Executes a Python file in a subprocess and captures its output.

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
