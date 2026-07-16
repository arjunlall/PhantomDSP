#!/usr/bin/env python3
"""Render a treatment-aware microcluster timbre refinement of candidate K."""

import argparse
import json
import math
from pathlib import Path

import numpy as np

from analyze_baseline import finite_float, sha256, write_svg_plot
from analyze_directional_diffuse_timbre import (
    ANALYSIS_DIRECTORY as TIMBRE_ANALYSIS_DIRECTORY,
    band_stats,
)
from explore_minimum_latency_renderer import minimum_phase_spectrum
from render_active_renderer import write_pcm24
from render_directional_diffuse_room import (
    ANALYSIS_DIRECTORY as K_ANALYSIS_DIRECTORY,
    DESIGN as K_DESIGN,
    H_FILES,
    OUTPUT_DIRECTORY as K_OUTPUT_DIRECTORY,
    OUTPUT_FILES as K_OUTPUT_FILES,
    SPEAKER_PATHS,
    build_minimum_phase_filter as build_directional_filter,
    reconstruct_microclusters,
    requested_directional_corrections,
)
from render_idealized_treated_room import (
    ANALYSIS_DIRECTORY as H_ANALYSIS_DIRECTORY,
    C_FILES,
    E_FILES,
)
from render_synthetic_direct import PATH_ORDER, REPOSITORY, load_stereo_paths
from render_synthetic_early_room import DIRECT_ANALYSIS, DIRECT_FILES
from render_theoretical_early_room import array_sha256, load_verified_inputs
from render_tonally_normalized_room import smooth_db_values


K_FILES = {
    side: K_OUTPUT_DIRECTORY / filename
    for side, filename in K_OUTPUT_FILES.items()
}
OUTPUT_DIRECTORY = REPOSITORY / "Synthetic Reference Room" / "IRs" / "timbre-balanced"
ANALYSIS_DIRECTORY = (
    REPOSITORY
    / "measurements"
    / "synthetic-reference-room"
    / "timbre-balanced"
    / "analysis"
)
OUTPUT_FILES = {
    "left": "Timbre Balanced Room Left Speaker.wav",
    "right": "Timbre Balanced Room Right Speaker.wav",
}
DESIGN = {
    "candidate_label": "L",
    "candidate_display_name": "Timbre-Balanced Room",
    "plot_prefix": "timbre-balanced",
    "status": "opt-in treatment-aware timbre candidate",
    "sample_rate_hz": K_DESIGN["sample_rate_hz"],
    "output_length_samples": K_DESIGN["output_length_samples"],
    "nfft": K_DESIGN["nfft"],
    "base_candidate": "K directional diffuse mastering room",
    "changed_branch": "directional deterministic microclusters only",
    "unchanged_branches": [
        "personal direct and bass",
        "treated specular reflections",
        "synthetic late field",
        "K interaural directional ratios",
        "J 200 Hz-1.8 kHz tonal normalization",
    ],
    "correction_source": "candidate K ERB timbre audit",
    "correction_support_hz": [4500.0, 14000.0],
    "correction_full_strength_hz": [6000.0, 12000.0],
    "attenuation_only": True,
    "maximum_attenuation_db": -18.0,
    "filter_samples": 4096,
    "filter_fade_samples": 512,
    "filter_calibration_iterations": 3,
    "bulk_delay_samples": 0,
    "interaural_contract": (
        "one identical microcluster filter per virtual speaker, shared by both ears"
    ),
}


def display_path(path):
    try:
        return str(path.relative_to(REPOSITORY))
    except ValueError:
        return str(path)


def db20(values):
    return 20.0 * np.log10(np.maximum(np.abs(values), 1e-30))


def correction_window(frequencies):
    low, high = DESIGN["correction_support_hz"]
    full_low, full_high = DESIGN["correction_full_strength_hz"]
    values = np.asarray(frequencies, dtype=np.float64)
    window = np.zeros_like(values)
    middle = (values >= full_low) & (values <= full_high)
    window[middle] = 1.0
    rise = (values > low) & (values < full_low)
    phase = (values[rise] - low) / (full_low - low)
    window[rise] = 0.5 - 0.5 * np.cos(math.pi * phase)
    fall = (values > full_high) & (values < high)
    phase = (values[fall] - full_high) / (high - full_high)
    window[fall] = 0.5 + 0.5 * np.cos(math.pi * phase)
    return window


