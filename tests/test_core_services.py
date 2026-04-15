from __future__ import annotations

import unittest
from pathlib import Path

from ide.analysis.engine import AnalysisManager, ConformanceChecker, PythonStaticAnalyser, StubDynAnalyser
from ide.domain.models import Artifact, ArtifactType, Operation, TestStatus, TraceLink
from ide.infrastructure.adapters import InMemoryPersistence, RevisionLog
from ide.services.language import JavaLangSvc, PythonLangSvc
from ide.services.testing import TestService
from ide.workspace.traceability import TraceabilityService
from ide.workspace.workspace_services import ArtifactStore, ProjectManager, VersionService


class ProjectAndArtifactTests(unittest.TestCase):
    def test_project_manager_create_switch_and_register(self) -> None:
        manager = ProjectManager()
        first = manager.create_project("First", Path("/tmp/first"))
        second = manager.create_project("Second", Path("/tmp/second"))
        artifact = Artifact(name="main.py", artifact_type=ArtifactType.CODE)

        manager.register_artifact(first, artifact)
        manager.register_artifact(first, artifact)
        active = manager.switch_project(first.project_id)

        self.assertEqual(active, first)
        self.assertEqual(manager.active_project, first)
        self.assertEqual(first.artifacts, [artifact.artifact_id])
        self.assertIn(second.project_id, manager.projects)

    def test_artifact_store_uses_persistence_boundary(self) -> None:
        store = ArtifactStore(InMemoryPersistence())
        artifact = Artifact(
            name="example.py",
            artifact_type=ArtifactType.CODE,
            language="python",
            content="def run():\n    return 1\n",
        )

        store.save(artifact)

        self.assertEqual(store.load(artifact.artifact_id), artifact)


class LanguageServiceTests(unittest.TestCase):
    def test_python_language_service_extracts_metadata_and_diagnostics(self) -> None:
        service = PythonLangSvc()
        source = "class Tool:\n    pass\n\ndef build():\n    # TODO wire\n    return 1\n"

        snapshot = service.parse(source, "py-1")
        diagnostics = service.diagnostics_for(source)

        self.assertEqual(snapshot.code_metadata["classes"], ["Tool"])
        self.assertEqual(snapshot.code_metadata["functions"], ["build"])
        self.assertEqual(diagnostics[0].source, "PythonLangSvc")

    def test_java_language_service_extracts_outline_metadata(self) -> None:
        service = JavaLangSvc()
        source = "public class Tool {\n    public void build() {}\n}\n"

        snapshot = service.parse(source, "java-1")

        self.assertEqual(snapshot.code_metadata["classes"], ["Tool"])
        self.assertIn("build", snapshot.code_metadata["methods"])
        self.assertIn("class", service.complete(source, 1, 1))

    def test_java_language_service_reports_missing_type(self) -> None:
        service = JavaLangSvc()

        diagnostics = service.diagnostics_for("public void run() {}\n")

        self.assertTrue(any("no class or interface" in d.message for d in diagnostics))


class AnalysisAndTestingTests(unittest.TestCase):
    def test_analysis_manager_runs_static_and_dynamic_paths(self) -> None:
        manager = AnalysisManager(
            language_services={"python": PythonLangSvc(), "java": JavaLangSvc()},
            static_analyser=PythonStaticAnalyser(),
            conformance_checker=ConformanceChecker(),
            dyn_analyser=StubDynAnalyser(),
        )
        artifact = Artifact(
            name="Tool.java",
            artifact_type=ArtifactType.CODE,
            language="java",
            content="class Tool { void run() {} }\n",
        )

        static = manager.run_static_analysis([artifact])
        conformance = manager.run_conformance_check(static.snapshot)

        self.assertIsNotNone(static.snapshot)
        self.assertEqual(conformance.summary, "Conformance check completed using placeholder metadata.")

    def test_test_service_classifies_pass_fail_skip(self) -> None:
        service = TestService()
        project = ProjectManager().create_project("Tests", Path("/tmp/tests"))
        artifact = Artifact(
            name="test_example.py",
            artifact_type=ArtifactType.TEST,
            language="python",
            content=(
                "def test_passes():\n"
                "    assert 1\n\n"
                "def test_fails():\n"
                "    assert False\n\n"
                "def test_skipped():\n"
                "    pass\n"
            ),
        )

        result = service.run_tests(project, [artifact])
        statuses = {case.name: case.status for case in result.suites[0].cases}

        self.assertEqual(statuses["test_passes"], TestStatus.PASSED)
        self.assertEqual(statuses["test_fails"], TestStatus.FAILED)
        self.assertEqual(statuses["test_skipped"], TestStatus.SKIPPED)
        self.assertFalse(result.success)


class TraceabilityAndRevisionTests(unittest.TestCase):
    def test_traceability_links_can_be_added_queried_and_removed(self) -> None:
        service = TraceabilityService()
        service_link = TraceLink(
            design_artifact_id="design-1",
            design_element="EditorView",
            code_artifact_id="code-1",
            code_element="EditorView",
        )
        link = service.add_link(service_link)

        self.assertEqual(service.get_links_for_design("design-1"), [link])
        self.assertEqual(service.get_links_for_code("code-1"), [link])
        self.assertTrue(service.remove_link(service_link.link_id))
        self.assertEqual(service.get_all(), [])

    def test_version_service_records_checkpoints(self) -> None:
        service = VersionService(RevisionLog())
        artifact = Artifact(
            name="main.py",
            artifact_type=ArtifactType.CODE,
            content="print('v1')\n",
        )

        revision = service.checkpoint(artifact, author="tester")

        self.assertEqual(service.get_history(artifact.artifact_id), [revision])
        self.assertEqual(revision.content, artifact.content)


class TextOperationTests(unittest.TestCase):
    def test_operation_can_be_submitted_without_real_networking(self) -> None:
        artifact = Artifact(name="main.py", artifact_type=ArtifactType.CODE)
        operation = Operation(artifact_id=artifact.artifact_id, user_id="u1", position=0, text="abc")

        self.assertEqual(operation.text, "abc")


if __name__ == "__main__":
    unittest.main()
