"""Main PySide6 IDE shell."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QDockWidget,
    QPlainTextEdit,
    QStatusBar,
    QTabWidget,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
)

from ide.domain.models import Artifact, ArtifactType, Diagnostic, Operation
from ide.presentation.editor_view import EditorView
from ide.presentation.widgets import CollabUI, DiagramCanvas

if TYPE_CHECKING:
    from ide.app.application import IDEApplication


class IDEShell(QMainWindow):
    def __init__(self, application: IDEApplication) -> None:
        super().__init__()
        self.application = application
        self.active_editor: EditorView | None = None
        self._last_diagnostics: list[Diagnostic] = []
        self.setWindowTitle("Architecture Driven Collaborative IDE")
        self.resize(1280, 820)

        self.analysis_timer = QTimer(self)
        self.analysis_timer.setSingleShot(True)
        self.analysis_timer.timeout.connect(lambda: self._run_static_analysis(add_output=False))

        self._create_actions()
        self._create_menu_bar()
        self._create_toolbar()
        self._create_central_tabs()
        self._create_docks()
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Desktop IDE shell ready.")
        self.refresh_project_explorer()

    def _create_actions(self) -> None:
        self.new_project_action = QAction("New Project", self)
        self.new_project_action.triggered.connect(self.new_project)

        self.open_project_action = QAction("Open Project…", self)
        self.open_project_action.setShortcut(QKeySequence("Ctrl+Shift+O"))
        self.open_project_action.triggered.connect(self.open_project)

        self.open_file_action = QAction("Open File…", self)
        self.open_file_action.setShortcut(QKeySequence("Ctrl+O"))
        self.open_file_action.triggered.connect(self.open_file)

        self.save_artifact_action = QAction("Save", self)
        self.save_artifact_action.setShortcut(QKeySequence("Ctrl+S"))
        self.save_artifact_action.triggered.connect(self.save_active_artifact)

        self.build_action = QAction("Run Build", self)
        self.build_action.triggered.connect(self.run_build)

        self.static_analysis_action = QAction("Run Static Analysis", self)
        self.static_analysis_action.triggered.connect(lambda: self._run_static_analysis(add_output=True))

        self.commit_action = QAction("Commit", self)
        self.commit_action.triggered.connect(self.commit)

        self.about_action = QAction("About", self)
        self.about_action.triggered.connect(self.about)

    def _create_menu_bar(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(self.new_project_action)
        file_menu.addAction(self.open_project_action)
        file_menu.addAction(self.open_file_action)
        file_menu.addSeparator()
        file_menu.addAction(self.save_artifact_action)
        build_menu = self.menuBar().addMenu("Build")
        build_menu.addAction(self.build_action)
        analyse_menu = self.menuBar().addMenu("Analyse")
        analyse_menu.addAction(self.static_analysis_action)
        vcs_menu = self.menuBar().addMenu("VCS")
        vcs_menu.addAction(self.commit_action)
        help_menu = self.menuBar().addMenu("Help")
        help_menu.addAction(self.about_action)

    def _create_toolbar(self) -> None:
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        toolbar.addAction(self.new_project_action)
        toolbar.addAction(self.open_file_action)
        toolbar.addAction(self.save_artifact_action)
        toolbar.addAction(self.build_action)
        toolbar.addAction(self.static_analysis_action)
        self.addToolBar(toolbar)

    def _create_central_tabs(self) -> None:
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.diagram_canvas = DiagramCanvas()
        self.tabs.addTab(self.diagram_canvas, "Design")
        # The Design tab should not be closable.
        self.tabs.tabBar().setTabButton(0, self.tabs.tabBar().ButtonPosition.RightSide, None)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.tabs.tabCloseRequested.connect(self._on_tab_close_requested)
        self.setCentralWidget(self.tabs)

    def _create_docks(self) -> None:
        self.project_tree = QTreeWidget()
        self.project_tree.setHeaderLabels(["Project Explorer"])
        self.project_tree.itemDoubleClicked.connect(self._open_tree_item)
        project_dock = QDockWidget("Project Explorer", self)
        project_dock.setWidget(self.project_tree)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, project_dock)

        self.collab_ui = CollabUI()
        self.collab_ui.set_peers(self.application.collab_service.peers)
        collab_dock = QDockWidget("Collaboration", self)
        collab_dock.setWidget(self.collab_ui)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, collab_dock)

        self.bottom_tabs = QTabWidget()
        self.diagnostics_tree = QTreeWidget()
        self.diagnostics_tree.setHeaderLabels(["Severity", "Line", "Source", "Message"])
        self.output_view = QPlainTextEdit()
        self.output_view.setReadOnly(True)
        self.bottom_tabs.addTab(self.diagnostics_tree, "Diagnostics")
        self.bottom_tabs.addTab(self.output_view, "Output")
        bottom_dock = QDockWidget("Diagnostics / Output", self)
        bottom_dock.setWidget(self.bottom_tabs)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, bottom_dock)

    # ------------------------------------------------------------------
    # File / Project actions
    # ------------------------------------------------------------------

    def new_project(self) -> None:
        name, accepted = QInputDialog.getText(self, "New Project", "Project name:")
        if not accepted or not name.strip():
            return
        self.application.open_project(name.strip(), Path.cwd() / name.strip())
        self._clear_code_editors()
        self.refresh_project_explorer()
        self.output_view.appendPlainText(f"Created project: {name.strip()}")

    def open_project(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Open Project Folder")
        if not path:
            return
        project_name = Path(path).name or "Opened Project"
        self.application.open_project(project_name, Path(path))
        self._clear_code_editors()
        self.refresh_project_explorer()
        self.output_view.appendPlainText(f"Opened project: {project_name} ({path})")
        self.statusBar().showMessage(f"Project '{project_name}' loaded.")

    def open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open File",
            str(self.application.project_manager.active_project.root_path)
            if self.application.project_manager.active_project else "",
            "All Files (*.*)",
        )
        if not path:
            return
        artifact = self.application.open_file(Path(path))
        if artifact is None:
            QMessageBox.warning(self, "Cannot Open", f"File type not supported or unreadable:\n{path}")
            return
        self.refresh_project_explorer()
        self.open_artifact(artifact)

    def save_active_artifact(self) -> None:
        if self.active_editor is None:
            self.statusBar().showMessage("No active editor to save.")
            return
        self.application.artifact_store.save(self.active_editor.artifact)
        artifact = self.active_editor.artifact
        label = str(artifact.path) if artifact.path else artifact.name
        self.statusBar().showMessage(f"Saved {label}.")

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
            "Desktop shell prototype with Python language support only.",
        )

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
            # Determine path parts relative to project root for tree grouping.
            if artifact.path is not None:
                try:
                    rel = artifact.path.relative_to(project.root_path)
                    parts = rel.parts
                except ValueError:
                    parts = (artifact.name,)
            else:
                parts = (artifact.name,)

            # Build intermediate directory nodes.
            parent = root_item
            for depth, part in enumerate(parts[:-1]):
                dir_key = "/".join(parts[: depth + 1])
                if dir_key not in dir_items:
                    dir_node = QTreeWidgetItem([part])
                    parent.addChild(dir_node)
                    dir_items[dir_key] = dir_node
                parent = dir_items[dir_key]

            # Add the file leaf node.
            file_item = QTreeWidgetItem([parts[-1]])
            file_item.setData(0, Qt.ItemDataRole.UserRole, artifact.artifact_id)
            parent.addChild(file_item)

        root_item.setExpanded(True)

    # ------------------------------------------------------------------
    # Tab and editor management
    # ------------------------------------------------------------------

    def _on_tab_changed(self, index: int) -> None:
        widget = self.tabs.widget(index)
        if isinstance(widget, EditorView):
            self.active_editor = widget
        else:
            self.active_editor = None

    def _on_tab_close_requested(self, index: int) -> None:
        widget = self.tabs.widget(index)
        if isinstance(widget, DiagramCanvas):
            return  # Design tab is not closable.
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
        # Switch to an already-open tab rather than creating a duplicate.
        existing = self._find_editor_tab(artifact.artifact_id)
        if existing is not None:
            self.tabs.setCurrentWidget(existing)
            self.active_editor = existing
            return

        language_service = self.application.language_services.get(artifact.language or "plain")
        if language_service is None:
            # Fall back to plain text service.
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
        self.collab_ui.log_event(f"Local edit broadcast for {artifact.name}")
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
        self.statusBar().showMessage(f"Analysis completed with {len(diagnostics)} diagnostic(s).")

    def _render_diagnostics(self, diagnostics: list[Diagnostic]) -> None:
        self.diagnostics_tree.clear()
        for diagnostic in diagnostics:
            self.diagnostics_tree.addTopLevelItem(
                QTreeWidgetItem(
                    [
                        diagnostic.severity.value,
                        str(diagnostic.line),
                        diagnostic.source,
                        diagnostic.message,
                    ]
                )
            )

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
