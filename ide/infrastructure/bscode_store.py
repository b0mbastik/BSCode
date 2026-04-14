"""Project-local .bscode persistence directory.

All IDE-internal state that should live alongside the project but not
clutter the project tree is stored here.

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

Adding a new category in the future:
  1. Add a ``<category>_path`` property.
  2. Call ``ensure_dirs()`` before first write.
  3. Read/write via standard ``Path`` operations.
"""

from __future__ import annotations

from pathlib import Path

# Canonical diagram-type names (matches DiagramCanvas tab labels).
DIAGRAM_TYPES: tuple[str, ...] = (
    "Component View",
    "Layered View",
    "Deployment View",
    "UML Class",
    "UML Sequence",
)

# Canonical diagram-type name  →  filename stem inside .bscode/design/
_DIAGRAM_FILENAMES: dict[str, str] = {
    "Component View":  "component-view",
    "Layered View":    "layered-view",
    "Deployment View": "deployment-view",
    "UML Class":       "uml-class",
    "UML Sequence":    "uml-sequence",
}


class BSCodeStore:
    """Manages the ``.bscode`` project-local persistence directory.

    Create one instance per open project.  All paths are derived from
    *project_root* so the store moves with the project folder.
    """

    ROOT_DIR    = ".bscode"
    DESIGN_DIR  = "design"

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.root         = project_root / self.ROOT_DIR
        self.design_path  = self.root / self.DESIGN_DIR

    # ------------------------------------------------------------------
    # Directory management
    # ------------------------------------------------------------------

    def ensure_dirs(self) -> None:
        """Create ``.bscode/design/`` (and any future subdirs) if absent."""
        self.design_path.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Design artefact persistence
    # ------------------------------------------------------------------

    def save_diagram(self, diagram_type: str, content: str) -> None:
        """Write *content* for *diagram_type* to ``.bscode/design/``."""
        self.ensure_dirs()
        path = self._diagram_path(diagram_type)
        if path is None:
            return
        try:
            path.write_text(content, encoding="utf-8")
        except OSError:
            pass

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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _diagram_path(self, diagram_type: str) -> Path | None:
        stem = _DIAGRAM_FILENAMES.get(diagram_type)
        if stem is None:
            return None
        return self.design_path / (stem + ".md")
