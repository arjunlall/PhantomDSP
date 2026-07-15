#!/usr/bin/env python3
"""Render H-derived room candidates with broad binaural tonal normalization."""

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
    C_FILES,
    DESIGN as H_DESIGN,
    E_FILES,
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
        "target_band_hz": [200.0, 1000.0],
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
J_DESIGN = {
    **DESIGN,
    "base_candidate": "I tonally normalized room",
    "correction": {
        **DESIGN["correction"],
        "flat_band_hz": [1000.0, 1500.0],
        "target_band_hz": [200.0, 1000.0],
        "evaluation_band_hz": [200.0, 1500.0],
        "transition_band_hz": [900.0, 1800.0],
        "transition_mode": "frequency-shaped raised cosine",
        "target": "candidate I 200 Hz-1 kHz log-frequency mean",
        "calibration_iterations": 0,
    },
}
PROFILES = {
    "I": {
        "label": "I",
        "name": "Tonally Normalized Mastering Room",
        "status": "opt-in candidate I tonally normalized mastering room",
        "design": DESIGN,
        "ir_output": OUTPUT_DIRECTORY,
        "analysis_output": ANALYSIS_DIRECTORY,
        "output_files": OUTPUT_FILES,
    },
    "J": {
        "label": "J",
        "name": "Midrange Normalized Mastering Room",
        "status": "opt-in candidate J midrange normalized mastering room",
        "design": J_DESIGN,
        "ir_output": (
            REPOSITORY
            / "Synthetic Reference Room"
            / "IRs"
            / "midrange-normalized"
        ),
        "analysis_output": (
            REPOSITORY
            / "measurements"
            / "synthetic-reference-room"
            / "midrange-normalized"
            / "analysis"
        ),
        "output_files": {
            "left": "Midrange Normalized Room Left Speaker.wav",
            "right": "Midrange Normalized Room Right Speaker.wav",
        },
    },
}
I_FILES = {
    side: OUTPUT_DIRECTORY / filename for side, filename in OUTPUT_FILES.items()
}


def display_path(path):
    try:
        return str(path.relative_to(REPOSITORY))
    except ValueError:
        return str(path)


def db20(values):
    return 20.0 * np.log10(np.maximum(np.abs(values), 1e-30))


def format_frequency(frequency):
    if frequency >= 1000.0:
        return f"{frequency / 1000.0:g} kHz"
    return f"{frequency:g} Hz"


