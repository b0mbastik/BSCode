"""Contextual help service with a registry of help topics."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class HelpTopic:
    title: str
    content: str
    keywords: list[str] = field(default_factory=list)
    topic_id: str = ""


# ---------------------------------------------------------------------------
# Built-in topic catalogue
# ---------------------------------------------------------------------------

_TOPICS: list[HelpTopic] = [
    HelpTopic(
        topic_id="editor",
        title="Code Editor",
        keywords=["edit", "code", "file", "tab", "save", "open"],
        content=(
            "The code editor opens text files in tabs at the centre of the window.\n\n"
            "Shortcuts:\n"
            "  Ctrl+O            Open a file\n"
            "  Ctrl+S            Save the active file\n"
            "  Ctrl+Shift+O      Open a project folder\n"
            "  Ctrl+W            Close the active tab\n\n"
            "Auto-save: edits are written to disk automatically. "
            "Press Ctrl+S to create an explicit version checkpoint."
        ),
    ),
    HelpTopic(
        topic_id="analysis",
        title="Static Analysis",
        keywords=["analyse", "analysis", "diagnostic", "warning", "error", "conformance"],
        content=(
            "Static analysis runs automatically 400 ms after each edit and can also "
            "be triggered manually via Analyse > Run Static Analysis (Ctrl+Shift+A).\n\n"
            "Results appear in the Diagnostics panel at the bottom and are "
            "highlighted inline in the editor.\n\n"
            "Conformance checking compares class names in your code against the "
            "architecture component names defined in the project."
        ),
    ),
    HelpTopic(
        topic_id="tests",
        title="Test Runner",
        keywords=["test", "pytest", "run", "pass", "fail", "suite"],
        content=(
            "Run > Run Tests (Ctrl+T) discovers test files (test_*.py / *_test.py) "
            "in the active project and simulates a pytest run.\n\n"
            "Results are shown in the Test Results panel at the bottom. "
            "Each suite can be expanded to see individual test cases with their "
            "status (passed / failed / skipped / error) and duration.\n\n"
            "Dynamic analysis is triggered automatically after each test run and "
            "produces additional diagnostics for failing tests."
        ),
    ),
    HelpTopic(
        topic_id="search",
        title="Project Search",
        keywords=["search", "find", "grep", "text", "query"],
        content=(
            "Edit > Find in Project (Ctrl+Shift+F) searches across every open "
            "artefact — code, architecture documents, design notes, and test files.\n\n"
            "Results appear in the Search Results panel with the artefact name, "
            "line number, and surrounding context. Double-click a result to "
            "jump to that artefact and line."
        ),
    ),
    HelpTopic(
        topic_id="traceability",
        title="Design-to-Code Traceability",
        keywords=["trace", "traceability", "link", "design", "architecture", "mapping"],
        content=(
            "The Traceability panel (right dock) lets you create explicit links "
            "between design elements and their code implementations.\n\n"
            "Click 'Add Link' and fill in the design artefact, element name, "
            "target code artefact, and element name. Links are stored in-project "
            "and can be reviewed or deleted at any time."
        ),
    ),
    HelpTopic(
        topic_id="comments",
        title="Comments & Annotations",
        keywords=["comment", "annotation", "note", "review"],
        content=(
            "The Comments panel (right dock) shows all annotations attached to "
            "the currently active artefact.\n\n"
            "Click 'Add Comment' to attach a note to a specific line. "
            "Comments include the author name (from your session), a line number, "
            "and free-text body."
        ),
    ),
    HelpTopic(
        topic_id="versioning",
        title="Version History",
        keywords=["version", "history", "revision", "checkpoint", "undo", "restore"],
        content=(
            "Every explicit Ctrl+S creates a revision checkpoint for the active file.\n\n"
            "View > Version History shows the full checkpoint list with author, "
            "timestamp, and message. Select a revision and click 'Restore' to "
            "revert the file to that snapshot."
        ),
    ),
    HelpTopic(
        topic_id="collaboration",
        title="Collaboration & Presence",
        keywords=["collab", "collaboration", "peer", "presence", "sync", "network"],
        content=(
            "The Collaboration panel (right dock) shows the list of connected peers "
            "and which artefact each is currently editing.\n\n"
            "All local edits are broadcast to peers via the operation queue. "
            "The sync status indicator in the status bar shows IDLE / PENDING / "
            "SYNCING / CONFLICT.\n\n"
            "In this prototype the network layer is stubbed; a real transport "
            "can be plugged in by replacing NetworkSync in infrastructure/adapters.py."
        ),
    ),
    HelpTopic(
        topic_id="diagrams",
        title="Architecture & Design Diagrams",
        keywords=["diagram", "design", "component", "uml", "sequence", "deployment", "layered"],
        content=(
            "The Design tab in the centre panel provides text-based editors for "
            "five diagram types:\n\n"
            "  • Component View   — box-and-connector components\n"
            "  • Layered View     — horizontal architecture tiers\n"
            "  • Deployment View  — nodes, containers, and artefacts\n"
            "  • UML Class        — classes, attributes, methods, relationships\n"
            "  • UML Sequence     — lifelines and message flows\n\n"
            "Each diagram tab starts with a template. Edit the DSL text; "
            "a real implementation would render it graphically."
        ),
    ),
    HelpTopic(
        topic_id="plugins",
        title="Extension API",
        keywords=["plugin", "extension", "api", "custom", "language"],
        content=(
            "The published extension API lives in ide/extensions/contracts.py. "
            "Implement one of the protocol classes and register it with the "
            "PluginRegistry in IDEApplication._register_builtin_plugins().\n\n"
            "Available extension points:\n"
            "  LanguageExtension    — syntax, completion, parse\n"
            "  AnalysisExtension    — custom static analysers\n"
            "  BuildExtension       — build-system integrations\n"
            "  TestExtension        — test-framework integrations\n"
            "  ThemeExtension       — UI theme / stylesheet"
        ),
    ),
]

_TOPIC_INDEX: dict[str, HelpTopic] = {t.topic_id: t for t in _TOPICS}


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class HelpService:
    """Provides contextual and keyword-driven help topics."""

    def get_topic(self, topic_id: str) -> HelpTopic | None:
        return _TOPIC_INDEX.get(topic_id)

    def get_contextual_help(self, context: str) -> HelpTopic:
        """Return the most relevant topic for a UI context string.

        The context string is a free-form label such as the name of a dock,
        menu, or widget (e.g. "editor", "diagnostics", "test_results").
        """
        context_lower = context.lower()
        # Try exact topic_id match first.
        if context_lower in _TOPIC_INDEX:
            return _TOPIC_INDEX[context_lower]
        # Keyword scan.
        for topic in _TOPICS:
            if any(kw in context_lower for kw in topic.keywords):
                return topic
        return self._default_topic()

    def search_help(self, query: str) -> list[HelpTopic]:
        """Return topics whose title, id, or keywords mention *query*."""
        q = query.lower()
        return [
            t for t in _TOPICS
            if q in t.title.lower()
            or q in t.topic_id
            or any(q in kw for kw in t.keywords)
            or q in t.content.lower()
        ]

    def all_topics(self) -> list[HelpTopic]:
        return list(_TOPICS)

    def register_topic(self, topic: HelpTopic) -> None:
        """Allow plugins to add their own help topics at runtime."""
        _TOPICS.append(topic)
        _TOPIC_INDEX[topic.topic_id] = topic

    @staticmethod
    def _default_topic() -> HelpTopic:
        return HelpTopic(
            topic_id="overview",
            title="IDE Overview",
            keywords=[],
            content=(
                "Architecture Driven Collaborative IDE\n\n"
                "Key areas:\n"
                "  • File > Open File / Open Project — load files and directories\n"
                "  • Run > Run Tests                 — execute test suites\n"
                "  • Analyse > Run Static Analysis   — check diagnostics\n"
                "  • Edit > Find in Project          — search all artefacts\n"
                "  • View > Version History          — checkpoint history\n"
                "  • Design tab                      — architecture diagrams\n"
                "  • Right docks                     — collaboration, comments, traceability\n\n"
                "Press F1 anywhere for contextual help."
            ),
        )
