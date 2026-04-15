"""Composition root for the IDE prototype."""

from __future__ import annotations

from pathlib import Path

from ide.analysis.engine import AnalysisManager, ConformanceChecker, PythonStaticAnalyser, StubDynAnalyser
from ide.domain.models import Artifact, ArtifactType, PluginMetadata
from ide.infrastructure.adapters import (
    FilesystemPersistence,
    NetworkSync,
    PlatformAbstraction,
    PluginRegistry,
    RevisionLog,
)
from ide.infrastructure.bscode_store import BSCodeStore
from ide.presentation.ide_shell import IDEShell
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

# ---------------------------------------------------------------------------
# File extension constants
# ---------------------------------------------------------------------------

_TEXT_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".py", ".pyw",
        ".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs",
        ".html", ".htm", ".css", ".scss", ".sass", ".less",
        ".java", ".kt", ".scala",
        ".c", ".cpp", ".cc", ".cxx", ".h", ".hpp",
        ".go", ".rs", ".swift",
        ".rb", ".php", ".lua",
        ".sh", ".bash", ".zsh", ".fish", ".bat", ".ps1",
        ".md", ".rst", ".txt",
        ".json", ".yaml", ".yml", ".toml", ".xml", ".csv",
        ".cfg", ".ini", ".env",
        ".sql",
    }
)

_SKIP_DIRS: frozenset[str] = frozenset(
    {
        ".bscode",                          # IDE-internal state — never shown as project files
        ".git", ".hg", ".svn",
        "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache",
        "node_modules", ".npm", ".yarn",
        ".venv", "venv", "env", ".tox",
        "dist", "build", "out", "target",
        ".idea", ".vscode", ".vs",
    }
)

_EXTENSION_LANGUAGE: dict[str, str] = {
    ".py": "python", ".pyw": "python",
    ".java": "java",
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript",
}

_MAX_SCAN_FILES = 300


