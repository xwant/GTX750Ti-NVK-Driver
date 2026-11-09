#!/usr/bin/env python3
"""Synthetic validation of statistics and manifest checks; no GPU data."""
import math
import tempfile
import unittest
from pathlib import Path

from compare_ab import compare, load_pairs, paired_effect
from analyze_mangohud import analyze


class StatisticsTests(unittest.TestCase):
    def test_known_constant_improvement(self):
        result = paired_effect([math.log(1.1)] * 8, 1000, 750)
        self.assertAlmostEqual(result["effect_percent"], 10)
        for endpoint in result["ci95_percent"]:
            self.assertAlmostEqual(endpoint, 10)

    def test_identical_and_symmetric_noisy_pairs(self):
        self.assertEqual(paired_effect([0.0] * 8, 1000, 750)["ci95_percent"],
                         [0.0, 0.0])
        values = [-0.04, 0.04] * 4
        result = paired_effect(values, 1000, 750)
        self.assertAlmostEqual(result["effect_percent"], 0)
        self.assertLess(result["ci95_percent"][0], 0)
        self.assertGreater(result["ci95_percent"][1], 0)
        self.assertEqual(result, paired_effect(values, 1000, 750))

    def test_p99_lower_is_better(self):
        pairs = {str(i): {
            "A": {"average_fps": 100, "one_percent_low_fps": 50,
                  "p99_frametime_ms": 20},
            "B": {"average_fps": 110, "one_percent_low_fps": 55,
                  "p99_frametime_ms": 20 / 1.1},
        } for i in range(8)}
        for metric in compare(pairs, 1000)["metrics"].values():
            self.assertAlmostEqual(metric["effect_percent"], 10)

    def test_geometric_pair_ratios_not_ratio_of_pooled_runs(self):
        # +/- log(2) cancel even if runs have very different raw FPS.
        result = paired_effect([math.log(2), -math.log(2)], 1000, 750)
        self.assertAlmostEqual(result["effect_percent"], 0)


class InputTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.manifest = self.root / "pairs.csv"
        self.rows = ["pair,variant,file"]
        for i in range(8):
            for variant in ("A", "B"):
                name = f"{i}_{variant}.csv"
                self.write_log(name, [10.0] * 12000)
                self.rows.append(f"{i},{variant},{name}")
        self.save_manifest()

    def save_manifest(self):
        self.manifest.write_text("\n".join(self.rows) + "\n")

    def write_log(self, name, times):
        (self.root / name).write_text("fps,frametime\n" +
                                     "".join(f"1,{t}\n" for t in times))

    def test_real_parser_and_pair_loading(self):
        pairs = load_pairs(self.manifest)
        self.assertEqual(len(pairs), 8)
        self.assertEqual(pairs["0"]["A"]["average_fps"], 100)
        # Fake fps=1 in CSV is deliberately ignored; frametime is authoritative.
        self.assertEqual(pairs["0"]["A"]["duration_s"], 120)

    def test_one_percent_low_definition(self):
        self.write_log("tail.csv", [10] * 990 + [100] * 10)
        result = analyze(self.root / "tail.csv")
        self.assertAlmostEqual(result["average_fps"], 1000 / 10.9)
        self.assertEqual(result["one_percent_low_fps"], 10)
        self.assertEqual(result["p99_frametime_ms"], 10)

    def test_duplicate_and_missing_variant_rejected(self):
        self.rows.append(self.rows[1])
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            load_pairs(self.manifest)
        self.rows = self.rows[:-2]
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            load_pairs(self.manifest)

    def test_reused_file_rejected(self):
        self.rows[2] = "0,B,0_A.csv"
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "reused"):
            load_pairs(self.manifest)

    def test_wrong_duration_rejected(self):
        self.write_log("0_A.csv", [10] * 100)
        with self.assertRaisesRegex(ValueError, "duration"):
            load_pairs(self.manifest)

    def test_nonfinite_frame_rejected(self):
        self.write_log("0_A.csv", [10] * 100 + [float("nan")])
        with self.assertRaisesRegex(ValueError, "invalid frametime"):
            load_pairs(self.manifest)

    def test_too_few_pairs_rejected(self):
        self.rows = self.rows[:5]
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "Need >= 8"):
            load_pairs(self.manifest)

    def test_malformed_row_rejected(self):
        self.rows[1] += ",unexpected"
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "Malformed"):
            load_pairs(self.manifest)


if __name__ == "__main__":
    unittest.main()
