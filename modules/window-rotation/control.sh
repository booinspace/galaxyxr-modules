#!/system/bin/sh
set -u
MODDIR=$(CDPATH='' cd -P "${0%/*}" && pwd) || exit 1
STATE=/dev/gxr-window-rotation
LOG="$MODDIR/runtime.log"
FINGERPRINT='samsung/xrvst2ue/xrvst2:14/UML2.260301.001/I610UES3AZJ2:user/release-keys'
umask 077
[ "$(id -u)" = 0 ] || { echo 'Root required'; exit 1; }

allowed() { [ ! -f "$MODDIR/disable" ] && [ ! -f "$MODDIR/remove" ]; }
start_time() { sed 's/.*) //' "/proc/$1/stat" 2>/dev/null | awk '{print $20}'; }
identity() { printf '%s:%s:%s' "$(cat /proc/sys/kernel/random/boot_id)" "$1" "$(start_time "$1")"; }
owns_state() { [ -f "$STATE/module-path" ] && [ "$(cat "$STATE/module-path")" = "$MODDIR" ]; }
fail() {
  : > "$MODDIR/disable"
  printf '%s\n' "$*" > "$MODDIR/failure"
  echo "DISABLED - $*"
  exit 1
}
clear_after_reboot() {
  [ ! -d "$STATE" ] || return 0
  previous=$(cat "$MODDIR/injected-identity" 2>/dev/null || true)
  boot=$(cat /proc/sys/kernel/random/boot_id)
  case "$previous" in ''|"$boot":*) return 0 ;; esac
  for name in runtime.log session-open failure; do
    [ ! -f "$MODDIR/$name" ] || mv "$MODDIR/$name" "$MODDIR/$name.before-$(date +%s)-$$" || return 1
  done
}
stock() {
  [ ! -d "$STATE" ] || return 1
  [ ! -f "$MODDIR/session-open" ] && return 0
  previous=$(cat "$MODDIR/injected-identity" 2>/dev/null || true)
  boot=$(cat /proc/sys/kernel/random/boot_id)
  case "$previous" in ''|"$boot":*) return 1 ;; *) return 0 ;; esac
}
status() {
  if allowed; then echo 'KernelSU checkbox: ON'; else echo 'KernelSU checkbox: OFF'; fi
  if owns_state; then cat "$STATE/status"; else echo 'Runtime not attached'; fi
  [ ! -f "$MODDIR/failure" ] || cat "$MODDIR/failure"
  if stock; then echo 'GXR_UPDATE_STATE=STOCK'; else echo 'Restoration pending; disable and fully reboot if it does not finish'; fi
}
export_logs() {
  for name in runtime.log failure session-open; do
    [ -f "$MODDIR/$name" ] || continue
    destination="/data/local/tmp/gxr-rotation-$name"
    cp "$MODDIR/$name" "$destination" || return 1
    chown 2000:2000 "$destination" && chmod 600 "$destination" || return 1
  done
  echo 'Available logs exported to /data/local/tmp/gxr-rotation-*'
}

case "${1:-action}" in
status) status ;;
off)
  : > "$MODDIR/disable"
  count=0
  while owns_state && [ "$count" -lt 18 ]; do sleep 1; count=$((count + 1)); done
  stock || { echo 'Restoration remains unverified; fully reboot before removal'; exit 1; }
  echo 'GXR_UPDATE_STATE=STOCK'
  ;;
reset)
  [ -f "$MODDIR/disable" ] || { echo 'Disable rotation first'; exit 1; }
  clear_after_reboot || exit 1
  stock || { echo 'Full reboot required before reset'; exit 1; }
  status
  ;;
action)
  if allowed && ! owns_state; then
    clear_after_reboot || exit 1
    if [ -f "$MODDIR/failure" ] || [ -f "$MODDIR/session-open" ]; then
      status; export_logs
      echo 'Leave disabled and fully reboot before retrying'
      exit 1
    fi
    nohup sh "$MODDIR/control.sh" run >> "$MODDIR/service.log" 2>&1 </dev/null &
    count=0
    while [ "$count" -lt 30 ]; do
      [ ! -f "$MODDIR/failure" ] || break
      if owns_state && grep -q '^RUNNING' "$STATE/status"; then break; fi
      sleep 1
      count=$((count + 1))
    done
  fi
  status
  [ ! -f "$LOG" ] || tail -8 "$LOG"
  export_logs
  ;;
