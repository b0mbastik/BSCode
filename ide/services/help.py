"""Minimal help text boundary for the IDE shell."""

from __future__ import annotations


class HelpService:
    """Provides a static help page; richer topic browsing is future work."""

    def overview(self) -> str:
        return (
            "Architecture Driven Collaborative IDE\n\n"
            "Core prototype areas:\n"
            "- Project selector and project explorer\n"
            "- Code editor with syntax highlighting\n"
            "- Editable architecture and design artefacts\n"
            "- Basic run, test, static analysis, and VCS entry points\n"
            "- Collaboration, notes, and traceability panels as service boundaries\n\n"
            "Several standard IDE features are intentionally skeletal, including "
            "debugging, completion, dynamic analysis, and build automation."
        )

    def about(self) -> str:
        return (
            "Architecture Driven Collaborative IDE\n\n"
            "Outline implementation for collaborative architecture-driven "
            "software development. The code emphasises architectural structure "
            "and replaceable service boundaries over complete production behaviour."
        )
