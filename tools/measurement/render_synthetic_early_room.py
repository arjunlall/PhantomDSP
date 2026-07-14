#!/usr/bin/env python3
"""Render candidate C: synthetic direct sound plus personal early reflections."""

import argparse
import json
import math
from pathlib import Path

import numpy as np

from analyze_baseline import COLORS, finite_float, read_pcm_wav, sha256, write_svg_plot
from analyze_bass_branches import log_smooth
from render_active_renderer import write_pcm24
from render_synthetic_direct import (
    ACTIVE_FILES,
    PATH_CHANNELS,
    PATH_ORDER,
    REPOSITORY,
    SOURCE_FILES,
    db20,
    load_stereo_paths,
)


DIRECT_DIRECTORY = REPOSITORY / "Synthetic Reference Room" / "IRs" / "direct"
DIRECT_FILES = {
    "left": DIRECT_DIRECTORY / "Personal Direct Left Speaker.wav",
    "right": DIRECT_DIRECTORY / "Personal Direct Right Speaker.wav",
}
DIRECT_ANALYSIS = (
    REPOSITORY
    / "measurements"
    / "synthetic-reference-room"
    / "direct-only"
    / "analysis"
    / "summary.json"
)
OUTPUT_DIRECTORY = (
    REPOSITORY / "Synthetic Reference Room" / "IRs" / "personal-early"
)
ANALYSIS_DIRECTORY = (
    REPOSITORY
    / "measurements"
    / "synthetic-reference-room"
    / "personal-early"
    / "analysis"
)
OUTPUT_FILES = {
    "left": "Personal Early Room Left Speaker.wav",
    "right": "Personal Early Room Right Speaker.wav",
}
DESIGN = {
    "sample_rate_hz": 48000,
    "early_window": {
        "fade_in_start_ms": 4.0,
        "full_level_start_ms": 4.75,
        "full_level_end_ms": 25.0,
        "fade_out_end_ms": 30.0,
    },
    "reflection_highpass": {
        "type": "cascaded RBJ Butterworth biquads (Linkwitz-Riley fourth order)",
        "cutoff_hz": 250.0,
        "q": 1.0 / math.sqrt(2.0),
        "sections": 2,
    },
    "additional_reflection_gain_db": 0.0,
    "output_length_samples": 8192,
    "nfft": 65536,
}


def early_window(length, peak, sample_rate):
    """Return a smooth reflection-only window positioned relative to peak."""
    definition = DESIGN["early_window"]
    offsets = {
        key: round(value * 1e-3 * sample_rate)
        for key, value in definition.items()
    }
    start = min(length, peak + offsets["fade_in_start_ms"])
    full_start = min(length, peak + offsets["full_level_start_ms"])
    full_end = min(length, peak + offsets["full_level_end_ms"])
    end = min(length, peak + offsets["fade_out_end_ms"] + 1)
    if not start < full_start <= full_end < end:
        raise ValueError("Early-reflection window is empty or out of order")

    window = np.zeros(length, dtype=np.float64)
    phase = np.linspace(0.0, math.pi, full_start - start, endpoint=False)
    window[start:full_start] = 0.5 - 0.5 * np.cos(phase)
    window[full_start:full_end] = 1.0
    phase = np.linspace(0.0, math.pi, end - full_end, endpoint=True)
    window[full_end:end] = 0.5 + 0.5 * np.cos(phase)
    return window


def rbj_highpass_coefficients(sample_rate, cutoff, q):
    omega = 2.0 * math.pi * cutoff / sample_rate
    cosine = math.cos(omega)
    alpha = math.sin(omega) / (2.0 * q)
    a0 = 1.0 + alpha
    return (
        np.array(
            [(1.0 + cosine) / 2.0, -(1.0 + cosine), (1.0 + cosine) / 2.0]
        )
        / a0,
        np.array([1.0, -2.0 * cosine / a0, (1.0 - alpha) / a0]),
    )


def apply_biquad(values, numerator, denominator):
    """Apply one causal normalized biquad without a SciPy dependency."""
    output = np.zeros_like(values, dtype=np.float64)
    x1 = x2 = y1 = y2 = 0.0
    for index, value in enumerate(values):
        result = (
            numerator[0] * value
            + numerator[1] * x1
            + numerator[2] * x2
            - denominator[1] * y1
            - denominator[2] * y2
        )
        output[index] = result
        x2, x1 = x1, value
        y2, y1 = y1, result
    return output


