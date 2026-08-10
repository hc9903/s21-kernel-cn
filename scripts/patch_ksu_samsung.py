#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KernelSU 三星适配补丁 (S21/o1q SM-G9910 5.4, KNOX 魔改内核)
1) sepolicy.c:  add_filename_trans 改用三星老式 filename_trans API
2) rules.c:     get_policydb 改用 selinux_state.ss
3) core_hook.c: ksu_umount_mnt 改用 d_path + ksys_umount (三星无 path_umount)
4) kernel_compat.c: strncpy_from_user_nofault 在 <5.8 用 strncpy_from_user
用法: 在内核源码根目录 python3 patch_ksu_samsung.py
"""
import sys
from pathlib import Path

def patch(rel, old, new, what):
    p = Path(rel)
    src = p.read_text()
    n = src.count(old)
    if n != 1:
        print(f"[失败] {rel} {what}: 命中 {n} 次 (期望 1 次)", file=sys.stderr)
        sys.exit(1)
    p.write_text(src.replace(old, new))
    print(f"OK  {rel}: {what}")

patch("KernelSU/kernel/selinux/sepolicy.c", '\tstruct filename_trans_key key;\n\tkey.ttype = tgt->value;\n\tkey.tclass = cls->value;\n\tkey.name = (char *)o;\n\n\tstruct filename_trans_datum *last = NULL;\n\n\tstruct filename_trans_datum *trans =\n\t\tpolicydb_filenametr_search(db, &key);\n\twhile (trans) {\n\t\tif (ebitmap_get_bit(&trans->stypes, src->value - 1)) {\n\t\t\t// Duplicate, overwrite existing data and return\n\t\t\ttrans->otype = def->value;\n\t\t\treturn true;\n\t\t}\n\t\tif (trans->otype == def->value)\n\t\t\tbreak;\n\t\tlast = trans;\n\t\ttrans = trans->next;\n\t}\n\n\tif (trans == NULL) {\n\t\ttrans = (struct filename_trans_datum *)kcalloc(sizeof(*trans),\n\t\t\t\t\t\t\t       1, GFP_ATOMIC);\n\t\tstruct filename_trans_key *new_key =\n\t\t\t(struct filename_trans_key *)kmalloc(sizeof(*new_key),\n\t\t\t\t\t\t\t     GFP_ATOMIC);\n\t\t*new_key = key;\n\t\tnew_key->name = kstrdup(key.name, GFP_ATOMIC);\n\t\ttrans->next = last;\n\t\ttrans->otype = def->value;\n\t\thashtab_insert(&db->filename_trans, new_key, trans,\n\t\t\t       filenametr_key_params);\n\t}\n\n\tdb->compat_filename_trans_count++;\n\treturn ebitmap_set_bit(&trans->stypes, src->value - 1, 1) == 0;\n}', '\tstruct filename_trans key;\n\tkey.stype = src->value;\n\tkey.ttype = tgt->value;\n\tkey.tclass = cls->value;\n\tkey.name = (char *)o;\n\n\tstruct filename_trans_datum *trans =\n\t\thashtab_search(db->filename_trans, &key);\n\tif (trans) {\n\t\t// 三星结构: 每个 key 只有一条规则, 直接覆盖 otype\n\t\ttrans->otype = def->value;\n\t\treturn true;\n\t}\n\n\ttrans = kzalloc(sizeof(*trans), GFP_ATOMIC);\n\tif (!trans)\n\t\treturn false;\n\ttrans->otype = def->value;\n\n\tstruct filename_trans *new_key = kzalloc(sizeof(*new_key), GFP_ATOMIC);\n\tif (!new_key) {\n\t\tkfree(trans);\n\t\treturn false;\n\t}\n\t*new_key = key;\n\tnew_key->name = kstrdup(key.name, GFP_ATOMIC);\n\tif (!new_key->name) {\n\t\tkfree(new_key);\n\t\tkfree(trans);\n\t\treturn false;\n\t}\n\n\treturn hashtab_insert(db->filename_trans, new_key, trans) == 0;\n}', "add_filename_trans 适配三星结构")
patch("KernelSU/kernel/selinux/rules.c", 'static struct policydb *get_policydb(void)\n{\n\tstruct policydb *db;\n\tstruct selinux_policy *policy = rcu_dereference(selinux_state.policy);\n\tdb = &policy->policydb;\n\treturn db;\n}', 'static struct policydb *get_policydb(void)\n{\n\tstruct policydb *db;\n\tstruct selinux_ss *ss = rcu_dereference(selinux_state.ss);\n\tdb = &ss->policydb;\n\treturn db;\n}', "get_policydb 用 selinux_state.ss")
patch("KernelSU/kernel/core_hook.c", 'static void ksu_umount_mnt(struct path *path, int flags)\n{\n\tint err = path_umount(path, flags);\n\tif (err) {\n\t\tpr_info("umount %s failed: %d\\n", path->dentry->d_iname, err);\n\t}\n}', 'static void ksu_umount_mnt(struct path *path, int flags)\n{\n\t// 三星 5.4 (KNOX) 无 path_umount 符号: 用 d_path 还原路径后调 ksys_umount\n\tchar *buf, *p;\n\tint err;\n\tmm_segment_t fs;\n\n\tbuf = (char *)__get_free_page(GFP_KERNEL);\n\tif (!buf) {\n\t\tpr_info("umount %s failed: ENOMEM\\n", path->dentry->d_iname);\n\t\treturn;\n\t}\n\tp = d_path(path, buf, PAGE_SIZE);\n\tif (IS_ERR(p)) {\n\t\tfree_page((unsigned long)buf);\n\t\tpr_info("umount %s failed: %ld\\n", path->dentry->d_iname,\n\t\t\tPTR_ERR(p));\n\t\treturn;\n\t}\n\tfs = get_fs();\n\tset_fs(KERNEL_DS);\n\terr = ksys_umount((char __user *)p, flags);\n\tset_fs(fs);\n\tfree_page((unsigned long)buf);\n\tif (err) {\n\t\tpr_info("umount %s failed: %d\\n", path->dentry->d_iname, err);\n\t}\n}', "ksu_umount_mnt 兼容 (无 path_umount)")
patch("KernelSU/kernel/core_hook.c", '#include <linux/capability.h>\n', '#include <linux/capability.h>\n#include <linux/syscalls.h>\n#include <linux/uaccess.h>\n', "补充 syscalls/uaccess include")
patch("KernelSU/kernel/kernel_compat.c", 'long ksu_strncpy_from_user_nofault(char *dst, const void __user *unsafe_addr,\n\t\t\t\t   long count)\n{\n\treturn strncpy_from_user_nofault(dst, unsafe_addr, count);\n}', 'long ksu_strncpy_from_user_nofault(char *dst, const void __user *unsafe_addr,\n\t\t\t\t   long count)\n{\n#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 8, 0)\n\treturn strncpy_from_user_nofault(dst, unsafe_addr, count);\n#else\n\treturn strncpy_from_user(dst, unsafe_addr, count);\n#endif\n}', "strncpy_from_user_nofault 兼容")
print("\nKernelSU 三星适配完成 (4 处)")
