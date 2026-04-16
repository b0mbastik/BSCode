"""Plain text search service across project artefacts."""

from __future__ import annotations

from dataclasses import dataclass

from ide.domain.models import Artifact


@dataclass(slots=True)
class SearchResult:
    artifact_id: str
    artifact_name: str
    line: int
    match_text: str
    context: str


class SearchService:
    """Minimal filename/content search boundary."""

    def search(
        self,
        query: str,
        artifacts: list[Artifact],
        *,
        case_sensitive: bool = False,
        max_results: int = 100,
    ) -> list[SearchResult]:
        if not query:
            return []

        results: list[SearchResult] = []
        normalized_query = query if case_sensitive else query.lower()

        for artifact in artifacts:
            normalized_name = artifact.name if case_sensitive else artifact.name.lower()
            if normalized_query in normalized_name:
                results.append(
                    SearchResult(
                        artifact_id=artifact.artifact_id,
                        artifact_name=artifact.name,
                        line=0,
                        match_text=artifact.name,
                        context="filename match",
                    )
                )
                if len(results) >= max_results:
                    return results
            source_lines = artifact.content.splitlines()
            for line_number, line_text in enumerate(source_lines, start=1):
                normalized_line = line_text if case_sensitive else line_text.lower()
                match_index = normalized_line.find(normalized_query)
                if match_index != -1:
                    results.append(
                        SearchResult(
                            artifact_id=artifact.artifact_id,
                            artifact_name=artifact.name,
                            line=line_number,
                            match_text=line_text[match_index: match_index + len(normalized_query)],
                            context=line_text.strip(),
                        )
                    )
                    if len(results) >= max_results:
                        return results
        return results
