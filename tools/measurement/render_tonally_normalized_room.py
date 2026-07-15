#!/usr/bin/env python3
"""Render candidate I: H with 200 Hz-1 kHz binaural tonal normalization."""

import argparse
import json
import math
from pathlib import Path

import numpy as np

from analyze_baseline import COLORS, finite_float, sha256, write_svg_plot
from analyze_bass_branches import log_smooth
from explore_minimum_latency_renderer import minimum_phase_spectrum
from render_active_renderer import write_pcm24
from render_idealized_treated_room import (
    ANALYSIS_DIRECTORY as H_ANALYSIS_DIRECTORY,
    DESIGN as H_DESIGN,
    OUTPUT_DIRECTORY as H_OUTPUT_DIRECTORY,
    OUTPUT_FILES as H_OUTPUT_FILES,
)
from render_synthetic_direct import PATH_ORDER, REPOSITORY, load_stereo_paths
from render_synthetic_early_room import DIRECT_ANALYSIS, DIRECT_FILES, band_metrics
from render_synthetic_late_room import pad_to
from render_theoretical_early_room import load_verified_inputs


H_FILES = {
    side: H_OUTPUT_DIRECTORY / filename
    for side, filename in H_OUTPUT_FILES.items()
}
OUTPUT_DIRECTORY = (
    REPOSITORY / "Synthetic Reference Room" / "IRs" / "tonally-normalized"
)
ANALYSIS_DIRECTORY = (
    REPOSITORY
    / "measurements"
    / "synthetic-reference-room"
    / "tonally-normalized"
    / "analysis"
)
OUTPUT_FILES = {
    "left": "Tonally Normalized Room Left Speaker.wav",
    "right": "Tonally Normalized Room Right Speaker.wav",
}
SPEAKER_PATHS = {
    "left": ("LL", "LR"),
    "right": ("RL", "RR"),
}
DESIGN = {
    "sample_rate_hz": H_DESIGN["sample_rate_hz"],
    "output_length_samples": H_DESIGN["output_length_samples"],
    "nfft": H_DESIGN["nfft"],
    "base_candidate": "H idealized treated room",
    "correction": {
        "reference": "complete-to-direct binaural energy ratio per virtual speaker",
        "smoothing_fractional_octave": 6,
        "flat_band_hz": [200.0, 1000.0],
        "transition_band_hz": [160.0, 1250.0],
        "target": "log-frequency mean of the uncorrected smoothed ratio",
        "phase": "minimum phase",
        "fir_samples": 4096,
        "fir_fade_samples": 512,
        "calibration_iterations": 4,
        "maximum_absolute_gain_db": 6.0,
        "bulk_delay_samples": 0,
        "applied_identically_within_speaker_pairs": {
            "left": ["LL", "LR"],
            "right": ["RL", "RR"],
        },
    },
}


def display_path(path):
    try:
        return str(path.relative_to(REPOSITORY))
    except ValueError:
        return str(path)


def db20(values):
    return 20.0 * np.log10(np.maximum(np.abs(values), 1e-30))


def smooth_db_values(frequencies, values):
    result = np.empty(len(values), dtype=np.float64)
    result[1:] = np.asarray(
        log_smooth(
            frequencies[1:],
            values[1:],
            fraction=DESIGN["correction"]["smoothing_fractional_octave"],
        ),
        dtype=np.float64,
    )
    result[0] = result[1]
    return result


def speaker_ratio_db(spectra, direct_spectra, paths):
    complete_power = sum(np.square(np.abs(spectra[path])) for path in paths)
    direct_power = sum(np.square(np.abs(direct_spectra[path])) for path in paths)
    return 10.0 * np.log10(
        np.maximum(complete_power, 1e-30) / np.maximum(direct_power, 1e-30)
    )


def log_frequency_samples(frequencies, values, low, high, count=512):
    nodes = np.geomspace(low, high, count)
    return np.interp(nodes, frequencies, values)


def log_band_stats(frequencies, values, low=200.0, high=1000.0):
    selected = log_frequency_samples(frequencies, values, low, high)
    mean = float(np.mean(selected))
    return {
        "mean_db": finite_float(mean, 6),
        "rms_deviation_from_mean_db": finite_float(
            np.sqrt(np.mean(np.square(selected - mean))), 6
        ),
        "peak_to_peak_db": finite_float(np.ptp(selected), 6),
        "minimum_db": finite_float(np.min(selected), 6),
        "maximum_db": finite_float(np.max(selected), 6),
    }


