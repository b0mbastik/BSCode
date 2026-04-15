# Architecture Mapping Table

| Architecture element | Design element | Implementation element | Notes |
| --- | --- | --- | --- |
| Presentation | IDEShell | `ide.presentation.ide_shell.IDEShell` | Main PySide6 window, menus, docks, tabs, status bar. |
| Presentation | EditorView | `ide.presentation.editor_view.EditorView` | Code editor with text buffer, local operations, diagnostics rendering. |
| Presentation | DiagramCanvas | `ide.presentation.widgets.DiagramCanvas` | Text-based architecture/design editing surface with component, layered, deployment, class, and sequence views. |
| Presentation | CollabUI | `ide.presentation.widgets.CollabUI` | Presence and collaboration event panel. |
| Workspace | ProjectManager | `ide.workspace.workspace_services.ProjectManager` | Creates and switches active projects. |
| Workspace | CollabService | `ide.workspace.workspace_services.CollabService` | Accepts edit operations and broadcasts through `NetworkSync`. |
| Workspace | ArtifactStore | `ide.workspace.workspace_services.ArtifactStore` | Stores code, architecture, design, and test artifacts. |
| Workspace | SessionManager | `ide.workspace.workspace_services.SessionManager` | Maintains current user/session context. |
| Workspace | CommentService | `ide.workspace.workspace_services.CommentService` | Maintains in-memory comments and annotations for artifacts. |
| Workspace | VersionService | `ide.workspace.workspace_services.VersionService` | Creates explicit save checkpoints through `RevisionLog`. |
| Workspace | TraceabilityService | `ide.workspace.traceability.TraceabilityService` | Maintains design-to-code trace links. |
| Core IDE Services | LanguageService | `ide.services.language.LanguageService` | Protocol for pluggable language support. |
| Core IDE Services | PythonLangSvc | `ide.services.language.PythonLangSvc` | Concrete outline language service for Python. |
| Core IDE Services | JavaLangSvc | `ide.services.language.JavaLangSvc` | Skeletal language service for Java file recognition, metadata extraction, completion and highlighting. |
| Core IDE Services | BuildService | `ide.services.integrations.BuildService` | Stub for external interpreter/build tool integration. |
| Core IDE Services | DebugService | `ide.services.integrations.DebugService` | Stub for debugger integration. |
| Core IDE Services | VCSService | `ide.services.integrations.VCSService` | Stub Git integration. |
| Core IDE Services | TestService | `ide.services.testing.TestService` | Discovers Python-style test functions and returns structured stub results. |
| Core IDE Services | SearchService | `ide.services.search.SearchService` | Searches project artifacts and live design diagram text. |
| Core IDE Services | HelpService | `ide.services.help.HelpService` | Provides structured help topics and contextual help. |
| Analysis Engine | AnalysisManager | `ide.analysis.engine.AnalysisManager` | Coordinates static, dynamic, and conformance workflows. |
| Analysis Engine | StaticAnalyser | `ide.analysis.engine.StaticAnalyser` | Abstract extension point for static analysis. |
| Analysis Engine | ConformanceChecker | `ide.analysis.engine.ConformanceChecker` | Stub architecture/design/code consistency check. |
| Analysis Engine | DynAnalyser | `ide.analysis.engine.DynAnalyser` | Abstract extension point for runtime/test-time analysis. |
| Infrastructure | PlatformAbstraction | `ide.infrastructure.adapters.PlatformAbstraction` | OS and filesystem boundary. |
| Infrastructure | Persistence | `ide.infrastructure.adapters.Persistence` | Storage/versioning boundary. |
| Infrastructure | NetworkSync | `ide.infrastructure.adapters.NetworkSync` | Collaboration transport boundary. |
| Infrastructure | PluginRegistry | `ide.infrastructure.adapters.PluginRegistry` | Registers language and analyser extensions. |
| Infrastructure | BSCodeStore | `ide.infrastructure.bscode_store.BSCodeStore` | Persists project-local design diagram text under `.bscode/design/`. |
| Application | IDEApplication | `ide.app.application.IDEApplication` | Composition root and startup flow. |

## Diagram Source Mapping

| Diagram | Source file | Purpose |
| --- | --- | --- |
| Logical component view | `docs/report/diagrams/logical_view_component_diagram.mmd` | Shows implemented architecture layers and dependencies. |
| Structural class view | `docs/report/diagrams/structural_design_class_diagram.mmd` | Shows main classes, protocols, and extension boundaries. |
| Edit/analyse/collaborate sequence | `docs/report/diagrams/behavioural_sequence_edit_analyse_collaborate.mmd` | Shows the main edit, autosave, collaboration, and analysis flow. |
| Test/dynamic analysis sequence | `docs/report/diagrams/behavioural_sequence_run_tests_dynamic_analysis.mmd` | Shows test execution and dynamic-analysis hook flow. |
