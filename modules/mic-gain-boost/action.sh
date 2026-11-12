#!/system/bin/sh
MODDIR=${0%/*}
sh "$MODDIR/control.sh" "${1:-action}" || exit $?
if [ "$#" -eq 0 ] || [ "$1" = action ]; then
  am start --user 0 -a android.intent.action.VIEW \
    -n me.weishu.kernelsu/.ui.webui.WebUIActivity \
    -d 'ksu://webui?id=gxr_mic_gain_azj2' >/dev/null ||
    echo 'Open the module WebUI in KernelSU GXR to adjust mic gain.'
fi
