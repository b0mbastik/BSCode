"""Executable entry point for the desktop IDE shell."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from ide.app.application import IDEApplication


def main() -> int:
    qt_app = QApplication(sys.argv)
    ide_app = IDEApplication()
    ide_app.show()
    return qt_app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
