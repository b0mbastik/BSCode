"""Language service extension point and outline language implementations."""

from __future__ import annotations

import re
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


class JavaLangSvc:
    """Minimal Java language service for outline-level IDE support.

    This is intentionally not a Java compiler or full parser. It extracts a
    small amount of metadata that is useful for architecture/design traceability
    and demonstrates the same plugin seam used by the Python service.
    """

    keywords = {
        "class", "interface", "public", "private", "protected", "static",
        "void", "return", "new", "extends", "implements",
    }
    _type_re = re.compile(r"\b(class|interface)\s+([A-Za-z_][A-Za-z0-9_]*)")
    _method_re = re.compile(
        r"\b(?:public|private|protected)?\s*"
        r"(?:static\s+)?"
        r"(?:[A-Za-z_][A-Za-z0-9_<>\[\]]*|void)\s+"
        r"([A-Za-z_][A-Za-z0-9_]*)\s*\("
    )

    def complete(self, source: str, line: int, column: int) -> list[str]:
        return ["class", "interface", "public", "private", "static", "void"]

    def highlight(self, source: str) -> list[tuple[int, int, str]]:
        spans: list[tuple[int, int, str]] = []
        for keyword in self.keywords:
            for match in re.finditer(rf"\b{re.escape(keyword)}\b", source):
                spans.append((match.start(), match.end(), "keyword"))
        return spans

    def parse(self, source: str, artifact_id: str) -> AnalysisSnapshot:
        lines = source.splitlines()
        type_matches = list(self._type_re.finditer(source))
        classes = [m.group(2) for m in type_matches if m.group(1) == "class"]
        interfaces = [m.group(2) for m in type_matches if m.group(1) == "interface"]
        methods = [
            name
            for name in self._method_re.findall(source)
            if name not in {"if", "for", "while", "switch", "catch"}
        ]
        todos = [index + 1 for index, line in enumerate(lines) if "TODO" in line]
        return AnalysisSnapshot(
            artifact_id=artifact_id,
            code_metadata={
                "language": "java",
                "line_count": len(lines),
                "classes": classes,
                "interfaces": interfaces,
                "methods": methods,
                "todos": todos,
            },
        )

    def diagnostics_for(self, source: str) -> list[Diagnostic]:
        diagnostics: list[Diagnostic] = []
        stripped = source.strip()
        for index, line in enumerate(source.splitlines(), start=1):
            if "TODO" in line:
                diagnostics.append(
                    Diagnostic(
                        message="TODO marker left in Java artifact.",
                        severity=DiagnosticSeverity.INFO,
                        line=index,
                        source="JavaLangSvc",
                    )
                )
        if stripped and not self._type_re.search(source):
            diagnostics.append(
                Diagnostic(
                    message="Java artifact contains no class or interface declaration yet.",
                    severity=DiagnosticSeverity.INFO,
                    source="JavaLangSvc",
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