def raised_cosine(length, rising=True):
    phase = np.linspace(0.0, math.pi, length, endpoint=True)
    values = 0.5 - 0.5 * np.cos(phase)
    return values if rising else values[::-1]


def taper_correction(frequencies, band_correction):
    low, high = DESIGN["correction"]["flat_band_hz"]
    transition_low, transition_high = DESIGN["correction"]["transition_band_hz"]
    result = np.zeros_like(band_correction)
    flat = (frequencies >= low) & (frequencies <= high)
    result[flat] = band_correction[flat]

    low_transition = (frequencies >= transition_low) & (frequencies < low)
    if np.any(low_transition):
        boundary = float(np.interp(low, frequencies, band_correction))
        result[low_transition] = boundary * raised_cosine(
            int(np.sum(low_transition)), rising=True
        )

    high_transition = (frequencies > high) & (frequencies <= transition_high)
    if np.any(high_transition):
        boundary = float(np.interp(high, frequencies, band_correction))
        result[high_transition] = boundary * raised_cosine(
            int(np.sum(high_transition)), rising=False
        )

    limit = DESIGN["correction"]["maximum_absolute_gain_db"]
    return np.clip(result, -limit, limit)


def minimum_phase_filter(correction_db):
    nfft = DESIGN["nfft"]
    definition = DESIGN["correction"]
    spectrum = minimum_phase_spectrum(
        np.power(10.0, correction_db / 20.0), nfft
    )
    impulse = np.fft.irfft(spectrum, nfft)[: definition["fir_samples"]].copy()
    fade = definition["fir_fade_samples"]
    impulse[-fade:] *= raised_cosine(fade, rising=False)
    impulse /= max(float(np.sum(impulse)), 1e-30)
    actual_spectrum = np.fft.rfft(impulse, nfft)
    return impulse, actual_spectrum


def design_speaker_filter(frequencies, raw_ratio_db):
    definition = DESIGN["correction"]
    low, high = definition["flat_band_hz"]
    original_smooth = smooth_db_values(frequencies, raw_ratio_db)
    target = float(
        np.mean(log_frequency_samples(frequencies, original_smooth, low, high))
    )
    band = (frequencies >= low) & (frequencies <= high)
    band_correction = np.zeros_like(raw_ratio_db)
    band_correction[band] = target - original_smooth[band]

    impulse = None
    actual_spectrum = None
    requested = None
    predicted_smooth = None
    for _ in range(definition["calibration_iterations"]):
        requested = taper_correction(frequencies, band_correction)
        impulse, actual_spectrum = minimum_phase_filter(requested)
        predicted_smooth = smooth_db_values(
            frequencies, raw_ratio_db + db20(actual_spectrum)
        )
        band_correction[band] += target - predicted_smooth[band]

    requested = taper_correction(frequencies, band_correction)
    impulse, actual_spectrum = minimum_phase_filter(requested)
    predicted_smooth = smooth_db_values(
        frequencies, raw_ratio_db + db20(actual_spectrum)
    )
    return {
        "target_db": target,
        "original_smoothed_ratio_db": original_smooth,
        "predicted_smoothed_ratio_db": predicted_smooth,
        "requested_correction_db": requested,
        "impulse": impulse,
        "spectrum": actual_spectrum,
    }


def interaural_preservation_metrics(before, after, frequencies, paths):
    low, high = DESIGN["correction"]["flat_band_hz"]
    band = (frequencies >= low) & (frequencies <= high)
    first, second = paths
    before_ratio = before[first] / np.where(
        np.abs(before[second]) > 1e-30, before[second], 1e-30
    )
    after_ratio = after[first] / np.where(
        np.abs(after[second]) > 1e-30, after[second], 1e-30
    )
    ild_delta = db20(after_ratio) - db20(before_ratio)
    phase_delta = np.angle(after_ratio / before_ratio, deg=True)
    return {
        "maximum_absolute_ild_delta_db": finite_float(
            np.max(np.abs(ild_delta[band])), 6
        ),
        "rms_ild_delta_db": finite_float(
            np.sqrt(np.mean(np.square(ild_delta[band]))), 6
        ),
        "maximum_absolute_phase_delta_degrees": finite_float(
            np.max(np.abs(phase_delta[band])), 6
        ),
    }


