"""Executable entry point for the desktop IDE shell."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QStyleFactory

from ide.app.application import IDEApplication


def main() -> int:
    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName("Architecture Driven Collaborative IDE")
    if "Fusion" in QStyleFactory.keys():
        qt_app.setStyle("Fusion")
    ide_app = IDEApplication()
    ide_app.show()
    return qt_app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
