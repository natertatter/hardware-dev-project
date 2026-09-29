"""Pull text out of PDF bytes using the stdlib (no PDF package).

Handles uncompressed literal strings and FlateDecode content streams.
Scanned pages and custom font encodings are out of scope; those return
empty text so the caller can fall back to a reviewable template.
"""

from __future__ import annotations

import re
import zlib

_STREAM_RE = re.compile(rb"stream\r?\n(.*?)\r?\n?endstream", re.DOTALL)
_LITERAL_RE = re.compile(rb"\((?:\\.|[^\\)])*\)")
_MAX_TEXT_CHARS = 200_000


def extract_pdf_text(content: bytes) -> str:
    """Return newline-joined text from PDF content streams, or empty."""
    pieces: list[str] = []
    streams = _iter_streams(content)
    sources = streams if streams else [content]
    for data in sources:
        piece = _literals_from(data)
        if piece:
            pieces.append(piece)
    text = "\n".join(pieces).strip()
    if len(text) > _MAX_TEXT_CHARS:
        text = text[:_MAX_TEXT_CHARS]
    if _printable_ratio(text) < 0.85:
        return ""
    return text


def _iter_streams(content: bytes) -> list[bytes]:
    streams: list[bytes] = []
    for match in _STREAM_RE.finditer(content):
        raw = match.group(1)
        header_start = max(0, match.start() - 500)
        header = content[header_start : match.start()]
        if b"FlateDecode" in header:
            try:
                raw = zlib.decompress(raw)
            except zlib.error:
                continue
        streams.append(raw)
    return streams


def _literals_from(data: bytes) -> str:
    lines: list[str] = []
    for match in _LITERAL_RE.finditer(data):
        raw = match.group()[1:-1]
        text = _unescape_pdf_literal(raw).strip()
        if text:
            lines.append(text)
    return "\n".join(lines)


def _unescape_pdf_literal(raw: bytes) -> str:
    out = bytearray()
    i = 0
    while i < len(raw):
        current = raw[i]
        if current != 0x5C or i + 1 >= len(raw):
            out.append(current)
            i += 1
            continue
        nxt = raw[i + 1]
        simple = {
            ord("n"): 0x0A,
            ord("r"): 0x0D,
            ord("t"): 0x09,
            ord("b"): 0x08,
            ord("f"): 0x0C,
            ord("("): ord("("),
            ord(")"): ord(")"),
            ord("\\"): ord("\\"),
        }
        if nxt in simple:
            out.append(simple[nxt])
            i += 2
            continue
        if 48 <= nxt <= 55:
            j = i + 1
            octal = bytearray()
            while j < len(raw) and j < i + 4 and 48 <= raw[j] <= 55:
                octal.append(raw[j])
                j += 1
            out.append(int(octal, 8) & 0xFF)
            i = j
            continue
        out.append(nxt)
        i += 2
    return out.decode("latin-1", errors="replace")


def _printable_ratio(text: str) -> float:
    if not text:
        return 1.0
    ok = sum(1 for ch in text if ch.isprintable() or ch in "\n\t")
    return ok / len(text)