def shift_relative_to_peak(values, source_peak, destination_peak, output_length):
    """Move a path so its source peak lands on the theoretical direct peak."""
    result = np.zeros(output_length, dtype=np.float64)
    shift = destination_peak - source_peak
    source_start = max(0, -shift)
    source_end = min(len(values), output_length - shift)
    if source_end > source_start:
        result[source_start + shift : source_end + shift] = values[
            source_start:source_end
        ]
    return result


def smoothed_db(spectrum, frequencies, fraction=6):
    result = np.empty(len(frequencies), dtype=np.float64)
    result[1:] = np.asarray(
        log_smooth(frequencies[1:], db20(spectrum[1:]), fraction=fraction),
        dtype=np.float64,
    )
    result[0] = result[1]
    return result


def band_metrics(frequencies, candidate, reference, low, high):
    selected = (frequencies >= low) & (frequencies <= high)
    delta = candidate[selected] - reference[selected]
    return {
        "mean_delta_db": finite_float(np.mean(delta), 6),
        "rms_delta_db": finite_float(np.sqrt(np.mean(np.square(delta))), 6),
        "maximum_absolute_delta_db": finite_float(np.max(np.abs(delta)), 6),
    }


def hair_metric(frequencies, spectrum, low=500.0, high=8000.0):
    raw = db20(spectrum)
    smooth = smoothed_db(spectrum, frequencies, fraction=6)
    selected = (frequencies >= low) & (frequencies <= high)
    residual = raw[selected] - smooth[selected]
    return {
        "band_hz": [low, high],
        "rms_db": finite_float(np.sqrt(np.mean(np.square(residual))), 6),
        "peak_to_peak_db": finite_float(np.max(residual) - np.min(residual), 6),
    }


def energy_ratio_db(numerator, denominator):
    top = float(np.sum(np.square(numerator)))
    bottom = float(np.sum(np.square(denominator)))
    return finite_float(10.0 * math.log10(max(top / max(bottom, 1e-30), 1e-30)), 6)


def load_direct_summary(path):
    summary = json.loads(path.read_text(encoding="utf-8"))
    for side, direct_path in DIRECT_FILES.items():
        expected = summary["rendered_files"][side]["sha256"]
        actual = sha256(direct_path)
        if actual != expected:
            raise ValueError(
                f"Direct IR hash mismatch for {direct_path}: {actual} != {expected}"
            )
    return summary


def write_analysis_plots(output, frequencies, production, direct, reflections, candidate):
    colors = {"LL": COLORS["LL"], "LR": "#7c3aed", "RL": "#dc2626", "RR": "#059669"}
    audible = (frequencies >= 20.0) & (frequencies <= 20000.0)
    spectra = {
        group: {
            label: np.fft.rfft(values, DESIGN["nfft"])
            for label, values in paths.items()
        }
        for group, paths in (
            ("direct", direct),
            ("reflections", reflections),
            ("candidate", candidate),
            ("production", production),
        )
    }
    write_svg_plot(
        output / "candidate-magnitude-response.svg",
        "Candidate C: Synthetic Direct + Personal Early Room",
        [
            (label, frequencies[audible], db20(spectra["candidate"][label][audible]), colors[label])
            for label in PATH_ORDER
        ],
        "Frequency (Hz)",
        "Unsmoothed magnitude (dB)",
        20.0,
        20000.0,
        -75.0,
        10.0,
        [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000],
        x_scale="log",
    )
    label = "LL"
    write_svg_plot(
        output / "ll-direct-versus-candidate.svg",
        "LL Path: A, B, and C",
        [
            ("A production", frequencies[audible], db20(spectra["production"][label][audible]), "#dc2626"),
            ("B direct", frequencies[audible], db20(spectra["direct"][label][audible]), "#6b7280"),
            ("C with early room", frequencies[audible], db20(spectra["candidate"][label][audible]), "#2563eb"),
        ],
        "Frequency (Hz)",
        "Unsmoothed magnitude (dB)",
        20.0,
        20000.0,
        -65.0,
        5.0,
        [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000],
        x_scale="log",
    )
    limit = round(55e-3 * DESIGN["sample_rate_hz"])
    time_ms = np.arange(limit) / DESIGN["sample_rate_hz"] * 1000.0
    peak = max(float(np.max(np.abs(values[:limit]))) for values in reflections.values())
    write_svg_plot(
        output / "reflection-impulse-response.svg",
        "Personal Early-Reflection Branch",
        [
            (label, time_ms, reflections[label][:limit], colors[label])
            for label in PATH_ORDER
        ],
        "Time (ms)",
        "Amplitude",
        0.0,
        time_ms[-1],
        -peak * 1.1,
        peak * 1.1,
        [0, 4, 5, 10, 15, 20, 25, 30, 40, 50],
    )
    bass = (frequencies >= 20.0) & (frequencies <= 500.0)
    direct_mean = np.mean(
        [smoothed_db(spectra["direct"][path], frequencies) for path in PATH_ORDER],
        axis=0,
    )
    candidate_mean = np.mean(
        [smoothed_db(spectra["candidate"][path], frequencies) for path in PATH_ORDER],
        axis=0,
    )
    write_svg_plot(
        output / "bass-preservation.svg",
        "Mean Path Bass: B versus C (1/6 octave)",
        [
            ("B direct", frequencies[bass], direct_mean[bass], "#6b7280"),
            ("C with early room", frequencies[bass], candidate_mean[bass], "#2563eb"),
        ],
        "Frequency (Hz)",
        "Mean path magnitude (dB)",
        20.0,
        500.0,
        -45.0,
        -10.0,
        [20, 50, 80, 100, 200, 300, 500],
        x_scale="log",
    )


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ir-output", type=Path, default=OUTPUT_DIRECTORY)
    parser.add_argument("--analysis-output", type=Path, default=ANALYSIS_DIRECTORY)
    return parser.parse_args()


