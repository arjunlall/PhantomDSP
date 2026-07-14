#!/usr/bin/env python3
"""Unit checks for minimum-latency renderer primitives."""

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from explore_minimum_latency_renderer import (
    advance_non_circular,
    butterworth_lowpass_response,
    delay_non_circular,
    minimum_phase_spectrum,
    rbj_highpass_response,
)


class MinimumLatencyRendererTests(unittest.TestCase):
    def test_advance_and_delay_are_non_circular(self):
        values = np.arange(8, dtype=np.float64)
        np.testing.assert_array_equal(
            advance_non_circular(values, 3), [3, 4, 5, 6, 7, 0, 0, 0]
        )
        np.testing.assert_array_equal(
            delay_non_circular(values, 3), [0, 0, 0, 0, 1, 2, 3, 4]
        )

    def test_constant_magnitude_has_immediate_minimum_phase_impulse(self):
        nfft = 64
        spectrum = minimum_phase_spectrum(np.ones(nfft // 2 + 1), nfft)
        impulse = np.fft.irfft(spectrum, nfft)
        np.testing.assert_allclose(impulse[0], 1.0, atol=1e-12)
        np.testing.assert_allclose(impulse[1:], 0.0, atol=1e-12)

    def test_butterworth_cutoff_is_minus_three_db(self):
        sample_rate = 48000
        cutoff = 80.0
        frequencies = np.array([0.0, cutoff, sample_rate / 2.0])
        response = butterworth_lowpass_response(
            frequencies, sample_rate, cutoff, 6
        )
        self.assertAlmostEqual(abs(response[0]), 1.0, places=12)
        self.assertAlmostEqual(abs(response[1]), 1.0 / np.sqrt(2.0), places=6)
        self.assertLess(abs(response[2]), 1e-12)

    def test_protective_highpass_is_causal_minimum_phase_shape(self):
        sample_rate = 48000
        cutoff = 5.0
        frequencies = np.array([0.0, cutoff, 20.0])
        response = rbj_highpass_response(
            frequencies, sample_rate, cutoff, 1.0 / np.sqrt(2.0)
        )
        self.assertLess(abs(response[0]), 1e-9)
        self.assertAlmostEqual(abs(response[1]), 1.0 / np.sqrt(2.0), places=6)
        self.assertGreater(abs(response[2]), 0.99)


if __name__ == "__main__":
    unittest.main()
