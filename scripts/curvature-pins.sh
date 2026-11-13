#!/system/bin/sh
set -eu
MODDIR=$(CDPATH= cd -P "$(dirname "$0")" && pwd)
umask 077
[ "$(id -u)" = 0 ] || { echo 'Root required.' >&2; exit 1; }
cli() {
  CLASSPATH="$MODDIR/bin/classes.dex" /system/bin/app_process /system/bin local.gxr.pins.PinCli "$@"
}
package=app.symfonik.music.player
if [ -f "$MODDIR/pin-app.conf" ]; then package=$(cat "$MODDIR/pin-app.conf"); fi
valid_package() {
  [ "$(printf '%s' "$1" | wc -c)" -le 200 ] &&
    printf '%s\n' "$1" | grep -Eq '^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)+$'
}
action=status
[ "$#" -eq 0 ] || action=$1
[ "$action" = close-all ] || valid_package "$package" ||
  { echo 'Invalid saved app package.' >&2; exit 1; }
case "$action" in
  status) [ "$#" -le 1 ] || exit 2; cli status "$package" ;;
  minimize|restore|close) [ "$#" -eq 1 ] || exit 2; cli "$action" "$package" ;;
  close-all) [ "$#" -eq 1 ] || exit 2; cli close-all ;;
  menu-poll)
    [ "$#" -eq 1 ] || exit 2
    [ ! -f "$MODDIR/disable" ] && [ ! -f "$MODDIR/remove" ] && [ ! -f "$MODDIR/failure" ] || exit 0
    state=/dev/gxr-window-curvature
    [ -f "$state/module-path" ] && [ "$(cat "$state/module-path")" = "$MODDIR" ] || exit 0
    line=$(grep '^GXR_PILL_PIN_REQUEST ' "$MODDIR/runtime.log" | tail -1 || true)
    [ -n "$line" ] || exit 0
    IFS=' ' read -r tag token issued task package extra <<EOF
