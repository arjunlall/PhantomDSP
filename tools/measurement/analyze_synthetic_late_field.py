#!/usr/bin/env python3
"""Characterize candidate D's late field as broad targets for candidate E."""

import argparse
import json
import math
from pathlib import Path

import numpy as np

from analyze_baseline import COLORS, finite_float, sha256, write_svg_plot
from render_synthetic_direct import PATH_ORDER, REPOSITORY, load_stereo_paths
from render_synthetic_early_room import (
    apply_biquad,
    rbj_highpass_coefficients,
)
from render_synthetic_late_room import (
    EARLY_FILES,
    OUTPUT_DIRECTORY as D_DIRECTORY,
    OUTPUT_FILES as D_OUTPUT_FILES,
    pad_to,
)


D_FILES = {side: D_DIRECTORY / filename for side, filename in D_OUTPUT_FILES.items()}
OUTPUT_DIRECTORY = (
    REPOSITORY
    / "measurements"
    / "synthetic-reference-room"
    / "personal-late-control"
    / "characterization"
)
BAND_CENTERS_HZ = (
    250.0,
    500.0,
    1000.0,
    2000.0,
    4000.0,
    8000.0,
    16000.0,
)
ANALYSIS = {
    "sample_rate_hz": 48000,
    "late_analysis_start_ms": 30.0,
    "late_analysis_end_ms": 500.0,
    "octave_filter": {
        "type": "causal RBJ second-order high-pass plus second-order low-pass",
        "q": 1.0 / math.sqrt(2.0),
        "edge_ratio": math.sqrt(2.0),
    },
    "iacc_maximum_lag_ms": 1.0,
    "decay_fits_db": {
        "EDT": [0.0, -10.0],
        "T20": [-5.0, -25.0],
        "T30": [-5.0, -35.0],
    },
}


def rbj_lowpass_coefficients(sample_rate, cutoff, q):
    omega = 2.0 * math.pi * cutoff / sample_rate
    cosine = math.cos(omega)
    alpha = math.sin(omega) / (2.0 * q)
    a0 = 1.0 + alpha
    return (
        np.array([(1.0 - cosine) / 2.0, 1.0 - cosine, (1.0 - cosine) / 2.0])
        / a0,
        np.array([1.0, -2.0 * cosine / a0, (1.0 - alpha) / a0]),
    )


def octave_filter(values, center_hz, sample_rate):
    definition = ANALYSIS["octave_filter"]
    edge_ratio = definition["edge_ratio"]
    numerator, denominator = rbj_highpass_coefficients(
        sample_rate, center_hz / edge_ratio, definition["q"]
    )
    filtered = apply_biquad(values, numerator, denominator)
    numerator, denominator = rbj_lowpass_coefficients(
        sample_rate, center_hz * edge_ratio, definition["q"]
    )
    return apply_biquad(filtered, numerator, denominator)


def energy_decay_db(values):
    energy = np.cumsum(np.square(values[::-1]), dtype=np.float64)[::-1]
    return 10.0 * np.log10(np.maximum(energy / max(energy[0], 1e-30), 1e-12))


def extrapolated_decay_seconds(decay_db, sample_rate, high_db, low_db):
    time = np.arange(len(decay_db), dtype=np.float64) / sample_rate
    selected = (decay_db <= high_db) & (decay_db >= low_db)
    if int(np.sum(selected)) < 10:
        return None
    slope, _ = np.polyfit(time[selected], decay_db[selected], 1)
    if slope >= 0.0:
        return None
    return float(-60.0 / slope)


def maximum_correlation(left, right, start, end, maximum_lag):
    left = left[start:end]
    right = right[start:end]
    correlations = []
    for lag in range(-maximum_lag, maximum_lag + 1):
        if lag < 0:
            first, second = left[-lag:], right[: len(right) + lag]
        elif lag > 0:
            first, second = left[:-lag], right[lag:]
        else:
            first, second = left, right
        correlations.append(
            float(
                np.dot(first, second)
                / max(float(np.linalg.norm(first) * np.linalg.norm(second)), 1e-30)
            )
        )
    correlations = np.asarray(correlations)
    index = int(np.argmax(np.abs(correlations)))
    return float(correlations[index]), index - maximum_lag


