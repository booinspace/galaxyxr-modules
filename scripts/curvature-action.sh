#!/system/bin/sh
set -eu
MODDIR=$(CDPATH= cd -P "${0%/*}" && pwd)
STATE=/dev/gxr-window-curvature
case "${1:-action}" in
action|start)
  if [ ! -f "$MODDIR/disable" ] && [ ! -f "$MODDIR/remove" ] &&
      [ ! -f /dev/ksu-restart-stage/busy ] &&
      [ ! -d "$STATE" ] && [ ! -d /dev/gxr-window-curvature-launch ] &&
      ! sh "$MODDIR/restart.sh" needs-restart; then
    # WebUI root inherits the manager's freezer cgroup; KernelSU su leaves that group.
    nohup /system/bin/su -c "exec sh \"$MODDIR/control.sh\" run" >> "$MODDIR/service.log" 2>&1 </dev/null &
    count=0
    while [ "$count" -lt 30 ]; do
      [ ! -f "$MODDIR/disable" ] || break
      if [ -f "$STATE/status" ] && grep -q '^RUNNING' "$STATE/status"; then break; fi
      sleep 1
      count=$((count + 1))
    done
  fi
  sh "$MODDIR/control.sh" status
  sh "$MODDIR/recovery.sh" export
  if [ "$#" -eq 0 ] || [ "$1" = action ]; then
    am start --user 0 -a android.intent.action.VIEW \
      -n me.weishu.kernelsu/.ui.webui.WebUIActivity \
      -d 'ksu://webui?id=gxr_window_curvature' >/dev/null ||
      echo 'Open this module’s WebUI in KernelSU GXR to change feature settings.'
  fi
  ;;
*) exec sh "$MODDIR/control.sh" "$@" ;;
esac
