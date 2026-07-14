#!/usr/bin/env python3
"""Render the opt-in personal direct-only synthetic binaural renderer."""

import argparse
import json
import math
from pathlib import Path

import numpy as np

from analyze_baseline import COLORS, finite_float, read_pcm_wav, sha256, write_svg_plot
from analyze_bass_branches import log_smooth
from explore_minimum_latency_renderer import minimum_phase_spectrum
from render_active_renderer import write_pcm24


REPOSITORY = Path(__file__).resolve().parents[2]
SOURCE_DIRECTORY = REPOSITORY / "JBL M2 Binaural Convolution" / "IRs"
OUTPUT_DIRECTORY = REPOSITORY / "Synthetic Reference Room" / "IRs" / "direct"
ANALYSIS_DIRECTORY = (
    REPOSITORY / "measurements" / "synthetic-reference-room" / "direct-only" / "analysis"
)
SOURCE_FILES = {
    "left": SOURCE_DIRECTORY / "JBL LSR305 LL 4_LR 4 5-500.wav",
    "right": SOURCE_DIRECTORY / "JBL LSR305 RL 4_RR 4 5-500.wav",
}
ACTIVE_FILES = {
    "left": SOURCE_DIRECTORY / "active" / "Left Speaker to Both Ears.wav",
    "right": SOURCE_DIRECTORY / "active" / "Right Speaker to Both Ears.wav",
}
OUTPUT_FILES = {
    "left": "Personal Direct Left Speaker.wav",
    "right": "Personal Direct Right Speaker.wav",
}
PATH_CHANNELS = {
    "left": (("LL", 0), ("LR", 1)),
    "right": (("RL", 0), ("RR", 1)),
}
PATH_ORDER = ("LL", "LR", "RL", "RR")
DESIGN = {
    "sample_rate_hz": 48000,
    "direct_window": {
        "pre_peak_start_ms": -3.0,
        "pre_peak_full_level_ms": -1.75,
        "post_peak_end_ms": 4.0,
        "post_peak_taper_ms": 0.5,
    },
    "magnitude_regularization": {
        "personal_fractional_octave": 12,
        "upper_treble_fractional_octave": 3,
        "upper_treble_blend_hz": [10000.0, 16000.0],
        "synthetic_bass_end_hz": 300.0,
        "personal_direct_start_hz": 700.0,
        "gain_match_hz": [500.0, 1000.0],
        "nyquist_rolloff_start_hz": 18000.0,
        "nyquist_rolloff_db": -24.0,
        "protective_highpass_hz": 8.0,
        "protective_highpass_order": 2,
    },
    "timing_model": {
        "speaker_azimuth_degrees": 30.0,
        "head_radius_m": 0.0875,
        "speed_of_sound_m_s": 343.0,
        "fractional_delay_order": 7,
    },
    "nfft": 65536,
    "output_length_samples": 8192,
}


def smoothstep(values, low, high):
    normalized = np.clip((values - low) / (high - low), 0.0, 1.0)
    return normalized * normalized * (3.0 - 2.0 * normalized)


def db20(values, floor=-160.0):
    return np.maximum(floor, 20.0 * np.log10(np.maximum(np.abs(values), 1e-12)))


def direct_window(length, peak, sample_rate):
    definition = DESIGN["direct_window"]
    window = np.zeros(length, dtype=np.float64)
    left_start = max(
        0, peak + round(definition["pre_peak_start_ms"] * 1e-3 * sample_rate)
    )
    left_full = max(
        left_start + 1,
        peak + round(definition["pre_peak_full_level_ms"] * 1e-3 * sample_rate),
    )
    right_end = min(
        length,
        peak + round(definition["post_peak_end_ms"] * 1e-3 * sample_rate) + 1,
    )
    right_taper = max(
        1, round(definition["post_peak_taper_ms"] * 1e-3 * sample_rate)
    )
    right_full = max(peak + 1, right_end - right_taper)
    phase = np.linspace(0.0, math.pi, left_full - left_start, endpoint=False)
    window[left_start:left_full] = 0.5 - 0.5 * np.cos(phase)
    window[left_full:right_full] = 1.0
    phase = np.linspace(0.0, math.pi, right_end - right_full, endpoint=True)
    window[right_full:right_end] = 0.5 + 0.5 * np.cos(phase)
    return window


