"""External build, debug, and version-control integration stubs."""

from __future__ import annotations

from ide.domain.models import Project, ToolExecutionResult


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
