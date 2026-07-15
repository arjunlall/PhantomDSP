#!/usr/bin/env python3
"""Audit candidate K's added-room timbre against its theoretical room model."""

import argparse
import json
import math
from pathlib import Path

import numpy as np

from analyze_baseline import finite_float, write_svg_plot
from render_directional_diffuse_room import (
    ANALYSIS_DIRECTORY as K_ANALYSIS_DIRECTORY,
    DESIGN as K_DESIGN,
    DIRECTIONAL_MODEL,
    H_FILES,
    J_FILES,
    OUTPUT_DIRECTORY as K_OUTPUT_DIRECTORY,
    OUTPUT_FILES as K_OUTPUT_FILES,
    PATH_EAR,
    SPEAKER_PATHS,
    build_minimum_phase_filter,
    correction_window,
    reconstruct_microclusters,
    requested_directional_corrections,
)
from render_idealized_treated_room import (
    ANALYSIS_DIRECTORY as H_ANALYSIS_DIRECTORY,
    C_FILES,
    E_FILES,
)
from render_soffit_mastering_room import (
    DESIGN as G_DESIGN,
    SURFACES,
    render_specular_paths,
    source_directivity_filter,
)
from render_synthetic_direct import PATH_ORDER, REPOSITORY, load_stereo_paths
from render_synthetic_early_room import DIRECT_ANALYSIS, DIRECT_FILES
from render_synthetic_late_room import pad_to
from render_theoretical_early_room import (
    array_sha256,
    load_verified_inputs,
    one_pole_high_shelf_impulse,
)
from render_tonally_normalized_room import PROFILES


K_FILES = {
    side: K_OUTPUT_DIRECTORY / filename
    for side, filename in K_OUTPUT_FILES.items()
}
J_PROFILE = PROFILES["J"]
ANALYSIS_DIRECTORY = (
    REPOSITORY
    / "measurements"
    / "synthetic-reference-room"
    / "directional-diffuse"
    / "timbre-analysis"
)
DESIGN = {
    "analysis_band_hz": [1500.0, 12000.0],
    "decision_band_hz": [6000.0, 10000.0],
    "anchor_band_hz": [800.0, 1250.0],
    "erb_rate_step": 0.5,
    "broad_excess_threshold_db": 1.0,
    "target": (
        "personal direct power multiplied by the K directional-HRTF ratios, "
        "G speaker directivity, and G treated-surface absorption"
    ),
    "surface_energy_weights": dict(K_DESIGN["direction_energy_weights"]),
    "surface_weights_define_1khz_energy_share": True,
    "raw_old_room_waveform_used": False,
    "old_room_octave_targets_used_in_reference": False,
    "research_sources": {
        "auditory_filter_bandwidth": "https://pubmed.ncbi.nlm.nih.gov/6630731/",
        "reflection_timbre_and_detection": "https://secure.aes.org/forum/pubs/journal/?elib=6079",
    },
}
BANDS = (
    (1500.0, 3000.0, "1.5-3 kHz"),
    (3000.0, 5000.0, "3-5 kHz"),
    (5000.0, 7000.0, "5-7 kHz"),
    (7000.0, 10000.0, "7-10 kHz"),
    (10000.0, 12000.0, "10-12 kHz"),
)


def display_path(path):
    try:
        return str(path.relative_to(REPOSITORY))
    except ValueError:
        return str(path)


def erb_width_hz(frequency_hz):
    """Moore-Glasberg equivalent rectangular bandwidth."""
    values = np.asarray(frequency_hz, dtype=np.float64)
    return 24.7 * (1.0 + 4.37 * values / 1000.0)


def erb_rate(frequency_hz):
    values = np.asarray(frequency_hz, dtype=np.float64)
    return 21.4 * np.log10(1.0 + 4.37 * values / 1000.0)


def frequency_from_erb_rate(rate):
    values = np.asarray(rate, dtype=np.float64)
    return 1000.0 / 4.37 * (np.power(10.0, values / 21.4) - 1.0)


def erb_centers(low_hz, high_hz, step=0.5):
    low_rate = float(erb_rate(low_hz))
    high_rate = float(erb_rate(high_hz))
    rates = np.arange(low_rate, high_rate + step * 0.5, step)
    centers = frequency_from_erb_rate(rates)
    return centers[centers <= high_hz * (1.0 + 1e-12)]


