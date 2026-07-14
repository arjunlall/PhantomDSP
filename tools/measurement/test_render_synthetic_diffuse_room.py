#!/usr/bin/env python3

import json
import unittest

import numpy as np

from analyze_baseline import read_pcm_wav, sha256
from analyze_synthetic_late_field import D_FILES
from render_synthetic_diffuse_room import (
    ANALYSIS_DIRECTORY,
    DESIGN,
    EARLY_FILES,
    OUTPUT_DIRECTORY,
    OUTPUT_FILES,
    TARGET_SUMMARY,
    paired_band_component,
)
from render_synthetic_direct import PATH_ORDER, load_stereo_paths
from render_synthetic_late_room import pad_to


class SyntheticDiffuseRoomTests(unittest.TestCase):
    def test_paired_component_is_deterministic_and_energy_normalized(self):
        arguments = (4096, 48000, 1000.0, 0.56, 0.1, 17)
        first_a, second_a = paired_band_component(*arguments)
        first_b, second_b = paired_band_component(*arguments)
        self.assertTrue(np.array_equal(first_a, first_b))
        self.assertTrue(np.array_equal(second_a, second_b))
        self.assertAlmostEqual(float(np.sum(np.square(first_a))), 1.0, places=10)
        self.assertAlmostEqual(float(np.sum(np.square(second_a))), 1.0, places=10)

    def test_checked_in_outputs_match_summary_and_preserve_candidate_c(self):
        summary = json.loads(
            (ANALYSIS_DIRECTORY / "summary.json").read_text(encoding="utf-8")
        )
        target = json.loads(TARGET_SUMMARY.read_text(encoding="utf-8"))[
            "candidate_e_target"
        ]
        rendered, sample_rate, _ = load_stereo_paths(
            {side: OUTPUT_DIRECTORY / filename for side, filename in OUTPUT_FILES.items()}
        )
        early, early_rate, _ = load_stereo_paths(EARLY_FILES)
        measured_d, measured_rate, _ = load_stereo_paths(D_FILES)
        self.assertEqual(sample_rate, early_rate)
        self.assertEqual(sample_rate, measured_rate)
        for side, filename in OUTPUT_FILES.items():
            path = OUTPUT_DIRECTORY / filename
            loaded = read_pcm_wav(path)
            self.assertEqual(loaded["sample_rate"], DESIGN["sample_rate_hz"])
            self.assertEqual(loaded["sample_width_bits"], 24)
            self.assertEqual(loaded["channels"], 2)
            self.assertEqual(loaded["frame_count"], DESIGN["output_length_samples"])
            self.assertEqual(sha256(path), summary["rendered_files"][side]["sha256"])

        for path in PATH_ORDER:
            control = pad_to(early[path], DESIGN["output_length_samples"])
            onset = summary["direct_peak_samples"][path] + round(25e-3 * sample_rate)
            first_difference = summary["metrics"]["first_difference_from_c_sample"][path]
            self.assertTrue(np.array_equal(rendered[path][:onset], control[:onset]))
            self.assertGreaterEqual(first_difference, onset)
            self.assertLessEqual(first_difference, onset + 4)
            self.assertFalse(np.array_equal(rendered[path], measured_d[path]))

        metrics = summary["metrics"]
        self.assertAlmostEqual(
            metrics["combined_retained_c_to_late_energy_ratio_db"],
            target["combined_retained_c_to_late_energy_ratio_db"],
            places=2,
        )
        self.assertLess(metrics["bass_preservation_20_80_hz"]["rms_delta_db"], 0.001)
        self.assertLess(metrics["modeled_correlated_renderer_gain_db"], 4.0)
        for key, band in metrics["bands"].items():
            self.assertLessEqual(
                abs(
                    band["energy_shape_db_relative_to_1khz"]
                    - target["late_energy_shape_db_relative_to_1khz"][key]
                ),
                1.1,
            )
            self.assertLessEqual(
                abs(
                    band["median_t30_seconds"]
                    - target["rt60_seconds_by_octave"][key]
                ),
                0.06,
            )
            self.assertLessEqual(
                abs(
                    band["mean_maximum_absolute_iacc"]
                    - target["maximum_absolute_iacc_by_octave"][key]
                ),
                0.06,
            )


if __name__ == "__main__":
    unittest.main()
