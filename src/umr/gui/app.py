"""GUI entry point: `umr gui`, `python -m umr.gui`."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from umr.gui.main_window import APP_TITLE, MainWindow


def main(argv: list[str] | None = None) -> int:
    """Start the desktop app. An optional argument opens a journey (yaml or folder) or a run (.json)."""
    args = list(sys.argv if argv is None else argv)
    app = QApplication.instance() or QApplication(args)
    QApplication.setApplicationName(APP_TITLE)
    QApplication.setOrganizationName("UserManualReviewer")
    if isinstance(app, QApplication):
        app.setStyle("Fusion")  # follows the system light/dark colour scheme on every platform
    window = MainWindow()
    target = Path(args[1]) if len(args) > 1 else None
    if target is not None and target.suffix.lower() == ".json":
        window.open_initial_journey()
        window.open_run(target)
    elif target is not None:
        window.open_journey(target)
    else:
        window.open_initial_journey()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
