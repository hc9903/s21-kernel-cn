#!/usr/bin/env bash
# 修复 vendor_boot: 移除 Droidspaces 内核已内置(=y)的 pinctrl 模块, 防止 duplicate symbol panic
# 原理: init 加载 /lib/modules/5.4-gki/*.ko; 若内核已内置某驱动(=y), 再加载对应 .ko
#       会报 "exports duplicate symbol ... (owned by kernel)" -> 模块拒载 -> init panic。
# 用法: fix_vendor_boot.sh <vendor_boot.img> <magiskboot> [out.img]
set -uo pipefail

VB_IN="${1:?vendor_boot.img}"
MAGISKBOOT="${2:?magiskboot path}"
OUT="$(realpath "${3:-vendor_boot_droidspaces_fix.img}")"

# 内核已内置(=y)需要在 modules.load 里移除的模块 (按 S21 港版实测)
REMOVE_MODS="pinctrl-msm pinctrl-lahaina pinctrl-shima pinctrl-yupik"

WORK=$(mktemp -d /tmp/vbfix.XXXXXX)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

echo "=== 解包 vendor_boot ==="
"$MAGISKBOOT" unpack "$VB_IN" >/tmp/vb_unpack.log 2>&1 || true
if [ ! -f ramdisk.cpio ] || [ ! -f dtb ]; then
  echo "!! 解包失败: 缺 ramdisk.cpio/dtb"; cat /tmp/vb_unpack.log; exit 1
fi

extract() { # extract <path-in-cpio> <local-out>
  "$MAGISKBOOT" cpio ramdisk.cpio "extract $1 $2" >/dev/null 2>&1 && [ -f "$2" ]
}
add_file() { # add <mode> <path-in-cpio> <local-src>
  "$MAGISKBOOT" cpio ramdisk.cpio "add $1 $2 $3" >/dev/null 2>&1 || true
  # 验证: add 后能提取回且一致
  "$MAGISKBOOT" cpio ramdisk.cpio "extract $2 $3.cmp" >/dev/null 2>&1
  if cmp -s "$3" "$3.cmp"; then :; else echo "!! add $2 验证失败"; exit 1; fi
  rm -f "$3.cmp"
}

echo "=== 提取模块元数据 ==="
extract lib/modules/5.4-gki/modules.load ml || { echo "!! 无 modules.load"; exit 1; }
extract lib/modules/5.4-gki/modules.dep mdep || true
extract lib/modules/5.4-gki/modules.softdep msoftdep || true

echo "=== 修改前 modules.load ($(wc -l < ml) 行) ==="
cat ml

echo "=== 移除内核已内置模块: 复刻能开机手机实测版的完整逻辑 ==="
# 手机实测版行为:
#  1. modules.load: 删除 pinctrl-msm/lahaina/shima/yupik 条目
#  2. modules.dep: 删除 pinctrl-msm 独立行; 从 sdhci-msm 等其他模块的依赖里移除 pinctrl-msm.ko;
#     保留 pinctrl-yupik/shima/lahaina 的空行(它们不再依赖 pinctrl-msm)
for m in $REMOVE_MODS; do
  sed -i "/^${m}\.ko$/d" ml
done
if [ -f mdep ]; then
  # 删除 pinctrl-msm.ko 独立行
  sed -i "/^\/lib\/modules\/5.4-gki\/pinctrl-msm\.ko:/d" mdep
  # 从所有依赖列表里移除 pinctrl-msm.ko (替换为空)
  sed -i "s# /lib/modules/5.4-gki/pinctrl-msm\.ko##g" mdep
  # pinctrl-yupik/shima/lahaina 行: 去掉依赖(变空行), 保留行本身 (与手机版一致)
  for m in pinctrl-yupik pinctrl-shima pinctrl-lahaina; do
    sed -i "s#^/lib/modules/5.4-gki/${m}\.ko: .*#/lib/modules/5.4-gki/${m}.ko:#" mdep
  done
fi
# modules.softdep: 移除 pinctrl_msm pre (与手机版一致)
if [ -f msoftdep ]; then
  sed -i "/pinctrl_msm/d" msoftdep
fi

echo "=== 修改后 modules.load ($(wc -l < ml) 行) ==="
cat ml

echo "=== 重新打包 ramdisk (回填 modules.load + modules.dep + modules.softdep) ==="
add_file 644 lib/modules/5.4-gki/modules.load ml
[ -f mdep ] && add_file 644 lib/modules/5.4-gki/modules.dep mdep
[ -f msoftdep ] && add_file 644 lib/modules/5.4-gki/modules.softdep msoftdep

echo "=== 重新打包 vendor_boot ==="
"$MAGISKBOOT" repack "$VB_IN" "$OUT" >/dev/null 2>&1 || true
[ -f "$OUT" ] || { echo "!! repack 失败"; exit 1; }
echo "输出: $OUT ($(stat -c%s "$OUT") 字节)"

echo "=== 验证: 修复后 modules.load 无 pinctrl ==="
VW=$(mktemp -d /tmp/vbfixv.XXXXXX); cd "$VW"
"$MAGISKBOOT" unpack "$OUT" >/dev/null 2>&1 || true
"$MAGISKBOOT" cpio ramdisk.cpio "extract lib/modules/5.4-gki/modules.load vl" >/dev/null 2>&1
if grep -q pinctrl vl 2>/dev/null; then echo "!! 仍有 pinctrl 残留"; exit 1; else echo "OK: 修复版 modules.load 无 pinctrl"; fi
echo "验证通过, 修复版 vendor_boot 可用"
rm -rf "$VW"
echo "完成"