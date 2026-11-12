#!/system/bin/sh
set -u
MODDIR=${0%/*}
BIN="$MODDIR/bin/gxr-fb10-gate"
case "${1:-status}" in
 off) sh "$MODDIR/auto.sh" disable || exit $?; exec sh "$MODDIR/action.sh" status ;;
 preflight)
  "$BIN" --build-payload || exit $?
  chown 0:0 "$MODDIR/payload/libvulkan_compositor.so" && chmod 0444 "$MODDIR/payload/libvulkan_compositor.so" &&
    chcon u:object_r:system_lib_file:s0 "$MODDIR/payload/libvulkan_compositor.so" || exit 1
  exec "$BIN" --preflight
  ;;
 status|report)
  sh "$MODDIR/auto.sh" status || exit $?
  selector=$(getprop cpm.10bit_framebuffers)
  case "$selector" in ''|false|0) baseline=1 ;; *) baseline=0 ;; esac
  if [ "$baseline" = 1 ] && { [ ! -d /dev/gxr-framebuffer10 ] || [ "$(cat /dev/gxr-framebuffer10/clean-completion 2>/dev/null)" = verified ]; } &&
      [ ! -d "$MODDIR/session-lease" ] && [ ! -f /dev/ksu-restart-stage/busy ] &&
      [ "$(sha256sum /system/lib64/libvulkan_compositor.so | cut -d' ' -f1)" = bd51da246ce12452b0069f3fc35a24389b7705c33819e37ab1916c5a6b3e8cd7 ]; then
    echo 'GXR_UPDATE_STATE=STOCK'
  fi
  echo 'Enable and use one GXR Soft restart to apply. Uncheck and Soft restart to remove.'
  echo 'Action does not start or stop Android independently.'
  ;;
 *) echo 'Usage: action.sh status|off|preflight'; exit 2 ;;
esac
