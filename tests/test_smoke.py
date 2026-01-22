"""Smoke tests for rfsurvey (standard library only, no network)."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rfsurvey import TOOL_NAME, TOOL_VERSION, analyze, load_samples
from rfsurvey.core import SurveyError, detect_anomalies, summarize_bands
from rfsurvey.cli import main


DEMO = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "demos",
    "01-basic",
    "sweep.csv",
)

CSV = (
    "timestamp,freq_hz,power_dbm\n"
    "t0,2437000000,-40\n"
    "t0,2462000000,-12\n"
    "t0,2401000000,-98\n"
    "t1,2437000000,-41\n"
    "t1,2462000000,-90\n"
    "t1,2401000000,-99\n"
    "t2,2437000000,-39\n"
    "t2,2462000000,-91\n"
    "t2,2401000000,-97\n"
)


class TestCore(unittest.TestCase):
    def test_metadata(self):
        self.assertEqual(TOOL_NAME, "rfsurvey")
        self.assertTrue(TOOL_VERSION.count(".") >= 1)

    def test_load_aliases_and_validation(self):
        s = load_samples("frequency,power\n2400000000,-50\n")
        self.assertEqual(len(s), 1)
        self.assertEqual(s[0].freq_hz, 2400000000)
        self.assertEqual(s[0].power_dbm, -50)

    def test_load_rejects_missing_columns(self):
        with self.assertRaises(SurveyError):
            load_samples("foo,bar\n1,2\n")

    def test_load_rejects_empty(self):
        with self.assertRaises(SurveyError):
            load_samples("")

    def test_load_skips_bad_rows_but_keeps_good(self):
        s = load_samples("freq_hz,power_dbm\nabc,-50\n2400000000,-60\n,,\n")
        self.assertEqual(len(s), 1)

    def test_load_all_bad_raises(self):
        with self.assertRaises(SurveyError):
            load_samples("freq_hz,power_dbm\nabc,xyz\n-5,-60\n")

    def test_band_summary(self):
        samples = load_samples(CSV)
        bands = summarize_bands(samples, squelch_dbm=-80.0)
        ism = [b for b in bands if b.name == "ISM-2.4/WiFi-BT"]
        self.assertTrue(ism)
        self.assertGreater(ism[0].bins, 0)
        self.assertGreaterEqual(ism[0].occupancy, 0.0)
        self.assertLessEqual(ism[0].occupancy, 1.0)

    def test_anomalies_detects_spike_and_persistent(self):
        samples = load_samples(CSV)
        anomalies = detect_anomalies(samples, z_thresh=4.0, persist_min_sweeps=3)
        kinds = {a.kind for a in anomalies}
        self.assertIn("spike", kinds)
        self.assertIn("persistent", kinds)

    def test_analyze_end_to_end(self):
        report = analyze(CSV)
        self.assertEqual(report.samples, 9)
        self.assertEqual(report.sweeps, 3)
        self.assertTrue(report.bands)
        self.assertLess(report.noise_floor_dbm, report.squelch_dbm)


class TestCLI(unittest.TestCase):
    def test_cli_table(self):
        rc = main(["analyze", DEMO])
        self.assertEqual(rc, 0)

    def test_cli_json(self):
        rc = main(["--format", "json", "analyze", DEMO])
        self.assertEqual(rc, 0)

    def test_cli_fail_on_anomaly(self):
        rc = main(["analyze", DEMO, "--fail-on-anomaly"])
        self.assertEqual(rc, 1)

    def test_cli_bad_path(self):
        rc = main(["analyze", os.path.join(os.path.dirname(DEMO), "nope.csv")])
        self.assertEqual(rc, 2)

    def test_cli_bad_data(self):
        import tempfile

        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as fh:
            fh.write("foo,bar\n1,2\n")
            path = fh.name
        try:
            rc = main(["analyze", path])
            self.assertEqual(rc, 2)
        finally:
            os.unlink(path)

    def test_json_is_parseable(self):
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            main(["--format", "json", "analyze", DEMO])
        data = json.loads(buf.getvalue())
        self.assertIn("bands", data)
        self.assertIn("anomalies", data)


if __name__ == "__main__":
    unittest.main()
