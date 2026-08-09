#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Droidspaces kABI 修复脚本 (适配三星 S21 / o1q / SM-G9910 5.4.274 源码树)
============================================================
作用: 把 CONFIG_SYSVIPC / CONFIG_POSIX_MQUEUE 新增的 task_struct / user_struct
字段挪进 android-common (GKI 体系) 预置的 ANDROID_KABI_RESERVE 空位,
使开启这些选项时内核数据结构布局与三星原厂 (选项全关) 完全一致,
从而保证 /vendor 预编译模块的 ABI 不被破坏。

依据: Droidspaces 官方文档 Kernel-Configuration.md 的 GKI 章节
  https://github.com/ravindu644/Droidspaces-OSS/blob/main/Documentation/Kernel-Configuration.md#gki
官方补丁: Documentation/resources/kernel-patches/GKI/below-kernel-6.12/
  (本脚本等价于 001.fix_sysvipc_kabi + 002.posix_mqueue padding, 按本树上下文改写)

用法: python3 apply_kabi_fix.py   (在内核源码根目录执行)
每个替换必须恰好命中一次, 否则报错退出 (防止静默失败)。
"""
import re
import sys
from pathlib import Path

FAILS = []


def edit(path: str, old: str, new: str, what: str):
    p = Path(path)
    src = p.read_text()
    hits = list(re.finditer(old, src, re.S))
    if not hits:
        FAILS.append(f"{path}: 未找到 {what}")
        return
    if len(hits) != 1:
        FAILS.append(f"{path}: {what} 匹配到 {len(hits)} 处, 未修改")
        return
    m = hits[0]
    # 替换串按字面插入 (re.sub 的反斜杠语义不适用, 这里不允许 \1 之类)
    assert "\\1" not in new and "\\2" not in new, "替换串里不允许反引用"
    p.write_text(src[: m.start()] + new + src[m.end():])
    print(f"OK  {path}: {what}")


# ---------- 1) include/linux/sched.h: SYSVIPC 字段挪进 KABI 预留位 ----------
SCHED = "include/linux/sched.h"

edit(SCHED,
     r'#ifdef CONFIG_SYSVIPC\n\s*struct sysv_sem\s+sysvsem;\n\s*struct sysv_shm\s+sysvshm;\n#endif',
     '#ifdef CONFIG_SYSVIPC\n\t// struct sysv_sem\t\t\tsysvsem;\n\t// struct sysv_shm\t\t\tsysvshm;\n#endif',
     "SYSVIPC 内嵌字段注释掉 (hunk1)")

edit(SCHED,
     r'\tANDROID_KABI_RESERVE\(3\);\n\tANDROID_KABI_RESERVE\(4\);\n\tANDROID_KABI_RESERVE\(5\);\n'
     r'\tANDROID_KABI_RESERVE\(6\);\n\tANDROID_KABI_RESERVE\(7\);\n\tANDROID_KABI_RESERVE\(8\);',
     '\tANDROID_KABI_RESERVE(3);\n\tANDROID_KABI_RESERVE(4);\n\tANDROID_KABI_RESERVE(5);\n\n'
     '#ifdef CONFIG_SYSVIPC\n'
     '\tANDROID_KABI_USE(6, struct sysv_sem sysvsem);\n'
     '\t_ANDROID_KABI_REPLACE(ANDROID_KABI_RESERVE(7); ANDROID_KABI_RESERVE(8), struct sysv_shm sysvshm);\n'
     '#else\n'
     '\tANDROID_KABI_RESERVE(6);\n\tANDROID_KABI_RESERVE(7);\n\tANDROID_KABI_RESERVE(8);\n'
     '#endif',
     "SYSVIPC 字段放入 KABI 预留位 6/7/8 (hunk2)")

# ---------- 2) include/linux/sched/user.h: POSIX_MQUEUE mq_bytes 挪进预留位 ----------
USER_H = "include/linux/sched/user.h"

edit(USER_H,
     r'#ifdef CONFIG_POSIX_MQUEUE\n\s*/\* protected by mq_lock\s*\*/\n\s*unsigned long mq_bytes;'
     r'\s*/\* How many bytes can be allocated to mqueue\? \*/\n#endif',
     '#ifdef CONFIG_POSIX_MQUEUE\n\t/* protected by mq_lock\t*/\n'
     '\t//unsigned long mq_bytes;\t/* How many bytes can be allocated to mqueue? */\n#endif',
     "POSIX_MQUEUE mq_bytes 注释掉 (hunk1)")

edit(USER_H,
     r'\tANDROID_KABI_RESERVE\(1\);\n\tANDROID_KABI_RESERVE\(2\);\n};',
     '#if defined(CONFIG_POSIX_MQUEUE)\n'
     '\tANDROID_KABI_USE(1, unsigned long mq_bytes);\n'
     '\tANDROID_KABI_RESERVE(2);\n'
     '#else\n'
     '\tANDROID_KABI_RESERVE(1);\n\tANDROID_KABI_RESERVE(2);\n'
     '#endif\n};',
     "POSIX_MQUEUE mq_bytes 放入 KABI 预留位 1 (hunk2)")

if FAILS:
    print("\n[失败] 以下替换未完成:", file=sys.stderr)
    for f in FAILS:
        print(" -", f, file=sys.stderr)
    sys.exit(1)

print("\nkABI 修复全部应用成功")
