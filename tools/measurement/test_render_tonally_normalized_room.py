#!/usr/bin/env python3

import json
import unittest

import numpy as np

from analyze_baseline import read_pcm_wav, sha256
from render_idealized_treated_room import ANALYSIS_DIRECTORY as H_ANALYSIS_DIRECTORY
from render_synthetic_direct import load_stereo_paths
from render_tonally_normalized_room import (
    ANALYSIS_DIRECTORY,
    DESIGN,
    H_FILES,
    OUTPUT_DIRECTORY,
    OUTPUT_FILES,
    SPEAKER_PATHS,
    design_speaker_filter,
    speaker_ratio_db,
)
from render_synthetic_early_room import DIRECT_FILES
from render_synthetic_late_room import pad_to


class TonallyNormalizedRoomTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = json.loads(
            (ANALYSIS_DIRECTORY / "summary.json").read_text(encoding="utf-8")
        )
        cls.h_summary = json.loads(
            (H_ANALYSIS_DIRECTORY / "summary.json").read_text(encoding="utf-8")
        )

    def test_design_corrects_complete_to_direct_binaural_energy_only(self):
        correction = DESIGN["correction"]
        self.assertEqual(
            correction["reference"],
            "complete-to-direct binaural energy ratio per virtual speaker",
        )
        self.assertEqual(correction["smoothing_fractional_octave"], 6)
        self.assertEqual(correction["flat_band_hz"], [200.0, 1000.0])
        self.assertEqual(correction["transition_band_hz"], [160.0, 1250.0])
        self.assertEqual(correction["phase"], "minimum phase")
        self.assertEqual(correction["bulk_delay_samples"], 0)
        self.assertEqual(
            correction["applied_identically_within_speaker_pairs"],
            {"left": ["LL", "LR"], "right": ["RL", "RR"]},
        )

    def test_checked_in_outputs_match_summary_and_verified_H_parent(self):
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
                sha256(H_FILES[side]),
                self.h_summary["rendered_files"][side]["sha256"],
            )

    def test_generated_filters_are_causal_and_pair_shared(self):
        candidate_h, sample_rate, _ = load_stereo_paths(H_FILES)
        direct, direct_rate, _ = load_stereo_paths(DIRECT_FILES)
        self.assertEqual(sample_rate, direct_rate)
        direct = {
            path: pad_to(values, DESIGN["output_length_samples"])
            for path, values in direct.items()
        }
        frequencies = np.fft.rfftfreq(DESIGN["nfft"], 1.0 / sample_rate)
        h_spectra = {
            path: np.fft.rfft(values, DESIGN["nfft"])
            for path, values in candidate_h.items()
        }
        direct_spectra = {
            path: np.fft.rfft(values, DESIGN["nfft"])
            for path, values in direct.items()
        }
        for speaker, paths in SPEAKER_PATHS.items():
            ratio = speaker_ratio_db(h_spectra, direct_spectra, paths)
            result = design_speaker_filter(frequencies, ratio)
            first = int(np.flatnonzero(np.abs(result["impulse"]) > 1e-15)[0])
            self.assertEqual(first, 0)
            self.assertEqual(
                self.summary["filter_impulse_first_nonzero_sample"][speaker], 0
            )

    def test_broad_binaural_coloration_is_materially_flatter(self):
        for speaker in SPEAKER_PATHS:
            response = self.summary["binaural_response_200_1000_hz"][speaker]
            self.assertLess(
                response["I"]["rms_deviation_from_mean_db"],
                response["H"]["rms_deviation_from_mean_db"] * 0.4,
            )
            self.assertLess(
                response["I"]["peak_to_peak_db"],
                response["H"]["peak_to_peak_db"] * 0.45,
            )
            self.assertLess(
                abs(response["I"]["mean_db"] - response["H"]["mean_db"]),
                0.01,
            )

    def test_spatial_ratios_and_protected_bands_are_preserved(self):
        for metrics in self.summary[
            "interaural_preservation_200_1000_hz"
        ].values():
            self.assertLess(metrics["rms_ild_delta_db"], 0.01)
            self.assertLess(metrics["maximum_absolute_ild_delta_db"], 0.1)
            self.assertLess(metrics["maximum_absolute_phase_delta_degrees"], 1.0)

        delta = self.summary["response_delta_I_minus_H"]
        self.assertLess(delta["bass_20_80_hz"]["rms_delta_db"], 0.005)
        self.assertLess(delta["protected_80_160_hz"]["rms_delta_db"], 0.01)
        self.assertLess(
            delta["protected_1250_8000_hz"]["rms_delta_db"], 0.005
        )
        for tail_db in self.summary[
            "truncated_filter_tail_energy_db_relative_to_complete_convolution"
        ].values():
            self.assertLess(tail_db, -90.0)
        self.assertLess(self.summary["modeled_correlated_renderer_gain_db"], 4.0)


if __name__ == "__main__":
    unittest.main()
