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
    QStatusBar,
    QTabWidget,
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



class _AddCommentDialog(QDialog):
    def __init__(self, parent: QWidget, artifact_name: str, author: str) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Add Comment - {artifact_name}")
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.line_edit = QLineEdit("1")
        self.line_edit.setAccessibleName("Line number input")
        self.body_edit = QPlainTextEdit()
        self.body_edit.setAccessibleName("Comment body input")
        self.body_edit.setPlaceholderText("Enter your comment...")
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



class IDEShell(QMainWindow):
    def __init__(self, application: IDEApplication) -> None:
        super().__init__()
        self.application = application
        self.active_editor: EditorView | None = None
        self._last_diagnostics: list[Diagnostic] = []
        self._project_selector_updating = False
        self._last_file_snapshot: set[str] = set()

        self.setWindowTitle("Architecture Driven Collaborative IDE")
        self.resize(1400, 900)
        self.setAccessibleName("Architecture Driven Collaborative IDE main window")

        self.analysis_timer = QTimer(self)
        self.analysis_timer.setSingleShot(True)
        self.analysis_timer.timeout.connect(lambda: self._run_static_analysis(add_output=False))

        self.filesystem_timer = QTimer(self)
        self.filesystem_timer.timeout.connect(self._refresh_project_if_changed)

        self._build_ui()
        self._apply_initial_layout()

        self.application.network_sync.add_status_listener(self._on_sync_status_changed)
        self.filesystem_timer.start(2500)

        self.statusBar().showMessage("Desktop IDE shell ready. Press F1 for help.")
        self._refresh_project_selector()
        self.refresh_project_explorer()
        self._load_diagrams_for_active_project()


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
        self.close_tab_action = QAction("Close Tab", self)
        self.close_tab_action.setShortcut(QKeySequence("Ctrl+W"))
        self.close_tab_action.setToolTip("Close the current editor tab (Ctrl+W)")
        self.close_tab_action.triggered.connect(self._close_active_tab)

        self.refresh_project_action = QAction("Refresh Explorer", self)
        self.refresh_project_action.triggered.connect(self.refresh_project_from_disk)

        self.find_in_project_action = QAction("Find in Project...", self)
        self.find_in_project_action.setShortcut(QKeySequence("Ctrl+Shift+F"))
        self.find_in_project_action.setToolTip("Search all artefacts in the project (Ctrl+Shift+F)")
        self.find_in_project_action.triggered.connect(self.show_search_bar)

        self.complete_action = QAction("Code Completion", self)
        self.complete_action.setShortcut(QKeySequence("Ctrl+Space"))
        self.complete_action.setToolTip("Show the completion popup scaffold (Ctrl+Space)")
        self.complete_action.triggered.connect(self.show_code_completion)

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

        self.debug_start_action = QAction("Start Debugging", self)
        self.debug_start_action.setShortcut(QKeySequence("F9"))
        self.debug_start_action.setToolTip("Debugger UI skeleton; runtime debugging is not implemented")
        self.debug_start_action.triggered.connect(self.start_debugging)

        self.debug_step_action = QAction("Step", self)
        self.debug_step_action.setShortcut(QKeySequence("F10"))
        self.debug_step_action.setToolTip("Debugger UI skeleton; stepping is not implemented")
        self.debug_step_action.triggered.connect(self.debug_step)

        self.debug_continue_action = QAction("Continue", self)
        self.debug_continue_action.setShortcut(QKeySequence("F11"))
        self.debug_continue_action.setToolTip("Debugger UI skeleton; continue is not implemented")
        self.debug_continue_action.triggered.connect(self.debug_continue)

        self.debug_stop_action = QAction("Stop Debugging", self)
        self.debug_stop_action.setToolTip("Debugger UI skeleton; stop is not implemented")
        self.debug_stop_action.triggered.connect(self.debug_stop)

        self.static_analysis_action = QAction("Run Static Analysis", self)
        self.static_analysis_action.setShortcut(QKeySequence("Ctrl+Shift+A"))
        self.static_analysis_action.setToolTip("Run static analysis on all project artefacts (Ctrl+Shift+A)")
        self.static_analysis_action.triggered.connect(
            lambda: self._run_static_analysis(add_output=True)
        )

        self.show_project_explorer_action = QAction("Project Explorer", self)
        self.show_project_explorer_action.setCheckable(True)
        self.show_project_explorer_action.setChecked(True)

        self.show_collaboration_action = QAction("Collaboration", self)
        self.show_collaboration_action.setCheckable(True)
        self.show_collaboration_action.setChecked(True)

        self.show_comments_action = QAction("Comments", self)
        self.show_comments_action.setCheckable(True)
        self.show_comments_action.setChecked(True)

        self.show_traceability_action = QAction("Traceability", self)
        self.show_traceability_action.setCheckable(True)
        self.show_traceability_action.setChecked(True)

        self.show_bottom_panel_action = QAction("Diagnostics / Output", self)
        self.show_bottom_panel_action.setCheckable(True)
        self.show_bottom_panel_action.setChecked(True)

        self.git_status_action = QAction("Status", self)
        self.git_status_action.triggered.connect(self.git_status)

        self.git_diff_action = QAction("Diff", self)
        self.git_diff_action.triggered.connect(self.git_diff)

        self.git_log_action = QAction("Log", self)
        self.git_log_action.triggered.connect(self.git_log)

        self.git_branches_action = QAction("Branches", self)
        self.git_branches_action.triggered.connect(self.git_branches)

        self.git_add_action = QAction("Add / Stage...", self)
        self.git_add_action.triggered.connect(self.git_add)

        self.commit_action = QAction("Commit", self)
        self.commit_action.setToolTip("Commit current changes via the VCS service")
        self.commit_action.triggered.connect(self.commit)

        self.git_pull_action = QAction("Pull", self)
        self.git_pull_action.triggered.connect(self.git_pull)

        self.git_push_action = QAction("Push", self)
        self.git_push_action.triggered.connect(self.git_push)

        self.git_merge_action = QAction("Merge Branch...", self)
        self.git_merge_action.triggered.connect(self.git_merge)

        self.help_topics_action = QAction("Help Topics...", self)
        self.help_topics_action.setShortcut(QKeySequence("F1"))
        self.help_topics_action.setToolTip("Open the help topics browser (F1)")
        self.help_topics_action.triggered.connect(self.show_help_topics)

        self.contextual_help_action = QAction("Contextual Help", self)
        self.contextual_help_action.setToolTip("Show help for the currently active panel")
        self.contextual_help_action.triggered.connect(self.show_contextual_help)

        self.about_action = QAction("About", self)
        self.about_action.triggered.connect(self.about)

    def _create_menu_bar(self) -> None:
        self.menuBar().setNativeMenuBar(False)
        file_menu = self.menuBar().addMenu("&File")
        file_menu.setAccessibleName("File menu")
        file_menu.addAction(self.refresh_project_action)
        file_menu.addSeparator()
        file_menu.addAction(self.close_tab_action)

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
        run_menu.addSeparator()
        run_menu.addAction(self.debug_start_action)
        run_menu.addAction(self.debug_step_action)
        run_menu.addAction(self.debug_continue_action)
        run_menu.addAction(self.debug_stop_action)

        analyse_menu = self.menuBar().addMenu("&Analyse")
        analyse_menu.setAccessibleName("Analyse menu")
        analyse_menu.addAction(self.static_analysis_action)

        view_menu = self.menuBar().addMenu("&View")
        view_menu.setAccessibleName("View menu")
        view_menu.addAction(self.show_project_explorer_action)
        view_menu.addAction(self.show_collaboration_action)
        view_menu.addAction(self.show_comments_action)
        view_menu.addAction(self.show_traceability_action)
        view_menu.addSeparator()
        view_menu.addAction(self.show_bottom_panel_action)

        vcs_menu = self.menuBar().addMenu("&VCS")
        vcs_menu.setAccessibleName("VCS menu")
        vcs_menu.addAction(self.git_status_action)
        vcs_menu.addAction(self.git_diff_action)
        vcs_menu.addAction(self.git_log_action)
        vcs_menu.addAction(self.git_branches_action)
        vcs_menu.addSeparator()
        vcs_menu.addAction(self.git_add_action)
        vcs_menu.addAction(self.commit_action)
        vcs_menu.addAction(self.git_pull_action)
        vcs_menu.addAction(self.git_push_action)
        vcs_menu.addAction(self.git_merge_action)

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

        search_label = QLabel("  Find: ")
        search_label.setAccessibleName("Project search label")
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Search project...")
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
        # The Design tab is permanent.
        self.tabs.tabBar().setTabButton(0, self.tabs.tabBar().ButtonPosition.RightSide, None)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.tabs.tabCloseRequested.connect(self._on_tab_close_requested)
        self.setCentralWidget(self.tabs)

    def _create_left_dock(self) -> None:
        self.project_tree = QTreeWidget()
        self.project_tree.setHeaderLabels(["Project Explorer"])
        self.project_tree.setHeaderHidden(True)
        self.project_tree.setAccessibleName("Project Explorer tree")
        self.project_tree.setToolTip("Double-click a file to open it in the editor.")
        self.project_tree.itemDoubleClicked.connect(self._open_tree_item)
        self.project_dock = QDockWidget("Project Explorer", self)
        self.project_dock.setAccessibleName("Project Explorer dock")
        self.project_dock.setObjectName("ProjectExplorerDock")
        self.project_dock.setWidget(self.project_tree)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.project_dock)
        self.show_project_explorer_action.triggered.connect(self.project_dock.setVisible)
        self.project_dock.visibilityChanged.connect(self.show_project_explorer_action.setChecked)

    def _create_right_docks(self) -> None:
        self.collab_ui = CollabUI()
        self.collab_ui.set_peers(self.application.collab_service.peers)
        self.collab_dock = QDockWidget("Collaboration", self)
        self.collab_dock.setAccessibleName("Collaboration panel dock")
        self.collab_dock.setObjectName("CollaborationDock")
        self.collab_dock.setWidget(self.collab_ui)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.collab_dock)
        self.show_collaboration_action.triggered.connect(self.collab_dock.setVisible)
        self.collab_dock.visibilityChanged.connect(self.show_collaboration_action.setChecked)

        comments_widget = QWidget()
        comments_layout = QVBoxLayout(comments_widget)
        comments_layout.setContentsMargins(4, 4, 4, 4)
        self.comments_tree = QTreeWidget()
        self.comments_tree.setHeaderLabels(["Line", "Author", "Comment"])
        self.comments_tree.setAccessibleName("Comments list")
        self.comments_tree.setToolTip("Inline annotations on the active artefact.")
        add_comment_btn = QPushButton("Add Comment...")
        add_comment_btn.setToolTip("Add an annotation to the active artefact")
        add_comment_btn.setAccessibleName("Add comment button")
        add_comment_btn.clicked.connect(self.add_comment)
        comments_layout.addWidget(self.comments_tree)
        comments_layout.addWidget(add_comment_btn)
        self.comments_dock = QDockWidget("Comments", self)
        self.comments_dock.setAccessibleName("Comments dock")
        self.comments_dock.setObjectName("CommentsDock")
        self.comments_dock.setWidget(comments_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.comments_dock)
        self.show_comments_action.triggered.connect(self.comments_dock.setVisible)
        self.comments_dock.visibilityChanged.connect(self.show_comments_action.setChecked)
        self.tabifyDockWidget(self.collab_dock, self.comments_dock)

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
        add_link_btn = QPushButton("Add Link...")
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
        self.trace_dock = QDockWidget("Traceability", self)
        self.trace_dock.setAccessibleName("Traceability dock")
        self.trace_dock.setObjectName("TraceabilityDock")
        self.trace_dock.setWidget(trace_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.trace_dock)
        self.show_traceability_action.triggered.connect(self.trace_dock.setVisible)
        self.trace_dock.visibilityChanged.connect(self.show_traceability_action.setChecked)
        self.tabifyDockWidget(self.comments_dock, self.trace_dock)

        self.collab_dock.raise_()

    def _create_bottom_dock(self) -> None:
        self.bottom_tabs = QTabWidget()
        self.bottom_tabs.setAccessibleName("Diagnostics and output panel tabs")

        self.diagnostics_tree = QTreeWidget()
        self.diagnostics_tree.setHeaderLabels(["Severity", "Line", "Source", "Message"])
        self.diagnostics_tree.setAccessibleName("Diagnostics panel")
        self.diagnostics_tree.setToolTip("Static analysis and conformance diagnostics.")
        self.bottom_tabs.addTab(self.diagnostics_tree, "Diagnostics")

        self.test_results_tree = QTreeWidget()
        self.test_results_tree.setHeaderLabels(["Test / Suite", "Status", "Duration (ms)", "Message"])
        self.test_results_tree.setAccessibleName("Test results panel")
        self.test_results_tree.setToolTip("Results from the most recent test run.")
        self.bottom_tabs.addTab(self.test_results_tree, "Test Results")

        self.search_results_tree = QTreeWidget()
        self.search_results_tree.setHeaderLabels(["Artefact", "Line", "Col", "Context"])
        self.search_results_tree.setAccessibleName("Search results panel")
        self.search_results_tree.setToolTip("Results from the last project-wide search. Double-click to navigate.")
        self.search_results_tree.itemDoubleClicked.connect(self._navigate_to_search_result)
        self.bottom_tabs.addTab(self.search_results_tree, "Search Results")

        self.output_view = QPlainTextEdit()
        self.output_view.setReadOnly(True)
        self.output_view.setAccessibleName("Output panel")
        self.output_view.setToolTip("Build, VCS, and other tool output.")
        self.bottom_tabs.addTab(self.output_view, "Output")

        debug_widget = QWidget()
        debug_layout = QVBoxLayout(debug_widget)
        debug_layout.setContentsMargins(4, 4, 4, 4)
        debug_controls = QWidget()
        debug_controls_layout = QHBoxLayout(debug_controls)
        debug_controls_layout.setContentsMargins(0, 0, 0, 0)
        debug_controls_layout.addWidget(QLabel("Breakpoints:"))
        self.breakpoint_field = QLineEdit()
        self.breakpoint_field.setPlaceholderText("e.g. 3, 8, 14")
        self.breakpoint_field.setAccessibleName("Debugger breakpoint line input")
        self.breakpoint_field.setToolTip("Comma-separated line numbers for the active Python file.")
        debug_controls_layout.addWidget(self.breakpoint_field)
        for action in (
            self.debug_start_action,
            self.debug_step_action,
            self.debug_continue_action,
            self.debug_stop_action,
        ):
            debug_button = QPushButton(action.text())
            debug_button.setToolTip(action.toolTip())
            debug_button.setAccessibleName(f"Debugger {action.text()} button")
            debug_button.clicked.connect(action.trigger)
            debug_controls_layout.addWidget(debug_button)
        debug_layout.addWidget(debug_controls)

        self.debug_stack_tree = QTreeWidget()
        self.debug_stack_tree.setHeaderLabels(["Function", "Line", "File"])
        self.debug_stack_tree.setAccessibleName("Debugger stack view")
        debug_layout.addWidget(self.debug_stack_tree)

        self.debug_variables_tree = QTreeWidget()
        self.debug_variables_tree.setHeaderLabels(["Variable", "Value"])
        self.debug_variables_tree.setAccessibleName("Debugger variables view")
        debug_layout.addWidget(self.debug_variables_tree)

        self.debug_output_view = QPlainTextEdit()
        self.debug_output_view.setReadOnly(True)
        self.debug_output_view.setAccessibleName("Debugger output view")
        debug_layout.addWidget(self.debug_output_view)
        self.bottom_tabs.addTab(debug_widget, "Debugger")

        self.bottom_dock = QDockWidget("Diagnostics / Output", self)
        self.bottom_dock.setAccessibleName("Bottom panel dock")
        self.bottom_dock.setObjectName("DiagnosticsOutputDock")
        self.bottom_dock.setWidget(self.bottom_tabs)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.bottom_dock)
        self.show_bottom_panel_action.triggered.connect(self.bottom_dock.setVisible)
        self.bottom_dock.visibilityChanged.connect(self.show_bottom_panel_action.setChecked)

    def _create_status_bar(self) -> None:
        status_bar = QStatusBar(self)
        self.setStatusBar(status_bar)

        self.sync_status_label = QLabel("Sync: idle")
        self.sync_status_label.setAccessibleName("Network synchronisation status indicator")
        self.sync_status_label.setToolTip(
            "Current collaboration sync status: idle / pending / syncing / conflict / error"
        )
        status_bar.addPermanentWidget(self.sync_status_label)

    def _apply_initial_layout(self) -> None:
        """Keep the bottom dock useful without letting it dominate startup."""
        self.resizeDocks(
            [self.bottom_dock],
            [max(220, self.height() // 3)],
            Qt.Orientation.Vertical,
        )
        self.resizeDocks(
            [self.project_dock],
            [260],
            Qt.Orientation.Horizontal,
        )


    def _close_active_tab(self) -> None:
        tab_index = self.tabs.currentIndex()
        if tab_index >= 0:
            self._on_tab_close_requested(tab_index)


    def refresh_project_from_disk(self) -> None:
        self.application.refresh_active_project_from_disk()
        self.refresh_project_explorer()
        self._last_file_snapshot = self._filesystem_snapshot()

    def run_build(self) -> None:
        project = self.application.project_manager.active_project
        if project is None:
            return
        result = self.application.build_service.run_build(project)
        self.output_view.appendPlainText(f"$ {result.command}\n{result.output}")
        self.statusBar().showMessage("Build outline completed.")


    def start_debugging(self) -> None:
        project = self.application.project_manager.active_project
        entrypoint = Path("<no-active-file>")
        if self.active_editor is not None and self.active_editor.artifact.path is not None:
            entrypoint = self.active_editor.artifact.path
        if project is not None:
            result = self.application.debug_service.start_debug_session(project, entrypoint, set())
            message = result.output
        else:
            message = "Debugger UI skeleton only; no active project."
        self._show_debugger_skeleton_message(message)

    def debug_step(self) -> None:
        self.application.debug_service.step()
        self._show_debugger_skeleton_message("Debugger step is a UI skeleton; runtime debugging is not implemented.")

    def debug_continue(self) -> None:
        self.application.debug_service.continue_execution()
        self._show_debugger_skeleton_message("Debugger continue is a UI skeleton; runtime debugging is not implemented.")

    def debug_stop(self) -> None:
        self.application.debug_service.stop()
        self._show_debugger_skeleton_message("Debugger stop is a UI skeleton; runtime debugging is not implemented.")

    def _show_debugger_skeleton_message(self, message: str) -> None:
        self.debug_stack_tree.clear()
        self.debug_variables_tree.clear()
        self.debug_output_view.setPlainText(message)
        self.bottom_tabs.setCurrentIndex(self.bottom_tabs.indexOf(self.debug_output_view.parentWidget()))
        self.statusBar().showMessage(message)


    def git_status(self) -> None:
        self._run_vcs_command("status")

    def git_diff(self) -> None:
        self._run_vcs_command("diff")

    def git_log(self) -> None:
        self._run_vcs_command("log")

    def git_branches(self) -> None:
        self._run_vcs_command("branches")

    def git_add(self) -> None:
        project = self.application.project_manager.active_project
        if project is None:
            return
        pathspec, accepted = QInputDialog.getText(self, "Git Add", "Pathspec to stage:", text=".")
        if not accepted or not pathspec.strip():
            return
        result = self.application.vcs_service.add(project, pathspec.strip())
        self._show_tool_result(result, "Git add")

    def commit(self) -> None:
        project = self.application.project_manager.active_project
        if project is None:
            return
        message, accepted = QInputDialog.getText(self, "Git Commit", "Commit message:")
        if not accepted or not message.strip():
            return
        result = self.application.vcs_service.commit(project, message.strip())
        self._show_tool_result(result, "Git commit")

    def git_pull(self) -> None:
        self._run_vcs_command("pull")

    def git_push(self) -> None:
        self._run_vcs_command("push")

    def git_merge(self) -> None:
        project = self.application.project_manager.active_project
        if project is None:
            return
        branch, accepted = QInputDialog.getText(self, "Git Merge", "Branch to merge:")
        if not accepted or not branch.strip():
            return
        result = self.application.vcs_service.merge(project, branch.strip())
        self._show_tool_result(result, "Git merge")

    def _run_vcs_command(self, command: str) -> None:
        project = self.application.project_manager.active_project
        if project is None:
            return
        service = self.application.vcs_service
        result = getattr(service, command)(project)
        self._show_tool_result(result, f"Git {command}")

    def _show_tool_result(self, result, label: str) -> None:
        self.output_view.appendPlainText(f"\n{'-' * 60}")
        self.output_view.appendPlainText(f"$ {result.command}\n{result.output}")
        self.bottom_tabs.setCurrentWidget(self.output_view)
        status = "completed" if result.success else f"failed ({result.exit_code})"
        self.statusBar().showMessage(f"{label} {status}.")

    def about(self) -> None:
        QMessageBox.about(
            self,
            "About",
            "Architecture Driven Collaborative IDE\n\n"
            "Desktop shell prototype with Python language support, multi-type "
            "diagram canvas, test runner, project search, version history, "
            "design traceability, and collaboration presence.\n\n"
            "Press F1 for help topics.",
        )


    def run_active_file(self) -> None:
        """Save the active file then execute it with the system Python interpreter."""
        if self.active_editor is None:
            self.statusBar().showMessage("No active file to run.")
            return

        artifact = self.active_editor.artifact

        if artifact.path is None:
            self.statusBar().showMessage("Cannot run an in-memory artefact; save it to disk first.")
            return

        if artifact.path.suffix.lower() not in (".py", ".java"):
            self.statusBar().showMessage(
                f"Run File supports .py and .java files (active file is {artifact.path.suffix or 'unknown'})."
            )
            return

        self.application.artifact_store.save(artifact)

        project = self.application.project_manager.active_project
        cwd = project.root_path if project else artifact.path.parent

        self.statusBar().showMessage(f"Running {artifact.path.name}...")
        self.output_view.appendPlainText(f"\n{'-' * 60}")
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
            f"{'-' * 60}\nProcess exited with code {result.exit_code}"
        )

        if result.success:
            self.statusBar().showMessage(f"{artifact.path.name} finished (exit 0).")
        else:
            self.statusBar().showMessage(
                f"{artifact.path.name} exited with code {result.exit_code}; see Output panel."
            )


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

        dyn_result = self.application.analysis_manager.run_dynamic_analysis_from_tests(result)
        if dyn_result.diagnostics:
            self._last_diagnostics.extend(dyn_result.diagnostics)
            self._render_diagnostics(self._last_diagnostics)
            if self.active_editor:
                self.active_editor.render_diagnostics(self._last_diagnostics)
            self.output_view.appendPlainText(dyn_result.summary)

        icon = "OK" if result.success else "FAIL"
        self.statusBar().showMessage(
            f"{icon} Tests: {result.total_passed} passed, "
            f"{result.total_failed} failed, {result.total_errors} errors"
        )

    def _render_test_results(self, result) -> None:
        self.test_results_tree.clear()
        for suite in result.suites:
            suite_icon = "OK" if suite.failed == 0 and suite.errors == 0 else "FAIL"
            suite_item = QTreeWidgetItem([
                f"{suite_icon} {suite.name}",
                f"{suite.passed}P / {suite.failed}F / {suite.errors}E / {suite.skipped}S",
                "",
                "",
            ])
            self.test_results_tree.addTopLevelItem(suite_item)
            for case in suite.cases:
                status_icons = {
                    "passed": "OK",
                    "failed": "FAIL",
                    "error": "ERROR",
                    "skipped": "SKIP",
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


    def show_search_bar(self) -> None:
        self.search_field.setFocus()
        self.search_field.selectAll()

    def show_code_completion(self) -> None:
        if self.active_editor is None:
            self.statusBar().showMessage("No active editor for code completion.")
            return
        self.active_editor.show_completion_skeleton()
        self.statusBar().showMessage("Completion popup skeleton shown; provider logic is not implemented.")

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
        for result_item in results:
            self.search_results_tree.addTopLevelItem(
                QTreeWidgetItem([
                    result_item.artifact_name,
                    str(result_item.line),
                    str(result_item.column),
                    result_item.context,
                ])
            )
            item = self.search_results_tree.topLevelItem(
                self.search_results_tree.topLevelItemCount() - 1
            )
            if result_item.artifact_id.startswith("design:"):
                item.setData(
                    0,
                    Qt.ItemDataRole.UserRole,
                    ("diagram", result_item.artifact_id.removeprefix("design:"), result_item.line),
                )
            else:
                item.setData(0, Qt.ItemDataRole.UserRole, ("artifact", result_item.artifact_id, result_item.line))

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
        result_data = item.data(0, Qt.ItemDataRole.UserRole)
        if result_data is None:
            return
        if len(result_data) == 2:
            result_kind, target_identifier, line_number = "artifact", result_data[0], result_data[1]
        else:
            result_kind, target_identifier, line_number = result_data
        if result_kind == "diagram":
            self.tabs.setCurrentWidget(self.diagram_canvas)
            self.diagram_canvas.set_current_diagram(str(target_identifier))
            editor = self.diagram_canvas.get_editor(str(target_identifier))
            if editor is not None:
                block = editor.document().findBlockByLineNumber(max(0, int(line_number) - 1))
                cursor = editor.textCursor()
                cursor.setPosition(block.position())
                editor.setTextCursor(cursor)
                editor.ensureCursorVisible()
            return
        artifact_id = str(target_identifier)
        artifact = self.application.artifact_store.load(artifact_id)
        if artifact is None:
            return
        self.open_artifact(artifact)
        if self.active_editor:
            block = self.active_editor.editor.document().findBlockByLineNumber(max(0, line_number - 1))
            cursor = self.active_editor.editor.textCursor()
            cursor.setPosition(block.position())
            self.active_editor.editor.setTextCursor(cursor)
            self.active_editor.editor.ensureCursorVisible()


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
            topic_item = QTreeWidgetItem([topic.title])
            topic_item.setData(0, Qt.ItemDataRole.UserRole, topic.topic_id)
            topic_list.addTopLevelItem(topic_item)

        def _show_topic(selected_item: QTreeWidgetItem) -> None:
            topic_id = selected_item.data(0, Qt.ItemDataRole.UserRole)
            selected_topic = self.application.help_service.get_topic(topic_id)
            if selected_topic:
                content_view.setPlainText(
                    f"{selected_topic.title}\n"
                    f"{'=' * len(selected_topic.title)}\n\n"
                    f"{selected_topic.content}"
                )

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
            f"Help - {topic.title}",
            topic.content,
        )


    def add_comment(self) -> None:
        if self.active_editor is None:
            self.statusBar().showMessage("No active artefact to comment on.")
            return
        artifact = self.active_editor.artifact
        session = self.application.session_manager.current_session
        author = session.display_name if session else "Anonymous"
        dialog = _AddCommentDialog(self, artifact.name, author)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.body:
            return
        comment = Comment(
            artifact_id=artifact.artifact_id,
            line=dialog.line_number,
            author=author,
            body=dialog.body,
        )
        self.application.comment_service.add_comment(comment)
        self.application.persist_project_state()
        self._refresh_comments(artifact.artifact_id)
        self.statusBar().showMessage(f"Comment added to {artifact.name}:{dialog.line_number}.")

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


    def add_trace_link(self) -> None:
        project = self.application.project_manager.active_project
        artifact_names: list[str] = []
        if project:
            artifact_names = [
                artifact.name
                for artifact in self.application.artifact_store.list_for_project(project)
            ]
        dialog = _AddTraceLinkDialog(self, artifact_names)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        link = TraceLink(
            design_artifact_id=dialog.design_artifact.text(),
            design_element=dialog.design_element.text(),
            code_artifact_id=dialog.code_artifact.text(),
            code_element=dialog.code_element.text(),
            description=dialog.description.text(),
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


    def refresh_project_explorer(self) -> None:
        self.project_tree.clear()
        project = self.application.project_manager.active_project
        if project is None:
            return

        root_item = QTreeWidgetItem([project.name])
        root_item.setData(0, Qt.ItemDataRole.UserRole, str(project.root_path))
        self.project_tree.addTopLevelItem(root_item)

        artifacts = self.application.artifact_store.list_for_project(project)
        dir_items: dict[str, QTreeWidgetItem] = {}

        for artifact in artifacts:
            if artifact.path is not None:
                try:
                    relative_path = artifact.path.relative_to(project.root_path)
                    path_parts = relative_path.parts
                except ValueError:
                    path_parts = (artifact.name,)
            else:
                path_parts = (artifact.name,)

            parent = root_item
            for depth, path_part in enumerate(path_parts[:-1]):
                directory_key = "/".join(path_parts[: depth + 1])
                if directory_key not in dir_items:
                    directory_item = QTreeWidgetItem([path_part])
                    directory_path = project.root_path.joinpath(*path_parts[: depth + 1])
                    directory_item.setData(0, Qt.ItemDataRole.UserRole, str(directory_path))
                    parent.addChild(directory_item)
                    dir_items[directory_key] = directory_item
                parent = dir_items[directory_key]

            file_item = QTreeWidgetItem([path_parts[-1]])
            file_item.setData(0, Qt.ItemDataRole.UserRole, str(artifact.path or artifact.name))
            file_item.setData(0, int(Qt.ItemDataRole.UserRole) + 1, artifact.artifact_id)
            file_item.setToolTip(0, str(artifact.path or artifact.name))
            parent.addChild(file_item)

        root_item.setExpanded(True)
        self._last_file_snapshot = self._filesystem_snapshot()

    def _refresh_project_if_changed(self) -> None:
        snapshot = self._filesystem_snapshot()
        if snapshot != self._last_file_snapshot:
            self.refresh_project_from_disk()

    def _filesystem_snapshot(self) -> set[str]:
        project = self.application.project_manager.active_project
        if project is None or not project.root_path.is_dir():
            return set()
        skip_dirs = {
            ".bscode", ".git", "__pycache__", ".pytest_cache", ".mypy_cache",
            "node_modules", ".venv", "venv", "dist", "build",
        }
        snapshot: set[str] = set()
        for path in project.root_path.rglob("*"):
            try:
                relative_path = path.relative_to(project.root_path)
            except ValueError:
                continue
            if any(part in skip_dirs or part.startswith(".") for part in relative_path.parts[:-1]):
                continue
            if path.is_file():
                snapshot.add(str(relative_path))
        return snapshot


    def _on_tab_changed(self, index: int) -> None:
        widget = self.tabs.widget(index)
        if isinstance(widget, EditorView):
            self.active_editor = widget
            self.application.collab_service.update_local_presence(
                widget.artifact.artifact_id, widget.artifact.name
            )
            self.collab_ui.set_peers(self.application.collab_service.peers)
            self._refresh_comments(widget.artifact.artifact_id)
            self.breakpoint_field.setText(
                ", ".join(str(line) for line in sorted(widget.breakpoints()))
            )
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
        artifact_id = item.data(0, int(Qt.ItemDataRole.UserRole) + 1)
        if artifact_id:
            artifact = self.application.artifact_store.load(str(artifact_id))
            if artifact is not None:
                self.open_artifact(artifact)

    def open_artifact(self, artifact: Artifact) -> None:
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


    def _on_sync_status_changed(self, status: SyncStatus) -> None:
        labels = {
            SyncStatus.IDLE: "Sync: idle",
            SyncStatus.PENDING: "Sync: pending...",
            SyncStatus.SYNCING: "Sync: syncing...",
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


    def _load_diagrams_for_active_project(self) -> None:
        """Populate the diagram canvas from .bscode/design/ for the active project."""
        self.diagram_canvas.reset_to_templates()
        saved = self.application.load_diagrams()
        if saved:
            self.diagram_canvas.load_saved_content(saved)

    def _clear_code_editors(self) -> None:
        for index in reversed(range(self.tabs.count())):
            widget = self.tabs.widget(index)
            if isinstance(widget, EditorView):
                self.tabs.removeTab(index)
                widget.deleteLater()
        self.active_editor = None
