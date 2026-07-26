"""Self-contained PNG encoder and a small drawing canvas.

Uses only stdlib ``zlib`` and ``struct`` -- no PIL, no matplotlib. Emits 8-bit
truecolor (RGB) PNGs.
"""

from __future__ import annotations

import struct
import zlib
from typing import List, Sequence, Tuple

from .font import GLYPH_HEIGHT, GLYPH_WIDTH, glyph

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
RGB = Tuple[int, int, int]


def _chunk(tag: bytes, data: bytes) -> bytes:
    out = struct.pack(">I", len(data)) + tag + data
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return out + struct.pack(">I", crc)


def encode_png(width: int, height: int, pixels: bytes) -> bytes:
    """Encode an RGB pixel buffer (``height*width*3`` bytes) to PNG bytes."""
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")
    if len(pixels) != width * height * 3:
        raise ValueError("pixel buffer size mismatch")
    # add a filter byte (0 = None) at the start of each scanline
    stride = width * 3
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        raw.extend(pixels[y * stride:(y + 1) * stride])
    compressed = zlib.compress(bytes(raw), 9)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        PNG_SIGNATURE
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", compressed)
        + _chunk(b"IEND", b"")
    )


class Canvas:
    """A simple RGB drawing surface that serializes to PNG."""

    def __init__(self, width: int, height: int, background: RGB = (0, 0, 0)) -> None:
        if width <= 0 or height <= 0:
            raise ValueError("width and height must be positive")
        self.width = width
        self.height = height
        self.buf = bytearray(width * height * 3)
        self.fill(background)

    def fill(self, color: RGB) -> None:
        r, g, b = color
        self.buf[:] = bytes((r, g, b)) * (self.width * self.height)

    def set_pixel(self, x: int, y: int, color: RGB) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            i = (y * self.width + x) * 3
            self.buf[i] = color[0] & 0xFF
            self.buf[i + 1] = color[1] & 0xFF
            self.buf[i + 2] = color[2] & 0xFF

    def get_pixel(self, x: int, y: int) -> RGB:
        i = (y * self.width + x) * 3
        return (self.buf[i], self.buf[i + 1], self.buf[i + 2])

    def hline(self, x0: int, x1: int, y: int, color: RGB) -> None:
        if x1 < x0:
            x0, x1 = x1, x0
        for x in range(x0, x1 + 1):
            self.set_pixel(x, y, color)

    def vline(self, x: int, y0: int, y1: int, color: RGB) -> None:
        if y1 < y0:
            y0, y1 = y1, y0
        for y in range(y0, y1 + 1):
            self.set_pixel(x, y, color)

    def rect(self, x0: int, y0: int, x1: int, y1: int, color: RGB) -> None:
        """Draw a rectangle outline."""
        self.hline(x0, x1, y0, color)
        self.hline(x0, x1, y1, color)
        self.vline(x0, y0, y1, color)
        self.vline(x1, y0, y1, color)

    def fill_rect(self, x0: int, y0: int, x1: int, y1: int, color: RGB) -> None:
        if x1 < x0:
            x0, x1 = x1, x0
        if y1 < y0:
            y0, y1 = y1, y0
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self.set_pixel(x, y, color)

    def draw_text(self, x: int, y: int, text: str, color: RGB, scale: int = 1) -> int:
        """Draw ``text`` with the built-in font. Returns the x cursor after drawing."""
        cx = x
        for ch in text:
            rows = glyph(ch)
            for gy in range(GLYPH_HEIGHT):
                row = rows[gy]
                for gx in range(GLYPH_WIDTH):
                    if gx < len(row) and row[gx] == "#":
                        for sy in range(scale):
                            for sx in range(scale):
                                self.set_pixel(cx + gx * scale + sx,
                                               y + gy * scale + sy, color)
            cx += (GLYPH_WIDTH + 1) * scale
        return cx

    def text_width(self, text: str, scale: int = 1) -> int:
        return len(text) * (GLYPH_WIDTH + 1) * scale

    def to_png(self) -> bytes:
        return encode_png(self.width, self.height, bytes(self.buf))

    def save(self, path: str) -> str:
        with open(path, "wb") as fh:
            fh.write(self.to_png())
        return path


def viridis(t: float) -> RGB:
    """Approximate viridis colormap; ``t`` in [0, 1] -> (r, g, b)."""
    t = 0.0 if t < 0 else (1.0 if t > 1 else t)
    stops = [
        (0.0, (68, 1, 84)),
        (0.25, (59, 82, 139)),
        (0.5, (33, 145, 140)),
        (0.75, (94, 201, 98)),
        (1.0, (253, 231, 37)),
    ]
    for i in range(len(stops) - 1):
        t0, c0 = stops[i]
        t1, c1 = stops[i + 1]
        if t0 <= t <= t1:
            f = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
            return (
                int(c0[0] + (c1[0] - c0[0]) * f),
                int(c0[1] + (c1[1] - c0[1]) * f),
                int(c0[2] + (c1[2] - c0[2]) * f),
            )
    return stops[-1][1]
