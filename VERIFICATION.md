# Verification Notes

## Commands Run

```bash
python3 -m compileall ide main.py
python3 -m unittest discover -s tests
QT_QPA_PLATFORM=offscreen .venv/bin/python -c "from PySide6.QtWidgets import QApplication; from ide.app.application import IDEApplication; app=QApplication([]); app.setStyle('Fusion'); ide=IDEApplication(); shell=ide.show(); app.processEvents(); shell.close(); print('ui ok')"
```

## Results

- `python3 -m compileall ide main.py`: passed.
- `python3 -m unittest discover -s tests`: passed, 23 tests.
- Offscreen PySide6 shell construction smoke test: passed.
- Offscreen smoke test confirmed Project Explorer and Diagnostics/Output docks are visible/restorable at startup.

## Manual Launch

Run the GUI shell with:

```bash
python3 main.py
```

If PySide6 is installed under a framework Python on macOS, use the interpreter that owns that installation, as described in `README.md`.

## Coverage Intent

The tests exercise non-UI architecture seams:

- project creation, switching, and artefact registration
- artefact persistence boundary
- Python and Java completion from keywords, file symbols, and project symbols
- Python and Java language-service metadata extraction
- Java package-name extraction for compile/run support
- structured static-analysis diagnostics and skeletal dynamic-analysis boundary
- Python debugger state transitions, breakpoints, and locals
- test-service heuristic classification and unittest execution output
- conformance checks for code/design mismatches and traceability inconsistencies
- basic traceability links
- autosave revision boundary
- `.bscode` sidecar persistence for notes, traceability links, and revisions

GUI behaviour is intentionally not automated. The UI remains manually smoke-testable through `main.py`.

## Intentional Limitations

- Collaboration networking is represented by a local `NetworkSync` boundary and presence stub.
- Static analysis and conformance are lightweight but real; dynamic analysis is a boundary only and does not produce diagnostics.
- Java compile/run support uses local `javac` and `java` where a JDK is installed.
- Build automation remains a service/UI boundary.
- Python debugging is minimal and real; Java debugging is intentionally not implemented.
- Class diagram generation from code and advanced/LSP-style completion are intentionally not implemented.
- Help, search, notes, traceability, and tests are intentionally simple smoke-level mechanisms.
- Report source, references, and word-count handling are intentionally left to the report author.
