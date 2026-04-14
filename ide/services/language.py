"""Language service extension point and Python implementation."""

from __future__ import annotations

from typing import Protocol

from ide.domain.models import AnalysisSnapshot, Diagnostic, DiagnosticSeverity


class LanguageService(Protocol):
    def complete(self, source: str, line: int, column: int) -> list[str]:
        ...

    def highlight(self, source: str) -> list[tuple[int, int, str]]:
        ...

    def parse(self, source: str, artifact_id: str) -> AnalysisSnapshot:
        ...


class PythonLangSvc:
    """Minimal concrete language service for the Python-only prototype."""

    keywords = {"class", "def", "from", "import", "return", "if", "else", "for", "while"}

    def complete(self, source: str, line: int, column: int) -> list[str]:
        return ["def", "class", "import", "pytest", "typing"]

    def highlight(self, source: str) -> list[tuple[int, int, str]]:
        spans: list[tuple[int, int, str]] = []
        for keyword in self.keywords:
            start = source.find(keyword)
            if start >= 0:
                spans.append((start, start + len(keyword), "keyword"))
        return spans

    def parse(self, source: str, artifact_id: str) -> AnalysisSnapshot:
        lines = source.splitlines()
        functions = [line.strip()[4:].split("(", 1)[0] for line in lines if line.strip().startswith("def ")]
        classes = [line.strip()[6:].split("(", 1)[0].rstrip(":") for line in lines if line.strip().startswith("class ")]
        todos = [index + 1 for index, line in enumerate(lines) if "TODO" in line]
        return AnalysisSnapshot(
            artifact_id=artifact_id,
            code_metadata={
                "language": "python",
                "line_count": len(lines),
                "functions": functions,
                "classes": classes,
                "todos": todos,
            },
        )

    def diagnostics_for(self, source: str) -> list[Diagnostic]:
        diagnostics: list[Diagnostic] = []
        for index, line in enumerate(source.splitlines(), start=1):
            if "TODO" in line:
                diagnostics.append(
                    Diagnostic(
                        message="TODO marker left in Python artifact.",
                        severity=DiagnosticSeverity.INFO,
                        line=index,
                        source="PythonLangSvc",
                    )
                )
            if "import *" in line:
                diagnostics.append(
                    Diagnostic(
                        message="Wildcard import makes architecture conformance harder to trace.",
                        severity=DiagnosticSeverity.WARNING,
                        line=index,
                        source="PythonLangSvc",
                    )
                )
        return diagnostics


class PlainTextLangSvc:
    """Generic language service for plain text and unsupported file types."""

    def complete(self, source: str, line: int, column: int) -> list[str]:
        return []

    def highlight(self, source: str) -> list[tuple[int, int, str]]:
        return []

    def parse(self, source: str, artifact_id: str) -> AnalysisSnapshot:
        return AnalysisSnapshot(
            artifact_id=artifact_id,
            code_metadata={"language": "plain", "line_count": len(source.splitlines())},
        )
