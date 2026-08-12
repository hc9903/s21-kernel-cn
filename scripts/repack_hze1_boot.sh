#!/usr/bin/env bash
set -euo pipefail

: "${KERNEL_IMAGE:?KERNEL_IMAGE is required}"
: "${STOCK_BOOT:?STOCK_BOOT is required}"
: "${MAGISK_BOOT:?MAGISK_BOOT is required}"
: "${MAGISKBOOT:?MAGISKBOOT is required}"
: "${OUTPUT_DIR:?OUTPUT_DIR is required}"
: "${TARGET_KERNELRELEASE:?TARGET_KERNELRELEASE is required}"
: "${EXPECTED_STOCK_BOOT_SHA256:?EXPECTED_STOCK_BOOT_SHA256 is required}"
: "${EXPECTED_STOCK_BOOT_SIZE:?EXPECTED_STOCK_BOOT_SIZE is required}"
: "${EXPECTED_STOCK_KERNEL_SHA256:?EXPECTED_STOCK_KERNEL_SHA256 is required}"
: "${EXPECTED_STOCK_KERNEL_SIZE:?EXPECTED_STOCK_KERNEL_SIZE is required}"
: "${EXPECTED_STOCK_RAMDISK_SHA256:?EXPECTED_STOCK_RAMDISK_SHA256 is required}"
: "${EXPECTED_MAGISK_BOOT_SHA256:?EXPECTED_MAGISK_BOOT_SHA256 is required}"
: "${EXPECTED_MAGISK_BOOT_SIZE:?EXPECTED_MAGISK_BOOT_SIZE is required}"
: "${EXPECTED_MAGISK_RAMDISK_SHA256:?EXPECTED_MAGISK_RAMDISK_SHA256 is required}"
: "${MAGISK_VERSION:?MAGISK_VERSION is required}"
: "${PROVENANCE_NOTICE:?PROVENANCE_NOTICE is required}"

fail() {
  echo "$*" >&2
  exit 1
}

sha256_of() {
  sha256sum "$1" | awk '{print $1}'
}

check_file() {
  local path=$1
  local expected_sha256=$2
  local expected_size=$3
  local label=$4
  local actual_sha256 actual_size

  test -s "$path" || fail "$label is missing or empty: $path"
  actual_sha256=$(sha256_of "$path")
  actual_size=$(stat -c %s "$path")
  [ "$actual_sha256" = "$expected_sha256" ] || \
    fail "$label SHA-256 mismatch: $actual_sha256"
  [ "$actual_size" = "$expected_size" ] || \
    fail "$label size mismatch: $actual_size"
}

check_cpio_state() {
  local ramdisk=$1
  local expected=$2
  local label=$3
  local status

  set +e
  "$MAGISKBOOT" cpio "$ramdisk" test >/dev/null 2>&1
  status=$?
  set -e
  [ "$status" -eq "$expected" ] || \
    fail "$label ramdisk state is $status, expected $expected"
}

unpack_template() {
  local template=$1
  local directory=$2
  mkdir -p "$directory"
  cp "$template" "$directory/boot.img"
  (
    cd "$directory"
    "$MAGISKBOOT" unpack -h boot.img
  )
  test -s "$directory/kernel" || fail "Template kernel was not unpacked"
  test -s "$directory/ramdisk.cpio" || fail "Template ramdisk was not unpacked"
  test -s "$directory/header" || fail "Template header was not unpacked"
}

verify_repack() {
  local output=$1
  local source_dir=$2
  local verify_dir=$3
  local expected_size=$4
  local expected_cpio_state=$5
  local label=$6

  [ "$(stat -c %s "$output")" = "$expected_size" ] || \
    fail "$label output size does not match its HZE1 template"
  mkdir -p "$verify_dir"
  (
    cd "$verify_dir"
    "$MAGISKBOOT" unpack -h "$output"
  )
  cmp --silent "$source_dir/header" "$verify_dir/header" || \
    fail "$label changed the boot header or cmdline"
  cmp --silent "$source_dir/ramdisk.cpio" "$verify_dir/ramdisk.cpio" || \
    fail "$label changed the selected template ramdisk"
  cmp --silent "$source_dir/kernel" "$verify_dir/kernel" || \
    fail "$label repacked a different kernel"
  check_cpio_state "$verify_dir/ramdisk.cpio" "$expected_cpio_state" "$label"
  grep -aFq "Linux version $TARGET_KERNELRELEASE " "$verify_dir/kernel" || \
    fail "$label kernel does not contain release $TARGET_KERNELRELEASE"
}

make_odin_tar() {
  local image=$1
  local output=$2
  local staging=$3
  mkdir -p "$staging"
  cp "$image" "$staging/boot.img"
  touch -d '@0' "$staging/boot.img"
  tar --format=ustar --owner=0 --group=0 --numeric-owner \
    -cf "$output" -C "$staging" boot.img
  [ "$(tar -tf "$output")" = "boot.img" ] || \
    fail "Unexpected Odin tar contents: $output"
}

check_file \
  "$STOCK_BOOT" "$EXPECTED_STOCK_BOOT_SHA256" "$EXPECTED_STOCK_BOOT_SIZE" \
  "HZE1 stock boot"
