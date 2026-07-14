#!/usr/bin/env python3
"""Analyze isolated convolved, clean-bass, and combined Equalizer APO captures."""

import argparse
import json
import math
import sys
import wave
from pathlib import Path

try:
    import numpy as np
except ImportError:
    raise SystemExit(
        "NumPy is required. Install it with: "
        "python3 -m pip install -r tools/measurement/requirements.txt"
    )

from analyze_baseline import (
    COLORS,
    PATHS,
    finite_float,
    parse_benchmark_log,
    read_pcm_wav,
    sha256,
    write_svg_plot,
)


SCHEMA_VERSION = 1
CAPTURES = ("combined", "convolved", "clean")
FREQUENCY_TICKS = [20, 30, 40, 50, 70, 90, 100, 120, 150, 200, 250, 300]
INSPECTION_FREQUENCIES = (118.0, 121.0, 124.0, 135.0)


def db20_array(values, floor=-180.0):
    return np.maximum(floor, 20.0 * np.log10(np.maximum(np.abs(values), 1e-12)))


def wrap_degrees(values):
    return (np.degrees(values) + 180.0) % 360.0 - 180.0


def log_smooth(frequencies, values, fraction=24, weights=None):
    """Smooth values in a fractional-octave window centered on each frequency."""
    complex_values = np.iscomplexobj(values)
    result = np.empty(len(values), dtype=np.complex128 if complex_values else np.float64)
    half_ratio = 2.0 ** (1.0 / (2.0 * fraction))
    source_weights = np.ones(len(values), dtype=np.float64) if weights is None else np.asarray(weights)

    for index, frequency in enumerate(frequencies):
        start = np.searchsorted(frequencies, frequency / half_ratio, side="left")
        stop = np.searchsorted(frequencies, frequency * half_ratio, side="right")
        window_values = values[start:stop]
        window_weights = source_weights[start:stop]
        valid = np.isfinite(window_values) & np.isfinite(window_weights) & (window_weights > 0)
        if not np.any(valid):
            result[index] = np.nan
            continue
        result[index] = np.sum(window_values[valid] * window_weights[valid]) / np.sum(window_weights[valid])
    return result


def group_delay_ms(spectrum, frequencies):
    phase = np.unwrap(np.angle(spectrum))
    return -np.gradient(phase, frequencies, edge_order=1) / (2.0 * np.pi) * 1000.0


def parse_capture_header(log_path):
    result = {}
    if not log_path.exists():
        return result
    prefixes = {
        "PhantomDSP commit: ": "commit",
        "Device name: ": "device_name",
        "Installed config: ": "installed_config",
        "Probe set: ": "probe_set",
        "Capture output gain: ": "capture_output_gain",
    }
    for line in log_path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        for prefix, key in prefixes.items():
            if line.startswith(prefix):
                result[key] = line[len(prefix):]
    return result


