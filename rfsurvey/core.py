"""Core spectrum-survey analytics engine (standard library only).

Input model: a CSV of spectrum sweep samples with at least two columns:
  - frequency in Hz (header any of: freq_hz, frequency_hz, freq, frequency, hz)
  - power in dBm    (header any of: power_dbm, power, dbm, level_dbm, level)
Optional column:
  - timestamp/sweep id (header any of: timestamp, time, sweep, ts) used to count
    how many sweeps a bin was occupied across the survey.

The engine computes per-band occupancy (fraction of bins above a noise-floor +
threshold), interference indicators, and statistical anomalies (outlier power
spikes via robust z-score on the median/MAD).
"""

from __future__ import annotations

import csv
import io
import math
from dataclasses import dataclass, field, asdict
from typing import Optional


# --- Named RF bands (Hz). Coarse, well-known allocations for labeling. ------
BANDS: list[tuple[str, float, float]] = [
    ("LF", 30_000, 300_000),
    ("MF/AM", 300_000, 3_000_000),
    ("HF/Shortwave", 3_000_000, 30_000_000),
    ("VHF-low", 30_000_000, 88_000_000),
    ("FM-broadcast", 88_000_000, 108_000_000),
    ("VHF-air/marine", 108_000_000, 174_000_000),
    ("VHF-high/UHF-TV", 174_000_000, 470_000_000),
    ("UHF", 470_000_000, 698_000_000),
    ("Cellular-700/800", 698_000_000, 960_000_000),
    ("ISM-915", 902_000_000, 928_000_000),
    ("Cellular-PCS/AWS", 960_000_000, 2_400_000_000),
    ("ISM-2.4/WiFi-BT", 2_400_000_000, 2_500_000_000),
    ("S-band", 2_500_000_000, 4_000_000_000),
    ("WiFi-5/C-band", 5_000_000_000, 6_000_000_000),
    ("SHF", 6_000_000_000, 30_000_000_000),
]


class SurveyError(Exception):
    """Raised on unrecoverable input problems (bad/empty/malformed data)."""


@dataclass
class Sample:
    freq_hz: float
    power_dbm: float
    sweep: Optional[str] = None


@dataclass
class BandStat:
    name: str
    low_hz: float
    high_hz: float
    bins: int
    occupied_bins: int
    occupancy: float          # fraction 0..1 of bins above squelch
    peak_dbm: float
    mean_dbm: float
    peak_freq_hz: float


@dataclass
class Anomaly:
    freq_hz: float
    power_dbm: float
    z_score: float
    band: str
    kind: str                 # "spike" or "persistent"


@dataclass
class SurveyReport:
    samples: int
    sweeps: int
    freq_min_hz: float
    freq_max_hz: float
    noise_floor_dbm: float
    squelch_dbm: float
    bands: list[BandStat] = field(default_factory=list)
    anomalies: list[Anomaly] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


_FREQ_KEYS = ("freq_hz", "frequency_hz", "freq", "frequency", "hz")
_POWER_KEYS = ("power_dbm", "power", "dbm", "level_dbm", "level")
_SWEEP_KEYS = ("timestamp", "time", "sweep", "ts")


def _pick(header: list[str], keys: tuple[str, ...]) -> Optional[str]:
    norm = {h.strip().lower(): h for h in header}
    for k in keys:
        if k in norm:
            return norm[k]
    return None


def load_samples(text: str) -> list[Sample]:
    """Parse spectrum-sweep CSV text into Sample rows.

    Raises SurveyError on missing required columns or zero valid rows.
    """
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise SurveyError("empty input: no CSV header found")
    header = list(reader.fieldnames)
    fcol = _pick(header, _FREQ_KEYS)
    pcol = _pick(header, _POWER_KEYS)
    scol = _pick(header, _SWEEP_KEYS)
    if fcol is None or pcol is None:
        raise SurveyError(
            "CSV must contain a frequency column (%s) and a power column (%s); got %s"
            % ("/".join(_FREQ_KEYS), "/".join(_POWER_KEYS), header)
        )
    out: list[Sample] = []
    for row in reader:
        raw_f = (row.get(fcol) or "").strip()
        raw_p = (row.get(pcol) or "").strip()
        if not raw_f or not raw_p:
            continue
        try:
            f = float(raw_f)
            p = float(raw_p)
        except ValueError:
            continue
        if not (math.isfinite(f) and math.isfinite(p)) or f <= 0:
            continue
        sweep = (row.get(scol) or "").strip() if scol else None
        out.append(Sample(freq_hz=f, power_dbm=p, sweep=sweep or None))
    if not out:
        raise SurveyError("no valid samples parsed from input")
    return out


def _median(values: list[float]) -> float:
    if not values:
        raise SurveyError("cannot compute median of an empty list")
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2.0


def _mad(values: list[float], med: float) -> float:
    devs = [abs(v - med) for v in values]
    return _median(devs)


def _band_for(freq_hz: float) -> str:
    for name, lo, hi in BANDS:
        if lo <= freq_hz < hi:
            return name
    return "out-of-range"