check_file \
  "$MAGISK_BOOT" "$EXPECTED_MAGISK_BOOT_SHA256" "$EXPECTED_MAGISK_BOOT_SIZE" \
  "HZE1 Magisk boot"
test -s "$KERNEL_IMAGE" || fail "DroidSpaces Image is missing"
test -x "$MAGISKBOOT" || fail "magiskboot is not executable"
grep -aFq "Linux version $TARGET_KERNELRELEASE " "$KERNEL_IMAGE" || \
  fail "DroidSpaces Image does not contain release $TARGET_KERNELRELEASE"

output_dir=$(realpath -m "$OUTPUT_DIR")
work_root=$(mktemp -d "${RUNNER_TEMP:-/tmp}/hze1-repack.XXXXXX")
trap 'rm -rf "$work_root"' EXIT
mkdir -p "$output_dir"

stock_dir="$work_root/stock"
magisk_dir="$work_root/magisk"
unpack_template "$STOCK_BOOT" "$stock_dir"
unpack_template "$MAGISK_BOOT" "$magisk_dir"

check_file \
  "$stock_dir/kernel" "$EXPECTED_STOCK_KERNEL_SHA256" \
  "$EXPECTED_STOCK_KERNEL_SIZE" "HZE1 stock kernel"
[ "$(sha256_of "$stock_dir/ramdisk.cpio")" = "$EXPECTED_STOCK_RAMDISK_SHA256" ] || \
  fail "HZE1 stock ramdisk SHA-256 mismatch"
[ "$(sha256_of "$magisk_dir/ramdisk.cpio")" = "$EXPECTED_MAGISK_RAMDISK_SHA256" ] || \
  fail "HZE1 Magisk ramdisk SHA-256 mismatch"
check_cpio_state "$stock_dir/ramdisk.cpio" 0 "HZE1 stock"
check_cpio_state "$magisk_dir/ramdisk.cpio" 1 "HZE1 Magisk"
grep -aFq "Linux version $TARGET_KERNELRELEASE " "$stock_dir/kernel" || \
  fail "Stock boot is not from the expected HZE1 kernel release"

cp "$KERNEL_IMAGE" "$stock_dir/kernel"
cp "$KERNEL_IMAGE" "$magisk_dir/kernel"

# Match Magisk v30.7's Samsung kernel patching stage. The HZE1-derived build
# contains the defex and PROCA patterns; the RKP pattern is optional and was
# absent in the audited HYDA build.
if "$MAGISKBOOT" hexpatch "$magisk_dir/kernel" \
  49010054011440B93FA00F71E9000054010840B93FA00F7189000054001840B91FA00F7188010054 \
  A1020054011440B93FA00F7140020054010840B93FA00F71E0010054001840B91FA00F7181010054
then
  echo "Samsung RKP pattern patched"
else
  echo "Samsung RKP pattern not present"
fi
"$MAGISKBOOT" hexpatch "$magisk_dir/kernel" 821B8012 E2FF8F12 || \
  fail "Samsung defex pattern was not found"
"$MAGISKBOOT" hexpatch "$magisk_dir/kernel" \
  70726F63615F636F6E66696700 \
  70726F63615F6D616769736B00 || \
  fail "Samsung PROCA pattern was not found"

stock_output="$output_dir/boot_HZE1_DroidSpaces_stock-ramdisk.img"
magisk_output="$output_dir/boot_HZE1_DroidSpaces_Magisk-${MAGISK_VERSION}.img"

(
  cd "$stock_dir"
  "$MAGISKBOOT" repack boot.img "$stock_output"
)
(
  cd "$magisk_dir"
  "$MAGISKBOOT" repack boot.img "$magisk_output"
)

verify_repack \
  "$stock_output" "$stock_dir" "$work_root/verify-stock" \
  "$EXPECTED_STOCK_BOOT_SIZE" 0 "stock-ramdisk boot"
verify_repack \
  "$magisk_output" "$magisk_dir" "$work_root/verify-magisk" \
  "$EXPECTED_MAGISK_BOOT_SIZE" 1 "Magisk boot"

make_odin_tar \
  "$stock_output" "$output_dir/boot_HZE1_DroidSpaces_stock-ramdisk.tar" \
  "$work_root/tar-stock"
make_odin_tar \
  "$magisk_output" "$output_dir/boot_HZE1_DroidSpaces_Magisk-${MAGISK_VERSION}.tar" \
  "$work_root/tar-magisk"

cat >"$output_dir/NOTICE.txt" <<EOF
$PROVENANCE_NOTICE
Target kernel release: $TARGET_KERNELRELEASE
The stock-ramdisk image preserves the HZE1 stock ramdisk and is not rooted.
The Magisk image preserves the existing HZE1 Magisk $MAGISK_VERSION ramdisk.
Only the kernel component is replaced. No dtbo or vendor modules are included.
These artifacts are CI-built compatibility candidates and still require device testing.
EOF

(
  cd "$output_dir"
  sha256sum \
    boot_HZE1_DroidSpaces_stock-ramdisk.img \
    boot_HZE1_DroidSpaces_stock-ramdisk.tar \
    "boot_HZE1_DroidSpaces_Magisk-${MAGISK_VERSION}.img" \
    "boot_HZE1_DroidSpaces_Magisk-${MAGISK_VERSION}.tar" \
    >SHA256SUMS
)
