"""Test-runner service: discovers and executes tests within a project."""

from __future__ import annotations

import re
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

# Pattern that matches a Python test function definition.
_TEST_FUNC_RE = re.compile(r"^[ \t]*def (test_\w+)\s*\(", re.MULTILINE)


class TestService:
    """Discovers test functions across project artefacts and simulates execution.

    The stub heuristic:
    - Files whose name starts with ``test_`` or ends with ``_test.py`` are
      treated as test suites.
    - Every ``def test_*`` function becomes a TestCase.
    - Functions whose body (next non-blank line) contains ``raise`` or
      ``assert False`` are marked FAILED; functions containing ``TODO`` or
      ``pass`` only are SKIPPED; everything else PASSED.
    - Dynamic analysis results are attached via ``attach_dynamic_results``.
    """

    def run_tests(self, project: Project, artifacts: list[Artifact]) -> TestRunResult:
        test_artifacts = [
            a for a in artifacts
            if a.artifact_type in (ArtifactType.CODE, ArtifactType.TEST)
            and self._is_test_file(a.name)
        ]
        command = f"pytest {project.root_path}"
        if not test_artifacts:
            return TestRunResult(
                suites=[],
                summary="No test files found. (stub: name files test_*.py or *_test.py)",
                success=True,
                command=command,
            )

        suites: list[TestSuite] = []
        for artifact in test_artifacts:
            suite = self._build_suite(artifact)
            suites.append(suite)

        total_p = sum(s.passed for s in suites)
        total_f = sum(s.failed for s in suites)
        total_e = sum(s.errors for s in suites)
        total_s = sum(s.skipped for s in suites)
        success = total_f == 0 and total_e == 0
        summary = (
            f"{'PASSED' if success else 'FAILED'} — "
            f"{total_p} passed, {total_f} failed, {total_e} errors, {total_s} skipped"
        )
        return TestRunResult(suites=suites, summary=summary, success=success, command=command)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_test_file(name: str) -> bool:
        stem = Path(name).stem
        return stem.startswith("test_") or stem.endswith("_test")

    def _build_suite(self, artifact: Artifact) -> TestSuite:
        suite = TestSuite(name=artifact.name)
        lines = artifact.content.splitlines()

        for match in _TEST_FUNC_RE.finditer(artifact.content):
            func_name = match.group(1)
            func_line = artifact.content[: match.start()].count("\n") + 1
            body_snippet = self._body_snippet(lines, func_line)
            status, message = self._classify(body_snippet)
            suite.cases.append(
                TestCase(
                    name=func_name,
                    status=status,
                    duration_ms=round(len(func_name) * 3.7 % 120 + 5, 1),
                    message=message,
                    artifact_id=artifact.artifact_id,
                    line=func_line,
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
    def _body_snippet(lines: list[str], def_line: int) -> str:
        """Return up to 5 body lines after the def line for classification."""
        start = def_line  # 1-based → index is def_line (the line after def)
        base_line = lines[def_line - 1] if 0 <= def_line - 1 < len(lines) else ""
        base_indent = len(base_line) - len(base_line.lstrip())
        snippet_lines = []
        for line in lines[start: start + 5]:
            stripped = line.strip()
            indent = len(line) - len(line.lstrip())
            if stripped.startswith("def ") and indent <= base_indent:
                break
            if stripped:
                snippet_lines.append(stripped)
            if len(snippet_lines) >= 3:
                break
        return "\n".join(snippet_lines)

    @staticmethod
    def _classify(body: str) -> tuple[TestStatus, str]:
        if "assert False" in body or (body.startswith("raise") and "NotImplementedError" not in body):
            return TestStatus.FAILED, "AssertionError: explicit failure in test body (stub)"
        if "TODO" in body or body.strip() in ("pass", "..."):
            return TestStatus.SKIPPED, "Test body not yet implemented"
        return TestStatus.PASSED, ""
