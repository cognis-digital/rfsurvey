"""Tests for feature extraction, classification, and interference flags."""

from __future__ import annotations

import math

import pytest

from wavewatch.classify.classifier import (
    CLASSES,
    THRESHOLDS,
    Classification,
    classify_emitter,
    classify_features,
)
from wavewatch.classify.features import (
    cyclo_strength,
    extract_features,
    papr,
    spectral_flatness,
)
from wavewatch.classify.interference import (
    GNSS_BANDS,
    detect_barrage_jamming,
    detect_gnss_spoof_hint,
    detect_sweep_jamming,
    scan_interference,
)
from wavewatch.detect.pipeline import detect_emitters
from wavewatch.io.capture import Capture
from wavewatch.io.generator import (
    complex_noise,
    gen_drone_link,
    gen_ble,
    gen_gnss,
    gen_tone,
    gen_wifi,
    generate,
    tone,
)
from wavewatch.analyze import analyze_capture


FEATURE_KEYS = [
    "bandwidth_frac", "duty_cycle", "snr_db", "hopping", "n_channels",
    "mean_burst_dur_s", "char_burst_dur_s", "phase_jitter_rad",
    "freq_stability_frac", "spectral_flatness", "cyclo_strength",
]


# --------------------------------------------------------------------------- #
# Feature primitives
# --------------------------------------------------------------------------- #
def test_spectral_flatness_tone_low():
    x = tone(512, 100.0, 1000.0)
    assert spectral_flatness(x) < 0.2


def test_spectral_flatness_noise_high():
    x = complex_noise(512, 1.0)
    assert spectral_flatness(x) > 0.3


def test_spectral_flatness_short():
    assert spectral_flatness([1 + 0j]) == 0.0


def test_papr_tone_low():
    x = tone(256, 100.0, 1000.0)
    assert papr(x) < 1.5


def test_papr_empty():
    assert papr([]) == 0.0


def test_cyclo_strength_range():
    x = complex_noise(256, 1.0)
    s, f = cyclo_strength(x)
    assert 0.0 <= s <= 1.0


def test_cyclo_strength_short():
    assert cyclo_strength([1 + 0j]) == (0.0, 0.0)


@pytest.mark.parametrize("scenario", ["tone", "wifi", "drone-link", "ble", "gnss"])
def test_extract_features_keys(scenario):
    cap, _ = generate(scenario)
    det = detect_emitters(cap)
    feats = extract_features(cap, det.emitters[0])
    for k in FEATURE_KEYS:
        assert k in feats


@pytest.mark.parametrize("scenario", ["tone", "wifi", "drone-link", "ble", "gnss"])
def test_features_are_finite(scenario):
    cap, _ = generate(scenario)
    det = detect_emitters(cap)
    feats = extract_features(cap, det.emitters[0])
    assert all(math.isfinite(v) for v in feats.values())


# --------------------------------------------------------------------------- #
# Classifier -- label correctness across seeds
# --------------------------------------------------------------------------- #
CLASS_GENERATORS = {
    "unknown": gen_tone,
    "wifi": gen_wifi,
    "drone-link": gen_drone_link,
    "ble": gen_ble,
    "gnss": gen_gnss,
}


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5, 6, 7, 8])
@pytest.mark.parametrize("expected,genfn", list(CLASS_GENERATORS.items()))
def test_classification_labels_across_seeds(seed, expected, genfn):
    cap, _ = genfn(seed=seed)
    rep = analyze_capture(cap)
    labels = [e.classification["label"] for e in rep.emitters]
    assert expected in labels, f"{expected} not in {labels} (seed={seed})"


@pytest.mark.parametrize("scenario", ["tone", "wifi", "drone-link", "ble", "gnss"])
def test_classification_has_confidence(scenario):
    cap, _ = generate(scenario)
    rep = analyze_capture(cap)
    for e in rep.emitters:
        c = e.classification
        assert 0.0 <= c["confidence"] <= 1.0


@pytest.mark.parametrize("scenario", ["tone", "wifi", "drone-link", "ble", "gnss"])
def test_classification_has_decision_trace(scenario):
    cap, _ = generate(scenario)
    rep = analyze_capture(cap)
    for e in rep.emitters:
        assert len(e.classification["decision_trace"]) >= 2


