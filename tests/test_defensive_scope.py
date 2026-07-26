"""Guardrail tests: wavewatch must remain defensive/analysis-only.

These scan the shipped source for any transmit / jamming / weaponization
capability and assert the package exposes no such surface. They are part of the
test suite so a regression that adds an offensive capability fails CI.
"""

from __future__ import annotations

import ast
import os

import pytest

import wavewatch

PACKAGE_DIR = os.path.dirname(os.path.abspath(wavewatch.__file__))


def _python_files():
    for root, _dirs, files in os.walk(PACKAGE_DIR):
        for f in files:
            if f.endswith(".py"):
                yield os.path.join(root, f)


# Terms that would indicate an active transmit / jamming / weaponization path.
FORBIDDEN_CALL_NAMES = {
    "transmit", "start_tx", "send_iq", "jam", "start_jamming", "emit_rf",
    "activate_jammer", "transmit_iq", "tx_start", "weaponize", "fire",
}


def test_no_transmit_or_jam_function_defs():
    offenders = []
    for path in _python_files():
        with open(path, "r", encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=path)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = node.name.lower()
                if name in FORBIDDEN_CALL_NAMES:
                    offenders.append((path, node.name))
    assert offenders == [], f"offensive-capability functions found: {offenders}"


def test_no_offensive_terms_in_public_api():
    names = set(dir(wavewatch))
    for term in ["transmit", "jam", "weapon", "tx"]:
        assert not any(term in n.lower() for n in names), f"public API mentions {term!r}"


def test_live_adapter_is_receive_only():
    from wavewatch.io.live import LiveCaptureAdapter
    adapter = LiveCaptureAdapter(sample_rate=1e6)
    # no transmit method exists
    assert not hasattr(adapter, "transmit")
    assert not hasattr(adapter, "send")
    # base adapter cannot even receive (no bundled backend)
    assert adapter.available() is False
    with pytest.raises(NotImplementedError):
        adapter.read(10)


def test_interference_module_is_detection_only():
    from wavewatch.classify import interference
    # only detectors are exported; no generators of jamming waveforms
    for name in dir(interference):
        low = name.lower()
        if low.startswith("_"):
            continue
        assert not (low.startswith("start_") or "transmit" in low)


def test_generator_jammers_are_fixtures_not_transmitters():
    # the "jammer" generators return in-memory Capture fixtures only
    from wavewatch.io.generator import gen_sweep_jammer, gen_barrage_jammer
    cap, label = gen_sweep_jammer()
    assert label == "interference"
    assert hasattr(cap, "samples")  # just data, nothing is emitted


def test_no_payload_demodulation_symbols():
    # lawful-by-design: no payload decode/demod entry points
    names = set(dir(wavewatch))
    for term in ["demodulate", "decode_payload", "descramble", "decrypt"]:
        assert not any(term in n.lower() for n in names)