def smooth_db_values(frequencies, values, design=DESIGN):
    result = np.empty(len(values), dtype=np.float64)
    result[1:] = np.asarray(
        log_smooth(
            frequencies[1:],
            values[1:],
            fraction=design["correction"]["smoothing_fractional_octave"],
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


def speaker_energy_db(spectra, paths):
    power = sum(np.square(np.abs(spectra[path])) for path in paths)
    return 10.0 * np.log10(np.maximum(power, 1e-30))


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


def taper_correction(frequencies, band_correction, design=DESIGN):
    definition = design["correction"]
    low, high = design["correction"]["flat_band_hz"]
    transition_low, transition_high = definition["transition_band_hz"]
    frequency_shaped = definition.get("transition_mode") == (
        "frequency-shaped raised cosine"
    )
    result = np.zeros_like(band_correction)
    flat = (frequencies >= low) & (frequencies <= high)
    result[flat] = band_correction[flat]

    low_transition = (frequencies >= transition_low) & (frequencies < low)
    if np.any(low_transition):
        fade = raised_cosine(int(np.sum(low_transition)), rising=True)
        if frequency_shaped:
            result[low_transition] = band_correction[low_transition] * fade
        else:
            boundary = float(np.interp(low, frequencies, band_correction))
            result[low_transition] = boundary * fade

    high_transition = (frequencies > high) & (frequencies <= transition_high)
    if np.any(high_transition):
        fade = raised_cosine(int(np.sum(high_transition)), rising=False)
        if frequency_shaped:
            result[high_transition] = band_correction[high_transition] * fade
        else:
            boundary = float(np.interp(high, frequencies, band_correction))
            result[high_transition] = boundary * fade

    limit = definition["maximum_absolute_gain_db"]
    return np.clip(result, -limit, limit)


def minimum_phase_filter(correction_db, design=DESIGN):
    nfft = design["nfft"]
    definition = design["correction"]
    spectrum = minimum_phase_spectrum(
        np.power(10.0, correction_db / 20.0), nfft
    )
    impulse = np.fft.irfft(spectrum, nfft)[: definition["fir_samples"]].copy()
    fade = definition["fir_fade_samples"]
    impulse[-fade:] *= raised_cosine(fade, rising=False)
    impulse /= max(float(np.sum(impulse)), 1e-30)
    actual_spectrum = np.fft.rfft(impulse, nfft)
    return impulse, actual_spectrum


def design_speaker_filter(frequencies, raw_ratio_db, design=DESIGN):
    definition = design["correction"]
    low, high = definition["flat_band_hz"]
    target_low, target_high = definition.get("target_band_hz", (low, high))
    original_smooth = smooth_db_values(frequencies, raw_ratio_db, design)
    target = float(
        np.mean(
            log_frequency_samples(
                frequencies, original_smooth, target_low, target_high
            )
        )
    )
    band = (frequencies >= low) & (frequencies <= high)
    band_correction = np.zeros_like(raw_ratio_db)
    if definition.get("transition_mode") == "frequency-shaped raised cosine":
        transition_low, transition_high = definition["transition_band_hz"]
        support = (frequencies >= transition_low) & (
            frequencies <= transition_high
        )
    else:
        support = band
    band_correction[support] = target - original_smooth[support]

    impulse = None
    actual_spectrum = None
    requested = None
    predicted_smooth = None
    for _ in range(definition["calibration_iterations"]):
        requested = taper_correction(frequencies, band_correction, design)
        impulse, actual_spectrum = minimum_phase_filter(requested, design)
        predicted_smooth = smooth_db_values(
            frequencies, raw_ratio_db + db20(actual_spectrum), design
        )
        band_correction[band] += target - predicted_smooth[band]

    requested = taper_correction(frequencies, band_correction, design)
    impulse, actual_spectrum = minimum_phase_filter(requested, design)
    predicted_smooth = smooth_db_values(
        frequencies, raw_ratio_db + db20(actual_spectrum), design
    )
    return {
        "target_db": target,
        "original_smoothed_ratio_db": original_smooth,
        "predicted_smoothed_ratio_db": predicted_smooth,
        "requested_correction_db": requested,
        "impulse": impulse,
        "spectrum": actual_spectrum,
    }


def interaural_preservation_metrics(
    before, after, frequencies, paths, design=DESIGN
):
    low, high = design["correction"].get(
        "evaluation_band_hz", design["correction"]["flat_band_hz"]
    )
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
    candidate_spectra,
    direct_spectra,
    filters,
    profile,
    i_spectra=None,
    component_spectra=None,
):
    label = profile["label"]
    design = profile["design"]
    plot_high = 1500.0 if label == "I" else 4000.0
    plot_ticks = (
        [100, 200, 300, 500, 1000, 1500]
        if label == "I"
        else [100, 200, 300, 500, 1000, 2000, 3000, 4000]
    )
    plot_band = (frequencies >= 100.0) & (frequencies <= plot_high)
    ratios = {}
    for speaker, paths in SPEAKER_PATHS.items():
        ratios[("H", speaker)] = smooth_db_values(
            frequencies,
            speaker_ratio_db(h_spectra, direct_spectra, paths),
            design,
        )
        ratios[(label, speaker)] = smooth_db_values(
            frequencies,
            speaker_ratio_db(candidate_spectra, direct_spectra, paths),
            design,
        )
    write_svg_plot(
        output / "binaural-tonal-normalization.svg",
        f"Per-Speaker Binaural Room Coloration: H versus {label}",
        [
            (
                "H left",
                frequencies[plot_band],
                ratios[("H", "left")][plot_band],
                "#6b7280",
            ),
            (
                f"{label} left",
                frequencies[plot_band],
                ratios[(label, "left")][plot_band],
                "#2563eb",
            ),
            (
                "H right",
                frequencies[plot_band],
                ratios[("H", "right")][plot_band],
                "#a1a1aa",
            ),
            (
                f"{label} right",
                frequencies[plot_band],
                ratios[(label, "right")][plot_band],
                "#059669",
            ),
        ],
        "Frequency (Hz)",
        "1/6-octave complete-to-direct ratio (dB)",
        100.0,
        plot_high,
        -7.0,
        7.0,
        plot_ticks,
        x_scale="log",
    )

    plots = ["binaural-tonal-normalization.svg"]
    if i_spectra is not None:
        comparison_series = []
        for speaker, color_i, color_j in (
            ("left", "#93c5fd", "#2563eb"),
            ("right", "#86efac", "#059669"),
        ):
            paths = SPEAKER_PATHS[speaker]
            i_ratio = smooth_db_values(
                frequencies,
                speaker_ratio_db(i_spectra, direct_spectra, paths),
                design,
            )
            comparison_series.extend(
                [
                    (
                        f"I {speaker}",
                        frequencies[plot_band],
                        i_ratio[plot_band],
                        color_i,
                    ),
                    (
                        f"{label} {speaker}",
                        frequencies[plot_band],
                        ratios[(label, speaker)][plot_band],
                        color_j,
                    ),
                ]
            )
        write_svg_plot(
            output / "i-j-room-coloration.svg",
            "Per-Speaker Binaural Room Coloration: I versus J",
            comparison_series,
            "Frequency (Hz)",
            "1/6-octave complete-to-direct ratio (dB)",
            100.0,
            plot_high,
            -7.0,
            7.0,
            plot_ticks,
            x_scale="log",
        )
        plots.append("i-j-room-coloration.svg")

    if label == "J":
        full_band = (frequencies >= 20.0) & (frequencies <= 20000.0)
        # The responses are already 1/6-octave smoothed. A log-spaced display
        # grid preserves their visible shape without emitting tens of
        # thousands of redundant SVG points.
        full_plot_frequencies = np.geomspace(20.0, 20000.0, 1200)
        write_svg_plot(
            output / "j-left-right-full-spectrum.svg",
            "Candidate J Full-Spectrum Per-Speaker Room Coloration",
            [
                (
                    "J left speaker",
                    full_plot_frequencies,
                    np.interp(
                        full_plot_frequencies,
                        frequencies[full_band],
                        ratios[(label, "left")][full_band],
                    ),
                    "#2563eb",
                ),
                (
                    "J right speaker",
                    full_plot_frequencies,
                    np.interp(
                        full_plot_frequencies,
                        frequencies[full_band],
                        ratios[(label, "right")][full_band],
                    ),
                    "#059669",
                ),
            ],
            "Frequency (Hz)",
            "1/6-octave complete-to-direct ratio (dB)",
            20.0,
            20000.0,
            -2.0,
            12.0,
            [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000],
            x_scale="log",
        )
        plots.append("j-left-right-full-spectrum.svg")

        if component_spectra is not None:
            component_colors = {
                "direct": "#6b7280",
                "early": "#2563eb",
                "late": "#d97706",
                "complete": "#059669",
            }
            for speaker, paths in SPEAKER_PATHS.items():
                combined_filter_db = speaker_ratio_db(
                    candidate_spectra, h_spectra, paths
                )
                component_curves = {
                    name: smooth_db_values(
                        frequencies,
                        speaker_energy_db(spectra, paths) + combined_filter_db,
                        design,
                    )
                    for name, spectra in component_spectra.items()
                }
                component_curves["complete"] = smooth_db_values(
                    frequencies,
                    speaker_energy_db(candidate_spectra, paths),
                    design,
                )
                reference = float(
                    np.interp(
                        1000.0,
                        frequencies,
                        component_curves["direct"],
                    )
                )
                for name in component_curves:
                    component_curves[name] -= reference
                filename = f"j-{speaker}-components-full-spectrum.svg"
                write_svg_plot(
                    output / filename,
                    f"Candidate J {speaker.title()} Speaker Components",
                    [
                        (
                            label_text,
                            full_plot_frequencies,
                            np.maximum(
                                np.interp(
                                    full_plot_frequencies,
                                    frequencies[full_band],
                                    component_curves[name][full_band],
                                ),
                                -40.0,
                            ),
                            component_colors[name],
                        )
                        for name, label_text in (
                            ("direct", "personal direct"),
                            ("early", "synthetic early"),
                            ("late", "synthetic late"),
                            ("complete", "complete J"),
                        )
                    ],
                    "Frequency (Hz)",
                    "Energy relative to J-filtered direct at 1 kHz (dB)",
                    20.0,
                    20000.0,
                    -40.0,
                    25.0,
                    [
                        20,
                        50,
                        100,
                        200,
                        500,
                        1000,
                        2000,
                        5000,
                        10000,
                        20000,
                    ],
                    x_scale="log",
                )
                plots.append(filename)

    path_series = []
    for path, h_color, candidate_color in (
        ("LL", "#6b7280", COLORS["LL"]),
        ("RR", "#a1a1aa", "#059669"),
    ):
        direct = smooth_db_values(
            frequencies, db20(direct_spectra[path]), design
        )
        path_series.extend(
            [
                (
                    f"H {path}",
                    frequencies[plot_band],
                    (
                        smooth_db_values(
                            frequencies, db20(h_spectra[path]), design
                        )
                        - direct
                    )[plot_band],
                    h_color,
                ),
                (
                    f"{label} {path}",
                    frequencies[plot_band],
                    (
                        smooth_db_values(
                            frequencies,
                            db20(candidate_spectra[path]),
                            design,
                        )
                        - direct
                    )[plot_band],
                    candidate_color,
                ),
            ]
        )
    write_svg_plot(
        output / f"ipsilateral-h-{label.lower()}-direct-relative.svg",
        f"Ipsilateral Direct-Relative Response: H versus {label}",
        path_series,
        "Frequency (Hz)",
        "1/6-octave complete-to-direct ratio (dB)",
        100.0,
        plot_high,
        -8.0,
        8.0,
        plot_ticks,
        x_scale="log",
    )

    audible = (frequencies >= 20.0) & (frequencies <= 20000.0)
    write_svg_plot(
        output / "tonal-correction-response.svg",
        f"Candidate {label} Minimum-Phase Tonal Correction",
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
    plots.extend(
        [
            f"ipsilateral-h-{label.lower()}-direct-relative.svg",
            "tonal-correction-response.svg",
        ]
    )
    return plots


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", choices=sorted(PROFILES), default="I")
    parser.add_argument("--ir-output", type=Path)
    parser.add_argument("--analysis-output", type=Path)
    return parser.parse_args()


def main():
    args = parse_args()
    profile = PROFILES[args.candidate]
    label = profile["label"]
    design = profile["design"]
    ir_output = args.ir_output or profile["ir_output"]
    analysis_output = args.analysis_output or profile["analysis_output"]
    output_files = profile["output_files"]
    direct_summary = load_verified_inputs(DIRECT_FILES, DIRECT_ANALYSIS.parent)
    h_summary = load_verified_inputs(H_FILES, H_ANALYSIS_DIRECTORY)
    i_summary = None
    candidate_i = None
    i_rate = None
    if label == "J":
        i_summary = load_verified_inputs(I_FILES, ANALYSIS_DIRECTORY)
        candidate_i, i_rate, _ = load_stereo_paths(I_FILES)
    direct, sample_rate, direct_metadata = load_stereo_paths(DIRECT_FILES)
    candidate_h, h_rate, h_metadata = load_stereo_paths(H_FILES)
    if (
        sample_rate != h_rate
        or (i_rate is not None and sample_rate != i_rate)
        or sample_rate != design["sample_rate_hz"]
    ):
        raise ValueError(f"Expected all inputs at {design['sample_rate_hz']} Hz")

    output_length = design["output_length_samples"]
    direct_padded = {
        path: pad_to(values, output_length) for path, values in direct.items()
    }
    nfft = design["nfft"]
    frequencies = np.fft.rfftfreq(nfft, 1.0 / sample_rate)
    direct_spectra = {
        path: np.fft.rfft(values, nfft) for path, values in direct_padded.items()
    }
    h_spectra = {
        path: np.fft.rfft(values, nfft) for path, values in candidate_h.items()
    }
    i_spectra = None
    if candidate_i is not None:
        i_spectra = {
            path: np.fft.rfft(values, nfft)
            for path, values in candidate_i.items()
        }
    base_candidate = candidate_i if candidate_i is not None else candidate_h
    base_spectra = i_spectra if i_spectra is not None else h_spectra
    filters = {}
    for speaker, paths in SPEAKER_PATHS.items():
        ratio = speaker_ratio_db(base_spectra, direct_spectra, paths)
        filters[speaker] = design_speaker_filter(frequencies, ratio, design)

    candidate = {}
    truncated_tail_energy = {}
    for speaker, paths in SPEAKER_PATHS.items():
        for path in paths:
            full = np.convolve(base_candidate[path], filters[speaker]["impulse"])
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

    ir_output.mkdir(parents=True, exist_ok=True)
    stereo = {
        "left": np.column_stack([candidate["LL"], candidate["LR"]]),
        "right": np.column_stack([candidate["RL"], candidate["RR"]]),
    }
    rendered_files = {}
    for side, values in stereo.items():
        path = ir_output / output_files[side]
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
        {side: ir_output / filename for side, filename in output_files.items()}
    )
    if rendered_rate != sample_rate:
        raise ValueError(f"Rendered {label} sample rate changed unexpectedly")
    candidate_spectra = {
        path: np.fft.rfft(values, nfft) for path, values in rendered.items()
    }
    component_spectra = None
    if label == "J":
        candidate_c, c_rate, _ = load_stereo_paths(C_FILES)
        candidate_e, e_rate, _ = load_stereo_paths(E_FILES)
        if c_rate != sample_rate or e_rate != sample_rate:
            raise ValueError("Expected J component inputs at the design sample rate")
        candidate_c = {
            path: pad_to(values, output_length)
            for path, values in candidate_c.items()
        }
        candidate_e = {
            path: pad_to(values, output_length)
            for path, values in candidate_e.items()
        }
        late = {
            path: candidate_e[path] - candidate_c[path] for path in PATH_ORDER
        }
        early = {
            path: candidate_h[path] - direct_padded[path] - late[path]
            for path in PATH_ORDER
        }
        component_spectra = {
            "direct": direct_spectra,
            "early": {
                path: np.fft.rfft(values, nfft)
                for path, values in early.items()
            },
            "late": {
                path: np.fft.rfft(values, nfft)
                for path, values in late.items()
            },
        }
    ratios = {}
    response_stats = {}
    interaural = {}
    evaluation_band = design["correction"].get(
        "evaluation_band_hz", design["correction"]["flat_band_hz"]
    )
    for speaker, paths in SPEAKER_PATHS.items():
        h_ratio = speaker_ratio_db(h_spectra, direct_spectra, paths)
        candidate_ratio = speaker_ratio_db(
            candidate_spectra, direct_spectra, paths
        )
        h_smooth = smooth_db_values(frequencies, h_ratio, design)
        candidate_smooth = smooth_db_values(
            frequencies, candidate_ratio, design
        )
        ratios[speaker] = {"H": h_smooth, label: candidate_smooth}
        response_stats[speaker] = {
            "H": log_band_stats(
                frequencies, h_smooth, *evaluation_band
            ),
            label: log_band_stats(
                frequencies,
                candidate_smooth,
                *evaluation_band,
            ),
            "target_db": finite_float(filters[speaker]["target_db"], 6),
        }
        if i_spectra is not None:
            i_ratio = speaker_ratio_db(i_spectra, direct_spectra, paths)
            i_smooth = smooth_db_values(frequencies, i_ratio, design)
            response_stats[speaker]["I"] = log_band_stats(
                frequencies,
                i_smooth,
                *evaluation_band,
            )
        interaural[speaker] = interaural_preservation_metrics(
            base_spectra, candidate_spectra, frequencies, paths, design
        )

    h_mean = np.mean(
        [
            smooth_db_values(frequencies, db20(h_spectra[path]), design)
            for path in PATH_ORDER
        ],
        axis=0,
    )
    candidate_mean = np.mean(
        [
            smooth_db_values(
                frequencies, db20(candidate_spectra[path]), design
            )
            for path in PATH_ORDER
        ],
        axis=0,
    )
    i_mean = None
    if i_spectra is not None:
        i_mean = np.mean(
            [
                smooth_db_values(frequencies, db20(i_spectra[path]), design)
                for path in PATH_ORDER
            ],
            axis=0,
        )
    audible = (frequencies >= 20.0) & (frequencies <= 20000.0)
    correlated = (
        candidate_spectra["LL"] + candidate_spectra["RL"],
        candidate_spectra["LR"] + candidate_spectra["RR"],
    )
    maximum_correlated = max(
        float(np.max(np.abs(values[audible]))) for values in correlated
    )

    analysis_output.mkdir(parents=True, exist_ok=True)
    plots = write_plots(
        analysis_output,
        frequencies,
        h_spectra,
        candidate_spectra,
        direct_spectra,
        filters,
        profile,
        i_spectra,
        component_spectra,
    )
    correction_low, correction_high = design["correction"]["flat_band_hz"]
    low, high = evaluation_band
    transition_low, transition_high = design["correction"]["transition_band_hz"]
    band_token = f"{int(low)}_{int(high)}"
    upper_token = f"{int(transition_high)}_8000"
    response_key = f"binaural_response_{band_token}_hz"
    interaural_key = f"interaural_preservation_{band_token}_hz"
    filter_gain_key = (
        f"filter_gain_{int(correction_low)}_{int(correction_high)}_hz"
    )
    delta_key = f"response_delta_{label}_minus_H"
    corrected_key = f"corrected_{band_token}_hz"
    protected_low_key = f"protected_80_{int(transition_low)}_hz"
    protected_upper_key = f"protected_{upper_token}_hz"
    filter_frequencies = tuple(
        sorted(
            {
                20.0,
                100.0,
                transition_low,
                low,
                correction_low,
                270.0,
                500.0,
                1000.0,
                1250.0,
                high,
                correction_high,
                transition_high,
                8000.0,
            }
        )
    )
    summary = {
        "schema_version": 1,
        "status": profile["status"],
        "design": design,
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
        response_key: response_stats,
        interaural_key: interaural,
        "filter_response_db": {
            speaker: response_at_frequencies(
                frequencies, values["spectrum"], filter_frequencies
            )
            for speaker, values in filters.items()
        },
        filter_gain_key: {
            speaker: log_band_stats(
                frequencies,
                db20(values["spectrum"]),
                correction_low,
                correction_high,
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
        delta_key: {
            "bass_20_80_hz": band_metrics(
                frequencies, candidate_mean, h_mean, 20.0, 80.0
            ),
            protected_low_key: band_metrics(
                frequencies, candidate_mean, h_mean, 80.0, transition_low
            ),
            corrected_key: band_metrics(
                frequencies, candidate_mean, h_mean, low, high
            ),
            protected_upper_key: band_metrics(
                frequencies, candidate_mean, h_mean, transition_high, 8000.0
            ),
        },
        "modeled_correlated_renderer_gain_db": finite_float(
            20.0 * math.log10(max(maximum_correlated, 1e-30)), 6
        ),
        "rendered_files": rendered_files,
        "plots": plots,
    }
    if i_summary is not None:
        summary["candidate_i_rendered_hashes"] = {
            side: i_summary["rendered_files"][side]["sha256"]
            for side in I_FILES
        }
        summary["response_delta_J_minus_I"] = {
            "established_200_1000_hz": band_metrics(
                frequencies, candidate_mean, i_mean, 200.0, 1000.0
            ),
            "correction_extension_1000_1500_hz": band_metrics(
                frequencies, candidate_mean, i_mean, 1000.0, 1500.0
            ),
            "release_1500_1800_hz": band_metrics(
                frequencies, candidate_mean, i_mean, 1500.0, 1800.0
            ),
            "protected_1800_8000_hz": band_metrics(
                frequencies, candidate_mean, i_mean, 1800.0, 8000.0
            ),
        }
    (analysis_output / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    left = response_stats["left"]
    right = response_stats["right"]
    base_label = "I" if label == "J" else "H"
    description = (
        f"Candidate J preserves I's complete room renderer and direct-only reference. It adds one causal minimum-phase tonal filter shared by both ear paths from each speaker. The combined {format_frequency(low)}-{format_frequency(high)} result is evaluated against the direct reference, while J's new correction is confined to the transition around {format_frequency(correction_low)}-{format_frequency(correction_high)}."
        if label == "J"
        else f"Candidate I preserves H's complete room renderer and direct-only reference. It applies one causal minimum-phase tonal filter to both paths from each virtual speaker, correcting only the 1/6-octave-smoothed complete-to-direct binaural energy ratio from {format_frequency(low)} to {format_frequency(high)}."
    )
    report = [
        f"# Candidate {label} {profile['name']}",
        "",
        description,
        "",
        "## Mathematical Target",
        "",
        f"- Left speaker: `(abs({base_label}_LL)^2 + abs({base_label}_LR)^2) / (abs(D_LL)^2 + abs(D_LR)^2)`.",
        f"- Right speaker: `(abs({base_label}_RL)^2 + abs({base_label}_RR)^2) / (abs(D_RL)^2 + abs(D_RR)^2)`.",
        (
            "- Each target is the log-frequency mean of its original smoothed ratio, preserving average band quantity."
            if label == "I"
            else "- J retains I's established 200 Hz-1 kHz target level, so the successful lower-midrange balance is not re-centered."
        ),
        f"- The new correction is unity below {format_frequency(transition_low)} and above {format_frequency(transition_high)}, with tapered transitions into the {format_frequency(correction_low)}-{format_frequency(correction_high)} normalization band.",
        "- Raw comb-filter teeth, direct HRTF magnitude, relative arrival times, and within-speaker interaural ratios are not independently inverted.",
        "",
        "## Offline Result",
        "",
        f"- Left-speaker RMS coloration falls from {left['H']['rms_deviation_from_mean_db']:.3f} to {left[label]['rms_deviation_from_mean_db']:.3f} dB; peak-to-peak falls from {left['H']['peak_to_peak_db']:.3f} to {left[label]['peak_to_peak_db']:.3f} dB.",
        f"- Right-speaker RMS coloration falls from {right['H']['rms_deviation_from_mean_db']:.3f} to {right[label]['rms_deviation_from_mean_db']:.3f} dB; peak-to-peak falls from {right['H']['peak_to_peak_db']:.3f} to {right[label]['peak_to_peak_db']:.3f} dB.",
        f"- {label}-minus-H bass RMS at 20-80 Hz: {summary[delta_key]['bass_20_80_hz']['rms_delta_db']:.4f} dB.",
        f"- {label}-minus-H protected upper-band RMS at {transition_high / 1000:g}-8 kHz: {summary[delta_key][protected_upper_key]['rms_delta_db']:.4f} dB.",
        f"- Maximum within-speaker ILD change: {max(values['maximum_absolute_ild_delta_db'] for values in interaural.values()):.4f} dB.",
        f"- Maximum within-speaker phase change: {max(values['maximum_absolute_phase_delta_degrees'] for values in interaural.values()):.4f} degrees.",
        f"- Modeled maximum correlated renderer gain: {summary['modeled_correlated_renderer_gain_db']:+.2f} dB.",
        "",
        f"{label} is an opt-in listening candidate. I and H remain unchanged, and A remains the production default.",
    ]
    if label == "J":
        report[18:18] = [
            f"- J-minus-I RMS at 200 Hz-1 kHz: {summary['response_delta_J_minus_I']['established_200_1000_hz']['rms_delta_db']:.4f} dB.",
            f"- J-minus-I RMS at 1-1.5 kHz: {summary['response_delta_J_minus_I']['correction_extension_1000_1500_hz']['rms_delta_db']:.4f} dB.",
        ]
    (analysis_output / "report.md").write_text(
        "\n".join(report) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
