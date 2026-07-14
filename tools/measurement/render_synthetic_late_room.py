#!/usr/bin/env python3
"""Render candidate D: candidate C plus the complementary measured late field."""

import argparse
import json
import math
from pathlib import Path

import numpy as np

from analyze_baseline import COLORS, finite_float, read_pcm_wav, sha256, write_svg_plot
from render_active_renderer import write_pcm24
from render_synthetic_direct import (
    ACTIVE_FILES,
    PATH_ORDER,
    REPOSITORY,
    SOURCE_FILES,
    db20,
    load_stereo_paths,
)
from render_synthetic_early_room import (
    ANALYSIS_DIRECTORY as EARLY_ANALYSIS_DIRECTORY,
    DESIGN as EARLY_DESIGN,
    OUTPUT_DIRECTORY as EARLY_OUTPUT_DIRECTORY,
    OUTPUT_FILES as EARLY_OUTPUT_FILES,
    apply_biquad,
    band_metrics,
    early_window,
    energy_ratio_db,
    hair_metric,
    rbj_highpass_coefficients,
    shift_relative_to_peak,
    smoothed_db,
)


EARLY_FILES = {
    side: EARLY_OUTPUT_DIRECTORY / filename
    for side, filename in EARLY_OUTPUT_FILES.items()
}
EARLY_ANALYSIS = EARLY_ANALYSIS_DIRECTORY / "summary.json"
OUTPUT_DIRECTORY = (
    REPOSITORY / "Synthetic Reference Room" / "IRs" / "personal-late-control"
)
ANALYSIS_DIRECTORY = (
    REPOSITORY
    / "measurements"
    / "synthetic-reference-room"
    / "personal-late-control"
    / "analysis"
)
OUTPUT_FILES = {
    "left": "Personal Late Room Left Speaker.wav",
    "right": "Personal Late Room Right Speaker.wav",
}
DESIGN = {
    "sample_rate_hz": 48000,
    "late_window": {
        "complementary_fade_start_ms": 25.0,
        "full_level_start_ms": 30.0,
        "end": "measured source end",
    },
    "reflection_highpass": dict(EARLY_DESIGN["reflection_highpass"]),
    "reflection_gain": "identical to candidate C",
    "output_length_samples": 32768,
    "nfft": 65536,
}
LISTENING_RESULT = {
    "date": "2026-07-14",
    "method": "informal sighted A/C/D comparison with unchanged downstream filters",
    "result": "D restored apparent monitor distance and sounded more spacious and preferable to A",
    "interpretation": "Sustained post-30 ms binaural decay is necessary in this system; A-like early comb density alone was insufficient",
    "limitations": "not blinded or independently level matched",
}
WINDOWS_BENCHMARK_RESULT = {
    "date": "2026-07-14",
    "commit": "9e0818f04c5ba9db781ccf0cfc6dfbef84919393",
    "device": "Output A1 Voicemeeter",
    "result": "three probes passed with expected renderer, WAV, and 2x2 routing loads; no clipping or configuration-error markers",
    "left_impulse_peak_dbfs": -25.065376,
    "right_impulse_peak_dbfs": -25.842562,
    "correlated_sweep_peak_dbfs": -4.844495,
    "single_core_cpu_percent_range": [0.60, 0.66],
    "capture_location": "temporary Windows evidence; not checked into the repository",
}


def late_window(length, peak, sample_rate):
    """Complement C's early fade from +25 ms, then retain the full tail."""
    early = early_window(length, peak, sample_rate)
    start = peak + round(
        DESIGN["late_window"]["complementary_fade_start_ms"]
        * 1e-3
        * sample_rate
    )
    if start >= length:
        raise ValueError("Late-field window begins outside the source IR")
    window = np.zeros(length, dtype=np.float64)
    window[start:] = 1.0 - early[start:]
    return window


def pad_to(values, length):
    if len(values) > length:
        raise ValueError("Cannot preserve a longer control in a shorter output")
    return np.pad(values, (0, length - len(values)))


def apply_reflection_highpass(values, sample_rate):
    definition = DESIGN["reflection_highpass"]
    numerator, denominator = rbj_highpass_coefficients(
        sample_rate, definition["cutoff_hz"], definition["q"]
    )
    filtered = values
    for _ in range(definition["sections"]):
        filtered = apply_biquad(filtered, numerator, denominator)
    return filtered


