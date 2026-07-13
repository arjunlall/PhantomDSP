#!/usr/bin/env python3
"""Analyze Equalizer APO Benchmark outputs as a 2x2 digital transfer matrix."""

import argparse
import hashlib
import html
import json
import math
import re
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


SCHEMA_VERSION = 1
COLORS = {
    "LL": "#2563eb",
    "LR": "#7c3aed",
    "RL": "#dc2626",
    "RR": "#059669",
}
PATHS = {
    "LL": ("left-output.wav", 0, "left input → left output"),
    "LR": ("left-output.wav", 1, "left input → right output"),
    "RL": ("right-output.wav", 0, "right input → left output"),
    "RR": ("right-output.wav", 1, "right input → right output"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_pcm_wav(path: Path):
    with wave.open(str(path), "rb") as source:
        if source.getcomptype() != "NONE":
            raise ValueError(f"{path} is compressed; PCM WAV is required")
        channels = source.getnchannels()
        sample_rate = source.getframerate()
        frame_count = source.getnframes()
        sample_width = source.getsampwidth()
        raw = source.readframes(frame_count)

    if sample_width == 1:
        samples = np.frombuffer(raw, dtype=np.uint8).astype(np.float64) - 128.0
        scale = 128.0
    elif sample_width == 2:
        samples = np.frombuffer(raw, dtype="<i2").astype(np.float64)
        scale = float(1 << 15)
    elif sample_width == 3:
        octets = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
        values = (
            octets[:, 0].astype(np.int32)
            | (octets[:, 1].astype(np.int32) << 8)
            | (octets[:, 2].astype(np.int32) << 16)
        )
        samples = np.where(values & 0x800000, values - 0x1000000, values).astype(np.float64)
        scale = float(1 << 23)
    elif sample_width == 4:
        samples = np.frombuffer(raw, dtype="<i4").astype(np.float64)
        scale = float(1 << 31)
    else:
        raise ValueError(f"Unsupported PCM width in {path}: {sample_width * 8} bits")

    samples = samples.reshape(-1, channels) / scale
    return {
        "samples": samples,
        "sample_rate": sample_rate,
        "frame_count": frame_count,
        "channels": channels,
        "sample_width_bits": sample_width * 8,
    }


def db20(value, floor=-180.0):
    if value <= 0:
        return floor
    return max(floor, 20.0 * math.log10(value))


def first_threshold(values, peak, relative_db):
    if peak <= 0:
        return None
    indices = np.flatnonzero(values >= peak * 10 ** (relative_db / 20.0))
    return int(indices[0]) if len(indices) else None


def finite_float(value, digits=6):
    value = float(value)
    return round(value, digits) if math.isfinite(value) else None


def analyze_path(samples, sample_rate, impulse_sample, input_amplitude):
    if impulse_sample >= len(samples):
        raise ValueError("Impulse sample lies beyond Benchmark output")

    output_peak = float(np.max(np.abs(samples)))
    response = samples[impulse_sample:] / input_amplitude
    absolute = np.abs(response)
    peak = float(np.max(absolute))
    peak_sample = int(np.argmax(absolute))

    nfft = 1 << max(1, (len(response) - 1).bit_length())
    spectrum = np.fft.rfft(response, n=nfft)
    frequencies = np.fft.rfftfreq(nfft, d=1.0 / sample_rate)
    magnitude_db = 20.0 * np.log10(np.maximum(np.abs(spectrum), 1e-9))
    wrapped_phase = (np.degrees(np.angle(spectrum)) + 180.0) % 360.0 - 180.0
    unwrapped_phase = np.unwrap(np.angle(spectrum))
    group_delay_ms = -np.gradient(unwrapped_phase, frequencies, edge_order=1) / (2.0 * np.pi) * 1000.0

    max_frequency = min(20000.0, sample_rate * 0.49)
    requested = np.geomspace(20.0, max_frequency, 600)
    frequency_indices = np.unique(
        np.clip(np.rint(requested * nfft / sample_rate).astype(int), 1, len(frequencies) - 1)
    )

    energy = np.cumsum(np.square(response[::-1]), dtype=np.float64)[::-1]
    if energy[0] > 0:
        energy_decay_db = 10.0 * np.log10(np.maximum(energy / energy[0], 1e-12))
    else:
        energy_decay_db = np.full_like(energy, -120.0)

    metrics = {
        "peak_sample": peak_sample,
        "peak_time_ms": peak_sample / sample_rate * 1000.0,
        "onset_minus_40_db_sample": first_threshold(absolute, peak, -40.0),
        "onset_minus_50_db_sample": first_threshold(absolute, peak, -50.0),
        "normalized_peak_gain_db": db20(peak),
        "output_peak_dbfs": db20(output_peak),
    }
    result = {
        "response": response,
        "energy_decay_db": energy_decay_db,
        "frequency_hz": frequencies[frequency_indices],
        "magnitude_db": magnitude_db[frequency_indices],
        "phase_degrees": wrapped_phase[frequency_indices],
        "group_delay_ms": group_delay_ms[frequency_indices],
        "metrics": metrics,
        "nfft": nfft,
    }
    return result


def parse_benchmark_log(path: Path):
    if not path.exists():
        return {}

    section = None
    runs = {}
    max_pattern = re.compile(
        r"Max output level:\s*([0-9.eE+\-]+)\s*\(([-0-9.eE+\-]+) dB\)"
        r"(?:\s*\((\d+) samples clipped!\))?"
    )
    cpu_pattern = re.compile(r"equivalent to\s+([0-9.eE+\-]+)% CPU load")

    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if line.startswith("=== ") and line.endswith(" ==="):
            section = line[4:-4]
            runs[section] = {}
            continue
        if section is None:
            continue
        maximum = max_pattern.search(line)
        if maximum:
            runs[section].update(
                {
                    "max_output_linear": float(maximum.group(1)),
                    "max_output_dbfs": float(maximum.group(2)),
                    "clipped_samples": int(maximum.group(3) or 0),
                }
            )
        cpu = cpu_pattern.search(line)
        if cpu:
            runs[section]["cpu_load_one_core_percent"] = float(cpu.group(1))
    return runs


def format_frequency(value):
    if value >= 1000:
        return f"{value / 1000:g}k"
    return f"{value:g}"


def format_number(value):
    if abs(value) >= 100:
        return f"{value:.0f}"
    if abs(value) >= 10:
        return f"{value:.1f}"
    return f"{value:.2f}"


def write_svg_plot(
    path,
    title,
    series,
    x_label,
    y_label,
    x_min,
    x_max,
    y_min,
    y_max,
    x_ticks,
    x_scale="linear",
):
    width, height = 1100, 620
    left, right, top, bottom = 88, 32, 62, 72
    plot_width = width - left - right
    plot_height = height - top - bottom

    if x_scale == "log":
        log_min, log_max = math.log10(x_min), math.log10(x_max)

        def x_position(value):
            return left + (math.log10(value) - log_min) / (log_max - log_min) * plot_width
    else:
        def x_position(value):
            return left + (value - x_min) / (x_max - x_min) * plot_width

    def y_position(value):
        return top + (y_max - value) / (y_max - y_min) * plot_height

    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{width / 2}" y="32" text-anchor="middle" font-family="sans-serif" font-size="22" font-weight="600">{html.escape(title)}</text>',
    ]

    for tick in x_ticks:
        if tick < x_min or tick > x_max:
            continue
        x = x_position(tick)
        label = format_frequency(tick) if x_scale == "log" else format_number(tick)
        elements.append(f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top + plot_height}" stroke="#e5e7eb"/>')
        elements.append(f'<text x="{x:.2f}" y="{top + plot_height + 25}" text-anchor="middle" font-family="sans-serif" font-size="12" fill="#374151">{label}</text>')

    for tick in np.linspace(y_min, y_max, 7):
        y = y_position(float(tick))
        elements.append(f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_width}" y2="{y:.2f}" stroke="#e5e7eb"/>')
        elements.append(f'<text x="{left - 10}" y="{y + 4:.2f}" text-anchor="end" font-family="sans-serif" font-size="12" fill="#374151">{format_number(float(tick))}</text>')

    elements.append(f'<rect x="{left}" y="{top}" width="{plot_width}" height="{plot_height}" fill="none" stroke="#6b7280"/>')
    elements.append(f'<text x="{left + plot_width / 2}" y="{height - 18}" text-anchor="middle" font-family="sans-serif" font-size="14">{html.escape(x_label)}</text>')
    elements.append(f'<text x="20" y="{top + plot_height / 2}" text-anchor="middle" transform="rotate(-90 20 {top + plot_height / 2})" font-family="sans-serif" font-size="14">{html.escape(y_label)}</text>')

    for label, x_values, y_values, color in series:
        points = []
        for x_value, y_value in zip(x_values, y_values):
            x_value, y_value = float(x_value), float(y_value)
            if not math.isfinite(x_value) or not math.isfinite(y_value):
                continue
            if x_value < x_min or x_value > x_max:
                continue
            y_value = min(y_max, max(y_min, y_value))
            points.append(f"{x_position(x_value):.2f},{y_position(y_value):.2f}")
        elements.append(f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="1.5" stroke-linejoin="round"/>')

    for index, (label, _, _, color) in enumerate(series):
        legend_x = left + 12 + index * 150
        legend_y = top + 20
        elements.append(f'<line x1="{legend_x}" y1="{legend_y}" x2="{legend_x + 24}" y2="{legend_y}" stroke="{color}" stroke-width="3"/>')
        elements.append(f'<text x="{legend_x + 31}" y="{legend_y + 4}" font-family="sans-serif" font-size="13">{html.escape(label)}</text>')

    elements.append("</svg>")
    path.write_text("\n".join(elements) + "\n", encoding="utf-8")


def plot_results(output_dir, analyses, sample_rate):
    labels = list(PATHS)

    impulse_limit = min(min(len(analyses[label]["response"]) for label in labels), round(sample_rate * 0.05))
    impulse_time = np.arange(impulse_limit) / sample_rate * 1000.0
    impulse_series = [
        (label, impulse_time, analyses[label]["response"][:impulse_limit], COLORS[label])
        for label in labels
    ]
    impulse_peak = max(float(np.max(np.abs(item[2]))) for item in impulse_series)
    write_svg_plot(
        output_dir / "impulse-response.svg",
        "Digital Impulse Response (first 50 ms)",
        impulse_series,
        "Time relative to probe impulse (ms)",
        "Normalized amplitude",
        0.0,
        impulse_time[-1],
        -impulse_peak * 1.05,
        impulse_peak * 1.05,
        list(np.arange(0.0, 51.0, 5.0)),
    )

    magnitude_series = [
        (label, analyses[label]["frequency_hz"], analyses[label]["magnitude_db"], COLORS[label])
        for label in labels
    ]
    magnitude_values = np.concatenate([item[2] for item in magnitude_series])
    magnitude_min = max(-120.0, math.floor((float(np.percentile(magnitude_values, 1)) - 5.0) / 10.0) * 10.0)
    magnitude_max = min(60.0, math.ceil((float(np.percentile(magnitude_values, 99)) + 5.0) / 10.0) * 10.0)
    if magnitude_max <= magnitude_min:
        magnitude_min, magnitude_max = -60.0, 20.0
    frequency_ticks = [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000]
    write_svg_plot(
        output_dir / "magnitude-response.svg",
        "Digital Magnitude Response",
        magnitude_series,
        "Frequency (Hz)",
        "Magnitude (dB)",
        20.0,
        20000.0,
        magnitude_min,
        magnitude_max,
        frequency_ticks,
        x_scale="log",
    )

    phase_series = [
        (label, analyses[label]["frequency_hz"], analyses[label]["phase_degrees"], COLORS[label])
        for label in labels
    ]
    write_svg_plot(
        output_dir / "phase-response.svg",
        "Digital Wrapped Phase Response",
        phase_series,
        "Frequency (Hz)",
        "Phase (degrees)",
        20.0,
        20000.0,
        -180.0,
        180.0,
        frequency_ticks,
        x_scale="log",
    )

    group_series = []
    valid_group_values = []
    for label in labels:
        valid = analyses[label]["magnitude_db"] > -60.0
        values = np.where(valid, analyses[label]["group_delay_ms"], np.nan)
        group_series.append((label, analyses[label]["frequency_hz"], values, COLORS[label]))
        valid_group_values.extend(values[np.isfinite(values)].tolist())
    if valid_group_values:
        group_min = max(-50.0, float(np.percentile(valid_group_values, 2)) - 2.0)
        group_max = min(100.0, float(np.percentile(valid_group_values, 98)) + 2.0)
        if group_max <= group_min:
            group_min, group_max = -5.0, 25.0
    else:
        group_min, group_max = -5.0, 25.0
    write_svg_plot(
        output_dir / "group-delay.svg",
        "Digital Group Delay (responses above −60 dB)",
        group_series,
        "Frequency (Hz)",
        "Group delay (ms)",
        20.0,
        20000.0,
        group_min,
        group_max,
        frequency_ticks,
        x_scale="log",
    )

    decay_limit = min(min(len(analyses[label]["energy_decay_db"]) for label in labels), round(sample_rate * 1.0))
    decay_indices = np.unique(np.linspace(0, decay_limit - 1, 1600).astype(int))
    decay_time = decay_indices / sample_rate * 1000.0
    decay_series = [
        (label, decay_time, analyses[label]["energy_decay_db"][decay_indices], COLORS[label])
        for label in labels
    ]
    write_svg_plot(
        output_dir / "energy-decay.svg",
        "Digital Energy Decay",
        decay_series,
        "Time relative to probe impulse (ms)",
        "Remaining energy (dB)",
        0.0,
        decay_time[-1],
        -100.0,
        0.0,
        list(np.arange(0.0, decay_time[-1] + 1.0, 100.0)),
    )


def serializable_summary(input_dir, metadata, wave_info, analyses, benchmark_runs):
    metrics = {}
    response_data = {}
    for label, analysis in analyses.items():
        path_metrics = analysis["metrics"]
        metrics[label] = {
            key: finite_float(value) if isinstance(value, float) else value
            for key, value in path_metrics.items()
        }
        response_data[label] = {
            "magnitude_db": [finite_float(value, 4) for value in analysis["magnitude_db"]],
            "phase_degrees": [finite_float(value, 4) for value in analysis["phase_degrees"]],
            "group_delay_ms": [finite_float(value, 5) for value in analysis["group_delay_ms"]],
        }

    frequencies = analyses["LL"]["frequency_hz"]
    direct_mean = (metrics["LL"]["peak_sample"] + metrics["RR"]["peak_sample"]) / 2.0
    cross_mean = (metrics["LR"]["peak_sample"] + metrics["RL"]["peak_sample"]) / 2.0
    source_files = {}
    for filename in [
        "probe-metadata.json",
        "left-input.wav",
        "right-input.wav",
        "left-output.wav",
        "right-output.wav",
        "benchmark.log",
    ]:
        source = input_dir / filename
        if source.exists():
            source_files[filename] = {"sha256": sha256(source), "bytes": source.stat().st_size}

    return {
        "schema_version": SCHEMA_VERSION,
        "sample_rate_hz": wave_info["sample_rate"],
        "frame_count": wave_info["frame_count"],
        "benchmark_output_sample_width_bits": wave_info["sample_width_bits"],
        "probe": metadata,
        "source_files": source_files,
        "path_definitions": {label: definition[2] for label, definition in PATHS.items()},
        "path_metrics": metrics,
        "spatial_timing": {
            "direct_peak_spread_samples": abs(metrics["LL"]["peak_sample"] - metrics["RR"]["peak_sample"]),
            "cross_peak_spread_samples": abs(metrics["LR"]["peak_sample"] - metrics["RL"]["peak_sample"]),
            "mean_cross_minus_direct_peak_samples": finite_float(cross_mean - direct_mean),
            "mean_cross_minus_direct_peak_ms": finite_float((cross_mean - direct_mean) / wave_info["sample_rate"] * 1000.0),
        },
        "benchmark_runs": benchmark_runs,
        "frequency_hz": [finite_float(value, 4) for value in frequencies],
        "frequency_response": response_data,
    }


def write_report(path, summary):
    metrics = summary["path_metrics"]
    timing = summary["spatial_timing"]
    lines = [
        "# Digital Baseline Analysis",
        "",
        "This report describes the complete Equalizer APO digital renderer. It does not include the physical headphone-to-ear transfer function and therefore is not a closed-loop acoustic validation.",
        "",
    ]
    clipped_impulses = [
        name
        for name in ("left impulse", "right impulse")
        if summary["benchmark_runs"].get(name, {}).get("clipped_samples", 0) > 0
    ]
    if clipped_impulses:
        lines.extend(
            [
                "## Validity Warning",
                "",
                "The impulse capture clipped and is not a valid transfer-function baseline. Re-run the Windows capture with a lower `-ProbeAmplitudeDbfs` value. Clipped runs: "
                + ", ".join(clipped_impulses)
                + ".",
                "",
            ]
        )
    lines.extend(
        [
            "## Path Timing and Level",
            "",
            "| Path | −50 dB onset | −40 dB onset | Peak sample | Peak time | Normalized peak | Output peak |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for label in PATHS:
        item = metrics[label]
        lines.append(
            f"| `{label}` | {item['onset_minus_50_db_sample']} | {item['onset_minus_40_db_sample']} | "
            f"{item['peak_sample']} | {item['peak_time_ms']:.3f} ms | "
            f"{item['normalized_peak_gain_db']:.2f} dB | {item['output_peak_dbfs']:.2f} dBFS |"
        )

    lines.extend(
        [
            "",
            "## Spatial Timing Summary",
            "",
            f"- Direct-path peak spread: {timing['direct_peak_spread_samples']} samples.",
            f"- Cross-path peak spread: {timing['cross_peak_spread_samples']} samples.",
            f"- Mean cross-minus-direct peak offset: {timing['mean_cross_minus_direct_peak_samples']:.2f} samples ({timing['mean_cross_minus_direct_peak_ms']:.3f} ms).",
            "",
            "## Benchmark Runs",
            "",
        ]
    )
    if summary["benchmark_runs"]:
        lines.extend(
            [
                "| Run | Maximum output | Clipped samples | One-core CPU |",
                "| --- | ---: | ---: | ---: |",
            ]
        )
        for name, result in summary["benchmark_runs"].items():
            maximum = result.get("max_output_dbfs")
            cpu = result.get("cpu_load_one_core_percent")
            maximum_text = f"{maximum:.2f} dBFS" if maximum is not None else "not parsed"
            cpu_text = f"{cpu:.2f}%" if cpu is not None else "not parsed"
            lines.append(f"| {name} | {maximum_text} | {result.get('clipped_samples', 'not parsed')} | {cpu_text} |")
    else:
        lines.append("No parseable `benchmark.log` was present.")

    lines.extend(
        [
            "",
            "## Plots",
            "",
            "- [Impulse response](impulse-response.svg)",
            "- [Magnitude response](magnitude-response.svg)",
            "- [Wrapped phase response](phase-response.svg)",
            "- [Group delay](group-delay.svg)",
            "- [Energy decay](energy-decay.svg)",
            "",
            "Equalizer APO Benchmark writes 16-bit output. Low-level onsets and decay near the quantization limit—especially on quieter cross paths—should not be treated as exact. Use the original 24-bit IRs when selecting a sample-trim boundary.",
            "",
            "The machine-readable frequency samples, path metrics, hashes, and Benchmark results are stored in [`summary.json`](summary.json).",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args():
    repo_root = Path(__file__).resolve().parents[2]
    baseline = repo_root / "measurements" / "digital-baseline"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=baseline / "raw")
    parser.add_argument("--output-dir", type=Path, default=baseline / "analysis")
    return parser.parse_args()


def main():
    args = parse_args()
    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()
    metadata_path = input_dir / "probe-metadata.json"
    required = [
        metadata_path,
        input_dir / "left-input.wav",
        input_dir / "right-input.wav",
        input_dir / "left-output.wav",
        input_dir / "right-output.wav",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise SystemExit("Missing Benchmark artifacts:\n- " + "\n- ".join(missing))

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    impulse_sample = int(metadata["impulse_sample"])
    input_amplitude = float(metadata["normalized_sample_value"])
    if input_amplitude <= 0:
        raise SystemExit("Probe metadata contains a non-positive impulse amplitude")
    for probe in metadata["files"].values():
        probe_path = input_dir / probe["filename"]
        if sha256(probe_path) != probe["sha256"]:
            raise SystemExit(f"Probe checksum does not match metadata: {probe_path.name}")

    loaded = {}
    for filename in ["left-output.wav", "right-output.wav"]:
        loaded[filename] = read_pcm_wav(input_dir / filename)
    reference = loaded["left-output.wav"]
    for filename, info in loaded.items():
        if info["sample_rate"] != metadata["sample_rate_hz"]:
            raise SystemExit(f"{filename} sample rate does not match probe metadata")
        if info["channels"] != 2:
            raise SystemExit(f"{filename} must contain two channels")
        if info["frame_count"] != metadata["frame_count"]:
            raise SystemExit(f"{filename} frame count does not match probe metadata")
        if info["frame_count"] != reference["frame_count"]:
            raise SystemExit("Benchmark output frame counts do not match")

    analyses = {}
    for label, (filename, channel, _) in PATHS.items():
        analyses[label] = analyze_path(
            loaded[filename]["samples"][:, channel],
            reference["sample_rate"],
            impulse_sample,
            input_amplitude,
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    benchmark_runs = parse_benchmark_log(input_dir / "benchmark.log")
    summary = serializable_summary(input_dir, metadata, reference, analyses, benchmark_runs)
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    write_report(output_dir / "report.md", summary)
    plot_results(output_dir, analyses, reference["sample_rate"])

    print(f"Wrote analysis to {output_dir}")
    for label in PATHS:
        metrics = summary["path_metrics"][label]
        print(
            f"{label}: peak={metrics['peak_sample']} samples "
            f"({metrics['peak_time_ms']:.3f} ms), "
            f"output={metrics['output_peak_dbfs']:.2f} dBFS"
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, wave.Error) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
