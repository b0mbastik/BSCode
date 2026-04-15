"""Published extension contracts for the Architecture Driven IDE.

This module is the stable public API for plugin developers. All
protocols defined here are versioned independently of the internal
implementation. A plugin that imports only from this module will remain
compatible across internal refactors.

Quick-start
-----------
1. Choose the protocol you want to implement (e.g. ``LanguageExtension``).
2. Write a class that satisfies the protocol (no inheritance required).
3. Register it with ``IDEApplication`` inside your entry-point::

       from ide.extensions.contracts import LanguageExtension
       from ide.domain.models import AnalysisSnapshot, PluginMetadata

       class MyLangSvc:
           name = "mylang"
           file_extensions = [".my"]

           def complete(self, source, line, column): return []
           def highlight(self, source): return []
           def parse(self, source, artifact_id):
               return AnalysisSnapshot(artifact_id=artifact_id)

       app.register_language_extension(MyLangSvc(), [".my"])
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ide.domain.models import (
    AnalysisResult,
    AnalysisSnapshot,
    Artifact,
    Project,
    TestRunResult,
    ToolExecutionResult,
)



@runtime_checkable
class LanguageExtension(Protocol):
    """Add a new programming or markup language to the IDE.

    The IDE calls these methods on a per-file basis. All methods must be
    safe to call with arbitrary untrusted source text.
    """

    #: Short identifier used to look up this service (e.g. ``"python"``).
    name: str
    #: File extensions this service handles (e.g. ``[".py", ".pyw"]``).
    file_extensions: list[str]

    def complete(self, source: str, line: int, column: int) -> list[str]:
        """Return completion candidates at *line*/*column* (1-based)."""
        ...

    def highlight(self, source: str) -> list[tuple[int, int, str]]:
        """Return ``(start, end, token_type)`` spans for syntax highlighting."""
        ...

    def parse(self, source: str, artifact_id: str) -> AnalysisSnapshot:
        """Parse *source* and return a structured metadata snapshot."""
        ...



@runtime_checkable
class AnalysisExtension(Protocol):
    """Contribute custom static analysis diagnostics.

    The IDE calls ``analyse`` after every debounced edit and on explicit
    'Run Static Analysis'.  Results are merged with the built-in analyser.
    """

    name: str

    def analyse(self, artifacts: list[Artifact]) -> AnalysisResult:
        """Analyse *artifacts* and return an ``AnalysisResult``."""
        ...



@runtime_checkable
class BuildExtension(Protocol):
    """Integrate a build system or compilation step.

    The IDE calls ``run`` when the user triggers 'Run Build'.
    Return a ``(success, output)`` pair; ``output`` is appended to the
    Output panel verbatim.
    """

    name: str

    def run(self, project: Project) -> ToolExecutionResult:
        """Execute the build for *project* and return the result."""
        ...



@runtime_checkable
class TestExtension(Protocol):
    """Integrate a test framework such as pytest, unittest, or jest.

    The IDE calls ``run_tests`` when the user triggers 'Run Tests'.
    The returned ``TestRunResult`` drives the Test Results panel and the
    dynamic analysis pass.
    """

    name: str

    def run_tests(self, project: Project, artifacts: list[Artifact]) -> TestRunResult:
        """Discover and run all tests for *project* and return results."""
        ...



@runtime_checkable
class ThemeExtension(Protocol):
    """Provide a Qt stylesheet that overrides the default IDE appearance.

    The stylesheet is applied to the ``QApplication`` instance at startup
    and whenever the user activates the theme.
    """

    name: str
    #: A complete Qt stylesheet string.
    stylesheet: str



@runtime_checkable
class VCSExtension(Protocol):
    """Integrate a version-control system.

    The IDE calls ``commit`` when the user triggers 'VCS > Commit'.
    Additional operations (diff, log, branch) may be added in future versions.
    """

    name: str

    def commit(self, project: Project, message: str) -> ToolExecutionResult:
        """Commit staged changes with *message* and return the result."""
        ...
