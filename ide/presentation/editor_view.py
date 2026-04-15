"""Editor presentation component."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat, QTextCursor, QTextFormat
from PySide6.QtWidgets import (
    QLabel,
    QPlainTextEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ide.domain.models import Artifact, Diagnostic, DiagnosticSeverity, Operation, TextBuffer, UserSession
from ide.services.language import LanguageService


class _LanguageHighlighter(QSyntaxHighlighter):
    def __init__(self, document, language_service: LanguageService) -> None:
        super().__init__(document)
        self.language_service = language_service
        self.keyword_format = QTextCharFormat()
        self.keyword_format.setForeground(QColor(0, 68, 153))
        self.keyword_format.setFontWeight(700)

    def highlightBlock(self, text: str) -> None:  # noqa: N802 - Qt override
        for start, end, token_type in self.language_service.highlight(text):
            if token_type == "keyword" and end > start:
                self.setFormat(start, end - start, self.keyword_format)


class EditorView(QWidget):
    """Code editor widget with inline diagnostic highlights.

    Accessibility: every child widget carries a descriptive
    ``accessibleName`` and ``toolTip`` so screen readers and keyboard
    navigation work correctly (WCAG 2.1 AA intent).
    """

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

        lang_label = artifact.language or "plain text"
        self.header = QLabel(f"{artifact.name} [{lang_label}]")
        self.header.setContentsMargins(8, 4, 8, 4)
        self.header.setAccessibleName(f"File header: {artifact.name}, language {lang_label}")
        self.header.setToolTip(
            f"Artefact: {artifact.name}\n"
            f"Language: {lang_label}\n"
            f"Path: {artifact.path or '(in-memory)'}"
        )

        self.editor = QPlainTextEdit()
        self.editor.setTabStopDistance(32)
        self.editor.setPlainText(self.buffer.content)
        self.editor.setAccessibleName(f"Code editor for {artifact.name}")
        self.editor.setToolTip(
            "Code editor — Ctrl+S saves and creates a version checkpoint. "
            "Edits are broadcast to collaborators automatically. "
            "Use Ctrl+Space from the IDE shell for code completion."
        )
        self.editor.textChanged.connect(self._on_text_changed)
        self.highlighter = _LanguageHighlighter(self.editor.document(), self.language_service)

        layout.addWidget(self.header)
        layout.addWidget(self.editor)

        # Make the editor itself focusable via Tab key.
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocusProxy(self.editor)

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

    def completion_candidates(self) -> list[str]:
        cursor = self.editor.textCursor()
        block = cursor.block()
        line = block.blockNumber() + 1
        column = cursor.positionInBlock() + 1
        return self.language_service.complete(self.editor.toPlainText(), line, column)

    def insert_completion(self, completion: str) -> None:
        cursor = self.editor.textCursor()
        cursor.insertText(completion)
        self.editor.setTextCursor(cursor)

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

    @staticmethod
    def _diagnostic_colour(severity: DiagnosticSeverity) -> QColor:
        if severity is DiagnosticSeverity.ERROR:
            return QColor(255, 220, 220)   # light red — sufficient contrast on white
        if severity is DiagnosticSeverity.WARNING:
            return QColor(255, 246, 204)   # light amber
        return QColor(226, 238, 255)       # light blue for info
