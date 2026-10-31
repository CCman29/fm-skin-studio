"""Real-screen preview: turn the game's stylesheets and screen files into browser HTML/CSS.

UI Toolkit is flexbox-based, so most layout translates directly. Things the browser can't do the same way
(texture slicing, tinting, game textures, bound data) are dropped or drawn as neutral placeholders. Everything is
generated from the user's own install, kept in the local cache, and never exported.
"""

from __future__ import annotations

import base64
import re

from . import uss

# Sheets that are always applied in the game (competition / phone / test sheets are left out).
PREVIEW_SHEETS = ["UnityDefaultRuntimeTheme", "default", "FigmaStyleVariables", "FigmaGeneratedVariableStyles",
                  "AlwaysAppliedStyleSheet", "LanguageDirectionLTRCombined", "MatchUIStyles"]

FONT_FILES = {"ABCSocial-Regular": "--typography-family-primary", "ABCSocialCondensed-Regular": "--typography-family-condensed",
              "FMUniverse-Regular": "--typography-family-thematic", "NotoSans-Regular": "--typography-family-international"}

_SEL_TOKEN = re.compile(r"(\s*>\s*)|(\s+)|(\.[^\s.#:>*]+)|(#[^\s.#:>*]+)|(::?[\w-]+)|(\*)|([A-Za-z_][\w-]*)")
_KEEP_PSEUDO = {":hover", ":active", ":focus", ":checked"}
_DROP_PROPS = re.compile(r"^(-unity-(slice|background|overflow|paragraph|text-(outline|generator|auto|overflow)|editor|material)"
                         r"|cursor|transition|rotate|scale|translate|transform-origin|filter|-unknown)")


def _esc(ident: str) -> str:
    return re.sub(r"([^\w-])", r"\\\1", ident)


def selector_css(selector: str) -> str | None:
    """UI Toolkit selector -> CSS selector inside the preview root; None if it can't be expressed."""
    out, pos = [], 0
    for m in _SEL_TOKEN.finditer(selector):
        if m.start() != pos:
            return None
        pos = m.end()
        child, space, cls, name, pseudo, star, typ = m.groups()
        if child:
            out.append(" > ")
        elif space:
            out.append(" ")
        elif cls:
            out.append("." + _esc(cls[1:]))
        elif name:
            out.append(f'[data-n="{name[1:]}"]')
        elif pseudo:
            if pseudo == ":root":
                out.append(".fm-root")
            elif pseudo in _KEEP_PSEUDO:
                out.append(pseudo)
            else:
                return None
        elif star:
            out.append("*")
        elif typ:
            out.append(f'[data-t="{typ}"]')
    if pos != len(selector.rstrip()):
        return None
    text = "".join(out).strip()
    return text if not text.startswith(">") else None


_ALIGN_H = {"left": "left", "center": "center", "right": "right"}
_ALIGN_V = {"upper": "flex-start", "middle": "center", "lower": "flex-end"}


def declaration_css(name: str, value: str) -> list[tuple[str, str]]:
    """One USS declaration -> zero or more CSS declarations."""
    value = value.strip()
    if "game-asset:" in value or "resource(" in value:
        return []  # game textures/fonts referenced directly: not available in the preview
    if name.startswith("--"):
        return [(name, value)]
    if name in ("-unity-font-definition", "-unity-font"):
        return [("font-family", value)]
    if name == "-unity-font-style":
        return [("font-weight", "700" if "bold" in value else "400"), ("font-style", "italic" if "italic" in value else "normal")]
    if name == "-unity-text-align":
        parts = value.split("-")
        if len(parts) == 2 and parts[1] in _ALIGN_H:
            return [("text-align", _ALIGN_H[parts[1]]), ("justify-content", _ALIGN_V.get(parts[0], "flex-start"))]
        return []
    if _DROP_PROPS.match(name):
        return []
    if name == "background-image" and not value.startswith(("linear-gradient", "none")):
        return []
    return [(name, value)]


