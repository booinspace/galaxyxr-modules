#!/system/bin/sh
set -eu
MODDIR=$(CDPATH='' cd -P "${0%/*}" && pwd)
umask 077
[ "$(id -u)" = 0 ] || { echo 'Root required.' >&2; exit 1; }
MODE=1 GAIN_DB=15
config="$MODDIR/config.conf"
[ -f "$config" ] || config="$MODDIR/config.default.conf"
seen=' '
while IFS='=' read -r key value || [ -n "$key" ]; do
  case "$key" in ''|'#'*) continue ;; MODE|GAIN_DB) ;; *) echo 'Invalid mic settings.' >&2; exit 1 ;; esac
  case "$seen" in *" $key "*) echo 'Duplicate mic setting.' >&2; exit 1 ;; esac
  seen="$seen$key "
  case "$key:$value" in
    MODE:0|MODE:1|MODE:2) MODE=$value ;;
    GAIN_DB:[0-9]|GAIN_DB:[1-3][0-9]|GAIN_DB:40) GAIN_DB=$value ;;
    *) echo 'Invalid mic setting value.' >&2; exit 1 ;;
  esac
done < "$config"
case "${1:-json}" in
set)
  [ "$#" -eq 3 ] || exit 2
  case "$2" in [0-9]|[1-3][0-9]|40) ;; *) echo 'Gain must be 0–40.' >&2; exit 2 ;; esac
  case "$3" in 0|1) ;; *) echo 'VD-only must be 0 or 1.' >&2; exit 2 ;; esac
  next_mode=$3
  if [ "$3" = 1 ] && [ "$MODE" = 2 ]; then next_mode=2; fi
  temporary="$MODDIR/.config.$$.tmp"
  trap 'rm -f "$temporary"' EXIT
  (set -C; printf 'MODE=%s\nGAIN_DB=%s\n' "$next_mode" "$2" > "$temporary")
  mv -f "$temporary" "$MODDIR/config.conf"
  exec sh "$MODDIR/settings.sh" json
  ;;
json)
  vd_only=1
  [ "$MODE" != 0 ] || vd_only=0
  runtime=$(sh "$MODDIR/control.sh" status)
  if printf '%s\n' "$runtime" | grep -qx RUNNING; then running=true; else running=false; fi
  printf '{"gain":%s,"vdOnly":%s,"running":%s}\n' "$GAIN_DB" "$vd_only" "$running"
  ;;
*) echo 'Usage: settings.sh json|set gain vdOnly' >&2; exit 2 ;;
esac
