#!/system/bin/sh
set -u
MODDIR=$(CDPATH='' cd -P "${0%/*}" && pwd) || exit 1
STATE=/dev/gxr_no_lowlight_azj2
KEY=ix.sysui.light_sensor.low_light_threshold
VALUE=-Infinity
BOOT=$(cat /proc/sys/kernel/random/boot_id)
umask 077
[ "$(id -u)" = 0 ] || { echo 'Root required'; exit 1; }
allowed() { [ ! -f "$MODDIR/disable" ] && [ ! -f "$MODDIR/remove" ]; }
sysui() {
  pid=$(pidof com.android.systemui)
  case "$pid" in ''|*[!0-9]*) return 1 ;; esac
  start=$(sed 's/.*) //' "/proc/$pid/stat" 2>/dev/null | awk '{print $20}')
  [ -n "$start" ] && printf '%s:%s:%s' "$BOOT" "$pid" "$start"
}
fail() { : > "$MODDIR/disable"; printf '%s\n' "$*" > "$MODDIR/failure"; echo "DISABLED - $*"; exit 1; }
check() {
  [ "$(getprop ro.product.model)" = SM-I610 ] || fail 'Wrong device'
  [ "$(getprop ro.build.fingerprint)" = 'samsung/xrvst2ue/xrvst2:14/UML2.260301.001/I610UES3AZJ2:user/release-keys' ] || fail 'Unsupported firmware'
  (cd "$MODDIR" && sha256sum -c SHA256SUMS) >/dev/null 2>&1 || fail 'Payload checksum mismatch'
  (cd / && sha256sum -c "$MODDIR/firmware.sha256") >/dev/null 2>&1 || fail 'Firmware checksum mismatch'
}
rp() {
  if command -v resetprop >/dev/null 2>&1; then resetprop "$@"
  elif [ -x /data/adb/ksud ]; then /data/adb/ksud resetprop "$@"
  else echo 'KernelSU resetprop is unavailable'; return 1; fi
}
snapshot() {
  previous=$(sed -n '1p' "$MODDIR/original-property" 2>/dev/null || true)
  if [ "$previous" != "$BOOT" ]; then
    printf '%s\n%s\n' "$BOOT" "$(getprop "$KEY")" > "$MODDIR/original-property.new"
    mv "$MODDIR/original-property.new" "$MODDIR/original-property"
    rm -f "$MODDIR/restored-sysui" "$MODDIR/applied-sysui" "$MODDIR/session-open" "$MODDIR/failure"
  fi
}
restore_property() {
  [ "$(sed -n '1p' "$MODDIR/original-property" 2>/dev/null)" = "$BOOT" ] || return 0
  [ -f "$MODDIR/session-open" ] || return 0
  original=$(sed -n '2p' "$MODDIR/original-property")
  if [ -z "$original" ]; then
    if [ -n "$(getprop "$KEY")" ]; then rp -d "$KEY" || return 1; fi
  else rp -n "$KEY" "$original" || return 1; fi
  [ "$(getprop "$KEY")" = "$original" ] || return 1
  if [ ! -f "$MODDIR/restored-sysui" ]; then
    identity=$(sysui || true)
    printf '%s\n' "${identity:-stopped}" > "$MODDIR/restored-sysui"
  fi
}
stock() {
  previous=$(cat "$MODDIR/session-open" 2>/dev/null || true)
  [ "$previous" = "$BOOT" ] || return 0
  [ -f "$MODDIR/restored-sysui" ] || return 1
  original=$(sed -n '2p' "$MODDIR/original-property")
  [ "$(getprop "$KEY")" = "$original" ] || return 1
  current=$(sysui || true)
  [ -n "$current" ] && [ "$current" != "$(cat "$MODDIR/restored-sysui")" ]
}
status() {
  if allowed; then echo 'KernelSU checkbox: ON'; else echo 'KernelSU checkbox: OFF'; fi
  echo "$KEY=$(getprop "$KEY")"
  [ ! -f "$MODDIR/failure" ] || cat "$MODDIR/failure"
  if stock; then echo 'GXR_UPDATE_STATE=STOCK'
  elif [ -f "$MODDIR/restored-sysui" ]; then echo 'Property restored; restart SystemUI before removal'
  else echo 'APPLIED - this SystemUI session uses the module threshold'; fi
}
case "${1:-action}" in
action)
  check
  status
  if allowed && stock; then echo 'ARMED - use KernelSU GXR Soft restart to apply before SystemUI initializes'; fi
  ;;
status) status ;;
off)
  : > "$MODDIR/disable"
  restore_property || { echo 'Could not restore original threshold'; exit 1; }
  stock || { echo 'Property restored; fully reboot disabled before uninstalling'; exit 1; }
  echo 'GXR_UPDATE_STATE=STOCK'
  ;;
prepare)
  allowed || exit 0
  check
  [ -n "${KSU_RESTART_GENERATION:-}" ] || fail 'Use the GXR coordinated restart'
  command -v resetprop >/dev/null 2>&1 || [ -x /data/adb/ksud ] || fail 'KernelSU resetprop unavailable'
  snapshot
  ;;
stopped)
  allowed || exit 1
  [ -n "${KSU_RESTART_GENERATION:-}" ] || fail 'No coordinated restart generation'
  [ -z "$(pidof com.android.systemui)" ] || fail 'SystemUI did not stop'
  printf '%s\n' "$BOOT" > "$MODDIR/session-open"
  rm -f "$MODDIR/restored-sysui"
  rp -n "$KEY" "$VALUE" || fail 'Could not set the low-light threshold'
  [ "$(getprop "$KEY")" = "$VALUE" ] || fail 'Threshold read-back mismatch'
  ;;
started)
  [ "$(getprop "$KEY")" = "$VALUE" ] || fail 'Threshold was not present at SystemUI startup'
  tries=0
  until identity=$(sysui); do
    sleep 1; tries=$((tries + 1)); [ "$tries" -lt 40 ] || fail 'SystemUI did not return'
  done
  printf '%s\n' "$identity" > "$MODDIR/applied-sysui"
  echo 'Low-light threshold applied; sensor and dim-light threshold remain enabled'
  ;;
abort)
  restore_property || exit 1
  : > "$MODDIR/disable"
  echo 'Restart interrupted; threshold restored, fully reboot disabled before retrying' > "$MODDIR/failure"
  ;;
run)
  allowed || exit 0
  mkdir "$STATE" 2>/dev/null || exit 0
  trap 'rmdir "$STATE" 2>/dev/null || true' EXIT
  while allowed; do sleep 1; done
  restore_property
  ;;
*) echo 'Usage: control.sh action|status|off|prepare|stopped|started|abort|run'; exit 1 ;;
esac
