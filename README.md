# Samsung S21 (SM-G9910 / o1q / 骁龙888) Droidspaces 内核仓库

为三星港版 S21 (SM-G9910, 港版 TGY / `o1q_chn_hkx_defconfig`) 编译 **Droidspaces** 内核并产出可直接刷机的完整刷机包。

## 当前主线:港版 Droidspaces 完整刷机包

核心 workflow: **`build_droidspaces_flash.yml`** — 一键产出完整刷机资产到 GitHub Release。

### 产物
| 资产 | 说明 |
|---|---|
| `boot.img` / `boot.tar` | Droidspaces 内核 + 原厂 ramdisk(Odin AP 刷) |
| `vendor_boot_droidspaces_fix.img` | 修复版 vendor_boot(移除 pinctrl 模块冲突,开机必需) |
| `FLASH-GUIDE.txt` | 刷机指南 |
| `NOTICE.txt` | 构建说明 |

### 触发
- workflow_dispatch: `ufw_fail2ban`(默认 true, 开 UFW/Fail2ban 增强)、`localversion`(默认港版 `-qgki-30957850-abG9910ZHSGHZB1`)

### 港版内核验证(workflow 内强制)
- 版本串: 必须精确 `5.4.274-qgki-30957850-abG9910ZHSGHZB1`
- 机型宏: `CONFIG_MACH_O1Q_CHN_HKX=y`(港版, 非国行 openx)
- Droidspaces 配置: SYSVIPC / POSIX_MQUEUE / USER_NS / DEVTMPFS
- 安全对齐: KDP / CRYPTO_FIPS 关闭(对齐 F926N)

### 关键:修复 vendor_boot(pinctrl 模块冲突)
Droidspaces 内核把 pinctrl 编译为内置(`=y`), 但 vendor_boot 的 `modules.load` 仍列出原厂 `pinctrl-msm.ko`。
init 加载时 → `duplicate symbol msm_gpio_mpm_wake_get` → 模块拒载 → `Kernel panic: Attempted to kill init!` → bootloop。

修复: 脚本 `scripts/fix_vendor_boot.sh` 修改 vendor_boot 的 `modules.load`/`modules.dep`/`modules.softdep`,
移除已内置的 pinctrl 模块。产物与实机能开机的手机版**逐字节一致**(sha256 相同)。

## 刷机流程(实测通过)

```
1. Odin/heimdall 刷港版五件套 (G9910ZHSGHZB1)
2. Download 模式: USERDATA=vbmeta_disabled_R.tar  (关 AVB), AP=twrp tar
3. TWRP: 跑 multidisabler + Format Data
4. TWRP 终端:
   dd if=/sdcard/vendor_boot_droidspaces_fix.img of=/dev/block/bootdevice/by-name/vendor_boot bs=1M
   dd if=/sdcard/boot.img of=/dev/block/bootdevice/by-name/boot bs=1M
5. reboot → 开机
6. Magisk App 修补 → root
```

## 编译方法(核心 workflow 内部)

```
make vendor/o1q_chn_hkx_defconfig
# clang r383902b1 + LLVM + LTO + CFI
# 追加 Droidspaces 配置(末尾)+ 锁港版版本串
```

工具链: Android clang r383902b1 (android-11.0.0_r48) + binutils-aarch64-linux-gnu, LLVM=1 LLVM_IAS=1, LTO/CFI。

## 源文件(挂在 release 1.0)
- `SM-G9910_HKTW_15_Opensource.zip` (港版源码, sha256 f865dfab...)
- `boot.img_TGY_G9910ZHSGHZB1.lz4` (原厂 boot, sha256 解压后 7b728e11...)
- `vendor_boot_TGY_G9910ZHSGHZB1.img` (原厂 vendor_boot, sha256 d90a49a3...)

## 保留的工具产物
- `backup-current` release: 本机实测能开机的 boot / vendor_boot 备份
- `magisk-boot-TGY-G9910ZHSGHZB1` release: Magisk boot + vbmeta_disabled + multidisabler
- `twrp-correct-kernel-31673131210` release: 当前可用的 TWRP (5.4.274 hze1 o1q)

## 其他 workflow(参考/历史)
- `build_recovery_correct_kernel.yml`: 构建当前 TWRP (twrp-correct-kernel)
- 旧审计/实验 workflow (build_abi_compare, build_hze1_compat, build_samsung_osrc, build_recovery): 保留作参考

## 关键背景(kABI / 模块 ABI)
Droidspaces 需 CONFIG_SYSVIPC / POSIX_MQUEUE。三星开源内核缺省关闭, 需 kABI padding 补丁
保住 task_struct 布局, 使 stock /vendor 模块 CRC 不因开启而改变。该逻辑内置于
`scripts/patch_droidspaces_kr.py`(应用 Droidspaces 补丁)。