run)
  allowed || exit 0
  owns_state && exit 0
  clear_after_reboot || fail 'Could not archive previous boot diagnostics'
  [ ! -f "$MODDIR/failure" ] && [ ! -f "$MODDIR/session-open" ] || fail 'Previous session needs a full reboot'
  for module in gxr_borderless_azj2 gxr_window_curvature; do
    other="/data/adb/modules/$module"
    if [ -d "$other" ] && [ ! -f "$other/disable" ] && [ ! -f "$other/remove" ]; then
      fail "Disable $module before the first isolated rotation test"
    fi
  done
  [ ! -d /dev/gxr-borderless-azj2 ] && [ ! -d /dev/gxr-window-curvature ] || fail 'Another window runtime is still stopping'
  [ -z "$(pidof frida-inject)" ] || fail 'Another injector is running; stop it before rotation'
  [ "$(getprop sys.boot_completed)" = 1 ] || fail 'Wait until Android finishes booting'
  [ "$(getprop ro.product.model)" = SM-I610 ] || fail 'Wrong device model'
  [ "$(getprop ro.build.fingerprint)" = "$FINGERPRINT" ] || fail 'Unsupported firmware'
  (cd "$MODDIR" && sha256sum -c SHA256SUMS) >/dev/null 2>&1 || fail 'Module payload hash mismatch'
  (cd / && sha256sum -c "$MODDIR/firmware.sha256") >/dev/null 2>&1 || fail 'Stock firmware hash mismatch'
  # shellcheck disable=SC2046
  set -- $(pidof com.android.systemui)
  [ "$#" -eq 1 ] || fail 'Expected exactly one SystemUI process'
  target=$1
  target_identity=$(identity "$target")
  [ -n "$(start_time "$target")" ] || fail 'SystemUI identity unavailable'
  [ "$(cat "$MODDIR/injected-identity" 2>/dev/null || true)" != "$target_identity" ] || fail 'Already tested this SystemUI incarnation; fully reboot before retrying'
  mkdir "$STATE" 2>/dev/null || fail 'Stale runtime state; fully reboot before retrying'
  chmod 700 "$STATE"
  printf '%s\n' "$MODDIR" > "$STATE/module-path"
  printf '%s\n' 'STARTING' > "$STATE/status"
  injector_pid=
  injector_start=
  ready=0
  cleanup() {
    trap - EXIT INT TERM HUP
    if [ -n "$injector_pid" ]; then
      printf 'stop\n' >&3 2>/dev/null || true
      count=0
      until grep -q '^GXR_ROTATION_STOPPED ' "$LOG" 2>/dev/null || [ "$count" -ge 10 ]; do
        kill -0 "$injector_pid" 2>/dev/null || break
        sleep 1
        count=$((count + 1))
      done
      if [ -n "$injector_start" ] && [ "$(start_time "$injector_pid")" = "$injector_start" ]; then
        kill -TERM "$injector_pid" 2>/dev/null || true
        sleep 2
        [ "$(start_time "$injector_pid")" != "$injector_start" ] || kill -KILL "$injector_pid" 2>/dev/null || true
      fi
      wait "$injector_pid" 2>/dev/null || true
      exec 3>&-
    fi
    if grep -q '^GXR_ROTATION_STOPPED ' "$LOG"; then
      rm -f "$MODDIR/session-open"
      if allowed; then
        : > "$MODDIR/disable"
        echo 'Unexpected stop; rotation restoration confirmed' > "$MODDIR/failure"
      fi
    else
      : > "$MODDIR/disable"
      echo 'Restoration unverified; leave disabled and fully reboot' > "$MODDIR/failure"
    fi
    rm -f "$STATE/module-path" "$STATE/status" "$STATE/control"
    rmdir "$STATE" 2>/dev/null || true
  }
  trap cleanup EXIT
  trap 'exit 1' INT TERM HUP
  mkfifo "$STATE/control" || fail 'Could not create injector control pipe'
  exec 3<> "$STATE/control"
  : > "$LOG"
  printf '%s\n' "$target_identity" > "$MODDIR/injected-identity"
  printf '%s\n' "$target_identity" > "$MODDIR/session-open"
  "$MODDIR/bin/frida-inject" -p "$target" -s "$MODDIR/bin/agent.js" -R qjs -i < "$STATE/control" >> "$LOG" 2>&1 &
  injector_pid=$!
  injector_start=$(start_time "$injector_pid")
  count=0
  while allowed && [ "$(identity "$target")" = "$target_identity" ]; do
    kill -0 "$injector_pid" 2>/dev/null || break
    grep -q '^GXR_ROTATION_FATAL ' "$LOG" && break
    grep -q '^GXR_ROTATION_STOPPED ' "$LOG" && break
    printf 'pulse\n' >&3 || break
    if grep -q '^GXR_ROTATION_READY' "$LOG"; then
      ready=1
      echo 'RUNNING - open an ordinary app window menu for rotation controls' > "$STATE/status"
    elif [ "$count" -ge 25 ]; then break; fi
    count=$((count + 1))
    if [ "$ready" -eq 1 ] && [ "$(wc -c < "$LOG")" -gt 524288 ]; then
      tail -40 "$LOG" > "$LOG.trim" && cat "$LOG.trim" > "$LOG"
      rm -f "$LOG.trim"
    fi
    sleep 1
  done
  ;;
*) echo 'Usage: control.sh action|status|off|reset|run'; exit 1 ;;
esac
