# ADR-0002: Python with PySide6 for a desktop application

- **Status:** Proposed
- **Date:** 2026-10-10

## Context
The owner wants a desktop application with a user-friendly GUI that shows review results visually. Most of the work is text parsing (Markdown, HTML) and LLM calls; the GUI shows tables, charts and highlighted passages side by side.

## Decision
Use **Python 3.12** for all code and **PySide6** (Qt 6, official Qt for Python bindings, LGPL) for the GUI:
- Qt Widgets for the main window, tables and forms
- custom-painted widgets for score rings, bar charts and heatmaps (Qt Charts available if needed)
- `QTextBrowser` to render passages and comparisons as HTML (lighter than `QWebEngineView`, which can be added later if richer HTML is needed)

Tooling: `uv` for environments and dependencies, `pytest` and `pytest-qt` for tests, `ruff` for lint and format, `mypy` for types.

## Consequences
- One language for core and GUI; the core is testable without Qt.
- Strong libraries are available for the core work: `markdown-it-py`, `beautifulsoup4`/`lxml`, `pydantic`, `httpx`, `openai`, `anthropic`, `rapidfuzz`.
- Desktop packaging (PyInstaller or Briefcase) needs its own decision later.
- Qt layouts are less flexible than web CSS; HTML in `QTextBrowser` fills that gap where richer rendering is needed.

## Alternatives considered
- **Electron + React (TypeScript)** – best-looking UI options, but two languages and a separate backend process for the parsing and LLM logic; heavier install.
- **Tauri + web frontend** – small binaries, but Rust plus JavaScript plus Python for the core logic.
- **Web app on localhost** – not a desktop app as requested.
- **Tkinter** – no charts or HTML rendering of comparable quality.
