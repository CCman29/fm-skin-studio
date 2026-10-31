import pytest

from fmskin import fonts, skinpack
from fmskin.skinpack import PackError
from fmskin.validate import FONT_FILES_BLOCKED, validate_pack


def test_catalog_is_complete_and_licensed():
    cat = fonts.catalog()["fonts"]
    assert 10 <= len(cat) <= 20
    assert {f["role"] for f in cat} == set(fonts.ROLE_TOKENS)
    for f in cat:
        assert (fonts.FONT_DIR / f["file"]).is_file()
        assert f["license"] and list((fonts.FONT_DIR / "licenses").glob(f"{f['id']}-*.txt"))
        assert f["widthVsDefault"] <= 6  # never noticeably wider than the game's font for that role


def test_font_files_refused_while_game_cannot_load_them(skins_root):
    pack = skinpack.create_pack(skins_root, "Fonts")
    with pytest.raises(PackError):
        fonts.use_font(pack, "HankenGrotesk", "body")


def test_font_file_is_a_validation_error(skins_root):
    pack = skinpack.create_pack(skins_root, "Fonts")
    fonts.use_font(pack, "HankenGrotesk", "body", allow_broken=True)
    assert (pack.path / "assets/fonts/HankenGrotesk-Regular.ttf").is_file()
    assert FONT_FILES_BLOCKED in [p.message for p in validate_pack(pack) if p.severity == "error"]

    fonts.use_font(pack, "ArchivoNarrow", "body", allow_broken=True)  # replacing removes the unused file
    assert not (pack.path / "assets/fonts/HankenGrotesk-Regular.ttf").exists()
    fonts.reset_font(pack, "body")
    assert "--typography-family-primary" not in pack.tokens()
    assert not list((pack.path / "assets/fonts").glob("*.ttf"))


def test_builtin_fonts(skins_root):
    pack = skinpack.create_pack(skins_root, "Builtin")
    fonts.use_builtin(pack, "abc-social-condensed", "headings")
    assert pack.tokens()["--typography-family-thematic"] == "var(--typography-family-condensed)"
    fonts.use_builtin(pack, "fm-universe", "headings")  # the role's own default clears the override
    assert "--typography-family-thematic" not in pack.tokens()
    assert [p for p in validate_pack(pack) if p.severity == "error"] == []
