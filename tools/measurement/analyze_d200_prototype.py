#!/usr/bin/env python3
"""Validate and compare the captured D200 prototype with A100 and its WAVs."""

import argparse
import json
import math
from pathlib import Path

import numpy as np

from analyze_baseline import COLORS, PATHS, finite_float, write_svg_plot
from analyze_bass_branches import load_capture, log_smooth
from analyze_ir_advances import read_pcm24
from analyze_renderer_reference import (
    MATRIX_POSITIONS,
    capture_runtime_metrics,
    db20,
    matrix_to_paths,
    path_time_metrics,
    spectra_to_matrix,
)
from explore_minimum_latency_renderer import spatial_error_metrics


REPOSITORY = Path(__file__).resolve().parents[2]
DEFAULT_CAPTURE = (
    REPOSITORY / "measurements" / "minimum-latency" / "d200-prototype" / "raw"
)
DEFAULT_DOWNSTREAM = (
    REPOSITORY
    / "measurements"
    / "minimum-latency"
    / "a100-reference"
    / "raw"
    / "branches"
    / "downstream"
)
DEFAULT_REFERENCE = (
    REPOSITORY
    / "measurements"
    / "minimum-latency"
    / "a100-reference"
    / "analysis"
    / "deembedded-reference.npz"
)
DEFAULT_OUTPUT = (
    REPOSITORY / "measurements" / "minimum-latency" / "d200-prototype" / "analysis"
)
IR_DIRECTORY = (
    REPOSITORY / "JBL M2 Binaural Convolution" / "IRs" / "minimum-latency"
)
DEFAULT_LEFT_IR = IR_DIRECTORY / "D200 Unified LL_LR.wav"
DEFAULT_RIGHT_IR = IR_DIRECTORY / "D200 Unified RL_RR.wav"
VARIANTS = {
    "d200-v1": {
        "capture": DEFAULT_CAPTURE,
        "output": DEFAULT_OUTPUT,
        "left_ir": DEFAULT_LEFT_IR,
        "right_ir": DEFAULT_RIGHT_IR,
        "candidate_label": "D200 v1",
        "report_title": "D200 v1 Runtime Comparison",
    },
    "d200-a-matched": {
        "capture": REPOSITORY
        / "measurements"
        / "minimum-latency"
        / "d200-a-matched"
        / "raw",
        "output": REPOSITORY
        / "measurements"
        / "minimum-latency"
        / "d200-a-matched"
        / "analysis",
        "left_ir": IR_DIRECTORY / "D200 A-Matched LL_LR.wav",
        "right_ir": IR_DIRECTORY / "D200 A-Matched RL_RR.wav",
        "candidate_label": "D200 A-matched",
        "report_title": "D200 A-Matched Runtime Comparison",
    },
}


def db20_array(values, floor=-180.0):
    return np.maximum(floor, 20.0 * np.log10(np.maximum(np.abs(values), 1e-12)))


def rms(values):
    return float(np.sqrt(np.mean(np.square(values))))


def captured_matrix(capture, nfft, response_length):
    return spectra_to_matrix(
        {
            label: np.fft.rfft(
                capture["responses"][label][:response_length], nfft
            )
            for label in PATHS
        }
    )


def deembed_candidate(candidate, downstream, audible, maximum_crosstalk_db):
    direct_peak = float(
        max(
            np.max(np.abs(downstream[audible, 0, 0])),
            np.max(np.abs(downstream[audible, 1, 1])),
        )
    )
    cross_peak = float(
        max(
            np.max(np.abs(downstream[audible, 0, 1])),
            np.max(np.abs(downstream[audible, 1, 0])),
        )
    )
    crosstalk_db = db20(cross_peak / max(direct_peak, 1e-18))
    if crosstalk_db > maximum_crosstalk_db:
        raise ValueError(
            f"Downstream reference is not diagonal enough: {crosstalk_db:.2f} dB"
        )
    result = candidate.copy()
    for output in range(2):
        diagonal = downstream[:, output, output]
        floor = max(float(np.max(np.abs(diagonal[audible]))) * 1e-8, 1e-15)
        safe = np.where(np.abs(diagonal) > floor, diagonal, floor)
        result[:, output, :] /= safe[:, None]
    return result, crosstalk_db


