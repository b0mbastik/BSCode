# Implementation Status Against Target-System Brief

This repository now uses two categories:

- **Structural outline**: classes, modules, interfaces, dataclasses, method
  signatures and collaboration points are present, but real behaviour is
  intentionally omitted.
- **Minimal retained behaviour**: a small amount of in-memory wiring remains
  only so the application can be imported/launched and interactions can be
  inspected.

## Structural Outline

| Brief item | Current implementation |
| --- | --- |
| GUI shell | PySide6 shell, menus, toolbar, docks, tabs and actions remain. Actions delegate to skeletal services. |
| Basic editor | Editor/view classes, document buffer, completion hook and operation callback remain. Rich editing, diagnostics painting and breakpoint behaviour are omitted. |
| Syntax highlighting | `LanguageService.highlight()` and highlighter classes remain; token logic is omitted. |
| Code completion | `CompletionItem`, popup and `LanguageService.complete()` remain; real candidate generation is omitted. |
| Python language support | `PythonLangSvc` remains as a language-service boundary without AST parsing or semantic behaviour. |
| Java language support | `JavaLangSvc` remains as a second language boundary without parsing/compile logic. |
| File explorer | Explorer widgets and artefact-open hooks remain; real project scanning is reduced to representative outline artefacts. |
| Project switching | `ProjectManager` and selector flow remain; project loading/unloading is skeletal. |
| Storage/retrieval | `Persistence`, `ArtifactStore`, `FilesystemPersistence` and `BSCodeStore` remain; durable writes are omitted. |
| Autosave/revisions | `Revision`, `RevisionLog` and `VersionService` remain; revision history is not implemented. |
| Architecture/design artefacts | `DiagramCanvas` and diagram concepts remain as text-based design boundaries. |
| Class diagram generation | Not implemented; class diagram remains an editable design artefact concept. |
| Run/interpreter integration | `RunService` remains and returns placeholder `ToolExecutionResult` objects. |
| Debugging | `DebugService`, `DebugSnapshot` and UI hooks remain; no real runtime debugging occurs. |
| Build automation | `BuildService` remains as an explicit boundary only. |
| Testing integration | `TestService` and result models remain; no framework discovery/execution occurs. |
| Static analysis | `StaticAnalyser`, `AnalysisManager` and diagnostics models remain; AST/regex checks are omitted. |
| Architecture conformance | `ConformanceChecker` remains as a rule boundary; comparison logic is omitted. |
| Dynamic analysis | `DynAnalyser`/`StubDynAnalyser` remain as future-work boundaries. |
| Version control | `VCSService` remains; Git commands are not executed. |
| Project search | `SearchService` remains; real search is omitted. |
| Help facility | Static help/about text remains. |
| Notes/comments | Comment models/service remain as a simple boundary. |
| Traceability | `TraceLink` and `TraceabilityService` remain as a simple link boundary. |
| Collaboration | Operation, session, presence, `CollabService`, `NetworkSync` and panel classes remain; no real networking/CRDT exists. |
| Accessibility basics | Accessible names, labels, tooltips and shortcut declarations are retained as structure. |
| Cross-platform baseline | Python/PySide6 entry point and path abstraction remain; packaging is omitted. |
| Plugin registry | `PluginRegistry` and extension contracts remain; dynamic loading is omitted. |
| Load/scaling infrastructure | No real scaling behaviour; only architectural seams remain. |
| Verification/tests | Tests now validate module/class existence, service contracts and simple interactions. |
| `.bscode` files | `.bscode` remains as the named metadata boundary; runtime sidecar persistence is skeletal. |

## Minimal Retained Behaviour

| Area | Reason retained |
| --- | --- |
| In-memory project/artefact registration | Keeps the shell and mapping between project, artefact and editor inspectable. |
| Placeholder result objects | Demonstrates how services return typed results to the UI. |
| Basic note/traceability in-memory lists | Shows the workspace-service responsibility without rich behaviour. |
| Debug state placeholders | Shows the debugger service/UI interaction without executing code. |
| Static diagram templates | Provides report-facing design artefact concepts. |
