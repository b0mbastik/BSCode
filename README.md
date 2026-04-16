# Architecture Driven Collaborative IDE Prototype

This repository contains a design-conformant outline implementation for a desktop IDE used in collaborative architecture-driven software development coursework. It is intentionally skeletal: the UI shell runs as a real desktop application, while deeper services expose extension points rather than complete production behaviour.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

On macOS, if PySide6 was installed with the framework Python installer but Homebrew `python3` is first on your path, run the interpreter that owns that installation:

```bash
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 main.py
```

## Architectural Layers

- `ide.presentation`: PySide6 desktop shell, editor surface, diagram canvas, collaboration presence panel, diagnostics and output views.
- `ide.workspace`: project selection, artifact storage facade, collaboration orchestration, user session context.
- `ide.services`: language services and external tool integration boundaries for build, debug, run, and Git.
- `ide.analysis`: static analysis, conformance checking, dynamic analysis extension points, and orchestration.
- `ide.infrastructure`: platform, persistence, network sync, and plugin registry boundaries.
- `ide.domain`: shared dataclasses and enums used across the layers.

## What Is Intentionally Skeletal

The prototype does not implement real networking, CRDT algorithms, database persistence, Java debugging, class-diagram generation from code, production language-server completion, production parsers, dynamic analysis diagnostics, rich help/search/comment workflows, or industrial static analysis. Those are represented by typed services and adapter boundaries so the design remains clear and extensible.

## Current Language Support

- Python is implemented as the concrete outline language service through `PythonLangSvc`; it provides keyword highlighting, simple symbol extraction, and lightweight completions from keywords, imports, functions, classes, and identifiers.
- Java is represented by a skeletal `JavaLangSvc` that recognises `.java` files, extracts shallow class/method metadata, applies keyword highlighting, and provides lightweight completions.
- Code completion is real but intentionally small: typing or pressing Ctrl+Space opens an editor-local popup populated by the active language service and simple project symbols.
- Other recognised text formats use `PlainTextLangSvc`.

The architecture treats language support as pluggable through the `LanguageService` protocol and `PluginRegistry`.

## Design Artefacts

Editable Mermaid diagram sources for the submission are stored in `docs/report/diagrams/`:

- `logical_view_component_diagram.mmd`
- `structural_design_class_diagram.mmd`
- `behavioural_sequence_edit_analyse_collaborate.mmd`
- `behavioural_sequence_run_tests_dynamic_analysis.mmd`

These diagrams use the same component and class names as the implementation.

## Verification

Run the lightweight non-UI checks with:

```bash
python3 -m compileall ide main.py
python3 -m unittest discover -s tests
```

See `VERIFICATION.md` for the latest recorded verification notes and intentional limitations.

See `IMPLEMENTATION_STATUS.md` for a brief fully-implemented vs outlined status against the target-system brief.

## Extending With A New Language

1. Implement the `LanguageService` protocol in `ide.services.language`.
2. Register the implementation in `IDEApplication._register_builtin_plugins`.
3. Associate artifacts with the new language name.
4. Add language-specific static analysis by implementing `StaticAnalyser` and registering it through the plugin registry or analysis manager.

## Extending Analysis

Replace or add implementations of `StaticAnalyser`, `DynAnalyser`, or `ConformanceChecker` in `ide.analysis.engine`. The current `DynAnalyser` is intentionally non-diagnostic; it exists only as the future runtime-analysis boundary.

## Debugging

`DebugService` provides a minimal Python-only debugger using the standard-library `bdb` module. It can start the active Python file, pause at simple line breakpoints, step, continue, stop, and report locals/output to the UI. Java debugging and advanced debugger features are intentionally out of scope.
