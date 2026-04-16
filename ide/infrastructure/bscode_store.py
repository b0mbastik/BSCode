"""Project-local ``.bscode`` metadata boundary.

The real persistence format is intentionally not implemented.  This class keeps
the expected sidecar locations and method contracts so the report can map notes,
traceability, revisions, and design artefacts to a project-local metadata
boundary.
"""

from __future__ import annotations

from pathlib import Path

from ide.domain.models import Comment, Revision, TraceLink


DIAGRAM_TYPES: tuple[str, ...] = (
    "Component View",
    "Layered View",
    "Deployment View",
    "UML Class",
    "UML Sequence",
)


class BSCodeStore:
    """Structural store for IDE metadata under ``.bscode``.

    The outline creates no required runtime files and returns empty collections.
    A production adapter would serialise JSON/diagram content here.
    """

    ROOT_DIR = ".bscode"
    DESIGN_DIR = "design"
    COMMENTS_FILE = "comments.json"
    TRACE_FILE = "traceability.json"
    REVISIONS_FILE = "revisions.json"

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.root = project_root / self.ROOT_DIR
        self.design_path = self.root / self.DESIGN_DIR

    def ensure_dirs(self) -> None:
        """Placeholder for creating project-local metadata directories."""
        # Directory creation is omitted in the outline implementation.
        return None

    def load_diagram(self, diagram_type: str) -> str | None:
        return None

    def load_all_diagrams(self) -> dict[str, str]:
        return {}

    def has_any_diagrams(self) -> bool:
        return False

    def save_comments(self, comments: list[Comment]) -> None:
        # TODO: future adapter writes comments.json.
        return None

    def load_comments(self) -> list[Comment]:
        return []

    def save_trace_links(self, links: list[TraceLink]) -> None:
        # TODO: future adapter writes traceability.json.
        return None

    def load_trace_links(self) -> list[TraceLink]:
        return []

    def save_revisions(self, revisions: list[Revision]) -> None:
        # TODO: future adapter writes revisions.json.
        return None

    def load_revisions(self) -> list[Revision]:
        return []
