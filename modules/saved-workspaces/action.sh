#!/system/bin/sh
MODDIR=${0%/*}
if [ "${1:-action}" = action ]; then
  sh "$MODDIR/service.sh"
  sleep 2
  sh "$MODDIR/control.sh" export
else
  sh "$MODDIR/control.sh" "$1"
fi
result=$?
echo 'Saved Workspaces uses the native Recent apps switcher.'
echo 'Requires Window Controls 0.1.70+ running. Close and reopen Recents after startup.'
[ ! -f "$MODDIR/frontend.status" ] || cat "$MODDIR/frontend.status"
[ ! -f /data/adb/modules/gxr_window_curvature/runtime.log ] || grep 'WORKSPACES_' /data/adb/modules/gxr_window_curvature/runtime.log | tail -5
exit "$result"
