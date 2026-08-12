# Samsung S21 CN kernel audit builds

This repository builds Samsung's published SM-G9910 (`o1q`) kernel source in
GitHub Actions and checks whether the DroidSpaces configuration preserves the
exported module ABI.

## Published source boundary

Samsung currently publishes these two Android 15 OSRC packages for SM-G9910:

- `G9910ZCUBHYDA`: `SM-G9910_CHN_15_Opensource.zip`
- `G9910ZHUBHYD9`: `SM-G9910_HKTW_15_Opensource.zip`

There is no published `G9910ZCUGHZE1` OSRC package. The current test phone runs
`G9910ZCUGHZE1`, while this repository's registered CHN source is HYDA.

Changing `CONFIG_LOCALVERSION` does not make HYDA source compatible with HZE1.
The normal audit workflow therefore accepts only explicitly registered source
revisions and does not call HYDA source an HZE1 source release.

## GitHub Actions

Run **Samsung OSRC audit build** and choose one mode:

- `baseline`: rebuild the unmodified Samsung configuration with the registered
  clang/LLD toolchain.
- `abi-pair`: build both the Samsung baseline and the kABI-patched DroidSpaces
  variant, then compare every baseline `Module.symvers` symbol CRC.

The workflow uploads audit artifacts only:

- `Image`
- embedded and build-time kernel configurations
- `Module.symvers`
- compiler/linker identity
- SHA-256 checksums
- ABI comparison report for `abi-pair`

It intentionally does not create a `boot.img`, AnyKernel/TWRP package, `dtbo`
package, or `/vendor/lib/modules` installer. A successful build is not approval
to flash it on a different firmware revision.

## HZE1 compatibility workflow

**HZE1 DroidSpaces compatibility build** is a separate, fixed-input workflow.
It is explicitly labelled:

> HYDA published source derived, HZE1 stock ABI verified

The workflow builds a baseline and DroidSpaces pair with the exact HZE1 kernel
release and with `CONFIG_RELR` disabled. Packaging is gated on all of these
checks:

- the baseline has exactly 13,661 vmlinux exports and the independently derived
  HZE1 stock CRC fingerprint;
- DroidSpaces retains every baseline CRC and adds exactly the 12 reviewed
  namespace exports in `sources/hze1-droidspaces-added-symbols.txt`;
- the stock and Magisk 30.7 HZE1 boot inputs match pinned SHA-256 values;
- repacked images preserve the selected ramdisk and boot header byte-for-byte
  and contain the exact HZE1 kernel release.

Only the kernel component is replaced. The workflow does not replace `dtbo` or
vendor modules. Its output is an ABI-verified compatibility candidate, not an
official HZE1-source Samsung build and not proof of successful device boot.

## Withdrawn HZE1 flash experiment / 已撤回的 HZE1 刷机实验

The `hze1-droidspaces-abi-v1` release has been withdrawn after a physical
`SM-G9910` running `G9910ZCUGHZE1` failed to boot its Magisk 30.7 image. After
the bootloader warning was acknowledged, the phone rebooted again in about
five to six seconds. It was recovered by flashing the complete matching stock
firmware, then rooted again by patching that firmware's AP file with Magisk.

Do not flash any `.img` or `.tar` from that release. The stock-ramdisk and
Magisk variants contain the same unbootable test kernel; changing the ramdisk
does not avoid the failure. The release is retained as a private draft only to
preserve its artifacts and audit evidence for diagnosis.

The failed experiment proves that matching the HZE1 kernel release string and
exported `vmlinux` symbol CRC fingerprint is not sufficient to establish boot
compatibility between the published HYDA source and the HZE1 firmware. Future
device tests must first establish that an unmodified-source baseline kernel can
boot, then introduce one independently attributable change at a time.

## DroidSpaces configuration

The DroidSpaces variant uses only [droidspaces-gki.config](droidspaces-gki.config)
and applies the upstream SYSVIPC and POSIX_MQUEUE kABI layout fixes through
[`scripts/apply_kabi_fix.py`](scripts/apply_kabi_fix.py).

Legacy full configuration fragments remain for reference, but the previous
Kokuban/Lucas workflows have been removed and those fragments are not part of
the active build path.

## Adding a firmware source

Add an entry to [`sources/sm-g9910-osrc.json`](sources/sm-g9910-osrc.json) only
after obtaining the corresponding Samsung OSRC archive. Record its exact
SHA-256, defconfig and kernel localversion. Do not reuse another firmware's
archive or rename its version string.
