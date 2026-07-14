#!/usr/bin/env python3

import json
import math
import unittest

import numpy as np

from analyze_baseline import read_pcm_wav, sha256
from render_synthetic_direct import PATH_ORDER, load_stereo_paths
from render_synthetic_late_room import pad_to
from render_soffit_mastering_room import (
    ANALYSIS_DIRECTORY,
    DESIGN,
    DIRECT_FILES,
    OUTPUT_DIRECTORY,
    OUTPUT_FILES,
    SURFACES,
    ear_positions,
    listener_position,
    source_positions,
)


class SoffitMasteringRoomTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = json.loads(
            (ANALYSIS_DIRECTORY / "summary.json").read_text(encoding="utf-8")
        )

    def test_geometry_is_proportioned_soffit_mounted_and_equilateral(self):
        room = DESIGN["room"]
        listener = listener_position()
        sources = source_positions()
        ears = ear_positions()

        self.assertAlmostEqual(listener[0], 0.03, places=12)
        self.assertAlmostEqual(room["listener_from_front_wall_m"] / room["length_m"], 0.379, places=3)
        self.assertGreater(abs(room["length_m"] - room["width_m"]), 1.0)
        self.assertEqual(set(SURFACES), {"left_wall", "right_wall", "floor", "ceiling"})
        self.assertFalse(DESIGN["soffit_mount"]["front_wall_reflection_retained"])
        self.assertFalse(DESIGN["soffit_mount"]["rear_radiation_retained"])

        for source in sources.values():
            self.assertAlmostEqual(source[1], room["listener_from_front_wall_m"], places=12)
        source_distance = np.linalg.norm(sources["left"] - listener)
        base_width = np.linalg.norm(sources["left"] - sources["right"])
        self.assertAlmostEqual(source_distance, base_width, places=12)
        self.assertAlmostEqual(
            abs(math.degrees(math.atan2(sources["left"][0] - listener[0], sources["left"][1] - listener[1]))),
            DESIGN["speaker_azimuth_degrees"],
            places=12,
        )
        self.assertAlmostEqual(np.mean([ear[0] for ear in ears.values()]), listener[0], places=12)

    def test_checked_in_outputs_match_summary_and_preserve_direct_onset(self):
        rendered, sample_rate, _ = load_stereo_paths(
            {side: OUTPUT_DIRECTORY / filename for side, filename in OUTPUT_FILES.items()}
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
            self.assertEqual(sha256(path), self.summary["rendered_files"][side]["sha256"])

        direct_padded = {
            path: pad_to(values, DESIGN["output_length_samples"])
            for path, values in direct.items()
        }
        order_half = DESIGN["fractional_delay_order"] // 2
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

    def test_room_branches_are_distinct_and_late_reference_is_unchanged(self):
        hashes = self.summary["branch_hashes"]
        self.assertEqual(len(set(hashes["complete_early"].values())), 4)
        self.assertEqual(len(set(hashes["microclusters"].values())), 4)
        self.assertFalse(self.summary["measured_early_or_late_waveform_samples_copied"])

        f_summary = json.loads(
            (
                ANALYSIS_DIRECTORY.parent.parent
                / "theoretical-early"
                / "analysis"
                / "summary.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            hashes["accepted_E_minus_C_synthetic_late"],
            f_summary["branch_hashes"]["accepted_E_minus_C_synthetic_late"],
        )

    def test_early_field_meets_spatial_and_level_contract(self):
        achieved = self.summary["achieved_center_metrics"]
        target = self.summary["target_center_metrics"]
        self.assertLess(abs(achieved["left_to_right_energy_db"]), 0.2)
        self.assertLess(
            abs(achieved["maximum_absolute_iacc"] - target["maximum_absolute_iacc"]),
            abs(1.0 - target["maximum_absolute_iacc"]),
        )
        self.assertGreater(achieved["maximum_absolute_iacc"], 0.1)
        self.assertLess(achieved["maximum_absolute_iacc"], 0.7)
        self.assertGreater(self.summary["first_full_center_ear_difference_ms"], 2.0)
        self.assertLess(self.summary["first_full_center_ear_difference_ms"], 6.0)
        for delta in self.summary["center_early_energy_delta_G_minus_E_db"].values():
            self.assertLess(abs(delta), 0.5)

        for path in PATH_ORDER:
            for level in self.summary[
                "specular_reflection_1_8khz_energy_db_relative_to_direct"
            ][path].values():
                self.assertLessEqual(level, -10.0)

    def test_bass_response_and_headroom_remain_controlled(self):
        response = self.summary["response_delta_G_minus_E"]
        self.assertLess(response["bass_20_80_hz"]["rms_delta_db"], 0.03)
        self.assertLess(abs(response["room_band_300_10000_hz"]["mean_delta_db"]), 2.0)
        self.assertLess(self.summary["modeled_correlated_renderer_gain_db"], 4.0)


if __name__ == "__main__":
    unittest.main()
