"""Composition root for the IDE prototype."""

from __future__ import annotations

from pathlib import Path

from ide.analysis.engine import AnalysisManager, ConformanceChecker, PythonStaticAnalyser, StubDynAnalyser
from ide.domain.models import Artifact, ArtifactType, PluginMetadata
from ide.infrastructure.adapters import FilesystemPersistence, NetworkSync, PlatformAbstraction, PluginRegistry
from ide.presentation.ide_shell import IDEShell
from ide.services.integrations import BuildService, DebugService, VCSService
from ide.services.language import LanguageService, PlainTextLangSvc, PythonLangSvc
from ide.workspace.workspace_services import ArtifactStore, CollabService, ProjectManager, SessionManager

# File extensions that are treated as text and opened in the editor.
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

# Directories that are never scanned.
_SKIP_DIRS: frozenset[str] = frozenset(
    {
        ".git", ".hg", ".svn",
        "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache",
        "node_modules", ".npm", ".yarn",
        ".venv", "venv", "env", ".tox",
        "dist", "build", "out", "target",
        ".idea", ".vscode", ".vs",
    }
)

# Language identifier derived from file extension.
_EXTENSION_LANGUAGE: dict[str, str] = {
    ".py": "python", ".pyw": "python",
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript",
}

# Maximum number of files scanned from a project directory.
_MAX_SCAN_FILES = 300


class IDEApplication:
    def __init__(self) -> None:
        self.platform = PlatformAbstraction()
        self.plugin_registry = PluginRegistry()
        self.project_manager = ProjectManager()
        self.project_registry = self.project_manager.projects
        self.session_manager = SessionManager()
        self.session_manager.sign_in_guest()

        self.persistence = FilesystemPersistence()
        self.artifact_store = ArtifactStore(self.persistence)
        self.network_sync = NetworkSync()
        self.collab_service = CollabService(self.network_sync)

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
        self.shell: IDEShell | None = None

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

        plain_service = PlainTextLangSvc()
        for lang in ("plain", "javascript", "typescript", "html", "css", "json",
                     "yaml", "markdown", "text", "xml", "toml", "bash", "sql"):
            self.language_services[lang] = plain_service

    def open_project(self, name: str, root_path: Path) -> None:
        normalised = self.platform.normalise_path(root_path)
        project = self.project_manager.create_project(name, normalised)
        if normalised.is_dir():
            self._scan_project_directory(project, normalised)
        else:
            for artifact in self._default_artifacts():
                self.artifact_store.save(artifact)
                self.project_manager.register_artifact(project, artifact)

    def open_file(self, path: Path) -> Artifact | None:
        """Open a single file and register it with the active project."""
        normalised = self.platform.normalise_path(path)
        if not normalised.is_file():
            return None
        if normalised.suffix.lower() not in _TEXT_EXTENSIONS:
            return None

        # Check if already registered in the active project.
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
            # Skip files inside ignored directories.
            if any(part in _SKIP_DIRS or part.startswith(".") for part in rel.parts[:-1]):
                continue
            if path.suffix.lower() not in _TEXT_EXTENSIONS:
                continue
            artifact = self._artifact_from_path(path)
            self.artifact_store.save(artifact)
            self.project_manager.register_artifact(project, artifact)
            count += 1

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

    def show(self) -> IDEShell:
        if self.project_manager.active_project is None:
            self.open_project("Architecture IDE Demo", Path.cwd())
        self.shell = IDEShell(self)
        self.shell.show()
        return self.shell

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
                content="# Architecture\n\n- Presentation\n- Workspace\n- Core IDE Services\n- Analysis Engine\n- Infrastructure\n",
            ),
            Artifact(
                name="design.md",
                artifact_type=ArtifactType.CODE,
                language="plain",
                content="# Design Notes\n\nArchitecture and design artefacts are versioned beside code.\n",
            ),
        ]
