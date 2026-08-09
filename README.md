# S21 国行 (SM-G9910 / o1q) Droidspaces 内核编译

用 GitHub Actions 把三星官方开源内核 (Linux 5.4.274, One UI 7 / Android 15) 编译成支持
[Droidspaces](https://github.com/ravindu644/Droidspaces-OSS) 的版本, 产物为刷机用的 `Image`。

参考:
- Droidspaces 官方内核配置文档: https://github.com/ravindu644/Droidspaces-OSS/blob/main/Documentation/Kernel-Configuration.md
- 内核编译教程: https://github.com/ravindu644/Android-Kernel-Tutorials
- 本仓库 Release 里的 `SM-G9910_CHN_15_Opensource.zip` 是 opensource.samsung.com 的原包

## 使用方法

1. 点仓库右上角 **Actions** → 左侧 **国行 S21 (o1q / SM-G9910) 5.4 Droidspaces 内核编译** → **Run workflow**。
2. 三个输入:
   - `source_url`: 默认即可 (你自己 Release 里存的三星原包)。
   - `defconfig_name`: 默认 `vendor/o1q_chn_openx_defconfig`, 别动。
   - `localversion`:**必须先看下面的「版本号」一节再填!**
3. 跑完后在本次运行页面下载 **o1q-droidspaces-kernel** 工件, 里面的 `Image` 就是新内核。

## ⚠️ 版本号 (localversion) —— 最重要的一步

S21 的 `/vendor` 里有三星预编译的内核模块 (WiFi BCM4375、蓝牙、NFC 等, 共 66 个)。
内核与模块靠 **vermagic (完整内核版本号) 匹配**。三星原厂内核版本号带后缀, 例如:
`5.4.274-qgki-30957850-abG998U1UESGHYF1`

如果编译出来的版本号对不上, 模块拒绝加载 → **WiFi/蓝牙/NFC 全挂**。

做法 (手机已 root):
```
# Termux 里
uname -r
```
把输出中 `5.4.274` **之后**的部分完整复制, 填进 workflow 的 `localversion` 输入。

本机当前固件实测输出:
```
5.4.274-qgki-2370012-abG9910ZCUBHYDA
```
所以 workflow 默认值已经填好:
```
-qgki-2370012-abG9910ZCUBHYDA
```
⚠️ 以后手机升级系统 (版本号后缀变化) 后重新编译, 记得先 `uname -r` 再改这个输入。
(必须带开头的 `-`。)

## 刷机 (和 S20+ 那套完全一样)

1. **备份**: 已 root 的 Termux 里
   ```
   su -c "dd if=/dev/block/by-name/boot of=/sdcard/boot.img"
   ```
2. 解包: 把 `boot.img` 和 `magiskboot` 放一起, `magiskboot unpack boot.img`。
3. 替换: 用编译出的 `Image` 覆盖解包目录里的 `kernel` 文件。
4. 回包: `magiskboot repack boot.img` → 得到 `new-boot.img`, 改名为 `boot.img`。
5. 打包: `tar -cvf Custom-Kernel.tar boot.img`。
6. 手机进 Download 模式, Odin 的 **AP** 栏刷入 `Custom-Kernel.tar`。

要点:
- **只换 kernel, 其它一律不动** (包括 dtb/ramdisk)。root 是 Magisk 打在 ramdisk 里的, 自动保留。
- 不用刷 dtbo、不用动 /vendor。dtb 由原 boot.img 自带, 与同版本源码匹配。
- 源码包必须和手机当前系统对应 (本包是 Android 15 / One UI 7)。
- 刷完进 Droidspaces App → 设置 → 需求 → 检查需求, 或 `su -c droidspaces check` 验证。

## 为什么 5.4 不需要 Droidspaces 文档里 GKI 那套 kABI 补丁

Droidspaces 文档把 5.4+ 归到 "GKI (Modern Kernels)" 只是按版本号粗略分类。
kABI 补丁是给**真 GKI 设备**用的 (Android 12 起强制, 有独立 vendor_boot、boot.img 里没有
ramdisk、vendor 模块按锁定 ABI 预编译)。S21 是 2021 年初发布, **不是 GKI 设备**:
boot.img 自带 ramdisk、无 vendor_boot, 所有模块都来自这份同一源码。
所以按非 GKI 路线处理: 把配置片段追加进 defconfig 即可, 无需 kABI 补丁
(ravindu644 自己的三星 5.15 内核 A16 也是这么干的, 同样稳定)。

## 常见问题

- **编译失败怎么办**: 打开失败的步骤看日志。工具链/源码下载失败重跑一次即可 (下载源偶发超时)。
- **想加 KernelSU?** 这是另一条路 (需要额外 patch + 可能关 RKP), 本 workflow 先保持纯 Magisk + Droidspaces。
- **手机开不了机**: 别慌, Odin AP 刷回第 1 步备份的原 `boot.img` (或打包成 tar) 即可。
- **`.github/workflows/main.yml` 那个 1 字节的空文件**: 删掉, 它会让每次 push 都报失败。
