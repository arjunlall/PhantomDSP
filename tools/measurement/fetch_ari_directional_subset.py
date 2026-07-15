#!/usr/bin/env python3
"""Download a deterministic ARI DTF screening subset for local analysis."""

import argparse
import hashlib
import html
import json
import os
import re
from pathlib import Path
from urllib.parse import quote, unquote
from urllib.request import urlopen


REPOSITORY = Path(__file__).resolve().parents[2]
DATASET_ROOT = REPOSITORY / "measurements" / "hrtf-datasets"
BASE_URL = "https://sofacoustics.org/data/database/ari"
DEFAULT_SUBJECTS = (
    2,
    8,
    15,
    18,
    22,
    28,
    30,
    38,
    42,
    47,
    55,
    60,
    63,
    72,
    90,
    93,
    104,
    122,
    123,
    140,
    143,
    158,
    159,
    164,
)
LAS_SUBJECTS = (
    4,
    5,
    92,
    214,
    257,
    714,
    742,
    890,
    911,
    912,
    916,
    919,
    929,
    938,
    939,
    940,
    942,
    943,
    945,
    946,
    948,
    949,
    950,
    953,
)
VARIANTS = {
    "semi-anechoic": {
        "output": DATASET_ROOT / "ari",
        "base_url": BASE_URL,
        "filename": "dtf_nh{subject}.sofa",
        "subjects": DEFAULT_SUBJECTS,
        "name": "ARI semi-anechoic in-the-ear directional transfer functions",
        "discovery_pattern": r"^dtf_nh(\d+)\.sofa$",
    },
    "las": {
        "output": DATASET_ROOT / "ari-las",
        "base_url": "https://sofacoustics.org/data/database/ari%20%28las%29",
        "filename": "dtf las_nh{subject}.sofa",
        "subjects": LAS_SUBJECTS,
        "name": "ARI Loudspeaker Array Studio in-the-ear directional transfer functions",
        "discovery_pattern": r"^dtf las_nh(\d+)\.sofa$",
    },
}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_subjects(value):
    return tuple(int(item.strip()) for item in value.split(",") if item.strip())


def load_expected_hashes(path):
    if path is None:
        return {}
    manifest = json.loads(path.read_text(encoding="utf-8"))
    entries = manifest.get("selected_subjects", manifest.get("files", []))
    return {entry.get("filename", entry.get("path")): entry["sha256"] for entry in entries}


def selection_description(arguments, subjects):
    if arguments.all:
        return "all matching files discovered in the official directory"
    if arguments.subjects:
        return "explicit subjects: " + ", ".join(f"nh{value}" for value in subjects)
    return f"deterministic {len(subjects)}-subject screening subset; not a population sample"


def fetch(url, destination):
    temporary = destination.with_suffix(destination.suffix + f".part.{os.getpid()}")
    with urlopen(url) as response, temporary.open("wb") as output:
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            output.write(block)
    temporary.replace(destination)


def discover_files(definition):
    with urlopen(definition["base_url"] + "/") as response:
        listing = response.read().decode("utf-8", errors="replace")
    names = {
        html.unescape(unquote(match))
        for match in re.findall(r'href="([^"]+\.sofa)"', listing, flags=re.IGNORECASE)
    }
    pattern = re.compile(definition["discovery_pattern"])
    discovered = []
    for name in names:
        match = pattern.match(name)
        if match:
            discovered.append((int(match.group(1)), name))
    return sorted(discovered)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=tuple(VARIANTS), default="semi-anechoic")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--all",
        action="store_true",
        help="Discover and fetch every matching file in the selected official directory",
    )
    parser.add_argument(
        "--subjects",
        type=parse_subjects,
        help="Comma-separated ARI subject numbers",
    )
    parser.add_argument(
        "--expected-manifest",
        type=Path,
        help="Verify downloaded hashes against a checked-in selected-source manifest",
    )
    arguments = parser.parse_args()
    definition = VARIANTS[arguments.variant]
    output = arguments.output or definition["output"]
    subjects = arguments.subjects or definition["subjects"]
    expected_hashes = load_expected_hashes(arguments.expected_manifest)
    output.mkdir(parents=True, exist_ok=True)

    files = []
    requested_files = (
        discover_files(definition)
        if arguments.all
        else [
            (subject, definition["filename"].format(subject=subject))
            for subject in subjects
        ]
    )
    for subject, filename in requested_files:
        destination = output / filename
        url = f"{definition['base_url']}/{quote(filename)}"
        if not destination.exists():
            print(f"Downloading {filename}", flush=True)
            fetch(url, destination)
        digest = sha256(destination)
        expected = expected_hashes.get(filename)
        if expected is not None and digest != expected:
            raise ValueError(
                f"Hash mismatch for {filename}: expected {expected}, got {digest}"
            )
        files.append(
            {
                "subject": f"nh{subject}",
                "path": filename,
                "url": url,
                "bytes": destination.stat().st_size,
                "sha256": digest,
            }
        )

    manifest = {
        "schema_version": 1,
        "dataset": definition["name"],
        "variant": arguments.variant,
        "source": definition["base_url"] + "/",
        "license": "Creative Commons Attribution-ShareAlike 3.0 Unported",
        "selection": selection_description(arguments, subjects),
        "verified_against": str(arguments.expected_manifest)
        if arguments.expected_manifest
        else None,
        "files": files,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
