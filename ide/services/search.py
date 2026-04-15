"""Full-text search service across all project artefacts."""

from __future__ import annotations

from dataclasses import dataclass, field

from ide.domain.models import Artifact


@dataclass(slots=True)
class SearchResult:
    artifact_id: str
    artifact_name: str
    line: int
    column: int
    match_text: str
    context: str


class SearchService:
    """Searches all artefact content for a query string.

    Covers code, architecture, design, and test artefacts equally:
    the search is purely text-based so any artefact with string content
    is included.
    """

    def search(
        self,
        query: str,
        artifacts: list[Artifact],
        *,
        case_sensitive: bool = False,
        whole_word: bool = False,
        max_results: int = 500,
    ) -> list[SearchResult]:
        if not query:
            return []

        results: list[SearchResult] = []
        normalized_query = query if case_sensitive else query.lower()

        for artifact in artifacts:
            source_lines = artifact.content.splitlines()
            for line_number, line_text in enumerate(source_lines, start=1):
                normalized_line = line_text if case_sensitive else line_text.lower()
                search_start_column = 0
                while True:
                    match_index = normalized_line.find(normalized_query, search_start_column)
                    if match_index == -1:
                        break
                    if whole_word and not self._is_word_boundary(
                        normalized_line,
                        match_index,
                        len(normalized_query),
                    ):
                        search_start_column = match_index + 1
                        continue
                    results.append(
                        SearchResult(
                            artifact_id=artifact.artifact_id,
                            artifact_name=artifact.name,
                            line=line_number,
                            column=match_index + 1,
                            match_text=line_text[match_index: match_index + len(normalized_query)],
                            context=line_text.strip(),
                        )
                    )
                    search_start_column = match_index + len(normalized_query)
                    if len(results) >= max_results:
                        return results
        return results

    @staticmethod
    def _is_word_boundary(text: str, start: int, length: int) -> bool:
        before = start == 0 or not text[start - 1].isidentifier()
        after = (start + length) >= len(text) or not text[start + length].isidentifier()
        return before and after
