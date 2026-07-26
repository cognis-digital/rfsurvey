"""Render an annotated spectrogram PNG (pure stdlib)."""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence

from ..dsp.spectrogram import Spectrogram
from ..dsp.util import db10, percentile
from ..detect.model import Emitter
from .png import Canvas, viridis

_BG = (18, 18, 24)
_AXIS = (200, 200, 210)
_BOX = (255, 80, 80)
_TEXT = (240, 240, 245)


def _power_to_norm(spec: Spectrogram):
    """Flatten spectrogram to a dB grid normalized to [0,1] for coloring."""
    grid = []
    all_db = []
    for row in spec.power:
        drow = [db10(v) for v in row]
        grid.append(drow)
        all_db.extend(drow)
    if not all_db:
        return grid, 0.0, 1.0
    lo = percentile(all_db, 5.0)
    hi = percentile(all_db, 99.0)
    if hi <= lo:
        hi = lo + 1.0
    return grid, lo, hi


def render_spectrogram_png(spec: Optional[Spectrogram], emitters: Sequence[Emitter],
                           path: str, labels: Optional[Dict[int, str]] = None,
                           width: int = 640, height: int = 400,
                           center_freq: float = 0.0,
                           title: str = "wavewatch spectrogram") -> str:
    """Render a spectrogram with emitter bounding boxes and axis labels."""
    labels = labels or {}
    margin_l, margin_r, margin_t, margin_b = 60, 20, 24, 30
    plot_w = max(1, width - margin_l - margin_r)
    plot_h = max(1, height - margin_t - margin_b)

    cv = Canvas(width, height, background=_BG)
    cv.draw_text(6, 6, title[:70], _TEXT, scale=1)

    if spec is None or spec.n_frames == 0 or spec.n_bins == 0:
        cv.draw_text(margin_l, height // 2, "NO SPECTROGRAM DATA", _AXIS)
        return cv.save(path)

    grid, lo, hi = _power_to_norm(spec)
    n_frames = spec.n_frames
    n_bins = spec.n_bins

    # paint the spectrogram: x=frequency, y=time (top = start)
    for py in range(plot_h):
        frame = int(py * n_frames / plot_h)
        frame = min(frame, n_frames - 1)
        drow = grid[frame]
        for px in range(plot_w):
            b = int(px * n_bins / plot_w)
            b = min(b, n_bins - 1)
            t = (drow[b] - lo) / (hi - lo)
            cv.set_pixel(margin_l + px, margin_t + py, viridis(t))

    # axes box
    cv.rect(margin_l, margin_t, margin_l + plot_w - 1, margin_t + plot_h - 1, _AXIS)

    # frequency axis ticks/labels
    f0 = spec.freqs[0]
    f1 = spec.freqs[-1]
    fspan = f1 - f0 if f1 != f0 else 1.0
    for k in range(5):
        frac = k / 4.0
        fx = margin_l + int(frac * (plot_w - 1))
        cv.vline(fx, margin_t + plot_h, margin_t + plot_h + 4, _AXIS)
        freq_hz = (f0 + frac * fspan) + center_freq
        label = _fmt_hz(freq_hz)
        cv.draw_text(max(0, fx - cv.text_width(label) // 2),
                     margin_t + plot_h + 8, label, _AXIS, scale=1)

    # emitter boxes
    for e in emitters:
        x0 = margin_l + int(((e.f_lo - f0) / fspan) * (plot_w - 1))
        x1 = margin_l + int(((e.f_hi - f0) / fspan) * (plot_w - 1))
        x0 = max(margin_l, min(margin_l + plot_w - 1, x0))
        x1 = max(margin_l, min(margin_l + plot_w - 1, x1))
        if x1 - x0 < 2:
            x1 = min(margin_l + plot_w - 1, x0 + 2)
        # time extent
        if e.bursts and spec.times:
            tmax = spec.times[-1] if spec.times[-1] > 0 else 1.0
            ty0 = margin_t + int((min(b.t_start for b in e.bursts) / tmax) * (plot_h - 1))
            ty1 = margin_t + int((max(b.t_end for b in e.bursts) / tmax) * (plot_h - 1))
        else:
            ty0, ty1 = margin_t, margin_t + plot_h - 1
        ty0 = max(margin_t, min(margin_t + plot_h - 1, ty0))
        ty1 = max(margin_t, min(margin_t + plot_h - 1, ty1))
        if ty1 - ty0 < 2:
            ty1 = min(margin_t + plot_h - 1, ty0 + 2)
        cv.rect(x0, ty0, x1, ty1, _BOX)
        lbl = labels.get(e.id, "")
        if lbl:
            cv.draw_text(x0 + 1, max(margin_t, ty0 - 9), lbl.upper()[:14], _BOX, scale=1)

    return cv.save(path)


def _fmt_hz(hz: float) -> str:
    a = abs(hz)
    if a >= 1e9:
        return f"{hz/1e9:.3f}G"
    if a >= 1e6:
        return f"{hz/1e6:.2f}M"
    if a >= 1e3:
        return f"{hz/1e3:.1f}K"
    return f"{hz:.0f}"
