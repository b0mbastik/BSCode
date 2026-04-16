# Architecture Mapping Table

| Architecture element | Design element | Implementation element | Outline status |
| --- | --- | --- | --- |
| Application | Composition root | `ide.app.application.IDEApplication` | Wires subsystems and registers skeletal services. |
| Presentation | Shell/controller | `ide.presentation.ide_shell.IDEShell` | Keeps menus, docks, tabs, panels and action wiring. |
| Presentation | Editor boundary | `ide.presentation.editor_view.EditorView`, `CodeEditor` | Keeps document/operation/completion/debug hooks; rich editing omitted. |
| Presentation | Design canvas | `ide.presentation.widgets.DiagramCanvas` | Keeps text-based design artefact concepts. |
| Presentation | Collaboration panel | `ide.presentation.widgets.CollabUI` | Keeps presence/event UI boundary. |
| Domain | Shared contracts | `ide.domain.models` | Dataclasses/enums retained as cross-layer contracts. |
| Workspace | Project management | `ProjectManager` | Active project and registration flow retained. |
| Workspace | Artefact storage | `ArtifactStore`, `Persistence` | In-memory facade retained; durable storage omitted. |
| Workspace | Collaboration | `CollabService`, `NetworkSync`, `Operation` | Architectural boundary only; no real networking. |
| Workspace | Notes/revisions/traceability | `CommentService`, `VersionService`, `TraceabilityService` | Simple structural services only. |
| Services | Language support | `LanguageService`, `PythonLangSvc`, `JavaLangSvc`, `PlainTextLangSvc` | Interfaces/classes retained; real parsing/highlighting/completion omitted. |
| Services | Tool integrations | `RunService`, `BuildService`, `DebugService`, `VCSService` | `RunService` executes single Python/Java files; build/debug/VCS remain placeholders. |
| Services | Testing/search/help | `TestService`, `SearchService`, `HelpService` | Boundaries retained; only help has static content. |
| Analysis | Analysis orchestration | `AnalysisManager`, `StaticAnalyser`, `ConformanceChecker`, `DynAnalyser` | Contracts and flow retained; algorithms omitted. |
| Infrastructure | Sidecar metadata | `BSCodeStore` | `.bscode` boundary retained; persistence omitted. |
| Infrastructure | Plugin extension | `PluginRegistry`, `ide.extensions.contracts` | Registry/contracts retained; dynamic loading omitted. |

## Diagram Source Mapping

| Diagram | Source file | Purpose |
| --- | --- | --- |
| Logical component view | `docs/report/diagrams/logical_view_component_diagram.mmd` | Shows subsystem/layer decomposition. |
| Structural class view | `docs/report/diagrams/structural_design_class_diagram.mmd` | Shows primary classes, protocols and boundaries. |
| Edit/analyse/collaborate sequence | `docs/report/diagrams/behavioural_sequence_edit_analyse_collaborate.mmd` | Shows intended interaction flow; behaviour is skeletal. |
| Test/dynamic analysis sequence | `docs/report/diagrams/behavioural_sequence_run_tests_dynamic_analysis.mmd` | Shows test-to-dynamic-analysis boundary; no real diagnostics are produced. |
