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

- `ide.presentation`: PySide6 desktop shell, editor surface, diagram placeholder, collaboration presence panel, diagnostics and output views.
- `ide.workspace`: project selection, artifact storage facade, collaboration orchestration, user session context.
- `ide.services`: language services and external tool integration stubs for build, debug, and Git.
- `ide.analysis`: static analysis, conformance checking, dynamic analysis extension points, and orchestration.
- `ide.infrastructure`: platform, persistence, network sync, and plugin registry boundaries.
- `ide.domain`: shared dataclasses and enums used across the layers.

## What Is Intentionally Skeletal

The prototype does not implement real networking, CRDT algorithms, database persistence, compilers, debuggers, Git operations, parsers, or production static analysis. Those are represented by typed services and adapter boundaries so the design remains clear and extensible.

## Current Language Support

Only Python is implemented as a concrete language service through `PythonLangSvc`. The architecture still treats language support as pluggable through the `LanguageService` protocol and `PluginRegistry`.

## Extending With A New Language

1. Implement the `LanguageService` protocol in `ide.services.language`.
2. Register the implementation in `IDEApplication._register_builtin_plugins`.
3. Associate artifacts with the new language name.
4. Add language-specific static analysis by implementing `StaticAnalyser` and registering it through the plugin registry or analysis manager.

## Extending Analysis

Replace or add implementations of `StaticAnalyser`, `DynAnalyser`, or `ConformanceChecker` in `ide.analysis.engine`. The `AnalysisManager` is the coordination point used by the UI and future service integrations.
