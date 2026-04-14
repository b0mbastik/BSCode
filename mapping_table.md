# Architecture Mapping Table

| Architecture element | Design element | Implementation element | Notes |
| --- | --- | --- | --- |
| Presentation | IDEShell | `ide.presentation.ide_shell.IDEShell` | Main PySide6 window, menus, docks, tabs, status bar. |
| Presentation | EditorView | `ide.presentation.editor_view.EditorView` | Code editor with text buffer, local operations, diagnostics rendering. |
| Presentation | DiagramCanvas | `ide.presentation.widgets.DiagramCanvas` | Placeholder architecture/design editing surface. |
| Presentation | CollabUI | `ide.presentation.widgets.CollabUI` | Presence and collaboration event panel. |
| Workspace | ProjectManager | `ide.workspace.workspace_services.ProjectManager` | Creates and switches active projects. |
| Workspace | CollabService | `ide.workspace.workspace_services.CollabService` | Accepts edit operations and broadcasts through `NetworkSync`. |
| Workspace | ArtifactStore | `ide.workspace.workspace_services.ArtifactStore` | Stores code, architecture, design, and test artifacts. |
| Workspace | SessionManager | `ide.workspace.workspace_services.SessionManager` | Maintains current user/session context. |
| Core IDE Services | LanguageService | `ide.services.language.LanguageService` | Protocol for pluggable language support. |
| Core IDE Services | PythonLangSvc | `ide.services.language.PythonLangSvc` | Only concrete language service in this prototype. |
| Core IDE Services | BuildService | `ide.services.integrations.BuildService` | Stub for external interpreter/build tool integration. |
| Core IDE Services | DebugService | `ide.services.integrations.DebugService` | Stub for debugger integration. |
| Core IDE Services | VCSService | `ide.services.integrations.VCSService` | Stub Git integration. |
| Analysis Engine | AnalysisManager | `ide.analysis.engine.AnalysisManager` | Coordinates static, dynamic, and conformance workflows. |
| Analysis Engine | StaticAnalyser | `ide.analysis.engine.StaticAnalyser` | Abstract extension point for static analysis. |
| Analysis Engine | ConformanceChecker | `ide.analysis.engine.ConformanceChecker` | Stub architecture/design/code consistency check. |
| Analysis Engine | DynAnalyser | `ide.analysis.engine.DynAnalyser` | Abstract extension point for runtime/test-time analysis. |
| Infrastructure | PlatformAbstraction | `ide.infrastructure.adapters.PlatformAbstraction` | OS and filesystem boundary. |
| Infrastructure | Persistence | `ide.infrastructure.adapters.Persistence` | Storage/versioning boundary. |
| Infrastructure | NetworkSync | `ide.infrastructure.adapters.NetworkSync` | Collaboration transport boundary. |
| Infrastructure | PluginRegistry | `ide.infrastructure.adapters.PluginRegistry` | Registers language and analyser extensions. |
| Application | IDEApplication | `ide.app.application.IDEApplication` | Composition root and startup flow. |
