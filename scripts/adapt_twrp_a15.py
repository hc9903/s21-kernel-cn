#!/usr/bin/env python3
"""A15 适配 o1q TWRP: fstab erofs/加密 + fallback 补丁 + BoardConfig TW_CUSTOM_*.

用法: python3 adapt_twrp_a15.py <device_tree> <twrp_src> <workspace>
  device_tree: device/samsung/o1q
  twrp_src:    bootable/recovery (TWRP 源码根, 相对 workspace)
  workspace:   repo 根目录 (含 scripts/)
"""

import subprocess
import sys
from pathlib import Path


def main() -> int:
    device_tree = Path(sys.argv[1])
    twrp_src = Path(sys.argv[2])
    workspace = Path(sys.argv[3])

    # 1. 更新 fstab
    fstab = device_tree / "recovery/root/system/etc/recovery.fstab"
    if not fstab.exists():
        print(f"[adapt] fstab 不存在: {fstab}")
        return 1
    lines = fstab.read_text(encoding="utf-8").splitlines()

    # 1a. 只读分区 ext4 -> erofs 双条目 (A15 用 EROFS)
    out = []
    for line in lines:
        parts = line.split()
        if (len(parts) >= 5 and parts[0] in ("system", "vendor", "product", "odm")
                and parts[2] == "ext4"):
            erofs_line = line.replace("ext4", "erofs", 1).replace("ro,barrier=1", "ro", 1)
            out.append(erofs_line)
            out.append(line)
        else:
            out.append(line)

    # 1b. /data 升级 A15 FBE v2 加密 flags
    for i, line in enumerate(out):
        if "/data" in line and "userdata" in line and "f2fs" in line:
            out[i] = (
                "/dev/block/bootdevice/by-name/userdata\t/data\tf2fs\t"
                "noatime,nosuid,nodev,discard,usrquota,grpquota,fsync_mode=nobarrier,"
                "reserve_root=32768,resgid=5678,inlinecrypt\t"
                "latemount,wait,check,fileencryption=aes-256-xts:aes-256-cts:v2,"
                "quota,reservedsize=128M,checkpoint=fs,fscompress,length=-20480,"
                "keydirectory=/metadata/vold/metadata_encryption"
            )

    fstab.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("[adapt] fstab 已更新 (erofs 双条目 + A15 /data 加密)")

    # 2. 应用 fallback 补丁 (un-decrypted /data 的 fallback 路径)
    patch_file = workspace / "scripts/twrp-a15-fallback.patch"
    if patch_file.exists():
        r = subprocess.run(
            ["patch", "-p1", "-d", str(twrp_src), "-i", str(patch_file)],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            print(f"[adapt] fallback 补丁未完全应用 (非致命):\n{r.stdout}\n{r.stderr}")
        else:
            print("[adapt] fallback 补丁已应用")
    else:
        print(f"[adapt] 警告: 找不到补丁文件 {patch_file}")

    # 3. BoardConfig.mk 追加 A15 配置
    board = device_tree / "BoardConfig.mk"
    with board.open("a", encoding="utf-8") as f:
        f.write("\n# A15 适配: un-decrypted /data fallback + logical partition tools\n")
        f.write("TW_CUSTOM_STORAGE_PATH := /cache\n")
        f.write("TW_CUSTOM_SETTINGS_PATH := /cache/recovery\n")
        f.write("TW_INCLUDE_LPDUMP := true\n")
        f.write("TW_INCLUDE_LPTOOLS := true\n")
    print("[adapt] BoardConfig.mk 已追加 TW_CUSTOM_* + LPDUMP/LPTOOLS")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
