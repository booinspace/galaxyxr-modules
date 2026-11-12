#!/system/bin/sh
set -eu
MODDIR=$(CDPATH= cd -P "${0%/*}" && pwd)
STATE=/dev/gxr-window-curvature
case "${1:-action}" in
action)
  if [ ! -f "$MODDIR/disable" ] && [ ! -f "$MODDIR/remove" ] &&
      [ ! -f /dev/ksu-restart-stage/busy ] &&
      [ ! -d "$STATE" ] && [ ! -d /dev/gxr-window-curvature-launch ]; then
    nohup sh "$MODDIR/control.sh" run >> "$MODDIR/service.log" 2>&1 </dev/null &
    count=0
    while [ "$count" -lt 30 ]; do
      [ ! -f "$MODDIR/disable" ] || break
      if [ -f "$STATE/status" ] && grep -q '^RUNNING' "$STATE/status"; then break; fi
      sleep 1
      count=$((count + 1))
    done
  fi
  sh "$MODDIR/control.sh" status
  exec sh "$MODDIR/recovery.sh" export
  ;;
*) exec sh "$MODDIR/control.sh" "$@" ;;
esac