def estimate_noise_floor(samples: list[Sample]) -> float:
    """Robust noise-floor estimate: 10th-percentile power across all bins."""
    powers = sorted(s.power_dbm for s in samples)
    idx = max(0, int(0.10 * (len(powers) - 1)))
    return powers[idx]


def summarize_bands(samples: list[Sample], squelch_dbm: float) -> list[BandStat]:
    """Per-band occupancy and power statistics."""
    buckets: dict[str, list[Sample]] = {}
    for s in samples:
        buckets.setdefault(_band_for(s.freq_hz), []).append(s)

    stats: list[BandStat] = []
    band_index = {name: (lo, hi) for name, lo, hi in BANDS}
    band_index["out-of-range"] = (0.0, 0.0)
    for name, rows in buckets.items():
        lo, hi = band_index[name]
        powers = [r.power_dbm for r in rows]
        occ_rows = [r for r in rows if r.power_dbm >= squelch_dbm]
        peak = max(rows, key=lambda r: r.power_dbm)
        stats.append(
            BandStat(
                name=name,
                low_hz=lo,
                high_hz=hi,
                bins=len(rows),
                occupied_bins=len(occ_rows),
                occupancy=round(len(occ_rows) / len(rows), 4),
                peak_dbm=round(peak.power_dbm, 2),
                mean_dbm=round(sum(powers) / len(powers), 2),
                peak_freq_hz=peak.freq_hz,
            )
        )
    stats.sort(key=lambda b: b.low_hz)
    return stats


def detect_anomalies(
    samples: list[Sample],
    z_thresh: float = 6.0,
    persist_min_sweeps: int = 3,
) -> list[Anomaly]:
    """Find power-spike outliers (robust z-score) and persistent occupants.

    - spike: power dBm far above the band median (z = 0.6745*(x-med)/MAD).
    - persistent: a frequency bin occupied across >= persist_min_sweeps sweeps,
      which can indicate a constant emitter / interference source.
    """
    anomalies: list[Anomaly] = []

    # Group by band for locally-robust spike detection.
    by_band: dict[str, list[Sample]] = {}
    for s in samples:
        by_band.setdefault(_band_for(s.freq_hz), []).append(s)

    for band, rows in by_band.items():
        powers = [r.power_dbm for r in rows]
        med = _median(powers)
        mad = _mad(powers, med)
        if mad <= 0:
            continue
        for r in rows:
            z = 0.6745 * (r.power_dbm - med) / mad
            if z >= z_thresh:
                anomalies.append(
                    Anomaly(
                        freq_hz=r.freq_hz,
                        power_dbm=round(r.power_dbm, 2),
                        z_score=round(z, 2),
                        band=band,
                        kind="spike",
                    )
                )

    # Persistent emitters: same rounded freq present in many distinct sweeps.
    sweeps_present = {s.sweep for s in samples if s.sweep is not None}
    if len(sweeps_present) >= 2:
        per_freq: dict[float, set] = {}
        per_freq_power: dict[float, float] = {}
        for s in samples:
            if s.sweep is None:
                continue
            key = round(s.freq_hz, 0)
            per_freq.setdefault(key, set()).add(s.sweep)
            per_freq_power[key] = max(per_freq_power.get(key, s.power_dbm), s.power_dbm)
        for key, sw in per_freq.items():
            if len(sw) >= persist_min_sweeps:
                anomalies.append(
                    Anomaly(
                        freq_hz=key,
                        power_dbm=round(per_freq_power[key], 2),
                        z_score=float(len(sw)),
                        band=_band_for(key),
                        kind="persistent",
                    )
                )

    anomalies.sort(key=lambda a: (a.kind, -a.z_score))
    return anomalies


def analyze(
    text: str,
    squelch_offset_db: float = 10.0,
    z_thresh: float = 6.0,
    persist_min_sweeps: int = 3,
) -> SurveyReport:
    """End-to-end: parse CSV -> noise floor -> band stats -> anomalies."""
    if not math.isfinite(squelch_offset_db):
        raise SurveyError("squelch_offset_db must be a finite number")
    if not math.isfinite(z_thresh) or z_thresh <= 0:
        raise SurveyError("z_thresh must be a positive finite number")
    if persist_min_sweeps < 1:
        raise SurveyError("persist_min_sweeps must be >= 1")
    samples = load_samples(text)
    noise_floor = estimate_noise_floor(samples)
    squelch = noise_floor + squelch_offset_db
    bands = summarize_bands(samples, squelch)
    anomalies = detect_anomalies(samples, z_thresh, persist_min_sweeps)
    sweeps = len({s.sweep for s in samples if s.sweep is not None})
    freqs = [s.freq_hz for s in samples]
    return SurveyReport(
        samples=len(samples),
        sweeps=sweeps,
        freq_min_hz=min(freqs),
        freq_max_hz=max(freqs),
        noise_floor_dbm=round(noise_floor, 2),
        squelch_dbm=round(squelch, 2),
        bands=bands,
        anomalies=anomalies,
    )
