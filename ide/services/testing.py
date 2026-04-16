"""Testing framework integration boundary.

The service keeps the contract for test discovery/execution and structured
results, but does not run ``unittest`` or classify real test bodies.  This keeps
the coursework implementation focused on architecture rather than framework
integration.
"""

from __future__ import annotations

from ide.domain.models import Project, TestCase, TestRunResult, TestStatus, TestSuite


class TestService:
    """Skeletal test runner returning placeholder structured results."""

    def run_tests(self, project: Project, artifacts: list) -> TestRunResult:
        suite = TestSuite(
            name="TestService boundary",
            cases=[
                TestCase(
                    name="test_execution_outline",
                    status=TestStatus.SKIPPED,
                    message="Testing framework integration is not implemented.",
                )
            ],
        )
        return TestRunResult(
            suites=[suite],
            summary="TestService boundary reached; no tests were executed.",
            success=True,
            command=f"test <{project.name}>",
            output="Placeholder test result for architecture outline.",
        )
