import json
import zipfile

import pytest

from fmskin import attributecolours, lighttheme, skinpack, skinpackage
from fmskin.skinpack import PackError

GAME_TOKENS = {
    "--colours-alpha-light-8": {"value": "rgba(255, 255, 255, 0.08)"},
    "--colours-alpha-light-48": {"value": "rgba(255, 255, 255, 0.48)"},
    "--colours-alpha-light-80": {"value": "rgba(255, 255, 255, 0.8)"},
    "--colours-base-neutral-white": {"value": "rgb(255, 255, 255)", "resolved": "rgb(255, 255, 255)"},
    "--layout-modules-block-surface": {"value": "rgb(30, 33, 41)", "resolved": "rgb(30, 33, 41)"},
    "--accent-fill": {"value": "rgb(40, 120, 200)", "resolved": "rgb(40, 120, 200)"},
}
SHEET = """
.card-title { color: rgb(255, 255, 255); }
.tab-label-faint { color: rgba(255, 255, 255, 0.6); }
.badge-text { color: rgb(255, 255, 255); }
.row:hover { background-color: var(--colours-alpha-light-48); }
.list-divider { border-bottom-color: var(--colours-alpha-light-8); }
.tab--active { border-bottom-color: var(--colours-alpha-light-80); }
.help-icon { -unity-background-image-tint-color: rgb(255, 255, 255); }
.big-button { background-color: var(--accent-fill); }
"""


class FakeIndex:
    def sheets(self):
        return {"AlwaysAppliedStyleSheet": {"uss": SHEET}, "PremierLeagueStyles": {"uss": ".x { color: rgb(255, 255, 255); }"}}


def test_is_light():
    assert lighttheme.is_light("#fdfcfd") and lighttheme.is_light("#f0e0c0")
    assert not lighttheme.is_light("#0a1e5c") and not lighttheme.is_light("#37003c")


def test_light_theme_writes_only_into_the_pack(skins_root):
    pack = skinpack.create_pack(skins_root, "Paper")
    pack.set_tokens({"--accent-fill": "rgb(55, 0, 60)"})  # a fill the skin made dark
    stats = lighttheme.apply(pack, FakeIndex(), GAME_TOKENS, text="#37003c", highlight="#e90052",
                             menu_colour="#37003c", sub_bar="#37003c", continue_colour="#e90052")
    tokens = pack.tokens()
    assert tokens["--colours-alpha-light-80"] == "rgba(55, 0, 60, 0.92)"  # text-strength tint
    assert tokens["--buttons-toggle-active-primary-surface"].startswith("rgb(")  # pale highlight for selected options
    text = pack.screen_sheet("lighttext")
    assert ".card-title { color: var(--global-text-primary); }" in text
    assert ".tab-label-faint { color: var(--global-text-secondary); }" in text
    assert ".badge-text" not in text and ".x " not in text  # coloured backgrounds and competition sheets stay white
    surfaces = pack.screen_sheet("lightsurfaces")
    assert ".row:hover { background-color: rgba(55, 0, 60, 0.18); }" in surfaces  # a wash, not a solid slab
    assert ".tab--active { border-bottom-color: rgb(233, 0, 82); }" in surfaces  # selection marker stays strong
    assert ".list-divider { border-bottom-color: rgba(55, 0, 60" in surfaces
    assert ".help-icon { -unity-background-image-tint-color: var(--global-text-primary); }" in surfaces
    assert ".big-button SIText" in surfaces  # white text inside the dark fill
    assert stats["washes"] == 1 and stats["onDark"] == 1
    tweaks = pack.screen_sheet("lighttweaks")
    assert ".secondary-navigation-tab-text" in tweaks and ".continue-button SIText" in tweaks  # both dark
    assert "panels: a picture" not in tweaks  # no panel texture yet
    assert "#MainMenu" in pack.screen_sheet("mainmenu")
    assert pack.info["lightTheme"]["highlight"] == "#e90052"


def test_panel_texture_kept_and_removed(skins_root, tmp_path):
    from PIL import Image
    pic = tmp_path / "fabric.jpg"
    Image.new("RGB", (8, 8), (240, 240, 240)).save(pic)
    pack = skinpack.create_pack(skins_root, "Cloth")
    lighttheme.apply(pack, FakeIndex(), GAME_TOKENS, text="#202020", highlight="#c00000", panel_texture=pic)
    assert 'url("assets/images/fabric.jpg")' in pack.screen_sheet("lighttweaks")
    lighttheme.reapply(pack, FakeIndex(), GAME_TOKENS, highlight="#0000c0")  # texture kept
    assert 'url("assets/images/fabric.jpg")' in pack.screen_sheet("lighttweaks")
    lighttheme.reapply(pack, FakeIndex(), GAME_TOKENS, panel_texture=lighttheme.NO_TEXTURE)
    assert "fabric.jpg" not in pack.screen_sheet("lighttweaks")


def test_remove_light_theme(skins_root):
    pack = skinpack.create_pack(skins_root, "Back To Dark")
    lighttheme.apply(pack, FakeIndex(), GAME_TOKENS, text="#202020", highlight="#c00000")
    lighttheme.remove(pack, GAME_TOKENS)
    assert not any(s.startswith("screen-light") for s in pack.sheets())
    assert "--colours-alpha-light-80" not in pack.tokens() and not pack.info.get("lightTheme")
    with pytest.raises(PackError):
        lighttheme.reapply(pack, FakeIndex(), GAME_TOKENS)


EPL = [{"from": 16, "text": "#FFFFFF", "background": "#37003c", "border": "#ffffff"},
       {"from": 1, "text": "#ffffff", "background": "#0b0b0b", "border": "#ffffff"},
       {"from": 11, "text": "#ffffff", "background": "#f2c200", "border": "#ffffff", "label": "Good"}]


def test_attribute_bands_normalise_and_warn():
    bands = attributecolours.normalise(EPL)
    assert [b["from"] for b in bands] == [16, 11, 1] and bands[0]["text"] == "#ffffff"
    assert [(lo, hi) for lo, hi, _ in attributecolours.ranges(bands)] == [(16, 20), (11, 15), (1, 10)]
    warn = attributecolours.warnings(bands)
    assert len(warn) == 1 and warn[0].startswith("11-15")  # white on yellow is hard to read
    for bad in ([EPL[0]], [EPL[0], dict(EPL[1], **{"from": 2})], [EPL[0], dict(EPL[1], text="white")],
                [EPL[0], dict(EPL[1], **{"from": 16})]):
        with pytest.raises(PackError):
            attributecolours.normalise(bad)


def test_attribute_colours_saved_and_packaged(skins_root, tmp_path):
    pack = skinpack.create_pack(skins_root, "Bands")
    attributecolours.set_for(pack, EPL)
    assert [b["from"] for b in attributecolours.get(pack)] == [16, 11, 1]
    exe = tmp_path / "installer.exe"
    exe.write_bytes(b"MZ")
    zip_path = skinpackage.make_package(pack, tmp_path / "Bands Installer.zip", exe=exe)
    with zipfile.ZipFile(zip_path) as z:
        readme = z.read("Bands Installer/README.txt").decode()
        manifest = json.loads(z.read("Bands Installer/package/skin-package.json"))
    assert "ATTRIBUTE COLOURS" in readme and "16-20" in readme and "#37003c" in readme
    assert manifest["attributeColours"][0]["background"] == "#37003c"
    attributecolours.set_for(pack, None)
    assert attributecolours.get(pack) == []
