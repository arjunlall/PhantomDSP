#!/usr/bin/env python3
"""Create exact, non-circular sample advances of the active stereo BRIR WAVs."""

import argparse
import hashlib
import json
import wave
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[2]
DEFAULT_IR_DIRECTORY = REPOSITORY / "JBL M2 Binaural Convolution" / "IRs"
PARENTS = {
    "JBL LSR305 LL 4_LR 4 5-500.wav": (
        "4f6aa5b21cd94a075904573f56d7b4ade24ebf6737405984a34d41a956aa386b"
    ),
    "JBL LSR305 RL 4_RR 4 5-500.wav": (
        "f733870e8ff87c578d57a30d5f898fea6f1d1cefe4aa15962fbe8912b1125efb"
    ),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_pcm(path: Path):
    with wave.open(str(path), "rb") as source:
        if source.getcomptype() != "NONE":
            raise ValueError(f"{path} is compressed; PCM WAV is required")
        params = source.getparams()
        raw = source.readframes(source.getnframes())
    return params, raw


def render(parent: Path, output: Path, shift: int):
    params, raw = read_pcm(parent)
    if params.nchannels != 2 or params.sampwidth != 3 or params.framerate != 48000:
        raise ValueError(f"Unexpected parent format: {parent}")
    if shift <= 0 or shift >= params.nframes:
        raise ValueError(f"Invalid shift for {parent}: {shift}")

    bytes_per_frame = params.nchannels * params.sampwidth
    split = shift * bytes_per_frame
    advanced = raw[split:] + bytes(split)

    output.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output), "wb") as target:
        target.setparams(params)
        target.writeframes(advanced)

    output_params, output_raw = read_pcm(output)
    if output_params != params:
        raise RuntimeError(f"Output format changed: {output}")
    if output_raw != advanced:
        raise RuntimeError(f"Output samples failed exact verification: {output}")

    return {
        "output": str(output.relative_to(REPOSITORY)),
        "sha256": sha256(output),
        "operation": f"non-circular advance: {shift} samples",
        "tail_zero_padded_samples": shift,
        "normalization": "none",
        "sample_rate": params.framerate,
        "sample_width_bits": params.sampwidth * 8,
        "channels": params.nchannels,
        "frames": params.nframes,
    }


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ir-directory",
        type=Path,
        default=DEFAULT_IR_DIRECTORY,
        help="Directory containing the two parent WAVs",
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=DEFAULT_IR_DIRECTORY / "advanced",
        help="Directory for derived WAVs",
    )
    parser.add_argument(
        "--shifts",
        type=int,
        nargs="+",
        default=(100, 160, 200),
        help="Common advances to render, in samples",
    )
    parser.add_argument("--manifest", type=Path, help="Optional JSON manifest path")
    return parser.parse_args()


def main():
    args = parse_args()
    result = {"parents": {}, "outputs": []}
    for filename, expected_hash in PARENTS.items():
        parent = args.ir_directory / filename
        parent_hash = sha256(parent)
        if parent_hash != expected_hash:
            raise SystemExit(
                f"Parent hash mismatch for {parent}: {parent_hash} != {expected_hash}"
            )
        result["parents"][filename] = parent_hash
        for shift in args.shifts:
            output = args.output_directory / f"{parent.stem} advance-{shift}.wav"
            item = render(parent, output, shift)
            item.update({"parent": filename, "parent_sha256": parent_hash})
            result["outputs"].append(item)

    encoded = json.dumps(result, indent=2) + "\n"
    if args.manifest:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(encoded, encoding="utf-8")
    print(encoded, end="")


if __name__ == "__main__":
    main()