$line
EOF
    [ "$tag" = GXR_PILL_PIN_REQUEST ] && [ -z "$extra" ] || exit 0
    [ "${#token}" -eq 32 ] && [ -f "$state/pin-menu-token" ] &&
      [ "$token" = "$(cat "$state/pin-menu-token")" ] || exit 0
    case "$issued:$task" in *[!0-9:]*|:*|*:|*:*:*) exit 0 ;; esac
    [ "${#issued}" -le 16 ] && [ "${#task}" -le 10 ] && valid_package "$package" || exit 0
    previous=$(cat "$state/last-pin-menu-request" 2>/dev/null || true)
    [ "$previous" != "$line" ] || exit 0
    printf '%s\n' "$line" > "$state/last-pin-menu-request"
    # Launches can take seconds; the supervisor must keep sending heartbeats.
    (
      set +e
      sh "$MODDIR/pins.sh" pin-task "$task" "$package" "$issued" "$token"
      result=$?
      printf 'pin-result %s %s\n' "$issued" "$result" >&3
    ) >> "$MODDIR/service.log" 2>&1 </dev/null &
    ;;
  pin|pin-task)
    task=
    issued=
    menu_token=
    if [ "$action" = pin-task ]; then
      [ "$#" -eq 5 ] || exit 2
      task=$2
      package=$3
      issued=$4
      menu_token=$5
      case "$issued:$task" in *[!0-9:]*|:*|*:|*:*:*) exit 2 ;; esac
      [ "${#issued}" -le 16 ] && [ "${#task}" -le 10 ] || exit 2
    else
      [ "$#" -eq 2 ] || exit 2
      package=$2
    fi
    menu_session() {
      [ -z "$task" ] || {
        [ ! -f "$MODDIR/disable" ] && [ ! -f "$MODDIR/remove" ] && [ ! -f "$MODDIR/failure" ] &&
          [ ! -f /dev/ksu-restart-stage/busy ] && [ "${#menu_token}" -eq 32 ] &&
          [ -f /dev/gxr-window-curvature/pin-menu-token ] &&
          [ "$menu_token" = "$(cat /dev/gxr-window-curvature/pin-menu-token)" ]
      }
    }
    menu_session || { echo 'The window runtime changed before pinning.' >&2; exit 1; }
    valid_package "$package" || { echo 'Invalid app package.' >&2; exit 2; }
    [ ! -f "$MODDIR/disable" ] && [ ! -f "$MODDIR/remove" ] &&
      [ ! -f "$MODDIR/failure" ] || { echo 'Enable healthy Window Controls first.' >&2; exit 1; }
    [ "$(getprop ro.build.version.incremental)" = I610UES3AZJ2 ] ||
      { echo 'AZJ2 firmware required.' >&2; exit 1; }
    [ -f /dev/gxr-window-curvature/module-path ] &&
      [ "$(cat /dev/gxr-window-curvature/module-path)" = "$MODDIR" ] &&
      grep -q '^RUNNING' /dev/gxr-window-curvature/status ||
      { echo 'Pinned-panel support is not running. Start Window Controls first.' >&2; exit 1; }
    (cd "$MODDIR" && sha256sum -c firmware.sha256 >/dev/null) ||
      { echo 'Firmware verification failed.' >&2; exit 1; }
    component=$(cli resolve "$package") || exit 1
    if [ -z "$task" ]; then cli preflight "$package"; fi
    class=$(printf '%s\n' "$component" | cut -d/ -f2)
    [ "$component" = "$package/$class" ] &&
      printf '%s\n' "$class" | grep -Eq '^[A-Za-z_][A-Za-z0-9_.$]*$' ||
      { echo 'Unexpected launcher component.' >&2; exit 1; }
    KSUD=/data/adb/ksud
    [ -x "$KSUD" ] || { echo 'KernelSU GXR ksud unavailable.' >&2; exit 1; }
    lock=/dev/gxr-window-pins-launch
    if ! mkdir "$lock" 2>/dev/null; then
      previous=$(cat "$lock/pid" 2>/dev/null || true)
      case "$previous" in ''|*[!0-9]*) echo 'Another pin operation is starting.' >&2; exit 1 ;; esac
      if kill -0 "$previous" 2>/dev/null; then
        echo 'Another pin operation is running.' >&2; exit 1
      fi
      rm -f "$lock/pid"
      rmdir "$lock" && mkdir "$lock" || { echo 'Pin operation lock is busy.' >&2; exit 1; }
    fi
    printf '%s\n' "$$" > "$lock/pid"
    prop_package=persist.xr.wm.allowlisted_overlay_activity.package
    prop_class=persist.xr.wm.allowlisted_overlay_activity.class_name
    old_package=$(getprop "$prop_package")
    old_class=$(getprop "$prop_class")
    phase=0
    restore() {
      result=$?
      current_package=$(getprop "$prop_package")
      current_class=$(getprop "$prop_class")
      # Restore only this operation's values; preserve changes made by another owner.
      if [ "$phase" -gt 0 ] &&
          { [ "$current_package" = "$package" ] || [ -z "$current_package" ]; } &&
          { [ "$current_class" = "$class" ] || [ "$current_class" = "$old_class" ]; }; then
        "$KSUD" resetprop -n "$prop_package" '' &&
          "$KSUD" resetprop -n "$prop_class" "$old_class" &&
          "$KSUD" resetprop -n "$prop_package" "$old_package" || result=1
      elif [ "$phase" -gt 0 ]; then
        echo 'Overlay allowlist changed externally; preserved its current values.' >&2
        result=1
      fi
      rm -f "$MODDIR/.pin-app.tmp"
      rm -f "$lock/pid"
      rmdir "$lock" 2>/dev/null || result=1
      trap - EXIT
      exit "$result"
    }
    trap restore EXIT
    trap 'exit 130' HUP INT TERM
    (set -C; printf '%s\n' "$package" > "$MODDIR/.pin-app.tmp")
    mv -f "$MODDIR/.pin-app.tmp" "$MODDIR/pin-app.conf"
    ready=0
    count=0
    while [ "$count" -lt 30 ]; do
      last_pins=$(grep -E '^GXR_PINS_(READY|ERROR|STOPPED)' "$MODDIR/runtime.log" | tail -1 || true)
      case "$last_pins" in
        GXR_PINS_READY*) ready=1; break ;;
        GXR_PINS_ERROR*|GXR_PINS_STOPPED*) break ;;
      esac
      sleep 0.2
      count=$((count + 1))
    done
    [ "$ready" = 1 ] || { echo 'Pinned-panel support is unavailable; export logs.' >&2; exit 1; }
    # -n bypasses persistent storage; a full reboot restores the stock properties.
    phase=1
    "$KSUD" resetprop -n "$prop_package" ''
    "$KSUD" resetprop -n "$prop_class" "$class"
    "$KSUD" resetprop -n "$prop_package" "$package"
    if [ -n "$task" ]; then
      menu_session || { echo 'Window Controls stopped before pinning.' >&2; exit 1; }
      cli close-for-pin "$task" "$package" "$issued"
    fi
    menu_session || { echo 'Window Controls stopped before app launch.' >&2; exit 1; }
    cli launch "$package"
    ;;
  *) echo 'Usage: pins.sh status|pin package|minimize|restore|close|close-all' >&2; exit 2 ;;
esac
