"""Small presentation widgets used by the IDE shell."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QListWidget, QPlainTextEdit, QVBoxLayout, QWidget

from ide.domain.models import PeerSession


class DiagramCanvas(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("DiagramCanvas")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        title = QLabel("Architecture / Design Canvas")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText("Architecture and design models will be edited here.")
        self.editor.setPlainText(
            "Component: Presentation -> Workspace\n"
            "Component: Workspace -> Core IDE Services\n"
            "Component: Core IDE Services -> Analysis Engine\n"
            "All layers may depend on Infrastructure abstractions.\n"
        )
        layout.addWidget(title)
        layout.addWidget(self.editor)


class CollabUI(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(QLabel("Presence"))
        self.peer_list = QListWidget()
        layout.addWidget(self.peer_list)
        layout.addWidget(QLabel("Collaboration Events"))
        self.event_log = QListWidget()
        layout.addWidget(self.event_log)

    def set_peers(self, peers: list[PeerSession]) -> None:
        self.peer_list.clear()
        for peer in peers:
            self.peer_list.addItem(f"{peer.display_name} - online")

    def log_event(self, message: str) -> None:
        self.event_log.insertItem(0, message)
