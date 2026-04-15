# Coursework Completion Work Log

## Audit

- Existing code already follows the intended layered architecture: presentation, workspace, core services, analysis, infrastructure, domain, and application composition root.
- Existing outline behaviours include editor tabs, project explorer, design canvas, test runner, search, help topics, traceability, comments, revision history, collaboration presence, build/VCS/debug service boundaries, and persistence/network/plugin seams.
- Main missing submission artefacts were editable diagram source files, Java outline language support, visible multi-project switching, smoke tests, verification notes, and a submission checklist.

## Implementation Plan

- Preserve the current architecture and add only high-value coursework gaps.
- Add Java as a skeletal language service through the same plugin path as Python.
- Add a visible project selector that switches between projects already managed by `ProjectManager`.
- Include live design-diagram text in project search without persisting temporary search artefacts.
- Add Mermaid diagram sources under `docs/report/diagrams/`.
- Add lightweight `unittest` smoke tests for non-UI classes and document verification.

## Intentional Limits

- No production networking, CRDT/OT, debugger backend, Git implementation, build system, Java compiler integration, or full static-analysis engine.
- No report draft, references document, or word-count file is created in this pass.
- GUI behaviour is kept smoke-testable manually; automated tests focus on non-UI architecture seams.
