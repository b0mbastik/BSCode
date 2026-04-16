from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from ide.analysis.engine import AnalysisManager, ConformanceChecker, PythonStaticAnalyser, StubDynAnalyser
from ide.domain.models import (
    Artifact,
    ArtifactType,
    Comment,
    CompletionItem,
    CompletionItemKind,
    DebugStatus,
    Operation,
    Revision,
    TestStatus,
    TraceLink,
)
from ide.infrastructure.adapters import InMemoryPersistence, RevisionLog
from ide.infrastructure.bscode_store import BSCodeStore
from ide.services.integrations import DebugService, RunService
from ide.services.language import JavaLangSvc, PlainTextLangSvc, PythonLangSvc
from ide.services.search import SearchService
from ide.services.testing import TestService
from ide.workspace.traceability import TraceabilityService
from ide.workspace.workspace_services import ArtifactStore, ProjectManager, VersionService


class ProjectAndPersistenceTests(unittest.TestCase):
    def test_project_and_artifact_boundaries(self) -> None:
        manager = ProjectManager()
        project = manager.create_project("Demo", Path("/tmp/demo"))
        artifact = Artifact(name="main.py", artifact_type=ArtifactType.CODE)
        store = ArtifactStore(InMemoryPersistence())

        manager.register_artifact(project, artifact)
        store.save(artifact)

        self.assertEqual(manager.active_project, project)
        self.assertEqual(store.load(artifact.artifact_id), artifact)

    def test_sidecar_state_persists_and_reloads(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = BSCodeStore(Path(temporary_directory))
            store.save_comments([Comment(artifact_id="a1", body="review note")])
            store.save_trace_links([TraceLink(design_element="Design", code_element="Code")])
            store.save_revisions([Revision(artifact_id="a1", content="v1")])

            self.assertEqual(store.load_comments()[0].body, "review note")
            self.assertEqual(store.load_trace_links()[0].code_element, "Code")
            self.assertEqual(store.load_revisions()[0].content, "v1")

    def test_autosave_revision_boundary_records_history(self) -> None:
        service = VersionService(RevisionLog())
        artifact = Artifact(name="main.py", artifact_type=ArtifactType.CODE, content="print('v1')\n")

        revision = service.autosave(artifact, author="tester")

        self.assertEqual(revision.message, "Autosave")
        self.assertEqual(service.get_history(artifact.artifact_id), [revision])


class CompletionTests(unittest.TestCase):
    def test_python_completion_returns_keywords_and_current_file_symbols(self) -> None:
        service = PythonLangSvc()
        source = "import os\nclass Tool:\n    pass\n\ndef build():\n    pass\n\nbu"

        completions = service.complete(source, 8, 3)
        labels = {item.label for item in completions}

        self.assertIn("build", labels)
        self.assertTrue(any(item.label == "build" and item.kind is CompletionItemKind.FUNCTION for item in completions))

    def test_python_completion_includes_project_symbols(self) -> None:
        service = PythonLangSvc()
        project_symbols = [CompletionItem(label="ProjectTool", kind=CompletionItemKind.CLASS)]

        labels = {item.label for item in service.complete("Pro", 1, 4, project_symbols)}

        self.assertIn("ProjectTool", labels)

    def test_java_completion_returns_keywords_methods_and_project_symbols(self) -> None:
        service = JavaLangSvc()
        source = "public class Tool { public void build() {} }\n"
        completions = service.complete(
            source,
            1,
            1,
            [CompletionItem(label="ProjectClass", kind=CompletionItemKind.CLASS)],
        )
        labels = {item.label for item in completions}

        self.assertIn("build", labels)
        self.assertIn("ProjectClass", labels)

    def test_plain_text_completion_is_empty(self) -> None:
        self.assertEqual(PlainTextLangSvc().complete("abc", 1, 2), [])


class AnalysisAndConformanceTests(unittest.TestCase):
    def _manager(self) -> AnalysisManager:
        return AnalysisManager(
            language_services={"python": PythonLangSvc(), "java": JavaLangSvc()},
            static_analyser=PythonStaticAnalyser(),
            conformance_checker=ConformanceChecker(),
            dyn_analyser=StubDynAnalyser(),
        )

    def test_python_analysis_reports_syntax_error(self) -> None:
        artifact = Artifact(
            name="broken.py",
            artifact_type=ArtifactType.CODE,
            language="python",
            content="def broken(:\n    pass\n",
        )

        result = self._manager().run_static_analysis([artifact])

        self.assertTrue(any(diagnostic.severity.value == "error" for diagnostic in result.diagnostics))

    def test_python_analysis_reports_duplicate_definitions_and_todos(self) -> None:
        artifact = Artifact(
            name="dup.py",
            artifact_type=ArtifactType.CODE,
            language="python",
            content="def run():\n    pass\n\ndef run():\n    # TODO wire\n    pass\n",
        )

        result = self._manager().run_static_analysis([artifact])
        messages = [diagnostic.message for diagnostic in result.diagnostics]

        self.assertTrue(any("Duplicate definition 'run'" in message for message in messages))
        self.assertTrue(any("TODO/FIXME" in message for message in messages))

    def test_python_analysis_reports_unused_import(self) -> None:
        artifact = Artifact(
            name="imports.py",
            artifact_type=ArtifactType.CODE,
            language="python",
            content="import os\n\ndef run():\n    return 1\n",
        )

        result = self._manager().run_static_analysis([artifact])

        self.assertTrue(any("Imported name 'os' is not used" in diagnostic.message for diagnostic in result.diagnostics))

    def test_java_analysis_reports_duplicate_class(self) -> None:
        artifact = Artifact(
            name="Tool.java",
            artifact_type=ArtifactType.CODE,
            language="java",
            content="class Tool {}\nclass Tool {}\n",
        )

        result = self._manager().run_static_analysis([artifact])

        self.assertTrue(any("Duplicate class 'Tool'" in diagnostic.message for diagnostic in result.diagnostics))

    def test_conformance_reports_code_and_design_mismatches(self) -> None:
        design = Artifact(
            name="design.md",
            artifact_type=ArtifactType.DESIGN,
            content="Tool\nMissingDesignOnly\n",
        )
        code = Artifact(
            name="tool.py",
            artifact_type=ArtifactType.CODE,
            language="python",
            content="class Tool:\n    pass\n\nclass ExtraCodeOnly:\n    pass\n",
        )
        manager = self._manager()

        static = manager.run_static_analysis([design, code])
        conformance = manager.run_conformance_check(static.snapshot)
        messages = [diagnostic.message for diagnostic in conformance.diagnostics]

        self.assertTrue(any("ExtraCodeOnly" in message for message in messages))
        self.assertTrue(any("MissingDesignOnly" in message for message in messages))

    def test_conformance_reports_traceability_inconsistency(self) -> None:
        design = Artifact(name="design.md", artifact_type=ArtifactType.DESIGN, content="Tool\n")
        code = Artifact(
            name="tool.py",
            artifact_type=ArtifactType.CODE,
            language="python",
            content="class Tool:\n    pass\n",
        )
        manager = self._manager()
        static = manager.run_static_analysis([design, code])

        conformance = manager.run_conformance_check(
            static.snapshot,
            [TraceLink(design_element="MissingDesign", code_element="MissingCode")],
        )
        messages = [diagnostic.message for diagnostic in conformance.diagnostics]

        self.assertTrue(any("MissingDesign" in message for message in messages))
        self.assertTrue(any("MissingCode" in message for message in messages))

    def test_dynamic_analysis_boundary_is_non_diagnostic(self) -> None:
        project = ProjectManager().create_project("Demo", Path("/tmp/demo"))

        result = StubDynAnalyser().analyse_runtime(project)

        self.assertEqual(result.diagnostics, [])


class DebugServiceTests(unittest.TestCase):
    def test_debug_service_rejects_non_python_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            java_file = root / "Tool.java"
            java_file.write_text("class Tool {}\n", encoding="utf-8")
            project = ProjectManager().create_project("Debug", root)

            result = DebugService().start_debug_session(project, java_file, {1})

            self.assertFalse(result.success)
            self.assertIn("Python", result.output)

    def test_python_debugger_pauses_at_breakpoint_and_exposes_locals(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            script = root / "debug_me.py"
            script.write_text("x = 1\ny = x + 1\nprint(y)\n", encoding="utf-8")
            project = ProjectManager().create_project("Debug", root)
            service = DebugService()

            result = service.start_debug_session(project, script, {2})
            snapshots = self._wait_for_events(service)
            service.stop()
            self._wait_for_events(service)

            self.assertTrue(result.success)
            paused = next(snapshot for snapshot in snapshots if snapshot.status is DebugStatus.PAUSED)
            self.assertEqual(paused.line, 2)
            self.assertEqual(paused.variables.get("x"), "1")

    def test_python_debugger_step_and_continue_state_transitions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            script = root / "debug_me.py"
            script.write_text("x = 1\ny = x + 1\nprint(y)\n", encoding="utf-8")
            project = ProjectManager().create_project("Debug", root)
            service = DebugService()

            service.start_debug_session(project, script, set())
            first_pause = self._wait_for_events(service)
            service.step()
            second_pause = self._wait_for_events(service)
            service.continue_execution()
            final_events = self._wait_for_events(service, wait_for_terminal=True)

            self.assertTrue(any(snapshot.status is DebugStatus.PAUSED for snapshot in first_pause))
            self.assertTrue(any(snapshot.status is DebugStatus.PAUSED for snapshot in second_pause))
            self.assertTrue(any(snapshot.status is DebugStatus.FINISHED for snapshot in final_events))

    @staticmethod
    def _wait_for_events(
        service: DebugService,
        *,
        wait_for_terminal: bool = False,
    ) -> list:
        deadline = time.time() + 2
        events = []
        while time.time() < deadline:
            events.extend(service.poll_events())
            if events:
                if not wait_for_terminal:
                    return events
                if any(event.status in {DebugStatus.FINISHED, DebugStatus.STOPPED, DebugStatus.ERROR} for event in events):
                    return events
            time.sleep(0.02)
        return events


class TestRunnerAndToolingTests(unittest.TestCase):
    def test_test_runner_fallback_classifies_basic_cases(self) -> None:
        project = ProjectManager().create_project("Tests", Path("/tmp/tests"))
        artifact = Artifact(
            name="test_example.py",
            artifact_type=ArtifactType.TEST,
            language="python",
            content="def test_passes():\n    assert 1\n\ndef test_fails():\n    assert False\n",
        )

        result = TestService().run_tests(project, [artifact])
        statuses = {case.name: case.status for case in result.suites[0].cases}

        self.assertEqual(statuses["test_passes"], TestStatus.PASSED)
        self.assertEqual(statuses["test_fails"], TestStatus.FAILED)
        self.assertEqual(result.total_failed, 1)

    def test_test_runner_executes_unittest_project_and_captures_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            test_file = root / "test_real.py"
            test_file.write_text(
                "import unittest\n\n"
                "class RealTest(unittest.TestCase):\n"
                "    def test_ok(self):\n"
                "        self.assertEqual(1, 1)\n",
                encoding="utf-8",
            )
            project = ProjectManager().create_project("Tests", root)
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
            self.assertTrue(result.output)

    def test_run_service_extracts_java_package_name(self) -> None:
        self.assertEqual(RunService._java_package("package edu.demo;\npublic class Main {}\n"), "edu.demo")

    def test_search_service_is_plain_filename_and_content_search(self) -> None:
        artifact = Artifact(name="tool.py", artifact_type=ArtifactType.CODE, content="class Tool:\n    pass\n")

        results = SearchService().search("tool", [artifact])

        self.assertTrue(any(result.context == "filename match" for result in results))
        self.assertTrue(any(result.line == 1 for result in results))


class WorkspaceBoundaryTests(unittest.TestCase):
    def test_traceability_service_is_basic_create_delete_store(self) -> None:
        service = TraceabilityService()
        link = service.add_link(
            TraceLink(design_element="Editor", code_element="EditorView", description="realised by")
        )

        self.assertEqual(service.get_all(), [link])
        self.assertTrue(service.remove_link(link.link_id))
        self.assertEqual(service.get_all(), [])

    def test_operation_model_supports_collaboration_boundary(self) -> None:
        artifact = Artifact(name="main.py", artifact_type=ArtifactType.CODE)
        operation = Operation(artifact_id=artifact.artifact_id, user_id="u1", position=0, text="abc")

        self.assertEqual(operation.text, "abc")


if __name__ == "__main__":
    unittest.main()