def roex_weights(frequencies, center_hz):
    """Symmetric rounded-exponential approximation to one auditory filter."""
    center = float(center_hz)
    p = 4.0 * center / float(erb_width_hz(center))
    relative = np.abs(np.asarray(frequencies, dtype=np.float64) - center) / center
    weights = (1.0 + p * relative) * np.exp(-p * relative)
    weights[0] = 0.0
    return weights / max(float(np.sum(weights)), 1e-30)


def auditory_band_power(frequencies, power, centers):
    values = np.asarray(power, dtype=np.float64)
    return np.asarray(
        [
            float(np.sum(roex_weights(frequencies, center) * values))
            for center in centers
        ],
        dtype=np.float64,
    )


def db_power_ratio(numerator, denominator):
    return 10.0 * np.log10(
        np.maximum(numerator, 1e-30) / np.maximum(denominator, 1e-30)
    )


def fused_power(spectra, paths):
    return sum(np.square(np.abs(spectra[path])) for path in paths)


def normalized_filter_power(impulse, nfft, frequencies, anchor_hz=1000.0):
    power = np.square(np.abs(np.fft.rfft(impulse, nfft)))
    anchor = float(np.interp(anchor_hz, frequencies, power))
    return power / max(anchor, 1e-30)


def surface_off_axis_angles(reflection_metadata):
    output = {}
    for speaker, paths in SPEAKER_PATHS.items():
        output[speaker] = {}
        for surface in DESIGN["surface_energy_weights"]:
            angles = [
                entry["speaker_off_axis_degrees"]
                for path in paths
                for entry in reflection_metadata[path]
                if entry["surface"] == surface
            ]
            if not angles:
                raise ValueError(f"Missing {speaker} {surface} reflection metadata")
            output[speaker][surface] = float(np.mean(angles))
    return output


def theoretical_microcluster_power(
    frequencies,
    nfft,
    sample_rate,
    direct_spectra,
    current_micro_spectra,
    model,
    reflection_metadata,
    directivity_strength=1.0,
    absorption_strength=1.0,
):
    """Return per-path diffuse power predicted by the designed room surfaces."""
    model_frequencies = np.asarray(model["frequencies_hz"], dtype=np.float64)
    window = correction_window(frequencies)
    weights = DESIGN["surface_energy_weights"]
    angles = surface_off_axis_angles(reflection_metadata)
    surface_power = {speaker: {} for speaker in SPEAKER_PATHS}
    for speaker in SPEAKER_PATHS:
        for surface_name in weights:
            directivity, _, _ = source_directivity_filter(
                sample_rate, angles[speaker][surface_name]
            )
            surface = SURFACES[surface_name]
            absorption = one_pole_high_shelf_impulse(
                sample_rate,
                surface["absorption_cutoff_hz"],
                surface["high_frequency_ratio"],
                G_DESIGN["directional_shadow"]["filter_samples"],
            )
            directivity_power = normalized_filter_power(
                directivity, nfft, frequencies
            )
            absorption_power = normalized_filter_power(
                absorption, nfft, frequencies
            )
            surface_power[speaker][surface_name] = (
                np.power(directivity_power, directivity_strength)
                * np.power(absorption_power, absorption_strength)
            )

    target = {}
    scales = {}
    for speaker, paths in SPEAKER_PATHS.items():
        raw = {}
        for path in paths:
            ear = PATH_EAR[path]
            directional_power = np.zeros_like(frequencies)
            for surface_name, weight in weights.items():
                delta = np.asarray(
                    model["directional_delta_db"][speaker][surface_name][ear],
                    dtype=np.float64,
                )
                interpolated = np.interp(
                    frequencies,
                    model_frequencies,
                    delta,
                    left=float(delta[0]),
                    right=float(delta[-1]),
                )
                hrtf_ratio = np.power(10.0, interpolated * window / 10.0)
                directional_power += (
                    weight
                    * surface_power[speaker][surface_name]
                    * hrtf_ratio
                )
            raw[path] = np.square(np.abs(direct_spectra[path])) * directional_power

        anchor = (frequencies >= DESIGN["anchor_band_hz"][0]) & (
            frequencies <= DESIGN["anchor_band_hz"][1]
        )
        current_anchor = sum(
            float(np.sum(np.square(np.abs(current_micro_spectra[path][anchor]))))
            for path in paths
        )
        target_anchor = sum(float(np.sum(raw[path][anchor])) for path in paths)
        scale = current_anchor / max(target_anchor, 1e-30)
        scales[speaker] = scale
        for path in paths:
            target[path] = raw[path] * scale
    return target, scales, angles, surface_power


