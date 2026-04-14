"""Workspace layer services."""

from __future__ import annotations

from pathlib import Path

from ide.domain.models import Artifact, Operation, PeerSession, Project, UserSession
from ide.infrastructure.adapters import NetworkSync, Persistence


class ProjectManager:
    def __init__(self) -> None:
        self.projects: dict[str, Project] = {}
        self.active_project: Project | None = None

    def create_project(self, name: str, root_path: Path) -> Project:
        project = Project(name=name, root_path=root_path)
        self.projects[project.project_id] = project
        self.active_project = project
        return project

    def switch_project(self, project_id: str) -> Project:
        if project_id not in self.projects:
            raise KeyError(f"Unknown project id: {project_id}")
        self.active_project = self.projects[project_id]
        return self.active_project

    def register_artifact(self, project: Project, artifact: Artifact) -> None:
        if artifact.artifact_id not in project.artifacts:
            project.artifacts.append(artifact.artifact_id)


class ArtifactStore:
    def __init__(self, persistence: Persistence) -> None:
        self.persistence = persistence
        self.artifacts: dict[str, Artifact] = {}

    def save(self, artifact: Artifact) -> None:
        self.artifacts[artifact.artifact_id] = artifact
        self.persistence.save_artifact(artifact)

    def load(self, artifact_id: str) -> Artifact | None:
        artifact = self.artifacts.get(artifact_id) or self.persistence.load_artifact(artifact_id)
        if artifact is not None:
            self.artifacts[artifact.artifact_id] = artifact
        return artifact

    def list_for_project(self, project: Project) -> list[Artifact]:
        return [artifact for artifact_id in project.artifacts if (artifact := self.load(artifact_id))]


class SessionManager:
    def __init__(self) -> None:
        self.current_session: UserSession | None = None

    def sign_in_guest(self, display_name: str = "Local User") -> UserSession:
        self.current_session = UserSession(
            user_id="local-user",
            display_name=display_name,
            authenticated=False,
        )
        return self.current_session


class CollabService:
    def __init__(self, network_sync: NetworkSync) -> None:
        self.network_sync = network_sync
        self.peers: list[PeerSession] = [
            PeerSession(peer_id="peer-ada", display_name="Ada"),
            PeerSession(peer_id="peer-grace", display_name="Grace"),
        ]
        self.crdt_document: str = ""

    def submit_op(self, operation: Operation) -> None:
        # TODO: Replace whole-document outline logic with a real CRDT.
        self.crdt_document = operation.text
        self.broadcast(operation)

    def broadcast(self, operation: Operation) -> None:
        self.network_sync.broadcast(operation)
