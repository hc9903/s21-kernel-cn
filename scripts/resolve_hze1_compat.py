#!/usr/bin/env python3
"""Validate and resolve the fixed SM-G9910 HZE1 compatibility manifest."""

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse


TEXT_FIELDS = (
    "target_firmware",
    "published_source_firmware",
    "published_source_package",
    "published_source_url",
    "published_source_sha256",
    "defconfig",
    "target_localversion",
    "expected_kernelrelease",
    "hze1_stock_boot_url",
    "hze1_stock_boot_sha256",
    "hze1_stock_kernel_sha256",
    "hze1_stock_ramdisk_sha256",
    "hze1_vmlinux_export_sha256",
    "magisk_version",
    "magisk_boot_url",
    "magisk_boot_sha256",
    "magisk_ramdisk_sha256",
    "magisk_apk_url",
    "magisk_apk_sha256",
    "magiskboot_x86_64_sha256",
    "provenance_notice",
)
INTEGER_FIELDS = (
    "hze1_stock_boot_size",
    "hze1_stock_kernel_size",
    "hze1_vmlinux_export_count",
    "magisk_boot_size",
)
SHA256_FIELDS = tuple(field for field in TEXT_FIELDS if field.endswith("_sha256"))
URL_FIELDS = tuple(field for field in TEXT_FIELDS if field.endswith("_url"))


def validate_sha256(field: str, value: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise SystemExit(f"{field} must be a 64-character lowercase hex digest")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    missing = [field for field in TEXT_FIELDS + INTEGER_FIELDS if not manifest.get(field)]
    if missing:
        raise SystemExit(f"Compatibility manifest is missing: {', '.join(missing)}")

    for field in TEXT_FIELDS:
        if not isinstance(manifest[field], str):
            raise SystemExit(f"{field} must be a string")
    for field in INTEGER_FIELDS:
        if not isinstance(manifest[field], int) or manifest[field] <= 0:
            raise SystemExit(f"{field} must be a positive integer")
    for field in SHA256_FIELDS:
        validate_sha256(field, manifest[field])
    for field in URL_FIELDS:
        parsed = urlparse(manifest[field])
        if parsed.scheme != "https" or not parsed.netloc:
            raise SystemExit(f"{field} must be an HTTPS URL")

    target = manifest["target_firmware"]
    source = manifest["published_source_firmware"]
    if target == source:
        raise SystemExit("Compatibility source and target firmware must be distinct")
    if target not in manifest["target_localversion"]:
        raise SystemExit("target_localversion does not identify the target firmware")
    if not manifest["expected_kernelrelease"].endswith(manifest["target_localversion"]):
        raise SystemExit("expected_kernelrelease and target_localversion disagree")
    if "HYDA published source derived, HZE1 stock ABI verified" not in manifest["provenance_notice"]:
        raise SystemExit("provenance_notice must state the source and ABI boundary")

    outputs = {key: str(value) for key, value in manifest.items()}
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as output_file:
            for key, value in outputs.items():
                output_file.write(f"{key}={value}\n")
    else:
        print(json.dumps(outputs, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