def response_at_frequencies(frequencies, spectrum, requested):
    output = {}
    values = db20(spectrum)
    for frequency in requested:
        output[str(int(frequency))] = finite_float(
            np.interp(frequency, frequencies, values), 6
        )
    return output


def write_plots(
    output,
    frequencies,
    h_spectra,
    i_spectra,
    direct_spectra,
    filters,
):
    plot_band = (frequencies >= 100.0) & (frequencies <= 1500.0)
    ratios = {}
    for speaker, paths in SPEAKER_PATHS.items():
        ratios[("H", speaker)] = smooth_db_values(
            frequencies, speaker_ratio_db(h_spectra, direct_spectra, paths)
        )
        ratios[("I", speaker)] = smooth_db_values(
            frequencies, speaker_ratio_db(i_spectra, direct_spectra, paths)
        )
    write_svg_plot(
        output / "binaural-tonal-normalization.svg",
        "Per-Speaker Binaural Room Coloration: H versus I",
        [
            (
                "H left",
                frequencies[plot_band],
                ratios[("H", "left")][plot_band],
                "#6b7280",
            ),
            (
                "I left",
                frequencies[plot_band],
                ratios[("I", "left")][plot_band],
                "#2563eb",
            ),
            (
                "H right",
                frequencies[plot_band],
                ratios[("H", "right")][plot_band],
                "#a1a1aa",
            ),
            (
                "I right",
                frequencies[plot_band],
                ratios[("I", "right")][plot_band],
                "#059669",
            ),
        ],
        "Frequency (Hz)",
        "1/6-octave complete-to-direct ratio (dB)",
        100.0,
        1500.0,
        -7.0,
        7.0,
        [100, 200, 300, 500, 1000, 1500],
        x_scale="log",
    )

    path_series = []
    for path, h_color, i_color in (
        ("LL", "#6b7280", COLORS["LL"]),
        ("RR", "#a1a1aa", "#059669"),
    ):
        direct = smooth_db_values(frequencies, db20(direct_spectra[path]))
        path_series.extend(
            [
                (
                    f"H {path}",
                    frequencies[plot_band],
                    (
                        smooth_db_values(frequencies, db20(h_spectra[path]))
                        - direct
                    )[plot_band],
                    h_color,
                ),
                (
                    f"I {path}",
                    frequencies[plot_band],
                    (
                        smooth_db_values(frequencies, db20(i_spectra[path]))
                        - direct
                    )[plot_band],
                    i_color,
                ),
            ]
        )
    write_svg_plot(
        output / "ipsilateral-h-i-direct-relative.svg",
        "Ipsilateral Direct-Relative Response: H versus I",
        path_series,
        "Frequency (Hz)",
        "1/6-octave complete-to-direct ratio (dB)",
        100.0,
        1500.0,
        -8.0,
        8.0,
        [100, 200, 300, 500, 1000, 1500],
        x_scale="log",
    )

    audible = (frequencies >= 20.0) & (frequencies <= 20000.0)
    write_svg_plot(
        output / "tonal-correction-response.svg",
        "Candidate I Minimum-Phase Tonal Correction",
        [
            (
                speaker,
                frequencies[audible],
                db20(values["spectrum"])[audible],
                color,
            )
            for speaker, values, color in (
                ("left speaker", filters["left"], "#2563eb"),
                ("right speaker", filters["right"], "#059669"),
            )
        ],
        "Frequency (Hz)",
        "Correction magnitude (dB)",
        20.0,
        20000.0,
        -7.0,
        7.0,
        [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000],
        x_scale="log",
    )


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ir-output", type=Path, default=OUTPUT_DIRECTORY)
    parser.add_argument("--analysis-output", type=Path, default=ANALYSIS_DIRECTORY)
    return parser.parse_args()