def requested_correction(frequencies, timbre_summary, speaker):
    centers = np.asarray(timbre_summary["erb_centers_hz"], dtype=np.float64)
    excess = np.asarray(
        timbre_summary["curves"][speaker]["micro_current_minus_target_db"],
        dtype=np.float64,
    )
    attenuation = -np.maximum(excess, 0.0)
    interpolated = np.interp(
        np.log2(np.maximum(frequencies, centers[0])),
        np.log2(centers),
        attenuation,
        left=float(attenuation[0]),
        right=float(attenuation[-1]),
    )
    return np.clip(
        interpolated * correction_window(frequencies),
        DESIGN["maximum_attenuation_db"],
        0.0,
    )


def build_minimum_phase_filter(requested_db):
    nfft = DESIGN["nfft"]
    frequencies = np.fft.rfftfreq(nfft, 1.0 / DESIGN["sample_rate_hz"])
    support = correction_window(frequencies)
    design_db = np.asarray(requested_db, dtype=np.float64).copy()
    impulse = None
    spectrum = None
    for _ in range(DESIGN["filter_calibration_iterations"] + 1):
        spectrum = minimum_phase_spectrum(np.power(10.0, design_db / 20.0), nfft)
        impulse = np.fft.irfft(spectrum, nfft)[: DESIGN["filter_samples"]]
        fade = DESIGN["filter_fade_samples"]
        impulse[-fade:] *= np.linspace(1.0, 0.0, fade, endpoint=True)
        spectrum = np.fft.rfft(impulse, nfft)
        residual = (requested_db - db20(spectrum)) * support
        design_db = np.clip(
            design_db + residual,
            DESIGN["maximum_attenuation_db"] * 1.25,
            0.0,
        )
    return impulse, spectrum


def response_band_delta(frequencies, candidate, reference, low, high):
    selected = (frequencies >= low) & (frequencies <= high)
    delta = candidate[selected] - reference[selected]
    return {
        "mean_db": finite_float(np.mean(delta), 6),
        "rms_db": finite_float(np.sqrt(np.mean(np.square(delta))), 6),
        "minimum_db": finite_float(np.min(delta), 6),
        "maximum_db": finite_float(np.max(delta), 6),
    }


def speaker_response(spectra, paths, frequencies):
    power = sum(np.square(np.abs(spectra[path])) for path in paths)
    return smooth_db_values(
        frequencies, 10.0 * np.log10(np.maximum(power, 1e-30))
    )


