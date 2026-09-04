# Samsung S21 (SM-G9910 / o1q) 港版 Droidspaces 内核

为三星港版 S21 (TGY / `o1q_chn_hkx_defconfig`) 编译 Droidspaces 完全版内核（+UFW/Fail2ban），自动产出可刷机 release。

## Release 速览
| Release | 用途 |
|---|---|
| `droidspaces-flash-*` | 最终刷机包: `boot.img/tar` + `vendor_boot_droidspaces_fix.img` + 刷机指南 |
| `twrp-correct-kernel-*` | 港版 TWRP + `vbmeta_disabled_R.tar`(关 AVB) |
| `1.0` | 编译源文件(港版源码 + 原厂 boot/vendor_boot) |
| `backup-current` | 实机可开机的 boot/vendor_boot 备份(对比基准) |

## 刷机(实测通过)
```
1. Odin 刷港版五件套 G9910ZHSGHZB1
2. Download: AP=twrp tar, USERDATA=vbmeta_disabled_R.tar
3. TWRP 终端跑两遍 multidisabler + Format Data
4. TWRP 终端 dd 刷 vendor_boot_droidspaces_fix.img → vendor_boot 分区
5. TWRP 终端 dd 刷 boot.img → boot 分区 → reboot
6. Magisk App 修补 → root
```

## 核心机制
- **港版验证**: 版本串 `5.4.274-qgki-30957850-abG9910ZHSGHZB1` + `CONFIG_MACH_O1Q_CHN_HKX=y`(workflow 强制)
- **vendor_boot 修复**: Droidspaces 内置 pinctrl, 但原厂 vendor_boot 的 `modules.load` 仍加载 `pinctrl-msm.ko` → `duplicate symbol` → init panic bootloop。`scripts/fix_vendor_boot.sh` 移除已内置 pinctrl 模块, 产物与实机可开机版本逐字节一致
- 工具链: Android clang r383902b1 + LLVM + LTO/CFI, defconfig 末尾追加 Droidspaces 配置

## Workflows
- `build_droidspaces_flash.yml`: 主产线(港版完全版 Droidspaces 刷机包, 无参数)
- `build_recovery_correct_kernel.yml`: 构建港版 TWRP