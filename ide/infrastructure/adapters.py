"""Infrastructure boundaries for platform, persistence, network, and plugins."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ide.domain.models import Artifact, Operation, PluginMetadata, Revision, SyncStatus


class PlatformAbstraction:
    """Small platform boundary for cross-platform filesystem concerns."""

    def normalise_path(self, path: str | Path) -> Path:
        return Path(path).expanduser().resolve()

    def application_data_dir(self) -> Path:
        return Path.home() / ".architecture_ide"



class Persistence(ABC):
    """Storage boundary for artefact persistence."""

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


class FilesystemPersistence(Persistence):
    """Filesystem persistence boundary.

    The outline implementation keeps an in-memory cache only.  Real file writes
    are intentionally omitted so persistence remains a design seam rather than
    a fully implemented storage layer.
    """

    def __init__(self) -> None:
        self._cache: dict[str, Artifact] = {}

    def save_artifact(self, artifact: Artifact) -> None:
        self._cache[artifact.artifact_id] = artifact

    def load_artifact(self, artifact_id: str) -> Artifact | None:
        return self._cache.get(artifact_id)



class RevisionLog:
    """Revision-history boundary.

    Only enough in-memory state is retained to show how autosave/checkpoint
    services collaborate with a log.  Rich revision browsing is out of scope.
    """

    MAX_PER_ARTIFACT = 50

    def __init__(self) -> None:
        self._log: dict[str, deque[Revision]] = {}

    def record(self, revision: Revision) -> None:
        bucket = self._log.setdefault(revision.artifact_id, deque(maxlen=self.MAX_PER_ARTIFACT))
        bucket.appendleft(revision)

    def get_history(self, artifact_id: str) -> list[Revision]:
        """Return revisions newest-first."""
        return list(self._log.get(artifact_id, []))

    def all_revisions(self) -> list[Revision]:
        return [revision for bucket in self._log.values() for revision in bucket]

    def replace_all(self, revisions: list[Revision]) -> None:
        self._log.clear()
        for revision in sorted(revisions, key=lambda revision_item: revision_item.timestamp, reverse=False):
            self.record(revision)

    def clear(self, artifact_id: str) -> None:
        self._log.pop(artifact_id, None)



class NetworkSync:
    """Remote collaboration transport boundary.

    No remote transport is implemented.  The class only records the most recent
    operation and exposes status-listener hooks used by the presentation layer.
    """

    def __init__(self) -> None:
        self._queue: list[Operation] = []
        self.status: SyncStatus = SyncStatus.IDLE
        self.endpoint: str = ""
        self.last_sent_operation: Operation | None = None
        self._status_listeners: list[Callable[[SyncStatus], None]] = []

    def connect(self, endpoint: str) -> None:
        self.endpoint = endpoint

    def add_status_listener(self, listener: Callable[[SyncStatus], None]) -> None:
        """Register a callable(SyncStatus) that is notified on status changes."""
        self._status_listeners.append(listener)

    def send(self, operation: Operation) -> None:
        self.last_sent_operation = operation
        self._set_status(SyncStatus.IDLE)

    def broadcast(self, operation: Operation) -> None:
        self.send(operation)

    def simulate_conflict(self) -> None:
        """Test hook: put the sync layer into CONFLICT state."""
        self._set_status(SyncStatus.CONFLICT)

    def resolve_conflict(self) -> None:
        """Test hook: clear the CONFLICT state."""
        self._set_status(SyncStatus.IDLE)

    def _flush(self) -> None:
        """Reserved for a future asynchronous transport adapter."""
        self._queue.clear()
        self._set_status(SyncStatus.IDLE)

    def _set_status(self, status: SyncStatus) -> None:
        if self.status != status:
            self.status = status
            for listener in self._status_listeners:
                try:
                    listener(status)
                except Exception:
                    # Listener failures must not block collaboration state updates.
                    pass



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
