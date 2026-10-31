import json
from pathlib import Path

import pytest


@pytest.fixture
def skins_root(tmp_path: Path) -> Path:
    root = tmp_path / "skins"
    root.mkdir()
    return root


@pytest.fixture
def foreign_skin(skins_root: Path) -> Path:
    """A skin someone else made (no FM Skin Studio marker)."""
    folder = skins_root / "someone-elses-skin"
    folder.mkdir()
    (folder / "skin.json").write_text(json.dumps({"Name": "Their Skin", "Sheets": ["theme.uss"]}), encoding="utf-8")
    (folder / "theme.uss").write_text(":root { --global-text-primary: rgb(1, 2, 3); }\n", encoding="utf-8")
    return folder


def make_layout(panels: list[dict]) -> dict:
    """Synthetic layout in the game's JSON shape (ids scrubbed)."""
    return {
        "m_compositionVersion": 1, "m_gridBreakpoint": 3, "m_layoutMode": 0,
        "m_layoutPreset": {"Name": "Fullscreen", "Size": {"x": 0, "y": 0}}, "m_allowedTags": [],
        "m_contentAlignment": 0,
        "m_gridComponents": [{
            "m_elementID": p["id"], "m_configDescriptions": [{"instanceID": 1}], "m_configDescriptionKeys": [p["id"]],
            "m_gridElementConfigs": [], "m_location": {"x": p["x"], "y": p["y"], "width": p["w"], "height": p["h"]},
            "m_minSize": {"x": p.get("minW", 1), "y": p.get("minH", 1)},
            "m_maxSize": {"x": p.get("maxW", 100), "y": p.get("maxH", 100)},
            "m_isLocked": p.get("locked", False), "m_isDebug": False, "m_isDynamic": False, "m_features": 0,
            "m_expandToContent": False, "m_takesFocus": False, "m_isOptional": False,
            "m_horizontalAlignment": 0, "m_verticalAlignment": 0,
        } for p in panels],
        "m_optionalSlices": {"m_contentModeX": 0, "m_contentModeY": 0, "m_overrideSlicesOrder": False,
                             "m_instantiationOrder": [], "m_bottom": []},
    }


def default_for(layout: dict, name: str = "TestGridComposition-Large", columns: int = 20) -> dict:
    from fmskin.index import _composition
    tree = dict(layout, m_Name=name)
    comp = _composition(tree, "test.bundle")
    comp["columns"] = columns
    return comp
