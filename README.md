# Architecture Driven Collaborative IDE Outline

This repository is an architecture-first outline implementation for the CS5033
Software Architecture and Design coursework.  It is intentionally not a
feature-complete IDE.  The code preserves subsystem boundaries, typed contracts,
service interfaces, presentation wiring, and extension points so the design can
be mapped clearly to implementation elements.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

## Architectural Layers

- `ide.presentation`: PySide6 shell, editor boundary, diagram canvas, docks and panels.
- `ide.app`: composition root wiring the subsystems together.
- `ide.workspace`: project, artefact, session, collaboration, notes, revisions and traceability boundaries.
- `ide.services`: language, run, debug, build, test, search, help and VCS service contracts.
- `ide.analysis`: static analysis, conformance and dynamic-analysis orchestration boundaries.
- `ide.infrastructure`: platform, persistence, revision log, network sync, plugin registry and `.bscode` sidecar boundaries.
- `ide.domain`: shared dataclasses/enums used as typed cross-layer contracts.
- `ide.extensions`: public plugin contracts.

## Scope

Most standard IDE features are outlined only.  The implementation keeps the
classes, method signatures, result models and collaboration points, but removes
real algorithms and tool execution.  This is deliberate: the coursework values
architecture, design structure and traceability over feature completeness.

Outlined boundaries include:

- syntax highlighting, completion and language parsing
- Python and Java language support
- run/debug/build/test/VCS integrations
- static, conformance and dynamic analysis
- project search
- autosave/revision persistence
- real collaboration networking and conflict handling
- graphical UML editing and class diagram generation from code
- dynamic plugin loading

## Design Artefacts

Editable Mermaid diagram sources for the report live in `docs/report/diagrams/`.
They mirror the implementation structure and are suitable for the logical,
structural and behavioural design sections of the report.

## Verification

The tests validate architecture and contracts rather than rich functionality:

```bash
python3 -m compileall ide main.py
python3 -m unittest discover -s tests
```

See `IMPLEMENTATION_STATUS.md` and `VERIFICATION.md` for the current outline
status and intentional limitations.
