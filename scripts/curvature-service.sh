#!/system/bin/sh
set -eu
MODDIR=$(CDPATH= cd -P "${0%/*}" && pwd)
COORD=/dev/ksu-restart-stage
allowed() { [ ! -f "$MODDIR/disable" ] && [ ! -f "$MODDIR/remove" ]; }
allowed || exit 0
case "${1:-}" in
  '')
    generation=${KSU_RESTART_GENERATION:-$(cat "$COORD/generation" 2>/dev/null || true)}
    nohup sh "$MODDIR/service.sh" worker "$generation" >> "$MODDIR/service.log" 2>&1 </dev/null &
    exit 0
    ;;
  worker) generation=${2:-} ;;
  *) exit 2 ;;
esac
if [ -n "$generation" ]; then
  printf '%s\n' "$generation" | grep -Eq '^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$' || exit 1
fi
echo 'AUTO_START - enabled module startup requested.'
count=0
while :; do
  allowed || exit 0
  if [ -n "$generation" ]; then
    [ "$generation" = "$(cat "$COORD/generation" 2>/dev/null || true)" ] || exit 0
    [ ! -f "$COORD/error" ] || exit 0
    if [ ! -f "$COORD/busy" ] && [ -f "$COORD/ready" ]; then break; fi
  else
    # A new restart owns startup if it begins before this cold-boot dispatch.
    [ ! -f "$COORD/busy" ] || exit 0
    break
  fi
  [ "$count" -lt 120 ] || { echo 'AUTO_START_DEFERRED - restart readiness timed out.'; exit 1; }
  sleep 1
  count=$((count + 1))
done
allowed || exit 0
echo 'AUTO_START - restart gate clear; starting the guarded controller.'
export GXR_WINDOW_AUTOSTART=1
exec sh "$MODDIR/control.sh" run
