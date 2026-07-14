#!/usr/bin/env python3
"""Render the causal D200 A-matched 2x2 prototype as 24-bit WAVs."""

import argparse
import json
from pathlib import Path

import numpy as np

from analyze_baseline import finite_float
from explore_minimum_latency_renderer import (
    PATH_ORDER,
    REFERENCE,
    build_low_paths,
    load_reference,
    rbj_peaking_response,
    smoothed_db,
    spatial_error_metrics,
)
from render_minimum_latency_renderer import (
    quantization_error_db,
    quantize_float24,
    sha256,
    timing_metrics,
    write_pcm24,
)


REPOSITORY = Path(__file__).resolve().parents[2]
DEFAULT_IR_OUTPUT = (
    REPOSITORY / "JBL M2 Binaural Convolution" / "IRs" / "minimum-latency"
)
DEFAULT_ANALYSIS_OUTPUT = (
    REPOSITORY
    / "measurements"
    / "minimum-latency"
    / "d200-a-matched"
    / "analysis"
)
OUTPUT_FILES = {
    "left_speaker": "D200 A-Matched LL_LR.wav",
    "right_speaker": "D200 A-Matched RL_RR.wav",
}
LOCKED_DESIGN = {
    "lowpass_cutoff_hz": 90.0,
    "lowpass_order": 1,
    "low_gain_db": 0.75,
    "highpass_cutoff_hz": 5.0,
    "highpass_order": 2,
    "cross_delay_samples": 15,
    "common_output_eq": {
        "type": "peaking",
        "center_hz": 350.0,
        "gain_db": -5.0,
        "q": 2.0,
    },
    "additional_high_advance_samples": 100,
    "output_length_samples": 32768,
    "nfft": 65536,
}


def rms(values):
    return float(np.sqrt(np.mean(np.square(values))))


def band_metrics(frequencies, candidate, reference, low, high):
    mask = (frequencies >= low) & (frequencies <= high)
    delta = candidate[mask] - reference[mask]
    return {
        "mean_delta_db": finite_float(float(np.mean(delta)), 6),
        "rms_delta_db": finite_float(rms(delta), 6),
        "maximum_absolute_delta_db": finite_float(
            float(np.max(np.abs(delta))), 6
        ),
    }


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, default=REFERENCE)
    parser.add_argument("--ir-output", type=Path, default=DEFAULT_IR_OUTPUT)
    parser.add_argument(
        "--analysis-output", type=Path, default=DEFAULT_ANALYSIS_OUTPUT
    )
    return parser.parse_args()


