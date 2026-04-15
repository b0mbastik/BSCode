# Verification Notes

## Commands Run

```bash
python3 -m compileall ide main.py
python3 -m unittest discover -s tests
```

## Results

- `python3 -m compileall ide main.py`: passed.
- `python3 -m unittest discover -s tests`: passed, 10 tests.

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
- analysis-manager orchestration
- test-service classification
- traceability links
- revision checkpoints

GUI behaviour is intentionally not automated. The UI remains manually smoke-testable through `main.py`.

## Intentional Limitations

- Collaboration networking is represented by a local `NetworkSync` boundary and presence stub.
- Static and dynamic analysis are outline implementations, not production analysers.
- Java support is a skeletal language-service plugin, not compiler integration.
- Build, debug, and VCS integrations are service boundaries with stubbed behaviour.
- Report source, references, and word-count handling are intentionally left to the report author.