def band_stats(centers, values, low_hz, high_hz):
    selected = (centers >= low_hz) & (centers <= high_hz)
    data = np.asarray(values)[selected]
    return {
        "mean_db": finite_float(np.mean(data), 6),
        "rms_db": finite_float(np.sqrt(np.mean(np.square(data))), 6),
        "minimum_db": finite_float(np.min(data), 6),
        "maximum_db": finite_float(np.max(data), 6),
    }


def write_plots(output, centers, curves, sensitivity_curves):
    output.mkdir(parents=True, exist_ok=True)
    plots = []
    ticks = [1500, 2000, 3000, 5000, 7000, 10000, 12000]
    colors = {
        "left_current": "#2563eb",
        "left_target": "#93c5fd",
        "right_current": "#059669",
        "right_target": "#86efac",
    }
    series = []
    for speaker in SPEAKER_PATHS:
        series.extend(
            [
                (
                    f"K {speaker} microclusters",
                    centers,
                    curves[speaker]["micro_relative_direct_db"],
                    colors[f"{speaker}_current"],
                ),
                (
                    f"theoretical {speaker} microclusters",
                    centers,
                    curves[speaker]["target_micro_relative_direct_db"],
                    colors[f"{speaker}_target"],
                ),
            ]
        )
    values = np.concatenate([item[2] for item in series])
    write_svg_plot(
        output / "microcluster-envelope-vs-theory.svg",
        "Candidate K Microcluster Envelope versus Theoretical Treated Room",
        series,
        "Auditory-band center frequency (Hz)",
        "Microcluster energy relative to personal direct (dB)",
        1500.0,
        12000.0,
        math.floor(float(np.min(values)) / 2.0) * 2.0,
        math.ceil(float(np.max(values)) / 2.0) * 2.0,
        ticks,
        x_scale="log",
    )
    plots.append("microcluster-envelope-vs-theory.svg")

    delta_values = np.concatenate(
        [curves[speaker]["micro_current_minus_target_db"] for speaker in SPEAKER_PATHS]
    )
    limit = max(2.0, math.ceil(float(np.max(np.abs(delta_values))) * 2.0) / 2.0)
    write_svg_plot(
        output / "microcluster-current-minus-theory.svg",
        "Candidate K Microcluster Excess over Theoretical Treated Room",
        [
            (
                f"{speaker} speaker",
                centers,
                curves[speaker]["micro_current_minus_target_db"],
                colors[f"{speaker}_current"],
            )
            for speaker in SPEAKER_PATHS
        ],
        "Auditory-band center frequency (Hz)",
        "K minus theoretical microcluster energy (dB)",
        1500.0,
        12000.0,
        -limit,
        limit,
        ticks,
        x_scale="log",
    )
    plots.append("microcluster-current-minus-theory.svg")

    write_svg_plot(
        output / "microcluster-model-sensitivity.svg",
        "Candidate K Microcluster Excess: Room-Model Sensitivity",
        [
            (
                label,
                centers,
                values,
                color,
            )
            for (label, values), color in zip(
                sensitivity_curves.items(),
                ("#2563eb", "#7c3aed", "#d97706", "#059669", "#6b7280"),
            )
        ],
        "Auditory-band center frequency (Hz)",
        "Mean K minus theoretical microcluster energy (dB)",
        1500.0,
        12000.0,
        -18.0,
        18.0,
        ticks,
        x_scale="log",
    )
    plots.append("microcluster-model-sensitivity.svg")

    for speaker, color in (("left", "#2563eb"), ("right", "#059669")):
        filename = f"{speaker}-auditory-room-contribution.svg"
        room_curves = [
            curves[speaker]["coherent_complete_relative_direct_db"],
            curves[speaker]["diffuse_bound_relative_direct_db"],
            curves[speaker]["theoretical_bound_relative_direct_db"],
        ]
        values = np.concatenate(room_curves)
        write_svg_plot(
            output / filename,
            f"Candidate K {speaker.title()} Speaker Auditory-Band Room Contribution",
            [
                (
                    "complete K, coherent",
                    centers,
                    room_curves[0],
                    "#6b7280",
                ),
                (
                    "K diffuse-energy bound",
                    centers,
                    room_curves[1],
                    color,
                ),
                (
                    "theoretical treated-room bound",
                    centers,
                    room_curves[2],
                    "#d97706",
                ),
            ],
            "Auditory-band center frequency (Hz)",
            "Complete/direct room contribution (dB)",
            1500.0,
            12000.0,
            math.floor(float(np.min(values)) / 2.0) * 2.0,
            math.ceil(float(np.max(values)) / 2.0) * 2.0,
            ticks,
            x_scale="log",
        )
        plots.append(filename)
    return plots


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-output", type=Path, default=ANALYSIS_DIRECTORY)
    return parser.parse_args()


