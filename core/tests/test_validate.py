import json

from conftest import default_for, make_layout

from fmskin import layouts, skinpack
from fmskin.validate import validate_pack

GAME_TOKENS = {"--global-text-primary": {}, "--layout-modules-block-surface": {}, "--typography-family-primary": {}}


def messages(problems, severity=None):
    return [p.message for p in problems if severity is None or p.severity == severity]


def test_clean_pack_has_no_errors(skins_root):
    pack = skinpack.create_pack(skins_root, "Clean")
    pack.set_tokens({"--global-text-primary": "rgb(255, 230, 0)"})
    assert messages(validate_pack(pack, GAME_TOKENS), "error") == []


def test_skin_json_rules(skins_root):
    pack = skinpack.create_pack(skins_root, "J")
    (pack.path / "skin.json").write_text(json.dumps({"name": "x", "sheets": ["tokens.uss"]}))
    msgs = messages(validate_pack(pack))
    assert any("must be spelled 'Name'" in m for m in msgs)
    assert any("lists no sheets" in m for m in msgs)
    (pack.path / "skin.json").write_text("{not json")
    assert "malformed" in messages(validate_pack(pack))[0]


def test_sheet_path_rules(skins_root):
    pack = skinpack.create_pack(skins_root, "P")
    (pack.path / "skin.json").write_text(json.dumps({"Name": "P", "Sheets": ["../escape.uss", "missing.uss", "a.css"]}))
    (pack.path / "a.css").write_text(":root{}")
    msgs = " | ".join(messages(validate_pack(pack), "error"))
    assert "escapes the skin folder" in msgs and "is missing" in msgs and "isn't a .uss" in msgs


def test_value_and_asset_rules(skins_root):
    pack = skinpack.create_pack(skins_root, "V")
    (pack.path / "tokens.uss").write_text(
        ":root {\n"
        "  --global-text-primary: rgb(1, 2);\n"
        "  --layout-modules-block-surface: var(--does-not-exist);\n"
        "  --typography-family-primary: url('assets/fonts/missing.ttf');\n"
        "  --made-up-token: rgb(1, 2, 3);\n"
        "}\n"
        ".x { background-image: url('https://example.com/a.png'); }\n")
    problems = validate_pack(pack, GAME_TOKENS)
    errors = " | ".join(messages(problems, "error"))
    assert "rgb() needs 3 numbers" in errors
    assert "could not be resolved" in errors
    assert "outside this sheet's folder" in errors
    assert any("doesn't exist" in m for m in messages(problems, "warning"))
    assert any("typo" in m for m in messages(problems, "info"))
    line = next(p.line for p in problems if "rgb() needs" in p.message)
    assert line == 2


def test_import_rules(skins_root):
    pack = skinpack.create_pack(skins_root, "I")
    (pack.path / "tokens.uss").write_text('@import "parts/colours.uss";\n@import "../../out.uss";\n')
    (pack.path / "parts").mkdir()
    (pack.path / "parts" / "colours.uss").write_text(":root { --global-text-primary: rgb(1,2,3); }")
    msgs = messages(validate_pack(pack, GAME_TOKENS), "error")
    assert len(msgs) == 1 and "outside this sheet's folder" in msgs[0]


def test_sheet_in_subfolder_cannot_reach_pack_assets(skins_root):
    """Mirrors the game: a sheet's url() root is its own folder, so sub/x.uss can't use ../assets."""
    pack = skinpack.create_pack(skins_root, "Sub")
    (pack.path / "assets").mkdir()
    (pack.path / "assets" / "a.png").write_bytes(b"png")
    (pack.path / "sub").mkdir()
    (pack.path / "sub" / "x.uss").write_text('.a { background-image: url("../assets/a.png"); }')
    (pack.path / "skin.json").write_text(json.dumps({"Name": "Sub", "Sheets": ["tokens.uss", "sub/x.uss"]}))
    assert any("outside this sheet's folder" in m for m in messages(validate_pack(pack), "error"))


def test_layout_rules_in_pack(skins_root):
    pack = skinpack.create_pack(skins_root, "Lay")
    good = make_layout([{"id": "A", "x": 0, "y": 0, "w": 4, "h": 2, "minW": 4, "minH": 2, "maxW": 4, "maxH": 2}])
    comps = [default_for(good, "AGridComposition-Large")]
    bad, _ = layouts.place(good, {"A": {"x": 19}}, 20, comps[0])
    layouts.save_to_pack(pack, "AGridComposition-Large", bad)
    assert any("Outside the grid" in m for m in messages(validate_pack(pack, compositions=comps), "error"))
