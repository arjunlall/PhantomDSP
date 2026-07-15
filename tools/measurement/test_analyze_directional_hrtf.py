import unittest

import numpy as np

from analyze_directional_hrtf import (
    MODEL_FREQUENCIES_HZ,
    angular_distances,
    direction_centered_profiles,
    match_scale,
    room_to_sofa,
    serialized_directional_model,
    warp_curve,
)


class DirectionalHrtfAnalysisTests(unittest.TestCase):
    def test_room_to_sofa_reverses_azimuth_sign(self):
        self.assertEqual(room_to_sofa(-30.0, 12.0), (30.0, 12.0))
        self.assertEqual(room_to_sofa(30.0, -12.0), (330.0, -12.0))

    def test_angular_distance_handles_azimuth_wrap(self):
        positions = np.array([[359.0, 0.0], [180.0, 0.0]])
        distances = angular_distances(positions, (1.0, 0.0))
        self.assertAlmostEqual(distances[0], 2.0, places=6)
        self.assertGreater(distances[1], 170.0)

    def test_direction_centering_cancels_each_ear_average(self):
        curves = {
            "LL": np.array([4.0, 6.0]),
            "RL": np.array([0.0, 2.0]),
            "LR": np.array([1.0, 3.0]),
            "RR": np.array([5.0, 7.0]),
        }
        centered = direction_centered_profiles(curves)
        np.testing.assert_allclose(centered["LL"] + centered["RL"], 0.0)
        np.testing.assert_allclose(centered["LR"] + centered["RR"], 0.0)

    def test_match_scale_recovers_frequency_warp(self):
        frequencies = np.linspace(1000.0, 16000.0, 1501)
        source = -8.0 * np.exp(-0.5 * ((frequencies - 9000.0) / 700.0) ** 2)
        candidate = {
            "LL": source,
            "RL": -source,
            "LR": -0.8 * source,
            "RR": 0.8 * source,
        }
        expected_scale = 0.9
        personal = {
            path: warp_curve(frequencies, values, expected_scale)
            for path, values in candidate.items()
        }
        result = match_scale(
            frequencies,
            personal,
            candidate,
            scales=np.linspace(0.85, 0.95, 21),
        )
        self.assertAlmostEqual(result["scale"], expected_scale, places=6)
        self.assertLess(result["score_db"], 1e-9)

    def test_serialized_model_has_compact_rendering_grid(self):
        frequencies = np.linspace(1000.0, 20000.0, 501)
        curves = {
            speaker: {
                surface: {
                    ear: np.full_like(frequencies, value, dtype=np.float64)
                    for ear, value in (("left", -1.0), ("right", 1.0))
                }
                for surface in ("left_wall", "right_wall", "floor", "ceiling")
            }
            for speaker in ("left", "right")
        }
        subjects = [
            {
                "listener": f"subject-{index}",
                "path": type("PathLike", (), {"name": f"subject-{index}.sofa"})(),
                "sha256": str(index),
                "match": {"scale": 1.0, "score_db": float(index)},
            }
            for index in range(6)
        ]
        model = serialized_directional_model(frequencies, curves, subjects, {})
        self.assertEqual(len(model["matched_subjects"]), 5)
        self.assertEqual(len(model["frequencies_hz"]), len(MODEL_FREQUENCIES_HZ))
        self.assertEqual(
            model["directional_delta_db"]["left"]["ceiling"]["left"],
            [-1.0] * len(MODEL_FREQUENCIES_HZ),
        )


if __name__ == "__main__":
    unittest.main()