def load_verified_summary(path, files):
    summary = json.loads(path.read_text(encoding="utf-8"))
    for side, source_path in files.items():
        expected = summary["rendered_files"][side]["sha256"]
        actual = sha256(source_path)
        if actual != expected:
            raise ValueError(
                f"Input IR hash mismatch for {source_path}: {actual} != {expected}"
            )
    return summary


def energy_decay_db(values):
    energy = np.cumsum(np.square(values[::-1]), dtype=np.float64)[::-1]
    return 10.0 * np.log10(np.maximum(energy / max(energy[0], 1e-30), 1e-8))


def time_energy_distribution(values, peak, sample_rate):
    cuts = [
        0,
        min(len(values), peak + round(4e-3 * sample_rate)),
        min(len(values), peak + round(30e-3 * sample_rate)),
        min(len(values), peak + round(80e-3 * sample_rate)),
        len(values),
    ]
    labels = ("through_4_ms", "4_30_ms", "30_80_ms", "after_80_ms")
    return {
        label: energy_ratio_db(values[low:high], values)
        for label, low, high in zip(labels, cuts, cuts[1:])
    }


def first_difference(left, right):
    indices = np.flatnonzero(left != right)
    return int(indices[0]) if len(indices) else None


def write_analysis_plots(output, frequencies, production, early, late, candidate):
    colors = {
        "LL": COLORS["LL"],
        "LR": "#7c3aed",
        "RL": "#dc2626",
        "RR": "#059669",
    }
    spectra = {
        group: {
            label: np.fft.rfft(values, DESIGN["nfft"])
            for label, values in paths.items()
        }
        for group, paths in (
            ("production", production),
            ("early", early),
            ("candidate", candidate),
        )
    }
    audible = (frequencies >= 20.0) & (frequencies <= 20000.0)
    label = "LL"
    write_svg_plot(
        output / "ll-a-c-d-magnitude.svg",
        "LL Path: A Production, C Early, and D Late Control",
        [
            ("A production", frequencies[audible], db20(spectra["production"][label][audible]), "#dc2626"),
            ("C early only", frequencies[audible], db20(spectra["early"][label][audible]), "#6b7280"),
            ("D with late field", frequencies[audible], db20(spectra["candidate"][label][audible]), "#2563eb"),
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

    limit = min(DESIGN["output_length_samples"], round(300e-3 * DESIGN["sample_rate_hz"]))
    stride = 3
    samples = np.arange(0, limit, stride)
    time_ms = samples / DESIGN["sample_rate_hz"] * 1000.0
    peak = max(float(np.max(np.abs(values[:limit]))) for values in late.values())
    write_svg_plot(
        output / "late-field-impulse-response.svg",
        "Measured Late-Field Addition",
        [
            (label, time_ms, late[label][samples], colors[label])
            for label in PATH_ORDER
        ],
        "Time (ms)",
        "Amplitude",
        0.0,
        time_ms[-1],
        -peak * 1.1,
        peak * 1.1,
        [0, 25, 30, 50, 80, 120, 180, 240, 300],
    )

    highpassed = {
        "A production": apply_reflection_highpass(production[label], DESIGN["sample_rate_hz"]),
        "C early only": apply_reflection_highpass(early[label], DESIGN["sample_rate_hz"]),
        "D with late field": apply_reflection_highpass(candidate[label], DESIGN["sample_rate_hz"]),
    }
    length = max(len(values) for values in highpassed.values())
    decay_time_ms = np.arange(length) / DESIGN["sample_rate_hz"] * 1000.0
    stride = 16
    decay_colors = {
        "A production": "#dc2626",
        "C early only": "#6b7280",
        "D with late field": "#2563eb",
    }
    write_svg_plot(
        output / "ll-energy-decay.svg",
        "LL Energy Decay above 250 Hz",
        [
            (
                name,
                decay_time_ms[::stride],
                energy_decay_db(pad_to(values, length))[::stride],
                decay_colors[name],
            )
            for name, values in highpassed.items()
        ],
        "Time (ms)",
        "Remaining energy (dB)",
        0.0,
        decay_time_ms[-1],
        -80.0,
        0.0,
        [0, 30, 80, 150, 250, 400, 550, 680],
    )

    bass = (frequencies >= 20.0) & (frequencies <= 500.0)
    early_mean = np.mean(
        [smoothed_db(spectra["early"][path], frequencies) for path in PATH_ORDER],
        axis=0,
    )
    candidate_mean = np.mean(
        [smoothed_db(spectra["candidate"][path], frequencies) for path in PATH_ORDER],
        axis=0,
    )
    write_svg_plot(
        output / "bass-preservation.svg",
        "Mean Path Bass: C versus D (1/6 octave)",
        [
            ("C early only", frequencies[bass], early_mean[bass], "#6b7280"),
            ("D with late field", frequencies[bass], candidate_mean[bass], "#2563eb"),
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
    early_summary = load_verified_summary(EARLY_ANALYSIS, EARLY_FILES)
    early, sample_rate, early_metadata = load_stereo_paths(EARLY_FILES)
    source, source_rate, source_metadata = load_stereo_paths(SOURCE_FILES)
    production, production_rate, production_metadata = load_stereo_paths(ACTIVE_FILES)
    if (
        sample_rate != DESIGN["sample_rate_hz"]
        or source_rate != sample_rate
        or production_rate != sample_rate
    ):
        raise ValueError(f"Expected all inputs at {DESIGN['sample_rate_hz']} Hz")
    if early_summary["design"]["reflection_highpass"] != DESIGN["reflection_highpass"]:
        raise ValueError("D must use exactly candidate C's reflection high-pass")

    output_length = DESIGN["output_length_samples"]
    source_peaks = {label: int(np.argmax(np.abs(values))) for label, values in source.items()}
    direct_peaks = {
        label: int(early_summary["paths"][label]["synthetic_direct_peak_sample"])
        for label in PATH_ORDER
    }
    reflection_gain_db = float(early_summary["total_reflection_gain_db"])
    reflection_gain = 10.0 ** (reflection_gain_db / 20.0)
    early_padded = {label: pad_to(values, output_length) for label, values in early.items()}

    late_inputs = {}
    late = {}
    candidate = {}
    for label in PATH_ORDER:
        late_inputs[label] = source[label] * late_window(
            len(source[label]), source_peaks[label], sample_rate
        )
        filtered = apply_reflection_highpass(late_inputs[label], sample_rate)
        late[label] = shift_relative_to_peak(
            filtered * reflection_gain,
            source_peaks[label],
            direct_peaks[label],
            output_length,
        )
        candidate[label] = early_padded[label] + late[label]

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

    rendered, rendered_rate, _ = load_stereo_paths(
        {side: args.ir_output / filename for side, filename in OUTPUT_FILES.items()}
    )
    if rendered_rate != sample_rate:
        raise ValueError("Rendered D sample rate changed unexpectedly")

    nfft = DESIGN["nfft"]
    frequencies = np.fft.rfftfreq(nfft, 1.0 / sample_rate)
    spectra = {
        group: {label: np.fft.rfft(values, nfft) for label, values in paths.items()}
        for group, paths in (
            ("production", production),
            ("early", early_padded),
            ("candidate", candidate),
        )
    }
    smooth = {
        group: {label: smoothed_db(values, frequencies) for label, values in paths.items()}
        for group, paths in spectra.items()
    }
    early_common = np.mean([smooth["early"][label] for label in PATH_ORDER], axis=0)
    candidate_common = np.mean([smooth["candidate"][label] for label in PATH_ORDER], axis=0)
    correlated_left = spectra["candidate"]["LL"] + spectra["candidate"]["RL"]
    correlated_right = spectra["candidate"]["LR"] + spectra["candidate"]["RR"]
    production_correlated_left = (
        spectra["production"]["LL"] + spectra["production"]["RL"]
    )
    production_correlated_right = (
        spectra["production"]["LR"] + spectra["production"]["RR"]
    )
    audible = (frequencies >= 20.0) & (frequencies <= 20000.0)
    maximum_correlated = max(
        float(np.max(np.abs(correlated_left[audible]))),
        float(np.max(np.abs(correlated_right[audible]))),
    )
    maximum_production_correlated = max(
        float(np.max(np.abs(production_correlated_left[audible]))),
        float(np.max(np.abs(production_correlated_right[audible]))),
    )

    args.analysis_output.mkdir(parents=True, exist_ok=True)
    write_analysis_plots(
        args.analysis_output, frequencies, production, early_padded, late, candidate
    )

    paths = {}
    for label in PATH_ORDER:
        nominal_start = direct_peaks[label] + round(25e-3 * sample_rate)
        differences = np.abs(rendered[label] - early_padded[label])
        paths[label] = {
            "source_peak_sample": source_peaks[label],
            "synthetic_direct_peak_sample": direct_peaks[label],
            "nominal_late_fade_start_sample": nominal_start,
            "late_branch_first_nonzero_sample": int(
                np.flatnonzero(np.abs(late[label]) > 1e-12)[0]
            ),
            "rendered_first_difference_from_C_sample": first_difference(
                rendered[label], early_padded[label]
            ),
            "maximum_absolute_difference_from_C_through_25_ms": finite_float(
                np.max(differences[: nominal_start + 1]), 12
            ),
            "late_to_C_energy_db": energy_ratio_db(late[label], early_padded[label]),
            "late_input_raw_energy_percent": finite_float(
                100.0
                * np.sum(np.square(late_inputs[label]))
                / max(np.sum(np.square(source[label])), 1e-30),
                6,
            ),
            "energy_distribution_above_250_hz": {
                "A_production": time_energy_distribution(
                    apply_reflection_highpass(production[label], sample_rate),
                    int(np.argmax(np.abs(production[label]))),
                    sample_rate,
                ),
                "C_early_only": time_energy_distribution(
                    apply_reflection_highpass(early_padded[label], sample_rate),
                    direct_peaks[label],
                    sample_rate,
                ),
                "D_late_control": time_energy_distribution(
                    apply_reflection_highpass(candidate[label], sample_rate),
                    direct_peaks[label],
                    sample_rate,
                ),
            },
            "hair": {
                "A_production": hair_metric(frequencies, spectra["production"][label]),
                "C_early_only": hair_metric(frequencies, spectra["early"][label]),
                "D_late_control": hair_metric(frequencies, spectra["candidate"][label]),
            },
        }

    summary = {
        "schema_version": 1,
        "status": "opt-in measured late-field diagnostic",
        "listening_result": LISTENING_RESULT,
        "windows_benchmark_result": WINDOWS_BENCHMARK_RESULT,
        "design": DESIGN,
        "candidate_C_files": early_metadata,
        "candidate_C_summary": str(EARLY_ANALYSIS.relative_to(REPOSITORY)),
        "source_files": source_metadata,
        "production_reference_files": production_metadata,
        "measured_absolute_timing_retained": False,
        "measured_relative_late_timing_retained": True,
        "left_right_room_asymmetry_retained": True,
        "reflection_gain_db": finite_float(reflection_gain_db, 6),
        "response_delta_D_minus_C": {
            "bass_20_80_hz": band_metrics(frequencies, candidate_common, early_common, 20.0, 80.0),
            "handoff_80_200_hz": band_metrics(frequencies, candidate_common, early_common, 80.0, 200.0),
            "upper_bass_200_300_hz": band_metrics(frequencies, candidate_common, early_common, 200.0, 300.0),
            "room_band_300_10000_hz": band_metrics(frequencies, candidate_common, early_common, 300.0, 10000.0),
        },
        "renderer_only_correlated_input_maximum_gain_db": {
            "A_production": finite_float(db20(maximum_production_correlated), 6),
            "D_late_control": finite_float(db20(maximum_correlated), 6),
        },
        "paths": paths,
        "rendered_files": rendered_files,
        "plots": [
            "ll-a-c-d-magnitude.svg",
            "late-field-impulse-response.svg",
            "ll-energy-decay.svg",
            "bass-preservation.svg",
        ],
    }
    (args.analysis_output / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    report = [
        "# Synthetic Reference Room: Measured Late-Field Diagnostic",
        "",
        "Candidate D changes one audible variable relative to C: it restores the measured room field after the early-reflection window. It is now the successful hybrid reference, not the proposed final synthetic room.",
        "",
        "## Construction",
        "",
        "- Keep candidate C unchanged through +25 ms relative to each theoretical direct peak.",
        "- Add a window exactly complementary to C's fade from +25 to +30 ms, then retain the complete measured tail.",
        "- Keep all four LL, LR, RL, and RR late paths distinct for this diagnostic.",
        "- Reuse C's fourth-order 250 Hz reflection high-pass, gain, and relative alignment without normalization.",
        "- Preserve C's direct arrival, clean bass, early field, and downstream processing.",
        "",
        "## Interpretation",
        "",
        "Informal sighted listening with unchanged downstream filters found that D restored apparent monitor distance and sounded more spacious and preferable to A. The comparison was not blinded or independently level matched. Windows Benchmark subsequently passed all three probes with no clipping or configuration errors.",
        "",
        "This establishes sustained post-30 ms binaural decay as necessary in this system; A-like early comb density alone was insufficient. The next renderer should keep D's direct sound, bass, and measured early field while replacing only this measured tail with a clean synthetic binaural late field.",
    ]
    (args.analysis_output / "report.md").write_text(
        "\n".join(report) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
