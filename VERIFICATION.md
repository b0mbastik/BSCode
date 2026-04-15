# Verification Notes

## Commands Run

```bash
python3 -m compileall ide main.py
python3 -m unittest discover -s tests
```

## Results

- `python3 -m compileall ide main.py`: passed.
- `python3 -m unittest discover -s tests`: passed, 16 tests.

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
- Python and Java language-service metadata extraction
- Java package-name extraction for compile/run support
- analysis-manager orchestration
- debugger session startup and pause/stop flow
- Git status adapter against a temporary repository
- test-service heuristic classification and real `unittest discover` execution
- traceability links
- revision checkpoints
- `.bscode` sidecar persistence for comments, traceability links, and revisions

GUI behaviour is intentionally not automated. The UI remains manually smoke-testable through `main.py`.

## Intentional Limitations

- Collaboration networking is represented by a local `NetworkSync` boundary and presence stub.
- Static and dynamic analysis are outline implementations, not production analysers.
- Java compile/run support uses local `javac` and `java` where a JDK is installed.
- Build automation remains a service boundary; debugger and VCS operations have working prototype implementations.
- Report source, references, and word-count handling are intentionally left to the report author.
