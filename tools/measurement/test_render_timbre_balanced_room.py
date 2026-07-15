import json
import unittest

import numpy as np

from analyze_baseline import read_pcm_wav, sha256
from render_synthetic_direct import PATH_ORDER, load_stereo_paths
from render_timbre_balanced_room import (
    ANALYSIS_DIRECTORY,
    DESIGN,
    K_FILES,
    OUTPUT_DIRECTORY,
    OUTPUT_FILES,
)


class TimbreBalancedRoomTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = json.loads(
            (ANALYSIS_DIRECTORY / "summary.json").read_text(encoding="utf-8")
        )

    def test_design_changes_only_the_microcluster_envelope(self):
        self.assertEqual(DESIGN["base_candidate"], "K directional diffuse mastering room")
        self.assertEqual(DESIGN["changed_branch"], "directional deterministic microclusters only")
        self.assertTrue(DESIGN["attenuation_only"])
        self.assertEqual(DESIGN["bulk_delay_samples"], 0)

    def test_outputs_match_summary_and_keep_k_as_parent(self):
        for side, filename in OUTPUT_FILES.items():
            path = OUTPUT_DIRECTORY / filename
            loaded = read_pcm_wav(path)
            self.assertEqual(loaded["sample_rate"], DESIGN["sample_rate_hz"])
            self.assertEqual(loaded["sample_width_bits"], 24)
            self.assertEqual(loaded["channels"], 2)
            self.assertEqual(loaded["frame_count"], DESIGN["output_length_samples"])
            self.assertEqual(sha256(path), self.summary["rendered_files"][side]["sha256"])
            self.assertEqual(
                sha256(K_FILES[side]),
                self.summary["candidate_k_rendered_hashes"][side],
            )

    def test_direct_and_protected_bands_are_unchanged(self):
        candidate, sample_rate, _ = load_stereo_paths(
            {side: OUTPUT_DIRECTORY / filename for side, filename in OUTPUT_FILES.items()}
        )
        parent, parent_rate, _ = load_stereo_paths(K_FILES)
        self.assertEqual(sample_rate, parent_rate)
        earliest_microcluster = min(self.summary["direct_peak_samples"].values()) + round(
            0.004 * sample_rate
        )
        for path in PATH_ORDER:
            self.assertTrue(
                np.array_equal(
                    candidate[path][:earliest_microcluster],
                    parent[path][:earliest_microcluster],
                )
            )
        for speaker in ("left", "right"):
            delta = self.summary["response_delta_balanced_minus_k"][speaker]
            self.assertLess(delta["20-80 Hz"]["rms_db"], 0.001)
            self.assertLess(abs(delta["200 Hz-1.8 kHz"]["mean_db"]), 0.01)
            self.assertLess(delta["200 Hz-1.8 kHz"]["rms_db"], 0.15)
            self.assertLess(
                max(
                    abs(delta["200 Hz-1.8 kHz"]["minimum_db"]),
                    abs(delta["200 Hz-1.8 kHz"]["maximum_db"]),
                ),
                0.5,
            )
            self.assertLess(delta["3-5 kHz"]["rms_db"], 0.2)

    def test_timbre_excess_is_removed_without_bulk_delay(self):
        for speaker in ("left", "right"):
            self.assertLess(
                abs(
                    self.summary["microcluster_residual_vs_theory_6_10_khz"][speaker][
                        "mean_db"
                    ]
                ),
                1.0,
            )
            self.assertLess(
                self.summary["response_delta_balanced_minus_k"][speaker]["6-10 kHz"][
                    "mean_db"
                ],
                -1.0,
            )
            self.assertEqual(
                self.summary["filter_impulse_first_nonzero_sample"][speaker], 0
            )
            self.assertLess(
                self.summary["microcluster_interaural_ratio_delta_6_10_khz"][speaker][
                    "rms_db"
                ],
                0.001,
            )
        self.assertLess(self.summary["modeled_correlated_renderer_gain_db"], 4.0)

    def test_plots_are_recorded(self):
        for plot in self.summary["plots"]:
            self.assertTrue((ANALYSIS_DIRECTORY / plot).is_file())


if __name__ == "__main__":
    unittest.main()
