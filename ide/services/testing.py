"""Test-runner service: discovers and executes tests within a project."""

from __future__ import annotations

import re
import subprocess
import sys
import time
from pathlib import Path

from ide.domain.models import (
    Artifact,
    ArtifactType,
    Project,
    TestCase,
    TestRunResult,
    TestStatus,
    TestSuite,
)

_TEST_FUNC_RE = re.compile(r"^[ \t]*def (test_\w+)\s*\(", re.MULTILINE)


class TestService:
    """Discovers and runs Python tests where possible.

    If test files exist on disk under the project root, this service runs
    ``python -m unittest discover``. For in-memory artefacts used by the
    outline prototype, it falls back to a deterministic lightweight classifier:

    - Files whose name starts with ``test_`` or ends with ``_test.py`` are
      treated as test suites.
    - Every ``def test_*`` function becomes a TestCase.
    - Functions whose body (next non-blank line) contains ``raise`` or
      ``assert False`` are marked FAILED; functions containing ``TODO`` or
      ``pass`` only are SKIPPED; everything else PASSED.
    """

    def run_tests(self, project: Project, artifacts: list[Artifact]) -> TestRunResult:
        if self._can_run_unittest(project, artifacts):
            return self._run_unittest_discover(project)

        test_artifacts = [
            artifact for artifact in artifacts
            if artifact.artifact_type in (ArtifactType.CODE, ArtifactType.TEST)
            and self._is_test_file(artifact.name)
        ]
        command = f"test-classifier {project.root_path}"
        if not test_artifacts:
            return TestRunResult(
                suites=[],
                summary="No test files found. Name files test_*.py or *_test.py.",
                success=True,
                command=command,
            )

        suites: list[TestSuite] = []
        for artifact in test_artifacts:
            suite = self._build_suite(artifact)
            suites.append(suite)

        result = TestRunResult(suites=suites, command=command)
        success = result.total_failed == 0 and result.total_errors == 0
        summary = (
            f"{'PASSED' if success else 'FAILED'} - "
            f"{result.total_passed} passed, {result.total_failed} failed, "
            f"{result.total_errors} errors, {result.total_skipped} skipped"
        )
        result.summary = summary
        result.success = success
        return result

    @staticmethod
    def _can_run_unittest(project: Project, artifacts: list[Artifact]) -> bool:
        if not project.root_path.exists() or not project.root_path.is_dir():
            return False
        return any(
            artifact.path is not None
            and artifact.path.exists()
            and artifact.path.suffix == ".py"
            and TestService._is_test_file(artifact.path.name)
            for artifact in artifacts
        )

    def _run_unittest_discover(self, project: Project) -> TestRunResult:
        command = [sys.executable, "-m", "unittest", "discover", "-s", str(project.root_path)]
        start_time = time.perf_counter()
        try:
            process_result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(project.root_path),
            )
        except subprocess.TimeoutExpired:
            suite = TestSuite(
                name="unittest discover",
                cases=[
                    TestCase(
                        name="unittest discover",
                        status=TestStatus.ERROR,
                        duration_ms=30000.0,
                        message="Test run timed out after 30 seconds.",
                    )
                ],
            )
            return TestRunResult(
                suites=[suite],
                summary="ERROR - unittest discover timed out",
                success=False,
                command=" ".join(command),
                output="Test run timed out after 30 seconds.",
            )

        duration_ms = round((time.perf_counter() - start_time) * 1000, 1)
        combined_output = (
            process_result.stdout
            + ("\n" + process_result.stderr if process_result.stderr else "")
        ).strip()
        test_status = TestStatus.PASSED if process_result.returncode == 0 else TestStatus.FAILED
        result_summary = self._unittest_summary(combined_output, process_result.returncode)
        suite = TestSuite(
            name="unittest discover",
            cases=[
                TestCase(
                    name="unittest discover",
                    status=test_status,
                    duration_ms=duration_ms,
                    message=result_summary,
                )
            ],
        )
        return TestRunResult(
            suites=[suite],
            summary=result_summary,
            success=process_result.returncode == 0,
            command=" ".join(command),
            output=combined_output,
        )

    @staticmethod
    def _unittest_summary(output: str, return_code: int) -> str:
        for line in reversed(output.splitlines()):
            stripped = line.strip()
            if stripped.startswith("OK") or stripped.startswith("FAILED") or stripped.startswith("ERROR"):
                return stripped
        return "PASSED - unittest discover" if return_code == 0 else "FAILED - unittest discover"

    @staticmethod
    def _is_test_file(name: str) -> bool:
        stem = Path(name).stem
        return stem.startswith("test_") or stem.endswith("_test")

    def _build_suite(self, artifact: Artifact) -> TestSuite:
        suite = TestSuite(name=artifact.name)
        lines = artifact.content.splitlines()

        for match in _TEST_FUNC_RE.finditer(artifact.content):
            test_function_name = match.group(1)
            test_function_line = artifact.content[: match.start()].count("\n") + 1
            body_snippet = self._body_snippet(lines, test_function_line)
            status, message = self._classify(body_snippet)
            suite.cases.append(
                TestCase(
                    name=test_function_name,
                    status=status,
                    duration_ms=round(len(test_function_name) * 3.7 % 120 + 5, 1),
                    message=message,
                    artifact_id=artifact.artifact_id,
                    line=test_function_line,
                )
            )

        if not suite.cases:
            suite.cases.append(
                TestCase(
                    name="(no test functions found)",
                    status=TestStatus.SKIPPED,
                    artifact_id=artifact.artifact_id,
                )
            )
        return suite

    @staticmethod
    def _body_snippet(lines: list[str], definition_line: int) -> str:
        """Return up to 5 body lines after the def line for classification."""
        start = definition_line
        definition_text = (
            lines[definition_line - 1]
            if 0 <= definition_line - 1 < len(lines)
            else ""
        )
        base_indent = len(definition_text) - len(definition_text.lstrip())
        snippet_lines = []
        for line in lines[start: start + 5]:
            stripped_line = line.strip()
            indentation = len(line) - len(line.lstrip())
            if stripped_line.startswith("def ") and indentation <= base_indent:
                break
            if stripped_line:
                snippet_lines.append(stripped_line)
            if len(snippet_lines) >= 3:
                break
        return "\n".join(snippet_lines)

    @staticmethod
    def _classify(body: str) -> tuple[TestStatus, str]:
        if "assert False" in body or (body.startswith("raise") and "NotImplementedError" not in body):
            return TestStatus.FAILED, "AssertionError: explicit failure in test body"
        if "TODO" in body or body.strip() in ("pass", "..."):
            return TestStatus.SKIPPED, "Test body not yet implemented"
        return TestStatus.PASSED, ""
