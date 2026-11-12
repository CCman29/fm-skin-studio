import pytest

from fmskin import fonts, skinpack
from fmskin.skinpack import PackError
from fmskin.validate import FONT_ENGINE_MISSING, validate_pack


def test_catalog_is_complete_and_licensed():
    cat = fonts.catalog()["fonts"]
    assert 10 <= len(cat) <= 20
    assert {f["role"] for f in cat} == set(fonts.ROLE_TOKENS)
    for f in cat:
        assert (fonts.FONT_DIR / f["file"]).is_file()
        assert f["license"] and list((fonts.FONT_DIR / "licenses").glob(f"{f['id']}-*.txt"))
        assert f["widthVsDefault"] <= 6  # never noticeably wider than the game's font for that role


def test_font_file_adds_the_text_engine_rule(skins_root):
    pack = skinpack.create_pack(skins_root, "Fonts")
    fonts.use_font(pack, "HankenGrotesk", "body")
    assert (pack.path / "assets/fonts/HankenGrotesk-Regular.ttf").is_file()
    assert "screen-textengine.uss" in pack.sheets()
    assert fonts.TEXT_ENGINE_RULE in pack.screen_sheet("textengine")
    problems = validate_pack(pack)
    assert [p for p in problems if p.severity == "error"] == []
    assert FONT_ENGINE_MISSING not in [p.message for p in problems]

    fonts.use_font(pack, "ArchivoNarrow", "body")  # replacing removes the unused file
    assert not (pack.path / "assets/fonts/HankenGrotesk-Regular.ttf").exists()
    fonts.reset_font(pack, "body")  # no font files left: the files and the rule go
    assert "--typography-family-primary" not in pack.tokens()
    assert not list((pack.path / "assets/fonts").glob("*.ttf"))
    assert "screen-textengine.uss" not in pack.sheets()


def test_font_file_without_the_rule_is_flagged(skins_root):
    pack = skinpack.create_pack(skins_root, "Fonts")
    font = pack.add_asset(fonts.FONT_DIR / "Exo2-Regular.ttf")
    pack.set_tokens({"--typography-family-primary": font})
    messages = [p.message for p in validate_pack(pack) if p.severity == "warning"]
    assert FONT_ENGINE_MISSING in messages


def test_builtin_fonts(skins_root):
    pack = skinpack.create_pack(skins_root, "Builtin")
    fonts.use_builtin(pack, "abc-social-condensed", "headings")
    assert pack.tokens()["--typography-family-thematic"] == "var(--typography-family-condensed)"
    fonts.use_builtin(pack, "fm-universe", "headings")  # the role's own default clears the override
    assert "--typography-family-thematic" not in pack.tokens()
    assert [p for p in validate_pack(pack) if p.severity == "error"] == []
