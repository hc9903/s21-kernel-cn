#!/usr/bin/env python3
"""Compare two Module.symvers (stock vs Route b) vmlinux exports.

Determines whether stock prebuilt /vendor modules can load with the
Route b kernel (security off + KSU): a stock module loads iff every
symbol it imports is still exported with an IDENTICAL CRC.

Outputs counts + the exact removed/changed symbols, tagged security vs
driver so the verdict is human-readable.
"""

import sys
from pathlib import Path

SECURITY_HINTS = (
    "security_", "sec_", "secgpio_", "defex_", "five_", "integrity_",
    "knox_", "hdm_", "fastuh_", "rkp_", "proca_", "dualpi_", "ssrm_",
    "dsms_", "gaf_", "slsi_security", "exynos_", "secmem_", "tima_",
    "stui_", "kdp_", "sdp_", "kdp", "fips_", "crypto_selftest",
)


def load_vmlinux_exports(path: Path) -> dict[str, str]:
    exports: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        crc, symbol, module = parts[:3]
        if module != "vmlinux":
            continue
        exports[symbol] = crc.lower()
    return exports


def tag(symbol: str) -> str:
    low = symbol.lower()
    for hint in SECURITY_HINTS:
        if hint in low:
            return "security"
    return "driver-ish"


def main(stock_path: str, routeb_path: str, out_path: str) -> int:
    stock = load_vmlinux_exports(Path(stock_path))
    routeb = load_vmlinux_exports(Path(routeb_path))

    stock_set = set(stock)
    routeb_set = set(routeb)

    removed = sorted(stock_set - routeb_set)
    added = sorted(routeb_set - stock_set)
    common = stock_set & routeb_set
    changed = sorted(s for s in common if stock[s] != routeb[s])
    same = sorted(s for s in common if stock[s] == routeb[s])

    removed_security = [s for s in removed if tag(s) == "security"]
    removed_driver = [s for s in removed if tag(s) != "security"]
    changed_security = [s for s in changed if tag(s) == "security"]
    changed_driver = [s for s in changed if tag(s) != "security"]

    # A stock module breaks only if it imports a removed symbol or a
    # changed-CRC symbol. Security symbols are not imported by drivers.
    dangerous = removed_driver + changed_driver

    lines = []
    lines.append("=== ABI 对比: stock HZE1 vs Route b (关安全+KSU) ===")
    lines.append(f"stock vmlinux 导出: {len(stock)}")
    lines.append(f"routeb vmlinux 导出: {len(routeb)}")
    lines.append("")
    lines.append(f"移除的符号 (安全类): {len(removed_security)}")
    lines.append(f"移除的符号 (驱动类): {len(removed_driver)}")
    lines.append(f"CRC 改变的符号 (安全类): {len(changed_security)}")
    lines.append(f"CRC 改变的符号 (驱动类): {len(changed_driver)}")
    lines.append(f"CRC 完全一致的公共符号: {len(same)}")
    lines.append(f"新增符号 (KSU 等, 无害): {len(added)}")
    lines.append("")
    lines.append(f"=== 危险符号 (会导致 stock 模块拒载) 共 {len(dangerous)} 个 ===")
    if dangerous:
        for s in dangerous:
            lines.append(f"  - {s}  ({tag(s)})  stock_crc={stock[s]}  routeb_crc={routeb.get(s, 'GONE')}")
    else:
        lines.append("  (无) — stock 预编译模块理论上能全部正常加载")
    lines.append("")
    lines.append("=== 移除的安全符号 (驱动不依赖, 可忽略) ===")
    for s in removed_security:
        lines.append(f"  - {s}")
    lines.append("")
    lines.append("=== CRC 改变的安全符号 (驱动不依赖, 可忽略) ===")
    for s in changed_security:
        lines.append(f"  - {s}  stock={stock[s]} routeb={routeb[s]}")

    verdict = "PASS" if not dangerous else "FAIL"
    lines.append("")
    lines.append(f"VERDICT: {verdict}  "
                 f"{'stock 模块可加载 (无需 TWRP 装重编模块)' if verdict == 'PASS' else '需要 TWRP 装重编模块'}")

    report = "\n".join(lines) + "\n"
    Path(out_path).write_text(report, encoding="utf-8")
    print(report)
    return 0 if not dangerous else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1], sys.argv[2], sys.argv[3]))
