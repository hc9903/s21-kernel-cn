#!/sbin/sh
#
# A15-aware Samsung services disabler (based on Ian Macdonald v3.1, A15-adapted)
# 修复: 原 v3.1 只处理 fileencryption=, 不处理 A15 FBE v2 的
#       inlinecrypt / keydirectory(metadata_encryption) / length / avb
#
# 刷入后必须在 TWRP 里 Format Data 再开机!

echo " "
echo "Multi-disabler (A15 适配版) for Samsung"
echo "处理: FBE v2 / metadata encryption / inlinecrypt / avb(dm-verity)"
echo " "

echo " - Mounting /vendor..."
mount /vendor 2>/dev/null
mount -o remount,rw /vendor 2>/dev/null
if ! mount | grep /vendor >/dev/null; then
  echo " -   Mount failed. Aborting..."
  exit 3
fi

echo " - Disabling FBE v2 / metadata encryption / dm-verity..."
for i in /vendor/etc/fstab*; do
  if [ -f "$i" ]; then
    echo " -   Processing: $i"
    # 删除加密 flags: fileencryption=<任意值>, inlinecrypt, keydirectory=<任意值>, length=-N, metadata_encryption=<任意值>/裸词
    sed -i 's/,fileencryption=[^,]*//g; s/,inlinecrypt//g; s/,keydirectory=[^,]*//g; s/,length=-[0-9]*//g; s/,metadata_encryption=[^,]*//g; s/,metadata_encryption//g' "$i"
    # 删除 dm-verity/avb flags
    sed -i 's/,avb_keys=[^,]*//g; s/,avb=[^,]*//g; s/,avb//g' "$i"
  fi
done

echo " - Disabling restoration of stock recovery..."
for i in /system /system_root /vendor; do
  if [ -f "$i/recovery-from-boot.p" ]; then
    mv "$i/recovery-from-boot.p" "$i/recovery-from-boot.p~"
    echo " -   Disabled: $i/recovery-from-boot.p"
  fi
done

echo " - Verifying..."
left=$(grep -lE 'fileencryption|inlinecrypt|keydirectory' /vendor/etc/fstab* 2>/dev/null)
if [ -z "$left" ]; then
  echo " -   [OK] 加密 flags 已全部清除"
else
  echo " -   [WARN] 仍有加密 flags 在: $left"
fi

echo " - Unmounting /vendor..."
umount /vendor 2>/dev/null
echo " "
echo " - Finished."
echo " - 下一步: TWRP 主界面 -> Wipe -> Format Data -> 输 yes -> Reboot"
echo " "
exit 0
