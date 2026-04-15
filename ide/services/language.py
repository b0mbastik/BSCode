"""Language-service extension point and outline implementations."""

from __future__ import annotations

import ast
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


def _keyword_spans(source: str, keywords: set[str]) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    for keyword in keywords:
        for match in re.finditer(rf"\b{re.escape(keyword)}\b", source):
            spans.append((match.start(), match.end(), "keyword"))
    return spans


def _todo_lines(lines: list[str]) -> list[int]:
    return [index + 1 for index, line in enumerate(lines) if "TODO" in line]


class PythonLangSvc:
    """Minimal concrete language service for the Python-only prototype."""

    keywords = {"class", "def", "from", "import", "return", "if", "else", "for", "while"}

    def complete(self, source: str, line: int, column: int) -> list[str]:
        return ["def", "class", "import", "pytest", "typing"]

    def highlight(self, source: str) -> list[tuple[int, int, str]]:
        return _keyword_spans(source, self.keywords)

    def parse(self, source: str, artifact_id: str) -> AnalysisSnapshot:
        lines = source.splitlines()
        functions: list[str] = []
        classes: list[str] = []
        methods: list[str] = []
        class_methods: dict[str, list[str]] = {}
        bases: dict[str, list[str]] = {}
        try:
            tree = ast.parse(source)
            for node in tree.body:
                if isinstance(node, ast.FunctionDef):
                    functions.append(node.name)
                elif isinstance(node, ast.ClassDef):
                    classes.append(node.name)
                    bases[node.name] = [
                        self._base_name(base)
                        for base in node.bases
                        if self._base_name(base)
                    ]
                    class_methods[node.name] = [
                        child.name
                        for child in node.body
                        if isinstance(child, ast.FunctionDef)
                    ]
                    methods.extend(class_methods[node.name])
        except SyntaxError:
            functions = [
                line.strip()[4:].split("(", 1)[0]
                for line in lines
                if line.strip().startswith("def ")
            ]
            classes = [
                line.strip()[6:].split("(", 1)[0].rstrip(":")
                for line in lines
                if line.strip().startswith("class ")
            ]
        return AnalysisSnapshot(
            artifact_id=artifact_id,
            code_metadata={
                "language": "python",
                "line_count": len(lines),
                "functions": functions,
                "classes": classes,
                "methods": methods,
                "class_methods": class_methods,
                "bases": bases,
                "todos": _todo_lines(lines),
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

    @staticmethod
    def _base_name(node: ast.expr) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return ""


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
    _inheritance_re = re.compile(
        r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)"
        r"(?:\s+extends\s+([A-Za-z_][A-Za-z0-9_]*))?"
        r"(?:\s+implements\s+([A-Za-z_][A-Za-z0-9_,\s]*))?"
    )
    _method_re = re.compile(
        r"\b(?:public|private|protected)?\s*"
        r"(?:static\s+)?"
        r"(?:[A-Za-z_][A-Za-z0-9_<>\[\]]*|void)\s+"
        r"([A-Za-z_][A-Za-z0-9_]*)\s*\("
    )

    def complete(self, source: str, line: int, column: int) -> list[str]:
        return ["class", "interface", "public", "private", "static", "void"]

    def highlight(self, source: str) -> list[tuple[int, int, str]]:
        return _keyword_spans(source, self.keywords)

    def parse(self, source: str, artifact_id: str) -> AnalysisSnapshot:
        lines = source.splitlines()
        type_matches = list(self._type_re.finditer(source))
        classes = [match.group(2) for match in type_matches if match.group(1) == "class"]
        interfaces = [match.group(2) for match in type_matches if match.group(1) == "interface"]
        bases: dict[str, list[str]] = {}
        for match in self._inheritance_re.finditer(source):
            class_name = match.group(1)
            parents: list[str] = []
            if match.group(2):
                parents.append(match.group(2))
            if match.group(3):
                parents.extend(
                    parent.strip()
                    for parent in match.group(3).split(",")
                    if parent.strip()
                )
            bases[class_name] = parents
        methods = [
            name
            for name in self._method_re.findall(source)
            if name not in {"if", "for", "while", "switch", "catch"}
        ]
        class_methods = {class_name: methods for class_name in classes}
        return AnalysisSnapshot(
            artifact_id=artifact_id,
            code_metadata={
                "language": "java",
                "line_count": len(lines),
                "classes": classes,
                "interfaces": interfaces,
                "methods": methods,
                "class_methods": class_methods,
                "bases": bases,
                "todos": _todo_lines(lines),
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
