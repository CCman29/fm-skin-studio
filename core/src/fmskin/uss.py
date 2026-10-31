"""Small USS reader/writer for skin sheets (the subset FM27's runtime skin loader accepts)."""

from __future__ import annotations

import bisect
import re
from dataclasses import dataclass, field

IMPORT_RE = re.compile(r"""@import\s+(?:url\(\s*(?:"([^"]*)"|'([^']*)'|([^)\s]+))\s*\)|"([^"]*)"|'([^']*)')\s*;""")
URL_RE = re.compile(r"""\b(url|resource)\(\s*(?:"([^"]*)"|'([^']*)'|([^)\s]*))\s*\)""")
VAR_RE = re.compile(r"var\(\s*(--[\w-]+)")
MANAGED_HEADER = "/* Managed by FM Skin Studio: global theme tokens. Edits here are kept but may be reformatted. */"


@dataclass
class Decl:
    name: str
    value: str
    line: int


@dataclass
class UssRule:
    selector: str
    line: int
    decls: list[Decl] = field(default_factory=list)


@dataclass
class UssDocument:
    imports: list[tuple[str, int]] = field(default_factory=list)
    rules: list[UssRule] = field(default_factory=list)
    errors: list[tuple[int, str]] = field(default_factory=list)


def _strip_comments(text: str) -> str:
    """Blank out /* */ comments but keep newlines so line numbers stay right."""
    return re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), text, flags=re.S)


def parse(text: str) -> UssDocument:
    doc = UssDocument()
    src = _strip_comments(text)

    newlines = [i for i, ch in enumerate(src) if ch == "\n"]

    def line_at(pos: int) -> int:
        return bisect.bisect_left(newlines, pos) + 1

    for m in IMPORT_RE.finditer(src):
        doc.imports.append((next(g for g in m.groups() if g is not None), line_at(m.start())))
    body = IMPORT_RE.sub(lambda m: " " * len(m.group(0)), src)

    pos = 0
    while True:
        open_i = body.find("{", pos)
        if open_i < 0:
            if body[pos:].strip():
                doc.errors.append((line_at(pos), "Text outside of any rule"))
            break
        close_i = body.find("}", open_i)
        nested = body.find("{", open_i + 1)
        if close_i < 0:
            doc.errors.append((line_at(open_i), "Missing closing '}'"))
            break
        if 0 <= nested < close_i:
            doc.errors.append((line_at(nested), "Nested blocks are not supported"))
        selector = body[pos:open_i].strip()
        if selector.startswith("@"):
            doc.errors.append((line_at(pos), f"Unsupported at-rule '{selector.split()[0]}'"))
        elif not selector:
            doc.errors.append((line_at(open_i), "Rule without a selector"))
        rule = UssRule(selector, line_at(pos + len(body[pos:open_i]) - len(body[pos:open_i].lstrip())))
        offset = open_i + 1
        for chunk in body[open_i + 1:close_i].split(";"):
            if chunk.strip():
                if ":" not in chunk:
                    doc.errors.append((line_at(offset), f"Declaration without ':' ({chunk.strip()[:40]})"))
                else:
                    name, value = chunk.split(":", 1)
                    rule.decls.append(Decl(name.strip(), value.strip(), line_at(offset + len(chunk) - len(chunk.lstrip()))))
            offset += len(chunk) + 1
        doc.rules.append(rule)
        pos = close_i + 1
    return doc


def read_token_rules(text: str) -> dict[str, dict[str, str]]:
    """{selector: {token: value}} for every block of a tokens sheet."""
    blocks: dict[str, dict[str, str]] = {}
    for rule in parse(text).rules:
        for d in rule.decls:
            if d.name.startswith("--"):
                blocks.setdefault(rule.selector, {})[d.name] = d.value
    return blocks


def read_tokens(text: str) -> dict[str, str]:
    tokens: dict[str, str] = {}
    for block in read_token_rules(text).values():
        tokens.update(block)
    return tokens


def render_tokens(tokens: dict[str, str], groups: dict[str, str] | None = None,
                  selectors: dict[str, str] | None = None) -> str:
    """A :root block plus one block per other selector a token lives on, grouped under comments."""
    by_selector: dict[str, list[str]] = {}
    for name in tokens:
        by_selector.setdefault((selectors or {}).get(name, ":root"), []).append(name)
    lines = [MANAGED_HEADER]
    for selector in sorted(by_selector, key=lambda s: (s != ":root", s)):
        lines.append(f"{selector} {{")
        by_group: dict[str, list[str]] = {}
        for name in by_selector[selector]:
            by_group.setdefault((groups or {}).get(name, ""), []).append(name)
        for group in sorted(by_group):
            if group:
                lines.append(f"    /* {group} */")
            lines += [f"    {n}: {tokens[n]};" for n in sorted(by_group[group])]
        lines.append("}")
    return "\n".join(lines) + "\n"


def asset_refs(value: str) -> list[tuple[str, str]]:
    """[(function, target)] for url()/resource() in a value."""
    return [(m.group(1), next((g for g in m.groups()[1:] if g is not None), "")) for m in URL_RE.finditer(value)]


_NUM = r"-?(?:\d+\.?\d*|\.\d+)"


def check_value(value: str) -> str | None:
    """Return a problem description, or None if the value looks acceptable to the game's decoder."""
    if not value:
        return "no value"
    for func in re.finditer(r"\b(rgba?)\(([^)]*)\)", value):
        args = [a.strip() for a in func.group(2).split(",")]
        want = 4 if func.group(1) == "rgba" else 3
        if len(args) != want or not all(re.fullmatch(_NUM + "%?", a) for a in args):
            return f"{func.group(1)}() needs {want} numbers"
    if value.count("(") != value.count(")"):
        return "unbalanced parentheses"
    if re.search(r"#[0-9a-fA-F]{3,8}\b", value) and not re.search(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b", value):
        return "bad hex colour"
    return None
