#!/system/bin/sh
set -eu
MODDIR=$(CDPATH= cd -P "${0%/*}" && pwd)
umask 077
[ "$(id -u)" = 0 ] || { echo 'Root required.' >&2; exit 1; }
[ "$#" -gt 0 ] || set -- json
ENABLED=0 HOLD_MS=500
load_settings() {
  [ -f "$MODDIR/quick-settings-gesture.conf" ] || return 0
  seen=' '
  count=0
  while IFS='=' read -r key value || [ -n "$key" ]; do
    case "$seen" in *" $key "*) return 1 ;; esac
    case "$key:$value" in
      ENABLED:0|ENABLED:1) ENABLED=$value ;;
      HOLD_MS:0|HOLD_MS:500) HOLD_MS=$value ;;
      *) return 1 ;;
    esac
    seen="$seen$key "
    count=$((count + 1))
  done < "$MODDIR/quick-settings-gesture.conf"
  [ "$count" -eq 2 ]
}
case "${1:-json}" in
set)
  [ "$#" -eq 3 ] || exit 2
  case "$2:$3" in 0:0|0:500|1:0|1:500) ;; *) echo 'Invalid pinch settings.' >&2; exit 2 ;; esac
  temporary="$MODDIR/.quick-settings.$$.tmp"
  trap 'rm -f "$temporary"' EXIT
  (set -C; printf 'ENABLED=%s\nHOLD_MS=%s\n' "$2" "$3" > "$temporary")
  mv -f "$temporary" "$MODDIR/quick-settings-gesture.conf"
  exec sh "$MODDIR/quick-settings-gesture.sh" json
  ;;
json|wire)
  load_settings || { echo 'Invalid saved pinch settings.' >&2; exit 1; }
  if [ "$1" = wire ]; then printf 'quick-settings %s %s\n' "$ENABLED" "$HOLD_MS"
  else printf '{"enabled":%s,"holdMs":%s}\n' "$ENABLED" "$HOLD_MS"; fi
  ;;
*) echo 'Usage: quick-settings-gesture.sh json|wire|set enabled holdMs' >&2; exit 2 ;;
esac