def main():
    args = parse_args()
    direct_summary = load_verified_inputs(DIRECT_FILES, DIRECT_ANALYSIS.parent)
    h_summary = load_verified_inputs(H_FILES, H_ANALYSIS_DIRECTORY)
    load_verified_inputs(J_FILES, J_PROFILE["analysis_output"])
    k_summary = load_verified_inputs(K_FILES, K_ANALYSIS_DIRECTORY)
    direct, sample_rate, _ = load_stereo_paths(DIRECT_FILES)
    candidate_c, c_rate, _ = load_stereo_paths(C_FILES)
    accepted_e, e_rate, _ = load_stereo_paths(E_FILES)
    accepted_h, h_rate, _ = load_stereo_paths(H_FILES)
    accepted_j, j_rate, _ = load_stereo_paths(J_FILES)
    accepted_k, k_rate, _ = load_stereo_paths(K_FILES)
    if len({sample_rate, c_rate, e_rate, h_rate, j_rate, k_rate}) != 1:
        raise ValueError("All renderer inputs must have the same sample rate")

    model = json.loads(DIRECTIONAL_MODEL.read_text(encoding="utf-8"))
    micro_j, _ = reconstruct_microclusters(
        direct,
        candidate_c,
        accepted_e,
        direct_summary,
        h_summary,
        sample_rate,
    )
    nfft = K_DESIGN["nfft"]
    frequencies = np.fft.rfftfreq(nfft, 1.0 / sample_rate)
    requested, _ = requested_directional_corrections(
        model, direct, micro_j, sample_rate, frequencies
    )
    micro_k = {}
    for path in PATH_ORDER:
        impulse, _ = build_minimum_phase_filter(requested[path])
        micro_k[path] = np.convolve(micro_j[path], impulse)[
            : K_DESIGN["output_length_samples"]
        ]
    expected_hashes = k_summary["modified_microcluster_hashes"]
    if {path: array_sha256(values) for path, values in micro_k.items()} != expected_hashes:
        raise ValueError("Reconstructed K microclusters no longer match the K summary")

    output_length = K_DESIGN["output_length_samples"]
    direct_padded = {path: pad_to(values, output_length) for path, values in direct.items()}
    c_padded = {path: pad_to(values, output_length) for path, values in candidate_c.items()}
    e_padded = {path: pad_to(values, output_length) for path, values in accepted_e.items()}
    late = {path: e_padded[path] - c_padded[path] for path in PATH_ORDER}
    h_early = {
        path: accepted_h[path] - direct_padded[path] - late[path]
        for path in PATH_ORDER
    }
    spectra = {
        "H": {path: np.fft.rfft(values, nfft) for path, values in accepted_h.items()},
        "J": {path: np.fft.rfft(values, nfft) for path, values in accepted_j.items()},
        "K": {path: np.fft.rfft(values, nfft) for path, values in accepted_k.items()},
        "direct_raw": {
            path: np.fft.rfft(values, nfft) for path, values in direct_padded.items()
        },
        "late_raw": {path: np.fft.rfft(values, nfft) for path, values in late.items()},
        "h_early_raw": {
            path: np.fft.rfft(values, nfft) for path, values in h_early.items()
        },
        "micro_j_raw": {path: np.fft.rfft(values, nfft) for path, values in micro_j.items()},
        "micro_k_raw": {path: np.fft.rfft(values, nfft) for path, values in micro_k.items()},
    }
    common_filter = {}
    for speaker, paths in SPEAKER_PATHS.items():
        numerator = sum(
            np.conj(spectra["H"][path]) * spectra["J"][path] for path in paths
        )
        denominator = sum(np.square(np.abs(spectra["H"][path])) for path in paths)
        common_filter[speaker] = numerator / np.maximum(denominator, 1e-30)

    components = {name: {} for name in ("direct", "specular", "micro", "late", "no_micro")}
    for speaker, paths in SPEAKER_PATHS.items():
        common = common_filter[speaker]
        for path in paths:
            components["direct"][path] = spectra["direct_raw"][path] * common
            components["specular"][path] = (
                spectra["h_early_raw"][path] - spectra["micro_j_raw"][path]
            ) * common
            components["micro"][path] = (
                spectra["micro_j_raw"][path] * common
                + spectra["micro_k_raw"][path]
                - spectra["micro_j_raw"][path]
            )
            components["late"][path] = spectra["late_raw"][path] * common
            components["no_micro"][path] = (
                components["direct"][path]
                + components["specular"][path]
                + components["late"][path]
            )

    direct_peaks = {
        path: int(direct_summary["paths"][path]["peak_sample"]) for path in PATH_ORDER
    }
    _, _, reflection_metadata = render_specular_paths(
        direct, direct_peaks, sample_rate
    )
    scenarios = {
        "full treated-room model": (1.0, 1.0),
        "half-strength losses": (0.5, 0.5),
        "speaker directivity only": (1.0, 0.0),
        "surface absorption only": (0.0, 1.0),
        "directional HRTF only": (0.0, 0.0),
    }
    scenario_targets = {}
    scenario_scales = {}
    angles = None
    for name, (directivity_strength, absorption_strength) in scenarios.items():
        target, scales, scenario_angles, _ = theoretical_microcluster_power(
            frequencies,
            nfft,
            sample_rate,
            components["direct"],
            components["micro"],
            model,
            reflection_metadata,
            directivity_strength=directivity_strength,
            absorption_strength=absorption_strength,
        )
        scenario_targets[name] = target
        scenario_scales[name] = scales
        if angles is None:
            angles = scenario_angles
    target_power = scenario_targets["full treated-room model"]

    centers = erb_centers(
        DESIGN["analysis_band_hz"][0],
        DESIGN["analysis_band_hz"][1],
        DESIGN["erb_rate_step"],
    )
    curves = {}
    band_metrics = {}
    for speaker, paths in SPEAKER_PATHS.items():
        direct_power = fused_power(components["direct"], paths)
        no_micro_power = fused_power(components["no_micro"], paths)
        micro_power = fused_power(components["micro"], paths)
        complete_power = fused_power(spectra["K"], paths)
        theoretical_micro = sum(target_power[path] for path in paths)
        auditory = {
            "direct": auditory_band_power(frequencies, direct_power, centers),
            "no_micro": auditory_band_power(frequencies, no_micro_power, centers),
            "micro": auditory_band_power(frequencies, micro_power, centers),
            "complete": auditory_band_power(frequencies, complete_power, centers),
            "target_micro": auditory_band_power(
                frequencies, theoretical_micro, centers
            ),
        }
        current_bound = auditory["no_micro"] + auditory["micro"]
        theoretical_bound = auditory["no_micro"] + auditory["target_micro"]
        curves[speaker] = {
            "micro_relative_direct_db": db_power_ratio(
                auditory["micro"], auditory["direct"]
            ),
            "target_micro_relative_direct_db": db_power_ratio(
                auditory["target_micro"], auditory["direct"]
            ),
            "micro_current_minus_target_db": db_power_ratio(
                auditory["micro"], auditory["target_micro"]
            ),
            "coherent_complete_relative_direct_db": db_power_ratio(
                auditory["complete"], auditory["direct"]
            ),
            "diffuse_bound_relative_direct_db": db_power_ratio(
                current_bound, auditory["direct"]
            ),
            "theoretical_bound_relative_direct_db": db_power_ratio(
                theoretical_bound, auditory["direct"]
            ),
            "coherent_micro_effect_db": db_power_ratio(
                auditory["complete"], auditory["no_micro"]
            ),
            "diffuse_micro_effect_db": db_power_ratio(
                current_bound, auditory["no_micro"]
            ),
            "theoretical_micro_effect_db": db_power_ratio(
                theoretical_bound, auditory["no_micro"]
            ),
        }
        band_metrics[speaker] = {
            label: {
                "micro_current_minus_target": band_stats(
                    centers,
                    curves[speaker]["micro_current_minus_target_db"],
                    low,
                    high,
                ),
                "coherent_micro_effect": band_stats(
                    centers,
                    curves[speaker]["coherent_micro_effect_db"],
                    low,
                    high,
                ),
                "diffuse_micro_effect": band_stats(
                    centers,
                    curves[speaker]["diffuse_micro_effect_db"],
                    low,
                    high,
                ),
                "theoretical_micro_effect": band_stats(
                    centers,
                    curves[speaker]["theoretical_micro_effect_db"],
                    low,
                    high,
                ),
            }
            for low, high, label in BANDS
        }

    sensitivity_curves = {}
    sensitivity_metrics = {}
    for name, target in scenario_targets.items():
        per_speaker = {}
        deltas = []
        for speaker, paths in SPEAKER_PATHS.items():
            current = auditory_band_power(
                frequencies, fused_power(components["micro"], paths), centers
            )
            predicted = auditory_band_power(
                frequencies, sum(target[path] for path in paths), centers
            )
            delta = db_power_ratio(current, predicted)
            deltas.append(delta)
            per_speaker[speaker] = band_stats(
                centers,
                delta,
                DESIGN["decision_band_hz"][0],
                DESIGN["decision_band_hz"][1],
            )
        sensitivity_curves[name] = np.mean(deltas, axis=0)
        sensitivity_metrics[name] = per_speaker

    decision_stats = {
        speaker: band_stats(
            centers,
            curves[speaker]["micro_current_minus_target_db"],
            DESIGN["decision_band_hz"][0],
            DESIGN["decision_band_hz"][1],
        )
        for speaker in SPEAKER_PATHS
    }
    threshold = DESIGN["broad_excess_threshold_db"]
    half_strength_stats = sensitivity_metrics["half-strength losses"]
    correction_warranted = all(
        decision_stats[speaker]["mean_db"] > threshold
        and half_strength_stats[speaker]["mean_db"] > threshold
        and band_stats(
            centers,
            curves[speaker]["coherent_micro_effect_db"],
            DESIGN["decision_band_hz"][0],
            DESIGN["decision_band_hz"][1],
        )["mean_db"]
        > threshold
        for speaker in SPEAKER_PATHS
    )
    plots = write_plots(
        args.analysis_output, centers, curves, sensitivity_curves
    )

    reconstructed = {
        path: components["no_micro"][path] + components["micro"][path]
        for path in PATH_ORDER
    }
    reconstruction_delta = {
        path: finite_float(
            np.sqrt(
                np.mean(
                    np.square(
                        np.abs(reconstructed[path] - spectra["K"][path])
                    )
                )
            )
            / max(
                np.sqrt(np.mean(np.square(np.abs(spectra["K"][path])))),
                1e-30,
            ),
            9,
        )
        for path in PATH_ORDER
    }
    summary = {
        "schema_version": 1,
        "status": "candidate K auditory-band timbre audit",
        "design": DESIGN,
        "candidate_k_summary": display_path(K_ANALYSIS_DIRECTORY / "summary.json"),
        "directional_model": display_path(DIRECTIONAL_MODEL),
        "erb_centers_hz": [finite_float(value, 3) for value in centers],
        "surface_off_axis_degrees": {
            speaker: {
                surface: finite_float(value, 6)
                for surface, value in surfaces.items()
            }
            for speaker, surfaces in angles.items()
        },
        "theoretical_target_anchor_scale": {
            scenario: {
                speaker: finite_float(value, 9)
                for speaker, value in scales.items()
            }
            for scenario, scales in scenario_scales.items()
        },
        "component_reconstruction_relative_rms": reconstruction_delta,
        "band_metrics": band_metrics,
        "model_sensitivity_6_10_khz": sensitivity_metrics,
        "decision": {
            "status": (
                "branch-only correction warranted"
                if correction_warranted
                else "no branch-only correction warranted"
            ),
            "rule": (
                "full and half-strength room models each predict more than "
                f"{threshold:.1f} dB less microcluster energy from 6-10 kHz, "
                "and K's coherent microcluster contribution also exceeds "
                f"{threshold:.1f} dB, in both speakers"
            ),
            "six_to_ten_khz": decision_stats,
        },
        "curves": {
            speaker: {
                name: [finite_float(value, 6) for value in values]
                for name, values in speaker_curves.items()
            }
            for speaker, speaker_curves in curves.items()
        },
        "plots": plots,
    }
    args.analysis_output.mkdir(parents=True, exist_ok=True)
    (args.analysis_output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    lines = [
        "# Candidate K Timbre Audit",
        "",
        "This audit tests whether K's deterministic microclusters add too much broad upper-frequency energy. It evaluates auditory-band power rather than raw comb-filter teeth.",
        "",
        "## Method",
        "",
        "- Reconstruct K's personal direct, treated specular, directional microcluster, and synthetic late branches.",
        "- Integrate their spectra with symmetric Moore-Glasberg ERB-spaced rounded-exponential filters from 1.5-12 kHz.",
        "- Calculate both K's coherent complete response and a decorrelated energy bound.",
        "- Predict the diffuse envelope from the personal direct paths, matched directional HRTF ratios, modeled monitor directivity, and treated-surface absorption.",
        "- Anchor theoretical and current microcluster power only from 800 Hz-1.25 kHz. No old-room upper-frequency target is used in the theoretical curve.",
        "",
        "## Result",
        "",
        f"Decision: **{summary['decision']['status']}**.",
        "",
        "| Speaker | 6-10 kHz mean K minus theory | RMS | Range |",
        "| --- | ---: | ---: | ---: |",
    ]
    for speaker in SPEAKER_PATHS:
        metrics = decision_stats[speaker]
        lines.append(
            f"| {speaker.title()} | {metrics['mean_db']:+.2f} dB | "
            f"{metrics['rms_db']:.2f} dB | "
            f"{metrics['minimum_db']:+.2f} to {metrics['maximum_db']:+.2f} dB |"
        )
    lines.extend(
        [
            "",
            "## Model Sensitivity",
            "",
            "| Scenario | Left 6-10 kHz K minus theory | Right 6-10 kHz K minus theory |",
            "| --- | ---: | ---: |",
        ]
    )
    for scenario, metrics in sensitivity_metrics.items():
        lines.append(
            f"| {scenario} | {metrics['left']['mean_db']:+.2f} dB | "
            f"{metrics['right']['mean_db']:+.2f} dB |"
        )
    lines.extend(
        [
            "",
            "## Band Detail",
            "",
            "| Band | Left K minus theory | Right K minus theory | Left net coherent effect | Right net coherent effect |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for _, _, label in BANDS:
        left = band_metrics["left"][label]
        right = band_metrics["right"][label]
        lines.append(
            f"| {label} | {left['micro_current_minus_target']['mean_db']:+.2f} dB | "
            f"{right['micro_current_minus_target']['mean_db']:+.2f} dB | "
            f"{left['coherent_micro_effect']['mean_db']:+.2f} dB | "
            f"{right['coherent_micro_effect']['mean_db']:+.2f} dB |"
        )
    lines.extend(
        [
            "",
            "The theoretical envelope is a model of this repository's intended room, not a universal mastering-room target. A correction is justified only when the discrepancy is broad, consistent between speakers, and large enough to survive auditory-band smoothing.",
            "",
            "## Research Basis",
            "",
            "- [Moore and Glasberg, Suggested formulae for calculating auditory-filter bandwidths and excitation patterns](https://pubmed.ncbi.nlm.nih.gov/6630731/)",
            "- [Olive and Toole, The Detection of Reflections in Typical Rooms](https://secure.aes.org/forum/pubs/journal/?elib=6079)",
            "",
            "## Plots",
            "",
            *[f"- `{plot}`" for plot in plots],
        ]
    )
    (args.analysis_output / "report.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary["decision"], indent=2))


if __name__ == "__main__":
    main()