def load_stereo_paths(files):
    paths = {}
    sample_rate = None
    metadata = {}
    for side, path in files.items():
        loaded = read_pcm_wav(path)
        if loaded["channels"] != 2:
            raise ValueError(f"Expected a stereo WAV: {path}")
        if sample_rate is None:
            sample_rate = loaded["sample_rate"]
        elif loaded["sample_rate"] != sample_rate:
            raise ValueError("Input sample rates do not match")
        for label, channel in PATH_CHANNELS[side]:
            paths[label] = loaded["samples"][:, channel]
        try:
            display_path = str(path.relative_to(REPOSITORY))
        except ValueError:
            display_path = str(path)
        metadata[side] = {
            "path": display_path,
            "sha256": sha256(path),
            "frames": loaded["frame_count"],
            "sample_width_bits": loaded["sample_width_bits"],
        }
    return paths, sample_rate, metadata


def smoothed_magnitude_db(spectrum, frequencies, fraction):
    result = np.empty(len(frequencies), dtype=np.float64)
    result[1:] = np.asarray(
        log_smooth(frequencies[1:], db20(spectrum[1:]), fraction=fraction),
        dtype=np.float64,
    )
    result[0] = result[1]
    return result


def theoretical_itd_samples(sample_rate):
    timing = DESIGN["timing_model"]
    angle = math.radians(timing["speaker_azimuth_degrees"])
    seconds = timing["head_radius_m"] / timing["speed_of_sound_m_s"] * (
        math.sin(angle) + angle
    )
    return seconds * sample_rate


def lagrange_fractional_delay(total_delay, order):
    """Return a causal Lagrange FIR whose group delay is total_delay samples."""
    base = math.floor(total_delay) - order // 2
    if base < 0:
        raise ValueError("The requested delay is too short for this FIR order")
    local_delay = total_delay - base
    coefficients = np.empty(order + 1, dtype=np.float64)
    for tap in range(order + 1):
        coefficient = 1.0
        for other in range(order + 1):
            if tap != other:
                coefficient *= (local_delay - other) / (tap - other)
        coefficients[tap] = coefficient
    result = np.zeros(base + order + 1, dtype=np.float64)
    result[base:] = coefficients
    return result


def protective_highpass_db(frequencies, cutoff, order):
    result = np.full(len(frequencies), -160.0, dtype=np.float64)
    positive = frequencies > 0.0
    ratio = cutoff / frequencies[positive]
    magnitude = 1.0 / np.sqrt(1.0 + np.power(ratio, 2 * order))
    result[positive] = db20(magnitude)
    return result


def band_mean(frequencies, values, low, high):
    selected = (frequencies >= low) & (frequencies <= high)
    return float(np.mean(values[selected]))


def tail_energy_db(values, output_length):
    total = float(np.sum(np.square(values)))
    tail = float(np.sum(np.square(values[output_length:])))
    return 10.0 * math.log10(max(tail / max(total, 1e-30), 1e-30))


