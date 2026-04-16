"""Design-to-implementation traceability service."""

from __future__ import annotations

from ide.domain.models import TraceLink


class TraceabilityService:
    """Manages TraceLinks that connect design elements to code artefacts.

    Persistence is handled by the project-local ``BSCodeStore`` sidecar.
    """

    def __init__(self) -> None:
        self._links: dict[str, TraceLink] = {}

    def add_link(self, link: TraceLink) -> TraceLink:
        self._links[link.link_id] = link
        return link

    def remove_link(self, link_id: str) -> bool:
        return self._links.pop(link_id, None) is not None

    def get_all(self) -> list[TraceLink]:
        return list(self._links.values())

    def replace_all(self, links: list[TraceLink]) -> None:
        self._links = {link.link_id: link for link in links}