def uss_to_css(text: str) -> str:
    out = []
    for rule in uss.parse(text).rules:
        selectors = [s for s in (selector_css(x.strip()) for x in rule.selector.split(",")) if s]
        if not selectors:
            continue
        body = [f"{n}: {v};" for d in rule.decls for n, v in declaration_css(d.name, d.value)]
        if body:
            out.append(f"{', '.join(selectors)} {{ {' '.join(body)} }}")
    return "\n".join(out)


def inline_css(style: str) -> str:
    """Inline style text 'prop: value; ...' from a screen file -> browser inline style."""
    parts = []
    for decl in style.split(";"):
        if ":" in decl:
            n, v = decl.split(":", 1)
            parts += [f"{a}: {b}" for a, b in declaration_css(n.strip(), v.strip())]
    return "; ".join(parts)


BASE_CSS = """
.fm-root { position: relative; overflow: hidden; color: rgb(235,235,235); font-family: var(--typography-family-primary), sans-serif;
  font-size: 14px; line-height: 1.25; }
.fm-root, .fm-root * { box-sizing: border-box; }
.fm-root [data-t] { display: flex; flex-direction: column; position: relative; flex-shrink: 1; min-width: 0; min-height: 0;
  border: 0 solid transparent; }
.fm-root .fm-text { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex-shrink: 0; max-width: 100%; display: block; }
.fm-root .fm-img { background: repeating-linear-gradient(45deg, rgba(255,255,255,.06) 0 6px, rgba(255,255,255,.1) 6px 12px);
  min-width: 12px; min-height: 12px; border-radius: 3px; }
/* highlight: a translucent white layer over the whole part (hover = innermost part; fm-hl = parts a setting paints) */
.fm-root .fm-hl::after, .fm-root .fm-pick:hover:not(:has(.fm-pick:hover))::after { content: ''; position: absolute; inset: 0;
  background: rgba(255, 255, 255, .42); border-radius: inherit; pointer-events: none; z-index: 5; }
.fm-root .fm-pick { cursor: pointer; }
"""


def font_faces(font_bytes: dict[str, bytes]) -> str:
    rules, tokens = [], []
    for name, data in font_bytes.items():
        token = FONT_FILES.get(name)
        if not token:
            continue
        family = f"FMPreview-{name}"
        mime = "font/otf" if data[:4] == b"OTTO" else "font/ttf"
        rules.append(f"@font-face {{ font-family: '{family}'; src: url(data:{mime};base64,{base64.b64encode(data).decode()}); }}")
        tokens.append(f"{token}: '{family}';")
    return "\n".join(rules) + "\n.fm-root { " + " ".join(tokens) + " }"


def build_css(sheets: dict[str, dict]) -> str:
    parts = [BASE_CSS]
    for name in PREVIEW_SHEETS:
        if name in sheets:
            parts.append(f"/* {name} */\n" + uss_to_css(sheets[name]["uss"]))
    return "\n".join(parts)


# ---- screen files -> render trees --------------------------------------------------------------------
MAX_NODES = 2500
_TEXT_TYPES = {"SIText", "Label", "SITextField", "TextElement", "SIButton", "Button"}
_IMAGE_TYPES = {"SIImage", "Image", "SIRenderTextureImage", "SIAspectRatioFitter", "FMBodymovinWidget"}
_SKIP_TYPES = {"BindingExpectComponent", "BindingRemapperComponent", "BindingRootComponent", "BindingSetterComponent",
               "BindingVariablesComponent", "EventTriggerComponent", "UxmlObjectAsset", "ContextShortcutsElement"}


def _words(identifier: str) -> str:
    return re.sub(r"(?<=[a-z])(?=[A-Z])|[_.%-]+", " ", identifier).strip()


def _sample_text(node: dict) -> str:
    text = node.get("txt") or str((node.get("d") or {}).get("text") or "")
    if text and not re.fullmatch(r"[\w.%#\[\]]+", text.replace(" ", "")) or (text and " " in text.strip()):
        return text
    if text:  # a data path such as team.HistoryHonours.AllHonoursCount -> "All Honours Count"
        return _words(text.split(".")[-1]).title() or "Text"
    words = _words((node.get("d") or {}).get("name") or "")
    return words.title() if words and words.lower() not in ("text", "label", "sitext") else "Text"


