"""Load default building maps from JSON files in app/maps/."""

from __future__ import annotations

import json
from pathlib import Path

from app.domain.building import BuildingLayout

MAPS_DIR = Path(__file__).resolve().parent.parent / "maps"

# Stable filenames for helpers used by tests.
_SEED_MAP = "two-floor-office.json"
_DUAL_NYC_MAP = "dual-nyc-office-template-2001.json"
_TITANIC_MAP = "rms-titanic.json"
_OVAL_STADIUM_MAP = "oval-stadium.json"
_TWIN_TOWER_MAP = "twin-towers-20m.json"


def parse_layout_json(data: object) -> BuildingLayout:
    """Parse a layout from either a raw layout object or the export wrapper."""
    if not isinstance(data, dict):
        raise ValueError("Map JSON must be an object")
    if data.get("format") == "evacuation-simulation-layout":
        layout_data = data.get("layout")
        if not isinstance(layout_data, dict):
            raise ValueError("Export wrapper is missing a layout object")
        return BuildingLayout.model_validate(layout_data)
    return BuildingLayout.model_validate(data)


def load_map_file(path: Path) -> BuildingLayout:
    """Load and validate one map JSON file."""
    return parse_layout_json(json.loads(path.read_text(encoding="utf-8")))


def iter_default_maps(maps_dir: Path | None = None) -> list[tuple[Path, BuildingLayout]]:
    """Return all *.json maps from the default maps folder, sorted by filename."""
    directory = maps_dir if maps_dir is not None else MAPS_DIR
    if not directory.is_dir():
        return []
    maps: list[tuple[Path, BuildingLayout]] = []
    for path in sorted(directory.glob("*.json")):
        maps.append((path, load_map_file(path)))
    return maps


def load_default_map(filename: str) -> BuildingLayout:
    """Load a named file from the default maps folder."""
    return load_map_file(MAPS_DIR / filename)


def create_seed_layout() -> BuildingLayout:
    return load_default_map(_SEED_MAP)


def create_23_floor_template() -> BuildingLayout:
    return load_default_map(_DUAL_NYC_MAP)


def create_titanic_template() -> BuildingLayout:
    return load_default_map(_TITANIC_MAP)


def create_oval_stadium_template() -> BuildingLayout:
    return load_default_map(_OVAL_STADIUM_MAP)


def create_twin_tower_template() -> BuildingLayout:
    return load_default_map(_TWIN_TOWER_MAP)
