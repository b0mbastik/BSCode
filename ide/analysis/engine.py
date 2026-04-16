"""Analysis engine interfaces and orchestration."""

from __future__ import annotations

import re
import ast
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
    TraceLink,
)
from ide.services.language import JavaLangSvc, LanguageService, PythonLangSvc


class StaticAnalyser(ABC):
    @abstractmethod
    def analyse(self, artifact: Artifact, language_service: LanguageService) -> AnalysisResult:
        raise NotImplementedError


class PythonStaticAnalyser(StaticAnalyser):
    """Small replaceable static analyser for prototype language services."""

    def analyse(self, artifact: Artifact, language_service: LanguageService) -> AnalysisResult:
        snapshot = language_service.parse(artifact.content, artifact.artifact_id)
        diagnostics: list[Diagnostic] = []
        if isinstance(language_service, PythonLangSvc):
            diagnostics.extend(self._python_diagnostics(artifact))
        elif isinstance(language_service, JavaLangSvc):
            diagnostics.extend(self._java_diagnostics(artifact, snapshot))
        else:
            diagnostics.extend(self._generic_diagnostics(artifact))
        return AnalysisResult(
            diagnostics=diagnostics,
            summary=f"Static analysis completed for {artifact.name}.",
            snapshot=snapshot,
        )

    def _python_diagnostics(self, artifact: Artifact) -> list[Diagnostic]:
        diagnostics = self._generic_diagnostics(artifact)
        try:
            tree = ast.parse(artifact.content)
        except SyntaxError as exc:
            diagnostics.append(
                Diagnostic(
                    message=exc.msg,
                    severity=DiagnosticSeverity.ERROR,
                    line=exc.lineno or 1,
                    column=exc.offset or 1,
                    source="PythonStaticAnalyser",
                    artifact_id=artifact.artifact_id,
                    file=str(artifact.path or artifact.name),
                )
            )
            return diagnostics

        definitions: dict[str, int] = {}
        imports: dict[str, int] = {}
        used_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.name in definitions:
                    diagnostics.append(
                        Diagnostic(
                            message=f"Duplicate definition '{node.name}'.",
                            severity=DiagnosticSeverity.WARNING,
                            line=node.lineno,
                            column=node.col_offset + 1,
                            source="PythonStaticAnalyser",
                            artifact_id=artifact.artifact_id,
                            file=str(artifact.path or artifact.name),
                        )
                    )
                definitions[node.name] = node.lineno
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports[alias.asname or alias.name.split(".", 1)[0]] = node.lineno
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    imports[alias.asname or alias.name] = node.lineno
            elif isinstance(node, ast.Name):
                used_names.add(node.id)

        for import_name, line in imports.items():
            if import_name not in used_names:
                diagnostics.append(
                    Diagnostic(
                        message=f"Imported name '{import_name}' is not used.",
                        severity=DiagnosticSeverity.INFO,
                        line=line,
                        source="PythonStaticAnalyser",
                        artifact_id=artifact.artifact_id,
                        file=str(artifact.path or artifact.name),
                    )
                )
        return diagnostics

    def _java_diagnostics(
        self,
        artifact: Artifact,
        snapshot: AnalysisSnapshot,
    ) -> list[Diagnostic]:
        diagnostics = self._generic_diagnostics(artifact)
        classes = [
            match.group(1)
            for match in re.finditer(r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)", artifact.content)
        ]
        for duplicate in self._duplicates(classes):
            diagnostics.append(
                Diagnostic(
                    message=f"Duplicate class '{duplicate}'.",
                    severity=DiagnosticSeverity.WARNING,
                    source="JavaStaticAnalyser",
                    artifact_id=artifact.artifact_id,
                    file=str(artifact.path or artifact.name),
                )
            )
        if artifact.content.strip() and not classes:
            diagnostics.append(
                Diagnostic(
                    message="Java artefact has no class declaration.",
                    severity=DiagnosticSeverity.INFO,
                    source="JavaStaticAnalyser",
                    artifact_id=artifact.artifact_id,
                    file=str(artifact.path or artifact.name),
                )
            )
        return diagnostics

    @staticmethod
    def _generic_diagnostics(artifact: Artifact) -> list[Diagnostic]:
        diagnostics: list[Diagnostic] = []
        for line_number, line in enumerate(artifact.content.splitlines(), start=1):
            if "TODO" in line or "FIXME" in line:
                diagnostics.append(
                    Diagnostic(
                        message="TODO/FIXME marker left in code artefact.",
                        severity=DiagnosticSeverity.INFO,
                        line=line_number,
                        column=max(line.find("TODO"), line.find("FIXME")) + 1,
                        source="StaticAnalyser",
                        artifact_id=artifact.artifact_id,
                        file=str(artifact.path or artifact.name),
                    )
                )
        return diagnostics

    @staticmethod
    def _duplicates(values: list[str]) -> list[str]:
        seen: set[str] = set()
        duplicates: list[str] = []
        for value in values:
            if value in seen and value not in duplicates:
                duplicates.append(value)
            seen.add(value)
        return duplicates