class IDEApplication:
    def __init__(self) -> None:
        # Platform / infrastructure
        self.platform = PlatformAbstraction()
        self.plugin_registry = PluginRegistry()
        self.revision_log = RevisionLog()

        # Workspace
        self.project_manager = ProjectManager()
        self.project_registry = self.project_manager.projects
        self.session_manager = SessionManager()
        self.session_manager.sign_in_guest()

        self.persistence = FilesystemPersistence()
        self.artifact_store = ArtifactStore(self.persistence)
        self.network_sync = NetworkSync()
        self.collab_service = CollabService(self.network_sync)
        self.bscode_store: BSCodeStore | None = None   # set per open project
        self.comment_service = CommentService()
        self.version_service = VersionService(self.revision_log)
        self.traceability_service = TraceabilityService()

        # Language services
        self.language_services: dict[str, LanguageService] = {}
        self._register_builtin_plugins()

        # Analysis
        self.analysis_manager = AnalysisManager(
            language_services=self.language_services,
            static_analyser=PythonStaticAnalyser(),
            conformance_checker=ConformanceChecker(),
            dyn_analyser=StubDynAnalyser(),
        )

        # Core services
        self.build_service = BuildService()
        self.debug_service = DebugService()
        self.vcs_service = VCSService()
        self.run_service = RunService()
        self.test_service = TestService()
        self.search_service = SearchService()
        self.help_service = HelpService()

        self.shell: IDEShell | None = None

    # ------------------------------------------------------------------
    # Plugin registration
    # ------------------------------------------------------------------

    def _register_builtin_plugins(self) -> None:
        python_service = PythonLangSvc()
        self.language_services["python"] = python_service
        self.plugin_registry.register_language(
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
        self.language_services["java"] = java_service
        self.plugin_registry.register_language(
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
        for lang in (
            "plain", "javascript", "typescript", "html", "css",
            "json", "yaml", "markdown", "text", "xml", "toml",
            "bash", "sql",
        ):
            self.language_services[lang] = plain_service

    # ------------------------------------------------------------------
    # Project / file operations
    # ------------------------------------------------------------------

    def open_project(self, name: str, root_path: Path) -> None:
        normalised = self.platform.normalise_path(root_path)
        project = self.project_manager.create_project(name, normalised)
        self.bscode_store = BSCodeStore(normalised)
        self._load_project_state()
        if normalised.is_dir():
            self._scan_project_directory(project, normalised)
        else:
            for artifact in self._default_artifacts():
                self.artifact_store.save(artifact)
                self.project_manager.register_artifact(project, artifact)

    def switch_project(self, project_id: str) -> None:
        """Switch active project and reset project-local design persistence."""
        project = self.project_manager.switch_project(project_id)
        self.bscode_store = BSCodeStore(project.root_path)
        self._load_project_state()

    def load_diagrams(self) -> dict[str, str]:
        """Return saved diagram content for the active project, keyed by diagram type."""
        if self.bscode_store is None:
            return {}
        return self.bscode_store.load_all_diagrams()

    def save_diagram(self, diagram_type: str, content: str) -> None:
        """Persist *content* for *diagram_type* under ``.bscode/design/``."""
        if self.bscode_store is not None:
            self.bscode_store.save_diagram(diagram_type, content)

    def persist_project_state(self) -> None:
        """Persist project-local comments, trace links, and revision history."""
        if self.bscode_store is None:
            return
        self.bscode_store.save_comments(self.comment_service.all_comments())
        self.bscode_store.save_trace_links(self.traceability_service.get_all())
        self.bscode_store.save_revisions(self.version_service.all_revisions())

    def open_file(self, path: Path) -> Artifact | None:
        """Open a single file and register it with the active project."""
        normalised = self.platform.normalise_path(path)
        if not normalised.is_file():
            return None
        if normalised.suffix.lower() not in _TEXT_EXTENSIONS:
            return None

        # Re-use an existing artefact for this path.
        project = self.project_manager.active_project
        if project is not None:
            for artifact_id in project.artifacts:
                existing = self.artifact_store.load(artifact_id)
                if existing is not None and existing.path == normalised:
                    return existing

        artifact = self._artifact_from_path(normalised)
        if project is None:
            self.open_project(normalised.parent.name or "Opened File", normalised.parent)
            project = self.project_manager.active_project

        assert project is not None
        self.artifact_store.save(artifact)
        self.project_manager.register_artifact(project, artifact)
        return artifact

    def register_language_extension(self, service: object, extensions: list[str]) -> None:
        """Public API for plugin developers to register a custom language service."""
        for ext in extensions:
            lang = ext.lstrip(".")
            self.language_services[lang] = service  # type: ignore[assignment]

    # ------------------------------------------------------------------
    # Shell entry point
    # ------------------------------------------------------------------

    def show(self) -> IDEShell:
        if self.project_manager.active_project is None:
            self.open_project("Architecture IDE Demo", Path.cwd())
        self.shell = IDEShell(self)
        self.shell.show()
        return self.shell

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _scan_project_directory(self, project, root_path: Path) -> None:
        count = 0
        for path in sorted(root_path.rglob("*")):
            if count >= _MAX_SCAN_FILES:
                break
            if not path.is_file():
                continue
            rel = path.relative_to(root_path)
            if any(part in _SKIP_DIRS or part.startswith(".") for part in rel.parts[:-1]):
                continue
            if path.suffix.lower() not in _TEXT_EXTENSIONS:
                continue
            artifact = self._artifact_from_path(path)
            self.artifact_store.save(artifact)
            self.project_manager.register_artifact(project, artifact)
            count += 1

    def _load_project_state(self) -> None:
        if self.bscode_store is None:
            return
        self.comment_service.replace_all(self.bscode_store.load_comments())
        self.traceability_service.replace_all(self.bscode_store.load_trace_links())
        self.version_service.replace_all(self.bscode_store.load_revisions())

    def _artifact_from_path(self, path: Path) -> Artifact:
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            content = ""
        ext = path.suffix.lower()
        language = _EXTENSION_LANGUAGE.get(ext, "plain")
        return Artifact(
            name=path.name,
            artifact_type=ArtifactType.CODE,
            language=language,
            content=content,
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
                    "        # TODO: connect to real project commands\n"
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
