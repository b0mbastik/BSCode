"""Project search service boundary."""

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
    """Outline search service.

    Search indexing and content scanning are deliberately omitted.  The method
    signature remains so the UI and future search adapters have a stable seam.
    """

    def search(
        self,
        query: str,
        artifacts: list[Artifact],
        *,
        case_sensitive: bool = False,
        max_results: int = 100,
    ) -> list[SearchResult]:
        return []
