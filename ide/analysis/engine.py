"""Analysis engine interfaces and orchestration."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ide.domain.models import (
    AnalysisResult,
    AnalysisSnapshot,
    Artifact,
    ArtifactType,
    Diagnostic,
    DiagnosticSeverity,
    Project,
    TestRunResult,
    TestStatus,
)
from ide.services.language import LanguageService, PythonLangSvc


class StaticAnalyser(ABC):
    @abstractmethod
    def analyse(self, artifact: Artifact, language_service: LanguageService) -> AnalysisResult:
        raise NotImplementedError


class PythonStaticAnalyser(StaticAnalyser):
    def analyse(self, artifact: Artifact, language_service: LanguageService) -> AnalysisResult:
        snapshot = language_service.parse(artifact.content, artifact.artifact_id)
        diagnostics: list[Diagnostic] = []
        if isinstance(language_service, PythonLangSvc):
            diagnostics.extend(language_service.diagnostics_for(artifact.content))
        if not snapshot.code_metadata.get("functions") and artifact.content.strip():
            diagnostics.append(
                Diagnostic(
                    message="Python artifact contains no functions yet.",
                    severity=DiagnosticSeverity.INFO,
                    source="StaticAnalyser",
                )
            )
        return AnalysisResult(
            diagnostics=diagnostics,
            summary=f"Static analysis completed for {artifact.name}.",
            snapshot=snapshot,
        )


class ConformanceChecker:
    def check(self, snapshot: AnalysisSnapshot) -> AnalysisResult:
        diagnostics: list[Diagnostic] = []
        declared_components = snapshot.architecture_metadata.get("components", [])
        code_classes = snapshot.code_metadata.get("classes", [])
        if declared_components and not set(declared_components).intersection(code_classes):
            diagnostics.append(
                Diagnostic(
                    message="No code classes currently map to declared architecture components.",
                    severity=DiagnosticSeverity.WARNING,
                    source="ConformanceChecker",
                )
            )
        return AnalysisResult(
            diagnostics=diagnostics,
            summary="Conformance check completed using placeholder metadata.",
            snapshot=snapshot,
        )


class DynAnalyser(ABC):
    """Dynamic analysis boundary — implementations run at test time."""

    @abstractmethod
    def analyse_runtime(self, project: Project) -> AnalysisResult:
        raise NotImplementedError

    @abstractmethod
    def analyse_test_results(self, test_result: TestRunResult) -> AnalysisResult:
        """Produce dynamic diagnostics from a completed test run."""
        raise NotImplementedError


class StubDynAnalyser(DynAnalyser):
    """Stub dynamic analyser that connects to the test-execution flow.

    For each failed or errored test case the analyser emits an ERROR
    diagnostic so that the inline editor highlights are updated
    immediately after a test run completes.
    """

    def analyse_runtime(self, project: Project) -> AnalysisResult:
        return AnalysisResult(
            diagnostics=[
                Diagnostic(
                    message="Dynamic analysis hook is ready for test-time profiling integration.",
                    severity=DiagnosticSeverity.INFO,
                    source="DynAnalyser",
                )
            ],
            summary=f"Dynamic analysis stub executed for {project.name}.",
        )

    def analyse_test_results(self, test_result: TestRunResult) -> AnalysisResult:
        diagnostics: list[Diagnostic] = []
        for suite in test_result.suites:
            for case in suite.cases:
                if case.status is TestStatus.FAILED:
                    diagnostics.append(
                        Diagnostic(
                            message=f"Test failed: {case.name} — {case.message or 'assertion error'}",
                            severity=DiagnosticSeverity.ERROR,
                            line=case.line or 1,
                            source="DynAnalyser",
                        )
                    )
                elif case.status is TestStatus.ERROR:
                    diagnostics.append(
                        Diagnostic(
                            message=f"Test error: {case.name} — {case.message or 'unexpected exception'}",
                            severity=DiagnosticSeverity.ERROR,
                            line=case.line or 1,
                            source="DynAnalyser",
                        )
                    )
        summary = (
            f"Dynamic analysis found {len(diagnostics)} issue(s) from test run "
            f"({test_result.total_passed} passed, {test_result.total_failed} failed)."
        )
        return AnalysisResult(diagnostics=diagnostics, summary=summary)


class AnalysisManager:
    def __init__(
        self,
        language_services: dict[str, LanguageService],
        static_analyser: StaticAnalyser,
        conformance_checker: ConformanceChecker,
        dyn_analyser: DynAnalyser,
    ) -> None:
        self.language_services = language_services
        self.static_analyser = static_analyser
        self.conformance_checker = conformance_checker
        self.dyn_analyser = dyn_analyser

    def run_static_analysis(self, artifacts: list[Artifact]) -> AnalysisResult:
        combined = AnalysisResult(summary="Static analysis completed.")
        for artifact in artifacts:
            if artifact.artifact_type is not ArtifactType.CODE:
                continue
            language_name = artifact.language or "python"
            language_service = self.language_services.get(language_name)
            if language_service is None:
                combined.diagnostics.append(
                    Diagnostic(
                        message=f"No language service registered for {language_name}.",
                        severity=DiagnosticSeverity.WARNING,
                        source="AnalysisManager",
                    )
                )
                continue
            result = self.static_analyser.analyse(artifact, language_service)
            combined.diagnostics.extend(result.diagnostics)
            combined.snapshot = result.snapshot
        if not combined.diagnostics:
            combined.diagnostics.append(
                Diagnostic(
                    message="No static analysis issues found by stub analyser.",
                    severity=DiagnosticSeverity.INFO,
                    source="AnalysisManager",
                )
            )
        return combined

    def run_conformance_check(self, snapshot: AnalysisSnapshot | None) -> AnalysisResult:
        if snapshot is None:
            return AnalysisResult(
                diagnostics=[
                    Diagnostic(
                        message="No analysis snapshot available for conformance checking.",
                        severity=DiagnosticSeverity.WARNING,
                        source="AnalysisManager",
                    )
                ],
                summary="Conformance check skipped.",
            )
        return self.conformance_checker.check(snapshot)

    def run_dynamic_analysis(self, project: Project) -> AnalysisResult:
        return self.dyn_analyser.analyse_runtime(project)

    def run_dynamic_analysis_from_tests(self, test_result: TestRunResult) -> AnalysisResult:
        """Derive dynamic diagnostics from a completed test run."""
        return self.dyn_analyser.analyse_test_results(test_result)