class ConformanceChecker:
    """Lightweight rule-based architecture/code conformance checks."""

    def check(
        self,
        snapshot: AnalysisSnapshot,
        trace_links: list[TraceLink] | None = None,
    ) -> AnalysisResult:
        diagnostics: list[Diagnostic] = []
        design_elements = set(snapshot.design_metadata.get("elements", []))
        architecture_elements = set(snapshot.architecture_metadata.get("components", []))
        declared_elements = design_elements | architecture_elements
        code_elements = set(
            snapshot.code_metadata.get("classes", [])
            + snapshot.code_metadata.get("interfaces", [])
            + snapshot.code_metadata.get("functions", [])
            + snapshot.code_metadata.get("methods", [])
        )
        for code_element in sorted(code_elements - declared_elements):
            diagnostics.append(
                Diagnostic(
                    message=f"Code element '{code_element}' is not represented in architecture/design metadata.",
                    severity=DiagnosticSeverity.WARNING,
                    line=0,
                    source="ConformanceChecker",
                )
            )
        for design_element in sorted(declared_elements - code_elements):
            diagnostics.append(
                Diagnostic(
                    message=f"Design element '{design_element}' has no matching code element.",
                    severity=DiagnosticSeverity.INFO,
                    line=0,
                    source="ConformanceChecker",
                )
            )
        for link in trace_links or []:
            if link.design_element and link.design_element not in declared_elements:
                diagnostics.append(
                    Diagnostic(
                        message=f"Trace link refers to missing design element '{link.design_element}'.",
                        severity=DiagnosticSeverity.WARNING,
                        source="ConformanceChecker",
                    )
                )
            if link.code_element and link.code_element not in code_elements:
                diagnostics.append(
                    Diagnostic(
                        message=f"Trace link refers to missing code element '{link.code_element}'.",
                        severity=DiagnosticSeverity.WARNING,
                        source="ConformanceChecker",
                    )
                )
        return AnalysisResult(
            diagnostics=diagnostics,
            summary=f"Conformance check completed with {len(diagnostics)} finding(s).",
            snapshot=snapshot,
        )


class DynAnalyser(ABC):
    """Dynamic-analysis boundary retained for future runtime analysis."""

    @abstractmethod
    def analyse_runtime(self, project: Project) -> AnalysisResult:
        raise NotImplementedError

    @abstractmethod
    def analyse_test_results(self, test_result: TestRunResult) -> AnalysisResult:
        """Accept completed test results without producing prototype diagnostics."""
        raise NotImplementedError


class StubDynAnalyser(DynAnalyser):
    """Skeletal dynamic analyser; no runtime diagnostics are produced."""

    def analyse_runtime(self, project: Project) -> AnalysisResult:
        return AnalysisResult(
            diagnostics=[],
            summary=f"Dynamic analysis boundary available for {project.name}; no runtime analysis implemented.",
        )

    def analyse_test_results(self, test_result: TestRunResult) -> AnalysisResult:
        return AnalysisResult(
            diagnostics=[],
            summary="Dynamic analysis boundary received test results; no diagnostics implemented.",
        )


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
        combined_snapshot = AnalysisSnapshot(artifact_id="project")
        combined_snapshot.code_metadata = {
            "classes": [],
            "interfaces": [],
            "functions": [],
            "methods": [],
        }
        combined_snapshot.architecture_metadata = {"components": []}
        combined_snapshot.design_metadata = {"elements": []}
        for artifact in artifacts:
            if artifact.artifact_type is ArtifactType.ARCHITECTURE:
                components = self._extract_declared_elements(artifact.content)
                combined_snapshot.architecture_metadata["components"].extend(components)
                continue
            if artifact.artifact_type is ArtifactType.DESIGN:
                elements = self._extract_declared_elements(artifact.content)
                combined_snapshot.design_metadata["elements"].extend(elements)
                continue
            if artifact.artifact_type is not ArtifactType.CODE:
                continue

            language_name = artifact.language or "python"
            language_service = self.language_services.get(language_name)
            if language_service is None:
                combined.diagnostics.append(
                    Diagnostic(
                        message=f"No language service registered for {language_name}.",
                        severity=DiagnosticSeverity.WARNING,
                        line=0,
                        source="AnalysisManager",
                    )
                )
                continue
            result = self.static_analyser.analyse(artifact, language_service)
            combined.diagnostics.extend(result.diagnostics)
            if result.snapshot is not None:
                for key in ("classes", "interfaces", "functions", "methods"):
                    values = result.snapshot.code_metadata.get(key, [])
                    if values:
                        combined_snapshot.code_metadata.setdefault(key, []).extend(values)
        combined.snapshot = combined_snapshot
        if not combined.diagnostics:
            combined.diagnostics.append(
                Diagnostic(
                    message="No static analysis issues found by outline analyser.",
                    severity=DiagnosticSeverity.INFO,
                    line=0,
                    source="AnalysisManager",
                )
            )
        return combined

    @staticmethod
    def _extract_declared_elements(source: str) -> list[str]:
        elements: list[str] = []
        for line in source.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if "->" in stripped:
                left, right = stripped.split("->", 1)
                elements.extend([left.strip(), right.strip()])
                continue
            match = re.search(r"\]\s*([A-Za-z][A-Za-z0-9_ ]+)", stripped)
            if match:
                elements.extend(part.strip() for part in match.group(1).split("|"))
                continue
            if re.match(r"^[A-Z][A-Za-z0-9_ ]+$", stripped):
                elements.append(stripped)
        return sorted({element for element in elements if element})

    def run_conformance_check(
        self,
        snapshot: AnalysisSnapshot | None,
        trace_links: list[TraceLink] | None = None,
    ) -> AnalysisResult:
        if snapshot is None:
            return AnalysisResult(
                diagnostics=[
                    Diagnostic(
                        message="No analysis snapshot available for conformance checking.",
                        severity=DiagnosticSeverity.WARNING,
                        line=0,
                        source="AnalysisManager",
                    )
                ],
                summary="Conformance check skipped.",
            )
        return self.conformance_checker.check(snapshot, trace_links or [])

    def run_dynamic_analysis(self, project: Project) -> AnalysisResult:
        return self.dyn_analyser.analyse_runtime(project)

    def run_dynamic_analysis_from_tests(self, test_result: TestRunResult) -> AnalysisResult:
        """Derive dynamic diagnostics from a completed test run."""
        return self.dyn_analyser.analyse_test_results(test_result)
