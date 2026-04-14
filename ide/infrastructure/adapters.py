"""Infrastructure boundaries for platform, persistence, network, and plugins."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from ide.domain.models import Artifact, Operation, PluginMetadata


class PlatformAbstraction:
    """Small platform boundary for cross-platform filesystem concerns."""

    def normalise_path(self, path: str | Path) -> Path:
        return Path(path).expanduser().resolve()

    def application_data_dir(self) -> Path:
        return Path.home() / ".architecture_ide"


class Persistence(ABC):
    """Storage/versioning boundary; replace with real persistence later."""

    @abstractmethod
    def save_artifact(self, artifact: Artifact) -> None:
        raise NotImplementedError

    @abstractmethod
    def load_artifact(self, artifact_id: str) -> Artifact | None:
        raise NotImplementedError


class InMemoryPersistence(Persistence):
    def __init__(self) -> None:
        self._artifacts: dict[str, Artifact] = {}

    def save_artifact(self, artifact: Artifact) -> None:
        self._artifacts[artifact.artifact_id] = artifact

    def load_artifact(self, artifact_id: str) -> Artifact | None:
        return self._artifacts.get(artifact_id)


class NetworkSync:
    """Remote collaboration transport boundary."""

    def connect(self, endpoint: str) -> None:
        self.endpoint = endpoint

    def send(self, operation: Operation) -> None:
        # TODO: Serialize and send operation over the selected transport.
        self.last_sent_operation = operation

    def broadcast(self, operation: Operation) -> None:
        self.send(operation)


class PluginRegistry:
    """Registry for future language, analysis, and tool integrations."""

    def __init__(self) -> None:
        self.languages: dict[str, Any] = {}
        self.analysers: dict[str, Any] = {}
        self.metadata: list[PluginMetadata] = []

    def register_language(self, name: str, service: Any, metadata: PluginMetadata) -> None:
        self.languages[name] = service
        self.metadata.append(metadata)

    def get_language(self, name: str) -> Any | None:
        return self.languages.get(name)

    def register_analyser(self, name: str, analyser: Any, metadata: PluginMetadata) -> None:
        self.analysers[name] = analyser
        self.metadata.append(metadata)

    def get_analyser(self, name: str) -> Any | None:
        return self.analysers.get(name)
