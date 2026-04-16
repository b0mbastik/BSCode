"""External tool integration boundaries.

This outline implementation keeps the service APIs for running files, building,
debugging, and version control, but intentionally avoids invoking subprocesses
or driving real debuggers.  The classes return typed placeholder results so the
presentation layer can demonstrate interactions without claiming production
tool integration.
"""

from __future__ import annotations

from pathlib import Path

from ide.domain.models import DebugSnapshot, DebugStatus, Project, ToolExecutionResult


class RunService:
    """Boundary for interpreter/compiler execution.

    Future adapters may call Python, Java, or other toolchains.  The coursework
    skeleton returns an explicit placeholder result instead.
    """

    def run_file(
        self,
        path: Path,
        *,
        cwd: Path | None = None,
        timeout: int = 30,
        extra_args: list[str] | None = None,
    ) -> ToolExecutionResult:
        return ToolExecutionResult(
            success=True,
            command=f"run {path.name}",
            output="RunService boundary only: interpreter execution is not implemented.",
        )

    def run_java_file(
        self,
        path: Path,
        *,
        cwd: Path | None = None,
        timeout: int = 30,
    ) -> ToolExecutionResult:
        return ToolExecutionResult(
            success=True,
            command=f"run-java {path.name}",
            output="Java compile/run boundary only: javac/java integration is not implemented.",
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
        """Structural hook retained for a future Java adapter."""
        return ""


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
