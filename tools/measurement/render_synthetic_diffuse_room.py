#!/usr/bin/env python3
"""Render candidate E: candidate C plus a synthetic binaural diffuse late field."""

import argparse
import json
import math
from pathlib import Path

import numpy as np

from analyze_baseline import finite_float, sha256, write_svg_plot
from analyze_synthetic_late_field import (
    energy_db,
    energy_decay_db,
    extrapolated_decay_seconds,
    maximum_correlation,
)
from explore_minimum_latency_renderer import minimum_phase_spectrum
from render_active_renderer import write_pcm24
from render_synthetic_direct import PATH_ORDER, REPOSITORY, load_stereo_paths
from render_synthetic_early_room import (
    ANALYSIS_DIRECTORY as EARLY_ANALYSIS_DIRECTORY,
    OUTPUT_DIRECTORY as EARLY_OUTPUT_DIRECTORY,
    OUTPUT_FILES as EARLY_OUTPUT_FILES,
    apply_biquad,
    band_metrics,
    rbj_highpass_coefficients,
    smoothed_db,
)
from render_synthetic_late_room import pad_to


EARLY_FILES = {
    side: EARLY_OUTPUT_DIRECTORY / filename
    for side, filename in EARLY_OUTPUT_FILES.items()
}
EARLY_ANALYSIS = EARLY_ANALYSIS_DIRECTORY / "summary.json"
TARGET_SUMMARY = (
    REPOSITORY
    / "measurements"
    / "synthetic-reference-room"
    / "personal-late-control"
    / "characterization"
    / "summary.json"
)
OUTPUT_DIRECTORY = REPOSITORY / "Synthetic Reference Room" / "IRs" / "synthetic-late"
ANALYSIS_DIRECTORY = (
    REPOSITORY
    / "measurements"
    / "synthetic-reference-room"
    / "synthetic-late"
    / "analysis"
)
OUTPUT_FILES = {
    "left": "Synthetic Late Field Left Speaker.wav",
    "right": "Synthetic Late Field Right Speaker.wav",
}
DESIGN = {
    "sample_rate_hz": 48000,
    "output_length_samples": 32768,
    "late_transition_ms": [25.0, 30.0],
    "noise_preroll_ms": 100.0,
    "final_fade_ms": 25.0,
    "random_seed": 20260714,
    "spectral_calibration_iterations": 8,
    "spectral_correction_fir_samples": 2048,
    "spectral_correction_limit_db": 6.0,
    "coherence_mix_scale_above_250_hz": 0.6,
    "late_highpass": {
        "type": "cascaded RBJ Butterworth biquads (Linkwitz-Riley fourth order)",
        "cutoff_hz": 250.0,
        "q": 1.0 / math.sqrt(2.0),
        "sections": 2,
    },
    "source_model": "independent deterministic Gaussian injections with a frequency-dependent shared ear component",
    "normalization": "equal energy in all four late paths, then one global target-ratio scale",
}
LISTENING_RESULT = {
    "date": "2026-07-14",
    "method": "informal sighted A/D/E comparison with unchanged downstream filters",
    "result": "no obvious difference between D and E; E sounded great and preserved the intended speaker placement",
    "spatial_observation": "A sounded narrower, approximately 20-25 degrees per side, while D and E matched the intended plus/minus 30-degree geometry",
    "interpretation": "the synthetic late field replaced D's measured late waveform without an obvious perceptual loss",
    "limitations": "not blinded or independently level matched; apparent angles are subjective estimates",
}
WINDOWS_BENCHMARK_RESULT = {
    "date": "2026-07-14",
    "commit": "1fa8dc2e8e760e2daba8db02e023f446535d804f",
    "device": "Output A1 Voicemeeter",
    "renderer_sha256": "5222eef0050b8e6d254a71dc505f0c20d532bc4a5f5ff487745ec83114c49d74",
    "result": "three probes passed with expected renderer, WAV, and 2x2 routing loads; no clipping or configuration-error markers",
    "left_impulse_peak_dbfs": -25.065376,
    "right_impulse_peak_dbfs": -25.842562,
    "correlated_sweep_peak_dbfs": -4.606780,
    "single_core_cpu_percent_range": [0.60, 0.67],
    "capture_location": "temporary Windows evidence; not checked into the repository",
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
    edge_ratio = math.sqrt(2.0)
    q = 1.0 / math.sqrt(2.0)
    numerator, denominator = rbj_highpass_coefficients(
        sample_rate, center_hz / edge_ratio, q
    )
    filtered = apply_biquad(values, numerator, denominator)
    numerator, denominator = rbj_lowpass_coefficients(
        sample_rate, center_hz * edge_ratio, q
    )
    return apply_biquad(filtered, numerator, denominator)


def apply_late_highpass(values, sample_rate):
    definition = DESIGN["late_highpass"]
    numerator, denominator = rbj_highpass_coefficients(
        sample_rate, definition["cutoff_hz"], definition["q"]
    )
    filtered = values
    for _ in range(definition["sections"]):
        filtered = apply_biquad(filtered, numerator, denominator)
    return filtered


def raised_cosine_fade_in(length):
    phase = np.linspace(0.0, math.pi, length, endpoint=True)
    return 0.5 - 0.5 * np.cos(phase)


def raised_cosine_fade_out(length):
    return raised_cosine_fade_in(length)[::-1]


def normalize_energy(values):
    return values / math.sqrt(max(float(np.sum(np.square(values))), 1e-30))


def paired_band_component(length, sample_rate, center_hz, rt60, coherence, seed):
    preroll = round(DESIGN["noise_preroll_ms"] * 1e-3 * sample_rate)
    rng = np.random.default_rng(seed)
    common = rng.standard_normal(length + preroll)
    independent = rng.standard_normal(length + preroll)
    first = octave_filter(common, center_hz, sample_rate)[preroll:]
    second = octave_filter(
        coherence * common + math.sqrt(max(1.0 - coherence**2, 0.0)) * independent,
        center_hz,
        sample_rate,
    )[preroll:]

    time = np.arange(length, dtype=np.float64) / sample_rate
    envelope = np.power(10.0, -3.0 * time / rt60)
    fade_in_length = round(
        (DESIGN["late_transition_ms"][1] - DESIGN["late_transition_ms"][0])
        * 1e-3
        * sample_rate
    )
    envelope[:fade_in_length] *= raised_cosine_fade_in(fade_in_length)
    fade_out_length = round(DESIGN["final_fade_ms"] * 1e-3 * sample_rate)
    envelope[-fade_out_length:] *= raised_cosine_fade_out(fade_out_length)
    return normalize_energy(first * envelope), normalize_energy(second * envelope)


def load_inputs():
    target_summary = json.loads(TARGET_SUMMARY.read_text(encoding="utf-8"))
    target = target_summary["candidate_e_target"]
    early_summary = json.loads(EARLY_ANALYSIS.read_text(encoding="utf-8"))
    for side, path in EARLY_FILES.items():
        expected = early_summary["rendered_files"][side]["sha256"]
        actual = sha256(path)
        if actual != expected:
            raise ValueError(f"Candidate C hash mismatch for {path}: {actual} != {expected}")
    early, sample_rate, metadata = load_stereo_paths(EARLY_FILES)
    if sample_rate != DESIGN["sample_rate_hz"]:
        raise ValueError(f"Expected candidate C at {DESIGN['sample_rate_hz']} Hz")
    return target_summary, target, early_summary, early, sample_rate, metadata


def build_components(target, sample_rate, length):
    centers = tuple(float(value) for value in target["rt60_seconds_by_octave"])
    components = {path: {} for path in PATH_ORDER}
    for source_index, path_pair in enumerate((("LL", "LR"), ("RL", "RR"))):
        for band_index, center in enumerate(centers):
            key = str(int(center))
            coherence = float(target["maximum_absolute_iacc_by_octave"][key])
            if center > 250.0:
                # The target is a maximum over ±1 ms, not the zero-lag mixing
                # coefficient. Finite band-limited noise adds residual maxima.
                coherence *= DESIGN["coherence_mix_scale_above_250_hz"]
            first, second = paired_band_component(
                length,
                sample_rate,
                center,
                float(target["rt60_seconds_by_octave"][key]),
                coherence,
                DESIGN["random_seed"] + source_index * 1000 + band_index,
            )
            components[path_pair[0]][key] = first
            components[path_pair[1]][key] = second
    return centers, components


def insert_late_sequences(sequences, direct_peaks, sample_rate):
    output = {path: np.zeros(DESIGN["output_length_samples"]) for path in PATH_ORDER}
    offset = round(DESIGN["late_transition_ms"][0] * 1e-3 * sample_rate)
    for path in PATH_ORDER:
        start = direct_peaks[path] + offset
        available = len(output[path]) - start
        output[path][start:] = sequences[path][:available]
    return output


def compose_late(centers, components, gains, direct_peaks, sample_rate):
    sequences = {}
    for path in PATH_ORDER:
        values = sum(
            gains[str(int(center))] * components[path][str(int(center))]
            for center in centers
        )
        sequences[path] = apply_late_highpass(values, sample_rate)
    return insert_late_sequences(sequences, direct_peaks, sample_rate)


def mean_band_energy_db(paths, center, sample_rate):
    energies = [
        float(np.sum(np.square(octave_filter(values, center, sample_rate))))
        for values in paths.values()
    ]
    return 10.0 * math.log10(max(float(np.mean(energies)), 1e-30))


def apply_spectral_correction(late, corrections_db, sample_rate):
    centers = np.asarray([float(key) for key in corrections_db], dtype=np.float64)
    corrections = np.asarray(
        [float(corrections_db[str(int(center))]) for center in centers],
        dtype=np.float64,
    )
    limit = DESIGN["spectral_correction_limit_db"]
    corrections = np.clip(corrections, -limit, limit)
    node_frequencies = np.concatenate(([20.0, 125.0], centers, [23000.0]))
    node_corrections = np.concatenate(([0.0, 0.0], corrections, [corrections[-1]]))
    nfft = 65536
    frequencies = np.fft.rfftfreq(nfft, 1.0 / sample_rate)
    positive = np.maximum(frequencies, node_frequencies[0])
    correction_db = np.interp(
        np.log2(positive), np.log2(node_frequencies), node_corrections
    )
    correction_db[0] = 0.0
    spectrum = minimum_phase_spectrum(np.power(10.0, correction_db / 20.0), nfft)
    impulse = np.fft.irfft(spectrum, nfft)[: DESIGN["spectral_correction_fir_samples"]]
    fade_length = min(256, len(impulse))
    impulse[-fade_length:] *= raised_cosine_fade_out(fade_length)
    convolution_length = len(next(iter(late.values()))) + len(impulse) - 1
    convolution_nfft = 1 << (convolution_length - 1).bit_length()
    impulse_spectrum = np.fft.rfft(impulse, convolution_nfft)
    return {
        path: np.fft.irfft(
            np.fft.rfft(values, convolution_nfft) * impulse_spectrum,
            convolution_nfft,
        )[: len(values)]
        for path, values in late.items()
    }


def calibrate_spectrum(centers, components, target, direct_peaks, sample_rate):
    shape = target["late_energy_shape_db_relative_to_1khz"]
    gains = {str(int(center)): 10.0 ** (float(shape[str(int(center))]) / 20.0) for center in centers}
    late = compose_late(centers, components, gains, direct_peaks, sample_rate)
    for _ in range(DESIGN["spectral_calibration_iterations"]):
        measured = {
            str(int(center)): mean_band_energy_db(late, center, sample_rate)
            for center in centers
        }
        reference = measured["1000"]
        corrections = {
            str(int(center)): float(shape[str(int(center))])
            - (measured[str(int(center))] - reference)
            for center in centers
        }
        late = apply_spectral_correction(late, corrections, sample_rate)
    return gains, late


def equalize_and_scale_late(late, control, target_ratio_db):
    mean_path_energy = float(
        np.mean([np.sum(np.square(values)) for values in late.values()])
    )
    for path in PATH_ORDER:
        path_energy = float(np.sum(np.square(late[path])))
        late[path] *= math.sqrt(mean_path_energy / max(path_energy, 1e-30))
    control_energy = sum(float(np.sum(np.square(values))) for values in control.values())
    late_energy = sum(float(np.sum(np.square(values))) for values in late.values())
    desired_late_energy = control_energy / (10.0 ** (target_ratio_db / 10.0))
    scale = math.sqrt(desired_late_energy / max(late_energy, 1e-30))
    return {path: values * scale for path, values in late.items()}, scale


def analyze_candidate(target, control, late, sample_rate):
    centers = tuple(float(value) for value in target["rt60_seconds_by_octave"])
    start = round(DESIGN["late_transition_ms"][1] * 1e-3 * sample_rate)
    end = round(500e-3 * sample_rate)
    maximum_lag = round(1e-3 * sample_rate)
    control_energy = sum(float(np.sum(np.square(values))) for values in control.values())
    late_energy = sum(float(np.sum(np.square(values))) for values in late.values())
    candidate = {path: control[path] + late[path] for path in PATH_ORDER}
    nfft = 65536
    frequencies = np.fft.rfftfreq(nfft, 1.0 / sample_rate)
    control_spectra = {
        path: np.fft.rfft(values, nfft) for path, values in control.items()
    }
    candidate_spectra = {
        path: np.fft.rfft(values, nfft) for path, values in candidate.items()
    }
    control_mean = np.mean(
        [smoothed_db(values, frequencies) for values in control_spectra.values()],
        axis=0,
    )
    candidate_mean = np.mean(
        [smoothed_db(values, frequencies) for values in candidate_spectra.values()],
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
    metrics = {
        "combined_retained_c_to_late_energy_ratio_db": finite_float(
            10.0 * math.log10(control_energy / max(late_energy, 1e-30)), 6
        ),
        "path_late_energy_db": {
            path: finite_float(energy_db(values), 6) for path, values in late.items()
        },
        "first_difference_from_c_sample": {
            path: int(np.flatnonzero(candidate[path] != control[path])[0])
            for path in PATH_ORDER
        },
        "bass_preservation_20_80_hz": band_metrics(
            frequencies, candidate_mean, control_mean, 20.0, 80.0
        ),
        "modeled_correlated_renderer_gain_db": finite_float(
            20.0 * math.log10(max(maximum_correlated, 1e-30)), 6
        ),
        "bands": {},
    }
    mean_band_energy = {
        str(int(center)): mean_band_energy_db(late, center, sample_rate)
        for center in centers
    }
    reference = mean_band_energy["1000"]
    for center in centers:
        key = str(int(center))
        filtered = {
            path: octave_filter(values, center, sample_rate)
            for path, values in late.items()
        }
        t30 = [
            extrapolated_decay_seconds(
                energy_decay_db(values), sample_rate, -5.0, -35.0
            )
            for values in filtered.values()
        ]
        left_iacc, _ = maximum_correlation(
            filtered["LL"], filtered["LR"], start, end, maximum_lag
        )
        right_iacc, _ = maximum_correlation(
            filtered["RL"], filtered["RR"], start, end, maximum_lag
        )
        metrics["bands"][key] = {
            "energy_shape_db_relative_to_1khz": finite_float(
                mean_band_energy[key] - reference, 6
            ),
            "median_t30_seconds": finite_float(np.median(t30), 6),
            "mean_maximum_absolute_iacc": finite_float(
                np.mean([abs(left_iacc), abs(right_iacc)]), 6
            ),
        }
    return metrics


def write_analysis_plots(output, target, metrics):
    centers = np.asarray(
        [float(value) for value in target["rt60_seconds_by_octave"]],
        dtype=np.float64,
    )
    keys = [str(int(center)) for center in centers]
    plots = (
        (
            "late-spectrum-target.svg",
            "Candidate E Late-Field Spectrum",
            "Energy relative to 1 kHz (dB)",
            [target["late_energy_shape_db_relative_to_1khz"][key] for key in keys],
            [metrics["bands"][key]["energy_shape_db_relative_to_1khz"] for key in keys],
            -16.0,
            12.0,
        ),
        (
            "late-decay-target.svg",
            "Candidate E Late-Field Decay",
            "Extrapolated decay (seconds)",
            [target["rt60_seconds_by_octave"][key] for key in keys],
            [metrics["bands"][key]["median_t30_seconds"] for key in keys],
            0.45,
            0.68,
        ),
        (
            "late-coherence-target.svg",
            "Candidate E Late-Field Coherence",
            "Maximum absolute correlation",
            [target["maximum_absolute_iacc_by_octave"][key] for key in keys],
            [metrics["bands"][key]["mean_maximum_absolute_iacc"] for key in keys],
            0.0,
            0.35,
        ),
    )
    for filename, title, ylabel, target_values, achieved_values, ymin, ymax in plots:
        write_svg_plot(
            output / filename,
            title,
            [
                ("D-derived target", centers, np.asarray(target_values), "#6b7280"),
                ("E achieved", centers, np.asarray(achieved_values), "#2563eb"),
            ],
            "Octave-band center (Hz)",
            ylabel,
            250.0,
            16000.0,
            ymin,
            ymax,
            list(centers),
            x_scale="log",
        )


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ir-output", type=Path, default=OUTPUT_DIRECTORY)
    parser.add_argument("--analysis-output", type=Path, default=ANALYSIS_DIRECTORY)
    return parser.parse_args()


def main():
    args = parse_args()
    target_summary, target, early_summary, early, sample_rate, early_metadata = load_inputs()
    output_length = DESIGN["output_length_samples"]
    control = {path: pad_to(values, output_length) for path, values in early.items()}
    direct_peaks = {
        path: int(early_summary["paths"][path]["synthetic_direct_peak_sample"])
        for path in PATH_ORDER
    }
    centers, components = build_components(target, sample_rate, output_length)
    gains, late = calibrate_spectrum(
        centers, components, target, direct_peaks, sample_rate
    )
    late, global_scale = equalize_and_scale_late(
        late,
        control,
        float(target["combined_retained_c_to_late_energy_ratio_db"]),
    )
    candidate = {path: control[path] + late[path] for path in PATH_ORDER}
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
        raise ValueError("Rendered E sample rate changed unexpectedly")
    rendered_late = {path: rendered[path] - control[path] for path in PATH_ORDER}
    metrics = analyze_candidate(target, control, rendered_late, sample_rate)

    args.analysis_output.mkdir(parents=True, exist_ok=True)
    write_analysis_plots(args.analysis_output, target, metrics)
    summary = {
        "schema_version": 1,
        "status": "accepted opt-in synthetic diffuse late-field reference E",
        "listening_result": LISTENING_RESULT,
        "windows_benchmark_result": WINDOWS_BENCHMARK_RESULT,
        "design": DESIGN,
        "target_summary": {
            "path": str(TARGET_SUMMARY.relative_to(REPOSITORY)),
            "sha256": sha256(TARGET_SUMMARY),
            "target": target,
            "measured_waveform_samples_copied": False,
        },
        "candidate_c_files": early_metadata,
        "direct_peak_samples": direct_peaks,
        "calibrated_band_gains": {
            key: finite_float(value, 9) for key, value in gains.items()
        },
        "global_late_scale": finite_float(global_scale, 9),
        "metrics": metrics,
        "rendered_files": rendered_files,
        "plots": [
            "late-spectrum-target.svg",
            "late-decay-target.svg",
            "late-coherence-target.svg",
        ],
    }
    (args.analysis_output / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    report = [
        "# Candidate E Synthetic Late Field",
        "",
        "Candidate E preserves candidate C and replaces only D's measured late tail with deterministic synthetic binaural decay. It uses D-derived broad targets but copies no measured late-field waveform samples.",
        "",
        "## Validation",
        "",
        f"- Retained-C-to-late energy ratio: {metrics['combined_retained_c_to_late_energy_ratio_db']:.3f} dB (target {target['combined_retained_c_to_late_energy_ratio_db']:.3f} dB).",
        f"- Maximum rendered IR peak: {maximum:.6f}.",
        "- All four synthetic late paths are normalized to equal total energy before one common level scale.",
        "- The 25-30 ms transition, frequency-dependent decay, spectrum, and binaural coherence are recorded in summary.json.",
        "",
        "## Listening and Runtime Result",
        "",
        "Informal sighted comparison found no obvious difference between D and E; E preserved the intended ±30° placement and sounded great. A sounded narrower, at an estimated ±20–25°. Windows Benchmark passed all three probes with no clipping or configuration errors, 4.61 dB correlated-sweep headroom, and 0.60–0.67% single-core CPU.",
        "",
        "## Boundary",
        "",
        "This is an isolated late-field experiment. The personal direct stage, measured early field, bass, target curve, headphone compensation, and personal balance remain unchanged.",
    ]
    (args.analysis_output / "report.md").write_text(
        "\n".join(report) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
