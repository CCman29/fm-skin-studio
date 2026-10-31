from PIL import Image

from fmskin import recipe, skinpack
from fmskin.validate import validate_pack


def test_full_theme_covers_everything(skins_root, tmp_path):
    button = tmp_path / "button.png"
    Image.new("RGB", (756, 141), (9, 41, 102)).save(button)
    pack = skinpack.create_pack(skins_root, "Recipe")
    result = recipe.apply(pack, recipe.Palette(continue_image=str(button)))
    assert result["warnings"] == []
    assert pack.sheets() == ["tokens.uss", "screen-continue.uss", "screen-global.uss", "screen-processing.uss", "screen-tactics.uss"]
    tokens = pack.tokens()
    for must in ("--layout-modules-block-surface", "--layout-modules-tiles-background", "--colours-ui-soft",
                 "--buttons-toggle-notactive-surface", "--continue-button-default-background", "--pitch-tile-default-background"):
        assert must in tokens
    assert "--colours-tactics-base-50" not in tokens  # the grass stays green
    tactics = (pack.path / "screen-tactics.uss").read_text()
    assert ".tactics-subs-block" in tactics and ".frame-tactics-nav-menu" in tactics
    assert "#continue-button-gradient" in (pack.path / "screen-continue.uss").read_text()
    assert [p for p in validate_pack(pack) if p.severity == "error"] == []
    assert pack.info["recipe"]["accent"] == recipe.Palette().accent


def test_light_palette_is_reported(skins_root):
    pack = skinpack.create_pack(skins_root, "Too Light")
    result = recipe.apply(pack, recipe.Palette(panel="#f3f5fa", tile="#eef1f7", backdrop=("#e3e8f0", "#cfd6e3")))
    areas = {w["area"] for w in result["warnings"]}
    assert {"Content panels", "Side tiles", "Page backdrop"} <= areas


def test_palette_from_json_accepts_lists():
    p = recipe.Palette.from_json({"accent": "#c8102e", "top_bar": ["#0a1a5c", "#061038"], "unknown": 1})
    assert p.accent == "#c8102e" and p.top_bar == ("#0a1a5c", "#061038")


def test_shared_packs_record_no_local_paths(skins_root, tmp_path):
    button, backdrop = tmp_path / "button.png", tmp_path / "my backdrop.jpg"
    Image.new("RGB", (756, 141), (9, 41, 102)).save(button)
    Image.new("RGB", (64, 36), (20, 20, 40)).save(backdrop)
    pack = skinpack.create_pack(skins_root, "Shareable")
    recipe.apply(pack, recipe.Palette(continue_image=str(button), backdrop_image=str(backdrop)))
    info = pack.info
    assert info["recipe"]["continue_image"] == "assets/images/button.png"
    assert info["recipe"]["backdrop_image"] == info["bars"]["backdrop"]["source"] == "assets/images/backdrop.jpg"
    assert str(tmp_path) not in (pack.path / skinpack.MARKER).read_text(encoding="utf-8")


def test_reapplying_colours_keeps_the_background_picture(skins_root, tmp_path):
    backdrop = tmp_path / "photo.jpg"
    Image.new("RGB", (64, 36), (20, 20, 40)).save(backdrop)
    pack = skinpack.create_pack(skins_root, "Keep Photo")
    recipe.apply(pack, recipe.Palette(backdrop_image=str(backdrop)))
    saved = pack.info["bars"]["backdrop"]["source"]
    # the simple colour picker sends back the pack-relative picture it was given
    recipe.apply(pack, recipe.Palette(accent="#ff9a4d", backdrop_image=saved))
    assert pack.info["bars"]["backdrop"] == {"mode": "image", "source": "assets/images/backdrop.jpg"}
    assert "assets/images/backdrop.jpg" in (pack.path / "screen-global.uss").read_text()
