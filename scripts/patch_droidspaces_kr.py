#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_droidspaces_kr.py — 韩版 Fold3 Droidspaces 方案 → S21 港版移植 (完整 6 处)
修复: kABI 就地替换 RESERVE 位 (非末尾追加); 补齐 cgroup.c + defex_rules.c
"""
import sys
from pathlib import Path

def err(msg):
    print("ERROR:", msg); sys.exit(1)

root = Path(sys.argv[1])
sched_h = root / "include/linux/sched.h"
user_h  = root / "include/linux/sched/user.h"
module_c= root / "kernel/module.c"
cgroup_c= root / "kernel/cgroup/cgroup.c"
defex_rules_c = root / "security/samsung/defex_lsm/defex_rules.c"
defconfig = root / "arch/arm64/configs/vendor/o1q_chn_hkx_defconfig"
count = 0

# ---------- ① module.c: CRC ignore ----------
c = module_c.read_text()
old = '\tpr_warn("%s: disagrees about version of symbol %s\\n",\n\t       info->name, symname);\n\treturn 0;'
new = '\tpr_warn("%s: disagrees about version of symbol %s, but ignoring (droidspaces: opensource kernel cannot match production symbol CRCs)\\n",\n\t       info->name, symname);\n\treturn 1;'
if old in c:
    module_c.write_text(c.replace(old, new)); count += 1
    print("[OK] 1/6 module.c: bad_version return 0 -> 1")
else:
    err("module.c 未命中")

# ---------- ② sched.h: SYSVIPC kABI, 就地替换 RESERVE(6/7/8) ----------
s = sched_h.read_text()
old_field = "\n#ifdef CONFIG_SYSVIPC\n\tstruct sysv_sem\t\t\tsysvsem;\n\tstruct sysv_shm\t\t\tsysvshm;\n#endif"
new_field = "\n#ifdef CONFIG_SYSVIPC\n\t/* droidspaces: sysvsem/sysvshm relocated to ANDROID_KABI_USE(RESERVE 6/7/8) */\n#endif"
if old_field not in s:
    err("sched.h 原 sysvsem 字段未命中")
s = s.replace(old_field, new_field, 1)
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
if old_reserve not in s:
    err("sched.h RESERVE 5-8 块未命中")
s = s.replace(old_reserve, new_reserve, 1)
sched_h.write_text(s); count += 1
print("[OK] 2/6 sched.h: SYSVIPC kABI padding (就地替换 RESERVE 6/7/8)")

# ---------- ③ user.h: POSIX_MQUEUE kABI, 就地替换 RESERVE(1) ----------
u = user_h.read_text()
old_u_field = "\n#ifdef CONFIG_POSIX_MQUEUE\n\t/* protected by mq_lock\t*/\n\tunsigned long mq_bytes;\t/* How many bytes can be allocated to mqueue? */\n#endif"
new_u_field = "\n#ifdef CONFIG_POSIX_MQUEUE\n\t/* droidspaces: mq_bytes relocated to ANDROID_KABI_USE(RESERVE 1) */\n#endif"
if old_u_field not in u:
    err("user.h 原 mq_bytes 字段未命中")
u = u.replace(old_u_field, new_u_field, 1)
old_u_reserve = "\tANDROID_KABI_RESERVE(1);\n\tANDROID_KABI_RESERVE(2);\n};"
new_u_reserve = ("\t#ifdef CONFIG_POSIX_MQUEUE\n"
                 "\tANDROID_KABI_USE(1, unsigned long mq_bytes);\n"
                 "\tANDROID_KABI_RESERVE(2);\n"
                 "\t#else\n"
                 "\tANDROID_KABI_RESERVE(1);\n"
                 "\tANDROID_KABI_RESERVE(2);\n"
                 "\t#endif\n};")
if old_u_reserve not in u:
    err("user.h RESERVE 1-2 块未命中")
u = u.replace(old_u_reserve, new_u_reserve, 1)
user_h.write_text(u); count += 1
print("[OK] 3/6 user.h: POSIX_MQUEUE kABI padding (就地替换 RESERVE 1)")

# ---------- ④ defconfig: KDP ----------
d = defconfig.read_text()
if "CONFIG_FASTUH_KDP=y" not in d:
    err("defconfig FASTUH_KDP 未命中")
d = d.replace("CONFIG_FASTUH_KDP=y", "# CONFIG_FASTUH_KDP is not set")
# 官方 010 补丁附带: 强制加载模块 (韩版虽未开, 但官方推荐且无害, 增强保留stock模块路线)
if "# CONFIG_MODULE_FORCE_LOAD is not set" in d:
    d = d.replace("# CONFIG_MODULE_FORCE_LOAD is not set", "CONFIG_MODULE_FORCE_LOAD=y")
elif "CONFIG_MODULE_FORCE_LOAD=y" not in d:
    d += "\n# Droidspaces: force-load modules (official 010.Disable-CRC-Checks custom.config)\nCONFIG_MODULE_FORCE_LOAD=y\n"
defconfig.write_text(d); count += 1
print("[OK] 4/6 defconfig: FASTUH_KDP=off + MODULE_FORCE_LOAD=y")

# ---------- ⑤ cgroup.c: cgroup 文件 link 补丁 (Droidspaces 容器必需) ----------
g = cgroup_c.read_text()
if "kernfs_create_link(cgrp->kn, name, kn);" in g:
    print("SKIP 5/6 cgroup.c: 已包含 (防重复)")
else:
    anchor_g = (
        "\t\tcfile->kn = kn;\n"
        "\t\tspin_unlock_irq(&cgroup_file_kn_lock);\n"
        "\t}\n"
        "\n"
        "\treturn 0;\n"
    )
    add_g = (
        "\t\tcfile->kn = kn;\n"
        "\t\tspin_unlock_irq(&cgroup_file_kn_lock);\n"
        "\t}\n"
        "\n"
        "\tif (cft->ss && (cgrp->root->flags & CGRP_ROOT_NOPREFIX) && !(cft->flags & CFTYPE_NO_PREFIX)) {\n"
        "\t\t\t\tsnprintf(name, CGROUP_FILE_NAME_MAX, \"%s.%s\", cft->ss->name, cft->name);\n"
        "\t\t\t\tkernfs_create_link(cgrp->kn, name, kn);\n"
        "\t}\n"
        "\n"
        "\treturn 0;\n"
    )
    if anchor_g in g:
        g = g.replace(anchor_g, add_g, 1)
        cgroup_c.write_text(g); count += 1
        print("[OK] 5/6 cgroup.c: cgroup 文件 link 补丁")
    else:
        err("cgroup.c 锚点未命中")

# ---------- ⑥ defex_rules.c: app_process 例外 (Droidspaces 运行必需) ----------
dr = defex_rules_c.read_text()
if 'feature_immutable_tgt_exception,"/system/bin/app_process32"' in dr:
    print("SKIP 6/6 defex_rules.c: 已包含 app_process 例外")
else:
    anchor_dr = '\t{feature_immutable_src_exception,"/vendor/bin/hw/android.hardware.biometrics.face@2.0-service"},'
    add_dr = ('\t{feature_immutable_src_exception,"/vendor/bin/hw/android.hardware.biometrics.face@2.0-service"},\n'
              '\t{feature_immutable_tgt_exception,"/system/bin/app_process32"},\n'
              '\t{feature_immutable_tgt_exception,"/system/bin/app_process64"},')
    if anchor_dr in dr:
        dr = dr.replace(anchor_dr, add_dr, 1)
        defex_rules_c.write_text(dr); count += 1
        print("[OK] 6/6 defex_rules.c: app_process32/64 例外")
    else:
        err("defex_rules.c 锚点未命中")

print(f"\n完成: {count}/6 处改动已应用")