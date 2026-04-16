"""Composition root for the architecture-first IDE outline."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ide.analysis.engine import AnalysisManager, ConformanceChecker, PythonStaticAnalyser, StubDynAnalyser
from ide.domain.models import Artifact, ArtifactType, PluginMetadata, Project
from ide.infrastructure.adapters import (
    FilesystemPersistence,
    NetworkSync,
    PlatformAbstraction,
    PluginRegistry,
    RevisionLog,
)
from ide.infrastructure.bscode_store import BSCodeStore
from ide.services.help import HelpService
from ide.services.integrations import BuildService, DebugService, RunService, VCSService
from ide.services.language import JavaLangSvc, LanguageService, PlainTextLangSvc, PythonLangSvc
from ide.services.search import SearchService
from ide.services.testing import TestService
from ide.workspace.traceability import TraceabilityService
from ide.workspace.workspace_services import (
    ArtifactStore,
    CollabService,
    CommentService,
    ProjectManager,
    SessionManager,
    VersionService,
)

if TYPE_CHECKING:
    from ide.presentation.ide_shell import IDEShell

_TEXT_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".py",
        ".pyw",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".mjs",
        ".cjs",
        ".html",
        ".htm",
        ".css",
        ".scss",
        ".sass",
        ".less",
        ".java",
        ".kt",
        ".scala",
        ".c",
        ".cpp",
        ".cc",
        ".cxx",
        ".h",
        ".hpp",
        ".go",
        ".rs",
        ".swift",
        ".rb",
        ".php",
        ".lua",
        ".sh",
        ".bash",
        ".zsh",
        ".fish",
        ".bat",
        ".ps1",
        ".md",
        ".rst",
        ".txt",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".xml",
        ".csv",
        ".cfg",
        ".ini",
        ".env",
        ".sql",
    }
)

_SKIP_DIRS: frozenset[str] = frozenset(
    {
        ".bscode",
        ".git",
        ".hg",
        ".svn",
        "__pycache__",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        "node_modules",
        ".npm",
        ".yarn",
        ".venv",
        "venv",
        "env",
        ".tox",
        "dist",
        "build",
        "out",
        "target",
        ".idea",
        ".vscode",
        ".vs",
    }
)

_EXTENSION_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".pyw": "python",
    ".java": "java",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
}

_PLAIN_TEXT_LANGUAGES: tuple[str, ...] = (
    "plain",
    "javascript",
    "typescript",
    "html",
    "css",
    "json",
    "yaml",
    "markdown",
    "text",
    "xml",
    "toml",
    "bash",
    "sql",
)

_MAX_SCAN_FILES = 300


class IDEApplication:
    """Wires subsystems and exposes high-level project operations.

    This class is intentionally more concrete than the services it composes:
    its purpose is to show how the presentation, workspace, services, analysis,
    infrastructure, and plugin boundaries collaborate.
    """

    def __init__(self) -> None:
        self.platform = PlatformAbstraction()
        self.plugin_registry = PluginRegistry()
        self.revision_log = RevisionLog()

        self.project_manager = ProjectManager()
        self.project_registry = self.project_manager.projects
        self.session_manager = SessionManager()
        self.session_manager.sign_in_guest()

        self.persistence = FilesystemPersistence()
        self.artifact_store = ArtifactStore(self.persistence)
        self.network_sync = NetworkSync()
        self.collab_service = CollabService(self.network_sync)
        self.bscode_store: BSCodeStore | None = None
        self.comment_service = CommentService()
        self.version_service = VersionService(self.revision_log)
        self.traceability_service = TraceabilityService()

        self.language_services: dict[str, LanguageService] = {}
        self._register_builtin_plugins()

        self.analysis_manager = AnalysisManager(
            language_services=self.language_services,
            static_analyser=PythonStaticAnalyser(),
            conformance_checker=ConformanceChecker(),
            dyn_analyser=StubDynAnalyser(),
        )

        self.build_service = BuildService()
        self.debug_service = DebugService()
        self.vcs_service = VCSService()
        self.run_service = RunService()
        self.test_service = TestService()
        self.search_service = SearchService()
        self.help_service = HelpService()

        self.shell: IDEShell | None = None

    def _register_builtin_plugins(self) -> None:
        python_service = PythonLangSvc()
        self._register_language_plugin(
            "python",
            python_service,
            PluginMetadata(
                name="PythonLangSvc",
                version="0.1",
                extension_point="LanguageService",
                description="Prototype Python language support.",
            ),
        )

        java_service = JavaLangSvc()
        self._register_language_plugin(
            "java",
            java_service,
            PluginMetadata(
                name="JavaLangSvc",
                version="0.1",
                extension_point="LanguageService",
                description="Skeletal Java language support for outline implementation.",
            ),
        )

        plain_service = PlainTextLangSvc()
        for lang in _PLAIN_TEXT_LANGUAGES:
            self.language_services[lang] = plain_service

    def _register_language_plugin(
        self,
        language: str,
        service: LanguageService,
        metadata: PluginMetadata,
    ) -> None:
        self.language_services[language] = service
        self.plugin_registry.register_language(language, service, metadata)

    def open_project(self, name: str, root_path: Path) -> None:
        normalised = self.platform.normalise_path(root_path)
        project = self.project_manager.create_project(name, normalised)
        self.bscode_store = BSCodeStore(normalised)
        self._load_project_state()
        # Project scanning is intentionally reduced to a few representative
        # artefacts.  The file explorer and store boundaries remain visible.
        for artifact in self._default_artifacts():
            self.artifact_store.save(artifact)
            self.project_manager.register_artifact(project, artifact)

    def switch_project(self, project_id: str) -> None:
        """Switch active project and reset project-local design persistence."""
        project = self.project_manager.switch_project(project_id)
        self.bscode_store = BSCodeStore(project.root_path)
        self._load_project_state()

    def refresh_active_project_from_disk(self) -> None:
        """Refresh hook retained for the explorer; real scanning is omitted."""
        return None

    def load_diagrams(self) -> dict[str, str]:
        """Return saved diagram content for the active project, keyed by diagram type."""
        if self.bscode_store is None:
            return {}
        return self.bscode_store.load_all_diagrams()

    def persist_project_state(self) -> None:
        """Persist project-local metadata through the sidecar boundary."""
        if self.bscode_store is None:
            return
        self.bscode_store.save_comments(self.comment_service.all_comments())
        self.bscode_store.save_trace_links(self.traceability_service.get_all())
        self.bscode_store.save_revisions(self.version_service.all_revisions())

    def register_language_extension(self, service: object, extensions: list[str]) -> None:
        """Public API for plugin developers to register a custom language service."""
        for ext in extensions:
            lang = ext.lstrip(".")
            self.language_services[lang] = service  # type: ignore[assignment]

    def show(self) -> IDEShell:
        from ide.presentation.ide_shell import IDEShell

        if self.project_manager.active_project is None:
            self.open_project("Architecture IDE Demo", Path.cwd())
        self.shell = IDEShell(self)
        self.shell.show()
        return self.shell

    def _scan_project_directory(self, project: Project, root_path: Path) -> None:
        """Placeholder for a future filesystem scanner."""
        return None

    def _load_project_state(self) -> None:
        if self.bscode_store is None:
            return
        self.comment_service.replace_all(self.bscode_store.load_comments())
        self.traceability_service.replace_all(self.bscode_store.load_trace_links())
        self.version_service.replace_all(self.bscode_store.load_revisions())

    def _artifact_from_path(self, path: Path) -> Artifact:
        ext = path.suffix.lower()
        language = _EXTENSION_LANGUAGE.get(ext, "plain")
        return Artifact(
            name=path.name,
            artifact_type=ArtifactType.CODE,
            language=language,
            content="",
            path=path,
        )

    def _default_artifacts(self) -> list[Artifact]:
        return [
            Artifact(
                name="main.py",
                artifact_type=ArtifactType.CODE,
                language="python",
                content=(
                    "class IDEShellAdapter:\n"
                    "    def open(self):\n"
                    "        # Extension point for project command integration.\n"
                    "        return 'desktop shell ready'\n"
                ),
            ),
            Artifact(
                name="architecture.md",
                artifact_type=ArtifactType.CODE,
                language="plain",
                content=(
                    "# Architecture\n\n"
                    "- Presentation\n"
                    "- Workspace\n"
                    "- Core IDE Services\n"
                    "- Analysis Engine\n"
                    "- Infrastructure\n"
                ),
            ),
            Artifact(
                name="design.md",
                artifact_type=ArtifactType.CODE,
                language="plain",
                content=(
                    "# Design Notes\n\n"
                    "Architecture and design artefacts are versioned beside code.\n"
                ),
            ),
        ]
