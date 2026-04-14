"""Composition root for the IDE prototype."""

from __future__ import annotations

from pathlib import Path

from ide.analysis.engine import AnalysisManager, ConformanceChecker, PythonStaticAnalyser, StubDynAnalyser
from ide.domain.models import Artifact, ArtifactType, PluginMetadata
from ide.infrastructure.adapters import InMemoryPersistence, NetworkSync, PlatformAbstraction, PluginRegistry
from ide.presentation.ide_shell import IDEShell
from ide.services.integrations import BuildService, DebugService, VCSService
from ide.services.language import LanguageService, PythonLangSvc
from ide.workspace.workspace_services import ArtifactStore, CollabService, ProjectManager, SessionManager


class IDEApplication:
    def __init__(self) -> None:
        self.platform = PlatformAbstraction()
        self.plugin_registry = PluginRegistry()
        self.project_manager = ProjectManager()
        self.project_registry = self.project_manager.projects
        self.session_manager = SessionManager()
        self.session_manager.sign_in_guest()

        self.persistence = InMemoryPersistence()
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

    def open_project(self, name: str, root_path: Path) -> None:
        project = self.project_manager.create_project(name, self.platform.normalise_path(root_path))
        for artifact in self._default_artifacts():
            self.artifact_store.save(artifact)
            self.project_manager.register_artifact(project, artifact)

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
                artifact_type=ArtifactType.ARCHITECTURE,
                content="# Architecture\n\n- Presentation\n- Workspace\n- Core IDE Services\n- Analysis Engine\n- Infrastructure\n",
            ),
            Artifact(
                name="design.md",
                artifact_type=ArtifactType.DESIGN,
                content="# Design Notes\n\nArchitecture and design artefacts are versioned beside code.\n",
            ),
        ]