def write_analysis_plots(
    output, frequencies, response_db, calibration_db, impulses, active_db
):
    band = (frequencies >= 20.0) & (frequencies <= 20000.0)
    colors = {"LL": COLORS["LL"], "LR": "#60a5fa", "RL": "#f59e0b", "RR": "#dc2626"}
    write_svg_plot(
        output / "magnitude-response.svg",
        "Synthetic Personal Direct Renderer",
        [
            (label, frequencies[band], response_db[label][band], colors[label])
            for label in PATH_ORDER
        ],
        "Frequency (Hz)",
        "Magnitude (dB)",
        20.0,
        20000.0,
        -65.0,
        5.0,
        [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000],
        x_scale="log",
    )
    ild = response_db["LL"] - response_db["LR"]
    write_svg_plot(
        output / "ild-response.svg",
        "Synthetic Ipsi-minus-Contra Magnitude",
        [("Mirrored speakers", frequencies[band], ild[band], "#2563eb")],
        "Frequency (Hz)",
        "Ipsilateral minus contralateral level (dB)",
        20.0,
        20000.0,
        -2.0,
        28.0,
        [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000],
        x_scale="log",
    )
    limit = min(len(next(iter(impulses.values()))), 256)
    time_ms = np.arange(limit) / DESIGN["sample_rate_hz"] * 1000.0
    peak = max(float(np.max(np.abs(values[:limit]))) for values in impulses.values())
    write_svg_plot(
        output / "impulse-response.svg",
        "Synthetic Direct Impulses (first 256 samples)",
        [
            (label, time_ms, impulses[label][:limit], colors[label])
            for label in PATH_ORDER
        ],
        "Time (ms)",
        "Amplitude",
        0.0,
        time_ms[-1],
        -peak * 1.1,
        peak * 1.1,
        [0, 1, 2, 3, 4, 5],
    )
    active_common = np.mean([active_db[label] for label in PATH_ORDER], axis=0)
    synthetic_common = np.mean(
        [calibration_db[label] for label in PATH_ORDER], axis=0
    )
    write_svg_plot(
        output / "bass-calibration.svg",
        "Bass Quantity Calibration",
        [
            ("Accepted renderer", frequencies[band], active_common[band], "#6b7280"),
            ("Synthetic direct", frequencies[band], synthetic_common[band], "#2563eb"),
        ],
        "Frequency (Hz)",
        "Mean path magnitude (dB)",
        20.0,
        1000.0,
        -45.0,
        -10.0,
        [20, 50, 100, 200, 300, 500, 700, 1000],
        x_scale="log",
    )


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ir-output", type=Path, default=OUTPUT_DIRECTORY)
    parser.add_argument("--analysis-output", type=Path, default=ANALYSIS_DIRECTORY)
    return parser.parse_args()


