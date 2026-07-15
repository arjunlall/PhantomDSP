import json
import unittest

import numpy as np

from analyze_directional_diffuse_timbre import (
    ANALYSIS_DIRECTORY,
    DESIGN,
    erb_centers,
    erb_width_hz,
    roex_weights,
)


class DirectionalDiffuseTimbreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = json.loads(
            (ANALYSIS_DIRECTORY / "summary.json").read_text(encoding="utf-8")
        )

    def test_erb_filterbank_is_monotonic_and_normalized(self):
        centers = erb_centers(1500.0, 12000.0, 0.5)
        self.assertGreater(len(centers), 20)
        self.assertTrue(np.all(np.diff(centers) > 0.0))
        self.assertGreater(erb_width_hz(8000.0), erb_width_hz(2000.0))
        frequencies = np.linspace(0.0, 24000.0, 32769)
        weights = roex_weights(frequencies, 7000.0)
        self.assertAlmostEqual(float(np.sum(weights)), 1.0, places=12)
        self.assertEqual(int(np.argmax(weights)), int(np.argmin(np.abs(frequencies - 7000.0))))

    def test_target_is_independent_of_old_room_upper_frequency_targets(self):
        design = self.summary["design"]
        self.assertFalse(design["raw_old_room_waveform_used"])
        self.assertFalse(design["old_room_octave_targets_used_in_reference"])
        self.assertAlmostEqual(sum(design["surface_energy_weights"].values()), 1.0)
        self.assertEqual(design["anchor_band_hz"], [800.0, 1250.0])

    def test_component_reconstruction_is_stable(self):
        for value in self.summary["component_reconstruction_relative_rms"].values():
            self.assertLess(value, 0.01)

    def test_decision_and_plots_are_recorded(self):
        self.assertIn(
            self.summary["decision"]["status"],
            (
                "branch-only correction warranted",
                "no branch-only correction warranted",
            ),
        )
        self.assertEqual(DESIGN["decision_band_hz"], [6000.0, 10000.0])
        for plot in self.summary["plots"]:
            self.assertTrue((ANALYSIS_DIRECTORY / plot).is_file())


if __name__ == "__main__":
    unittest.main()