# States the game only shows in particular situations (empty data, loading, hover, phone layout...).
_HIDDEN = re.compile(r"tooltip|popup|loading|spinner|no-?data|empty|placeholder|unavailable|^phone|-phone|ios-|"
                     r"hover-|dropdown-?list|overlay-hidden|tutorial|tile-interaction|interaction-button|"
                     r"grid-element__controls|edit-mode|"
                     # situations a normal club manager isn't in: international jobs, unemployed, deadline day, FMC
                     r"incamp|camp(final|visible)|unemployed|deadline|^isnation|international|knockedout|retired|fmc", re.I)


def _hidden(node: dict) -> bool:
    name = (node.get("d") or {}).get("name") or ""
    return bool(_HIDDEN.search(name) and not name.lower().startswith("nonphone")) or \
        any(_HIDDEN.search(c) for c in node.get("c") or [])


def render_tree(name: str, screens: dict[str, dict], guids: dict[str, str]) -> dict | None:
    """Screen file -> {t, n, c, css, text, ch} with templates inlined (depth and size limited).

    A template instance's own children go into the template's content container (UXML content-container), as in
    the game; without that they'd pile up next to the template. Switches show one case, like the game does."""
    count = [0]

    def walk(node: dict, owner: dict, depth: int, slot: dict | None = None) -> dict | None:
        """`slot` = {"kids": [(node, owner)], "used": bool}: an instance's children waiting for this template's
        content container."""
        if not node or count[0] > MAX_NODES or depth > 48 or node["t"] in _SKIP_TYPES or _hidden(node):
            return None
        count[0] += 1
        d = node.get("d") or {}
        out: dict = {"t": node["t"]}
        if d.get("name"):
            out["n"] = d["name"]
        if node.get("c"):
            out["c"] = node["c"]
        if node.get("s"):
            css = inline_css(node["s"])
            if css:
                out["css"] = css
        if node["t"] in _TEXT_TYPES:
            out["text"] = _sample_text(node)
        if node["t"] in _IMAGE_TYPES:
            out["img"] = True
        kids = [(k, owner, slot) for k in node.get("ch") or []]
        if node.get("cc") and slot and not slot["used"]:
            slot["used"] = True
            kids += [(k, o, None) for k, o in slot["kids"]]
        alias = node.get("tpl")
        if alias:
            target = guids.get((owner.get("templates") or {}).get(alias, ""), alias)
            sub = screens.get(target)
            if sub and sub.get("root"):
                out["tpl"] = target
                inner = {"kids": [(k, owner) for k, _o, _s in kids], "used": False}
                kids = [(k, sub, inner) for k in sub["root"].get("ch") or []]
                if not any(_has_cc(k) for k, _o, _s in kids):  # no content container: children follow the template
                    kids += [(k, o, None) for k, o in inner["kids"]]
                    inner["used"] = True
        if node["t"] in ("BindableSwitchElement", "SwitchElement", "TabGroup"):
            kids = kids[:1]  # the game shows one case of a switch (or one tab) at a time; preview the first
        else:  # sibling visibility conditions are usually alternatives (human / AI, has data / none): keep the first
            seen_visible = False
            keep = []
            for k in kids:
                if k[0].get("t") == "SIVisible":
                    if seen_visible:
                        continue
                    seen_visible = True
                keep.append(k)
            kids = keep
        children = [c for c in (walk(k, o, depth + 1, sl) for k, o, sl in kids) if c]
        if children:
            out["ch"] = children
        return out

    screen = screens.get(name)
    if not screen or not screen.get("root"):
        return None
    tree = walk(screen["root"], screen, 0)
    if tree is not None:
        tree["truncated"] = count[0] > MAX_NODES
    return tree


def _has_cc(node: dict) -> bool:
    return bool(node.get("cc")) or any(_has_cc(c) for c in node.get("ch") or [])
