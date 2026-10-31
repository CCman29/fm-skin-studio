"""Decode Unity UI Toolkit StyleSheet assets (as read by UnityPy) into readable rules / USS text.

The numeric ids below are Unity's public UI Toolkit enums (StylePropertyId, StyleValueType,
StyleValueKeyword, StyleValueFunction, Dimension.Unit, StyleSelectorType, StyleSelectorRelationship).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_PROPERTY_IDS = {
    131072: "AlignContent", 131073: "AlignItems", 131074: "AlignSelf", 262144: "All", 131075: "AspectRatio",
    458752: "BackgroundColor", 458753: "BackgroundImage", 262145: "BackgroundPosition", 458754: "BackgroundPositionX",
    458755: "BackgroundPositionY", 458756: "BackgroundRepeat", 458757: "BackgroundSize", 458758: "BorderBottomColor",
    458759: "BorderBottomLeftRadius", 458760: "BorderBottomRightRadius", 131076: "BorderBottomWidth",
    262146: "BorderColor", 458761: "BorderLeftColor", 131077: "BorderLeftWidth", 262147: "BorderRadius",
    458762: "BorderRightColor", 131078: "BorderRightWidth", 458763: "BorderTopColor", 458764: "BorderTopLeftRadius",
    458765: "BorderTopRightRadius", 131079: "BorderTopWidth", 262148: "BorderWidth", 131080: "Bottom", 65536: "Color",
    196608: "Cursor", 131081: "Display", 458766: "Filter", 262149: "Flex", 131082: "FlexBasis", 131083: "FlexDirection",
    131084: "FlexGrow", 131085: "FlexShrink", 131086: "FlexWrap", 65537: "FontSize", 131087: "Height",
    131088: "JustifyContent", 131089: "Left", 65538: "LetterSpacing", 262150: "Margin", 131090: "MarginBottom",
    131091: "MarginLeft", 131092: "MarginRight", 131093: "MarginTop", 131094: "MaxHeight", 131095: "MaxWidth",
    131096: "MinHeight", 131097: "MinWidth", 458767: "Opacity", 458768: "Overflow", 262151: "Padding",
    131098: "PaddingBottom", 131099: "PaddingLeft", 131100: "PaddingRight", 131101: "PaddingTop", 131102: "Position",
    131103: "Right", 327680: "Rotate", 327681: "Scale", 196609: "TextOverflow", 65539: "TextShadow", 131104: "Top",
    327682: "TransformOrigin", 262152: "Transition", 393216: "TransitionDelay", 393217: "TransitionDuration",
    393218: "TransitionProperty", 393219: "TransitionTimingFunction", 327683: "Translate",
    196610: "UnityBackgroundImageTintColor", 262153: "UnityBackgroundScaleMode", 65540: "UnityEditorTextRenderingMode",
    65541: "UnityFont", 65542: "UnityFontDefinition", 65543: "UnityFontStyleAndWeight", 65544: "UnityMaterial",
    196611: "UnityOverflowClipBox", 65545: "UnityParagraphSpacing", 196612: "UnitySliceBottom",
    196613: "UnitySliceLeft", 196614: "UnitySliceRight", 196615: "UnitySliceScale", 196616: "UnitySliceTop",
    196617: "UnitySliceType", 65546: "UnityTextAlign", 65547: "UnityTextAutoSize", 65548: "UnityTextGenerator",
    262154: "UnityTextOutline", 65549: "UnityTextOutlineColor", 65550: "UnityTextOutlineWidth",
    196618: "UnityTextOverflowPosition", 65551: "Visibility", 65552: "WhiteSpace", 131105: "Width", 65553: "WordSpacing",
}
_CSS_OVERRIDES = {"UnityFontStyleAndWeight": "-unity-font-style"}


def _css_name(enum_name: str) -> str:
    if enum_name in _CSS_OVERRIDES:
        return _CSS_OVERRIDES[enum_name]
    kebab = re.sub(r"(?<!^)(?=[A-Z])", "-", enum_name).lower()
    return "-" + kebab if kebab.startswith("unity-") else kebab


PROPERTY_NAMES = {pid: _css_name(name) for pid, name in _PROPERTY_IDS.items()}

# StyleValueType
KEYWORD, FLOAT, DIMENSION, COLOR, RESOURCE_PATH, ASSET_REF, ENUM, VARIABLE, STRING, FUNCTION, COMMA, SCALABLE_IMAGE, MISSING_ASSET = range(1, 14)
_KEYWORDS = ["inherit", "initial", "auto", "unset", "true", "false", "none", "cover", "contain"]
_FUNCTIONS = ["unknown", "var", "env", "linear-gradient", "none", "custom", "tint", "opacity", "invert", "grayscale",
              "sepia", "blur", "contrast", "hue-rotate", "material-property"]
_UNITS = ["", "px", "%", "s", "ms", "deg", "grad", "rad", "turn"]
_SELECTOR_PREFIX = {1: "*", 2: "", 3: ".", 4: ":", 5: ":", 6: "#", 7: ""}


@dataclass
class Declaration:
    name: str
    value: str
    line: int = 0
    var_refs: list[str] = field(default_factory=list)

    @property
    def is_custom(self) -> bool:
        return self.name.startswith("--")


@dataclass
class Rule:
    selectors: list[str]
    declarations: list[Declaration]
    line: int = 0


@dataclass
class DecodedSheet:
    name: str
    rules: list[Rule]

    def to_uss(self) -> str:
        out = []
        for rule in self.rules:
            body = "\n".join(f"    {d.name}: {d.value};" for d in rule.declarations)
            out.append(f"{', '.join(rule.selectors)} {{\n{body}\n}}")
        return "\n\n".join(out) + "\n"


def _fmt_number(value: float) -> str:
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def _fmt_color(c: dict) -> str:
    r, g, b = (round(c[k] * 255) for k in "rgb")
    a = c.get("a", 1.0)
    if a >= 0.9995:
        return f"rgb({r}, {g}, {b})"
    return f"rgba({r}, {g}, {b}, {_fmt_number(a)})"


class _ValueReader:
    def __init__(self, sheet: dict, values: list[dict]):
        self.sheet, self.values, self.pos, self.var_refs = sheet, values, 0, []

    def _pool(self, key: str, index: int):
        pool = self.sheet.get(key) or []
        return pool[index] if 0 <= index < len(pool) else None

    def read_all(self) -> str:
        parts = []
        while self.pos < len(self.values):
            parts.append(self.read_one())
        return " ".join(parts).replace(" ,", ",")

    def read_one(self) -> str:
        v = self.values[self.pos]
        self.pos += 1
        kind, idx = v["m_ValueType"], v["valueIndex"]
        if kind == KEYWORD:
            return _KEYWORDS[idx] if idx < len(_KEYWORDS) else f"keyword-{idx}"
        if kind == FLOAT:
            return _fmt_number(self._pool("floats", idx) or 0.0)
        if kind == DIMENSION:
            d = self._pool("dimensions", idx) or {"value": 0, "unit": 0}
            unit = _UNITS[d["unit"]] if d["unit"] < len(_UNITS) else ""
            return _fmt_number(d["value"]) + unit
        if kind == COLOR:
            return _fmt_color(self._pool("colors", idx) or {"r": 0, "g": 0, "b": 0, "a": 1})
        if kind in (ENUM, VARIABLE):
            text = self._pool("strings", idx) or ""
            if kind == VARIABLE:
                self.var_refs.append(text)
            return text
        if kind == STRING:
            return '"' + (self._pool("strings", idx) or "").replace('"', '\\"') + '"'
        if kind == RESOURCE_PATH:
            return f'resource("{self._pool("strings", idx) or ""}")'
        if kind in (ASSET_REF, SCALABLE_IMAGE, MISSING_ASSET):
            return f'url("game-asset:{kind}:{idx}")'
        if kind == COMMA:
            return ","
        if kind == FUNCTION:
            name = _FUNCTIONS[idx] if idx < len(_FUNCTIONS) else f"func{idx}"
            argc = 0
            if self.pos < len(self.values) and self.values[self.pos]["m_ValueType"] == FLOAT:
                argc = int(self._pool("floats", self.values[self.pos]["valueIndex"]) or 0)
                self.pos += 1
            args = [self.read_one() for _ in range(min(argc, len(self.values) - self.pos))]
            return f"{name}({' '.join(args).replace(' ,', ',')})"
        return f"/*type{kind}*/"


def selector_text(complex_selector: dict) -> str:
    out = ""
    for i, sel in enumerate(complex_selector.get("m_Selectors", [])):
        compound = "".join(_SELECTOR_PREFIX.get(p["m_Type"], "") + (p["m_Value"] if p["m_Type"] != 1 else "")
                           for p in sel.get("m_Parts", []))
        if i:
            out += " > " if sel.get("m_PreviousRelationship") == 1 else " "
        out += compound
    return out


def decode(sheet: dict) -> DecodedSheet:
    """`sheet` is the UnityPy typetree of a StyleSheet MonoBehaviour."""
    rules = []
    for raw_rule in sheet.get("m_Rules", []):
        decls = []
        for prop in raw_rule.get("m_Properties", []):
            name = prop.get("m_CustomName") or PROPERTY_NAMES.get(prop.get("m_Id"), f"-unknown-{prop.get('m_Id')}")
            reader = _ValueReader(sheet, prop.get("m_Values", []))
            decls.append(Declaration(name, reader.read_all(), prop.get("m_Line", 0), reader.var_refs))
        selectors = [selector_text(cs) for cs in raw_rule.get("m_ComplexSelectors", [])] or [":root"]
        rules.append(Rule(selectors, decls, raw_rule.get("line", 0)))
    return DecodedSheet(sheet.get("m_Name", ""), rules)


def is_stylesheet(tree: dict) -> bool:
    return "m_Rules" in tree and "strings" in tree and "colors" in tree
