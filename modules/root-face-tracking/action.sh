#!/system/bin/sh
MODDIR=${0%/*}
if [ "$#" -gt 0 ]; then exec sh "$MODDIR/control.sh" "$@"; fi
sh "$MODDIR/control.sh" status
am start --user 0 -a android.intent.action.VIEW \
  -n me.weishu.kernelsu/.ui.webui.WebUIActivity \
  -d 'ksu://webui?id=gxr_root_ft_azj2' >/dev/null || echo 'Open this module WebUI in KernelSU GXR.'
