#!/usr/bin/env bash
# pack_modules_twrp.sh — 打包 TWRP 刷机 zip (boot.img + 重编模块)
# 用法: 通过环境变量传入
#   BOOT_IMG        : 已回包的 boot.img (repack_ksu_boot.sh 产物)
#   MODULES_ROOT    : make modules_install 的 INSTALL_MOD_PATH (含 lib/modules/<ver>/...)
#   UPDATE_BINARY   : update-binary 脚本路径
#   OUTPUT_DIR      : 产物目录
#   KERNEL_RELEASE  : 内核版本串 (用于 zip 内文件名与 NOTICE)
set -euo pipefail

: "${BOOT_IMG:?BOOT_IMG required}"
: "${MODULES_ROOT:?MODULES_ROOT required}"
: "${UPDATE_BINARY:?UPDATE_BINARY required}"
: "${OUTPUT_DIR:?OUTPUT_DIR required}"
: "${KERNEL_RELEASE:?KERNEL_RELEASE required}"

out=$(realpath -m "$OUTPUT_DIR")
mkdir -p "$out"
work=$(mktemp -d "${RUNNER_TEMP:-/tmp}/ksu-modules-pack.XXXXXX")
trap 'rm -rf "$work"' EXIT

# 1) 收集所有 .ko (flatten 到 modules/)
mkdir -p "$work/modules"
ko_count=0
while IFS= read -r -d '' ko; do
  cp -f "$ko" "$work/modules/" 2>/dev/null && ko_count=$((ko_count+1))
done < <(find "$MODULES_ROOT" -name '*.ko' -print0)

echo "收集到 $ko_count 个 .ko 模块"
[ "$ko_count" -gt 0 ] || { echo "错误: 没有找到任何 .ko 模块!"; exit 1; }

# 2) boot.img + update-binary
cp -f "$BOOT_IMG" "$work/boot.img"
mkdir -p "$work/META-INF/com/google/android"
cp -f "$UPDATE_BINARY" "$work/META-INF/com/google/android/update-binary"
chmod 0755 "$work/META-INF/com/google/android/update-binary"

# 3) 打 zip (store 模式对 boot.img 无意义, 直接默认压缩)
zip_name="KSU-modules-${KERNEL_RELEASE//\//_}.zip"
(
  cd "$work"
  zip -r -9 "$out/$zip_name" META-INF boot.img modules >/dev/null
)

# 4) NOTICE + SHA256SUMS
cat >"$out/NOTICE.txt" <<EOF
S21 (SM-G9910, o1q) 保留模块内核 + KernelSU v1.0.5
Kernel release: $KERNEL_RELEASE
- 源码: Samsung G9910ZCUBHYDA OSRC (与 HZE1 同 changelist 2370012)
- 路线: 保留 66 个 =m 驱动, 重编模块 + 匹配 vermagic, 更贴近原厂加载顺序
- KernelSU: v1.0.5 + 三星 KNOX 五补丁 (scripts/patch_ksu_samsung.py)
- 关三星安全: FASTUH/RKP/KDP/FIVE/GAF/INTEGRITY/DEFEX/KNOX_NCM/HDM
- 模块数: $ko_count (含 techpack camera/audio DLKM)
刷机: TWRP 刷入本 zip (adb sideload 或 push 后 install)
救机: Odin 刷回 boot_stock.tar (magisk-boot-G9910ZCUGHZE1 release)
EOF

(
  cd "$out"
  set +e  # 报告段容忍 find|head 的 SIGPIPE (pipefail 下 head 提前退出会让 find 报 Broken pipe)
  sha256sum "$zip_name" boot.img boot.tar >SHA256SUMS 2>/dev/null
  echo "--- 产物清单 ---"
  ls -la "$zip_name" boot.img boot.tar NOTICE.txt SHA256SUMS
  echo "--- 模块清单 (前 20) ---"
  find "$work/modules" -name '*.ko' | head -20
  echo "--- 模块总数 ---"
  echo "$ko_count"
)
