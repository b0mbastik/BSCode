"""Shared typed models for the IDE skeleton."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4


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


@dataclass(slots=True)
class Diagnostic:
    message: str
    severity: DiagnosticSeverity = DiagnosticSeverity.INFO
    line: int = 1
    column: int = 1
    source: str = "analysis"


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


@dataclass(slots=True)
class ToolExecutionResult:
    success: bool
    command: str
    output: str
    exit_code: int = 0


@dataclass(slots=True)
class PluginMetadata:
    name: str
    version: str
    extension_point: str
    description: str = ""
