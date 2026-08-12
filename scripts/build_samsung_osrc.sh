#!/usr/bin/env bash
set -euo pipefail

: "${VARIANT:?VARIANT is required}"
: "${FIRMWARE:?FIRMWARE is required}"
: "${DEFCONFIG:?DEFCONFIG is required}"
: "${LOCALVERSION:?LOCALVERSION is required}"

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

scripts/config --file out/.config --set-str LOCALVERSION "$LOCALVERSION"
scripts/config --file out/.config --disable LOCALVERSION_AUTO

if [ "$VARIANT" = droidspaces ]; then
  scripts/kconfig/merge_config.sh -m -O out \
    out/.config "$workspace/droidspaces-gki.config"
fi

make "${make_args[@]}" olddefconfig

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
  echo "KernelSU must not be present in the audit build" >&2
  exit 1
fi

if ! make "${make_args[@]}" >"$build_log" 2>&1; then
  tail -n 180 "$build_log" >&2
  exit 1
fi

tail -n 40 "$build_log"

test -s "$image"
test -s out/Module.symvers

mkdir -p "$artifact_dir"
cp "$image" "$artifact_dir/Image"
cp out/.config "$artifact_dir/build.config"
cp out/Module.symvers "$artifact_dir/Module.symvers"
scripts/extract-ikconfig "$image" >"$artifact_dir/Image.config"
cmp --silent out/.config "$artifact_dir/Image.config" || {
  echo "Embedded Image configuration differs from out/.config" >&2
  exit 1
}

make "${make_args[@]}" --silent kernelrelease >"$artifact_dir/kernelrelease.txt"
strings "$image" >"$artifact_dir/Image.strings"
grep -m1 '^Linux version ' "$artifact_dir/Image.strings" \
  >"$artifact_dir/compiler.txt"
rm "$artifact_dir/Image.strings"

grep -Fq "$FIRMWARE" "$artifact_dir/kernelrelease.txt" || {
  echo "Kernel release does not identify registered firmware $FIRMWARE" >&2
  exit 1
}
grep -Fq 'LLD 11.0.2' "$artifact_dir/compiler.txt" || {
  echo "Kernel was not linked with the registered LLD 11.0.2 toolchain" >&2
  cat "$artifact_dir/compiler.txt" >&2
  exit 1
}

cat >"$artifact_dir/NOTICE.txt" <<EOF
Audit artifact only. This is not a boot image or a flashable package.
Registered source firmware: $FIRMWARE
Variant: $VARIANT
Do not use this Image on a different firmware build.
EOF

(
  cd "$artifact_dir"
  sha256sum Image Image.config Module.symvers kernelrelease.txt compiler.txt \
    >SHA256SUMS
)
