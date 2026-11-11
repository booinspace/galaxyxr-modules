#!/system/bin/sh
# Start the second SystemUI injector only after borderless has settled.
MODDIR=${0%/*}
[ ! -f "$MODDIR/disable" ] && [ ! -f "$MODDIR/remove" ] || exit 0
(
  borderless=/data/adb/modules/gxr_borderless_azj2
  if [ -d "$borderless" ] && [ ! -f "$borderless/disable" ]; then
    count=0
    until grep -q '^RUNNING ' /dev/gxr-borderless-azj2/status 2>/dev/null; do
      [ ! -f "$MODDIR/disable" ] && [ ! -f "$MODDIR/remove" ] || exit 0
      if [ -f "$borderless/disable" ] || [ "$count" -ge 45 ]; then
        : > "$MODDIR/disable"
        echo 'Borderless did not reach a stable running state; curvature was not attached' > "$MODDIR/failure"
        exit 1
      fi
      count=$((count + 1))
      sleep 1
    done
    sleep 10
    if [ -f "$borderless/disable" ] || ! grep -q '^RUNNING ' /dev/gxr-borderless-azj2/status 2>/dev/null; then
      : > "$MODDIR/disable"
      echo 'Borderless stopped during startup; curvature was not attached' > "$MODDIR/failure"
      exit 1
    fi
  fi
  [ ! -f "$MODDIR/disable" ] && [ ! -f "$MODDIR/remove" ] || exit 0
  sh "$MODDIR/control.sh" run >> "$MODDIR/service.log" 2>&1
) &
