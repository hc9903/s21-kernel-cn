#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_droidspaces_kr.py — 韩版 Fold3 Droidspaces 4 处改动 → S21 港版移植
修复: kABI 用"就地替换 RESERVE 位"而非"文件末尾追加" (追加会重复声明 redeclare)
"""
import sys
from pathlib import Path

def err(msg):
    print("ERROR:", msg); sys.exit(1)

root = Path(sys.argv[1])
sched_h = root / "include/linux/sched.h"
user_h  = root / "include/linux/sched/user.h"
module_c= root / "kernel/module.c"
defconfig = root / "arch/arm64/configs/vendor/o1q_chn_hkx_defconfig"
count = 0

# ---------- ① module.c: CRC ignore ----------
c = module_c.read_text()
old = '\tpr_warn("%s: disagrees about version of symbol %s\\n",\n\t       info->name, symname);\n\treturn 0;'
new = '\tpr_warn("%s: disagrees about version of symbol %s, but ignoring (droidspaces: opensource kernel cannot match production symbol CRCs)\\n",\n\t       info->name, symname);\n\treturn 1;'
if old in c:
    module_c.write_text(c.replace(old, new)); count += 1
    print("[OK] module.c: bad_version return 0 -> 1")
else:
    err("module.c 未命中")

# ---------- ② sched.h: SYSVIPC kABI —— 就地替换 RESERVE(6/7/8) ----------
s = sched_h.read_text()

# 2a) 删掉 CONFIG_SYSVIPC 下的原字段 (1080-1081)
old_field = "\n#ifdef CONFIG_SYSVIPC\n\tstruct sysv_sem\t\t\tsysvsem;\n\tstruct sysv_shm\t\t\tsysvshm;\n#endif"
new_field = "\n#ifdef CONFIG_SYSVIPC\n\t/* droidspaces: sysvsem/sysvshm relocated to ANDROID_KABI_USE(RESERVE 6/7/8) */\n#endif"
if old_field in s:
    s = s.replace(old_field, new_field, 1)
    changed_field = True
else:
    changed_field = False

# 2b) 就地替换 RESERVE(6) -> KABI_USE, RESERVE(7..8) -> kABI replace
old_reserve = "\tANDROID_KABI_RESERVE(5);\n\tANDROID_KABI_RESERVE(6);\n\tANDROID_KABI_RESERVE(7);\n\tANDROID_KABI_RESERVE(8);"
new_reserve = ("\tANDROID_KABI_RESERVE(5);\n"
               "\t#ifdef CONFIG_SYSVIPC\n"
               "\tANDROID_KABI_USE(6, struct sysv_sem sysvsem);\n"
               "\t_ANDROID_KABI_REPLACE(ANDROID_KABI_RESERVE(7); ANDROID_KABI_RESERVE(8), struct sysv_shm sysvshm);\n"
               "\t#else\n"
               "\tANDROID_KABI_RESERVE(6);\n"
               "\tANDROID_KABI_RESERVE(7);\n"
               "\tANDROID_KABI_RESERVE(8);\n"
               "\t#endif")
if old_reserve in s:
    s = s.replace(old_reserve, new_reserve, 1)
    if changed_field:
        sched_h.write_text(s); count += 1
        print("[OK] sched.h: SYSVIPC kABI (就地替换 RESERVE 6/7/8)")
    else:
        err("sched.h 原 sysvsem 字段未命中(已第二步, 但原字段找不到)")
else:
    err("sched.h RESERVE 5-8 块未命中")

# ---------- ③ user.h: POSIX_MQUEUE kABI —— 就地替换 ----------
u = user_h.read_text()
old_u_field = "\n#ifdef CONFIG_POSIX_MQUEUE\n\t/* protected by mq_lock\t*/\n\tunsigned long mq_bytes;\t/* How many bytes can be allocated to mqueue? */\n#endif"
new_u_field = "\n#ifdef CONFIG_POSIX_MQUEUE\n\t/* droidspaces: mq_bytes relocated to ANDROID_KABI_USE(RESERVE 1) */\n#endif"
if old_u_field in u:
    u = u.replace(old_u_field, new_u_field, 1)
old_u_reserve = "\tANDROID_KABI_RESERVE(1);\n\tANDROID_KABI_RESERVE(2);\n};"
new_u_reserve = ("\t#ifdef CONFIG_POSIX_MQUEUE\n"
                 "\tANDROID_KABI_USE(1, unsigned long mq_bytes);\n"
                 "\tANDROID_KABI_RESERVE(2);\n"
                 "\t#else\n"
                 "\tANDROID_KABI_RESERVE(1);\n"
                 "\tANDROID_KABI_RESERVE(2);\n"
                 "\t#endif\n};")
if old_u_reserve in u:
    u = u.replace(old_u_reserve, new_u_reserve, 1)
    user_h.write_text(u); count += 1
    print("[OK] user.h: POSIX_MQUEUE kABI (就地替换 RESERVE 1)")
else:
    err("user.h RESERVE 1-2 块未命中")

# ---------- ④ defconfig: KDP ----------
d = defconfig.read_text()
if "CONFIG_FASTUH_KDP=y" in d:
    d = d.replace("CONFIG_FASTUH_KDP=y", "# CONFIG_FASTUH_KDP is not set")
    defconfig.write_text(d); count += 1
    print("[OK] defconfig: FASTUH_KDP=y -> not set (保留 FASTUH+RKP)")
else:
    err("defconfig FASTUH_KDP 未命中")

print(f"\n完成: {count}/4 处改动已应用")