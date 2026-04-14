"""Design-to-implementation traceability service."""

from __future__ import annotations

from ide.domain.models import TraceLink


class TraceabilityService:
    """Manages TraceLinks that connect design elements to code artefacts.

    Links are held in memory. A real implementation would persist them
    alongside the project (e.g. a JSON sidecar file).
    """

    def __init__(self) -> None:
        self._links: dict[str, TraceLink] = {}  # link_id → TraceLink

    def add_link(self, link: TraceLink) -> TraceLink:
        self._links[link.link_id] = link
        return link

    def remove_link(self, link_id: str) -> bool:
        return self._links.pop(link_id, None) is not None

    def get_all(self) -> list[TraceLink]:
        return list(self._links.values())

    def get_links_for_design(self, design_artifact_id: str) -> list[TraceLink]:
        return [l for l in self._links.values() if l.design_artifact_id == design_artifact_id]

    def get_links_for_code(self, code_artifact_id: str) -> list[TraceLink]:
        return [l for l in self._links.values() if l.code_artifact_id == code_artifact_id]

    def get_links_for_artifact(self, artifact_id: str) -> list[TraceLink]:
        """Return all links that mention *artifact_id* on either side."""
        return [
            l for l in self._links.values()
            if l.design_artifact_id == artifact_id or l.code_artifact_id == artifact_id
        ]
