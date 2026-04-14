"""Full-text search service across all project artefacts."""

from __future__ import annotations

from dataclasses import dataclass, field

from ide.domain.models import Artifact


@dataclass(slots=True)
class SearchResult:
    artifact_id: str
    artifact_name: str
    line: int
    column: int           # 1-based
    match_text: str       # the exact matched substring
    context: str          # the full trimmed line for display


class SearchService:
    """Searches all artefact content for a query string.

    Covers code, architecture, design, and test artefacts equally —
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
        needle = query if case_sensitive else query.lower()

        for artifact in artifacts:
            raw_lines = artifact.content.splitlines()
            for line_num, raw_line in enumerate(raw_lines, start=1):
                haystack = raw_line if case_sensitive else raw_line.lower()
                col = 0
                while True:
                    idx = haystack.find(needle, col)
                    if idx == -1:
                        break
                    if whole_word and not self._is_word_boundary(haystack, idx, len(needle)):
                        col = idx + 1
                        continue
                    results.append(
                        SearchResult(
                            artifact_id=artifact.artifact_id,
                            artifact_name=artifact.name,
                            line=line_num,
                            column=idx + 1,
                            match_text=raw_line[idx: idx + len(needle)],
                            context=raw_line.strip(),
                        )
                    )
                    col = idx + len(needle)
                    if len(results) >= max_results:
                        return results
        return results

    @staticmethod
    def _is_word_boundary(text: str, start: int, length: int) -> bool:
        before = start == 0 or not text[start - 1].isidentifier()
        after = (start + length) >= len(text) or not text[start + length].isidentifier()
        return before and after
