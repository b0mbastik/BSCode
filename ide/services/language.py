"""Language-service extension point and outline implementations."""

from __future__ import annotations

import ast
import keyword
import re
from typing import Protocol

from ide.domain.models import AnalysisSnapshot, CompletionItem, CompletionItemKind


class LanguageService(Protocol):
    def complete(
        self,
        source: str,
        line: int,
        column: int,
        project_symbols: list[CompletionItem] | None = None,
    ) -> list[CompletionItem]:
        """Return lightweight completion candidates for a source position."""
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
    return [
        index + 1
        for index, line in enumerate(lines)
        if "TODO" in line or "FIXME" in line
    ]


def _prefix_at(source: str, line: int, column: int) -> str:
    lines = source.splitlines()
    if line <= 0 or line > len(lines):
        return ""
    before_cursor = lines[line - 1][: max(0, column - 1)]
    match = re.search(r"[A-Za-z_][A-Za-z0-9_]*$", before_cursor)
    return match.group(0) if match else ""


def _dedupe_and_filter(
    items: list[CompletionItem],
    prefix: str,
    limit: int = 40,
) -> list[CompletionItem]:
    seen: set[str] = set()
    results: list[CompletionItem] = []
    normalized_prefix = prefix.lower()
    for item in items:
        if not item.label or item.label in seen:
            continue
        if normalized_prefix and not item.label.lower().startswith(normalized_prefix):
            continue
        seen.add(item.label)
        results.append(item)
        if len(results) >= limit:
            break
    return results


_IDENTIFIER_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")


class PythonLangSvc:
    """Minimal concrete language service for the Python-only prototype."""

    keywords = set(keyword.kwlist)

    def complete(
        self,
        source: str,
        line: int,
        column: int,
        project_symbols: list[CompletionItem] | None = None,
    ) -> list[CompletionItem]:
        prefix = _prefix_at(source, line, column)
        snapshot = self.parse(source, "completion")
        items = [
            CompletionItem(label=name, kind=CompletionItemKind.KEYWORD)
            for name in sorted(self.keywords)
        ]
        items.extend(
            CompletionItem(label=name, kind=CompletionItemKind.CLASS)
            for name in snapshot.code_metadata.get("classes", [])
        )
        items.extend(
            CompletionItem(label=name, kind=CompletionItemKind.FUNCTION)
            for name in snapshot.code_metadata.get("functions", [])
        )
        items.extend(
            CompletionItem(label=name, kind=CompletionItemKind.IMPORT)
            for name in snapshot.code_metadata.get("imports", [])
        )
        items.extend(
            CompletionItem(label=name, kind=CompletionItemKind.VARIABLE)
            for name in snapshot.code_metadata.get("identifiers", [])
        )
        items.extend(project_symbols or [])
        return _dedupe_and_filter(items, prefix)

    def highlight(self, source: str) -> list[tuple[int, int, str]]:
        return _keyword_spans(source, self.keywords)

    def parse(self, source: str, artifact_id: str) -> AnalysisSnapshot:
        lines = source.splitlines()
        functions: list[str] = []
        classes: list[str] = []
        imports: list[str] = []
        identifiers: set[str] = set()
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    functions.append(node.name)
                elif isinstance(node, ast.ClassDef):
                    classes.append(node.name)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.asname or alias.name.split(".", 1)[0])
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        imports.append(alias.asname or alias.name)
                elif isinstance(node, ast.Name):
                    identifiers.add(node.id)
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
            identifiers.update(_IDENTIFIER_RE.findall(source))
        return AnalysisSnapshot(
            artifact_id=artifact_id,
            code_metadata={
                "language": "python",
                "line_count": len(lines),
                "functions": sorted(set(functions)),
                "classes": sorted(set(classes)),
                "imports": sorted(set(imports)),
                "identifiers": sorted(identifiers - self.keywords),
                "todos": _todo_lines(lines),
            },
        )


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
        r"\b(?:public|private|protected)?\s*(?:static\s+)?"
        r"(?:[A-Za-z_][A-Za-z0-9_<>\[\]]*|void)\s+"
        r"([A-Za-z_][A-Za-z0-9_]*)\s*\("
    )

    def complete(
        self,
        source: str,
        line: int,
        column: int,
        project_symbols: list[CompletionItem] | None = None,
    ) -> list[CompletionItem]:
        prefix = _prefix_at(source, line, column)
        snapshot = self.parse(source, "completion")
        items = [
            CompletionItem(label=name, kind=CompletionItemKind.KEYWORD)
            for name in sorted(self.keywords)
        ]
        items.extend(
            CompletionItem(label=name, kind=CompletionItemKind.CLASS)
            for name in snapshot.code_metadata.get("classes", [])
        )
        items.extend(
            CompletionItem(label=name, kind=CompletionItemKind.METHOD)
            for name in snapshot.code_metadata.get("methods", [])
        )
        items.extend(
            CompletionItem(label=name, kind=CompletionItemKind.VARIABLE)
            for name in snapshot.code_metadata.get("identifiers", [])
        )
        items.extend(project_symbols or [])
        return _dedupe_and_filter(items, prefix)

    def highlight(self, source: str) -> list[tuple[int, int, str]]:
        return _keyword_spans(source, self.keywords)

    def parse(self, source: str, artifact_id: str) -> AnalysisSnapshot:
        lines = source.splitlines()
        type_matches = list(self._type_re.finditer(source))
        classes = [match.group(2) for match in type_matches if match.group(1) == "class"]
        interfaces = [match.group(2) for match in type_matches if match.group(1) == "interface"]
        methods = [
            name
            for name in self._method_re.findall(source)
            if name not in {"if", "for", "while", "switch", "catch"}
        ]
        identifiers = sorted(set(_IDENTIFIER_RE.findall(source)) - self.keywords)
        return AnalysisSnapshot(
            artifact_id=artifact_id,
            code_metadata={
                "language": "java",
                "line_count": len(lines),
                "classes": sorted(set(classes)),
                "interfaces": sorted(set(interfaces)),
                "methods": sorted(set(methods)),
                "identifiers": identifiers,
                "todos": _todo_lines(lines),
            },
        )


class PlainTextLangSvc:
    """Generic language service for plain text and unsupported file types."""

    def complete(
        self,
        source: str,
        line: int,
        column: int,
        project_symbols: list[CompletionItem] | None = None,
    ) -> list[CompletionItem]:
        return []

    def highlight(self, source: str) -> list[tuple[int, int, str]]:
        return []

    def parse(self, source: str, artifact_id: str) -> AnalysisSnapshot:
        return AnalysisSnapshot(
            artifact_id=artifact_id,
            code_metadata={"language": "plain", "line_count": len(source.splitlines())},
        )
