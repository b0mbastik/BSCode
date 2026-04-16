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
            "- Run, test, debug, analysis, VCS, and build service boundaries\n"
            "- Collaboration, notes, and traceability panels as architectural seams\n\n"
            "The implementation is deliberately skeletal: most features preserve "
            "interfaces and interactions but omit real algorithms/tool execution."
        )

    def about(self) -> str:
        return (
            "Architecture Driven Collaborative IDE\n\n"
            "Architecture-first outline implementation for collaborative "
            "architecture-driven software development. The code emphasises "
            "subsystem structure and replaceable service boundaries."
        )
