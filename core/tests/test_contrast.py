from fmskin import bars, contrast, skinpack
from fmskin.validate import validate_pack

GAME = {"--layout-modules-block-surface": {"value": "var(--colours-alpha-dark-75)"},
        "--colours-alpha-dark-75": {"value": "rgba(13, 14, 17, 0.75)"},
        "--data-tables-background": {"value": "rgba(255, 255, 255, 0)"}}


def light_warnings(pack):
    return [p.message for p in validate_pack(pack, GAME) if "too light for FM27's white text" in p.message]


def test_dark_surfaces_pass(skins_root):
    pack = skinpack.create_pack(skins_root, "Dark")
    pack.set_tokens({"--layout-modules-block-surface": "rgba(10, 22, 70, 0.94)", "--data-tables-background": "rgba(255, 255, 255, 0)"})
    bars.apply(pack, {"topBar": {"mode": "gradient", "colours": ["#0a1a5c", "#061038"]}})
    assert light_warnings(pack) == []


def test_light_surfaces_and_bars_warn(skins_root):
    pack = skinpack.create_pack(skins_root, "Light")
    pack.set_tokens({"--layout-modules-block-surface": "rgb(243, 245, 250)", "--data-tables-background": "rgb(255, 255, 255)"})
    bars.apply(pack, {"topBar": {"mode": "gradient", "colours": ["#ffffff", "#f1f3f8"]},
                      "pageHeader": {"mode": "solid", "colours": ["#0e2470"]}})
    msgs = light_warnings(pack)
    assert any(m.startswith("Content panels") for m in msgs)
    assert any(m.startswith("Table rows") for m in msgs)
    assert any(m.startswith("Top menu bar") for m in msgs)
    assert not any(m.startswith("Page header") for m in msgs)


def test_light_backdrop_warns(skins_root):
    pack = skinpack.create_pack(skins_root, "Pale")
    bars.apply(pack, {"backdrop": {"mode": "gradient", "colours": ["#e3e8f0", "#cfd6e3"]}})
    assert any(m.startswith("Page backdrop") for m in light_warnings(pack))
    bars.apply(pack, {"backdrop": {"mode": "gradient", "colours": ["#5d6d93", "#3f4c70"]}})
    assert not any(m.startswith("Page backdrop") for m in light_warnings(pack))


def test_untouched_and_mostly_transparent_surfaces_are_ignored(skins_root):
    pack = skinpack.create_pack(skins_root, "Faint")
    pack.set_tokens({"--data-tables-background-accent": "rgba(255, 255, 255, 0.06)"})
    assert light_warnings(pack) == []


def test_ratio_maths():
    assert round(contrast.white_ratio((255, 255, 255, 1)), 1) == 1.0
    assert contrast.white_ratio((0, 0, 0, 1)) > 20
