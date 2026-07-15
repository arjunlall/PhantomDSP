#!/usr/bin/env python3

import json
import math
import unittest

import numpy as np

from analyze_baseline import read_pcm_wav, sha256
from render_idealized_treated_room import (
    ANALYSIS_DIRECTORY,
    DESIGN,
    G_ANALYSIS_DIRECTORY,
    OUTPUT_DIRECTORY,
    OUTPUT_FILES,
    treatment_impulse,
)
from render_soffit_mastering_room import DESIGN as G_DESIGN
from render_synthetic_direct import PATH_ORDER, load_stereo_paths
from render_synthetic_early_room import DIRECT_FILES
from render_synthetic_late_room import pad_to


class IdealizedTreatedRoomTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = json.loads(
            (ANALYSIS_DIRECTORY / "summary.json").read_text(encoding="utf-8")
        )
        cls.g_summary = json.loads(
            (G_ANALYSIS_DIRECTORY / "summary.json").read_text(encoding="utf-8")
        )

    def test_profile_preserves_G_and_applies_surface_specific_treatment(self):
        self.assertFalse(DESIGN["geometry_changed"])
        self.assertFalse(DESIGN["personal_direct_changed"])
        self.assertFalse(DESIGN["microclusters_changed"])
        self.assertFalse(DESIGN["synthetic_late_field_changed"])
        self.assertEqual(
            self.summary["inherited_G_geometry"], self.g_summary["design"]["room"]
        )
        treatment = DESIGN["surface_treatment"]
        self.assertTrue(treatment["applied_after_G_specular_energy_calibration"])
        self.assertEqual(treatment["transition_hz"], 1000.0)
        self.assertEqual(treatment["low_frequency_attenuation_db"]["floor"], -12.0)
        self.assertEqual(treatment["low_frequency_attenuation_db"]["left_wall"], -9.0)
        self.assertEqual(treatment["low_frequency_attenuation_db"]["right_wall"], -9.0)
        self.assertEqual(treatment["low_frequency_attenuation_db"]["ceiling"], -9.0)

    def test_treatment_filters_are_causal_and_recover_at_high_frequency(self):
        sample_rate = DESIGN["sample_rate_hz"]
        for surface, attenuation_db in DESIGN["surface_treatment"][
            "low_frequency_attenuation_db"
        ].items():
            impulse = treatment_impulse(surface, sample_rate)
            expected_dc = 10.0 ** (attenuation_db / 20.0)
            self.assertAlmostEqual(float(np.sum(impulse)), expected_dc, places=9)
            self.assertEqual(int(np.flatnonzero(np.abs(impulse) > 1e-15)[0]), 0)
            nyquist = abs(np.fft.rfft(impulse, G_DESIGN["nfft"])[-1])
            self.assertAlmostEqual(float(nyquist), 1.0, places=9)
            self.assertLess(
                self.summary["surface_filter_response_db"][surface]["250"],
                -7.0,
            )
            self.assertGreater(
                self.summary["surface_filter_response_db"][surface]["8000"],
                -0.1,
            )

    def test_checked_in_outputs_match_summary_and_preserve_direct_onset(self):
        rendered, sample_rate, _ = load_stereo_paths(
            {
                side: OUTPUT_DIRECTORY / filename
                for side, filename in OUTPUT_FILES.items()
            }
        )
        direct, direct_rate, _ = load_stereo_paths(DIRECT_FILES)
        self.assertEqual(sample_rate, direct_rate)
        for side, filename in OUTPUT_FILES.items():
            path = OUTPUT_DIRECTORY / filename
            loaded = read_pcm_wav(path)
            self.assertEqual(loaded["sample_rate"], DESIGN["sample_rate_hz"])
            self.assertEqual(loaded["sample_width_bits"], 24)
            self.assertEqual(loaded["channels"], 2)
            self.assertEqual(loaded["frame_count"], DESIGN["output_length_samples"])
            self.assertEqual(
                sha256(path), self.summary["rendered_files"][side]["sha256"]
            )

        direct_padded = {
            path: pad_to(values, DESIGN["output_length_samples"])
            for path, values in direct.items()
        }
        order_half = G_DESIGN["fractional_delay_order"] // 2
        for path in PATH_ORDER:
            first_specular = min(
                reflection["extra_delay_samples"]
                for reflection in self.summary["reflections"][path]
            )
            first_possible = (
                math.floor(self.summary["direct_peak_samples"][path] + first_specular)
                - order_half
            )
            self.assertTrue(
                np.array_equal(
                    rendered[path][:first_possible],
                    direct_padded[path][:first_possible],
                )
            )

    def test_G_microclusters_and_late_field_are_unchanged(self):
        shared = self.summary["shared_branch_hashes"]
        g_hashes = self.g_summary["branch_hashes"]
        self.assertEqual(
            shared["accepted_E_minus_C_synthetic_late"],
            g_hashes["accepted_E_minus_C_synthetic_late"],
        )
        self.assertEqual(shared["G_microclusters"], g_hashes["microclusters"])
        self.assertEqual(
            shared["G_specular_before_H_treatment"], g_hashes["specular"]
        )
        self.assertFalse(
            self.summary["measured_early_or_late_waveform_samples_copied"]
        )

    def test_response_is_smoother_without_changing_bass_or_spatial_field(self):
        h_response = self.summary["direct_relative_response"]
        g_response = self.summary["direct_relative_response_G_reference"]
        for path in ("LL", "RR"):
            self.assertGreater(
                h_response[path]["worst_200_350_hz_delta_db"],
                g_response[path]["worst_200_350_hz_delta_db"] + 1.0,
            )
            self.assertLess(
                h_response[path]["peak_to_peak_200_1000_hz_db"],
                g_response[path]["peak_to_peak_200_1000_hz_db"],
            )
        delta = self.summary["response_delta_H_minus_G"]
        self.assertLess(delta["bass_20_80_hz"]["rms_delta_db"], 0.02)
        self.assertLess(delta["spatial_1000_8000_hz"]["rms_delta_db"], 0.1)
        self.assertLess(abs(self.summary["early_energy_delta_H_minus_G_db"]), 0.2)
        center = self.summary["achieved_center_metrics"]
        self.assertGreater(center["maximum_absolute_iacc"], 0.1)
        self.assertLess(center["maximum_absolute_iacc"], 0.7)
        self.assertLess(abs(center["left_to_right_energy_db"]), 0.2)
        self.assertLess(self.summary["modeled_correlated_renderer_gain_db"], 4.0)


if __name__ == "__main__":
    unittest.main()
