#!/usr/bin/env python3

import math
import unittest

import numpy as np

from render_synthetic_direct import (
    DESIGN,
    direct_window,
    lagrange_fractional_delay,
    theoretical_itd_samples,
)


class SyntheticDirectRendererTests(unittest.TestCase):
    def test_theoretical_itd_matches_locked_geometry(self):
        self.assertAlmostEqual(theoretical_itd_samples(48000), 12.533862558, places=9)

    def test_fractional_delay_has_unity_dc_and_requested_first_moment(self):
        delay = theoretical_itd_samples(48000)
        impulse = lagrange_fractional_delay(
            delay, DESIGN["timing_model"]["fractional_delay_order"]
        )
        samples = np.arange(len(impulse), dtype=np.float64)
        self.assertAlmostEqual(float(np.sum(impulse)), 1.0, places=12)
        self.assertAlmostEqual(float(np.sum(samples * impulse)), delay, places=10)

    def test_direct_window_ends_before_first_room_cluster(self):
        sample_rate = 48000
        peak = 1000
        window = direct_window(2000, peak, sample_rate)
        end = peak + round(
            DESIGN["direct_window"]["post_peak_end_ms"] * 1e-3 * sample_rate
        )
        first_room_cluster = peak + round(5.1e-3 * sample_rate)
        self.assertEqual(window[end], 0.0)
        self.assertTrue(np.all(window[end + 1 :] == 0.0))
        self.assertLess(end, first_room_cluster)
        self.assertEqual(window[peak], 1.0)


if __name__ == "__main__":
    unittest.main()
