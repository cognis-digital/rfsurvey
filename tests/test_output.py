"""Tests for output writers: PNG encoder, spectrogram render, JSON/SARIF/GeoJSON."""

from __future__ import annotations

import json
import struct
import zlib

import pytest

from wavewatch.analyze import analyze_capture
from wavewatch.io.generator import generate
from wavewatch.output.geojson import to_geojson, write_geojson
from wavewatch.output.json_out import to_json, write_json
from wavewatch.output.png import Canvas, encode_png, viridis
from wavewatch.output.sarif import SARIF_VERSION, to_sarif, write_sarif
from wavewatch.output.spectro_png import render_spectrogram_png

PNG_SIG = b"\x89PNG\r\n\x1a\n"


# --------------------------------------------------------------------------- #
# PNG encoder
# --------------------------------------------------------------------------- #
def _decode_png_chunks(data):
    assert data[:8] == PNG_SIG
    pos = 8
    chunks = []
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        tag = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        crc = struct.unpack(">I", data[pos + 8 + length:pos + 12 + length])[0]
        assert zlib.crc32(tag + body) & 0xFFFFFFFF == crc
        chunks.append((tag, body))
        pos += 12 + length
    return chunks


@pytest.mark.parametrize("w,h", [(1, 1), (4, 4), (16, 8), (64, 32), (100, 50)])
def test_encode_png_signature_and_chunks(w, h):
    pixels = bytes([120]) * (w * h * 3)
    data = encode_png(w, h, pixels)
    chunks = _decode_png_chunks(data)
    tags = [c[0] for c in chunks]
    assert tags[0] == b"IHDR"
    assert b"IDAT" in tags
    assert tags[-1] == b"IEND"


@pytest.mark.parametrize("w,h", [(4, 4), (16, 16), (32, 8)])
def test_encode_png_ihdr_dimensions(w, h):
    pixels = bytes(w * h * 3)
    data = encode_png(w, h, pixels)
    chunks = _decode_png_chunks(data)
    ihdr = dict(chunks)[b"IHDR"]
    width, height, depth, ctype = struct.unpack(">IIBB", ihdr[:10])
    assert (width, height) == (w, h)
    assert depth == 8 and ctype == 2


def test_encode_png_idat_decodes_to_pixels():
    w, h = 8, 4
    pixels = bytes(range(w * h * 3 % 256)) + bytes(w * h * 3)
    pixels = pixels[: w * h * 3]
    data = encode_png(w, h, pixels)
    chunks = dict(_decode_png_chunks(data))
    raw = zlib.decompress(chunks[b"IDAT"])
    # each scanline is 1 filter byte + w*3 pixel bytes
    assert len(raw) == h * (1 + w * 3)
    for y in range(h):
        assert raw[y * (1 + w * 3)] == 0  # filter type None


def test_encode_png_bad_buffer_size():
    with pytest.raises(ValueError):
        encode_png(4, 4, b"\x00\x00\x00")


def test_encode_png_zero_dims():
    with pytest.raises(ValueError):
        encode_png(0, 4, b"")


def test_canvas_set_get_pixel():
    cv = Canvas(10, 10)
    cv.set_pixel(3, 4, (255, 128, 64))
    assert cv.get_pixel(3, 4) == (255, 128, 64)


def test_canvas_fill():
    cv = Canvas(5, 5, background=(10, 20, 30))
    assert cv.get_pixel(0, 0) == (10, 20, 30)
    assert cv.get_pixel(4, 4) == (10, 20, 30)


def test_canvas_rect_and_lines():
    cv = Canvas(20, 20)
    cv.rect(2, 2, 10, 10, (255, 0, 0))
    assert cv.get_pixel(2, 2) == (255, 0, 0)
    assert cv.get_pixel(10, 10) == (255, 0, 0)


def test_canvas_fill_rect():
    cv = Canvas(20, 20)
    cv.fill_rect(5, 5, 8, 8, (0, 255, 0))
    assert cv.get_pixel(6, 6) == (0, 255, 0)


def test_canvas_draw_text_returns_cursor():
    cv = Canvas(200, 20)
    end = cv.draw_text(0, 0, "ABC", (255, 255, 255))
    assert end > 0


def test_canvas_out_of_bounds_ignored():
    cv = Canvas(4, 4)
    cv.set_pixel(100, 100, (1, 2, 3))  # should not raise
    cv.set_pixel(-1, -1, (1, 2, 3))


def test_canvas_save_valid_png(tmp_path):
    cv = Canvas(16, 16)
    p = str(tmp_path / "c.png")
    cv.save(p)
    with open(p, "rb") as fh:
        assert fh.read(8) == PNG_SIG


@pytest.mark.parametrize("t", [0.0, 0.25, 0.5, 0.75, 1.0, -1.0, 2.0])
def test_viridis_returns_rgb(t):
    r, g, b = viridis(t)
    assert all(0 <= c <= 255 for c in (r, g, b))


