"""Small presentation widgets used by the IDE shell."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QPlainTextEdit,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ide.domain.models import PeerSession


_DIAGRAM_TEMPLATES: list[tuple[str, str]] = [
    (
        "Component View",
        "# Component Diagram\n"
        "# Notation: ComponentName -> DependsOn\n\n"
        "Presentation -> Workspace\n"
        "Workspace -> CoreIDEServices\n"
        "CoreIDEServices -> AnalysisEngine\n"
        "AnalysisEngine -> Infrastructure\n"
        "Presentation -> Infrastructure\n",
    ),
    (
        "Layered View",
        "# Layered Architecture View\n"
        "# List layers top-to-bottom; each layer may only depend on layers below it.\n\n"
        "[Layer 1]  Presentation\n"
        "[Layer 2]  Workspace\n"
        "[Layer 3]  Core IDE Services  |  Analysis Engine\n"
        "[Layer 4]  Domain Models\n"
        "[Layer 5]  Infrastructure\n",
    ),
    (
        "Deployment View",
        "# Deployment Diagram\n"
        "# Notation: Node { Container { Artefact } }\n\n"
        "Developer Workstation {\n"
        "    IDE Process {\n"
        "        ide.app\n"
        "        ide.presentation\n"
        "        ide.services\n"
        "    }\n"
        "    Filesystem {\n"
        "        project_files\n"
        "        revision_log\n"
        "    }\n"
        "}\n"
        "Collaboration Server (outline) {\n"
        "    NetworkSync endpoint\n"
        "}\n",
    ),
    (
        "UML Class",
        "# UML Class Diagram\n"
        "# Notation: ClassName { +field: Type  +method(): RetType }\n\n"
        "IDEApplication {\n"
        "    +project_manager: ProjectManager\n"
        "    +artifact_store: ArtifactStore\n"
        "    +analysis_manager: AnalysisManager\n"
        "    +open_project(name, path): void\n"
        "    +open_file(path): Artifact\n"
        "}\n\n"
        "IDEApplication --> ProjectManager\n"
        "IDEApplication --> ArtifactStore\n"
        "IDEApplication --> AnalysisManager\n",
    ),
    (
        "UML Sequence",
        "# UML Sequence Diagram\n"
        "# Notation: Sender -> Receiver: message()\n\n"
        "User -> IDEShell: open_file(path)\n"
        "IDEShell -> IDEApplication: open_file(path)\n"
        "IDEApplication -> FilesystemPersistence: read(path)\n"
        "FilesystemPersistence --> IDEApplication: content\n"
        "IDEApplication --> IDEShell: Artifact\n"
        "IDEShell -> EditorView: open_artifact(artifact)\n"
        "EditorView --> IDEShell: editor tab shown\n",
    ),
]


class DiagramCanvas(QWidget):
    """Multi-tab design editor covering the five key diagram types.

    Each tab provides a text-based DSL editor pre-loaded with a template.
    A real implementation would render the DSL graphically; here the text
    itself carries the architectural information.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("DiagramCanvas")
        self.setAccessibleName("Architecture and design diagram editor")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        header = QLabel("Architecture / Design Canvas - select a diagram type below")
        header.setAccessibleName("Diagram canvas header")
        layout.addWidget(header)

        self._tabs = QTabWidget()
        self._tabs.setAccessibleName("Diagram type tabs")
        self._editors: dict[str, QPlainTextEdit] = {}

        self._on_change: Callable[[str, str], None] | None = None

        for name, template in _DIAGRAM_TEMPLATES:
            editor = QPlainTextEdit()
            editor.setPlainText(template)
            editor.setPlaceholderText(f"Edit the {name} DSL here.")
            editor.setAccessibleName(f"{name} diagram editor")
            editor.setToolTip(f"Text-based editor for {name} diagrams.")
            editor.textChanged.connect(
                lambda diagram_name=name, diagram_editor=editor: self._emit_change(
                    diagram_name,
                    diagram_editor,
                )
            )
            self._tabs.addTab(editor, name)
            self._editors[name] = editor

        layout.addWidget(self._tabs)

        # Preserve the existing ``.editor`` attribute for code that expects it.
        self._tabs.currentChanged.connect(self._sync_editor_alias)
        self.editor = self._editors[_DIAGRAM_TEMPLATES[0][0]]

    def set_on_change(self, callback: Callable[[str, str], None]) -> None:
        """Register ``callback(diagram_type, content)`` fired on any diagram edit."""
        self._on_change = callback

    def _emit_change(self, name: str, editor: QPlainTextEdit) -> None:
        if self._on_change is not None:
            self._on_change(name, editor.toPlainText())

    def load_saved_content(self, saved: dict[str, str]) -> None:
        """Populate editors from a ``{diagram_type: content}`` mapping.

        Only types present in *saved* are updated; missing types keep their
        default template so the canvas is never left blank.
        """
        for diagram_type, content in saved.items():
            editor = self._editors.get(diagram_type)
            if editor is not None:
                editor.blockSignals(True)
                editor.setPlainText(content)
                editor.blockSignals(False)

    def reset_to_templates(self) -> None:
        for diagram_type, template in _DIAGRAM_TEMPLATES:
            editor = self._editors.get(diagram_type)
            if editor is not None:
                editor.blockSignals(True)
                editor.setPlainText(template)
                editor.blockSignals(False)

    def _sync_editor_alias(self, index: int) -> None:
        name = self._tabs.tabText(index)
        if name in self._editors:
            self.editor = self._editors[name]

    def get_editor(self, diagram_type: str) -> QPlainTextEdit | None:
        return self._editors.get(diagram_type)

    def diagram_types(self) -> list[str]:
        return list(self._editors)

    def set_current_diagram(self, diagram_type: str) -> None:
        for index in range(self._tabs.count()):
            if self._tabs.tabText(index) == diagram_type:
                self._tabs.setCurrentIndex(index)
                return

    def set_content(self, diagram_type: str, content: str) -> None:
        editor = self._editors.get(diagram_type)
        if editor is not None:
            editor.setPlainText(content)

    def get_content(self, diagram_type: str) -> str:
        editor = self._editors.get(diagram_type)
        return editor.toPlainText() if editor else ""


