"""Rule-tier checks (ADR-0006). Importing this package registers them."""

from umr.checks.rules import code, duplicates, images, links, numbering, orphans, ui_labels, versions

__all__ = ["code", "duplicates", "images", "links", "numbering", "orphans", "ui_labels", "versions"]