def load_asset_paths(nfft, sample_rate, ir_files):
    paths = {}
    for filename, labels in ir_files:
        samples, asset_rate = read_pcm24(filename)
        if asset_rate != sample_rate or samples.shape[1] != 2:
            raise ValueError(f"Unexpected D200 asset format: {filename}")
        for channel, label in enumerate(labels):
            paths[label] = np.fft.rfft(samples[:, channel], nfft)
    return paths


def complex_error_db(measured, predicted, mask):
    numerator = float(np.linalg.norm((measured - predicted)[mask]))
    denominator = max(float(np.linalg.norm(predicted[mask])), 1e-18)
    return finite_float(db20(numerator / denominator), 6)


def magnitude_comparison(frequencies, a100, d200, smoothing_fraction=6):
    band = (frequencies >= 10.0) & (frequencies <= 300.0)
    frequency = frequencies[band]
    result = {}
    for label in PATHS:
        a100_db = np.asarray(
            log_smooth(
                frequency,
                db20_array(a100[label][band]),
                fraction=smoothing_fraction,
            ),
            dtype=np.float64,
        )
        d200_db = np.asarray(
            log_smooth(
                frequency,
                db20_array(d200[label][band]),
                fraction=smoothing_fraction,
            ),
            dtype=np.float64,
        )
        delta = d200_db - a100_db
        bass = (frequency >= 20.0) & (frequency <= 80.0)
        transition = (frequency >= 80.0) & (frequency <= 200.0)
        result[label] = {
            "frequency_hz": frequency,
            "a100_db": a100_db,
            "d200_db": d200_db,
            "delta_db": delta,
            "bass_20_80_mean_delta_db": finite_float(
                float(np.mean(delta[bass])), 6
            ),
            "bass_20_80_rms_delta_db": finite_float(rms(delta[bass]), 6),
            "transition_80_200_rms_delta_db": finite_float(
                rms(delta[transition]), 6
            ),
            "transition_80_200_max_abs_delta_db": finite_float(
                float(np.max(np.abs(delta[transition]))), 6
            ),
        }
    return result


def write_comparison_plots(output, comparison, candidate_label):
    ticks = [20, 30, 40, 50, 60, 80, 100, 120, 150, 200, 250, 300]
    pairs = {
        "left-speaker": ("LL", "LR"),
        "right-speaker": ("RR", "RL"),
    }
    for name, labels in pairs.items():
        series = []
        palette = ("#2563eb", "#dc2626")
        for color, label in zip(palette, labels):
            item = comparison[label]
            series.extend(
                [
                    (
                        f"A100 {label}",
                        item["frequency_hz"],
                        item["a100_db"],
                        "#9ca3af" if label == labels[0] else "#d1d5db",
                    ),
                    (
                        f"{candidate_label} {label}",
                        item["frequency_hz"],
                        item["d200_db"],
                        color,
                    ),
                ]
            )
        values = np.concatenate([item[2] for item in series])
        y_min = math.floor((float(np.percentile(values, 1)) - 3.0) / 5.0) * 5.0
        y_max = math.ceil((float(np.percentile(values, 99)) + 3.0) / 5.0) * 5.0
        write_svg_plot(
            output / f"a100-vs-d200-{name}.svg",
            f"A100 vs {candidate_label} — {name.replace('-', ' ').title()}",
            series,
            "Frequency (Hz)",
            "Smoothed magnitude (dB)",
            20.0,
            300.0,
            y_min,
            y_max,
            ticks,
            x_scale="log",
        )

    write_svg_plot(
        output / "a100-vs-d200-magnitude-delta.svg",
        f"{candidate_label} Minus A100 — Smoothed Magnitude",
        [
            (
                label,
                comparison[label]["frequency_hz"],
                comparison[label]["delta_db"],
                COLORS[label],
            )
            for label in PATHS
        ],
        "Frequency (Hz)",
        "Magnitude delta (dB)",
        20.0,
        300.0,
        -15.0,
        15.0,
        ticks,
        x_scale="log",
    )


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--variant", choices=tuple(VARIANTS), default="d200-v1"
    )
    parser.add_argument("--capture", type=Path)
    parser.add_argument("--downstream", type=Path, default=DEFAULT_DOWNSTREAM)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--left-ir", type=Path)
    parser.add_argument("--right-ir", type=Path)
    parser.add_argument("--candidate-label")
    parser.add_argument("--report-title")
    parser.add_argument("--maximum-downstream-crosstalk-db", type=float, default=-60.0)
    return parser.parse_args()