def write_plots(output, frequencies, actual, k_spectra, l_spectra, residual):
    output.mkdir(parents=True, exist_ok=True)
    plots = []
    selected = (frequencies >= 4000.0) & (frequencies <= 15000.0)
    write_svg_plot(
        output / "microcluster-timbre-filters.svg",
        f"{DESIGN['candidate_display_name']} Microcluster Filters",
        [
            (
                f"{speaker} actual",
                frequencies[selected],
                db20(actual[speaker])[selected],
                color,
            )
            for speaker, color in (("left", "#2563eb"), ("right", "#059669"))
        ],
        "Frequency (Hz)",
        "Microcluster filter gain (dB)",
        4000.0,
        15000.0,
        -20.0,
        1.0,
        [4000, 5000, 6000, 7000, 8000, 10000, 12000, 14000, 15000],
        x_scale="log",
    )
    plots.append("microcluster-timbre-filters.svg")

    centers = np.asarray(residual["erb_centers_hz"], dtype=np.float64)
    write_svg_plot(
        output / "microcluster-residual-vs-theory.svg",
        "Timbre-Balanced Microcluster Residual versus Theory",
        [
            (
                f"{speaker} speaker",
                centers,
                np.asarray(residual[speaker], dtype=np.float64),
                color,
            )
            for speaker, color in (("left", "#2563eb"), ("right", "#059669"))
        ],
        "Auditory-band center frequency (Hz)",
        "Candidate minus theoretical microcluster energy (dB)",
        1500.0,
        12000.0,
        -8.0,
        8.0,
        [1500, 2000, 3000, 5000, 7000, 10000, 12000],
        x_scale="log",
    )
    plots.append("microcluster-residual-vs-theory.svg")

    k_response = {
        speaker: speaker_response(k_spectra, paths, frequencies)
        for speaker, paths in SPEAKER_PATHS.items()
    }
    l_response = {
        speaker: speaker_response(l_spectra, paths, frequencies)
        for speaker, paths in SPEAKER_PATHS.items()
    }
    audible = (frequencies >= 20.0) & (frequencies <= 20000.0)
    display_frequencies = np.geomspace(20.0, 20000.0, 1200)
    comparison_plot = f"k-versus-{DESIGN['plot_prefix']}-full-spectrum.svg"
    write_svg_plot(
        output / comparison_plot,
        f"Candidate K versus {DESIGN['candidate_display_name']}",
        [
            (
                f"{candidate} {speaker}",
                display_frequencies,
                np.interp(
                    display_frequencies,
                    frequencies[audible],
                    response[speaker][audible],
                ),
                color,
            )
            for candidate, response, speaker, color in (
                ("K", k_response, "left", "#93c5fd"),
                (DESIGN["candidate_label"], l_response, "left", "#2563eb"),
                ("K", k_response, "right", "#86efac"),
                (DESIGN["candidate_label"], l_response, "right", "#059669"),
            )
        ],
        "Frequency (Hz)",
        "1/6-octave binaural per-speaker energy (dB)",
        20.0,
        20000.0,
        -65.0,
        5.0,
        [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000],
        x_scale="log",
    )
    plots.append(comparison_plot)

    delta_plot = f"{DESIGN['plot_prefix']}-minus-k.svg"
    write_svg_plot(
        output / delta_plot,
        f"{DESIGN['candidate_display_name']} Minus Candidate K",
        [
            (
                f"{speaker} speaker",
                display_frequencies,
                np.interp(
                    display_frequencies,
                    frequencies[audible],
                    (l_response[speaker] - k_response[speaker])[audible],
                ),
                color,
            )
            for speaker, color in (("left", "#2563eb"), ("right", "#059669"))
        ],
        "Frequency (Hz)",
        f"{DESIGN['candidate_label']} minus K (dB)",
        20.0,
        20000.0,
        -6.0,
        1.0,
        [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000],
        x_scale="log",
    )
    plots.append(delta_plot)
    return plots


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ir-output", type=Path, default=OUTPUT_DIRECTORY)
    parser.add_argument("--analysis-output", type=Path, default=ANALYSIS_DIRECTORY)
    return parser.parse_args()