def main():
    args = parse_args()
    direct_summary = load_direct_summary(DIRECT_ANALYSIS)
    direct, sample_rate, direct_metadata = load_stereo_paths(DIRECT_FILES)
    production, production_rate, production_metadata = load_stereo_paths(ACTIVE_FILES)
    source, source_rate, source_metadata = load_stereo_paths(SOURCE_FILES)
    if (
        sample_rate != DESIGN["sample_rate_hz"]
        or source_rate != sample_rate
        or production_rate != sample_rate
    ):
        raise ValueError(f"Expected all inputs at {DESIGN['sample_rate_hz']} Hz")

    source_peaks = {label: int(np.argmax(np.abs(values))) for label, values in source.items()}
    direct_peaks = {label: int(np.argmax(np.abs(values))) for label, values in direct.items()}
    numerator, denominator = rbj_highpass_coefficients(
        sample_rate,
        DESIGN["reflection_highpass"]["cutoff_hz"],
        DESIGN["reflection_highpass"]["q"],
    )
    calibration_gain_db = direct_summary["personal_gain_adjustment_db"]
    total_reflection_gain_db = calibration_gain_db + DESIGN["additional_reflection_gain_db"]
    reflection_gain = 10.0 ** (total_reflection_gain_db / 20.0)

    windowed = {}
    reflections = {}
    candidate = {}
    for label in PATH_ORDER:
        windowed[label] = source[label] * early_window(
            len(source[label]), source_peaks[label], sample_rate
        )
        filtered = windowed[label]
        for _ in range(DESIGN["reflection_highpass"]["sections"]):
            filtered = apply_biquad(filtered, numerator, denominator)
        reflections[label] = shift_relative_to_peak(
            filtered * reflection_gain,
            source_peaks[label],
            direct_peaks[label],
            DESIGN["output_length_samples"],
        )
        candidate[label] = direct[label][: DESIGN["output_length_samples"]] + reflections[label]

    maximum = max(float(np.max(np.abs(values))) for values in candidate.values())
    if maximum >= 0.98:
        raise ValueError(f"Candidate IR peak {maximum:.4f} is too close to full scale")

    args.ir_output.mkdir(parents=True, exist_ok=True)
    stereo = {
        "left": np.column_stack([candidate["LL"], candidate["LR"]]),
        "right": np.column_stack([candidate["RL"], candidate["RR"]]),
    }
    rendered_files = {}
    for side, values in stereo.items():
        path = args.ir_output / OUTPUT_FILES[side]
        write_pcm24(path, values, sample_rate)
        rendered_files[side] = {
            "path": str(path.relative_to(REPOSITORY)),
            "sha256": sha256(path),
            "frames": len(values),
            "channels": 2,
            "sample_width_bits": 24,
            "peak_linear": finite_float(np.max(np.abs(values)), 9),
        }

    nfft = DESIGN["nfft"]
    frequencies = np.fft.rfftfreq(nfft, 1.0 / sample_rate)
    direct_spectra = {label: np.fft.rfft(values, nfft) for label, values in direct.items()}
    candidate_spectra = {label: np.fft.rfft(values, nfft) for label, values in candidate.items()}
    direct_smooth = {
        label: smoothed_db(values, frequencies) for label, values in direct_spectra.items()
    }
    candidate_smooth = {
        label: smoothed_db(values, frequencies) for label, values in candidate_spectra.items()
    }
    direct_common = np.mean([direct_smooth[label] for label in PATH_ORDER], axis=0)
    candidate_common = np.mean([candidate_smooth[label] for label in PATH_ORDER], axis=0)
    correlated = candidate_spectra["LL"] + candidate_spectra["RL"]
    correlated_right = candidate_spectra["LR"] + candidate_spectra["RR"]
    audible = (frequencies >= 20.0) & (frequencies <= 20000.0)
    maximum_correlated = max(
        float(np.max(np.abs(correlated[audible]))),
        float(np.max(np.abs(correlated_right[audible]))),
    )

    args.analysis_output.mkdir(parents=True, exist_ok=True)
    write_analysis_plots(
        args.analysis_output, frequencies, production, direct, reflections, candidate
    )
    production_spectra = {
        label: np.fft.rfft(values, nfft) for label, values in production.items()
    }
    paths = {}
    for label in PATH_ORDER:
        start = direct_peaks[label] + round(
            DESIGN["early_window"]["fade_in_start_ms"] * 1e-3 * sample_rate
        )
        paths[label] = {
            "source_peak_sample": source_peaks[label],
            "synthetic_direct_peak_sample": direct_peaks[label],
            "reflection_branch_first_nonzero_sample": int(
                np.flatnonzero(np.abs(reflections[label]) > 1e-12)[0]
            ),
            "nominal_reflection_start_sample": start,
            "reflection_to_direct_energy_db": energy_ratio_db(
                reflections[label], direct[label]
            ),
            "retained_windowed_raw_energy_percent": finite_float(
                100.0
                * np.sum(np.square(windowed[label]))
                / max(np.sum(np.square(source[label])), 1e-30),
                6,
            ),
            "hair": {
                "A_production": hair_metric(frequencies, production_spectra[label]),
                "B_direct": hair_metric(frequencies, direct_spectra[label]),
                "C_personal_early": hair_metric(frequencies, candidate_spectra[label]),
            },
        }
    summary = {
        "schema_version": 1,
        "status": "opt-in personal early-reflection prototype",
        "design": DESIGN,
        "direct_files": direct_metadata,
        "production_reference_files": production_metadata,
        "source_files": source_metadata,
        "direct_summary": str(DIRECT_ANALYSIS.relative_to(REPOSITORY)),
        "source_peak_samples_used_for_relative_timing_only": source_peaks,
        "measured_absolute_timing_retained": False,
        "measured_relative_reflection_timing_retained": True,
        "left_right_room_asymmetry_retained": True,
        "personal_direct_gain_adjustment_applied_to_reflections_db": finite_float(calibration_gain_db, 6),
        "total_reflection_gain_db": finite_float(total_reflection_gain_db, 6),
        "response_delta_C_minus_B": {
            "bass_20_80_hz": band_metrics(frequencies, candidate_common, direct_common, 20.0, 80.0),
            "handoff_80_200_hz": band_metrics(frequencies, candidate_common, direct_common, 80.0, 200.0),
            "upper_bass_200_300_hz": band_metrics(frequencies, candidate_common, direct_common, 200.0, 300.0),
            "room_band_300_10000_hz": band_metrics(frequencies, candidate_common, direct_common, 300.0, 10000.0),
        },
        "renderer_only_correlated_input_maximum_gain_db": finite_float(db20(maximum_correlated), 6),
        "paths": paths,
        "rendered_files": rendered_files,
        "plots": [
            "candidate-magnitude-response.svg",
            "ll-direct-versus-candidate.svg",
            "reflection-impulse-response.svg",
            "bass-preservation.svg",
        ],
    }
    (args.analysis_output / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    report = [
        "# Synthetic Reference Room: Personal Early-Reflection Prototype",
        "",
        "Candidate C keeps the synthetic direct renderer and adds only the personal four-path early-reflection field. It is opt-in and does not replace production.",
        "",
        "## Construction",
        "",
        "- Extract each raw BRIR path from +4 to +30 ms relative to its own direct peak, with smooth 0.75 ms fade-in and 5 ms fade-out windows.",
        "- Keep LL, LR, RL, and RR distinct so reflection direction and interaural differences survive.",
        "- Apply a causal fourth-order Linkwitz-Riley high-pass at 250 Hz to the reflection branch only. This prevents delayed room energy from changing B's clean bass while retaining the externalization band.",
        "- Align each reflection field to B's theoretical direct peak. Old absolute propagation time and latency are not retained.",
        "- Omit the measured late tail after 30 ms. This isolates whether early personal room structure restores externalization.",
        "",
        "## Listening question",
        "",
        "Does C move the phantom sources in front of the listener without reintroducing muddy bass or an obvious reverberant effect? If yes, the next version can replace these measured early arrivals with theory-derived reflection taps while preserving the useful binaural structure.",
    ]
    (args.analysis_output / "report.md").write_text(
        "\n".join(report) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
