from __future__ import annotations

import unittest
import tempfile
from pathlib import Path

from ide.analysis.engine import AnalysisManager, ConformanceChecker, PythonStaticAnalyser, StubDynAnalyser
from ide.app.application import IDEApplication
from ide.domain.models import (
    Artifact,
    ArtifactType,
    CompletionItem,
    DebugStatus,
    Operation,
    PluginMetadata,
    TestStatus,
    TraceLink,
)
from ide.infrastructure.adapters import FilesystemPersistence, NetworkSync, PluginRegistry, RevisionLog
from ide.infrastructure.bscode_store import BSCodeStore
from ide.services.integrations import BuildService, DebugService, RunService, VCSService
from ide.services.language import JavaLangSvc, PlainTextLangSvc, PythonLangSvc
from ide.services.search import SearchService
from ide.services.testing import TestService
from ide.workspace.traceability import TraceabilityService
from ide.workspace.workspace_services import ArtifactStore, CollabService, ProjectManager, VersionService


class ArchitectureContractTests(unittest.TestCase):
    def test_application_composition_root_wires_major_subsystems(self) -> None:
        app = IDEApplication()

        self.assertIsInstance(app.project_manager, ProjectManager)
        self.assertIsInstance(app.artifact_store, ArtifactStore)
        self.assertIsInstance(app.analysis_manager, AnalysisManager)
        self.assertIn("python", app.language_services)
        self.assertIn("java", app.language_services)

    def test_domain_models_support_cross_layer_contracts(self) -> None:
        artifact = Artifact(name="main.py", artifact_type=ArtifactType.CODE, language="python")
        operation = Operation(artifact_id=artifact.artifact_id, user_id="local", position=0, text="outline")
        completion = CompletionItem(label="Placeholder")

        self.assertEqual(operation.artifact_id, artifact.artifact_id)
        self.assertEqual(completion.insert_text, "Placeholder")

    def test_project_manager_and_artifact_store_show_workspace_flow(self) -> None:
        manager = ProjectManager()
        project = manager.create_project("Outline", Path("/tmp/outline"))
        store = ArtifactStore(FilesystemPersistence())
        artifact = Artifact(name="design.md", artifact_type=ArtifactType.DESIGN)

        manager.register_artifact(project, artifact)
        store.save(artifact)

        self.assertEqual(manager.active_project, project)
        self.assertEqual(store.list_for_project(project), [artifact])

    def test_language_services_preserve_parse_complete_highlight_contract(self) -> None:
        for service in (PythonLangSvc(), JavaLangSvc(), PlainTextLangSvc()):
            snapshot = service.parse("class Example: pass", "a1")
            self.assertIn("language", snapshot.code_metadata)
            self.assertIsInstance(service.highlight("source"), list)
            self.assertIsInstance(service.complete("source", 1, 1), list)

    def test_analysis_manager_preserves_static_and_conformance_boundaries(self) -> None:
        manager = AnalysisManager(
            language_services={"python": PythonLangSvc(), "plain": PlainTextLangSvc()},
            static_analyser=PythonStaticAnalyser(),
            conformance_checker=ConformanceChecker(),
            dyn_analyser=StubDynAnalyser(),
        )
        artifact = Artifact(name="main.py", artifact_type=ArtifactType.CODE, language="python")

        static_result = manager.run_static_analysis([artifact])
        conformance_result = manager.run_conformance_check(static_result.snapshot, [TraceLink()])

        self.assertIsNotNone(static_result.snapshot)
        self.assertIn("omitted", static_result.summary)
        self.assertIn("boundary", conformance_result.summary)

    def test_dynamic_analysis_boundary_returns_non_diagnostic_result(self) -> None:
        project = ProjectManager().create_project("Outline", Path("/tmp/outline"))
        result = StubDynAnalyser().analyse_runtime(project)

        self.assertEqual(result.diagnostics, [])
        self.assertIn("outlined", result.summary)

    def test_tool_services_return_placeholder_result_objects(self) -> None:
        project = ProjectManager().create_project("Outline", Path("/tmp/outline"))

        self.assertIn("boundary", BuildService().run_build(project).output)
        self.assertIn("boundary", VCSService().status(project).output)

    def test_run_service_executes_python_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            script = root / "hello.py"
            script.write_text("print('hello from run service')\n", encoding="utf-8")

            result = RunService().run_file(script, cwd=root)

            self.assertTrue(result.success)
            self.assertIn("hello from run service", result.output)

    def test_run_service_extracts_java_package_name(self) -> None:
        source = "package edu.example;\npublic class Main {}\n"

        self.assertEqual(RunService._java_package(source), "edu.example")

    def test_debug_service_preserves_python_only_session_boundary(self) -> None:
        project = ProjectManager().create_project("Outline", Path("/tmp/outline"))
        service = DebugService()

        start = service.start_debug_session(project, Path("main.py"), {3})
        events = service.poll_events()
        service.continue_execution()
        finished = service.poll_events()

        self.assertTrue(start.success)
        self.assertEqual(events[0].status, DebugStatus.PAUSED)
        self.assertEqual(finished[-1].status, DebugStatus.FINISHED)

    def test_debug_service_rejects_non_python_entrypoints(self) -> None:
        project = ProjectManager().create_project("Outline", Path("/tmp/outline"))
        result = DebugService().start_debug_session(project, Path("Main.java"), set())

        self.assertFalse(result.success)
        self.assertIn("Python", result.output)

    def test_test_and_search_services_are_structural_boundaries(self) -> None:
        project = ProjectManager().create_project("Outline", Path("/tmp/outline"))
        test_result = TestService().run_tests(project, [])
        search_result = SearchService().search("query", [])

        self.assertEqual(test_result.suites[0].cases[0].status, TestStatus.SKIPPED)
        self.assertEqual(search_result, [])

    def test_metadata_store_keeps_bscode_boundary_without_runtime_state(self) -> None:
        store = BSCodeStore(Path("/tmp/outline"))

        self.assertEqual(store.load_all_diagrams(), {})
        self.assertEqual(store.load_comments(), [])
        self.assertEqual(store.load_trace_links(), [])
        self.assertEqual(store.load_revisions(), [])

    def test_collaboration_and_traceability_boundaries_remain_visible(self) -> None:
        network = NetworkSync()
        collab = CollabService(network)
        artifact = Artifact(name="main.py", artifact_type=ArtifactType.CODE)
        operation = Operation(artifact_id=artifact.artifact_id, user_id="u1", position=0, text="x")

        collab.submit_op(operation)
        trace_service = TraceabilityService()
        link = trace_service.add_link(TraceLink(design_element="Design", code_element="Code"))

        self.assertEqual(network.last_sent_operation, operation)
        self.assertEqual(trace_service.get_all(), [link])

    def test_revision_and_plugin_boundaries_are_structural(self) -> None:
        revision_service = VersionService(RevisionLog())
        artifact = Artifact(name="main.py", artifact_type=ArtifactType.CODE, content="print('outline')")
        revision = revision_service.autosave(artifact, "tester")

        registry = PluginRegistry()
        registry.register_language(
            "python",
            PythonLangSvc(),
            PluginMetadata(name="PythonLangSvc", version="outline", extension_point="LanguageService"),
        )

        self.assertIn("boundary", revision.message)
        self.assertEqual(revision_service.get_history(artifact.artifact_id), [])
        self.assertIsInstance(registry.get_language("python"), PythonLangSvc)


if __name__ == "__main__":
    unittest.main()
