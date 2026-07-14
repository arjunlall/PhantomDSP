#!/usr/bin/env python3

import json
import unittest

import numpy as np

from render_synthetic_early_room import (
    ANALYSIS_DIRECTORY,
    DESIGN,
    OUTPUT_DIRECTORY,
    OUTPUT_FILES,
    apply_biquad,
    early_window,
    rbj_highpass_coefficients,
    shift_relative_to_peak,
)
from analyze_baseline import read_pcm_wav, sha256


class SyntheticEarlyRoomTests(unittest.TestCase):
    def test_early_window_is_zero_before_four_ms_and_after_thirty_ms(self):
        sample_rate = DESIGN["sample_rate_hz"]
        peak = 1000
        window = early_window(4000, peak, sample_rate)
        start = peak + round(4e-3 * sample_rate)
        full = peak + round(4.75e-3 * sample_rate)
        end = peak + round(30e-3 * sample_rate)
        self.assertTrue(np.all(window[: start + 1] == 0.0))
        self.assertEqual(window[full], 1.0)
        self.assertEqual(window[peak + round(25e-3 * sample_rate) - 1], 1.0)
        self.assertEqual(window[end], 0.0)
        self.assertTrue(np.all(window[end + 1 :] == 0.0))

    def test_highpass_has_zero_dc_and_unity_high_frequency_gain(self):
        numerator, denominator = rbj_highpass_coefficients(48000, 100.0, 2 ** -0.5)
        dc = np.sum(numerator) / np.sum(denominator)
        nyquist = (numerator[0] - numerator[1] + numerator[2]) / (
            denominator[0] - denominator[1] + denominator[2]
        )
        self.assertAlmostEqual(float(dc), 0.0, places=10)
        self.assertAlmostEqual(float(nyquist), 1.0, places=10)

    def test_highpass_is_causal(self):
        numerator, denominator = rbj_highpass_coefficients(48000, 250.0, 2 ** -0.5)
        impulse = np.zeros(128)
        impulse[10] = 1.0
        output = impulse
        for _ in range(DESIGN["reflection_highpass"]["sections"]):
            output = apply_biquad(output, numerator, denominator)
        self.assertTrue(np.all(output[:10] == 0.0))
        self.assertNotEqual(output[10], 0.0)

    def test_relative_shift_maps_source_peak_to_direct_peak(self):
        values = np.arange(20, dtype=np.float64)
        shifted = shift_relative_to_peak(values, 10, 3, 12)
        self.assertEqual(shifted[3], values[10])
        self.assertTrue(np.array_equal(shifted[:12], values[7:19]))

    def test_checked_in_outputs_match_analysis_summary(self):
        summary = json.loads(
            (ANALYSIS_DIRECTORY / "summary.json").read_text(encoding="utf-8")
        )
        for side, filename in OUTPUT_FILES.items():
            path = OUTPUT_DIRECTORY / filename
            loaded = read_pcm_wav(path)
            self.assertEqual(loaded["sample_rate"], DESIGN["sample_rate_hz"])
            self.assertEqual(loaded["sample_width_bits"], 24)
            self.assertEqual(loaded["channels"], 2)
            self.assertEqual(loaded["frame_count"], DESIGN["output_length_samples"])
            self.assertEqual(sha256(path), summary["rendered_files"][side]["sha256"])


if __name__ == "__main__":
    unittest.main()
