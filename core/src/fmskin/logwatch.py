"""Read FM27's Player.log for the skin loader's own messages."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

_PATTERNS = [
    ("ignored", re.compile(r"^\[Skins\] Ignoring skin '(?P<skin>[^']*)': (?P<detail>.*)$")),
    ("parse-error", re.compile(r"^\[Skins\] Failed to parse skin\.json: (?P<detail>.*)$")),
    ("uss", re.compile(r"^\[USS\] (?P<detail>.*)$")),
    ("decode-failed", re.compile(r"^.*Skin sheet decode failed for (?P<detail>.*)$")),
]


@dataclass
class LogEvent:
    kind: str
    skin: str | None
    detail: str
    offset: int

    def to_json(self) -> dict:
        return asdict(self)


def parse_lines(text: str, base_offset: int = 0) -> list[LogEvent]:
    events, offset = [], base_offset
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        for kind, pattern in _PATTERNS:
            m = pattern.match(stripped)
            if m:
                skin = m.groupdict().get("skin")
                detail = m.group("detail")
                if skin is None:
                    s = re.search(r"'([^'/]+)/", detail)
                    skin = s.group(1) if s else None
                events.append(LogEvent(kind, skin, detail, offset))
                break
        offset += len(line.encode("utf-8", errors="replace"))
    return events


def read_since(log: Path, offset: int = 0) -> tuple[list[LogEvent], int]:
    """Events after byte `offset`; returns (events, new_offset). Restarts from 0 if the log was rotated."""
    if not log.is_file():
        return [], 0
    size = log.stat().st_size
    if offset > size:
        offset = 0
    with log.open("rb") as fh:
        fh.seek(offset)
        data = fh.read()
    return parse_lines(data.decode("utf-8", errors="replace"), offset), offset + len(data)