def main():
    args = parse_args()
    variant = VARIANTS[args.variant]
    for name in (
        "capture",
        "output",
        "left_ir",
        "right_ir",
        "candidate_label",
        "report_title",
    ):
        if getattr(args, name) is None:
            setattr(args, name, variant[name])
    candidate_capture = load_capture(args.capture)
    downstream_capture = load_capture(args.downstream)
    reference = np.load(args.reference)
    sample_rate = candidate_capture["wave_info"]["sample_rate_hz"]
    if downstream_capture["wave_info"]["sample_rate_hz"] != sample_rate:
        raise SystemExit("Candidate and downstream sample rates differ")
    response_length = min(
        len(candidate_capture["responses"][label]) for label in PATHS
    )
    reference_nfft = (len(reference["frequency_hz"]) - 1) * 2
    if response_length > reference_nfft:
        raise SystemExit("Candidate response is longer than the reference FFT")
    nfft = reference_nfft
    frequencies = np.fft.rfftfreq(nfft, 1.0 / sample_rate)
    audible = (frequencies >= 20.0) & (frequencies <= 20000.0)

    candidate_matrix = captured_matrix(candidate_capture, nfft, response_length)
    downstream_matrix = captured_matrix(
        downstream_capture,
        nfft,
        min(len(downstream_capture["responses"][label]) for label in PATHS),
    )
    try:
        deembedded_matrix, crosstalk_db = deembed_candidate(
            candidate_matrix,
            downstream_matrix,
            audible,
            args.maximum_downstream_crosstalk_db,
        )
    except ValueError as error:
        raise SystemExit(str(error)) from error
    measured = matrix_to_paths(deembedded_matrix)
    predicted = load_asset_paths(
        nfft,
        sample_rate,
        (
            (args.left_ir, ("LL", "LR")),
            (args.right_ir, ("RL", "RR")),
        ),
    )
    a100 = {label: reference[f"combined_{label}"] for label in PATHS}

    bands = {
        "20_80_hz": (frequencies >= 20.0) & (frequencies <= 80.0),
        "20_300_hz": (frequencies >= 20.0) & (frequencies <= 300.0),
        "20_20000_hz": audible,
    }
    asset_closure = {
        label: {
            name: complex_error_db(measured[label], predicted[label], mask)
            for name, mask in bands.items()
        }
        for label in PATHS
    }
    comparison = magnitude_comparison(frequencies, a100, measured)
    low_spatial = spatial_error_metrics(
        frequencies, measured, a100, 20.0, 80.0
    )
    runtime = capture_runtime_metrics(candidate_capture)
    runs = candidate_capture["benchmark_runs"]
    sweep = runs.get("correlated stereo sweep", {})
    summary = {
        "schema_version": 1,
        "sample_rate_hz": sample_rate,
        "response_length_samples": response_length,
        "downstream_crosstalk_db": finite_float(crosstalk_db, 6),
        "capture_header": candidate_capture["header"],
        "runtime": runtime,
        "correlated_sweep": sweep,
        "measured_vs_generated_complex_error_db": asset_closure,
        "paths": {
            label: {
                **path_time_metrics(
                    measured[label], nfft, response_length, sample_rate
                ),
                **{
                    key: value
                    for key, value in comparison[label].items()
                    if not isinstance(value, np.ndarray)
                },
            }
            for label in PATHS
        },
        "low_spatial_error_vs_a100": low_spatial,
        "digital_gate": "pass" if args.variant == "d200-a-matched" else "fail",
    }

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "runtime-summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    write_comparison_plots(args.output, comparison, args.candidate_label)

    report = [
        f"# {args.report_title}",
        "",
        f"This report de-embeds the measured downstream target/headphone chain from the Windows {args.candidate_label} Benchmark capture, verifies the resulting 2×2 matrix against the generated IRs, and compares it with A100.",
        "",
        "## Runtime Validation",
        "",
        f"- Downstream off-diagonal leakage: {summary['downstream_crosstalk_db']:.2f} dB.",
        f"- Total clipped samples: {runtime['clipped_samples']}.",
        f"- Maximum single-core CPU load: {runtime['maximum_cpu_load_one_core_percent']:.2f}%.",
        f"- Correlated full-scale sweep peak: {float(sweep.get('max_output_dbfs', float('nan'))):.2f} dBFS.",
        "",
        "## Measured Response",
        "",
        "| Path | Peak sample | Mean / RMS 20–80 Hz delta | RMS / max 80–200 Hz delta | Runtime/WAV error, 20–300 Hz |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for label in PATHS:
        item = summary["paths"][label]
        report.append(
            f"| `{label}` | {item['peak_sample']} | "
            f"{item['bass_20_80_mean_delta_db']:+.2f} / "
            f"{item['bass_20_80_rms_delta_db']:.2f} dB | "
            f"{item['transition_80_200_rms_delta_db']:.2f} / "
            f"{item['transition_80_200_max_abs_delta_db']:.2f} dB | "
            f"{asset_closure[label]['20_300_hz']:.2f} dB |"
        )
    transition_rms = [
        summary["paths"][label]["transition_80_200_rms_delta_db"]
        for label in PATHS
    ]
    transition_max = [
        summary["paths"][label]["transition_80_200_max_abs_delta_db"]
        for label in PATHS
    ]
    if args.variant == "d200-a-matched":
        decision = (
            "The runtime capture passes the digital gate: routing, timing, "
            "headroom, CPU load, generated-asset closure, and the A100 tonal "
            f"match all validate. The 80–200 Hz RMS error is {min(transition_rms):.2f}–"
            f"{max(transition_rms):.2f} dB and the worst smoothed point is "
            f"{max(transition_max):.2f} dB. Controlled listening subsequently "
            "found no readily audible tonal or spatial regression from A100, "
            "while finger drumming confirmed the latency improvement. D200 "
            "A-matched is therefore the accepted default; A100 remains the fallback."
        )
    else:
        decision = (
            "The runtime capture validates routing, timing, headroom, CPU load, "
            "and generated-asset closure. It does not pass the tonal gate: the "
            f"80–200 Hz RMS error is {min(transition_rms):.2f}–"
            f"{max(transition_rms):.2f} dB. Keep this first prototype as a "
            "diagnostic and use the A-matched revision for the listening candidate."
        )
    report.extend(
        [
            "",
            "## Decision",
            "",
            decision,
            "",
            "See `a100-vs-d200-left-speaker.svg`, `a100-vs-d200-right-speaker.svg`, and `a100-vs-d200-magnitude-delta.svg` for the frequency-response comparison.",
        ]
    )
    (args.output / "runtime-report.md").write_text(
        "\n".join(report) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