def main():
    args = parse_args()
    design = LOCKED_DESIGN
    reference, sample_rate, combined, high = load_reference(
        args.reference,
        design["nfft"],
        design["output_length_samples"],
        design["additional_high_advance_samples"],
    )
    frequencies = np.fft.rfftfreq(design["nfft"], 1.0 / sample_rate)
    low, low_tail, deep_levels = build_low_paths(
        reference,
        sample_rate,
        frequencies,
        design["nfft"],
        design["output_length_samples"],
        design["lowpass_cutoff_hz"],
        design["lowpass_order"],
        design["highpass_cutoff_hz"],
        design["highpass_order"],
        design["cross_delay_samples"],
        design["low_gain_db"],
    )
    output_eq = design["common_output_eq"]
    common_correction = rbj_peaking_response(
        frequencies,
        sample_rate,
        output_eq["center_hz"],
        output_eq["gain_db"],
        output_eq["q"],
    )
    candidate_spectra = {
        label: (high[label] + low[label]) * common_correction
        for label in PATH_ORDER
    }
    candidate_full_impulses = {
        label: np.fft.irfft(candidate_spectra[label], design["nfft"])
        for label in PATH_ORDER
    }
    candidate_impulses = {
        label: candidate_full_impulses[label][
            : design["output_length_samples"]
        ]
        for label in PATH_ORDER
    }
    low_impulses = {
        label: np.fft.irfft(low[label], design["nfft"])[
            : design["output_length_samples"]
        ]
        for label in PATH_ORDER
    }

    stereo_outputs = {
        "left_speaker": np.column_stack(
            [candidate_impulses["LL"], candidate_impulses["LR"]]
        ),
        "right_speaker": np.column_stack(
            [candidate_impulses["RL"], candidate_impulses["RR"]]
        ),
    }
    files = {}
    for key, samples in stereo_outputs.items():
        output_path = args.ir_output / OUTPUT_FILES[key]
        write_pcm24(output_path, samples, sample_rate)
        quantized = quantize_float24(samples)
        files[key] = {
            "path": str(output_path.relative_to(REPOSITORY)),
            "sha256": sha256(output_path),
            "sample_rate_hz": sample_rate,
            "sample_width_bits": 24,
            "channels": 2,
            "frames": len(samples),
            "peak_linear": finite_float(float(np.max(np.abs(quantized))), 9),
            "quantization_error_rms_db": quantization_error_db(
                samples, quantized
            ),
        }

    comparison = {}
    for label in PATH_ORDER:
        smooth_frequency, candidate_db = smoothed_db(
            frequencies, candidate_spectra[label], high=500.0
        )
        _, a100_db = smoothed_db(
            frequencies, combined[label], high=500.0
        )
        _, high_db = smoothed_db(
            frequencies, high[label], high=500.0
        )
        comparison[label] = {
            "bass_20_80_vs_a100": band_metrics(
                smooth_frequency, candidate_db, a100_db, 20.0, 80.0
            ),
            "midbass_80_160_vs_a100": band_metrics(
                smooth_frequency, candidate_db, a100_db, 80.0, 160.0
            ),
            "upper_bass_160_250_vs_a100": band_metrics(
                smooth_frequency, candidate_db, a100_db, 160.0, 250.0
            ),
            "return_250_500_vs_advanced_brir": band_metrics(
                smooth_frequency, candidate_db, high_db, 250.0, 500.0
            ),
        }

    spatial = {
        "20_80_vs_a100": spatial_error_metrics(
            frequencies, candidate_spectra, combined, 20.0, 80.0
        ),
        "80_160_vs_a100": spatial_error_metrics(
            frequencies, candidate_spectra, combined, 80.0, 160.0
        ),
        "160_250_vs_a100": spatial_error_metrics(
            frequencies, candidate_spectra, combined, 160.0, 250.0
        ),
        "250_500_vs_advanced_brir": spatial_error_metrics(
            frequencies, candidate_spectra, high, 250.0, 500.0
        ),
    }
    summary = {
        "schema_version": 1,
        "status": "offline prototype; not the active renderer",
        "reference": {
            "path": str(args.reference.relative_to(REPOSITORY)),
            "sha256": sha256(args.reference),
            "precision_branches_used": True,
        },
        "design": design,
        "deep_target_level_db_before_calibration": {
            ear: finite_float(value, 6) for ear, value in deep_levels.items()
        },
        "low_tail_energy_beyond_output_db": {
            ear: finite_float(value, 6) for ear, value in low_tail.items()
        },
        "candidate_tail_energy_beyond_output_db": {
            label: finite_float(
                10.0
                * np.log10(
                    max(
                        float(
                            np.sum(
                                np.square(
                                    candidate_full_impulses[label][
                                        design["output_length_samples"] :
                                    ]
                                )
                            )
                        )
                        / max(
                            float(
                                np.sum(
                                    np.square(candidate_full_impulses[label])
                                )
                            ),
                            1e-30,
                        ),
                        1e-30,
                    )
                ),
                6,
            )
            for label in PATH_ORDER
        },
        "paths": {
            label: {
                **timing_metrics(candidate_impulses[label], sample_rate),
                "low_model_peak_sample": int(
                    np.argmax(np.abs(low_impulses[label]))
                ),
                "comparison": comparison[label],
            }
            for label in PATH_ORDER
        },
        "spatial_error": spatial,
        "files": files,
    }
    args.analysis_output.mkdir(parents=True, exist_ok=True)
    (args.analysis_output / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )

    report = [
        "# D200 A-Matched Renderer Prototype",
        "",
        "This offline revision keeps A100 as the playback default. It responds to the measured D200 v1 loss in the 80–200 Hz handoff without reintroducing a runtime bass branch.",
        "",
        "## Locked Design",
        "",
        "- Keep the same common 200-sample BRIR advance and one-convolution 2×2 topology as D200 v1.",
        "- Replace the sixth-order 80 Hz low-pass with a first-order 90 Hz low-pass and +0.75 dB calibration.",
        "- Retain the causal 5 Hz protective high-pass and 15-sample cross-path offset.",
        "- Let the clean model decay gently through upper bass so the complete response stays close to the preferred A100 reference through 200 Hz.",
        "- Apply one common −5 dB, 350 Hz, Q 2 correction after the 2×2 sum to remove the gentle model's shared lower-mid excess without changing interaural ratios.",
        "",
        "The first-order low model peaks at sample 1 on direct paths and sample 16 on cross paths. Relative to the advanced BRIR peaks, that closely recreates A100's clean-before-convolved timing while avoiding v1's approximately 8.5 ms low-pass peak delay.",
        "",
        "## Offline Response Match",
        "",
        "| Path | 20–80 Hz mean / RMS | 80–160 Hz mean / RMS | 160–250 Hz mean / RMS | Total peak |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for label in PATH_ORDER:
        item = summary["paths"][label]
        bass = item["comparison"]["bass_20_80_vs_a100"]
        mid = item["comparison"]["midbass_80_160_vs_a100"]
        upper = item["comparison"]["upper_bass_160_250_vs_a100"]
        report.append(
            f"| `{label}` | {bass['mean_delta_db']:+.2f} / {bass['rms_delta_db']:.2f} dB | "
            f"{mid['mean_delta_db']:+.2f} / {mid['rms_delta_db']:.2f} dB | "
            f"{upper['mean_delta_db']:+.2f} / {upper['rms_delta_db']:.2f} dB | "
            f"{item['peak_sample']} ({item['peak_time_ms']:.3f} ms) |"
        )
    report.extend(
        [
            "",
            "Windows runtime validation is recorded in `runtime-report.md`. The digital gate passes; A100 remains the default pending a controlled listening comparison with D200 A-Matched.",
        ]
    )
    (args.analysis_output / "report.md").write_text(
        "\n".join(report) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