def main(args=None):
    if args is None:
        args = parse_args()
    direct_summary = load_verified_inputs(DIRECT_FILES, DIRECT_ANALYSIS.parent)
    h_summary = load_verified_inputs(H_FILES, H_ANALYSIS_DIRECTORY)
    k_summary = load_verified_inputs(K_FILES, K_ANALYSIS_DIRECTORY)
    timbre_summary = json.loads(
        (TIMBRE_ANALYSIS_DIRECTORY / "summary.json").read_text(encoding="utf-8")
    )
    if timbre_summary["decision"]["status"] != "branch-only correction warranted":
        raise ValueError("The timbre audit does not warrant this candidate")

    direct, sample_rate, _ = load_stereo_paths(DIRECT_FILES)
    candidate_c, c_rate, _ = load_stereo_paths(C_FILES)
    accepted_e, e_rate, _ = load_stereo_paths(E_FILES)
    accepted_k, k_rate, k_metadata = load_stereo_paths(K_FILES)
    if len({sample_rate, c_rate, e_rate, k_rate, DESIGN["sample_rate_hz"]}) != 1:
        raise ValueError("All renderer inputs must have the same sample rate")

    model = json.loads(
        (REPOSITORY / k_summary["directional_model_path"]).read_text(encoding="utf-8")
    )
    micro_j, _ = reconstruct_microclusters(
        direct,
        candidate_c,
        accepted_e,
        direct_summary,
        h_summary,
        sample_rate,
    )
    nfft = DESIGN["nfft"]
    frequencies = np.fft.rfftfreq(nfft, 1.0 / sample_rate)
    directional_requested, _ = requested_directional_corrections(
        model, direct, micro_j, sample_rate, frequencies
    )
    micro_k = {}
    for path in PATH_ORDER:
        impulse, _ = build_directional_filter(directional_requested[path])
        micro_k[path] = np.convolve(micro_j[path], impulse)[
            : DESIGN["output_length_samples"]
        ]
    if {
        path: array_sha256(values) for path, values in micro_k.items()
    } != k_summary["modified_microcluster_hashes"]:
        raise ValueError("Reconstructed candidate K microclusters changed")

    filters = {}
    filtered_micro = {}
    for speaker, paths in SPEAKER_PATHS.items():
        requested = requested_correction(frequencies, timbre_summary, speaker)
        impulse, spectrum = build_minimum_phase_filter(requested)
        filters[speaker] = {
            "requested": requested,
            "impulse": impulse,
            "spectrum": spectrum,
        }
        for path in paths:
            filtered_micro[path] = np.convolve(micro_k[path], impulse)[
                : DESIGN["output_length_samples"]
            ]

    candidate = {
        path: accepted_k[path] + filtered_micro[path] - micro_k[path]
        for path in PATH_ORDER
    }
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
        raise ValueError("Rendered candidate sample rate changed")

    spectra = {
        "K": {path: np.fft.rfft(values, nfft) for path, values in accepted_k.items()},
        "L": {path: np.fft.rfft(values, nfft) for path, values in rendered.items()},
        "micro_K": {path: np.fft.rfft(values, nfft) for path, values in micro_k.items()},
        "micro_L": {
            path: np.fft.rfft(values, nfft) for path, values in filtered_micro.items()
        },
    }
    responses = {
        candidate_name: {
            speaker: speaker_response(path_spectra, paths, frequencies)
            for speaker, paths in SPEAKER_PATHS.items()
        }
        for candidate_name, path_spectra in (("K", spectra["K"]), ("L", spectra["L"]))
    }
    centers = np.asarray(timbre_summary["erb_centers_hz"], dtype=np.float64)
    residual = {"erb_centers_hz": centers.tolist()}
    residual_metrics = {}
    for speaker in SPEAKER_PATHS:
        actual_filter = np.interp(
            centers, frequencies, db20(filters[speaker]["spectrum"])
        )
        current_excess = np.asarray(
            timbre_summary["curves"][speaker]["micro_current_minus_target_db"],
            dtype=np.float64,
        )
        residual[speaker] = (current_excess + actual_filter).tolist()
        residual_metrics[speaker] = band_stats(
            centers,
            residual[speaker],
            6000.0,
            10000.0,
        )

    band_deltas = {
        speaker: {
            label: response_band_delta(
                frequencies,
                responses["L"][speaker],
                responses["K"][speaker],
                low,
                high,
            )
            for low, high, label in (
                (20.0, 80.0, "20-80 Hz"),
                (200.0, 1800.0, "200 Hz-1.8 kHz"),
                (3000.0, 5000.0, "3-5 kHz"),
                (6000.0, 10000.0, "6-10 kHz"),
                (10000.0, 14000.0, "10-14 kHz"),
            )
        }
        for speaker in SPEAKER_PATHS
    }
    interaural_preservation = {}
    for speaker, paths in SPEAKER_PATHS.items():
        ratios = {}
        for name in ("micro_K", "micro_L"):
            raw_ratio = 10.0 * np.log10(
                np.maximum(np.square(np.abs(spectra[name][paths[0]])), 1e-30)
                / np.maximum(np.square(np.abs(spectra[name][paths[1]])), 1e-30)
            )
            ratios[name] = smooth_db_values(frequencies, raw_ratio)
        interaural_preservation[speaker] = response_band_delta(
            frequencies,
            ratios["micro_L"],
            ratios["micro_K"],
            6000.0,
            10000.0,
        )
    audible = (frequencies >= 20.0) & (frequencies <= 20000.0)
    correlated = (
        spectra["L"]["LL"] + spectra["L"]["RL"],
        spectra["L"]["LR"] + spectra["L"]["RR"],
    )
    maximum_correlated = max(
        float(np.max(np.abs(values[audible]))) for values in correlated
    )
    actual_filters = {speaker: values["spectrum"] for speaker, values in filters.items()}
    plots = write_plots(
        args.analysis_output,
        frequencies,
        actual_filters,
        spectra["K"],
        spectra["L"],
        residual,
    )
    summary = {
        "schema_version": 1,
        "status": DESIGN["status"],
        "design": DESIGN,
        "candidate_k_files": k_metadata,
        "candidate_k_rendered_hashes": {
            side: k_summary["rendered_files"][side]["sha256"] for side in K_FILES
        },
        "timbre_audit": display_path(TIMBRE_ANALYSIS_DIRECTORY / "summary.json"),
        "direct_peak_samples": {
            path: int(direct_summary["paths"][path]["peak_sample"])
            for path in PATH_ORDER
        },
        "filter_response_db": {
            speaker: {
                str(frequency): finite_float(
                    np.interp(frequency, frequencies, db20(filters[speaker]["spectrum"])),
                    6,
                )
                for frequency in (4000, 5000, 6000, 7000, 8000, 10000, 12000, 14000)
            }
            for speaker in SPEAKER_PATHS
        },
        "filter_impulse_first_nonzero_sample": {
            speaker: int(
                np.flatnonzero(np.abs(filters[speaker]["impulse"]) > 1e-15)[0]
            )
            for speaker in SPEAKER_PATHS
        },
        "microcluster_residual_vs_theory_6_10_khz": residual_metrics,
        "microcluster_interaural_ratio_delta_6_10_khz": interaural_preservation,
        "response_delta_balanced_minus_k": band_deltas,
        "modeled_correlated_renderer_gain_db": finite_float(
            20.0 * math.log10(max(maximum_correlated, 1e-30)), 6
        ),
        "rendered_files": rendered_files,
        "plots": plots,
    }
    args.analysis_output.mkdir(parents=True, exist_ok=True)
    (args.analysis_output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        f"# {DESIGN['candidate_display_name']}",
        "",
        "This opt-in candidate keeps K's personal direct sound, bass, treated specular field, late field, timing, and directional interaural ratios. It changes only the shared spectral envelope of each virtual speaker's deterministic microcluster branch.",
        "",
        "## Design",
        "",
        "- The ERB-smoothed K-minus-theoretical excess is converted to attenuation only; no deficient band is boosted.",
        (
            f"- Correction fades in from {DESIGN['correction_support_hz'][0] / 1000:g}-"
            f"{DESIGN['correction_full_strength_hz'][0] / 1000:g} kHz, remains active through "
            f"{DESIGN['correction_full_strength_hz'][1] / 1000:g} kHz, and fades out by "
            f"{DESIGN['correction_support_hz'][1] / 1000:g} kHz."
        ),
        "- The same causal minimum-phase filter is applied to both ear paths from each speaker, preserving directional ratios and adding no bulk delay.",
        "",
        "## Offline Result",
        "",
        "| Speaker | Residual microcluster excess, 6-10 kHz | Complete response change, 6-10 kHz |",
        "| --- | ---: | ---: |",
    ]
    for speaker in SPEAKER_PATHS:
        lines.append(
            f"| {speaker.title()} | {residual_metrics[speaker]['mean_db']:+.2f} dB | "
            f"{band_deltas[speaker]['6-10 kHz']['mean_db']:+.2f} dB |"
        )
    lines.extend(
        [
            "",
            f"Modeled maximum correlated gain: {summary['modeled_correlated_renderer_gain_db']:+.2f} dB.",
            "",
            "## Plots",
            "",
            *[f"- `{plot}`" for plot in plots],
        ]
    )
    (args.analysis_output / "report.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "residual_6_10_khz": residual_metrics,
        "complete_delta_6_10_khz": {
            speaker: band_deltas[speaker]["6-10 kHz"] for speaker in SPEAKER_PATHS
        },
        "modeled_correlated_renderer_gain_db": summary["modeled_correlated_renderer_gain_db"],
    }, indent=2))


if __name__ == "__main__":
    main()
