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

# Pattern that matches a Python test function definition.
_TEST_FUNC_RE = re.compile(r"^[ \t]*def (test_\w+)\s*\(", re.MULTILINE)


class TestService:
    """Discovers and runs Python tests where possible.

    If test files exist on disk under the project root this service runs
    ``python -m unittest discover``. For in-memory artefacts used by the
    outline prototype it falls back to a deterministic lightweight heuristic:

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
        started = time.perf_counter()
        try:
            proc = subprocess.run(
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
            )

        duration_ms = round((time.perf_counter() - started) * 1000, 1)
        output = (proc.stdout + ("\n" + proc.stderr if proc.stderr else "")).strip()
        status = TestStatus.PASSED if proc.returncode == 0 else TestStatus.FAILED
        summary = self._unittest_summary(output, proc.returncode)
        suite = TestSuite(
            name="unittest discover",
            cases=[
                TestCase(
                    name="unittest discover",
                    status=status,
                    duration_ms=duration_ms,
                    message=summary,
                )
            ],
        )
        return TestRunResult(
            suites=[suite],
            summary=summary,
            success=proc.returncode == 0,
            command=" ".join(command),
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
