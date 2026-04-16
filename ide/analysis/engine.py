"""Analysis subsystem interfaces and skeletal orchestration.

The assignment requires architecture/design/code consistency to be represented,
but not fully implemented.  This module therefore keeps the analyser contracts,
manager, and result models while replacing real AST/regex algorithms with
explicit outline responses.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ide.domain.models import (
    AnalysisResult,
    AnalysisSnapshot,
    Artifact,
    Diagnostic,
    DiagnosticSeverity,
    Project,
    TestRunResult,
    TraceLink,
)
from ide.services.language import LanguageService


class StaticAnalyser(ABC):
    """Replaceable boundary for language-aware static analysis."""

    @abstractmethod
    def analyse(self, artifact: Artifact, language_service: LanguageService) -> AnalysisResult:
        raise NotImplementedError


class PythonStaticAnalyser(StaticAnalyser):
    """Outline static analyser used to demonstrate the analysis seam.

    The name is retained for compatibility with the existing composition root;
    this class no longer performs Python AST or Java regex checks.
    """

    def analyse(self, artifact: Artifact, language_service: LanguageService) -> AnalysisResult:
        snapshot = language_service.parse(artifact.content, artifact.artifact_id)
        return AnalysisResult(
            diagnostics=[],
            summary=f"Static analysis boundary reached for {artifact.name}; checks are not implemented.",
            snapshot=snapshot,
        )


class ConformanceChecker:
    """Boundary for architecture/design/code conformance rules.

    A future implementation would compare parsed code metadata, design metadata,
    architecture metadata, and trace links.  The outline keeps the inputs and
    output type but deliberately omits rule execution.
    """

    def check(
        self,
        snapshot: AnalysisSnapshot,
        trace_links: list[TraceLink] | None = None,
    ) -> AnalysisResult:
        return AnalysisResult(
            diagnostics=[],
            summary="Conformance checker boundary reached; rule execution is not implemented.",
            snapshot=snapshot,
        )


class DynAnalyser(ABC):
    """Dynamic-analysis boundary retained for future runtime conformance work."""

    @abstractmethod
    def analyse_runtime(self, project: Project) -> AnalysisResult:
        raise NotImplementedError

    @abstractmethod
    def analyse_test_results(self, test_result: TestRunResult) -> AnalysisResult:
        raise NotImplementedError


class StubDynAnalyser(DynAnalyser):
    """Non-diagnostic dynamic analyser used by the outline prototype."""

    def analyse_runtime(self, project: Project) -> AnalysisResult:
        return AnalysisResult(
            diagnostics=[],
            summary=f"Dynamic analysis is an outlined boundary for {project.name}.",
        )

    def analyse_test_results(self, test_result: TestRunResult) -> AnalysisResult:
        return AnalysisResult(
            diagnostics=[],
            summary="Dynamic analysis received test results; no runtime diagnostics are implemented.",
        )


class AnalysisManager:
    """Facade coordinating static, conformance, and dynamic analysis boundaries."""

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
        project_snapshot = AnalysisSnapshot(
            artifact_id="project",
            code_metadata={"outline_only": True},
            architecture_metadata={"outline_only": True},
            design_metadata={"outline_only": True},
        )
        diagnostics: list[Diagnostic] = []

        for artifact in artifacts:
            language_name = artifact.language or "plain"
            language_service = self.language_services.get(language_name)
            if language_service is None:
                diagnostics.append(
                    Diagnostic(
                        message=f"No language service boundary registered for {language_name}.",
                        severity=DiagnosticSeverity.WARNING,
                        source="AnalysisManager",
                        artifact_id=artifact.artifact_id,
                        file=str(artifact.path or artifact.name),
                    )
                )
                continue
            self.static_analyser.analyse(artifact, language_service)

        return AnalysisResult(
            diagnostics=diagnostics,
            summary="Static analysis orchestration completed; concrete checks are omitted.",
            snapshot=project_snapshot,
        )

    def run_conformance_check(
        self,
        snapshot: AnalysisSnapshot | None,
        trace_links: list[TraceLink] | None = None,
    ) -> AnalysisResult:
        if snapshot is None:
            return AnalysisResult(
                diagnostics=[
                    Diagnostic(
                        message="No analysis snapshot available for conformance boundary.",
                        severity=DiagnosticSeverity.INFO,
                        source="AnalysisManager",
                    )
                ],
                summary="Conformance boundary skipped.",
            )
        return self.conformance_checker.check(snapshot, trace_links or [])

    def run_dynamic_analysis(self, project: Project) -> AnalysisResult:
        return self.dyn_analyser.analyse_runtime(project)

    def run_dynamic_analysis_from_tests(self, test_result: TestRunResult) -> AnalysisResult:
        return self.dyn_analyser.analyse_test_results(test_result)
