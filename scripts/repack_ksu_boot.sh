#!/usr/bin/env bash
# repack_ksu_boot.sh — 用原厂 boot 模板 + 新 Image 打包, 严格保留 ramdisk
# 修复历史 bug: 之前 Kokuban 打包 RAMDISK_SZ=0 (ramdisk 丢失 → 刷入必死)
set -euo pipefail

: "${KERNEL_IMAGE:?KERNEL_IMAGE is required}"
: "${STOCK_BOOT:?STOCK_BOOT is required}"
: "${MAGISKBOOT:?MAGISKBOOT is required}"
: "${OUTPUT_DIR:?OUTPUT_DIR is required}"
: "${TARGET_KERNELRELEASE:?TARGET_KERNELRELEASE is required}"
: "${EXPECTED_STOCK_BOOT_SHA256:?EXPECTED_STOCK_BOOT_SHA256 is required}"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

sha256_of() {
  sha256sum "$1" | awk '{print $1}'
}

echo "=== 1. 校验输入 ==="
test -s "$KERNEL_IMAGE" || fail "新内核 Image 缺失: $KERNEL_IMAGE"
test -x "$MAGISKBOOT" || fail "magiskboot 不可执行"
test -s "$STOCK_BOOT" || fail "原厂 boot 模板缺失"

[ "$(sha256_of "$STOCK_BOOT")" = "$EXPECTED_STOCK_BOOT_SHA256" ] || \
  fail "原厂 boot 模板 SHA256 不匹配 (下载可能被篡改)"

# 新 Image 必须包含目标版本串
grep -aFq "Linux version $TARGET_KERNELRELEASE " "$KERNEL_IMAGE" || \
  fail "新 Image 不含版本串 $TARGET_KERNELRELEASE"

work_root=$(mktemp -d "${RUNNER_TEMP:-/tmp}/ksu-repack.XXXXXX")
trap 'rm -rf "$work_root"' EXIT
output_dir=$(realpath -m "$OUTPUT_DIR")
mkdir -p "$output_dir" "$work_root/template"

echo "=== 2. 解包原厂模板 (必须拿到 kernel + ramdisk.cpio + header) ==="
cp "$STOCK_BOOT" "$work_root/template/boot.img"
(
  cd "$work_root/template"
  "$MAGISKBOOT" unpack -h boot.img
)
test -s "$work_root/template/kernel" || fail "模板 kernel 未解出"
test -s "$work_root/template/ramdisk.cpio" || fail "模板 ramdisk 未解出 (原厂 boot 必须有 ramdisk)"
test -s "$work_root/template/header" || fail "模板 header 未解出"

STOCK_RAMDISK_SHA=$(sha256_of "$work_root/template/ramdisk.cpio")
echo "模板 ramdisk.cpio sha256: $STOCK_RAMDISK_SHA"
echo "模板 ramdisk 大小: $(stat -c %s "$work_root/template/ramdisk.cpio") bytes"

echo "=== 3. 替换内核 (只换 kernel, 不碰 ramdisk/header/dtb) ==="
cp "$KERNEL_IMAGE" "$work_root/template/kernel"
NEW_KERNEL_SHA=$(sha256_of "$work_root/template/kernel")
echo "新内核 sha256: $NEW_KERNEL_SHA"

echo "=== 4. 回包 ==="
(
  cd "$work_root/template"
  "$MAGISKBOOT" repack boot.img "$output_dir/boot.img"
)

echo "=== 5. 严格验证回包 (防止再次丢 ramdisk!) ==="
test -s "$output_dir/boot.img" || fail "回包产物缺失"
mkdir -p "$work_root/verify"
(
  cd "$work_root/verify"
  "$MAGISKBOOT" unpack -h "$output_dir/boot.img" 2>&1 | tee /tmp/ksu_unpack_check.txt
)
# 关键检查 1: RAMDISK_SZ > 0
RAMDISK_SZ=$(grep -oP 'RAMDISK_SZ\s+\[\K[0-9]+' /tmp/ksu_unpack_check.txt || true)
[ -n "$RAMDISK_SZ" ] && [ "$RAMDISK_SZ" -gt 0 ] || \
  fail "回包 RAMDISK_SZ=$RAMDISK_SZ — ramdisk 丢失! 刷入必死。"
echo "✅ RAMDISK_SZ=$RAMDISK_SZ (必须 > 0)"

# 关键检查 2: header 与模板一致 (cmdline/os_version 等原样保留)
cmp --silent "$work_root/template/header" "$work_root/verify/header" || \
  fail "回包 header 与模板不一致!"
echo "✅ header 与模板一致"

# 关键检查 3: ramdisk 内容与模板完全一致
[ "$(sha256_of "$work_root/verify/ramdisk.cpio")" = "$STOCK_RAMDISK_SHA" ] || \
  fail "回包 ramdisk 与模板不一致!"
echo "✅ ramdisk 与模板 sha256 一致: $STOCK_RAMDISK_SHA"

# 关键检查 4: kernel 就是我们的新 Image
[ "$(sha256_of "$work_root/verify/kernel")" = "$NEW_KERNEL_SHA" ] || \
  fail "回包 kernel 不是新 Image!"
echo "✅ kernel 与编译产物一致"

# 关键检查 5: 版本串
grep -aFq "Linux version $TARGET_KERNELRELEASE " "$work_root/verify/kernel" || \
  fail "回包 kernel 版本串缺失"
echo "✅ 版本串 $TARGET_KERNELRELEASE 确认"

echo "=== 6. 打 Odin tar (USTAR, 文件名 boot.img) ==="
staging="$work_root/tar-stage"
mkdir -p "$staging"
cp "$output_dir/boot.img" "$staging/boot.img"
tar --format=ustar --owner=0 --group=0 --numeric-owner \
  -cf "$output_dir/boot.tar" -C "$staging" boot.img
[ "$(tar -tf "$output_dir/boot.tar")" = "boot.img" ] || \
  fail "Odin tar 内容异常"
echo "✅ boot.tar 已生成"

echo "=== 7. 写 NOTICE + SHA256SUMS ==="
cat >"$output_dir/NOTICE.txt" <<EOF
${NOTICE_DESC:-S21 (SM-G9910, o1q) 全内置内核 + KernelSU v1.0.5}
Kernel release: $TARGET_KERNELRELEASE
- 源码: ${SOURCE_DESC:-Samsung G9910ZCUBHYDA OSRC (SM-G9910_CHN_15_Opensource.zip)}
- 路线: ${ROUTE_DESC:-保留模块 + 重编全部 .ko, TWRP 安装}
- ${KSU_DESC:-KernelSU: v1.0.5 + 三星 KNOX 五补丁 (scripts/patch_ksu_samsung.py)}
- boot 模板: ${BOOT_TEMPLATE_DESC:-HZE1 原厂 boot_stock.img} (ramdisk 原样保留, SHA256 已校验)
- 仅替换 kernel 段; dtbo/vendor 分区未动
刷机: Odin AP 槽刷 boot.tar (或 recovery adb 刷 boot.img)
救机: 刷回 ${STOCK_BOOT_DESC:-magisk-boot-G9910ZCUGHZE1 release 的 boot_stock.tar}
EOF

(
  cd "$output_dir"
  sha256sum boot.img boot.tar >SHA256SUMS
  echo "--- 产物清单 ---"
  ls -la boot.img boot.tar NOTICE.txt SHA256SUMS
  echo "--- SHA256SUMS ---"
  cat SHA256SUMS
)