def load_capture(directory):
    metadata_path = directory / "probe-metadata.json"
    required = [
        metadata_path,
        directory / "left-input.wav",
        directory / "right-input.wav",
        directory / "left-output.wav",
        directory / "right-output.wav",
        directory / "benchmark.log",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise ValueError("Missing Benchmark artifacts:\n- " + "\n- ".join(missing))

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    for probe in metadata["files"].values():
        probe_path = directory / probe["filename"]
        if sha256(probe_path) != probe["sha256"]:
            raise ValueError(f"Probe checksum does not match metadata: {probe_path}")

    loaded = {
        filename: read_pcm_wav(directory / filename)
        for filename in ("left-output.wav", "right-output.wav")
    }
    reference = loaded["left-output.wav"]
    for filename, info in loaded.items():
        if info["sample_rate"] != metadata["sample_rate_hz"]:
            raise ValueError(f"{directory.name}/{filename} has the wrong sample rate")
        if info["channels"] != 2:
            raise ValueError(f"{directory.name}/{filename} must contain two channels")
        if info["frame_count"] != metadata["frame_count"]:
            raise ValueError(f"{directory.name}/{filename} has the wrong frame count")
        if info["sample_width_bits"] != reference["sample_width_bits"]:
            raise ValueError(f"{directory.name} output sample widths do not match")

    impulse_sample = int(metadata["impulse_sample"])
    input_amplitude = float(metadata["normalized_sample_value"])
    if input_amplitude <= 0:
        raise ValueError(f"{directory.name} has a non-positive probe amplitude")

    responses = {}
    for label, (filename, channel, _) in PATHS.items():
        responses[label] = loaded[filename]["samples"][impulse_sample:, channel] / input_amplitude

    source_files = {}
    for path in required:
        source_files[path.name] = {"sha256": sha256(path), "bytes": path.stat().st_size}
    return {
        "metadata": metadata,
        "wave_info": {
            "sample_rate_hz": reference["sample_rate"],
            "frame_count": reference["frame_count"],
            "sample_width_bits": reference["sample_width_bits"],
        },
        "responses": responses,
        "header": parse_capture_header(directory / "benchmark.log"),
        "benchmark_runs": parse_benchmark_log(directory / "benchmark.log"),
        "source_files": source_files,
    }


def point_metrics(frequencies, data, frequency):
    index = int(np.argmin(np.abs(frequencies - frequency)))
    return {
        "frequency_hz": finite_float(frequencies[index], 4),
        "clean_to_convolved_db": finite_float(data["clean_to_convolved_db"][index], 4),
        "phase_difference_degrees": finite_float(data["phase_difference_degrees"][index], 4),
        "interference_db": finite_float(data["interference_db"][index], 4),
        "sum_vs_convolved_db": finite_float(data["sum_vs_convolved_db"][index], 4),
    }


def build_analysis(captures, low_frequency, high_frequency, transition_low, transition_high, smoothing_fraction):
    reference = captures["combined"]
    sample_rate = reference["wave_info"]["sample_rate_hz"]
    response_length = min(
        len(captures[capture]["responses"][label])
        for capture in CAPTURES
        for label in PATHS
    )
    nfft = 1 << max(1, (response_length - 1).bit_length())
    all_frequencies = np.fft.rfftfreq(nfft, d=1.0 / sample_rate)
    band = (all_frequencies >= low_frequency) & (all_frequencies <= high_frequency)
    frequencies = all_frequencies[band]
    transition = (frequencies >= transition_low) & (frequencies <= transition_high)

    spectra = {capture: {} for capture in CAPTURES}
    group_delays = {capture: {} for capture in CAPTURES}
    for capture in CAPTURES:
        for label in PATHS:
            spectrum = np.fft.rfft(captures[capture]["responses"][label][:response_length], n=nfft)
            spectra[capture][label] = spectrum[band]
            delay = group_delay_ms(spectrum, all_frequencies)[band]
            group_delays[capture][label] = log_smooth(
                frequencies,
                delay,
                fraction=smoothing_fraction,
                weights=np.square(np.abs(spectrum[band])),
            )

    paths = {}
    metrics = {}
    for label in PATHS:
        combined = spectra["combined"][label]
        convolved = spectra["convolved"][label]
        clean = spectra["clean"][label]
        predicted = convolved + clean
        error = combined - predicted

        raw_clean_to_convolved = db20_array(clean) - db20_array(convolved)
        relative_phasor = clean * np.conj(convolved)
        phase_weights = np.sqrt(np.abs(clean) * np.abs(convolved))
        unit_phasor = relative_phasor / np.maximum(np.abs(relative_phasor), 1e-18)
        smoothed_phasor = log_smooth(
            frequencies,
            unit_phasor,
            fraction=smoothing_fraction,
            weights=phase_weights,
        )
        raw_interference = db20_array(predicted) - db20_array(np.abs(convolved) + np.abs(clean))
        raw_sum_vs_convolved = db20_array(predicted) - db20_array(convolved)
        scalar_branch_magnitude = np.abs(convolved) + np.abs(clean)
        error_reference = max(float(np.max(scalar_branch_magnitude[transition])), 1e-12)
        raw_closure_error = db20_array(error / error_reference)

        path_data = {
            "combined_magnitude_db": log_smooth(frequencies, db20_array(combined), smoothing_fraction),
            "convolved_magnitude_db": log_smooth(frequencies, db20_array(convolved), smoothing_fraction),
            "clean_magnitude_db": log_smooth(frequencies, db20_array(clean), smoothing_fraction),
            "clean_to_convolved_db": log_smooth(frequencies, raw_clean_to_convolved, smoothing_fraction),
            "phase_difference_degrees": wrap_degrees(np.angle(smoothed_phasor)),
            "interference_db": log_smooth(frequencies, raw_interference, smoothing_fraction),
            "sum_vs_convolved_db": log_smooth(frequencies, raw_sum_vs_convolved, smoothing_fraction),
            "closure_error_db": log_smooth(frequencies, raw_closure_error, smoothing_fraction),
            "combined_group_delay_ms": group_delays["combined"][label],
            "convolved_group_delay_ms": group_delays["convolved"][label],
            "clean_group_delay_ms": group_delays["clean"][label],
        }

        transition_indices = np.flatnonzero(transition)
        worst_interference = transition_indices[
            int(np.argmin(path_data["interference_db"][transition]))
        ]
        worst_sum = transition_indices[
            int(np.argmin(path_data["sum_vs_convolved_db"][transition]))
        ]
        balance = transition_indices[
            int(np.argmin(np.abs(path_data["clean_to_convolved_db"][transition])))
        ]
        error_rms = float(np.sqrt(np.mean(np.square(np.abs(error[transition])))))
        scalar_branch_rms = float(
            np.sqrt(np.mean(np.square(scalar_branch_magnitude[transition])))
        )
        closure_rms = 20.0 * math.log10(
            max(error_rms / max(scalar_branch_rms, 1e-12), 1e-12)
        )

        metrics[label] = {
            "deepest_interference_db": finite_float(path_data["interference_db"][worst_interference], 4),
            "deepest_interference_frequency_hz": finite_float(frequencies[worst_interference], 4),
            "phase_at_deepest_interference_degrees": finite_float(path_data["phase_difference_degrees"][worst_interference], 4),
            "clean_to_convolved_at_deepest_interference_db": finite_float(path_data["clean_to_convolved_db"][worst_interference], 4),
            "minimum_sum_vs_convolved_db": finite_float(path_data["sum_vs_convolved_db"][worst_sum], 4),
            "minimum_sum_vs_convolved_frequency_hz": finite_float(frequencies[worst_sum], 4),
            "closest_branch_level_frequency_hz": finite_float(frequencies[balance], 4),
            "closest_branch_level_mismatch_db": finite_float(path_data["clean_to_convolved_db"][balance], 4),
            "phase_at_closest_branch_level_degrees": finite_float(path_data["phase_difference_degrees"][balance], 4),
            "interference_at_closest_branch_level_db": finite_float(path_data["interference_db"][balance], 4),
            "closure_rms_error_db": finite_float(closure_rms, 4),
            "inspection_points": {
                f"{frequency:g}": point_metrics(frequencies, path_data, frequency)
                for frequency in INSPECTION_FREQUENCIES
            },
        }
        paths[label] = path_data

    return {
        "sample_rate_hz": sample_rate,
        "nfft": nfft,
        "frequencies": frequencies,
        "paths": paths,
        "metrics": metrics,
    }


def serializable_summary(captures, analysis, args):
    path_data = {}
    for label, values in analysis["paths"].items():
        path_data[label] = {
            key: [finite_float(value, 5) for value in data]
            for key, data in values.items()
        }
    capture_data = {}
    for name, capture in captures.items():
        capture_data[name] = {
            "header": capture["header"],
            "wave_info": capture["wave_info"],
            "benchmark_runs": capture["benchmark_runs"],
            "source_files": capture["source_files"],
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "frequency_band_hz": [args.low_frequency, args.high_frequency],
        "transition_band_hz": [args.transition_low, args.transition_high],
        "smoothing_fractional_octave": args.smoothing_fraction,
        "captures": capture_data,
        "path_definitions": {label: value[2] for label, value in PATHS.items()},
        "path_metrics": analysis["metrics"],
        "frequency_hz": [finite_float(value, 5) for value in analysis["frequencies"]],
        "path_data": path_data,
    }


def plot_metric(output_dir, filename, title, frequencies, paths, key, y_label, y_min, y_max):
    series = [(label, frequencies, paths[label][key], COLORS[label]) for label in PATHS]
    write_svg_plot(
        output_dir / filename,
        title,
        series,
        "Frequency (Hz)",
        y_label,
        float(frequencies[0]),
        float(frequencies[-1]),
        y_min,
        y_max,
        FREQUENCY_TICKS,
        x_scale="log",
    )


def plot_results(output_dir, analysis):
    frequencies = analysis["frequencies"]
    paths = analysis["paths"]

    for branch in CAPTURES:
        magnitude_key = f"{branch}_magnitude_db"
        values = np.concatenate([paths[label][magnitude_key] for label in PATHS])
        y_min = math.floor((float(np.nanpercentile(values, 1)) - 3.0) / 5.0) * 5.0
        y_max = math.ceil((float(np.nanpercentile(values, 99)) + 3.0) / 5.0) * 5.0
        plot_metric(
            output_dir,
            f"{branch}-magnitude.svg",
            f"{branch.title()} Branch Magnitude",
            frequencies,
            paths,
            magnitude_key,
            "Magnitude (dB)",
            y_min,
            y_max,
        )

        delay_key = f"{branch}_group_delay_ms"
        delays = np.concatenate([paths[label][delay_key] for label in PATHS])
        delay_min = max(-50.0, math.floor((float(np.nanpercentile(delays, 2)) - 2.0) / 5.0) * 5.0)
        delay_max = min(100.0, math.ceil((float(np.nanpercentile(delays, 98)) + 2.0) / 5.0) * 5.0)
        if delay_max <= delay_min:
            delay_min, delay_max = -5.0, 25.0
        plot_metric(
            output_dir,
            f"{branch}-group-delay.svg",
            f"{branch.title()} Branch Group Delay",
            frequencies,
            paths,
            delay_key,
            "Group delay (ms)",
            delay_min,
            delay_max,
        )

    plot_metric(
        output_dir,
        "clean-to-convolved.svg",
        "Clean-to-Convolved Branch Level",
        frequencies,
        paths,
        "clean_to_convolved_db",
        "Clean / convolved (dB)",
        -40.0,
        40.0,
    )
    plot_metric(
        output_dir,
        "phase-difference.svg",
        "Clean Minus Convolved Phase",
        frequencies,
        paths,
        "phase_difference_degrees",
        "Phase difference (degrees)",
        -180.0,
        180.0,
    )
    plot_metric(
        output_dir,
        "interference.svg",
        "Vector-Sum Interference",
        frequencies,
        paths,
        "interference_db",
        "Sum / scalar magnitude sum (dB)",
        -30.0,
        0.0,
    )
    plot_metric(
        output_dir,
        "sum-vs-convolved.svg",
        "Combined Output Relative to Convolved Branch",
        frequencies,
        paths,
        "sum_vs_convolved_db",
        "Combined / convolved (dB)",
        -30.0,
        30.0,
    )
    plot_metric(
        output_dir,
        "vector-sum-closure.svg",
        "Measured Combined Minus Convolved + Clean",
        frequencies,
        paths,
        "closure_error_db",
        "Error relative to scalar-branch band peak (dB)",
        -120.0,
        0.0,
    )


def write_report(path, summary):
    transition = summary["transition_band_hz"]
    metrics = summary["path_metrics"]
    lines = [
        "# Bass Branch Analysis",
        "",
        "This report compares the isolated convolved and clean-low branches after the exact shared Equalizer APO downstream processing. The measured combined capture validates their complex vector sum.",
        "",
        "## Capture Validation",
        "",
        "| Capture | Commit | Benchmark device | Impulse clipping |",
        "| --- | --- | --- | ---: |",
    ]
    for name in CAPTURES:
        capture = summary["captures"][name]
        header = capture["header"]
        clipping = sum(
            run.get("clipped_samples", 0)
            for run_name, run in capture["benchmark_runs"].items()
            if run_name in ("left impulse", "right impulse")
        )
        lines.append(
            f"| {name} | `{header.get('commit', 'unknown')[:12]}` | "
            f"`{header.get('device_name', 'unknown')}` | {clipping} |"
        )

    worst_closure = max(item["closure_rms_error_db"] for item in metrics.values())
    if worst_closure > -25.0:
        lines.extend(
            [
                "",
                "**Validity warning:** The isolated branches do not reconstruct the measured combined response closely enough. Inspect the capture routing before using the cancellation results.",
            ]
        )

    lines.extend(
        [
            "",
            f"## Transition Summary ({transition[0]:g}–{transition[1]:g} Hz)",
            "",
            "Interference compares the complex sum with the sum of branch magnitudes; 0 dB is perfectly in phase and increasingly negative values indicate cancellation. Closure RMS is normalized to the scalar branch energy so genuine cancellation does not make the routing check look artificially worse.",
            "",
            "| Path | Deepest interference | Frequency | Clean/convolved there | Phase there | Minimum sum vs convolved | Closure RMS |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for label in PATHS:
        item = metrics[label]
        lines.append(
            f"| `{label}` | {item['deepest_interference_db']:.2f} dB | "
            f"{item['deepest_interference_frequency_hz']:.1f} Hz | "
            f"{item['clean_to_convolved_at_deepest_interference_db']:.2f} dB | "
            f"{item['phase_at_deepest_interference_degrees']:.1f}° | "
            f"{item['minimum_sum_vs_convolved_db']:.2f} dB at "
            f"{item['minimum_sum_vs_convolved_frequency_hz']:.1f} Hz | "
            f"{item['closure_rms_error_db']:.1f} dB |"
        )

    problem_paths = [
        label for label in PATHS if metrics[label]["deepest_interference_db"] < -3.0
    ]
    worst_label = min(
        PATHS, key=lambda label: metrics[label]["deepest_interference_db"]
    )
    worst = metrics[worst_label]
    clean_difference = worst["clean_to_convolved_at_deepest_interference_db"]
    clean_relation = "above" if clean_difference >= 0.0 else "below"
    closure_values = [item["closure_rms_error_db"] for item in metrics.values()]
    minimum_sum = min(item["minimum_sum_vs_convolved_db"] for item in metrics.values())
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            f"- {len(problem_paths)} of {len(PATHS)} paths exceed the planned 3 dB cancellation limit in the transition band, so the measured bass blend does not meet the acceptance criterion.",
            f"- The strongest cancellation is `{worst_label}` at {worst['deepest_interference_frequency_hz']:.1f} Hz: the clean branch is {abs(clean_difference):.2f} dB {clean_relation} the convolved branch and their phase difference is {worst['phase_at_deepest_interference_degrees']:.1f}°.",
            f"- Vector-sum closure is {min(closure_values):.1f} to {max(closure_values):.1f} dB RMS, which supports the branch routing and cancellation diagnosis at the available 16-bit precision.",
        ]
    )
    if minimum_sum >= 0.0:
        lines.append(
            "- After smoothing, the combined output remains above the convolved branch alone across the transition band. The issue is therefore lost and path-dependent boost, not necessarily a net notch below the original convolved response."
        )

    lines.extend(
        [
            "",
            "## Closest Branch-Level Points",
            "",
            "| Path | Closest-level frequency | Remaining mismatch | Phase difference | Interference |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for label in PATHS:
        item = metrics[label]
        lines.append(
            f"| `{label}` | {item['closest_branch_level_frequency_hz']:.1f} Hz | "
            f"{item['closest_branch_level_mismatch_db']:.2f} dB | "
            f"{item['phase_at_closest_branch_level_degrees']:.1f}° | "
            f"{item['interference_at_closest_branch_level_db']:.2f} dB |"
        )

    lines.extend(
        [
            "",
            "## Existing EQ Region",
            "",
            "These samples cover the current narrow 118–135 Hz corrections. Values use 1/24-octave smoothing by default.",
            "",
            "| Path | Frequency | Clean/convolved | Phase difference | Interference | Sum vs convolved |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for label in PATHS:
        for requested in INSPECTION_FREQUENCIES:
            point = metrics[label]["inspection_points"][f"{requested:g}"]
            lines.append(
                f"| `{label}` | {point['frequency_hz']:.1f} Hz | "
                f"{point['clean_to_convolved_db']:.2f} dB | "
                f"{point['phase_difference_degrees']:.1f}° | "
                f"{point['interference_db']:.2f} dB | "
                f"{point['sum_vs_convolved_db']:.2f} dB |"
            )

    lines.extend(
        [
            "",
            "## Plots",
            "",
            "- [Combined magnitude](combined-magnitude.svg), [convolved magnitude](convolved-magnitude.svg), and [clean magnitude](clean-magnitude.svg)",
            "- [Combined group delay](combined-group-delay.svg), [convolved group delay](convolved-group-delay.svg), and [clean group delay](clean-group-delay.svg)",
            "- [Clean-to-convolved level](clean-to-convolved.svg) and [phase difference](phase-difference.svg)",
            "- [Vector-sum interference](interference.svg) and [combined relative to convolved](sum-vs-convolved.svg)",
            "- [Measured vector-sum closure error](vector-sum-closure.svg)",
            "",
            "The captures are 16-bit Benchmark outputs. The closure measurement distinguishes real branch interaction from routing or analysis errors, but extremely deep nulls remain quantization-sensitive.",
            "",
            "Machine-readable samples, hashes, and metrics are stored in [`summary.json`](summary.json).",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args():
    repo_root = Path(__file__).resolve().parents[2]
    measurement_root = repo_root / "measurements" / "bass-branches"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=measurement_root / "raw")
    parser.add_argument("--output-dir", type=Path, default=measurement_root / "analysis")
    parser.add_argument("--low-frequency", type=float, default=20.0)
    parser.add_argument("--high-frequency", type=float, default=300.0)
    parser.add_argument("--transition-low", type=float, default=50.0)
    parser.add_argument("--transition-high", type=float, default=200.0)
    parser.add_argument("--smoothing-fraction", type=int, default=24)
    return parser.parse_args()


def main():
    args = parse_args()
    if not (0 < args.low_frequency < args.transition_low < args.transition_high <= args.high_frequency):
        raise SystemExit("Frequency limits must satisfy low < transition-low < transition-high <= high")
    if args.smoothing_fraction <= 0:
        raise SystemExit("Smoothing fraction must be positive")

    input_root = args.input_root.resolve()
    output_dir = args.output_dir.resolve()
    captures = {name: load_capture(input_root / name) for name in CAPTURES}
    metadata = captures["combined"]["metadata"]
    wave_info = captures["combined"]["wave_info"]
    for name in CAPTURES[1:]:
        if captures[name]["metadata"] != metadata:
            raise ValueError(f"{name} probe metadata does not match the combined capture")
        if captures[name]["wave_info"] != wave_info:
            raise ValueError(f"{name} WAV format does not match the combined capture")

    analysis = build_analysis(
        captures,
        args.low_frequency,
        args.high_frequency,
        args.transition_low,
        args.transition_high,
        args.smoothing_fraction,
    )
    summary = serializable_summary(captures, analysis, args)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    write_report(output_dir / "report.md", summary)
    plot_results(output_dir, analysis)

    print(f"Wrote bass branch analysis to {output_dir}")
    for label in PATHS:
        item = summary["path_metrics"][label]
        print(
            f"{label}: deepest interference={item['deepest_interference_db']:.2f} dB "
            f"at {item['deepest_interference_frequency_hz']:.1f} Hz; "
            f"closure={item['closure_rms_error_db']:.1f} dB"
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, wave.Error) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
