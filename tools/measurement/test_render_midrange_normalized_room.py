#!/usr/bin/env python3

import json
import unittest

from analyze_baseline import read_pcm_wav, sha256
from render_tonally_normalized_room import (
    ANALYSIS_DIRECTORY as I_ANALYSIS_DIRECTORY,
    H_FILES,
    I_FILES,
    PROFILES,
)


PROFILE = PROFILES["J"]
DESIGN = PROFILE["design"]
OUTPUT_DIRECTORY = PROFILE["ir_output"]
ANALYSIS_DIRECTORY = PROFILE["analysis_output"]
OUTPUT_FILES = PROFILE["output_files"]


class MidrangeNormalizedRoomTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = json.loads(
            (ANALYSIS_DIRECTORY / "summary.json").read_text(encoding="utf-8")
        )
        cls.i_summary = json.loads(
            (I_ANALYSIS_DIRECTORY / "summary.json").read_text(encoding="utf-8")
        )

    def test_design_extends_i_without_recentering_it(self):
        correction = DESIGN["correction"]
        self.assertEqual(correction["flat_band_hz"], [1000.0, 1500.0])
        self.assertEqual(correction["target_band_hz"], [200.0, 1000.0])
        self.assertEqual(correction["evaluation_band_hz"], [200.0, 1500.0])
        self.assertEqual(correction["transition_band_hz"], [900.0, 1800.0])
        self.assertEqual(
            correction["transition_mode"], "frequency-shaped raised cosine"
        )
        self.assertEqual(correction["phase"], "minimum phase")
        self.assertEqual(correction["bulk_delay_samples"], 0)
        for speaker in ("left", "right"):
            self.assertLess(
                abs(
                    self.summary["binaural_response_200_1500_hz"][speaker][
                        "target_db"
                    ]
                    - self.i_summary["binaural_response_200_1000_hz"][speaker][
                        "target_db"
                    ]
                ),
                0.005,
            )

    def test_checked_in_outputs_match_summary_and_verified_parents(self):
        for side, filename in OUTPUT_FILES.items():
            path = OUTPUT_DIRECTORY / filename
            loaded = read_pcm_wav(path)
            self.assertEqual(loaded["sample_rate"], DESIGN["sample_rate_hz"])
            self.assertEqual(loaded["sample_width_bits"], 24)
            self.assertEqual(loaded["channels"], 2)
            self.assertEqual(
                loaded["frame_count"], DESIGN["output_length_samples"]
            )
            self.assertEqual(
                sha256(path), self.summary["rendered_files"][side]["sha256"]
            )
            self.assertEqual(
                sha256(I_FILES[side]),
                self.summary["candidate_i_rendered_hashes"][side],
            )
            self.assertEqual(
                sha256(H_FILES[side]),
                self.summary["candidate_h_rendered_hashes"][side],
            )

    def test_broad_midrange_coloration_is_materially_flatter(self):
        for speaker in ("left", "right"):
            response = self.summary["binaural_response_200_1500_hz"][speaker]
            self.assertLess(
                response["J"]["rms_deviation_from_mean_db"],
                response["H"]["rms_deviation_from_mean_db"] * 0.35,
            )
            self.assertLess(
                response["J"]["peak_to_peak_db"],
                response["H"]["peak_to_peak_db"] * 0.35,
            )

    def test_i_balance_spatial_ratios_and_protected_bands_are_preserved(self):
        comparison = self.summary["response_delta_J_minus_I"]
        self.assertLess(
            comparison["established_200_1000_hz"]["rms_delta_db"], 0.1
        )
        self.assertGreater(
            comparison["correction_extension_1000_1500_hz"]["rms_delta_db"],
            1.0,
        )
        self.assertLess(
            comparison["protected_1800_8000_hz"]["rms_delta_db"], 0.002
        )

        for metrics in self.summary[
            "interaural_preservation_200_1500_hz"
        ].values():
            self.assertLess(metrics["rms_ild_delta_db"], 0.01)
            self.assertLess(metrics["maximum_absolute_ild_delta_db"], 0.1)
            self.assertLess(metrics["maximum_absolute_phase_delta_degrees"], 1.0)
        for first in self.summary[
            "filter_impulse_first_nonzero_sample"
        ].values():
            self.assertEqual(first, 0)
        for tail_db in self.summary[
            "truncated_filter_tail_energy_db_relative_to_complete_convolution"
        ].values():
            self.assertLess(tail_db, -90.0)
        self.assertLess(self.summary["modeled_correlated_renderer_gain_db"], 4.0)


if __name__ == "__main__":
    unittest.main()
