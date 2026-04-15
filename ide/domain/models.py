"""Shared typed models for the IDE skeleton."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4


# ---------------------------------------------------------------------------
# Artefact / project core
# ---------------------------------------------------------------------------

class ArtifactType(str, Enum):
    CODE = "code"
    ARCHITECTURE = "architecture"
    DESIGN = "design"
    TEST = "test"


class DiagnosticSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(slots=True)
class Artifact:
    name: str
    artifact_type: ArtifactType
    content: str = ""
    path: Path | None = None
    language: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    artifact_id: str = field(default_factory=lambda: str(uuid4()))


@dataclass(slots=True)
class Project:
    name: str
    root_path: Path
    artifacts: list[str] = field(default_factory=list)
    project_id: str = field(default_factory=lambda: str(uuid4()))


# ---------------------------------------------------------------------------
# User / session
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class UserSession:
    user_id: str
    display_name: str
    authenticated: bool = False


@dataclass(slots=True)
class PeerSession:
    peer_id: str
    display_name: str
    active_artifact_id: str | None = None
    active_artifact_name: str | None = None


# ---------------------------------------------------------------------------
# Editing operations / buffers
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class Operation:
    artifact_id: str
    user_id: str
    position: int
    delete_count: int = 0
    text: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class TextBuffer:
    content: str = ""

    def apply(self, operation: Operation) -> None:
        start = max(0, min(operation.position, len(self.content)))
        end = max(start, min(start + operation.delete_count, len(self.content)))
        self.content = self.content[:start] + operation.text + self.content[end:]


# ---------------------------------------------------------------------------
# Diagnostics / analysis
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class Diagnostic:
    message: str
    severity: DiagnosticSeverity = DiagnosticSeverity.INFO
    line: int = 1
    column: int = 1
    source: str = "analysis"
    artifact_id: str | None = None


@dataclass(slots=True)
class AnalysisSnapshot:
    artifact_id: str
    code_metadata: dict[str, Any] = field(default_factory=dict)
    architecture_metadata: dict[str, Any] = field(default_factory=dict)
    design_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AnalysisResult:
    diagnostics: list[Diagnostic] = field(default_factory=list)
    summary: str = "No analysis has been run."
    snapshot: AnalysisSnapshot | None = None


# ---------------------------------------------------------------------------
# Test execution
# ---------------------------------------------------------------------------

class TestStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass(slots=True)
class TestCase:
    name: str
    status: TestStatus = TestStatus.PASSED
    duration_ms: float = 0.0
    message: str = ""
    artifact_id: str | None = None
    line: int | None = None


@dataclass
class TestSuite:
    name: str
    cases: list[TestCase] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for c in self.cases if c.status is TestStatus.PASSED)

    @property
    def failed(self) -> int:
        return sum(1 for c in self.cases if c.status is TestStatus.FAILED)

    @property
    def errors(self) -> int:
        return sum(1 for c in self.cases if c.status is TestStatus.ERROR)

    @property
    def skipped(self) -> int:
        return sum(1 for c in self.cases if c.status is TestStatus.SKIPPED)


@dataclass
class TestRunResult:
    suites: list[TestSuite] = field(default_factory=list)
    summary: str = "No tests have been run."
    success: bool = True
    command: str = ""

    @property
    def total_passed(self) -> int:
        return sum(s.passed for s in self.suites)

    @property
    def total_failed(self) -> int:
        return sum(s.failed for s in self.suites)

    @property
    def total_errors(self) -> int:
        return sum(s.errors for s in self.suites)

    @property
    def total_skipped(self) -> int:
        return sum(s.skipped for s in self.suites)


# ---------------------------------------------------------------------------
# Design-to-implementation traceability
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class TraceLink:
    link_id: str = field(default_factory=lambda: str(uuid4()))
    design_artifact_id: str = ""
    design_element: str = ""
    code_artifact_id: str = ""
    code_element: str = ""
    description: str = ""


# ---------------------------------------------------------------------------
# Comments / annotations
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class Comment:
    comment_id: str = field(default_factory=lambda: str(uuid4()))
    artifact_id: str = ""
    line: int = 1
    author: str = ""
    body: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Version history
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class Revision:
    revision_id: str = field(default_factory=lambda: str(uuid4()))
    artifact_id: str = ""
    content: str = ""
    author: str = ""
    message: str = "Checkpoint"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Collaboration / sync
# ---------------------------------------------------------------------------

class SyncStatus(str, Enum):
    IDLE = "idle"
    PENDING = "pending"
    SYNCING = "syncing"
    CONFLICT = "conflict"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Build / tool execution
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class ToolExecutionResult:
    success: bool
    command: str
    output: str
    exit_code: int = 0


# ---------------------------------------------------------------------------
# Plugins
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class PluginMetadata:
    name: str
    version: str
    extension_point: str
    description: str = ""
