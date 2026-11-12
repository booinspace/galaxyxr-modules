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
stop-playback)
  [ "$#" -eq 1 ] || exit 2
  [ ! -d "$MODDIR/webroot/recordings" ] || : > "$MODDIR/webroot/recordings/stop-playback"
  echo 'Playback stop requested.'
  ;;
record|play|delete-recording)
  [ "$#" -eq 1 ] || exit 2
  # Android mksh closes extra exec-opened descriptors before launching flock.
  exec 0>"$MODDIR/.mic-test.lock"
  flock -n 0 || { echo 'Could not lock the microphone test. Wait for any other test to finish and retry.' >&2; exit 1; }
  if [ "$1" = play ]; then
    rm -f "$MODDIR/webroot/recordings/stop-playback"
    CLASSPATH="$MODDIR/bin/helper.dex" timeout -k 2 15 /system/bin/app_process /system/bin com.gxr.mic.MicTest play "$MODDIR"
    exit $?
  elif [ "$1" = delete-recording ]; then
    rm -f "$MODDIR/webroot/recordings/mic-test.wav" "$MODDIR/webroot/recordings/mic-test.wav.part"
  else
    [ "$MODE" = 0 ] || { echo 'Turn Virtual Desktop only off to hear boost in this test.' >&2; exit 1; }
    [ ! -f "$MODDIR/disable" ] && [ ! -f "$MODDIR/remove" ] &&
      sh "$MODDIR/control.sh" status | grep -qx RUNNING || { echo 'Enable and start mic boost first.' >&2; exit 1; }
    [ "$(getprop ro.build.fingerprint)" = 'samsung/xrvst2ue/xrvst2:14/UML2.260301.001/I610UES3AZJ2:user/release-keys' ] || exit 1
    (cd "$MODDIR" && sha256sum -c SHA256SUMS) >/dev/null 2>&1 || { echo 'Module integrity check failed.' >&2; exit 1; }
    if CLASSPATH="$MODDIR/bin/helper.dex" timeout -k 2 15 /system/bin/app_process /system/bin com.gxr.mic.MicTest capture "$MODDIR" >&2; then :
    else
      result=$?
      rm -f "$MODDIR/webroot/recordings/mic-test.wav.part"
      echo "Recording failed (exit $result); any previously saved clip remains available." >&2
      exit 1
    fi
  fi
  exec sh "$MODDIR/settings.sh" json
  ;;
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
  recording=false
  if [ -f "$MODDIR/webroot/recordings/mic-test.wav" ] &&
      CLASSPATH="$MODDIR/bin/helper.dex" timeout -k 1 5 /system/bin/app_process /system/bin com.gxr.mic.MicTest validate "$MODDIR" >/dev/null 2>&1; then recording=true; fi
  printf '{"gain":%s,"vdOnly":%s,"running":%s,"recording":%s}\n' "$GAIN_DB" "$vd_only" "$running" "$recording"
  ;;
*) echo 'Usage: settings.sh json|set gain vdOnly|record|play|stop-playback|delete-recording' >&2; exit 2 ;;
esac
