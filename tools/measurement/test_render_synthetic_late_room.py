#!/usr/bin/env python3

import json
import unittest

import numpy as np

from analyze_baseline import read_pcm_wav, sha256
from render_synthetic_direct import PATH_ORDER, load_stereo_paths
from render_synthetic_early_room import early_window
from render_synthetic_late_room import (
    ANALYSIS_DIRECTORY,
    DESIGN,
    EARLY_FILES,
    OUTPUT_DIRECTORY,
    OUTPUT_FILES,
    late_window,
    pad_to,
)


class SyntheticLateRoomTests(unittest.TestCase):
    def test_late_window_is_exact_complement_after_twenty_five_ms(self):
        sample_rate = DESIGN["sample_rate_hz"]
        peak = 1000
        length = 40000
        early = early_window(length, peak, sample_rate)
        late = late_window(length, peak, sample_rate)
        start = peak + round(25e-3 * sample_rate)
        full = peak + round(30e-3 * sample_rate)
        self.assertTrue(np.all(late[: start + 1] == 0.0))
        self.assertTrue(np.allclose(early[start:] + late[start:], 1.0))
        self.assertEqual(late[full], 1.0)
        self.assertTrue(np.all(late[full:] == 1.0))

    def test_checked_in_outputs_match_summary_and_preserve_C_through_25_ms(self):
        summary = json.loads(
            (ANALYSIS_DIRECTORY / "summary.json").read_text(encoding="utf-8")
        )
        rendered, sample_rate, _ = load_stereo_paths(
            {side: OUTPUT_DIRECTORY / filename for side, filename in OUTPUT_FILES.items()}
        )
        early, early_rate, _ = load_stereo_paths(EARLY_FILES)
        self.assertEqual(sample_rate, early_rate)
        for side, filename in OUTPUT_FILES.items():
            path = OUTPUT_DIRECTORY / filename
            loaded = read_pcm_wav(path)
            self.assertEqual(loaded["sample_rate"], DESIGN["sample_rate_hz"])
            self.assertEqual(loaded["sample_width_bits"], 24)
            self.assertEqual(loaded["channels"], 2)
            self.assertEqual(loaded["frame_count"], DESIGN["output_length_samples"])
            self.assertEqual(sha256(path), summary["rendered_files"][side]["sha256"])
        for label in PATH_ORDER:
            control = pad_to(early[label], DESIGN["output_length_samples"])
            direct_peak = summary["paths"][label]["synthetic_direct_peak_sample"]
            end = direct_peak + round(25e-3 * sample_rate)
            self.assertTrue(np.array_equal(rendered[label][: end + 1], control[: end + 1]))


if __name__ == "__main__":
    unittest.main()
