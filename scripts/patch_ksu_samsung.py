#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KernelSU sepolicy.c 三星适配补丁 (S21/o1q SM-G9910 5.4 内核)

三星的 SELinux 是 KNOX 魔改版, 使用老式 filename_trans API:
  - struct filename_trans { stype; ttype; tclass; name; } (无 filename_trans_key)
  - struct filename_trans_datum { otype; } (无 stypes 位图 / next 链)
  - hashtab_insert(h, k, d) 3 参 (无 key_params)
  - policydb 无 compat_filename_trans_count
KernelSU v1.0.5 的 sepolicy.c 按 5.9+ 新 API 编写, 需改写 add_filename_trans。
用法: 在内核源码根目录 python3 patch_ksu_samsung.py, 必须恰好命中一次。
"""
import sys
from pathlib import Path

p = Path("KernelSU/kernel/selinux/sepolicy.c")
src = p.read_text()

old = '\tstruct filename_trans_key key;\n\tkey.ttype = tgt->value;\n\tkey.tclass = cls->value;\n\tkey.name = (char *)o;\n\n\tstruct filename_trans_datum *last = NULL;\n\n\tstruct filename_trans_datum *trans =\n\t\tpolicydb_filenametr_search(db, &key);\n\twhile (trans) {\n\t\tif (ebitmap_get_bit(&trans->stypes, src->value - 1)) {\n\t\t\t// Duplicate, overwrite existing data and return\n\t\t\ttrans->otype = def->value;\n\t\t\treturn true;\n\t\t}\n\t\tif (trans->otype == def->value)\n\t\t\tbreak;\n\t\tlast = trans;\n\t\ttrans = trans->next;\n\t}\n\n\tif (trans == NULL) {\n\t\ttrans = (struct filename_trans_datum *)kcalloc(sizeof(*trans),\n\t\t\t\t\t\t\t       1, GFP_ATOMIC);\n\t\tstruct filename_trans_key *new_key =\n\t\t\t(struct filename_trans_key *)kmalloc(sizeof(*new_key),\n\t\t\t\t\t\t\t     GFP_ATOMIC);\n\t\t*new_key = key;\n\t\tnew_key->name = kstrdup(key.name, GFP_ATOMIC);\n\t\ttrans->next = last;\n\t\ttrans->otype = def->value;\n\t\thashtab_insert(&db->filename_trans, new_key, trans,\n\t\t\t       filenametr_key_params);\n\t}\n\n\tdb->compat_filename_trans_count++;\n\treturn ebitmap_set_bit(&trans->stypes, src->value - 1, 1) == 0;\n}'
new = '\tstruct filename_trans key;\n\tkey.stype = src->value;\n\tkey.ttype = tgt->value;\n\tkey.tclass = cls->value;\n\tkey.name = (char *)o;\n\n\tstruct filename_trans_datum *trans =\n\t\thashtab_search(db->filename_trans, &key);\n\tif (trans) {\n\t\t// 三星结构: 每个 key 只有一条规则, 直接覆盖 otype\n\t\ttrans->otype = def->value;\n\t\treturn true;\n\t}\n\n\ttrans = kzalloc(sizeof(*trans), GFP_ATOMIC);\n\tif (!trans)\n\t\treturn false;\n\ttrans->otype = def->value;\n\n\tstruct filename_trans *new_key = kzalloc(sizeof(*new_key), GFP_ATOMIC);\n\tif (!new_key) {\n\t\tkfree(trans);\n\t\treturn false;\n\t}\n\t*new_key = key;\n\tnew_key->name = kstrdup(key.name, GFP_ATOMIC);\n\tif (!new_key->name) {\n\t\tkfree(new_key);\n\t\tkfree(trans);\n\t\treturn false;\n\t}\n\n\treturn hashtab_insert(db->filename_trans, new_key, trans) == 0;\n}'

n = src.count(old)
if n != 1:
    print(f"[失败] 旧代码块命中 {n} 次 (期望 1 次)", file=sys.stderr)
    sys.exit(1)

p.write_text(src.replace(old, new))
print("OK  KernelSU sepolicy.c: add_filename_trans 已适配三星 SELinux 结构")
