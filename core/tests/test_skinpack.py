import json
import zipfile

import pytest

from fmskin import skinpack
from fmskin.skinpack import MARKER, PackError, SkinPack


def test_create_pack_writes_game_format(skins_root):
    pack = skinpack.create_pack(skins_root, "My Dark Skin")
    data = json.loads((pack.path / "skin.json").read_text(encoding="utf-8"))
    assert pack.path.name == "my-dark-skin"
    assert data == {"Name": "My Dark Skin", "Sheets": ["tokens.uss"]}  # exact, case-sensitive keys
    assert (pack.path / MARKER).is_file()


def test_name_clash_never_overwrites(skins_root, foreign_skin):
    a = skinpack.create_pack(skins_root, "someone elses skin")
    assert a.path.name == "someone-elses-skin-2"
    assert json.loads((foreign_skin / "skin.json").read_text())["Name"] == "Their Skin"


def test_foreign_skin_is_read_only(foreign_skin):
    pack = SkinPack(foreign_skin)
    before = {p.name: p.read_bytes() for p in foreign_skin.iterdir()}
    with pytest.raises(PackError):
        pack.set_tokens({"--global-text-primary": "rgb(9, 9, 9)"})
    with pytest.raises(PackError):
        pack.rename("Hijacked")
    with pytest.raises(PackError):
        skinpack.delete_pack(pack)
    assert {p.name: p.read_bytes() for p in foreign_skin.iterdir()} == before


def test_duplicate_copies_into_new_pack(skins_root, foreign_skin):
    copy = skinpack.create_pack(skins_root, "Copy of Theirs", source=SkinPack(foreign_skin))
    assert copy.path != foreign_skin and copy.managed
    assert copy.sheets() == ["tokens.uss", "theme.uss"]
    assert not (foreign_skin / MARKER).exists()


def test_tokens_merge_and_remove(skins_root):
    pack = skinpack.create_pack(skins_root, "T")
    pack.set_tokens({"--global-text-primary": "rgb(255, 230, 0)", "--layout-modules-block-surface": "rgba(1, 2, 3, 0.5)"},
                    groups={"--global-text-primary": "Text"})
    assert pack.tokens()["--global-text-primary"] == "rgb(255, 230, 0)"
    pack.set_tokens({"--global-text-primary": None})
    assert "--global-text-primary" not in pack.tokens()
    with pytest.raises(PackError):
        pack.set_tokens({"color": "red"})


def test_tokens_on_non_root_selector(skins_root):
    pack = skinpack.create_pack(skins_root, "Charts")
    pack.set_tokens({"--line-colour-1": "rgb(1, 1, 1)", "--global-text-primary": "rgb(2, 2, 2)"},
                    selectors={"--line-colour-1": ".silinechart"})
    text = (pack.path / "tokens.uss").read_text()
    assert ".silinechart {" in text and ":root {" in text
    assert pack.token_selectors()["--line-colour-1"] == ".silinechart"
    pack.set_tokens({"--line-colour-1": "rgb(3, 3, 3)"})  # remembers its selector
    assert pack.token_selectors()["--line-colour-1"] == ".silinechart"


def test_screen_sheets_listed_after_tokens(skins_root):
    pack = skinpack.create_pack(skins_root, "S")
    pack.write_screen_sheet("Training Overview", ".x { width: 10px; }")
    assert pack.sheets() == ["tokens.uss", "screen-training-overview.uss"]
    pack.write_screen_sheet("Training Overview", "")
    assert pack.sheets() == ["tokens.uss"]


def test_add_asset_types(skins_root, tmp_path):
    pack = skinpack.create_pack(skins_root, "A")
    font = tmp_path / "My Font.ttf"
    font.write_bytes(b"fake")
    assert pack.add_asset(font) == 'url("assets/fonts/My_Font.ttf")'
    bad = tmp_path / "x.gif"
    bad.write_bytes(b"x")
    with pytest.raises(PackError):
        pack.add_asset(bad)


def test_export_import_round_trip(skins_root, tmp_path):
    pack = skinpack.create_pack(skins_root, "Share Me")
    pack.set_tokens({"--global-text-primary": "rgb(1, 2, 3)"})
    archive = skinpack.export_pack(pack, tmp_path / "share")
    assert archive.suffix == ".fmskin"
    imported = skinpack.import_pack(archive, skins_root)
    assert imported.path.name == "share-me-2" and imported.tokens() == pack.tokens()


def test_import_rejects_zip_slip(skins_root, tmp_path):
    evil = tmp_path / "evil.fmskin"
    with zipfile.ZipFile(evil, "w") as zf:
        zf.writestr("pack/skin.json", "{}")
        zf.writestr("pack/../../escape.txt", "x")
    with pytest.raises(PackError):
        skinpack.import_pack(evil, skins_root)
    assert not (tmp_path / "escape.txt").exists()


def test_list_skins_flags_managed(skins_root, foreign_skin):
    skinpack.create_pack(skins_root, "Mine")
    rows = {r["id"]: r for r in skinpack.list_skins(skins_root)}
    assert rows["mine"]["managed"] and not rows["someone-elses-skin"]["managed"]
