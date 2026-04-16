"""Language-service boundaries for the outline IDE.

The classes in this module intentionally avoid real parsing, completion, or
highlighting algorithms.  They preserve the service contracts and collaboration
points needed by the architecture so future language plugins can replace the
skeletal behaviour without changing the presentation layer.
"""

from __future__ import annotations

from typing import Protocol

from ide.domain.models import AnalysisSnapshot, CompletionItem


class LanguageService(Protocol):
    """Protocol implemented by language plugins.

    Presentation code asks the active service for highlighting, parsing
    metadata, and completion candidates.  In this outline implementation those
    operations return placeholder data only.
    """

    def complete(
        self,
        source: str,
        line: int,
        column: int,
        project_symbols: list[CompletionItem] | None = None,
    ) -> list[CompletionItem]:
        ...

    def highlight(self, source: str) -> list[tuple[int, int, str]]:
        ...

    def parse(self, source: str, artifact_id: str) -> AnalysisSnapshot:
        ...


class PythonLangSvc:
    """Skeletal Python language service.

    Responsibility: define where Python-specific completion, highlighting, and
    parsing would live.  Actual AST analysis and semantic completion are
    intentionally omitted for the coursework outline.
    """

    def complete(
        self,
        source: str,
        line: int,
        column: int,
        project_symbols: list[CompletionItem] | None = None,
    ) -> list[CompletionItem]:
        # TODO: future implementation may delegate to an AST/LSP-backed provider.
        return list(project_symbols or [])[:5]

    def highlight(self, source: str) -> list[tuple[int, int, str]]:
        # Syntax highlighting is represented as a boundary only.
        return []

    def parse(self, source: str, artifact_id: str) -> AnalysisSnapshot:
        return AnalysisSnapshot(
            artifact_id=artifact_id,
            code_metadata={
                "language": "python",
                "outline_only": True,
                "classes": [],
                "functions": [],
                "imports": [],
                "identifiers": [],
            },
        )


class JavaLangSvc:
    """Skeletal Java language service.

    Responsibility: demonstrate that Java support plugs into the same contract
    as Python.  Compilation, semantic parsing, and Java completion are omitted.
    """

    def complete(
        self,
        source: str,
        line: int,
        column: int,
        project_symbols: list[CompletionItem] | None = None,
    ) -> list[CompletionItem]:
        return list(project_symbols or [])[:5]

    def highlight(self, source: str) -> list[tuple[int, int, str]]:
        return []

    def parse(self, source: str, artifact_id: str) -> AnalysisSnapshot:
        return AnalysisSnapshot(
            artifact_id=artifact_id,
            code_metadata={
                "language": "java",
                "outline_only": True,
                "classes": [],
                "interfaces": [],
                "methods": [],
                "identifiers": [],
            },
        )


class PlainTextLangSvc:
    """Fallback language service for text and unsupported artefacts."""

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
            code_metadata={"language": "plain", "outline_only": True},
        )
