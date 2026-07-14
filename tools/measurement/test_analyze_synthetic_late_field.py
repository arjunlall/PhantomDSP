#!/usr/bin/env python3

import math
import unittest

import numpy as np

from analyze_synthetic_late_field import (
    energy_decay_db,
    extrapolated_decay_seconds,
    maximum_correlation,
    octave_filter,
)


class SyntheticLateFieldAnalysisTests(unittest.TestCase):
    def test_decay_fit_recovers_exponential_rt60(self):
        sample_rate = 48000
        rt60 = 0.6
        time = np.arange(sample_rate) / sample_rate
        amplitude = np.exp(-math.log(1000.0) * time / rt60)
        decay = energy_decay_db(amplitude)
        recovered = extrapolated_decay_seconds(decay, sample_rate, -5.0, -35.0)
        self.assertAlmostEqual(recovered, rt60, places=3)

    def test_maximum_correlation_recovers_delay(self):
        rng = np.random.default_rng(7)
        left = rng.normal(size=4096)
        right = np.pad(left[:-7], (7, 0))
        correlation, lag = maximum_correlation(left, right, 0, len(left), 48)
        self.assertGreater(correlation, 0.99)
        self.assertEqual(lag, 7)

    def test_octave_filter_is_finite_and_rejects_dc(self):
        values = np.ones(4096)
        filtered = octave_filter(values, 1000.0, 48000)
        self.assertTrue(np.all(np.isfinite(filtered)))
        self.assertLess(abs(float(np.mean(filtered[-1000:]))), 1e-6)


if __name__ == "__main__":
    unittest.main()
