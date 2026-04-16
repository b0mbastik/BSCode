# Verification Notes

## Verification Scope

The repository is now an architecture-first outline.  Verification therefore
checks importability, class/service contracts, subsystem wiring and simple
placeholder interactions.  Tests deliberately do not assert real IDE behaviour.

## Commands

```bash
python3 -m compileall ide main.py
python3 -m unittest discover -s tests
```

## Latest Result

- `python3 -m compileall ide main.py`: passed.
- `python3 -m unittest discover -s tests`: passed, 13 architecture-focused tests.

## Expected Coverage

The focused tests cover:

- composition root wiring
- domain dataclass contracts
- project and artefact manager interaction
- language-service method shape
- analysis and conformance boundaries
- dynamic-analysis boundary
- run/build/debug/VCS placeholder result objects
- test/search service boundaries
- `.bscode` metadata boundary
- collaboration, traceability, revision and plugin boundaries

## Intentional Limitations

- No real file scanning, file writes or sidecar JSON persistence.
- No AST parsing, regex analysis, code completion, or syntax highlighting logic.
- No subprocess execution for Python, Java, tests, builds or Git.
- No real debugger execution, breakpoints, stack inspection or variables.
- No real dynamic analysis or conformance-rule execution.
- No collaboration server, CRDT/OT, conflict resolution or remote presence.
- No dynamic plugin loading.
- GUI behaviour remains a structural shell and is not tested as a production UI.
