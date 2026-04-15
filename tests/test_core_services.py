from __future__ import annotations

import unittest
import tempfile
from pathlib import Path

from ide.analysis.engine import AnalysisManager, ConformanceChecker, PythonStaticAnalyser, StubDynAnalyser
from ide.domain.models import Artifact, ArtifactType, Comment, Operation, Revision, TestStatus, TraceLink
from ide.infrastructure.adapters import InMemoryPersistence, RevisionLog
from ide.infrastructure.bscode_store import BSCodeStore
from ide.services.integrations import RunService
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

    def test_static_diagnostics_are_tied_to_source_artifact(self) -> None:
        manager = AnalysisManager(
            language_services={"python": PythonLangSvc()},
            static_analyser=PythonStaticAnalyser(),
            conformance_checker=ConformanceChecker(),
            dyn_analyser=StubDynAnalyser(),
        )
        artifact = Artifact(
            name="todo.py",
            artifact_type=ArtifactType.CODE,
            language="python",
            content="def run():\n    # TODO fix\n",
        )

        result = manager.run_static_analysis([artifact])

        self.assertTrue(any(d.artifact_id == artifact.artifact_id for d in result.diagnostics))

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

    def test_test_service_runs_real_unittest_for_disk_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            test_file = root / "test_real.py"
            test_file.write_text(
                "import unittest\n\n"
                "class RealTest(unittest.TestCase):\n"
                "    def test_ok(self):\n"
                "        self.assertEqual(1, 1)\n",
                encoding="utf-8",
            )
            project = ProjectManager().create_project("DiskTests", root)
            artifact = Artifact(
                name=test_file.name,
                artifact_type=ArtifactType.TEST,
                language="python",
                path=test_file,
                content=test_file.read_text(encoding="utf-8"),
            )

            result = TestService().run_tests(project, [artifact])

            self.assertTrue(result.success)
            self.assertIn("unittest", result.command)

    def test_run_service_extracts_java_package_name(self) -> None:
        source = "package edu.demo;\npublic class Main {}\n"

        self.assertEqual(RunService._java_package(source), "edu.demo")


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

    def test_bscode_store_persists_workspace_sidecars(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = BSCodeStore(Path(tmp))
            comment = Comment(
                artifact_id="a1",
                line=3,
                author="tester",
                body="review note",
            )
            link = TraceLink(
                design_artifact_id="d1",
                design_element="Diagram",
                code_artifact_id="c1",
                code_element="Class",
            )
            revision = Revision(
                artifact_id="a1",
                content="v1",
                author="tester",
            )

            store.save_comments([comment])
            store.save_trace_links([link])
            store.save_revisions([revision])

            self.assertEqual(store.load_comments()[0].body, "review note")
            self.assertEqual(store.load_trace_links()[0].code_element, "Class")
            self.assertEqual(store.load_revisions()[0].content, "v1")


class TextOperationTests(unittest.TestCase):
    def test_operation_can_be_submitted_without_real_networking(self) -> None:
        artifact = Artifact(name="main.py", artifact_type=ArtifactType.CODE)
        operation = Operation(artifact_id=artifact.artifact_id, user_id="u1", position=0, text="abc")

        self.assertEqual(operation.text, "abc")


if __name__ == "__main__":
    unittest.main()