def energy_db(values):
    return 10.0 * math.log10(max(float(np.sum(np.square(values))), 1e-30))


def energy_ratio_db(numerator, denominator):
    return energy_db(numerator) - energy_db(denominator)


def combined_control_to_late_db(control, late, paths):
    control_energy = sum(float(np.sum(np.square(control[path]))) for path in paths)
    late_energy = sum(float(np.sum(np.square(late[path]))) for path in paths)
    return 10.0 * math.log10(max(control_energy / max(late_energy, 1e-30), 1e-30))


def mean_energy_db(values_db):
    """Average energies represented in decibels, then return decibels."""
    values_db = np.asarray(list(values_db), dtype=np.float64)
    return 10.0 * math.log10(
        float(np.mean(np.power(10.0, values_db / 10.0)))
    )


def write_plots(output, bands):
    centers = np.asarray(BAND_CENTERS_HZ)
    path_colors = {
        "LL": COLORS["LL"],
        "LR": "#7c3aed",
        "RL": "#dc2626",
        "RR": "#059669",
    }
    write_svg_plot(
        output / "t30-by-octave.svg",
        "Candidate D Late-Field T30",
        [
            (
                path,
                centers,
                np.asarray([bands[str(int(center))]["decay_seconds"][path]["T30"] for center in centers]),
                path_colors[path],
            )
            for path in PATH_ORDER
        ]
        + [
            (
                "Median target",
                centers,
                np.asarray([bands[str(int(center))]["aggregate"]["median_T30_seconds"] for center in centers]),
                "#111827",
            )
        ],
        "Octave-band center (Hz)",
        "Extrapolated decay (seconds)",
        250.0,
        16000.0,
        0.3,
        0.8,
        list(BAND_CENTERS_HZ),
        x_scale="log",
    )
    write_svg_plot(
        output / "late-to-C-by-octave.svg",
        "Late-Field Energy Relative to Candidate C",
        [
            (
                path,
                centers,
                np.asarray(
                    [
                        bands[str(int(center))]["late_to_c_energy_db"][path]
                        for center in centers
                    ]
                ),
                path_colors[path],
            )
            for path in PATH_ORDER
        ],
        "Octave-band center (Hz)",
        "Late minus C energy (dB)",
        250.0,
        16000.0,
        -16.0,
        0.0,
        list(BAND_CENTERS_HZ),
        x_scale="log",
    )
    write_svg_plot(
        output / "late-field-coherence.svg",
        "Late-Field Maximum Absolute Correlation (±1 ms)",
        [
            (
                "L speaker / ears",
                centers,
                np.asarray([bands[str(int(center))]["iacc"]["left_speaker"]["absolute"] for center in centers]),
                "#2563eb",
            ),
            (
                "R speaker / ears",
                centers,
                np.asarray([bands[str(int(center))]["iacc"]["right_speaker"]["absolute"] for center in centers]),
                "#dc2626",
            ),
            (
                "L ear / speakers",
                centers,
                np.asarray([bands[str(int(center))]["cross_source"]["left_ear"]["absolute"] for center in centers]),
                "#7c3aed",
            ),
            (
                "R ear / speakers",
                centers,
                np.asarray([bands[str(int(center))]["cross_source"]["right_ear"]["absolute"] for center in centers]),
                "#059669",
            ),
        ],
        "Octave-band center (Hz)",
        "Absolute normalized correlation",
        250.0,
        16000.0,
        0.0,
        0.5,
        list(BAND_CENTERS_HZ),
        x_scale="log",
    )


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT_DIRECTORY)
    return parser.parse_args()