class CollabUI(QWidget):
    """Collaboration panel showing peer presence and activity log.

    Presence records which artefact each peer is currently editing.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setAccessibleName("Collaboration panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        presence_label = QLabel("Peer Presence")
        presence_label.setAccessibleName("Peer presence section header")
        layout.addWidget(presence_label)

        self.peer_list = QListWidget()
        self.peer_list.setAccessibleName("Peer presence list")
        self.peer_list.setToolTip("Shows connected collaborators and which file they are editing.")
        self.peer_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.peer_list.setMaximumHeight(120)
        layout.addWidget(self.peer_list)

        event_label = QLabel("Collaboration Events")
        event_label.setAccessibleName("Collaboration event log header")
        layout.addWidget(event_label)

        self.event_log = QListWidget()
        self.event_log.setAccessibleName("Collaboration event log")
        self.event_log.setToolTip("Live log of collaborative editing events.")
        layout.addWidget(self.event_log)

    def set_peers(self, peers: list[PeerSession]) -> None:
        self.peer_list.clear()
        for peer in peers:
            if peer.active_artifact_name:
                label = f"{peer.display_name} - editing: {peer.active_artifact_name}"
            else:
                label = f"{peer.display_name} - idle"
            self.peer_list.addItem(label)

    def update_peer(self, peer: PeerSession) -> None:
        """Refresh a single peer row without clearing the whole list."""
        for i in range(self.peer_list.count()):
            item = self.peer_list.item(i)
            if item and peer.display_name in item.text():
                if peer.active_artifact_name:
                    item.setText(f"{peer.display_name} - editing: {peer.active_artifact_name}")
                else:
                    item.setText(f"{peer.display_name} - idle")
                return
        self.set_peers([peer])

    def log_event(self, message: str) -> None:
        self.event_log.insertItem(0, message)
        while self.event_log.count() > 100:
            self.event_log.takeItem(self.event_log.count() - 1)
