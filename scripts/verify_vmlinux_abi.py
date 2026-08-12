#!/usr/bin/env python3
"""Verify the canonical vmlinux export CRC fingerprint in Module.symvers."""

import argparse
import hashlib
import re
from pathlib import Path


CRC_PATTERN = re.compile(r"0x[0-9a-fA-F]{8}")


def read_vmlinux_symbols(path: Path) -> dict[str, str]:
    symbols: dict[str, str] = {}
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8", errors="strict").splitlines(), start=1
    ):
        if not raw_line.strip():
            continue
        fields = raw_line.split()
        if len(fields) < 3:
            raise SystemExit(f"{path}:{line_number}: malformed Module.symvers line")
        crc, symbol, module = fields[:3]
        if module != "vmlinux":
            continue
        if not CRC_PATTERN.fullmatch(crc):
            raise SystemExit(f"{path}:{line_number}: invalid CRC for {symbol}: {crc}")
        if symbol in symbols:
            raise SystemExit(f"{path}:{line_number}: duplicate vmlinux symbol: {symbol}")
        symbols[symbol] = crc.lower()
    return symbols


def canonical_bytes(symbols: dict[str, str]) -> bytes:
    rows = sorted((crc, symbol) for symbol, crc in symbols.items())
    return "".join(f"{crc}\t{symbol}\n" for crc, symbol in rows).encode("ascii")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("symvers", type=Path)
    parser.add_argument("--expected-count", required=True, type=int)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--canonical-out", type=Path)
    args = parser.parse_args()

    expected_sha256 = args.expected_sha256.lower()
    if len(expected_sha256) != 64 or any(
        char not in "0123456789abcdef" for char in expected_sha256
    ):
        raise SystemExit("--expected-sha256 must be a lowercase SHA-256 digest")

    symbols = read_vmlinux_symbols(args.symvers)
    canonical = canonical_bytes(symbols)
    actual_sha256 = hashlib.sha256(canonical).hexdigest()
    passed = len(symbols) == args.expected_count and actual_sha256 == expected_sha256

    lines = [
        "canonical_format=lowercase CRC, tab, symbol, newline; sorted by (CRC, symbol)",
        f"expected_symbols={args.expected_count}",
        f"actual_symbols={len(symbols)}",
        f"expected_sha256={expected_sha256}",
        f"actual_sha256={actual_sha256}",
        f"result={'pass' if passed else 'fail'}",
    ]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if args.canonical_out:
        args.canonical_out.parent.mkdir(parents=True, exist_ok=True)
        args.canonical_out.write_bytes(canonical)
    print("\n".join(lines))

    if not passed:
        raise SystemExit("vmlinux export ABI does not match the HZE1 stock fingerprint")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