def main():
    args = parse_args()
    candidate, sample_rate, candidate_metadata = load_stereo_paths(D_FILES)
    control, control_rate, control_metadata = load_stereo_paths(EARLY_FILES)
    if sample_rate != ANALYSIS["sample_rate_hz"] or control_rate != sample_rate:
        raise ValueError(f"Expected all inputs at {ANALYSIS['sample_rate_hz']} Hz")
    control = {
        path: pad_to(values, len(candidate[path])) for path, values in control.items()
    }
    late = {path: candidate[path] - control[path] for path in PATH_ORDER}
    start = round(ANALYSIS["late_analysis_start_ms"] * 1e-3 * sample_rate)
    end = round(ANALYSIS["late_analysis_end_ms"] * 1e-3 * sample_rate)
    maximum_lag = round(ANALYSIS["iacc_maximum_lag_ms"] * 1e-3 * sample_rate)

    bands = {}
    for center in BAND_CENTERS_HZ:
        key = str(int(center))
        filtered_late = {
            path: octave_filter(late[path], center, sample_rate) for path in PATH_ORDER
        }
        filtered_control = {
            path: octave_filter(control[path], center, sample_rate) for path in PATH_ORDER
        }
        decay = {}
        t30_values = []
        for path in PATH_ORDER:
            curve = energy_decay_db(filtered_late[path])
            decay[path] = {}
            for name, limits in ANALYSIS["decay_fits_db"].items():
                value = extrapolated_decay_seconds(
                    curve, sample_rate, limits[0], limits[1]
                )
                decay[path][name] = finite_float(value, 6) if value is not None else None
            if decay[path]["T30"] is not None:
                t30_values.append(decay[path]["T30"])

        correlations = {}
        for name, first_path, second_path in (
            ("left_speaker", "LL", "LR"),
            ("right_speaker", "RL", "RR"),
            ("left_ear", "LL", "RL"),
            ("right_ear", "LR", "RR"),
        ):
            value, lag = maximum_correlation(
                filtered_late[first_path],
                filtered_late[second_path],
                start,
                end,
                maximum_lag,
            )
            correlations[name] = {
                "signed": finite_float(value, 6),
                "absolute": finite_float(abs(value), 6),
                "lag_samples": lag,
                "lag_ms": finite_float(lag / sample_rate * 1000.0, 6),
            }
        bands[key] = {
            "center_hz": center,
            "decay_seconds": decay,
            "aggregate": {
                "median_T30_seconds": finite_float(np.median(t30_values), 6),
            },
            "late_energy_db": {
                path: finite_float(energy_db(filtered_late[path]), 6)
                for path in PATH_ORDER
            },
            "late_to_c_energy_db": {
                path: finite_float(
                    energy_ratio_db(filtered_late[path], filtered_control[path]), 6
                )
                for path in PATH_ORDER
            },
            "iacc": {
                "left_speaker": correlations["left_speaker"],
                "right_speaker": correlations["right_speaker"],
            },
            "cross_source": {
                "left_ear": correlations["left_ear"],
                "right_ear": correlations["right_ear"],
            },
        }

    broad = {
        "path_late_to_c_energy_db": {
            path: finite_float(energy_ratio_db(late[path], control[path]), 6)
            for path in PATH_ORDER
        },
        "combined_retained_c_to_late_energy_ratio_db": {
            "left_speaker": finite_float(combined_control_to_late_db(control, late, ("LL", "LR")), 6),
            "right_speaker": finite_float(combined_control_to_late_db(control, late, ("RL", "RR")), 6),
            "left_ear": finite_float(combined_control_to_late_db(control, late, ("LL", "RL")), 6),
            "right_ear": finite_float(combined_control_to_late_db(control, late, ("LR", "RR")), 6),
        },
        "late_ear_level_difference_db": {
            "left_speaker_LL_minus_LR": finite_float(
                energy_ratio_db(late["LL"], late["LR"]), 6
            ),
            "right_speaker_RR_minus_RL": finite_float(
                energy_ratio_db(late["RR"], late["RL"]), 6
            ),
        },
        "late_source_total_balance_db": finite_float(
            energy_ratio_db(
                np.concatenate([late["LL"], late["LR"]]),
                np.concatenate([late["RL"], late["RR"]]),
            ),
            6,
        ),
    }
    median_control_to_late = float(
        np.median(
            list(broad["combined_retained_c_to_late_energy_ratio_db"].values())
        )
    )
    mean_late_energy_db = {
        key: mean_energy_db(value["late_energy_db"].values())
        for key, value in bands.items()
    }
    reference_late_energy_db = mean_late_energy_db["1000"]
    target = {
        "purpose": "broad statistical target for candidate E; do not copy D waveform or narrow resonances",
        "transition_ms": [25.0, 30.0],
        "protective_highpass_hz": 250.0,
        "combined_retained_c_to_late_energy_ratio_db": finite_float(
            median_control_to_late, 3
        ),
        "late_energy_shape_db_relative_to_1khz": {
            key: finite_float(value - reference_late_energy_db, 3)
            for key, value in mean_late_energy_db.items()
        },
        "rt60_seconds_by_octave": {
            key: value["aggregate"]["median_T30_seconds"] for key, value in bands.items()
        },
        "maximum_absolute_iacc_by_octave": {
            key: finite_float(
                np.mean(
                    [
                        value["iacc"]["left_speaker"]["absolute"],
                        value["iacc"]["right_speaker"]["absolute"],
                    ]
                ),
                3,
            )
            for key, value in bands.items()
        },
        "late_ear_level_difference_db": 0.0,
        "source_symmetry": "use averaged D statistics rather than measured left/right imbalance",
        "late_source_injection": "separate decorrelated inputs into one shared binaural diffuse field",
    }

    args.output.mkdir(parents=True, exist_ok=True)
    write_plots(args.output, bands)
    summary = {
        "schema_version": 1,
        "status": "offline characterization of the preferred D late field",
        "analysis": ANALYSIS,
        "input_files": {
            "candidate_d": {
                side: {
                    **metadata,
                    "sha256": sha256(D_FILES[side]),
                }
                for side, metadata in candidate_metadata.items()
            },
            "candidate_c": {
                side: {
                    **metadata,
                    "sha256": sha256(EARLY_FILES[side]),
                }
                for side, metadata in control_metadata.items()
            },
        },
        "broad_metrics": broad,
        "octave_bands": bands,
        "candidate_e_target": target,
        "plots": [
            "t30-by-octave.svg",
            "late-to-C-by-octave.svg",
            "late-field-coherence.svg",
        ],
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    report = [
        "# Preferred D Late-Field Characterization",
        "",
        "This analysis subtracts candidate C from D and measures only the post-25 ms addition. It defines broad candidate E targets without copying D's waveform or narrow room resonances.",
        "",
        "## Main findings",
        "",
        f"- Median combined candidate-C-to-late energy ratio: {median_control_to_late:.2f} dB.",
        f"- Median 500 Hz–16 kHz T30: {np.median([bands[str(int(center))]['aggregate']['median_T30_seconds'] for center in BAND_CENTERS_HZ if center >= 500]):.3f} seconds.",
        "- Late energy is nearly equal at the two ears for each speaker, unlike the strongly lateralized direct paths.",
        "- Maximum binaural correlation is low above 500 Hz, consistent with a diffuse field; the 250 Hz band remains more coherent.",
        "- Candidate E should use symmetric averaged targets and separate source injections into one shared binaural diffuse field.",
        "",
        "## Boundary",
        "",
        "Candidate C contains the retained direct and early fields, so this level ratio is not a strict direct-to-reverberant ratio. These are engineering targets derived from the preferred hybrid, not proof that each metric is independently perceptually necessary. E must change only the late field so listening can validate the synthetic replacement.",
    ]
    (args.output / "report.md").write_text(
        "\n".join(report) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
