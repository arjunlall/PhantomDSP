import json
import unittest

import numpy as np

from analyze_baseline import read_pcm_wav, sha256
from render_directional_diffuse_room import (
    ANALYSIS_DIRECTORY,
    DESIGN,
    J_FILES,
    OUTPUT_DIRECTORY,
    OUTPUT_FILES,
)
from render_synthetic_direct import PATH_ORDER, load_stereo_paths


class DirectionalDiffuseRoomTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = json.loads(
            (ANALYSIS_DIRECTORY / "summary.json").read_text(encoding="utf-8")
        )

    def test_design_changes_only_the_microcluster_localization_band(self):
        self.assertEqual(DESIGN["base_candidate"], "J midrange-normalized mastering room")
        self.assertEqual(DESIGN["changed_branch"], "G/H deterministic microclusters only")
        self.assertAlmostEqual(
            sum(DESIGN["direction_energy_weights"].values()), 1.0
        )
        self.assertEqual(DESIGN["correction_support_hz"], [3000.0, 14000.0])
        self.assertEqual(
            DESIGN["correction_full_strength_hz"], [4000.0, 12000.0]
        )
        self.assertEqual(DESIGN["bulk_delay_samples"], 0)
        self.assertEqual(
            len(self.summary["directional_model"]["matched_subjects"]), 5
        )

    def test_outputs_match_summary_and_keep_j_as_verified_parent(self):
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
                sha256(J_FILES[side]),
                self.summary["candidate_j_rendered_hashes"][side],
            )

    def test_direct_and_low_frequency_contracts_are_preserved(self):
        candidate, sample_rate, _ = load_stereo_paths(
            {
                side: OUTPUT_DIRECTORY / filename
                for side, filename in OUTPUT_FILES.items()
            }
        )
        parent, parent_rate, _ = load_stereo_paths(J_FILES)
        self.assertEqual(sample_rate, parent_rate)
        earliest_possible_microcluster = min(
            self.summary["direct_peak_samples"].values()
        ) + round(0.004 * sample_rate)
        for path in PATH_ORDER:
            self.assertTrue(
                np.array_equal(
                    candidate[path][:earliest_possible_microcluster],
                    parent[path][:earliest_possible_microcluster],
                )
            )
        delta = self.summary["response_delta_K_minus_J"]
        self.assertLess(delta["bass_20_80_hz"]["rms_delta_db"], 0.001)
        self.assertLess(delta["protected_200_1800_hz"]["rms_delta_db"], 0.02)

    def test_directional_cues_change_without_tonal_revoicing(self):
        response = self.summary["filter_response_db"]
        self.assertGreater(
            max(
                abs(response[path][str(frequency)])
                for path in PATH_ORDER
                for frequency in (5000, 7000, 8000, 10000, 12000)
            ),
            2.0,
        )
        for path in PATH_ORDER:
            self.assertEqual(
                self.summary["filter_impulse_first_nonzero_sample"][path], 0
            )
        for metrics in self.summary[
            "microcluster_binaural_energy_preservation"
        ].values():
            self.assertLess(metrics["rms_delta_db"], 0.2)
        for metrics in self.summary["response_delta_K_minus_J"][
            "directional_4000_12000_hz"
        ].values():
            self.assertLess(metrics["rms_delta_db"], 0.2)
        before = self.summary["microcluster_center_metrics_before"]
        after = self.summary["microcluster_center_metrics_after"]
        self.assertLess(
            abs(after["maximum_absolute_iacc"] - before["maximum_absolute_iacc"]),
            0.03,
        )
        self.assertLess(abs(after["left_to_right_energy_db"]), 0.2)
        self.assertLess(self.summary["modeled_correlated_renderer_gain_db"], 4.0)

    def test_full_spectrum_plots_are_recorded(self):
        for plot in (
            "k-left-right-full-spectrum.svg",
            "j-k-room-coloration-full-spectrum.svg",
            "k-minus-j-fused-delta-full-spectrum.svg",
            "k-left-components-full-spectrum.svg",
            "k-right-components-full-spectrum.svg",
        ):
            self.assertIn(plot, self.summary["plots"])
            self.assertTrue((ANALYSIS_DIRECTORY / plot).is_file())


if __name__ == "__main__":
    unittest.main()
