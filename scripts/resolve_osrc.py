#!/usr/bin/env python3
"""Resolve a registered Samsung OSRC entry for GitHub Actions."""

import argparse
import json
from pathlib import Path


REQUIRED_FIELDS = ("source_url", "source_sha256", "defconfig", "localversion")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--firmware", required=True)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()

    entries = json.loads(args.manifest.read_text(encoding="utf-8"))
    if args.firmware not in entries:
        known = ", ".join(sorted(entries)) or "none"
        raise SystemExit(
            f"Firmware {args.firmware!r} is not registered. Known entries: {known}"
        )

    entry = entries[args.firmware]
    missing = [field for field in REQUIRED_FIELDS if not entry.get(field)]
    if missing:
        raise SystemExit(
            f"Manifest entry {args.firmware!r} is missing: {', '.join(missing)}"
        )

    if args.firmware not in entry["localversion"]:
        raise SystemExit(
            "Registered localversion does not contain the firmware identifier; "
            "refusing to create a misleading build"
        )

    sha256 = entry["source_sha256"].lower()
    if len(sha256) != 64 or any(char not in "0123456789abcdef" for char in sha256):
        raise SystemExit("source_sha256 must be a 64-character lowercase hex digest")

    outputs = {
        "source_url": entry["source_url"],
        "source_sha256": sha256,
        "defconfig": entry["defconfig"],
        "localversion": entry["localversion"],
    }

    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as output_file:
            for key, value in outputs.items():
                output_file.write(f"{key}={value}\n")
    else:
        print(json.dumps(outputs, indent=2, sort_keys=True))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
