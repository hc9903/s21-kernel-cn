#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_droidspaces_kr.py — 韩版 Fold3 Droidspaces 4 处改动 → S21 港版移植"""
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

# ① module.c
c = module_c.read_text()
old = '\tpr_warn("%s: disagrees about version of symbol %s\\n",\n\t       info->name, symname);\n\treturn 0;'
new = '\tpr_warn("%s: disagrees about version of symbol %s, but ignoring (droidspaces: opensource kernel cannot match production symbol CRCs)\\n",\n\t       info->name, symname);\n\treturn 1;'
if old in c:
    module_c.write_text(c.replace(old, new)); count += 1
    print("[OK] module.c: bad_version return 0 -> 1")
else:
    err("module.c 未命中")

# ② sched.h SYSVIPC
s = sched_h.read_text()
old_s = "\n#ifdef CONFIG_SYSVIPC\n\tstruct sysv_sem\t\t\tsysvsem;\n\tstruct sysv_shm\t\t\tsysvshm;\n#endif"
new_s_comment = "\n#ifdef CONFIG_SYSVIPC\n\t/* droidspaces: sysvsem/sysvshm moved to ANDROID_KABI_USE below */\n#endif"
if old_s in s:
    s = s.replace(old_s, new_s_comment, 1)
    anchor = "\tANDROID_KABI_RESERVE(8);"
    if anchor in s:
        kbd = ("\n#ifdef CONFIG_SYSVIPC\n"
               "\tANDROID_KABI_USE(6, struct sysv_sem sysvsem);\n"
               "\t_ANDROID_KABI_REPLACE(ANDROID_KABI_RESERVE(7); ANDROID_KABI_RESERVE(8), struct sysv_shm sysvshm);\n"
               "#else\n"
               "\tANDROID_KABI_RESERVE(7);\n"
               "\tANDROID_KABI_RESERVE(8);\n"
               "#endif")
        s = s.replace(anchor, anchor + kbd, 1)
        sched_h.write_text(s); count += 1
        print("[OK] sched.h: SYSVIPC kABI padding (USE 6 / 7,8)")
    else:
        err("sched.h RESERVE(8) 锚点未命中")
else:
    err("sched.h CONFIG_SYSVIPC 原字段未命中: repr=" + repr(old_s[:60]))

# ③ user.h POSIX_MQUEUE
u = user_h.read_text()
old_u = "\n#ifdef CONFIG_POSIX_MQUEUE\n\t/* protected by mq_lock\t*/\n\tunsigned long mq_bytes;\t/* How many bytes can be allocated to mqueue? */\n#endif"
new_u = "\n#ifdef CONFIG_POSIX_MQUEUE\n\t/* droidspaces: mq_bytes moved to ANDROID_KABI_USE below */\n#endif"
if old_u in u:
    u = u.replace(old_u, new_u, 1)
    anchor_u = "\tANDROID_KABI_RESERVE(2);\n};"
    if anchor_u in u:
        kbu = ("\t#ifdef CONFIG_POSIX_MQUEUE\n"
               "\tANDROID_KABI_USE(1, unsigned long mq_bytes);\n"
               "\tANDROID_KABI_RESERVE(2);\n"
               "\t#else\n"
               "\tANDROID_KABI_RESERVE(1);\n"
               "\tANDROID_KABI_RESERVE(2);\n"
               "\t#endif\n};")
        u = u.replace(anchor_u, kbu, 1)
        user_h.write_text(u); count += 1
        print("[OK] user.h: POSIX_MQUEUE kABI padding (USE 1+)")
    else:
        err("user.h RESERVE(2) 锚点未命中")
else:
    err("user.h CONFIG_POSIX_MQUEUE 原字段未命中: repr=" + repr(old_u[:60]))

# ④ defconfig KDP
d = defconfig.read_text()
if "CONFIG_FASTUH_KDP=y" in d:
    d = d.replace("CONFIG_FASTUH_KDP=y", "# CONFIG_FASTUH_KDP is not set")
    defconfig.write_text(d); count += 1
    print("[OK] defconfig: FASTUH_KDP=y -> not set (保留 FASTUH+RKP)")
else:
    err("defconfig FASTUH_KDP 未命中")

print(f"\n完成: {count}/4 处改动已应用")