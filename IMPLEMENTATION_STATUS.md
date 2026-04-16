# Implementation Status Against Target-System Brief

This file uses only two categories:

- **Fully implemented**: working behaviour exists in the prototype and is usable within the coursework scope.
- **Outlined**: the architecture seam exists, but production behaviour is deliberately left for future work.

## Fully Implemented

| Brief item | Evidence |
| --- | --- |
| GUI for user interaction | PySide6 shell with menus, toolbar, tabs, docks, status bar. |
| Basic editor | Project files open in editable tabs with autosave, diagnostics, line numbers with matched editor background, clickable breakpoint gutter, and syntax highlighting. |
| Syntax highlighting | `EditorView` applies keyword highlighting through each language service. |
| Help facility | Structured help topics and contextual help dialog. |
| Storage/retrieval of development artefacts | Code files, comments, traceability links, and revision data persist through files or `.bscode` sidecars. |
| File explorer | Project explorer scans project files, opens artefacts, refreshes when external file changes are detected, and can be hidden/restored from the View menu. |
| Compiler/interpreter integration | Python files run through the active interpreter; Java files compile/run through local `javac`/`java` when a JDK is installed. |
| Static code analysis | Python/Java metadata extraction and diagnostics run through `AnalysisManager`; conformance checks compare declared architecture elements with parsed code elements. |
| Multiple concurrent projects | Projects registered in the session can be switched through the project selector. |
| Testing framework integration | On-disk Python projects run with `unittest discover`; in-memory prototype artefacts use deterministic fallback classification. |
| Version control systems | Git status, diff, log, branch listing, add/stage, commit, pull, push, and merge run through `VCSService` against the active project root. |
| Incremental architecture/design specification | Design canvas and Mermaid source files provide editable component, layered, deployment, class, and sequence views. |
| Static/dynamic analysis workflow | Static diagnostics and conformance checks run after edits; test results feed the dynamic-analysis hook. |
| Accessible UI basics | Main widgets/actions include accessible names, labels, tooltips, keyboard shortcuts, and clickable line-number breakpoints. |
| Heterogeneous platform baseline | Python/PySide6 implementation, path abstraction, Fusion Qt style, and in-window menus for more consistent macOS/Windows/Linux UI. |
| Java and Python initial support | Python and Java language services are registered and file types are recognised. |
| Future language support | `LanguageService`, extension contracts, and `PluginRegistry` provide the extension seam. |

## Outlined

| Brief item | Current boundary |
| --- | --- |
| Build automation tools | `BuildService` defines the boundary; Maven/Gradle/project build orchestration is future work. |
| Debugger integration | The debugger panel, controls, breakpoint field, stack view, variables view, and `DebugService` boundary remain; runtime debugging has been removed for future implementation. |
| Code completion | The editor shows a VS Code-style completion popup scaffold while typing or on Ctrl+Space; candidate generation and insertion are future work. |
| Class diagram generation from code | Removed from the IDE; UML Class remains an editable design tab only. |
| Distributed collaboration | `CollabService`, `NetworkSync`, presence UI, and sync status exist; real server/peer networking is future work. |
| Conflict-free concurrent editing | Operation broadcasting seam exists; CRDT/OT and conflict resolution are future work. |
| Production static/dynamic analysis | Prototype diagnostics exist; industrial parsers, profilers, and architecture rule engines are future work. |
| Graphical diagram editor | Text-based diagrams are implemented; drag/drop UML rendering is future work. |
| Dynamic plugin loading | Protocols and registry exist; discovering/installing plugins from disk is future work. |
| Load/scaling infrastructure | Boundaries support replacement; server-side scaling and load testing are future work. |
