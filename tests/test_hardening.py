"""Hardening tests: input validation, edge cases, and error paths."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rfsurvey.core import SurveyError, analyze, load_samples
from rfsurvey.cli import main

TOOL_NAME = "rfsurvey"


# ---------------------------------------------------------------------------
# core.py — analyze() parameter validation
# ---------------------------------------------------------------------------

class TestAnalyzeValidation(unittest.TestCase):
    MINIMAL_CSV = "freq_hz,power_dbm\n2400000000,-60\n2410000000,-80\n"

    def test_nan_squelch_offset_raises(self):
        with self.assertRaises(SurveyError):
            analyze(self.MINIMAL_CSV, squelch_offset_db=float("nan"))

    def test_inf_squelch_offset_raises(self):
        with self.assertRaises(SurveyError):
            analyze(self.MINIMAL_CSV, squelch_offset_db=float("inf"))

    def test_zero_z_thresh_raises(self):
        with self.assertRaises(SurveyError):
            analyze(self.MINIMAL_CSV, z_thresh=0.0)

    def test_negative_z_thresh_raises(self):
        with self.assertRaises(SurveyError):
            analyze(self.MINIMAL_CSV, z_thresh=-1.0)

    def test_zero_persist_min_sweeps_raises(self):
        with self.assertRaises(SurveyError):
            analyze(self.MINIMAL_CSV, persist_min_sweeps=0)

    def test_negative_persist_min_sweeps_raises(self):
        with self.assertRaises(SurveyError):
            analyze(self.MINIMAL_CSV, persist_min_sweeps=-5)

    def test_valid_params_succeed(self):
        report = analyze(self.MINIMAL_CSV, squelch_offset_db=5.0, z_thresh=3.0,
                         persist_min_sweeps=1)
        self.assertGreater(report.samples, 0)


# ---------------------------------------------------------------------------
# core.py — load_samples() edge cases
# ---------------------------------------------------------------------------

class TestLoadSamplesEdgeCases(unittest.TestCase):
    def test_whitespace_only_input(self):
        with self.assertRaises(SurveyError):
            load_samples("   \n  \n")

    def test_header_only_no_data_rows(self):
        with self.assertRaises(SurveyError):
            load_samples("freq_hz,power_dbm\n")

    def test_nonfinite_freq_skipped(self):
        # inf freq should be filtered; only the valid row should survive
        csv = "freq_hz,power_dbm\ninf,-50\n2400000000,-60\n"
        samples = load_samples(csv)
        self.assertEqual(len(samples), 1)
        self.assertEqual(samples[0].freq_hz, 2400000000.0)

    def test_negative_freq_skipped(self):
        csv = "freq_hz,power_dbm\n-100,-50\n2400000000,-60\n"
        samples = load_samples(csv)
        self.assertEqual(len(samples), 1)

    def test_zero_freq_skipped(self):
        csv = "freq_hz,power_dbm\n0,-50\n2400000000,-60\n"
        samples = load_samples(csv)
        self.assertEqual(len(samples), 1)

    def test_nan_power_row_skipped(self):
        csv = "freq_hz,power_dbm\n2400000000,nan\n2410000000,-60\n"
        samples = load_samples(csv)
        self.assertEqual(len(samples), 1)
        self.assertEqual(samples[0].freq_hz, 2410000000.0)


# ---------------------------------------------------------------------------
# CLI — argument range validation returns exit code 2
# ---------------------------------------------------------------------------

class TestCLIArgValidation(unittest.TestCase):
    # We need a real (valid) CSV file on disk to reach the arg-validation path
    # before file I/O.
    def setUp(self):
        self._fh = tempfile.NamedTemporaryFile(
            "w", suffix=".csv", delete=False
        )
        self._fh.write("freq_hz,power_dbm\n2400000000,-60\n")
        self._fh.close()
        self.csv_path = self._fh.name

    def tearDown(self):
        os.unlink(self.csv_path)

    def test_zero_z_thresh_cli(self):
        rc = main(["analyze", self.csv_path, "--z-thresh", "0"])
        self.assertEqual(rc, 2)

    def test_negative_z_thresh_cli(self):
        rc = main(["analyze", self.csv_path, "--z-thresh", "-1"])
        self.assertEqual(rc, 2)

    def test_zero_persist_sweeps_cli(self):
        rc = main(["analyze", self.csv_path, "--persist-sweeps", "0"])
        self.assertEqual(rc, 2)

    def test_negative_persist_sweeps_cli(self):
        rc = main(["analyze", self.csv_path, "--persist-sweeps", "-3"])
        self.assertEqual(rc, 2)

    def test_valid_args_succeed(self):
        rc = main([
            "analyze", self.csv_path, "--z-thresh", "4", "--persist-sweeps", "1"
        ])
        self.assertEqual(rc, 0)


# ---------------------------------------------------------------------------
# mcp_server.py — module compiles and serve() is importable
# ---------------------------------------------------------------------------

class TestMCPServerImport(unittest.TestCase):
    def test_mcp_server_importable(self):
        """mcp_server must import without error (mcp package not required)."""
        import importlib
        mod = importlib.import_module("rfsurvey.mcp_server")
        self.assertTrue(callable(mod.serve))

    def test_mcp_server_missing_extra_returns_1(self):
        """serve() returns 1 cleanly when 'mcp' package is absent."""
        import rfsurvey.mcp_server as ms
        import unittest.mock as mock
        # Simulate mcp package not installed by making the import raise ImportError
        with mock.patch.dict("sys.modules", {"mcp": None,
                                             "mcp.server": None,
                                             "mcp.server.fastmcp": None}):
            rc = ms.serve()
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
