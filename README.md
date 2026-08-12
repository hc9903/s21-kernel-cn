# Samsung S21 CN kernel audit builds

This repository builds Samsung's published SM-G9910 (`o1q`) kernel source in
GitHub Actions and checks whether the DroidSpaces configuration preserves the
exported module ABI.

## Current limitation

The only registered Samsung source package currently available here is for
`G9910ZCUBHYDA`. The current test phone runs `G9910ZCUGHZE1`. These are not the
same firmware source revision.

Changing `CONFIG_LOCALVERSION` does not make HYDA source compatible with HZE1.
The workflow therefore accepts only explicitly registered source revisions and
does not provide an HZE1 option until the matching Samsung OSRC package is
available.

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
