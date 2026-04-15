"""Workspace layer services."""

from __future__ import annotations

from pathlib import Path

from ide.domain.models import (
    Artifact,
    Comment,
    Operation,
    PeerSession,
    Project,
    Revision,
    UserSession,
)
from ide.infrastructure.adapters import NetworkSync, Persistence, RevisionLog


# ---------------------------------------------------------------------------
# Project management
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Artefact store
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Collaboration service  (presence + op broadcasting)
# ---------------------------------------------------------------------------

class CollabService:
    """Tracks peer presence and broadcasts local operations.

    Presence: each peer advertises the artefact they are currently editing
    via ``active_artifact_id`` / ``active_artifact_name`` on PeerSession.
    The local user's current artefact is updated via ``update_local_presence``.
    """

    def __init__(self, network_sync: NetworkSync) -> None:
        self.network_sync = network_sync
        self.peers: list[PeerSession] = [
            PeerSession(peer_id="peer-ada", display_name="Ada"),
            PeerSession(peer_id="peer-grace", display_name="Grace"),
        ]
        self.crdt_document: str = ""

    def submit_op(self, operation: Operation) -> None:
        # TODO: Replace whole-document snapshot with a real CRDT algorithm.
        self.crdt_document = operation.text
        self.broadcast(operation)

    def broadcast(self, operation: Operation) -> None:
        self.network_sync.broadcast(operation)

    def update_local_presence(
        self, artifact_id: str | None, artifact_name: str | None
    ) -> None:
        """Advertise which artefact the local user is currently editing.

        Simulates peer activity by having the first stub peer mirror the
        same artefact (in a real system this would come from the network).
        """
        if artifact_id and self.peers:
            self.peers[0].active_artifact_id = artifact_id
            self.peers[0].active_artifact_name = artifact_name

    def get_peers_editing(self, artifact_id: str) -> list[PeerSession]:
        """Return stub peers whose presence shows them editing *artifact_id*."""
        return [p for p in self.peers if p.active_artifact_id == artifact_id]


# ---------------------------------------------------------------------------
# Comment service
# ---------------------------------------------------------------------------

class CommentService:
    """Stores and retrieves inline comments/annotations on artefacts."""

    def __init__(self) -> None:
        self._comments: dict[str, list[Comment]] = {}  # artifact_id → comments

    def add_comment(self, comment: Comment) -> Comment:
        self._comments.setdefault(comment.artifact_id, []).append(comment)
        return comment

    def get_comments(self, artifact_id: str) -> list[Comment]:
        return list(self._comments.get(artifact_id, []))

    def remove_comment(self, comment_id: str) -> bool:
        for bucket in self._comments.values():
            for i, c in enumerate(bucket):
                if c.comment_id == comment_id:
                    bucket.pop(i)
                    return True
        return False

    def all_comments(self) -> list[Comment]:
        return [c for bucket in self._comments.values() for c in bucket]

    def replace_all(self, comments: list[Comment]) -> None:
        self._comments.clear()
        for comment in comments:
            self._comments.setdefault(comment.artifact_id, []).append(comment)


# ---------------------------------------------------------------------------
# Version service
# ---------------------------------------------------------------------------

class VersionService:
    """Creates explicit revision checkpoints and retrieves version history.

    Checkpoints are created on every explicit Ctrl+S save. Auto-saves on
    each keystroke do *not* create checkpoints to avoid revision log noise.
    """

    def __init__(self, revision_log: RevisionLog) -> None:
        self._log = revision_log

    def checkpoint(
        self,
        artifact: Artifact,
        author: str,
        message: str = "Manual save",
    ) -> Revision:
        revision = Revision(
            artifact_id=artifact.artifact_id,
            content=artifact.content,
            author=author,
            message=message,
        )
        self._log.record(revision)
        return revision

    def get_history(self, artifact_id: str) -> list[Revision]:
        return self._log.get_history(artifact_id)

    def all_revisions(self) -> list[Revision]:
        return self._log.all_revisions()

    def replace_all(self, revisions: list[Revision]) -> None:
        self._log.replace_all(revisions)
