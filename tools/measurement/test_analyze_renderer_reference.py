#!/usr/bin/env python3
"""Unit checks for A100 renderer-reference matrix de-embedding."""

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from analyze_renderer_reference import (
    deembed_capture_matrices,
    matrix_to_paths,
    spectra_to_matrix,
)


class RendererReferenceTests(unittest.TestCase):
    def test_path_matrix_mapping_round_trips(self):
        spectra = {
            "LL": np.full(4, 1.0 + 1.0j),
            "LR": np.full(4, 2.0 + 2.0j),
            "RL": np.full(4, 3.0 + 3.0j),
            "RR": np.full(4, 4.0 + 4.0j),
        }

        rebuilt = matrix_to_paths(spectra_to_matrix(spectra))

        for label, expected in spectra.items():
            np.testing.assert_array_equal(rebuilt[label], expected)

    def test_deembedding_recovers_all_four_paths(self):
        bins = 32
        audible = np.ones(bins, dtype=bool)
        frequency_index = np.arange(bins)
        downstream = np.zeros((bins, 2, 2), dtype=np.complex128)
        downstream[:, 0, 0] = 0.7 * np.exp(-1j * frequency_index * 0.031)
        downstream[:, 1, 1] = 0.5 * np.exp(-1j * frequency_index * 0.047)

        convolved = np.empty((bins, 2, 2), dtype=np.complex128)
        clean = np.empty((bins, 2, 2), dtype=np.complex128)
        for output in range(2):
            for source in range(2):
                scale = 0.1 * (1 + output * 2 + source)
                convolved[:, output, source] = scale * np.exp(
                    -1j * frequency_index * (0.02 + scale)
                )
                clean[:, output, source] = 0.5 * scale * np.exp(
                    -1j * frequency_index * (0.01 + scale)
                )

        def captured(matrix):
            return np.einsum("fij,fjk->fik", downstream, matrix)

        matrices = {
            "downstream": downstream,
            "convolved": captured(convolved),
            "clean": captured(clean),
            "combined": captured(convolved + clean),
        }

        recovered, crosstalk_db, closure_rms = deembed_capture_matrices(
            matrices, audible, -60.0
        )

        np.testing.assert_allclose(recovered["convolved"], convolved, atol=1e-12)
        np.testing.assert_allclose(recovered["clean"], clean, atol=1e-12)
        np.testing.assert_allclose(
            recovered["combined"], convolved + clean, atol=1e-12
        )
        self.assertEqual(crosstalk_db, -180.0)
        self.assertLess(closure_rms, 1e-14)

    def test_rejects_cross_channel_downstream_processing(self):
        bins = 8
        identity = np.broadcast_to(np.eye(2), (bins, 2, 2)).copy()
        downstream = identity.copy()
        downstream[:, 0, 1] = 0.01
        matrices = {
            "downstream": downstream,
            "combined": identity,
            "convolved": identity,
            "clean": np.zeros_like(identity),
        }

        with self.assertRaisesRegex(ValueError, "not sufficiently diagonal"):
            deembed_capture_matrices(
                matrices, np.ones(bins, dtype=bool), -60.0
            )


if __name__ == "__main__":
    unittest.main()
