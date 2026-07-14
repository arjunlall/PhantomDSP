#!/usr/bin/env python3
"""Model the bass error caused by advancing BRIRs beyond the clean path."""

import argparse
import json
from pathlib import Path

try:
    import numpy as np
except ImportError:
    raise SystemExit(
        "NumPy is required. Install it with: "
        "python3 -m pip install -r tools/measurement/requirements.txt"
    )

from analyze_baseline import PATHS, finite_float
from analyze_bass_branches import db20_array, load_capture, log_smooth


REPOSITORY = Path(__file__).resolve().parents[2]
RENDERERS = {
    "A_legacy": REPOSITORY / "measurements" / "bass-branches" / "raw",
    "C_lr4_65": (
        REPOSITORY / "measurements" / "candidates" / "lr4-65" / "bass-branches" / "raw"
    ),
}


def load_spectra(root):
    captures = {name: load_capture(root / name) for name in ("convolved", "clean")}
    sample_rate = captures["clean"]["wave_info"]["sample_rate_hz"]
    response_length = min(
        len(captures[name]["responses"][label])
        for name in captures
        for label in PATHS
    )
    nfft = 1 << (response_length - 1).bit_length()
    all_frequencies = np.fft.rfftfreq(nfft, 1.0 / sample_rate)
    band = (all_frequencies >= 20.0) & (all_frequencies <= 250.0)
    frequencies = all_frequencies[band]
    spectra = {name: {} for name in captures}
    for name in captures:
        for label in PATHS:
            spectra[name][label] = np.fft.rfft(
                captures[name]["responses"][label][:response_length], nfft
            )[band]
    return sample_rate, frequencies, spectra


def model_renderer(root, shift, smoothing_fraction):
    sample_rate, frequencies, spectra = load_spectra(root)
    brir_advance = np.exp(2j * np.pi * frequencies * shift / sample_rate)

    # The shared clean-path delay is reduced from 100 samples to zero. The
    # existing 15-sample cross-path offset remains part of the captured data.
    clean_advance_samples = 100
    clean_advance = np.exp(
        2j * np.pi * frequencies * clean_advance_samples / sample_rate
    )
    low = (frequencies >= 25.0) & (frequencies <= 60.0)
    transition = (frequencies >= 60.0) & (frequencies <= 150.0)
    paths = {}
    for label in PATHS:
        convolved = spectra["convolved"][label]
        clean = spectra["clean"][label]
        ideal = (convolved + clean) * brir_advance
        candidate_convolved = convolved * brir_advance
        candidate_clean = clean * clean_advance
        candidate = candidate_convolved + candidate_clean

        magnitude_delta = log_smooth(
            frequencies,
            db20_array(candidate) - db20_array(ideal),
            fraction=smoothing_fraction,
        )
        phase_delta = np.degrees(np.angle(candidate / ideal))
        interference = log_smooth(
            frequencies,
            db20_array(candidate)
            - db20_array(np.abs(candidate_convolved) + np.abs(candidate_clean)),
            fraction=smoothing_fraction,
        )
        paths[label] = {
            "deep_bass_rms_magnitude_error_db": finite_float(
                np.sqrt(np.mean(magnitude_delta[low] ** 2)), 5
            ),
            "transition_rms_magnitude_error_db": finite_float(
                np.sqrt(np.mean(magnitude_delta[transition] ** 2)), 5
            ),
            "transition_max_abs_magnitude_error_db": finite_float(
                np.max(np.abs(magnitude_delta[transition])), 5
            ),
            "transition_rms_phase_error_degrees": finite_float(
                np.sqrt(np.mean(phase_delta[transition] ** 2)), 5
            ),
            "worst_transition_interference_db": finite_float(
                np.min(interference[transition]), 5
            ),
        }

    return {
        "brir_advance_samples": shift,
        "clean_advance_samples": clean_advance_samples,
        "remaining_relative_lag_samples": shift - clean_advance_samples,
        "paths": paths,
        "worst_path_metrics": {
            "deep_bass_rms_magnitude_error_db": max(
                item["deep_bass_rms_magnitude_error_db"] for item in paths.values()
            ),
            "transition_rms_magnitude_error_db": max(
                item["transition_rms_magnitude_error_db"] for item in paths.values()
            ),
            "transition_max_abs_magnitude_error_db": max(
                item["transition_max_abs_magnitude_error_db"] for item in paths.values()
            ),
            "transition_rms_phase_error_degrees": max(
                item["transition_rms_phase_error_degrees"] for item in paths.values()
            ),
            "worst_transition_interference_db": min(
                item["worst_transition_interference_db"] for item in paths.values()
            ),
        },
    }


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shifts", type=int, nargs="+", default=(160, 200))
    parser.add_argument("--smoothing-fraction", type=int, default=24)
    parser.add_argument("--output", type=Path, help="Optional JSON output path")
    return parser.parse_args()


def main():
    args = parse_args()
    if min(args.shifts) <= 100:
        raise SystemExit("This model is intended for BRIR advances greater than 100 samples")
    result = {
        "assumptions": {
            "clean_base_delay_before_samples": 100,
            "clean_base_delay_after_samples": 0,
            "clean_gain_change_db": 0,
            "clean_cross_offset_change_samples": 0,
            "comparison": "candidate versus an ideal common advance of the current renderer",
        },
        "renderers": {},
    }
    for name, root in RENDERERS.items():
        result["renderers"][name] = {
            str(shift): model_renderer(root, shift, args.smoothing_fraction)
            for shift in args.shifts
        }

    encoded = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")


if __name__ == "__main__":
    main()
