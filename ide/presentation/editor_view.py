"""Editor presentation component."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QTextCursor, QTextFormat
from PySide6.QtWidgets import QLabel, QPlainTextEdit, QTextEdit, QVBoxLayout, QWidget

from ide.domain.models import Artifact, Diagnostic, DiagnosticSeverity, Operation, TextBuffer, UserSession
from ide.services.language import LanguageService


class EditorView(QWidget):
    def __init__(
        self,
        artifact: Artifact,
        language_service: LanguageService,
        session: UserSession,
        on_operation: Callable[[Operation, Artifact], None],
    ) -> None:
        super().__init__()
        self.artifact = artifact
        self.buffer = TextBuffer(artifact.content)
        self.language_service = language_service
        self.session = session
        self.on_operation = on_operation
        self._updating_from_model = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.header = QLabel(f"{artifact.name} [{artifact.language or 'plain text'}]")
        self.header.setContentsMargins(8, 4, 8, 4)
        self.editor = QPlainTextEdit()
        self.editor.setTabStopDistance(32)
        self.editor.setPlainText(self.buffer.content)
        self.editor.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.header)
        layout.addWidget(self.editor)

    def apply_op(self, operation: Operation) -> None:
        self.buffer.apply(operation)
        self.artifact.content = self.buffer.content
        self._updating_from_model = True
        self.editor.setPlainText(self.buffer.content)
        self._updating_from_model = False

    def render_diagnostics(self, diagnostics: list[Diagnostic]) -> None:
        selections: list[QTextEdit.ExtraSelection] = []
        for diagnostic in diagnostics:
            selection = QTextEdit.ExtraSelection()
            block = self.editor.document().findBlockByLineNumber(max(0, diagnostic.line - 1))
            cursor = QTextCursor(block)
            cursor.select(QTextCursor.SelectionType.LineUnderCursor)
            selection.cursor = cursor
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.format.setBackground(self._diagnostic_colour(diagnostic.severity))
            selections.append(selection)
        self.editor.setExtraSelections(selections)

    def _on_text_changed(self) -> None:
        if self._updating_from_model:
            return
        current_text = self.editor.toPlainText()
        operation = Operation(
            artifact_id=self.artifact.artifact_id,
            user_id=self.session.user_id,
            position=0,
            delete_count=len(self.buffer.content),
            text=current_text,
        )
        self.buffer.apply(operation)
        self.artifact.content = self.buffer.content
        self.on_operation(operation, self.artifact)

    def _diagnostic_colour(self, severity: DiagnosticSeverity) -> QColor:
        if severity is DiagnosticSeverity.ERROR:
            return QColor(255, 220, 220)
        if severity is DiagnosticSeverity.WARNING:
            return QColor(255, 246, 204)
        return QColor(226, 238, 255)
