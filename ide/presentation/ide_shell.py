"""Main PySide6 IDE shell."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QDockWidget,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QStatusBar,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ide.domain.models import (
    Artifact,
    ArtifactType,
    Comment,
    Diagnostic,
    Operation,
    SyncStatus,
    TraceLink,
)
from ide.presentation.editor_view import EditorView
from ide.presentation.widgets import CollabUI, DiagramCanvas

if TYPE_CHECKING:
    from ide.app.application import IDEApplication


# ---------------------------------------------------------------------------
# Helper dialogs
# ---------------------------------------------------------------------------

class _AddCommentDialog(QDialog):
    def __init__(self, parent: QWidget, artifact_name: str, author: str) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Add Comment — {artifact_name}")
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.line_edit = QLineEdit("1")
        self.line_edit.setAccessibleName("Line number input")
        self.body_edit = QPlainTextEdit()
        self.body_edit.setAccessibleName("Comment body input")
        self.body_edit.setPlaceholderText("Enter your comment …")
        self.body_edit.setFixedHeight(90)
        form.addRow("Line:", self.line_edit)
        form.addRow("Author:", QLabel(author))
        form.addRow("Comment:", self.body_edit)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def line_number(self) -> int:
        try:
            return max(1, int(self.line_edit.text()))
        except ValueError:
            return 1

    @property
    def body(self) -> str:
        return self.body_edit.toPlainText().strip()


class _AddTraceLinkDialog(QDialog):
    def __init__(self, parent: QWidget, artifact_names: list[str]) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Trace Link")
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.design_artifact = QLineEdit()
        self.design_artifact.setAccessibleName("Design artefact name input")
        self.design_element = QLineEdit()
        self.design_element.setAccessibleName("Design element name input")
        self.code_artifact = QLineEdit()
        self.code_artifact.setAccessibleName("Code artefact name input")
        self.code_element = QLineEdit()
        self.code_element.setAccessibleName("Code element name input")
        self.description = QLineEdit()
        self.description.setAccessibleName("Link description input")
        form.addRow("Design artefact:", self.design_artifact)
        form.addRow("Design element:", self.design_element)
        form.addRow("Code artefact:", self.code_artifact)
        form.addRow("Code element:", self.code_element)
        form.addRow("Description:", self.description)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


# ---------------------------------------------------------------------------
# Main shell
# ---------------------------------------------------------------------------

class IDEShell(QMainWindow):
    def __init__(self, application: IDEApplication) -> None:
        super().__init__()
        self.application = application
        self.active_editor: EditorView | None = None
        self._last_diagnostics: list[Diagnostic] = []
        self._project_selector_updating = False

        self.setWindowTitle("Architecture Driven Collaborative IDE")
        self.resize(1400, 900)
        self.setAccessibleName("Architecture Driven Collaborative IDE main window")

        # Debounce timers
        self.analysis_timer = QTimer(self)
        self.analysis_timer.setSingleShot(True)
        self.analysis_timer.timeout.connect(lambda: self._run_static_analysis(add_output=False))


        self._build_ui()

        # Sync status from the network layer.
        self.application.network_sync.add_status_listener(self._on_sync_status_changed)

        self.statusBar().showMessage("Desktop IDE shell ready.  Press F1 for help.")
        self._refresh_project_selector()
        self.refresh_project_explorer()
        self._load_diagrams_for_active_project()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self._create_actions()
        self._create_menu_bar()
        self._create_toolbar()
        self._create_central_tabs()
        self._create_left_dock()
        self._create_right_docks()
        self._create_bottom_dock()
        self._create_status_bar()

    def _create_actions(self) -> None:
        # File
        self.new_project_action = QAction("New Project", self)
        self.new_project_action.setToolTip("Create a new empty project")
        self.new_project_action.triggered.connect(self.new_project)

        self.open_project_action = QAction("Open Project…", self)
        self.open_project_action.setShortcut(QKeySequence("Ctrl+Shift+O"))
        self.open_project_action.setToolTip("Open a folder as a project (Ctrl+Shift+O)")
        self.open_project_action.triggered.connect(self.open_project)

        self.open_file_action = QAction("Open File…", self)
        self.open_file_action.setShortcut(QKeySequence("Ctrl+O"))
        self.open_file_action.setToolTip("Open a single file (Ctrl+O)")
        self.open_file_action.triggered.connect(self.open_file)

        self.save_artifact_action = QAction("Save", self)
        self.save_artifact_action.setShortcut(QKeySequence("Ctrl+S"))
        self.save_artifact_action.setToolTip("Save active file and create a version checkpoint (Ctrl+S)")
        self.save_artifact_action.triggered.connect(self.save_active_artifact)

        self.close_tab_action = QAction("Close Tab", self)
        self.close_tab_action.setShortcut(QKeySequence("Ctrl+W"))
        self.close_tab_action.setToolTip("Close the current editor tab (Ctrl+W)")
        self.close_tab_action.triggered.connect(self._close_active_tab)

        self.version_history_action = QAction("Version History…", self)
        self.version_history_action.setToolTip("Show revision history for the active file")
        self.version_history_action.triggered.connect(self.show_version_history)

        # Edit
        self.find_in_project_action = QAction("Find in Project…", self)
        self.find_in_project_action.setShortcut(QKeySequence("Ctrl+Shift+F"))
        self.find_in_project_action.setToolTip("Search all artefacts in the project (Ctrl+Shift+F)")
        self.find_in_project_action.triggered.connect(self.show_search_bar)

        self.complete_action = QAction("Code Completion…", self)
        self.complete_action.setShortcut(QKeySequence("Ctrl+Space"))
        self.complete_action.setToolTip("Show language-service completion candidates (Ctrl+Space)")
        self.complete_action.triggered.connect(self.show_code_completion)

        # Run
        self.run_file_action = QAction("Run Active File", self)
        self.run_file_action.setShortcut(QKeySequence("F5"))
        self.run_file_action.setToolTip(
            "Run the currently active Python file with the system interpreter (F5)"
        )
        self.run_file_action.triggered.connect(self.run_active_file)

        self.run_tests_action = QAction("Run Tests", self)
        self.run_tests_action.setShortcut(QKeySequence("Ctrl+T"))
        self.run_tests_action.setToolTip("Discover and run all test files in the project (Ctrl+T)")
        self.run_tests_action.triggered.connect(self.run_tests)

        self.build_action = QAction("Run Build", self)
        self.build_action.setToolTip("Invoke the build service for the active project")
        self.build_action.triggered.connect(self.run_build)

        # Analyse
        self.static_analysis_action = QAction("Run Static Analysis", self)
        self.static_analysis_action.setShortcut(QKeySequence("Ctrl+Shift+A"))
        self.static_analysis_action.setToolTip("Run static analysis on all project artefacts (Ctrl+Shift+A)")
        self.static_analysis_action.triggered.connect(
            lambda: self._run_static_analysis(add_output=True)
        )

        # VCS
        self.commit_action = QAction("Commit", self)
        self.commit_action.setToolTip("Commit current changes via the VCS service")
        self.commit_action.triggered.connect(self.commit)

        # Help
        self.help_topics_action = QAction("Help Topics…", self)
        self.help_topics_action.setShortcut(QKeySequence("F1"))
        self.help_topics_action.setToolTip("Open the help topics browser (F1)")
        self.help_topics_action.triggered.connect(self.show_help_topics)

        self.contextual_help_action = QAction("Contextual Help", self)
        self.contextual_help_action.setToolTip("Show help for the currently active panel")
        self.contextual_help_action.triggered.connect(self.show_contextual_help)

        self.about_action = QAction("About", self)
        self.about_action.triggered.connect(self.about)

    def _create_menu_bar(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        file_menu.setAccessibleName("File menu")
        file_menu.addAction(self.new_project_action)
        file_menu.addAction(self.open_project_action)
        file_menu.addAction(self.open_file_action)
        file_menu.addSeparator()
        file_menu.addAction(self.save_artifact_action)
        file_menu.addAction(self.close_tab_action)
        file_menu.addSeparator()
        file_menu.addAction(self.version_history_action)

        edit_menu = self.menuBar().addMenu("&Edit")
        edit_menu.setAccessibleName("Edit menu")
        edit_menu.addAction(self.find_in_project_action)
        edit_menu.addAction(self.complete_action)

        run_menu = self.menuBar().addMenu("&Run")
        run_menu.setAccessibleName("Run menu")
        run_menu.addAction(self.run_file_action)
        run_menu.addSeparator()
        run_menu.addAction(self.run_tests_action)
        run_menu.addAction(self.build_action)

        analyse_menu = self.menuBar().addMenu("&Analyse")
        analyse_menu.setAccessibleName("Analyse menu")
        analyse_menu.addAction(self.static_analysis_action)

        vcs_menu = self.menuBar().addMenu("&VCS")
        vcs_menu.setAccessibleName("VCS menu")
        vcs_menu.addAction(self.commit_action)

        help_menu = self.menuBar().addMenu("&Help")
        help_menu.setAccessibleName("Help menu")
        help_menu.addAction(self.help_topics_action)
        help_menu.addAction(self.contextual_help_action)
        help_menu.addSeparator()
        help_menu.addAction(self.about_action)

    def _create_toolbar(self) -> None:
        toolbar = QToolBar("Main toolbar")
        toolbar.setMovable(False)
        toolbar.setAccessibleName("Main toolbar")
        toolbar.addAction(self.new_project_action)
        toolbar.addAction(self.open_file_action)
        toolbar.addAction(self.save_artifact_action)
        toolbar.addSeparator()
        toolbar.addAction(self.run_file_action)
        toolbar.addAction(self.run_tests_action)
        toolbar.addAction(self.build_action)
        toolbar.addAction(self.static_analysis_action)
        toolbar.addAction(self.complete_action)
        toolbar.addSeparator()

        project_label = QLabel("Project: ")
        project_label.setAccessibleName("Active project selector label")
        self.project_selector = QComboBox()
        self.project_selector.setAccessibleName("Active project selector")
        self.project_selector.setToolTip("Switch between projects opened in this IDE session.")
        self.project_selector.setMinimumWidth(180)
        self.project_selector.currentIndexChanged.connect(self._on_project_selected)
        toolbar.addWidget(project_label)
        toolbar.addWidget(self.project_selector)
        toolbar.addSeparator()

        # Inline search field
        search_label = QLabel("  Find: ")
        search_label.setAccessibleName("Project search label")
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Search project…")
        self.search_field.setMaximumWidth(220)
        self.search_field.setAccessibleName("Project search field")
        self.search_field.setToolTip("Type and press Enter to search all project artefacts (Ctrl+Shift+F)")
        self.search_field.returnPressed.connect(self._execute_search)
        toolbar.addWidget(search_label)
        toolbar.addWidget(self.search_field)

        self.addToolBar(toolbar)

    def _create_central_tabs(self) -> None:
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setAccessibleName("Editor tabs")
        self.diagram_canvas = DiagramCanvas()
        self.tabs.addTab(self.diagram_canvas, "Design")
        # Design tab is permanent — remove its close button.
        self.tabs.tabBar().setTabButton(0, self.tabs.tabBar().ButtonPosition.RightSide, None)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.tabs.tabCloseRequested.connect(self._on_tab_close_requested)
        self.setCentralWidget(self.tabs)

    def _create_left_dock(self) -> None:
        self.project_tree = QTreeWidget()
        self.project_tree.setHeaderLabels(["Project Explorer"])
        self.project_tree.setAccessibleName("Project Explorer tree")
        self.project_tree.setToolTip("Double-click a file to open it in the editor.")
        self.project_tree.itemDoubleClicked.connect(self._open_tree_item)
        project_dock = QDockWidget("Project Explorer", self)
        project_dock.setAccessibleName("Project Explorer dock")
        project_dock.setWidget(self.project_tree)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, project_dock)

    def _create_right_docks(self) -> None:
        # --- Collaboration ---
        self.collab_ui = CollabUI()
        self.collab_ui.set_peers(self.application.collab_service.peers)
        collab_dock = QDockWidget("Collaboration", self)
        collab_dock.setAccessibleName("Collaboration panel dock")
        collab_dock.setWidget(self.collab_ui)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, collab_dock)

        # --- Comments ---
        comments_widget = QWidget()
        comments_layout = QVBoxLayout(comments_widget)
        comments_layout.setContentsMargins(4, 4, 4, 4)
        self.comments_tree = QTreeWidget()
        self.comments_tree.setHeaderLabels(["Line", "Author", "Comment"])
        self.comments_tree.setAccessibleName("Comments list")
        self.comments_tree.setToolTip("Inline annotations on the active artefact.")
        add_comment_btn = QPushButton("Add Comment…")
        add_comment_btn.setToolTip("Add an annotation to the active artefact")
        add_comment_btn.setAccessibleName("Add comment button")
        add_comment_btn.clicked.connect(self.add_comment)
        comments_layout.addWidget(self.comments_tree)
        comments_layout.addWidget(add_comment_btn)
        comments_dock = QDockWidget("Comments", self)
        comments_dock.setAccessibleName("Comments dock")
        comments_dock.setWidget(comments_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, comments_dock)
        self.tabifyDockWidget(collab_dock, comments_dock)

        # --- Traceability ---
        trace_widget = QWidget()
        trace_layout = QVBoxLayout(trace_widget)
        trace_layout.setContentsMargins(4, 4, 4, 4)
        self.trace_tree = QTreeWidget()
        self.trace_tree.setHeaderLabels(["Design Artefact", "Design Element", "Code Artefact", "Code Element", "Description"])
        self.trace_tree.setAccessibleName("Traceability links list")
        self.trace_tree.setToolTip("Design-to-code traceability links.")
        trace_btn_row = QWidget()
        trace_btn_layout = QHBoxLayout(trace_btn_row)
        trace_btn_layout.setContentsMargins(0, 0, 0, 0)
        add_link_btn = QPushButton("Add Link…")
        add_link_btn.setToolTip("Create a new traceability link")
        add_link_btn.setAccessibleName("Add trace link button")
        add_link_btn.clicked.connect(self.add_trace_link)
        remove_link_btn = QPushButton("Remove Link")
        remove_link_btn.setToolTip("Delete the selected traceability link")
        remove_link_btn.setAccessibleName("Remove trace link button")
        remove_link_btn.clicked.connect(self.remove_trace_link)
        trace_btn_layout.addWidget(add_link_btn)
        trace_btn_layout.addWidget(remove_link_btn)
        trace_layout.addWidget(self.trace_tree)
        trace_layout.addWidget(trace_btn_row)
        trace_dock = QDockWidget("Traceability", self)
        trace_dock.setAccessibleName("Traceability dock")
        trace_dock.setWidget(trace_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, trace_dock)
        self.tabifyDockWidget(comments_dock, trace_dock)

        collab_dock.raise_()

    def _create_bottom_dock(self) -> None:
        self.bottom_tabs = QTabWidget()
        self.bottom_tabs.setAccessibleName("Diagnostics and output panel tabs")

        # Diagnostics
        self.diagnostics_tree = QTreeWidget()
        self.diagnostics_tree.setHeaderLabels(["Severity", "Line", "Source", "Message"])
        self.diagnostics_tree.setAccessibleName("Diagnostics panel")
        self.diagnostics_tree.setToolTip("Static analysis and conformance diagnostics.")
        self.bottom_tabs.addTab(self.diagnostics_tree, "Diagnostics")

        # Test Results
        self.test_results_tree = QTreeWidget()
        self.test_results_tree.setHeaderLabels(["Test / Suite", "Status", "Duration (ms)", "Message"])
        self.test_results_tree.setAccessibleName("Test results panel")
        self.test_results_tree.setToolTip("Results from the most recent test run.")
        self.bottom_tabs.addTab(self.test_results_tree, "Test Results")

        # Search Results
        self.search_results_tree = QTreeWidget()
        self.search_results_tree.setHeaderLabels(["Artefact", "Line", "Col", "Context"])
        self.search_results_tree.setAccessibleName("Search results panel")
        self.search_results_tree.setToolTip("Results from the last project-wide search. Double-click to navigate.")
        self.search_results_tree.itemDoubleClicked.connect(self._navigate_to_search_result)
        self.bottom_tabs.addTab(self.search_results_tree, "Search Results")

        # Output
        self.output_view = QPlainTextEdit()
        self.output_view.setReadOnly(True)
        self.output_view.setAccessibleName("Output panel")
        self.output_view.setToolTip("Build, VCS, and other tool output.")
        self.bottom_tabs.addTab(self.output_view, "Output")

        bottom_dock = QDockWidget("Diagnostics / Output", self)
        bottom_dock.setAccessibleName("Bottom panel dock")
        bottom_dock.setWidget(self.bottom_tabs)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, bottom_dock)

    def _create_status_bar(self) -> None:
        sb = QStatusBar(self)
        self.setStatusBar(sb)

        self.sync_status_label = QLabel("Sync: idle")
        self.sync_status_label.setAccessibleName("Network synchronisation status indicator")
        self.sync_status_label.setToolTip(
            "Current collaboration sync status: idle / pending / syncing / conflict / error"
        )
        sb.addPermanentWidget(self.sync_status_label)

    # ------------------------------------------------------------------
    # File / project actions
    # ------------------------------------------------------------------

    def new_project(self) -> None:
        name, accepted = QInputDialog.getText(self, "New Project", "Project name:")
        if not accepted or not name.strip():
            return
        self.application.open_project(name.strip(), Path.cwd() / name.strip())
        self._clear_code_editors()
        self._refresh_project_selector()
        self._load_diagrams_for_active_project()
        self.refresh_project_explorer()
        self._refresh_trace_links()
        self.output_view.appendPlainText(f"Created project: {name.strip()}")

    def open_project(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Open Project Folder")
        if not path:
            return
        project_name = Path(path).name or "Opened Project"
        self.application.open_project(project_name, Path(path))
        self._clear_code_editors()
        self._refresh_project_selector()
        self._load_diagrams_for_active_project()
        self.refresh_project_explorer()
        self._refresh_trace_links()
        self.output_view.appendPlainText(f"Opened project: {project_name} ({path})")
        self.statusBar().showMessage(f"Project '{project_name}' loaded.")

    def open_file(self) -> None:
        root = ""
        if self.application.project_manager.active_project:
            root = str(self.application.project_manager.active_project.root_path)
        path, _ = QFileDialog.getOpenFileName(self, "Open File", root, "All Files (*.*)")
        if not path:
            return
        artifact = self.application.open_file(Path(path))
        if artifact is None:
            QMessageBox.warning(self, "Cannot Open", f"File type not supported or unreadable:\n{path}")
            return
        self.refresh_project_explorer()
        self.open_artifact(artifact)

    def save_active_artifact(self) -> None:
        # Design tab active — save all diagram types.
        if self.tabs.currentWidget() is self.diagram_canvas:
            self._save_diagrams()
            return

        # Code editor active — save the file.
        if self.active_editor is None:
            self.statusBar().showMessage("No active editor to save.")
            return
        artifact = self.active_editor.artifact
        self.application.artifact_store.save(artifact)
        session = self.application.session_manager.current_session
        author = session.display_name if session else "Local User"
        self.application.version_service.checkpoint(artifact, author)
        self.application.persist_project_state()
        label = str(artifact.path) if artifact.path else artifact.name
        self.statusBar().showMessage(f"Saved {label}  [checkpoint created]")

    def _close_active_tab(self) -> None:
        idx = self.tabs.currentIndex()
        if idx >= 0:
            self._on_tab_close_requested(idx)

    def run_build(self) -> None:
        project = self.application.project_manager.active_project
        if project is None:
            return
        result = self.application.build_service.run_build(project)
        self.output_view.appendPlainText(f"$ {result.command}\n{result.output}")
        self.statusBar().showMessage("Build stub completed.")

    def commit(self) -> None:
        project = self.application.project_manager.active_project
        if project is None:
            return
        result = self.application.vcs_service.commit(project, "Prototype checkpoint")
        self.output_view.appendPlainText(f"$ {result.command}\n{result.output}")
        self.statusBar().showMessage("VCS commit stub completed.")

    def about(self) -> None:
        QMessageBox.about(
            self,
            "About",
            "Architecture Driven Collaborative IDE\n\n"
            "Desktop shell prototype — Python language support, multi-type "
            "diagram canvas, test runner, project search, version history, "
            "design traceability, and collaboration presence.\n\n"
            "Press F1 for help topics.",
        )

    # ------------------------------------------------------------------
    # Run file
    # ------------------------------------------------------------------

    def run_active_file(self) -> None:
        """Save the active file then execute it with the system Python interpreter."""
        if self.active_editor is None:
            self.statusBar().showMessage("No active file to run.")
            return

        artifact = self.active_editor.artifact

        if artifact.path is None:
            self.statusBar().showMessage("Cannot run an in-memory artefact — save it to disk first.")
            return

        if artifact.path.suffix.lower() not in (".py", ".java"):
            self.statusBar().showMessage(
                f"Run File supports .py and .java files (active file is {artifact.path.suffix or 'unknown'})."
            )
            return

        # Auto-save before running so the interpreter sees the latest edits.
        self.application.artifact_store.save(artifact)

        project = self.application.project_manager.active_project
        cwd = project.root_path if project else artifact.path.parent

        self.statusBar().showMessage(f"Running {artifact.path.name}…")
        self.output_view.appendPlainText(f"\n{'─' * 60}")
        if artifact.path.suffix.lower() == ".java":
            self.output_view.appendPlainText(f"$ javac/java {artifact.path}")
        else:
            self.output_view.appendPlainText(f"$ python {artifact.path}")
        self.bottom_tabs.setCurrentWidget(self.output_view)

        if artifact.path.suffix.lower() == ".java":
            result = self.application.run_service.run_java_file(artifact.path, cwd=cwd)
        else:
            result = self.application.run_service.run_file(artifact.path, cwd=cwd)

        self.output_view.appendPlainText(result.output)
        self.output_view.appendPlainText(
            f"{'─' * 60}\nProcess exited with code {result.exit_code}"
        )

        if result.success:
            self.statusBar().showMessage(f"{artifact.path.name} finished (exit 0).")
        else:
            self.statusBar().showMessage(
                f"{artifact.path.name} exited with code {result.exit_code} — see Output panel."
            )

    # ------------------------------------------------------------------
    # Test runner
    # ------------------------------------------------------------------

    def run_tests(self) -> None:
        project = self.application.project_manager.active_project
        if project is None:
            self.statusBar().showMessage("No active project.")
            return
        artifacts = self.application.artifact_store.list_for_project(project)
        result = self.application.test_service.run_tests(project, artifacts)

        self.output_view.appendPlainText(f"$ {result.command}\n{result.summary}")
        self._render_test_results(result)
        self.bottom_tabs.setCurrentWidget(self.test_results_tree)

        # Feed results into dynamic analysis.
        dyn_result = self.application.analysis_manager.run_dynamic_analysis_from_tests(result)
        if dyn_result.diagnostics:
            self._last_diagnostics.extend(dyn_result.diagnostics)
            self._render_diagnostics(self._last_diagnostics)
            if self.active_editor:
                self.active_editor.render_diagnostics(self._last_diagnostics)
            self.output_view.appendPlainText(dyn_result.summary)

        icon = "✓" if result.success else "✗"
        self.statusBar().showMessage(
            f"{icon} Tests: {result.total_passed} passed, "
            f"{result.total_failed} failed, {result.total_errors} errors"
        )

    def _render_test_results(self, result) -> None:
        self.test_results_tree.clear()
        for suite in result.suites:
            suite_icon = "✓" if suite.failed == 0 and suite.errors == 0 else "✗"
            suite_item = QTreeWidgetItem([
                f"{suite_icon} {suite.name}",
                f"{suite.passed}P / {suite.failed}F / {suite.errors}E / {suite.skipped}S",
                "",
                "",
            ])
            self.test_results_tree.addTopLevelItem(suite_item)
            for case in suite.cases:
                status_icons = {
                    "passed": "✓", "failed": "✗", "error": "!", "skipped": "—",
                }
                icon = status_icons.get(case.status.value, "?")
                case_item = QTreeWidgetItem([
                    f"  {icon} {case.name}",
                    case.status.value,
                    f"{case.duration_ms:.1f}",
                    case.message,
                ])
                suite_item.addChild(case_item)
            suite_item.setExpanded(suite.failed > 0 or suite.errors > 0)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def show_search_bar(self) -> None:
        self.search_field.setFocus()
        self.search_field.selectAll()

    def show_code_completion(self) -> None:
        if self.active_editor is None:
            self.statusBar().showMessage("No active editor for code completion.")
            return
        candidates = self.active_editor.completion_candidates()
        if not candidates:
            self.statusBar().showMessage("No completion candidates available.")
            return
        completion, accepted = QInputDialog.getItem(
            self,
            "Code Completion",
            "Insert completion:",
            candidates,
            0,
            False,
        )
        if accepted and completion:
            self.active_editor.insert_completion(completion)
            self.statusBar().showMessage(f"Inserted completion: {completion}")

    def _execute_search(self) -> None:
        query = self.search_field.text().strip()
        if not query:
            return
        project = self.application.project_manager.active_project
        if project is None:
            return
        artifacts = self._searchable_artifacts()
        results = self.application.search_service.search(query, artifacts)

        self.search_results_tree.clear()
        for r in results:
            self.search_results_tree.addTopLevelItem(
                QTreeWidgetItem([
                    r.artifact_name,
                    str(r.line),
                    str(r.column),
                    r.context,
                ])
            )
            # Store artifact_id + line for navigation.
            item = self.search_results_tree.topLevelItem(
                self.search_results_tree.topLevelItemCount() - 1
            )
            if r.artifact_id.startswith("design:"):
                item.setData(
                    0,
                    Qt.ItemDataRole.UserRole,
                    ("diagram", r.artifact_id.removeprefix("design:"), r.line),
                )
            else:
                item.setData(0, Qt.ItemDataRole.UserRole, ("artifact", r.artifact_id, r.line))

        self.bottom_tabs.setCurrentWidget(self.search_results_tree)
        self.statusBar().showMessage(
            f"Search '{query}': {len(results)} match(es) across {len(artifacts)} artefact(s)."
        )

    def _searchable_artifacts(self) -> list[Artifact]:
        project = self.application.project_manager.active_project
        if project is None:
            return []
        artifacts = self.application.artifact_store.list_for_project(project)
        design_artifacts = [
            Artifact(
                name=f"{diagram_type} diagram",
                artifact_type=ArtifactType.DESIGN,
                language="plain",
                content=self.diagram_canvas.get_content(diagram_type),
                artifact_id=f"design:{diagram_type}",
            )
            for diagram_type in self.diagram_canvas.diagram_types()
        ]
        return artifacts + design_artifacts

    def _navigate_to_search_result(self, item: QTreeWidgetItem) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data is None:
            return
        if len(data) == 2:
            kind, target, line = "artifact", data[0], data[1]
        else:
            kind, target, line = data
        if kind == "diagram":
            self.tabs.setCurrentWidget(self.diagram_canvas)
            self.diagram_canvas.set_current_diagram(str(target))
            editor = self.diagram_canvas.get_editor(str(target))
            if editor is not None:
                block = editor.document().findBlockByLineNumber(max(0, int(line) - 1))
                cursor = editor.textCursor()
                cursor.setPosition(block.position())
                editor.setTextCursor(cursor)
                editor.ensureCursorVisible()
            return
        artifact_id = str(target)
        artifact = self.application.artifact_store.load(artifact_id)
        if artifact is None:
            return
        self.open_artifact(artifact)
        # Scroll to line in the editor.
        if self.active_editor:
            block = self.active_editor.editor.document().findBlockByLineNumber(max(0, line - 1))
            cursor = self.active_editor.editor.textCursor()
            cursor.setPosition(block.position())
            self.active_editor.editor.setTextCursor(cursor)
            self.active_editor.editor.ensureCursorVisible()

    # ------------------------------------------------------------------
    # Help
    # ------------------------------------------------------------------

    def show_help_topics(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Help Topics")
        dialog.setMinimumSize(640, 480)
        dialog.setAccessibleName("Help topics dialog")
        layout = QHBoxLayout(dialog)

        topic_list = QTreeWidget()
        topic_list.setHeaderLabels(["Topic"])
        topic_list.setMaximumWidth(200)
        topic_list.setAccessibleName("Help topic list")
        content_view = QPlainTextEdit()
        content_view.setReadOnly(True)
        content_view.setAccessibleName("Help topic content")
        layout.addWidget(topic_list)
        layout.addWidget(content_view)

        topics = self.application.help_service.all_topics()
        for topic in topics:
            item = QTreeWidgetItem([topic.title])
            item.setData(0, Qt.ItemDataRole.UserRole, topic.topic_id)
            topic_list.addTopLevelItem(item)

        def _show_topic(item: QTreeWidgetItem) -> None:
            tid = item.data(0, Qt.ItemDataRole.UserRole)
            t = self.application.help_service.get_topic(tid)
            if t:
                content_view.setPlainText(f"{t.title}\n{'=' * len(t.title)}\n\n{t.content}")

        topic_list.itemClicked.connect(_show_topic)
        if topic_list.topLevelItemCount() > 0:
            topic_list.setCurrentItem(topic_list.topLevelItem(0))
            _show_topic(topic_list.topLevelItem(0))

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        bottom = QHBoxLayout()
        bottom.addStretch()
        bottom.addWidget(close_btn)
        outer = QVBoxLayout()
        outer.addLayout(layout)
        outer.addLayout(bottom)
        dialog.setLayout(outer)
        dialog.exec()

    def show_contextual_help(self) -> None:
        context = "overview"
        if self.active_editor:
            context = "editor"
        elif self.tabs.currentWidget() is self.diagram_canvas:
            context = "diagrams"
        topic = self.application.help_service.get_contextual_help(context)
        QMessageBox.information(
            self,
            f"Help — {topic.title}",
            topic.content,
        )

    # ------------------------------------------------------------------
    # Version history
    # ------------------------------------------------------------------

    def show_version_history(self) -> None:
        if self.active_editor is None:
            self.statusBar().showMessage("No active file to show history for.")
            return
        artifact = self.active_editor.artifact
        revisions = self.application.version_service.get_history(artifact.artifact_id)

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Version History — {artifact.name}")
        dialog.setMinimumSize(700, 400)
        dialog.setAccessibleName("Version history dialog")
        layout = QVBoxLayout(dialog)

        table = QTableWidget(len(revisions), 4)
        table.setHorizontalHeaderLabels(["#", "Author", "Timestamp", "Message"])
        table.setAccessibleName("Version history table")
        table.setToolTip("Select a revision and click Restore to revert the file.")
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.horizontalHeader().setStretchLastSection(True)

        for i, rev in enumerate(revisions):
            table.setItem(i, 0, QTableWidgetItem(rev.revision_id[:8]))
            table.setItem(i, 1, QTableWidgetItem(rev.author))
            table.setItem(i, 2, QTableWidgetItem(rev.timestamp.strftime("%Y-%m-%d %H:%M:%S")))
            table.setItem(i, 3, QTableWidgetItem(rev.message))
            for col in range(4):
                if item := table.item(i, col):
                    item.setData(Qt.ItemDataRole.UserRole, rev.revision_id)

        layout.addWidget(QLabel(f"{len(revisions)} checkpoint(s) for {artifact.name}"))
        layout.addWidget(table)

        btn_row = QHBoxLayout()
        restore_btn = QPushButton("Restore Selected")
        restore_btn.setToolTip("Restore the active file to the selected revision")
        restore_btn.setAccessibleName("Restore revision button")
        close_btn = QPushButton("Close")
        btn_row.addWidget(restore_btn)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        def _restore() -> None:
            rows = table.selectionModel().selectedRows()
            if not rows:
                return
            rev_id = table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)
            rev = next((r for r in revisions if r.revision_id == rev_id), None)
            if rev and self.active_editor:
                self.active_editor.artifact.content = rev.content
                self.active_editor.editor.setPlainText(rev.content)
                self.statusBar().showMessage(f"Restored {artifact.name} to revision {rev_id[:8]}.")
            dialog.accept()

        restore_btn.clicked.connect(_restore)
        close_btn.clicked.connect(dialog.accept)
        dialog.exec()

    # ------------------------------------------------------------------
    # Comments
    # ------------------------------------------------------------------

    def add_comment(self) -> None:
        if self.active_editor is None:
            self.statusBar().showMessage("No active artefact to comment on.")
            return
        artifact = self.active_editor.artifact
        session = self.application.session_manager.current_session
        author = session.display_name if session else "Anonymous"
        dlg = _AddCommentDialog(self, artifact.name, author)
        if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.body:
            return
        comment = Comment(
            artifact_id=artifact.artifact_id,
            line=dlg.line_number,
            author=author,
            body=dlg.body,
        )
        self.application.comment_service.add_comment(comment)
        self.application.persist_project_state()
        self._refresh_comments(artifact.artifact_id)
        self.statusBar().showMessage(f"Comment added to {artifact.name}:{dlg.line_number}.")

    def _refresh_comments(self, artifact_id: str) -> None:
        self.comments_tree.clear()
        for comment in self.application.comment_service.get_comments(artifact_id):
            item = QTreeWidgetItem([
                str(comment.line),
                comment.author,
                comment.body,
            ])
            item.setData(0, Qt.ItemDataRole.UserRole, comment.comment_id)
            self.comments_tree.addTopLevelItem(item)

    # ------------------------------------------------------------------
    # Traceability
    # ------------------------------------------------------------------

    def add_trace_link(self) -> None:
        project = self.application.project_manager.active_project
        artifact_names: list[str] = []
        if project:
            artifact_names = [
                a.name
                for a in self.application.artifact_store.list_for_project(project)
            ]
        dlg = _AddTraceLinkDialog(self, artifact_names)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        link = TraceLink(
            design_artifact_id=dlg.design_artifact.text(),
            design_element=dlg.design_element.text(),
            code_artifact_id=dlg.code_artifact.text(),
            code_element=dlg.code_element.text(),
            description=dlg.description.text(),
        )
        self.application.traceability_service.add_link(link)
        self.application.persist_project_state()
        self._refresh_trace_links()
        self.statusBar().showMessage("Trace link added.")

    def remove_trace_link(self) -> None:
        selected = self.trace_tree.selectedItems()
        if not selected:
            return
        link_id = selected[0].data(0, Qt.ItemDataRole.UserRole)
        if link_id and self.application.traceability_service.remove_link(link_id):
            self.application.persist_project_state()
            self._refresh_trace_links()
            self.statusBar().showMessage("Trace link removed.")

    def _refresh_trace_links(self) -> None:
        self.trace_tree.clear()
        for link in self.application.traceability_service.get_all():
            item = QTreeWidgetItem([
                link.design_artifact_id,
                link.design_element,
                link.code_artifact_id,
                link.code_element,
                link.description,
            ])
            item.setData(0, Qt.ItemDataRole.UserRole, link.link_id)
            self.trace_tree.addTopLevelItem(item)

    # ------------------------------------------------------------------
    # Project switching
    # ------------------------------------------------------------------

    def _refresh_project_selector(self) -> None:
        self._project_selector_updating = True
        self.project_selector.clear()
        active = self.application.project_manager.active_project
        active_index = -1
        for index, project in enumerate(self.application.project_manager.projects.values()):
            self.project_selector.addItem(project.name, project.project_id)
            if active is not None and project.project_id == active.project_id:
                active_index = index
        if active_index >= 0:
            self.project_selector.setCurrentIndex(active_index)
        self._project_selector_updating = False

    def _on_project_selected(self, index: int) -> None:
        if self._project_selector_updating or index < 0:
            return
        project_id = self.project_selector.itemData(index)
        active = self.application.project_manager.active_project
        if not project_id or (active is not None and project_id == active.project_id):
            return
        self.application.switch_project(str(project_id))
        self._clear_code_editors()
        self._load_diagrams_for_active_project()
        self.refresh_project_explorer()
        self._refresh_trace_links()
        project = self.application.project_manager.active_project
        if project is not None:
            self.output_view.appendPlainText(f"Switched project: {project.name}")
            self.statusBar().showMessage(f"Project '{project.name}' active.")

    # ------------------------------------------------------------------
    # Project explorer
    # ------------------------------------------------------------------

    def refresh_project_explorer(self) -> None:
        self.project_tree.clear()
        project = self.application.project_manager.active_project
        if project is None:
            return

        root_item = QTreeWidgetItem([project.name])
        self.project_tree.addTopLevelItem(root_item)

        artifacts = self.application.artifact_store.list_for_project(project)
        dir_items: dict[str, QTreeWidgetItem] = {}

        for artifact in artifacts:
            if artifact.path is not None:
                try:
                    rel = artifact.path.relative_to(project.root_path)
                    parts = rel.parts
                except ValueError:
                    parts = (artifact.name,)
            else:
                parts = (artifact.name,)

            parent = root_item
            for depth, part in enumerate(parts[:-1]):
                dir_key = "/".join(parts[: depth + 1])
                if dir_key not in dir_items:
                    dir_node = QTreeWidgetItem([part])
                    parent.addChild(dir_node)
                    dir_items[dir_key] = dir_node
                parent = dir_items[dir_key]

            file_item = QTreeWidgetItem([parts[-1]])
            file_item.setData(0, Qt.ItemDataRole.UserRole, artifact.artifact_id)
            file_item.setToolTip(0, str(artifact.path or artifact.name))
            parent.addChild(file_item)

        root_item.setExpanded(True)

    # ------------------------------------------------------------------
    # Tab and editor management
    # ------------------------------------------------------------------

    def _on_tab_changed(self, index: int) -> None:
        widget = self.tabs.widget(index)
        if isinstance(widget, EditorView):
            self.active_editor = widget
            # Update presence and refresh sidebar panels.
            self.application.collab_service.update_local_presence(
                widget.artifact.artifact_id, widget.artifact.name
            )
            self.collab_ui.set_peers(self.application.collab_service.peers)
            self._refresh_comments(widget.artifact.artifact_id)
        else:
            self.active_editor = None

    def _on_tab_close_requested(self, index: int) -> None:
        widget = self.tabs.widget(index)
        if isinstance(widget, DiagramCanvas):
            return
        self.tabs.removeTab(index)
        if isinstance(widget, EditorView):
            if self.active_editor is widget:
                self.active_editor = None
            widget.deleteLater()

    def _open_tree_item(self, item: QTreeWidgetItem) -> None:
        artifact_id = item.data(0, Qt.ItemDataRole.UserRole)
        if artifact_id:
            artifact = self.application.artifact_store.load(str(artifact_id))
            if artifact is not None:
                self.open_artifact(artifact)

    def open_artifact(self, artifact: Artifact) -> None:
        # Switch to an already-open tab rather than duplicating it.
        existing = self._find_editor_tab(artifact.artifact_id)
        if existing is not None:
            self.tabs.setCurrentWidget(existing)
            self.active_editor = existing
            return

        language_service = self.application.language_services.get(artifact.language or "plain")
        if language_service is None:
            language_service = self.application.language_services.get("plain")
        if language_service is None:
            QMessageBox.warning(self, "Missing Language Service", f"No language service for '{artifact.language}'.")
            return

        session = self.application.session_manager.current_session
        if session is None:
            session = self.application.session_manager.sign_in_guest()

        editor = EditorView(
            artifact=artifact,
            language_service=language_service,
            session=session,
            on_operation=self._handle_editor_operation,
        )
        index = self.tabs.addTab(editor, artifact.name)
        self.tabs.setCurrentIndex(index)
        self.active_editor = editor
        if self._last_diagnostics:
            editor.render_diagnostics(self._last_diagnostics)

    def _find_editor_tab(self, artifact_id: str) -> EditorView | None:
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if isinstance(widget, EditorView) and widget.artifact.artifact_id == artifact_id:
                return widget
        return None

    def _handle_editor_operation(self, operation: Operation, artifact: Artifact) -> None:
        self.application.collab_service.submit_op(operation)
        self.application.artifact_store.save(artifact)
        self.collab_ui.log_event(f"Local edit: {artifact.name}")
        self.analysis_timer.start(400)

    # ------------------------------------------------------------------
    # Analysis and diagnostics
    # ------------------------------------------------------------------

    def _run_static_analysis(self, add_output: bool) -> None:
        project = self.application.project_manager.active_project
        if project is None:
            return
        artifacts = self.application.artifact_store.list_for_project(project)
        result = self.application.analysis_manager.run_static_analysis(artifacts)
        conformance = self.application.analysis_manager.run_conformance_check(result.snapshot)
        diagnostics = result.diagnostics + conformance.diagnostics
        self._last_diagnostics = diagnostics
        self._render_diagnostics(diagnostics)
        if self.active_editor is not None:
            self.active_editor.render_diagnostics(diagnostics)
        if add_output:
            self.output_view.appendPlainText(f"{result.summary}\n{conformance.summary}")
        self.statusBar().showMessage(f"Analysis: {len(diagnostics)} diagnostic(s).")

    def _render_diagnostics(self, diagnostics: list[Diagnostic]) -> None:
        self.diagnostics_tree.clear()
        for diagnostic in diagnostics:
            artifact_label = "project"
            if diagnostic.artifact_id:
                artifact = self.application.artifact_store.load(diagnostic.artifact_id)
                artifact_label = artifact.name if artifact is not None else diagnostic.artifact_id[:8]
            self.diagnostics_tree.addTopLevelItem(
                QTreeWidgetItem([
                    diagnostic.severity.value,
                    str(diagnostic.line),
                    f"{diagnostic.source} / {artifact_label}",
                    diagnostic.message,
                ])
            )

    # ------------------------------------------------------------------
    # Sync status
    # ------------------------------------------------------------------

    def _on_sync_status_changed(self, status: SyncStatus) -> None:
        labels = {
            SyncStatus.IDLE: "Sync: idle",
            SyncStatus.PENDING: "Sync: pending…",
            SyncStatus.SYNCING: "Sync: syncing…",
            SyncStatus.CONFLICT: "Sync: CONFLICT",
            SyncStatus.ERROR: "Sync: ERROR",
        }
        self.sync_status_label.setText(labels.get(status, f"Sync: {status.value}"))
        if status is SyncStatus.CONFLICT:
            self.sync_status_label.setStyleSheet("color: red; font-weight: bold;")
        elif status is SyncStatus.ERROR:
            self.sync_status_label.setStyleSheet("color: darkred; font-weight: bold;")
        else:
            self.sync_status_label.setStyleSheet("")

    # ------------------------------------------------------------------
    # Design artefact persistence
    # ------------------------------------------------------------------

    def _load_diagrams_for_active_project(self) -> None:
        """Populate the diagram canvas from .bscode/design/ for the active project."""
        self.diagram_canvas.reset_to_templates()
        saved = self.application.load_diagrams()
        if saved:
            self.diagram_canvas.load_saved_content(saved)

    def _save_diagrams(self) -> None:
        """Write all five diagram types to .bscode/design/ for the active project."""
        from ide.infrastructure.bscode_store import DIAGRAM_TYPES
        for diagram_type in DIAGRAM_TYPES:
            self.application.save_diagram(diagram_type, self.diagram_canvas.get_content(diagram_type))
        self.statusBar().showMessage(f"Design diagrams saved to .bscode/design/  ({len(DIAGRAM_TYPES)} files)")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _clear_code_editors(self) -> None:
        for index in reversed(range(self.tabs.count())):
            widget = self.tabs.widget(index)
            if isinstance(widget, EditorView):
                self.tabs.removeTab(index)
                widget.deleteLater()
        self.active_editor = None
