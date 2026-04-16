"""Project-local ``.bscode`` persistence directory.

IDE-internal state that should move with the project, but not clutter the
visible source tree, is stored under ``.bscode``.

Current layout::

    <project_root>/
      .bscode/
        design/
          component-view.md
          layered-view.md
          deployment-view.md
          uml-class.md
          uml-sequence.md
        <reserved for future IDE state>
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from ide.domain.models import Comment, Revision, TraceLink

# Canonical diagram-type names matching DiagramCanvas tab labels.
DIAGRAM_TYPES: tuple[str, ...] = (
    "Component View",
    "Layered View",
    "Deployment View",
    "UML Class",
    "UML Sequence",
)

_DIAGRAM_FILENAMES: dict[str, str] = {
    "Component View": "component-view",
    "Layered View": "layered-view",
    "Deployment View": "deployment-view",
    "UML Class": "uml-class",
    "UML Sequence": "uml-sequence",
}


class BSCodeStore:
    """Manages the ``.bscode`` project-local persistence directory.

    Create one instance per open project. All paths are derived from
    ``project_root`` so the store moves with the project folder.
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
        """Create ``.bscode/design/`` (and any future subdirs) if absent."""
        self.root.mkdir(parents=True, exist_ok=True)
        self.design_path.mkdir(parents=True, exist_ok=True)

    def load_diagram(self, diagram_type: str) -> str | None:
        """Return saved content for *diagram_type*, or ``None`` if unsaved."""
        path = self._diagram_path(diagram_type)
        if path is None or not path.exists():
            return None
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return None

    def load_all_diagrams(self) -> dict[str, str]:
        """Return ``{diagram_type: content}`` for every diagram that has been saved."""
        result: dict[str, str] = {}
        for diagram_type in _DIAGRAM_FILENAMES:
            content = self.load_diagram(diagram_type)
            if content is not None:
                result[diagram_type] = content
        return result

    def has_any_diagrams(self) -> bool:
        """True if at least one diagram file exists on disk."""
        if not self.design_path.exists():
            return False
        return any(
            (self.design_path / (stem + ".md")).exists()
            for stem in _DIAGRAM_FILENAMES.values()
        )

    def save_comments(self, comments: list[Comment]) -> None:
        self._write_json(
            self.root / self.COMMENTS_FILE,
            [
                {
                    "comment_id": comment.comment_id,
                    "artifact_id": comment.artifact_id,
                    "line": comment.line,
                    "author": comment.author,
                    "body": comment.body,
                    "timestamp": comment.timestamp.isoformat(),
                }
                for comment in comments
            ],
        )

    def load_comments(self) -> list[Comment]:
        return [
            Comment(
                comment_id=str(record.get("comment_id", "")),
                artifact_id=str(record.get("artifact_id", "")),
                line=int(record.get("line", 1)),
                author=str(record.get("author", "")),
                body=str(record.get("body", "")),
                timestamp=self._parse_datetime(record.get("timestamp", "")),
            )
            for record in self._read_json(self.root / self.COMMENTS_FILE)
        ]

    def save_trace_links(self, links: list[TraceLink]) -> None:
        self._write_json(
            self.root / self.TRACE_FILE,
            [
                {
                    "link_id": link.link_id,
                    "design_artifact_id": link.design_artifact_id,
                    "design_element": link.design_element,
                    "code_artifact_id": link.code_artifact_id,
                    "code_element": link.code_element,
                    "description": link.description,
                }
                for link in links
            ],
        )

    def load_trace_links(self) -> list[TraceLink]:
        return [
            TraceLink(
                link_id=str(record.get("link_id", "")),
                design_artifact_id=str(record.get("design_artifact_id", "")),
                design_element=str(record.get("design_element", "")),
                code_artifact_id=str(record.get("code_artifact_id", "")),
                code_element=str(record.get("code_element", "")),
                description=str(record.get("description", "")),
            )
            for record in self._read_json(self.root / self.TRACE_FILE)
        ]

    def save_revisions(self, revisions: list[Revision]) -> None:
        self._write_json(
            self.root / self.REVISIONS_FILE,
            [
                {
                    "revision_id": revision.revision_id,
                    "artifact_id": revision.artifact_id,
                    "content": revision.content,
                    "author": revision.author,
                    "message": revision.message,
                    "timestamp": revision.timestamp.isoformat(),
                }
                for revision in revisions
            ],
        )

    def load_revisions(self) -> list[Revision]:
        return [
            Revision(
                revision_id=str(record.get("revision_id", "")),
                artifact_id=str(record.get("artifact_id", "")),
                content=str(record.get("content", "")),
                author=str(record.get("author", "")),
                message=str(record.get("message", "Checkpoint")),
                timestamp=self._parse_datetime(record.get("timestamp", "")),
            )
            for record in self._read_json(self.root / self.REVISIONS_FILE)
        ]

    def _diagram_path(self, diagram_type: str) -> Path | None:
        stem = _DIAGRAM_FILENAMES.get(diagram_type)
        if stem is None:
            return None
        return self.design_path / (stem + ".md")

    def _write_json(self, path: Path, payload: list[dict[str, object]]) -> None:
        self.ensure_dirs()
        try:
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError:
            pass

    @staticmethod
    def _read_json(path: Path) -> list[dict[str, object]]:
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return payload if isinstance(payload, list) else []

    @staticmethod
    def _parse_datetime(value: object) -> datetime:
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                pass
        return datetime.now().astimezone()
