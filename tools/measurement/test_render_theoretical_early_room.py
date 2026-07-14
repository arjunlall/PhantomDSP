#!/usr/bin/env python3

import json
import math
import unittest

import numpy as np

from analyze_baseline import read_pcm_wav, sha256
from render_synthetic_direct import PATH_ORDER, load_stereo_paths
from render_synthetic_late_room import pad_to
from render_theoretical_early_room import (
    ANALYSIS_DIRECTORY,
    DESIGN,
    DIRECT_FILES,
    OUTPUT_DIRECTORY,
    OUTPUT_FILES,
    ear_positions,
    mirror_point,
    one_pole_high_shelf_impulse,
    source_positions,
)


class TheoreticalEarlyRoomTests(unittest.TestCase):
    def test_mirror_geometry_and_left_right_symmetry(self):
        point = np.array([-0.5, 0.8, 1.2])
        mirrored = mirror_point(point, 0, -2.4)
        self.assertTrue(np.array_equal(mirrored, np.array([-4.3, 0.8, 1.2])))
        sources = source_positions()
        ears = ear_positions()
        self.assertTrue(np.array_equal(sources["left"] * [-1, 1, 1], sources["right"]))
        self.assertTrue(np.array_equal(ears["left"] * [-1, 1, 1], ears["right"]))

    def test_high_shelf_has_exact_dc_and_nyquist_endpoints(self):
        impulse = one_pole_high_shelf_impulse(48000, 2500.0, 0.45, 256)
        spectrum = np.fft.rfft(impulse, 65536)
        self.assertAlmostEqual(float(abs(spectrum[0])), 1.0, places=12)
        self.assertAlmostEqual(float(abs(spectrum[-1])), 0.45, places=12)

    def test_checked_in_outputs_match_summary_and_preserve_direct_onset(self):
        summary = json.loads(
            (ANALYSIS_DIRECTORY / "summary.json").read_text(encoding="utf-8")
        )
        rendered, sample_rate, _ = load_stereo_paths(
            {side: OUTPUT_DIRECTORY / filename for side, filename in OUTPUT_FILES.items()}
        )
        direct, direct_rate, _ = load_stereo_paths(DIRECT_FILES)
        self.assertEqual(sample_rate, direct_rate)

        for side, filename in OUTPUT_FILES.items():
            path = OUTPUT_DIRECTORY / filename
            loaded = read_pcm_wav(path)
            self.assertEqual(loaded["sample_rate"], DESIGN["sample_rate_hz"])
            self.assertEqual(loaded["sample_width_bits"], 24)
            self.assertEqual(loaded["channels"], 2)
            self.assertEqual(loaded["frame_count"], DESIGN["output_length_samples"])
            self.assertEqual(sha256(path), summary["rendered_files"][side]["sha256"])

        order_half = DESIGN["fractional_delay_order"] // 2
        direct_padded = {
            path: pad_to(values, DESIGN["output_length_samples"])
            for path, values in direct.items()
        }
        for path in PATH_ORDER:
            first_extra = min(
                reflection["extra_delay_samples"]
                for reflection in summary["reflections"][path]
            )
            first_possible_sample = (
                math.floor(summary["direct_peak_samples"][path] + first_extra)
                - order_half
            )
            self.assertTrue(
                np.array_equal(
                    rendered[path][:first_possible_sample],
                    direct_padded[path][:first_possible_sample],
                )
            )

    def test_theoretical_branch_is_symmetric_and_hits_energy_target(self):
        summary = json.loads(
            (ANALYSIS_DIRECTORY / "summary.json").read_text(encoding="utf-8")
        )
        hashes = summary["branch_hashes"]["theoretical_early"]
        self.assertEqual(hashes["LL"], hashes["RR"])
        self.assertEqual(hashes["LR"], hashes["RL"])
        self.assertNotEqual(hashes["LL"], hashes["LR"])
        self.assertAlmostEqual(
            summary["combined_theoretical_early_to_direct_energy_db"],
            DESIGN["target_combined_early_to_direct_energy_db"],
            places=6,
        )
        self.assertFalse(summary["measured_early_waveform_samples_copied"])

    def test_bass_and_headroom_remain_controlled(self):
        summary = json.loads(
            (ANALYSIS_DIRECTORY / "summary.json").read_text(encoding="utf-8")
        )
        bass = summary["response_delta_F_minus_E"]["bass_20_80_hz"]
        self.assertLess(bass["rms_delta_db"], 0.02)
        self.assertLess(summary["modeled_correlated_renderer_gain_db"], 4.0)


if __name__ == "__main__":
    unittest.main()
