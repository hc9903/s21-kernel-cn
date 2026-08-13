#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kokubanify.py — 把三星 defconfig 改造成 Kokuban 风格(全内置内核)

策略(参考 YuzakiKokuban):
  1. 所有 CONFIG_X=m 改为 CONFIG_X=y (驱动全内置, 不再依赖 /vendor 模块)
  2. 关闭三星安全特性 (FASTUH/RKP/KDP, FIVE, GAF, KNOX_NCM, SECURITY_DEFEX, INTEGRITY)
  3. 追加 Droidspaces 配置片段
  4. 可选 KernelSU
  5. 自定义版本串 (全内置后版本串自由, 无需匹配原厂模块)

用法: python3 kokubanify.py <defconfig> <fragment|none> <localversion> <ksu:true|false>
"""
import os
import re
import sys
from pathlib import Path


def resolve(path, what="file"):
    """解析输入路径: 先按 CWD 相对解析, 再回退到 $GITHUB_WORKSPACE 下 (workflow 常在 kernel/ 目录下运行)."""
    p = Path(path)
    if p.exists():
        return p
    ws = os.environ.get("GITHUB_WORKSPACE")
    if ws:
        for cand in (Path(ws) / path, Path(ws) / Path(path).name):
            if cand.exists():
                return cand
    raise FileNotFoundError(
        f"{what} not found: {path} (cwd={Path.cwd()}, GITHUB_WORKSPACE={ws})"
    )


DEFCONFIG = resolve(sys.argv[1], "defconfig")
FRAGMENT = sys.argv[2]
LOCALVERSION = sys.argv[3]
KSU = sys.argv[4].lower() == "true"
# 可选第 5 参: keep_modules=true 时保留 =m (模块路线), 不转 =y (全内置路线默认转)
KEEP_MODULES = len(sys.argv) > 5 and sys.argv[5].lower() == "true"

# 1) 三星安全特性清单 (关闭)
DISABLE_SECURITY = [
    "CONFIG_FASTUH", "CONFIG_FASTUH_RKP", "CONFIG_FASTUH_KDP",
    "CONFIG_KNOX_NCM", "CONFIG_SECURITY_DEFEX", "CONFIG_SECURITY_DEFEX_USER",
    "CONFIG_GAF", "CONFIG_GAF_V3", "CONFIG_GAF_V6",
    "CONFIG_FIVE", "CONFIG_FIVE_GKI_10", "CONFIG_FIVE_GKI_20", "CONFIG_FIVE_DEBUG",
    "CONFIG_INTEGRITY", "CONFIG_INTEGRITY_SIGNATURE", "CONFIG_INTEGRITY_ASYMMETRIC_KEYS",
    "CONFIG_INTEGRITY_TRUSTED_KEYRING", "CONFIG_INTEGRITY_AUDIT",
    # HDM 驱动引用 fastuh_call, FASTUH 关闭后链接失败, 必须一起关
    "CONFIG_HDM",
]

src = DEFCONFIG.read_text()
lines = src.splitlines()
out = []
converted = 0

for line in lines:
    stripped = line.strip()
    # 1) =m → =y (全内置); keep_modules 时跳过此步, 保留 =m 走模块路线
    m = re.match(r"^(CONFIG_[A-Z0-9_]+)=m$", stripped)
    if m and not KEEP_MODULES:
        out.append(m.group(1) + "=y")
        converted += 1
        continue
    if m and KEEP_MODULES:
        out.append(line)
        continue
    # 2) 关闭三星安全: 已有 =y 的直接改写为 not set
    hit = False
    for sym in DISABLE_SECURITY:
        if stripped == sym + "=y":
            out.append("# " + sym + " is not set")
            hit = True
            break
    if hit:
        continue
    out.append(line)

# 2b) 没出现过的安全符号, 追加 not set
existing = set()
for line in out:
    stripped = line.strip()
    m = re.match(r"^# (CONFIG_[A-Z0-9_]+) is not set$", stripped)
    if m:
        existing.add(m.group(1))
    m = re.match(r"^(CONFIG_[A-Z0-9_]+)=", stripped)
    if m:
        existing.add(m.group(1))
appended_security = []
for sym in DISABLE_SECURITY:
    if sym not in existing:
        out.append("# " + sym + " is not set")
        appended_security.append(sym)

# 3) Droidspaces 片段
if FRAGMENT and FRAGMENT != "none":
    out.append("")
    out.extend(resolve(FRAGMENT, "fragment").read_text().splitlines())

# 4) KernelSU
if KSU:
    out.append("CONFIG_KSU=y")

# 5) 自定义版本串
if LOCALVERSION:
    if not LOCALVERSION.startswith("-"):
        LOCALVERSION = "-" + LOCALVERSION
    out.append("")
    out.append('CONFIG_LOCALVERSION="%s"' % LOCALVERSION)

DEFCONFIG.write_text("\n".join(out) + "\n")
print(f"kokubanify: {converted} 个 =m 转为 =y, 关闭 {len(appended_security)} 个安全符号"
      + (" + KSU" if KSU else "") + f" + localversion {LOCALVERSION}")
