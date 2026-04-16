"""Editor presentation component for the outline IDE.

The editor keeps the UI boundary, document model, operation hook, completion
popup placeholder, and diagnostics/debug rendering methods.  Rich editing
behaviour such as autosave pipelines, breakpoint handling, and inline painting
is intentionally omitted.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QSyntaxHighlighter, QTextCursor
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from ide.domain.models import Artifact, CompletionItem, Diagnostic, Operation, TextBuffer, UserSession
from ide.services.language import LanguageService


class _LanguageHighlighter(QSyntaxHighlighter):
    """Placeholder highlighter delegating to the language-service boundary."""

    def __init__(self, document, language_service: LanguageService) -> None:
        super().__init__(document)
        self.language_service = language_service

    def highlightBlock(self, text: str) -> None:
        # Token styling is intentionally omitted in the outline.
        self.language_service.highlight(text)


class CodeEditor(QPlainTextEdit):
    """Minimal editor widget preserving future gutter/debugger hooks."""

    def __init__(self) -> None:
        super().__init__()
        self.setAccessibleName("Code editor")
        self.setToolTip("Outline editor surface; rich editing behaviour is future work.")
        self._breakpoints: set[int] = set()

    def breakpoints(self) -> set[int]:
        return set(self._breakpoints)

    def set_breakpoints(self, breakpoints: set[int]) -> None:
        self._breakpoints = {line for line in breakpoints if line > 0}

    def toggle_breakpoint(self, line: int) -> None:
        # Breakpoint UI is represented structurally only.
        if line > 0:
            self._breakpoints = {line}


class _CompletionPopup(QListWidget):
    """Placeholder completion popup used by the editor shell."""

    def __init__(self, editor: CodeEditor, on_insert: Callable[[str], None]) -> None:
        super().__init__(editor.viewport())
        self.editor = editor
        self.on_insert = on_insert
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAccessibleName("Code completion popup")
        self.setToolTip("Completion boundary; candidate generation is skeletal.")
        self.hide()
        self.itemClicked.connect(self._insert_item)

    def show_items(self, items: list[CompletionItem]) -> None:
        self.clear()
        for completion in items:
            item = QListWidgetItem(completion.label)
            item.setData(Qt.ItemDataRole.UserRole, completion.insert_text)
            self.addItem(item)
        if items:
            self.show()
        else:
            self.hide()

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
    """Presentation-layer editor boundary.

    Collaborates with ``LanguageService`` for future language behaviour and
    emits ``Operation`` objects to the shell.  The implementation is deliberately
    skeletal and avoids rich editor algorithms.
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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.header = QLabel(f"{artifact.name} [{artifact.language or 'plain'}]")
        self.header.setAccessibleName(f"File header for {artifact.name}")

        self.editor = CodeEditor()
        self.editor.setPlainText(self.buffer.content)
        self.editor.textChanged.connect(self._on_text_changed)
        self.highlighter = _LanguageHighlighter(self.editor.document(), language_service)

        self.completion_popup = _CompletionPopup(self.editor, self.insert_completion)
        self.completion_timer = QTimer(self)
        self.completion_timer.setSingleShot(True)
        self.completion_timer.timeout.connect(self.show_completion)

        layout.addWidget(self.header)
        layout.addWidget(self.editor)
        self.setFocusProxy(self.editor)

    def apply_op(self, operation: Operation) -> None:
        """Apply an operation to the local buffer.

        This keeps the collaboration seam visible; conflict handling is omitted.
        """
        self.buffer.apply(operation)
        self.artifact.content = self.buffer.content
        self._updating_from_model = True
        self.editor.setPlainText(self.buffer.content)
        self._updating_from_model = False

    def render_diagnostics(self, diagnostics: list[Diagnostic]) -> None:
        """Diagnostics rendering hook retained for the analysis subsystem."""
        return None

    def show_completion(self) -> None:
        items = self.completion_provider(self) if self.completion_provider else []
        self.completion_popup.show_items(items)

    def insert_completion(self, completion: str) -> None:
        cursor = self.editor.textCursor()
        cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        cursor.insertText(completion)
        self.editor.setTextCursor(cursor)

    def set_execution_line(self, line: int) -> None:
        """Debugger execution-line hook; no painting is performed."""
        return None

    def clear_execution_line(self) -> None:
        return None

    def breakpoints(self) -> set[int]:
        return self.editor.breakpoints()

    def _on_text_changed(self) -> None:
        if self._updating_from_model:
            return
        self.buffer.content = self.editor.toPlainText()
        self.artifact.content = self.buffer.content
        operation = Operation(
            artifact_id=self.artifact.artifact_id,
            user_id=self.session.user_id,
            position=0,
            delete_count=0,
            text=self.buffer.content,
        )
        self.on_operation(operation, self.artifact)
        # Completion debounce is structural only; services return placeholders.
        self.completion_timer.start(500)
