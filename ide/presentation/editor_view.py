"""Editor presentation component."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QRect, QSize, QTimer, Qt
from PySide6.QtGui import QColor, QPainter, QSyntaxHighlighter, QTextCharFormat, QTextCursor, QTextFormat
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ide.domain.models import (
    Artifact,
    CompletionItem,
    Diagnostic,
    DiagnosticSeverity,
    Operation,
    TextBuffer,
    UserSession,
)
from ide.services.language import LanguageService


class _LanguageHighlighter(QSyntaxHighlighter):
    def __init__(self, document, language_service: LanguageService) -> None:
        super().__init__(document)
        self.language_service = language_service
        self.keyword_format = QTextCharFormat()
        self.keyword_format.setForeground(QColor(0, 68, 153))
        self.keyword_format.setFontWeight(700)

    def highlightBlock(self, text: str) -> None:
        for start, end, token_type in self.language_service.highlight(text):
            if token_type == "keyword" and end > start:
                self.setFormat(start, end - start, self.keyword_format)


class _LineNumberArea(QWidget):
    def __init__(self, editor: "CodeEditor") -> None:
        super().__init__(editor)
        self.editor = editor
        self.setAccessibleName("Line number and breakpoint gutter")
        self.setToolTip("Click a line number to toggle a debugger breakpoint.")

    def sizeHint(self) -> QSize:
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event) -> None:
        self.editor.line_number_area_paint_event(event)

    def mousePressEvent(self, event) -> None:
        self.editor.line_number_area_mouse_press(event)


class CodeEditor(QPlainTextEdit):
    """Plain-text editor with a line-number gutter and clickable breakpoints."""

    def __init__(self) -> None:
        super().__init__()
        self.line_number_area = _LineNumberArea(self)
        self._breakpoints: set[int] = set()

        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._update_line_number_area)
        self._update_line_number_area_width()

    def breakpoints(self) -> set[int]:
        return set(self._breakpoints)

    def set_breakpoints(self, breakpoints: set[int]) -> None:
        self._breakpoints = {line for line in breakpoints if line > 0}
        self.line_number_area.update()

    def toggle_breakpoint(self, line: int) -> None:
        if line in self._breakpoints:
            self._breakpoints.remove(line)
        elif line > 0:
            self._breakpoints.add(line)
        self.line_number_area.update()

    def line_number_area_width(self) -> int:
        digits = len(str(max(1, self.blockCount())))
        return 18 + self.fontMetrics().horizontalAdvance("9") * digits

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        contents = self.contentsRect()
        self.line_number_area.setGeometry(
            QRect(contents.left(), contents.top(), self.line_number_area_width(), contents.height())
        )

    def line_number_area_paint_event(self, event) -> None:
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), self.palette().base())

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                line_number = block_number + 1
                painter.setPen(QColor(120, 120, 120))
                painter.drawText(
                    0,
                    top,
                    self.line_number_area.width() - 6,
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight,
                    str(line_number),
                )
                if line_number in self._breakpoints:
                    painter.setBrush(QColor(210, 36, 36))
                    painter.setPen(Qt.PenStyle.NoPen)
                    radius = 5
                    painter.drawEllipse(4, top + 4, radius * 2, radius * 2)

            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1

    def line_number_area_mouse_press(self, event) -> None:
        y = int(event.position().y()) if hasattr(event, "position") else event.y()
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        while block.isValid():
            if top <= y <= bottom:
                self.toggle_breakpoint(block_number + 1)
                return
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1

    def _update_line_number_area_width(self) -> None:
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_line_number_area(self, rect: QRect, vertical_delta: int) -> None:
        if vertical_delta:
            self.line_number_area.scroll(0, vertical_delta)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_line_number_area_width()


class _CompletionPopup(QListWidget):
    """Small editor-local completion popup."""

    def __init__(self, editor: CodeEditor, on_insert: Callable[[str], None]) -> None:
        super().__init__(editor.viewport())
        self.editor = editor
        self.on_insert = on_insert
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAccessibleName("Code completion popup")
        self.setToolTip("Completion candidates from the active language service.")
        self.setMaximumHeight(140)
        self.setMinimumWidth(280)
        self.itemClicked.connect(self._insert_item)
        self.hide()

    def show_items(self, items: list[CompletionItem]) -> None:
        self.clear()
        if not items:
            self.hide()
            return
        for completion in items:
            item = QListWidgetItem(f"{completion.label}  {completion.kind.value}")
            item.setData(Qt.ItemDataRole.UserRole, completion.insert_text)
            self.addItem(item)
        cursor_rect = self.editor.cursorRect()
        self.move(cursor_rect.left(), cursor_rect.bottom())
        self.resize(320, min(140, 24 * len(items) + 8))
        self.show()
        self.editor.setFocus()

    def insert_current(self) -> bool:
        item = self.currentItem() or self.item(0)
        if item is None:
            return False
        self._insert_item(item)
        return True

    def _insert_item(self, item: QListWidgetItem) -> None:
        insert_text = item.data(Qt.ItemDataRole.UserRole)
        if insert_text:
            self.on_insert(str(insert_text))
        self.hide()


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
        completion_provider: Callable[["EditorView"], list[CompletionItem]] | None = None,
    ) -> None:
        super().__init__()
        self.artifact = artifact
        self.buffer = TextBuffer(artifact.content)
        self.language_service = language_service
        self.session = session
        self.on_operation = on_operation
        self.completion_provider = completion_provider
        self._updating_from_model = False
        self._diagnostic_selections: list[QTextEdit.ExtraSelection] = []
        self._execution_selection: QTextEdit.ExtraSelection | None = None

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

        self.editor = CodeEditor()
        self.editor.setTabStopDistance(32)
        self.editor.setPlainText(self.buffer.content)
        self.editor.setAccessibleName(f"Code editor for {artifact.name}")
        self.editor.setToolTip(
            "Code editor: edits are broadcast to collaborators automatically. "
            "Ctrl+Space opens lightweight language-service completion."
        )
        self.editor.textChanged.connect(self._on_text_changed)
        self.highlighter = _LanguageHighlighter(self.editor.document(), self.language_service)
        self.completion_popup = _CompletionPopup(self.editor, self.insert_completion)
        self.completion_timer = QTimer(self)
        self.completion_timer.setSingleShot(True)
        self.completion_timer.timeout.connect(self.show_completion)

        layout.addWidget(self.header)
        layout.addWidget(self.editor)

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
            if diagnostic.artifact_id != self.artifact.artifact_id:
                continue
            if diagnostic.line <= 0:
                continue
            selection = QTextEdit.ExtraSelection()
            block = self.editor.document().findBlockByLineNumber(max(0, diagnostic.line - 1))
            if not block.isValid():
                continue
            cursor = QTextCursor(block)
            cursor.select(QTextCursor.SelectionType.LineUnderCursor)
            selection.cursor = cursor
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.format.setBackground(self._diagnostic_colour(diagnostic.severity))
            selections.append(selection)
        self._diagnostic_selections = selections
        self._apply_extra_selections()

    def show_completion(self) -> None:
        if self.completion_provider is None:
            self.completion_popup.hide()
            return
        self.completion_popup.show_items(self.completion_provider(self))

    def insert_completion(self, completion: str) -> None:
        cursor = self.editor.textCursor()
        cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        cursor.insertText(completion)
        self.editor.setTextCursor(cursor)

    def set_execution_line(self, line: int) -> None:
        block = self.editor.document().findBlockByLineNumber(max(0, line - 1))
        if not block.isValid():
            return
        selection = QTextEdit.ExtraSelection()
        cursor = QTextCursor(block)
        cursor.select(QTextCursor.SelectionType.LineUnderCursor)
        selection.cursor = cursor
        selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        selection.format.setBackground(QColor(205, 232, 255))
        self._execution_selection = selection
        self._apply_extra_selections()
        self.editor.setTextCursor(cursor)
        self.editor.ensureCursorVisible()

    def clear_execution_line(self) -> None:
        self._execution_selection = None
        self._apply_extra_selections()

    def breakpoints(self) -> set[int]:
        return self.editor.breakpoints()

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
        self._schedule_completion_popup()

    def _schedule_completion_popup(self) -> None:
        cursor = self.editor.textCursor()
        if cursor.position() == 0:
            self.completion_popup.hide()
            return
        text_before_cursor = self.editor.toPlainText()[: cursor.position()]
        last_character = text_before_cursor[-1:]
        if last_character.isalnum() or last_character in {"_", "."}:
            self.completion_timer.start(250)
        else:
            self.completion_popup.hide()

    def _apply_extra_selections(self) -> None:
        selections = list(self._diagnostic_selections)
        if self._execution_selection is not None:
            selections.append(self._execution_selection)
        self.editor.setExtraSelections(selections)

    @staticmethod
    def _diagnostic_colour(severity: DiagnosticSeverity) -> QColor:
        if severity is DiagnosticSeverity.ERROR:
            return QColor(255, 220, 220)
        if severity is DiagnosticSeverity.WARNING:
            return QColor(255, 246, 204)
        return QColor(226, 238, 255)
