#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""merge_droidspaces_config.py — 按 Droidspaces 官方 GKI 规则逐项 merge 配置到 S21 defconfig

官方工作流程规则 (Kernel Configuration / GKI 部分):
  - 不要将配置作为代码块追加到文件末尾
  - 逐个搜索每个选项:
      若 `# CONFIG_X is not set`  -> 改成 CONFIG_X=y
      若 `CONFIG_X=y`            -> 保持不变
      若不存在                    -> 在末尾追加
用法: python3 merge_droidspaces_config.py <defconfig路径> [enable_ufw_fail2ban true|false]
"""
import sys
from pathlib import Path

def err(m): print("ERROR:", m); sys.exit(1)

path = Path(sys.argv[1])
ufw = len(sys.argv) > 2 and sys.argv[2].lower() == "true"

# Droidspaces GKI 必需 + 推荐配置 (逐个 item, 按官方规则处理)
REQUIRED = [
    "SYSVIPC", "POSIX_MQUEUE",
    "IPC_NS", "PID_NS", "UTS_NS", "USER_NS", "NAMESPACES",
    "DEVTMPFS",
    "TMPFS_XATTR", "TMPFS_POSIX_ACL",
    "NETFILTER_XT_MATCH_ADDRTYPE", "NF_CT_NETLINK",
]
# ufw_fail2ban=true 时额外开启 (ipset/recent, 仅新增匹配器不改符号CRC)
UFW_EXTRA = [
    "NETFILTER_XT_MATCH_RECENT", "IP_SET", "IP_SET_HASH_IP", "IP_SET_HASH_NET", "NETFILTER_XT_SET",
]

lines = path.read_text().split("\n")

def set_line_y(lines, sym):
    """就地: not set -> y, 已 y 保持, 缺则返回 False 表示需追加"""
    pat_on  = f"CONFIG_{sym}=y"
    pat_off = f"# CONFIG_{sym} is not set"
    for i, ln in enumerate(lines):
        if ln == pat_on:
            return ("keep", i)
        if ln == pat_off:
            lines[i] = pat_on
            return ("turned_on", i)
    return ("absent", None)

# 逐项 merge
for sym in REQUIRED + (UFW_EXTRA if ufw else []):
    action, idx = set_line_y(lines, sym)
    if action == "absent":
        lines.append(f"CONFIG_{sym}=y")   # 不存在 -> 末尾追加 (官方规则允许)
        print(f"  {sym}: 不存在 -> 末尾追加 =y")
    elif action == "turned_on":
        print(f"  {sym}: not set -> =y (就地, 第{idx+1}行)")
    else:
        print(f"  {sym}: 已是 =y, 保持不变")

path.write_text("\n".join(lines))
# 去掉可能的重复空行
txt = path.read_text()
while "\n\n\n" in txt: txt = txt.replace("\n\n\n", "\n\n")
path.write_text(txt)
print(f"\n完成: 逐项 merge 就位于 {path} (ufw_fail2ban={ufw})")
print("验证无重复定义:")
import re
for sym in REQUIRED + (UFW_EXTRA if ufw else []):
    cnt = len(re.findall(rf"^CONFIG_{sym}=(?:y|m|n)$", txt, re.M))
    if cnt > 1: print(f"  ⚠️ {sym} 出现 {cnt} 次 (异常)")
print("OK: 每个配置只出现一次")