# --------------------------------------------------------------------------- #
# Annotated spectrogram
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("scenario", ["tone", "wifi", "drone-link", "gnss"])
def test_render_spectrogram_valid_png(tmp_path, scenario):
    cap, _ = generate(scenario)
    rep = analyze_capture(cap)
    p = str(tmp_path / f"{scenario}.png")
    render_spectrogram_png(rep.detection.spectrogram, rep.detection.emitters, p,
                           labels=rep.label_map(), center_freq=cap.center_freq)
    with open(p, "rb") as fh:
        data = fh.read()
    assert data[:8] == PNG_SIG
    _decode_png_chunks(data)


def test_render_spectrogram_none(tmp_path):
    p = str(tmp_path / "none.png")
    render_spectrogram_png(None, [], p)
    with open(p, "rb") as fh:
        assert fh.read(8) == PNG_SIG


def test_render_spectrogram_dimensions(tmp_path):
    cap, _ = generate("wifi")
    rep = analyze_capture(cap)
    p = str(tmp_path / "d.png")
    render_spectrogram_png(rep.detection.spectrogram, rep.detection.emitters, p,
                           width=320, height=240)
    with open(p, "rb") as fh:
        data = fh.read()
    chunks = dict(_decode_png_chunks(data))
    width, height = struct.unpack(">II", chunks[b"IHDR"][:8])
    assert (width, height) == (320, 240)


# --------------------------------------------------------------------------- #
# JSON
# --------------------------------------------------------------------------- #
def test_to_json_parses():
    cap, _ = generate("drone-link")
    rep = analyze_capture(cap)
    obj = json.loads(to_json(rep))
    assert obj["tool"] == "wavewatch"
    assert "emitters" in obj and "summary" in obj


def test_write_json(tmp_path):
    cap, _ = generate("wifi")
    rep = analyze_capture(cap)
    p = str(tmp_path / "r.json")
    write_json(rep, p)
    with open(p) as fh:
        obj = json.load(fh)
    assert obj["version"]


# --------------------------------------------------------------------------- #
# SARIF
# --------------------------------------------------------------------------- #
def test_sarif_structure():
    cap, _ = generate("drone-link")
    rep = analyze_capture(cap)
    s = to_sarif(rep)
    assert s["version"] == SARIF_VERSION
    assert "runs" in s and len(s["runs"]) == 1
    assert s["runs"][0]["tool"]["driver"]["name"] == "wavewatch"


def test_sarif_has_results():
    cap, _ = generate("drone-link")
    rep = analyze_capture(cap)
    s = to_sarif(rep)
    assert len(s["runs"][0]["results"]) >= 1
    for r in s["runs"][0]["results"]:
        assert "ruleId" in r and "message" in r and "level" in r


def test_sarif_interference_result():
    cap, _ = generate("sweep")
    rep = analyze_capture(cap)
    s = to_sarif(rep)
    rule_ids = [r["ruleId"] for r in s["runs"][0]["results"]]
    assert "interference.detected" in rule_ids


def test_write_sarif(tmp_path):
    cap, _ = generate("ble")
    rep = analyze_capture(cap)
    p = str(tmp_path / "r.sarif")
    write_sarif(rep, p)
    with open(p) as fh:
        obj = json.load(fh)
    assert obj["version"] == SARIF_VERSION


# --------------------------------------------------------------------------- #
# GeoJSON
# --------------------------------------------------------------------------- #
def test_geojson_with_position():
    cap, _ = generate("drone-link", position=(38.9, -77.0))
    rep = analyze_capture(cap)
    gj = to_geojson(rep, position=cap.position)
    assert gj["type"] == "FeatureCollection"
    assert len(gj["features"]) >= 1
    coords = gj["features"][0]["geometry"]["coordinates"]
    assert coords == [-77.0, 38.9]  # GeoJSON is [lon, lat]


def test_geojson_none_without_position():
    cap, _ = generate("drone-link")
    rep = analyze_capture(cap)
    assert to_geojson(rep) is None


def test_write_geojson_skips_without_position(tmp_path):
    cap, _ = generate("wifi")
    rep = analyze_capture(cap)
    result = write_geojson(rep, str(tmp_path / "g.geojson"))
    assert result is None


def test_write_geojson_with_position(tmp_path):
    cap, _ = generate("wifi", position=(40.0, -75.0))
    rep = analyze_capture(cap)
    p = write_geojson(rep, str(tmp_path / "g.geojson"), position=cap.position)
    assert p is not None
    with open(p) as fh:
        obj = json.load(fh)
    assert obj["type"] == "FeatureCollection"


def test_geojson_auto_position_from_capture():
    cap, _ = generate("ble", position=(10.0, 20.0))
    rep = analyze_capture(cap)
    gj = to_geojson(rep)  # should read position from capture summary
    assert gj is not None
    assert gj["features"][0]["geometry"]["coordinates"] == [20.0, 10.0]
