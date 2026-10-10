"""Load journeys and manuals from disk (ADR-0005)."""

from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError

from umr.domain import Journey, Manual
from umr.ingest.html import parse_html
from umr.ingest.markdown import parse_markdown

MD_EXT = {".md", ".markdown"}
HTML_EXT = {".html", ".htm"}


class IngestError(Exception):
    pass


class ManualYaml(BaseModel):
    id: str | None = None
    title: str
    version: str | None = None
    entry: str | None = None


class JourneyYaml(BaseModel):
    name: str
    description: str = ""
    manuals: list[str]
    reference: dict[str, str] = {}


def _read_yaml(path: Path) -> dict[str, object]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise IngestError(f"{path}: invalid YAML: {e}") from e
    if not isinstance(data, dict):
        raise IngestError(f"{path}: expected a mapping at the top level")
    return data


def load_manual(folder: Path) -> Manual:
    folder = folder.resolve()
    if not folder.is_dir():
        raise IngestError(f"Manual folder not found: {folder}")
    meta_path = folder / "manual.yaml"
    if meta_path.exists():
        try:
            meta = ManualYaml.model_validate(_read_yaml(meta_path))
        except ValidationError as e:
            raise IngestError(f"{meta_path}: {e}") from e
    else:
        meta = ManualYaml(title=folder.name)
    manual_id = meta.id or folder.name
    manual = Manual(id=manual_id, title=meta.title, version=meta.version, entry=meta.entry, root_path=folder)
    for f in sorted(folder.rglob("*")):
        if not f.is_file():
            continue
        rel = f.relative_to(folder).as_posix()
        ext = f.suffix.lower()
        if ext in MD_EXT:
            manual.pages.append(parse_markdown(manual_id, rel, f))
        elif ext in HTML_EXT:
            manual.pages.append(parse_html(manual_id, rel, f))
    if not manual.pages:
        raise IngestError(f"No .md or .html files in {folder}")
    return manual


def load_journey(path: Path) -> Journey:
    """Load a journey.yaml, or a single manual folder as a one-manual journey."""
    path = path.resolve()
    if path.is_dir() and not (path / "journey.yaml").exists():
        manual = load_manual(path)
        return Journey(name=manual.title, root_path=path, manuals=[manual])
    if path.is_dir():
        path = path / "journey.yaml"
    if not path.exists():
        raise IngestError(f"Journey file not found: {path}")
    try:
        meta = JourneyYaml.model_validate(_read_yaml(path))
    except ValidationError as e:
        raise IngestError(f"{path}: {e}") from e
    root = path.parent
    journey = Journey(name=meta.name, description=meta.description, root_path=root,
                      reference={k: (root / v).resolve() for k, v in meta.reference.items()})
    ids: set[str] = set()
    for rel in meta.manuals:
        manual = load_manual(root / rel)
        if manual.id in ids:
            raise IngestError(f"Duplicate manual id '{manual.id}' in {path}")
        ids.add(manual.id)
        journey.manuals.append(manual)
    for key, ref in journey.reference.items():
        if not ref.exists():
            raise IngestError(f"{path}: reference '{key}' not found: {ref}")
    return journey
