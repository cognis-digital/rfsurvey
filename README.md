# wavewatch

**Offline RF signal reconnaissance and triage from capture files.**

wavewatch detects, fingerprints, and classifies radio emitters from standard IQ
and spectrum capture files, entirely offline, using a pure-Python DSP core. It
turns a raw recording into reproducible, machine-readable findings — with a
decision trace for every classification — so RF triage can drop into an
automated analysis pipeline.

A Cognis Digital tool.

---

## Scope: defensive, lawful-by-design

wavewatch is **analysis only**. It reads capture files and reports what it sees.

- **No transmit path.** Nothing in this package emits RF.
- **No jamming or countermeasures.** Interference detectors flag the *signature*
  of sweep/barrage jamming and GNSS spoofing so an analyst can triage a link's
  health — they never generate or counter a signal.
- **No payload demodulation.** Emitters are labelled by their *stability and
  cyclostationary signatures*, not by decoding their contents. This is a
  deliberate privacy- and lawful-by-design choice.
- **No weaponization.** There is no targeting, guidance, or control capability.

These boundaries are enforced by the test suite (`tests/test_defensive_scope.py`),
so a change that adds an offensive capability fails CI.

Operate wavewatch only on signals you are authorized to record and analyze, in
accordance with applicable law and spectrum regulations.

---

## Highlights

- **Zero third-party runtime dependencies.** Python 3.11+ standard library only.
  The FFT (radix-2 Cooley–Tukey + Bluestein for arbitrary lengths), PSD (Welch),
  spectrogram, and the annotated-spectrogram **PNG encoder** (`zlib` + `struct`)
  are all implemented from scratch. No NumPy, SciPy, PIL, or matplotlib.
- **Works without SDR hardware.** Reads **SigMF**, **WAV-IQ**, and **CSV
  power-spectra**. A built-in synthetic-signal generator means tests and demos
  need no external data.
- **Emitter detection.** CFAR / energy band detection, burst segmentation, and
  frequency-hopping grouping.
- **Fingerprint & classify.** Phase-jitter, frequency-stability, spectral
  flatness, and cyclostationary features label a likely class
  (`drone-link` / `wifi` / `ble` / `gnss` / `unknown`) with a confidence score —
  without decoding any payload.
- **Interference flags.** Sweep- and barrage-jamming signatures and GNSS-spoofing
  hints (interoperates with `spoofwatch`).
- **Reproducible decisions.** Every classification carries its features,
  thresholds, and a step-by-step decision trace.
- **Outputs.** JSON, SARIF-style findings, GeoJSON (when position metadata is
  present), and an annotated spectrogram PNG.
- **MCP server.** A self-contained JSON-RPC/stdio MCP server exposes an
  `analyze_capture` tool for agent pipelines.

---

## Install

```bash
pip install .
# or run straight from a checkout, no install required:
python -m wavewatch --help
```

Requires Python 3.11+. `pytest` is only needed to run the tests.

---

## Quickstart

Analyze a synthetic scenario (no capture file needed) and write every output:

```bash
python -m wavewatch analyze --scenario drone-link \
    --json out/report.json --sarif out/findings.sarif \
    --geojson out/emitters.geojson --png out/spectrogram.png
```

Analyze a real capture file (format is auto-detected by extension):

```bash
python -m wavewatch analyze capture.sigmf-meta --json -
python -m wavewatch analyze recording.wav --png spec.png
python -m wavewatch analyze spectrum.csv --json report.json
```

Generate a synthetic capture to disk (SigMF or WAV-IQ):

```bash
python -m wavewatch generate wifi --out samples/wifi        # SigMF
python -m wavewatch generate ble  --out samples/ble.wav     # WAV-IQ
```

Available scenarios: `noise`, `tone`, `wifi`, `drone-link`, `ble`, `gnss`,
`sweep`, `barrage`.

---

## Library usage

```python
from wavewatch import analyze_capture, load_capture, generate

capture, _ = generate("drone-link")          # or: load_capture("capture.sigmf-meta")
report = analyze_capture(capture)

print(report.summary())
for e in report.emitters:
    emitter = e.emitter
    cls = e.classification
    print(emitter["rf_center_hz"], cls["label"], cls["confidence"])
    for step in cls["decision_trace"]:
        print("  ", step)
```

---

## MCP server

Run the stdio MCP server and call the `analyze_capture` tool from an agent:

```bash
python -m wavewatch serve-mcp
```

The server implements `initialize`, `tools/list`, and `tools/call` over
JSON-RPC 2.0 (one JSON message per line). `analyze_capture` accepts either a
capture `path` or a synthetic `scenario`, and returns structured findings as
JSON or SARIF.

---

## How it works

1. **Ingest** — a capture is read into an in-memory `Capture` (IQ samples or a
   pre-computed spectrum) with sample rate, center frequency, and optional
   geolocation.
2. **Transform** — a Welch PSD and an STFT spectrogram are computed with the
   pure-Python DSP core.
3. **Detect** — CFAR-style band detection segments occupied spectrum; per-band
   burst segmentation measures temporal activity; narrowband, bursty channels
   scattered across the band are grouped into a single frequency-hopping emitter.
4. **Fingerprint** — for each emitter, stability and structure features are
   measured on the raw samples (phase jitter, frequency stability, spectral
   flatness, cyclostationary strength) — never the payload.
5. **Classify** — interpretable membership rules score each class; the highest
   score wins, and the features, thresholds, and reasoning are recorded as a
   decision trace.
6. **Flag & report** — interference detectors add jamming/spoofing flags, and
   results are emitted as JSON / SARIF / GeoJSON / annotated PNG.

---

## Capture formats

| Format         | Read | Write | Notes                                                    |
| -------------- | :--: | :---: | -------------------------------------------------------- |
| SigMF          |  ✓   |   ✓   | `cf32`, `cf64`, `ci16`, `ci8`, `cu8` (+ real variants)   |
| WAV-IQ         |  ✓   |   ✓   | 2-channel (I=left, Q=right), 16-bit PCM or 32-bit float  |
| CSV spectrum   |  ✓   |   ✓   | `frequency,power` rows, or a single power column         |

A receive-only live-capture adapter *interface* is provided
(`wavewatch.io.live.LiveCaptureAdapter`) for out-of-tree SDR backends. The core
ships no hardware driver and remains file-based and offline. There is,
deliberately, no transmit method.

---

## Tests

```bash
python -m pytest -q
```

The suite covers FFT correctness against direct DFTs, PSD/spectrogram behavior,
each detector and classifier path, every reader/writer, PNG-encoder validity,
the MCP server and CLI, edge cases (empty / DC-only / pure-noise / clipped
captures), and the defensive-scope guardrails.

---

## License

MIT — see [LICENSE](LICENSE).
