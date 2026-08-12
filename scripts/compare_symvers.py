#!/usr/bin/env python3
"""Compare baseline and modified Module.symvers exported symbol CRCs."""

import argparse
from pathlib import Path


def read_symvers(path: Path) -> dict[str, tuple[str, str]]:
    symbols: dict[str, tuple[str, str]] = {}
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8", errors="strict").splitlines(), start=1
    ):
        if not raw_line.strip():
            continue
        fields = raw_line.split()
        if len(fields) < 3:
            raise SystemExit(f"{path}:{line_number}: malformed Module.symvers line")
        crc, symbol, module = fields[:3]
        if symbol in symbols and symbols[symbol][0] != crc:
            raise SystemExit(f"{path}:{line_number}: duplicate CRC for {symbol}")
        symbols[symbol] = (crc, module)
    return symbols


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline", type=Path)
    parser.add_argument("modified", type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()

    baseline = read_symvers(args.baseline)
    modified = read_symvers(args.modified)

    missing = sorted(set(baseline) - set(modified))
    changed = sorted(
        symbol
        for symbol in set(baseline) & set(modified)
        if baseline[symbol][0] != modified[symbol][0]
    )
    added = sorted(set(modified) - set(baseline))

    lines = [
        f"baseline_symbols={len(baseline)}",
        f"modified_symbols={len(modified)}",
        f"added_symbols={len(added)}",
        f"missing_symbols={len(missing)}",
        f"changed_crcs={len(changed)}",
    ]

    if changed:
        lines.append("\nChanged CRCs:")
        for symbol in changed:
            lines.append(
                f"{symbol} {baseline[symbol][0]} -> {modified[symbol][0]}"
            )
    if missing:
        lines.append("\nMissing baseline symbols:")
        lines.extend(missing)
    if added:
        lines.append("\nAdded symbols:")
        lines.extend(added)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:5]))

    if changed or missing:
        raise SystemExit(
            "Exported symbol ABI changed; inspect the uploaded ABI report"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
