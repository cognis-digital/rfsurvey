"""WAV-IQ reader/writer (pure stdlib ``struct``).

Interprets a 2-channel WAV as complex IQ: left channel = I, right channel = Q.
Supports 16-bit PCM and 32-bit IEEE float sample formats. A ``sample_rate``
override is accepted because WAV headers cannot carry an RF center frequency.
"""

from __future__ import annotations

import struct
from typing import List, Tuple

from .capture import Capture

Complex = complex


def _read_chunks(raw: bytes):
    if raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
        raise ValueError("not a RIFF/WAVE file")
    pos = 12
    fmt = None
    data = None
    while pos + 8 <= len(raw):
        cid = raw[pos:pos + 4]
        (size,) = struct.unpack("<I", raw[pos + 4:pos + 8])
        body = raw[pos + 8:pos + 8 + size]
        if cid == b"fmt ":
            fmt = body
        elif cid == b"data":
            data = body
        pos += 8 + size + (size & 1)  # chunks are word-aligned
    if fmt is None or data is None:
        raise ValueError("missing fmt or data chunk")
    return fmt, data


def read_waviq(path: str, center_freq: float = 0.0) -> Capture:
    """Read a 2-channel WAV file as complex IQ (I=left, Q=right)."""
    with open(path, "rb") as fh:
        raw = fh.read()
    fmt, data = _read_chunks(raw)
    audio_format, channels, sample_rate, _byte_rate, _block_align, bits = \
        struct.unpack("<HHIIHH", fmt[:16])

    if channels != 2:
        raise ValueError(f"WAV-IQ expects 2 channels (I/Q); got {channels}")

    if audio_format == 3 and bits == 32:  # IEEE float
        vals = [v[0] for v in struct.iter_unpack("<f", data[: (len(data) // 4) * 4])]
    elif audio_format == 1 and bits == 16:  # PCM 16
        vals = [v[0] / 32768.0 for v in struct.iter_unpack("<h", data[: (len(data) // 2) * 2])]
    elif audio_format == 1 and bits == 8:  # unsigned PCM 8
        vals = [(v[0] - 128) / 128.0 for v in struct.iter_unpack("<B", data)]
    else:
        raise ValueError(f"unsupported WAV format code={audio_format} bits={bits}")

    samples: List[Complex] = []
    for i in range(0, len(vals) - 1, 2):
        samples.append(complex(vals[i], vals[i + 1]))

    return Capture(
        samples=samples,
        sample_rate=float(sample_rate),
        center_freq=center_freq,
        source=path,
        metadata={"format": "wav-iq", "bits": bits, "audio_format": audio_format},
        kind="iq",
    )


def write_waviq(path: str, capture: Capture, float32: bool = True) -> str:
    """Write a capture to a 2-channel WAV (I=left, Q=right)."""
    samples = capture.samples
    fs = int(round(capture.sample_rate))
    if float32:
        audio_format, bits = 3, 32
        frames = b"".join(struct.pack("<ff", s.real, s.imag) for s in samples)
    else:
        audio_format, bits = 1, 16
        def q(v: float) -> int:
            return max(-32768, min(32767, int(round(v * 32767))))
        frames = b"".join(struct.pack("<hh", q(s.real), q(s.imag)) for s in samples)

    channels = 2
    block_align = channels * bits // 8
    byte_rate = fs * block_align
    data_size = len(frames)
    fmt_chunk = struct.pack("<HHIIHH", audio_format, channels, fs, byte_rate, block_align, bits)
    riff_size = 4 + (8 + len(fmt_chunk)) + (8 + data_size)
    with open(path, "wb") as fh:
        fh.write(b"RIFF")
        fh.write(struct.pack("<I", riff_size))
        fh.write(b"WAVE")
        fh.write(b"fmt ")
        fh.write(struct.pack("<I", len(fmt_chunk)))
        fh.write(fmt_chunk)
        fh.write(b"data")
        fh.write(struct.pack("<I", data_size))
        fh.write(frames)
    return path