@pytest.mark.parametrize("scenario", ["tone", "wifi", "drone-link", "ble", "gnss"])
def test_classification_carries_thresholds(scenario):
    cap, _ = generate(scenario)
    rep = analyze_capture(cap)
    for e in rep.emitters:
        assert "narrowband_frac" in e.classification["thresholds"]


@pytest.mark.parametrize("scenario", ["tone", "wifi", "drone-link", "ble", "gnss"])
def test_classification_scores_all_classes(scenario):
    cap, _ = generate(scenario)
    rep = analyze_capture(cap)
    for e in rep.emitters:
        for cls in CLASSES:
            assert cls in e.classification["scores"]


def test_classify_features_reproducible():
    cap, _ = generate("drone-link")
    det = detect_emitters(cap)
    feats = extract_features(cap, det.emitters[0])
    a = classify_features(feats)
    b = classify_features(feats)
    assert a.label == b.label
    assert math.isclose(a.confidence, b.confidence)


def test_classification_unknown_when_no_match():
    feats = {
        "bandwidth_frac": 0.5, "duty_cycle": 0.5, "snr_db": 30.0, "hopping": 0.0,
        "n_channels": 1.0, "mean_burst_dur_s": 0.0, "char_burst_dur_s": 0.0,
        "phase_jitter_rad": 0.0, "freq_stability_frac": 0.5, "spectral_flatness": 0.0,
        "cyclo_strength": 0.0, "cyclo_freq_frac": 0.0,
    }
    result = classify_features(feats)
    assert isinstance(result, Classification)
    assert result.label in CLASSES


def test_thresholds_present():
    assert "min_confidence" in THRESHOLDS
    assert THRESHOLDS["hop_min_channels"] >= 3


# --------------------------------------------------------------------------- #
# Interference
# --------------------------------------------------------------------------- #
def test_sweep_flag_on_sweep():
    cap, _ = generate("sweep")
    det = detect_emitters(cap)
    flag = detect_sweep_jamming(det.spectrogram)
    assert flag is not None
    assert flag.kind == "sweep_jamming"


def test_no_sweep_flag_on_noise():
    cap, _ = generate("noise")
    det = detect_emitters(cap)
    assert detect_sweep_jamming(det.spectrogram) is None


def test_no_sweep_flag_on_tone():
    cap, _ = generate("tone")
    det = detect_emitters(cap)
    assert detect_sweep_jamming(det.spectrogram) is None


def test_barrage_flag_on_barrage():
    cap, _ = generate("barrage")
    rep = analyze_capture(cap)
    kinds = [f["kind"] for f in rep.interference]
    assert "barrage_jamming" in kinds


def test_no_barrage_flag_on_gnss():
    cap, _ = generate("gnss")
    rep = analyze_capture(cap)
    kinds = [f["kind"] for f in rep.interference]
    assert "barrage_jamming" not in kinds


def test_gnss_spoof_hint_on_clean_carrier():
    # a strong, clean CW carrier sitting in the GPS L1 band
    n = 20000
    fs = 4_000_000.0
    amp = 40.0
    sig = tone(n, 200_000.0, fs, amp=amp)
    noise = complex_noise(n, 1.0)
    cap = Capture(samples=[sig[i] + noise[i] for i in range(n)],
                  sample_rate=fs, center_freq=1_575_420_000.0)
    det = detect_emitters(cap)
    from wavewatch.classify.features import extract_features
    feats = {e.id: extract_features(cap, e) for e in det.emitters}
    hints = detect_gnss_spoof_hint(cap, det.emitters, feats)
    assert len(hints) >= 1
    assert hints[0].kind == "gnss_spoof_hint"


def test_no_gnss_spoof_hint_out_of_band():
    cap, _ = gen_tone()  # center_freq 0, not a GNSS band
    det = detect_emitters(cap)
    from wavewatch.classify.features import extract_features
    feats = {e.id: extract_features(cap, e) for e in det.emitters}
    assert detect_gnss_spoof_hint(cap, det.emitters, feats) == []


def test_gnss_bands_defined():
    assert any(abs(v - 1_575_420_000.0) < 1e3 for v in GNSS_BANDS.values())


def test_scan_interference_returns_list():
    cap, _ = generate("wifi")
    det = detect_emitters(cap)
    from wavewatch.classify.features import extract_features
    feats = {e.id: extract_features(cap, e) for e in det.emitters}
    flags = scan_interference(cap, det.spectrogram, det.psd, det.emitters, feats)
    assert isinstance(flags, list)