def main():
    args = parse_args()
    source, sample_rate, source_metadata = load_stereo_paths(SOURCE_FILES)
    active, active_rate, active_metadata = load_stereo_paths(ACTIVE_FILES)
    if sample_rate != DESIGN["sample_rate_hz"] or active_rate != sample_rate:
        raise ValueError(f"Expected all inputs at {DESIGN['sample_rate_hz']} Hz")

    nfft = DESIGN["nfft"]
    frequencies = np.fft.rfftfreq(nfft, 1.0 / sample_rate)
    regularization = DESIGN["magnitude_regularization"]
    source_db = {}
    source_peaks = {}
    for label, values in source.items():
        peak = int(np.argmax(np.abs(values)))
        source_peaks[label] = peak
        windowed = values * direct_window(len(values), peak, sample_rate)
        spectrum = np.fft.rfft(windowed, nfft)
        personal = smoothed_magnitude_db(
            spectrum, frequencies, regularization["personal_fractional_octave"]
        )
        upper = smoothed_magnitude_db(
            spectrum, frequencies, regularization["upper_treble_fractional_octave"]
        )
        upper_blend = smoothstep(
            frequencies, *regularization["upper_treble_blend_hz"]
        )
        source_db[label] = personal * (1.0 - upper_blend) + upper * upper_blend

    active_db = {}
    for label, values in active.items():
        spectrum = np.fft.rfft(values, nfft)
        active_db[label] = smoothed_magnitude_db(spectrum, frequencies, 6)

    ipsi_personal = 0.5 * (source_db["LL"] + source_db["RR"])
    contra_personal = 0.5 * (source_db["LR"] + source_db["RL"])
    active_ipsi = 0.5 * (active_db["LL"] + active_db["RR"])
    gain_low, gain_high = regularization["gain_match_hz"]
    gain_adjustment_db = band_mean(
        frequencies, active_ipsi, gain_low, gain_high
    ) - band_mean(frequencies, ipsi_personal, gain_low, gain_high)
    ipsi_personal += gain_adjustment_db
    contra_personal += gain_adjustment_db

    active_common_low = np.mean([active_db[label] for label in PATH_ORDER], axis=0)
    personal_blend = smoothstep(
        frequencies,
        regularization["synthetic_bass_end_hz"],
        regularization["personal_direct_start_hz"],
    )
    ipsi_db = active_common_low * (1.0 - personal_blend) + ipsi_personal * personal_blend
    contra_db = active_common_low * (1.0 - personal_blend) + contra_personal * personal_blend

    highpass = protective_highpass_db(
        frequencies,
        regularization["protective_highpass_hz"],
        regularization["protective_highpass_order"],
    )
    treble_rolloff = regularization["nyquist_rolloff_db"] * smoothstep(
        frequencies,
        regularization["nyquist_rolloff_start_hz"],
        sample_rate / 2.0,
    )
    ipsi_db += highpass + treble_rolloff
    contra_db += highpass + treble_rolloff

    ipsi_full = np.fft.irfft(
        minimum_phase_spectrum(np.power(10.0, ipsi_db / 20.0), nfft), nfft
    )
    contra_minimum_phase = np.fft.irfft(
        minimum_phase_spectrum(np.power(10.0, contra_db / 20.0), nfft), nfft
    )
    itd_samples = theoretical_itd_samples(sample_rate)
    delay_filter = lagrange_fractional_delay(
        itd_samples, DESIGN["timing_model"]["fractional_delay_order"]
    )
    contra_full = np.convolve(contra_minimum_phase, delay_filter)
    output_length = DESIGN["output_length_samples"]
    ipsi = ipsi_full[:output_length]
    contra = contra_full[:output_length]
    impulses = {"LL": ipsi, "LR": contra, "RL": contra.copy(), "RR": ipsi.copy()}

    maximum = max(float(np.max(np.abs(values))) for values in impulses.values())
    if maximum >= 0.98:
        raise ValueError(f"Synthetic IR peak {maximum:.4f} is too close to full scale")

    args.ir_output.mkdir(parents=True, exist_ok=True)
    stereo = {
        "left": np.column_stack([impulses["LL"], impulses["LR"]]),
        "right": np.column_stack([impulses["RL"], impulses["RR"]]),
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
            "peak_linear": finite_float(float(np.max(np.abs(values))), 9),
        }

    response_db = {}
    calibration_db = {}
    for label, values in impulses.items():
        spectrum = np.fft.rfft(values, nfft)
        response_db[label] = smoothed_magnitude_db(
            spectrum, frequencies, 24
        )
        calibration_db[label] = smoothed_magnitude_db(
            spectrum, frequencies, 6
        )
    args.analysis_output.mkdir(parents=True, exist_ok=True)
    write_analysis_plots(
        args.analysis_output,
        frequencies,
        response_db,
        calibration_db,
        impulses,
        active_db,
    )
    delay_frequency = np.linspace(0.0, sample_rate / 2.0, 4097)
    delay_response = np.array(
        [
            np.sum(delay_filter * np.exp(-2j * np.pi * frequency * np.arange(len(delay_filter)) / sample_rate))
            for frequency in delay_frequency
        ]
    )
    correlated_spectrum = np.fft.rfft(ipsi, nfft) + np.fft.rfft(contra, nfft)
    audible = (frequencies >= 20.0) & (frequencies <= 20000.0)
    audible_indices = np.flatnonzero(audible)
    correlated_index = audible_indices[
        int(np.argmax(np.abs(correlated_spectrum[audible])))
    ]
    active_common = np.mean([active_db[label] for label in PATH_ORDER], axis=0)
    synthetic_common = np.mean(
        [calibration_db[label] for label in PATH_ORDER], axis=0
    )
    bass = (frequencies >= 20.0) & (frequencies <= 300.0)
    bass_delta = synthetic_common[bass] - active_common[bass]
    summary = {
        "schema_version": 1,
        "status": "opt-in direct-only prototype",
        "design": DESIGN,
        "source_files": source_metadata,
        "bass_calibration_files": active_metadata,
        "source_peak_samples_used_for_windowing_only": source_peaks,
        "measured_timing_retained": False,
        "left_right_asymmetry_retained": False,
        "personal_gain_adjustment_db": finite_float(gain_adjustment_db, 6),
        "bass_quantity_match_20_300_hz": {
            "mean_delta_db": finite_float(np.mean(bass_delta), 6),
            "rms_delta_db": finite_float(
                np.sqrt(np.mean(np.square(bass_delta))), 6
            ),
            "maximum_absolute_delta_db": finite_float(
                np.max(np.abs(bass_delta)), 6
            ),
        },
        "renderer_only_correlated_input_headroom": {
            "maximum_gain_db": finite_float(
                db20(correlated_spectrum[correlated_index]), 6
            ),
            "frequency_hz": finite_float(frequencies[correlated_index], 6),
            "note": "Excludes downstream target, headphone, and balance filters.",
        },
        "theoretical_itd": {
            "samples": finite_float(itd_samples, 9),
            "milliseconds": finite_float(itd_samples / sample_rate * 1000.0, 9),
            "fractional_delay_fir": [finite_float(value, 12) for value in delay_filter],
            "magnitude_error_db": {
                str(frequency): finite_float(
                    db20(delay_response[np.argmin(np.abs(delay_frequency - frequency))]), 6
                )
                for frequency in (1000.0, 4000.0, 8000.0, 12000.0, 16000.0)
            },
        },
        "paths": {
            label: {
                "peak_sample": int(np.argmax(np.abs(values))),
                "peak_time_ms": finite_float(
                    np.argmax(np.abs(values)) / sample_rate * 1000.0, 6
                ),
                "peak_linear": finite_float(np.max(np.abs(values)), 9),
                "tail_energy_beyond_output_db": finite_float(
                    tail_energy_db(ipsi_full if label in ("LL", "RR") else contra_full, output_length),
                    6,
                ),
            }
            for label, values in impulses.items()
        },
        "symmetry": {
            "LL_equals_RR": bool(np.array_equal(impulses["LL"], impulses["RR"])),
            "LR_equals_RL": bool(np.array_equal(impulses["LR"], impulses["RL"])),
        },
        "rendered_files": rendered_files,
        "plots": [
            "magnitude-response.svg",
            "ild-response.svg",
            "impulse-response.svg",
            "bass-calibration.svg",
        ],
    }
    (args.analysis_output / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    report = [
        "# Synthetic Reference Room: Personal Direct Prototype",
        "",
        "This opt-in control renderer contains a symmetrized personal direct HRTF and no measured room tail. It is not the production default.",
        "",
        "## Construction",
        "",
        "- Smoothly window each measured path from −3 ms through +4 ms around its own direct peak; the first repeatable room cluster starts after +5 ms.",
        "- Geometrically average LL/RR and LR/RL magnitudes to remove unverified left/right measurement asymmetry.",
        "- Use the accepted renderer only as a broad sub-300 Hz magnitude reference so bass quantity does not become an A/B confound.",
        "- Reconstruct causal minimum-phase direct and cross filters; no measured arrival time survives.",
        f"- Delay only the contralateral path by {itd_samples:.3f} samples ({itd_samples / sample_rate * 1000.0:.3f} ms), calculated for a ±30° speaker angle and 8.75 cm head radius.",
        "",
        "## Interpretation",
        "",
        "This version is expected to sound drier and less externalized than the production renderer. Its purpose is to validate the personal direct-HRTF anchor and theoretical timing before synthetic early reflections and a shared late field are added.",
    ]
    (args.analysis_output / "report.md").write_text(
        "\n".join(report) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