def main():
    args = parse_args()
    direct_summary = load_verified_inputs(DIRECT_FILES, DIRECT_ANALYSIS.parent)
    h_summary = load_verified_inputs(H_FILES, H_ANALYSIS_DIRECTORY)
    direct, sample_rate, direct_metadata = load_stereo_paths(DIRECT_FILES)
    candidate_h, h_rate, h_metadata = load_stereo_paths(H_FILES)
    if sample_rate != h_rate or sample_rate != DESIGN["sample_rate_hz"]:
        raise ValueError(f"Expected all inputs at {DESIGN['sample_rate_hz']} Hz")

    output_length = DESIGN["output_length_samples"]
    direct_padded = {
        path: pad_to(values, output_length) for path, values in direct.items()
    }
    nfft = DESIGN["nfft"]
    frequencies = np.fft.rfftfreq(nfft, 1.0 / sample_rate)
    direct_spectra = {
        path: np.fft.rfft(values, nfft) for path, values in direct_padded.items()
    }
    h_spectra = {
        path: np.fft.rfft(values, nfft) for path, values in candidate_h.items()
    }
    filters = {}
    for speaker, paths in SPEAKER_PATHS.items():
        ratio = speaker_ratio_db(h_spectra, direct_spectra, paths)
        filters[speaker] = design_speaker_filter(frequencies, ratio)

    candidate = {}
    truncated_tail_energy = {}
    for speaker, paths in SPEAKER_PATHS.items():
        for path in paths:
            full = np.convolve(candidate_h[path], filters[speaker]["impulse"])
            candidate[path] = full[:output_length]
            truncated_tail_energy[path] = 10.0 * math.log10(
                max(
                    float(np.sum(np.square(full[output_length:])))
                    / max(float(np.sum(np.square(full))), 1e-30),
                    1e-30,
                )
            )
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
            "path": display_path(path),
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
        raise ValueError("Rendered I sample rate changed unexpectedly")
    i_spectra = {
        path: np.fft.rfft(values, nfft) for path, values in rendered.items()
    }
    ratios = {}
    response_stats = {}
    interaural = {}
    for speaker, paths in SPEAKER_PATHS.items():
        h_ratio = speaker_ratio_db(h_spectra, direct_spectra, paths)
        i_ratio = speaker_ratio_db(i_spectra, direct_spectra, paths)
        h_smooth = smooth_db_values(frequencies, h_ratio)
        i_smooth = smooth_db_values(frequencies, i_ratio)
        ratios[speaker] = {"H": h_smooth, "I": i_smooth}
        response_stats[speaker] = {
            "H": log_band_stats(frequencies, h_smooth),
            "I": log_band_stats(frequencies, i_smooth),
            "target_db": finite_float(filters[speaker]["target_db"], 6),
        }
        interaural[speaker] = interaural_preservation_metrics(
            h_spectra, i_spectra, frequencies, paths
        )

    h_mean = np.mean(
        [smooth_db_values(frequencies, db20(h_spectra[path])) for path in PATH_ORDER],
        axis=0,
    )
    i_mean = np.mean(
        [smooth_db_values(frequencies, db20(i_spectra[path])) for path in PATH_ORDER],
        axis=0,
    )
    audible = (frequencies >= 20.0) & (frequencies <= 20000.0)
    correlated = (
        i_spectra["LL"] + i_spectra["RL"],
        i_spectra["LR"] + i_spectra["RR"],
    )
    maximum_correlated = max(
        float(np.max(np.abs(values[audible]))) for values in correlated
    )

    args.analysis_output.mkdir(parents=True, exist_ok=True)
    write_plots(
        args.analysis_output,
        frequencies,
        h_spectra,
        i_spectra,
        direct_spectra,
        filters,
    )
    filter_frequencies = (20.0, 100.0, 160.0, 200.0, 270.0, 500.0, 1000.0, 1250.0, 2000.0, 8000.0)
    summary = {
        "schema_version": 1,
        "status": "opt-in candidate I tonally normalized mastering room",
        "design": DESIGN,
        "direct_peak_samples": {
            path: int(direct_summary["paths"][path]["peak_sample"])
            for path in PATH_ORDER
        },
        "direct_files": direct_metadata,
        "candidate_h_files": h_metadata,
        "candidate_h_rendered_hashes": {
            side: h_summary["rendered_files"][side]["sha256"]
            for side in H_FILES
        },
        "binaural_response_200_1000_hz": response_stats,
        "interaural_preservation_200_1000_hz": interaural,
        "filter_response_db": {
            speaker: response_at_frequencies(
                frequencies, values["spectrum"], filter_frequencies
            )
            for speaker, values in filters.items()
        },
        "filter_gain_200_1000_hz": {
            speaker: log_band_stats(
                frequencies,
                db20(values["spectrum"]),
                *DESIGN["correction"]["flat_band_hz"],
            )
            for speaker, values in filters.items()
        },
        "filter_impulse_first_nonzero_sample": {
            speaker: int(np.flatnonzero(np.abs(values["impulse"]) > 1e-15)[0])
            for speaker, values in filters.items()
        },
        "truncated_filter_tail_energy_db_relative_to_complete_convolution": {
            path: finite_float(value, 6)
            for path, value in truncated_tail_energy.items()
        },
        "response_delta_I_minus_H": {
            "bass_20_80_hz": band_metrics(
                frequencies, i_mean, h_mean, 20.0, 80.0
            ),
            "protected_80_160_hz": band_metrics(
                frequencies, i_mean, h_mean, 80.0, 160.0
            ),
            "corrected_200_1000_hz": band_metrics(
                frequencies, i_mean, h_mean, 200.0, 1000.0
            ),
            "protected_1250_8000_hz": band_metrics(
                frequencies, i_mean, h_mean, 1250.0, 8000.0
            ),
        },
        "modeled_correlated_renderer_gain_db": finite_float(
            20.0 * math.log10(max(maximum_correlated, 1e-30)), 6
        ),
        "rendered_files": rendered_files,
        "plots": [
            "binaural-tonal-normalization.svg",
            "ipsilateral-h-i-direct-relative.svg",
            "tonal-correction-response.svg",
        ],
    }
    (args.analysis_output / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    left = response_stats["left"]
    right = response_stats["right"]
    report = [
        "# Candidate I Tonally Normalized Mastering Room",
        "",
        "Candidate I preserves H's complete room renderer and direct-only reference. It applies one causal minimum-phase tonal filter to both paths from each virtual speaker, correcting only the 1/6-octave-smoothed complete-to-direct binaural energy ratio from 200 Hz to 1 kHz.",
        "",
        "## Mathematical Target",
        "",
        "- Left speaker: `(abs(H_LL)^2 + abs(H_LR)^2) / (abs(D_LL)^2 + abs(D_LR)^2)`.",
        "- Right speaker: `(abs(H_RL)^2 + abs(H_RR)^2) / (abs(D_RL)^2 + abs(D_RR)^2)`.",
        "- Each target is the log-frequency mean of its original smoothed ratio, preserving average band quantity.",
        "- The correction is unity below 160 Hz and above 1.25 kHz, with tapered transitions into the 200 Hz-1 kHz normalization band.",
        "- Raw comb-filter teeth, direct HRTF magnitude, relative arrival times, and within-speaker interaural ratios are not independently inverted.",
        "",
        "## Offline Result",
        "",
        f"- Left-speaker RMS coloration falls from {left['H']['rms_deviation_from_mean_db']:.3f} to {left['I']['rms_deviation_from_mean_db']:.3f} dB; peak-to-peak falls from {left['H']['peak_to_peak_db']:.3f} to {left['I']['peak_to_peak_db']:.3f} dB.",
        f"- Right-speaker RMS coloration falls from {right['H']['rms_deviation_from_mean_db']:.3f} to {right['I']['rms_deviation_from_mean_db']:.3f} dB; peak-to-peak falls from {right['H']['peak_to_peak_db']:.3f} to {right['I']['peak_to_peak_db']:.3f} dB.",
        f"- I-minus-H bass RMS at 20-80 Hz: {summary['response_delta_I_minus_H']['bass_20_80_hz']['rms_delta_db']:.4f} dB.",
        f"- I-minus-H protected upper-band RMS at 1.25-8 kHz: {summary['response_delta_I_minus_H']['protected_1250_8000_hz']['rms_delta_db']:.4f} dB.",
        f"- Maximum within-speaker ILD change: {max(values['maximum_absolute_ild_delta_db'] for values in interaural.values()):.4f} dB.",
        f"- Maximum within-speaker phase change: {max(values['maximum_absolute_phase_delta_degrees'] for values in interaural.values()):.4f} degrees.",
        f"- Modeled maximum correlated renderer gain: {summary['modeled_correlated_renderer_gain_db']:+.2f} dB.",
        "",
        "I is an opt-in listening candidate. H remains unchanged and A remains the production default.",
    ]
    (args.analysis_output / "report.md").write_text(
        "\n".join(report) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
