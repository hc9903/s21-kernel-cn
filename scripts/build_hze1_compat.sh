#!/usr/bin/env bash
set -euo pipefail

: "${VARIANT:?VARIANT is required}"
: "${DEFCONFIG:?DEFCONFIG is required}"
: "${TARGET_FIRMWARE:?TARGET_FIRMWARE is required}"
: "${SOURCE_FIRMWARE:?SOURCE_FIRMWARE is required}"
: "${TARGET_LOCALVERSION:?TARGET_LOCALVERSION is required}"
: "${EXPECTED_KERNELRELEASE:?EXPECTED_KERNELRELEASE is required}"
: "${PROVENANCE_NOTICE:?PROVENANCE_NOTICE is required}"

case "$VARIANT" in
  baseline|droidspaces) ;;
  *)
    echo "Unsupported build variant: $VARIANT" >&2
    exit 2
    ;;
esac

workspace=${GITHUB_WORKSPACE:-$(pwd)}
kernel_dir="$workspace/kernel"
clang_dir="$workspace/toolchains/clang"
gcc_dir="$workspace/toolchains/gcc64"
artifact_dir="$workspace/artifacts/$VARIANT"
build_log="$workspace/build-$VARIANT.log"
image="$kernel_dir/out/arch/arm64/boot/Image"

test -d "$kernel_dir"
test -x "$clang_dir/bin/clang"
test -x "$clang_dir/bin/ld.lld"
test -x "$gcc_dir/bin/aarch64-linux-android-gcc"
test -f "$kernel_dir/arch/arm64/configs/$DEFCONFIG"
test -f "$workspace/hze1-compat.config"

export PATH="$clang_dir/bin:$gcc_dir/bin:$PATH"
export ARCH=arm64

make_args=(
  -j"$(nproc)"
  O=out
  ARCH=arm64
  LLVM=1
  LLVM_IAS=1
  CROSS_COMPILE="$gcc_dir/bin/aarch64-linux-android-"
  CLANG_TRIPLE=aarch64-linux-gnu-
  DTC_EXT="$kernel_dir/tools/dtc"
  CONFIG_BUILD_ARM64_DT_OVERLAY=y
  CONFIG_SECTION_MISMATCH_WARN_ONLY=y
  DISABLE_WRAPPER=1
)

cd "$kernel_dir"

if [ "$VARIANT" = droidspaces ]; then
  python3 "$workspace/scripts/apply_kabi_fix.py"
fi

make "${make_args[@]}" "$DEFCONFIG"
scripts/config --file out/.config --set-str LOCALVERSION "$TARGET_LOCALVERSION"
scripts/config --file out/.config --disable LOCALVERSION_AUTO

scripts/kconfig/merge_config.sh -m -O out \
  out/.config "$workspace/hze1-compat.config"

if [ "$VARIANT" = droidspaces ]; then
  scripts/kconfig/merge_config.sh -m -O out \
    out/.config "$workspace/droidspaces-gki.config"
fi

make "${make_args[@]}" olddefconfig

grep -qx "CONFIG_LOCALVERSION=\"$TARGET_LOCALVERSION\"" out/.config || {
  echo "Target localversion was not preserved" >&2
  exit 1
}
grep -qx '# CONFIG_LOCALVERSION_AUTO is not set' out/.config || {
  echo "CONFIG_LOCALVERSION_AUTO must be disabled" >&2
  exit 1
}
grep -qx '# CONFIG_RELR is not set' out/.config || {
  echo "CONFIG_RELR must match the HZE1 stock configuration (disabled)" >&2
  exit 1
}

if grep -q '^CONFIG_SEC_AUTO_INPUT=' out/.config; then
  echo "Published HYDA source unexpectedly implements CONFIG_SEC_AUTO_INPUT" >&2
  exit 1
fi

if [ "$VARIANT" = baseline ]; then
  if grep -Eq '^CONFIG_(SYSVIPC|POSIX_MQUEUE|IPC_NS|PID_NS|DEVTMPFS|NETFILTER_XT_MATCH_ADDRTYPE|USER_NS)=y$' out/.config; then
    echo "Baseline unexpectedly enables DroidSpaces-only options" >&2
    exit 1
  fi
else
  for option in \
    SYSVIPC POSIX_MQUEUE IPC_NS PID_NS DEVTMPFS \
    NETFILTER_XT_MATCH_ADDRTYPE USER_NS
  do
    grep -qx "CONFIG_${option}=y" out/.config || {
      echo "Required DroidSpaces option CONFIG_${option}=y is missing" >&2
      exit 1
    }
  done
fi

if grep -qx 'CONFIG_KSU=y' out/.config; then
  echo "KernelSU is outside the HZE1 compatibility build" >&2
  exit 1
fi

if ! make "${make_args[@]}" >"$build_log" 2>&1; then
  tail -n 180 "$build_log" >&2
  exit 1
fi

tail -n 40 "$build_log"
test -s "$image"
test -s out/Module.symvers

# The defconfig target creates include/config/kernel.release before the fixed
# localversion is merged. Read it only after the full build has refreshed all
# generated release files from the final .config.
actual_release=$(make "${make_args[@]}" --silent kernelrelease)
if [ "$actual_release" != "$EXPECTED_KERNELRELEASE" ]; then
  echo "Unexpected kernel release: $actual_release" >&2
  echo "Expected kernel release: $EXPECTED_KERNELRELEASE" >&2
  exit 1
fi

mkdir -p "$artifact_dir"
cp "$image" "$artifact_dir/Image"
cp out/.config "$artifact_dir/build.config"
cp out/Module.symvers "$artifact_dir/Module.symvers"
scripts/extract-ikconfig "$image" >"$artifact_dir/Image.config"
cmp --silent out/.config "$artifact_dir/Image.config" || {
  echo "Embedded Image configuration differs from out/.config" >&2
  exit 1
}

printf '%s\n' "$actual_release" >"$artifact_dir/kernelrelease.txt"
strings "$image" >"$artifact_dir/Image.strings"
grep -m1 '^Linux version ' "$artifact_dir/Image.strings" \
  >"$artifact_dir/compiler.txt"
rm "$artifact_dir/Image.strings"

grep -Fq "Linux version $EXPECTED_KERNELRELEASE " "$artifact_dir/compiler.txt" || {
  echo "Image does not contain the exact HZE1 kernel release" >&2
  cat "$artifact_dir/compiler.txt" >&2
  exit 1
}
grep -Fq 'LLD 11.0.2' "$artifact_dir/compiler.txt" || {
  echo "Kernel was not linked with LLD 11.0.2" >&2
  cat "$artifact_dir/compiler.txt" >&2
  exit 1
}

cat >"$artifact_dir/NOTICE.txt" <<EOF
$PROVENANCE_NOTICE
Target firmware: $TARGET_FIRMWARE
Published Samsung source firmware: $SOURCE_FIRMWARE
Variant: $VARIANT
CONFIG_RELR is disabled to match the HZE1 stock configuration.
CONFIG_SEC_AUTO_INPUT is present in HZE1 stock but unavailable in the published HYDA tree.
This build does not replace dtbo or vendor modules.
EOF

(
  cd "$artifact_dir"
  sha256sum Image Image.config Module.symvers kernelrelease.txt compiler.txt \
    >SHA256SUMS
)
