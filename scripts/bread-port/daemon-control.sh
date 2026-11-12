#!/system/bin/sh
# Module identity is provided by its checksummed control.sh wrapper.
# shellcheck disable=SC2154
set -u
MODDIR=$(CDPATH='' cd -P "${0%/*}" && pwd) || exit 1
STATE="/dev/$ID"
BOOT=$(cat /proc/sys/kernel/random/boot_id)
umask 077
[ "$(id -u)" = 0 ] || { echo 'Root required'; exit 1; }
allowed() { [ ! -f "$MODDIR/disable" ] && [ ! -f "$MODDIR/remove" ]; }
start_time() { sed 's/.*) //' "/proc/$1/stat" 2>/dev/null | awk '{print $20}'; }
identity() { printf '%s:%s:%s' "$BOOT" "$1" "$(start_time "$1")"; }
owns() { [ -f "$STATE/module-path" ] && [ "$(cat "$STATE/module-path")" = "$MODDIR" ]; }
child_live() {
  child=$(cat "$STATE/child-pid" 2>/dev/null || true)
  case "$child" in ''|*[!0-9]*) return 1 ;; esac
  [ "$(cat "$STATE/child-id" 2>/dev/null)" = "$(identity "$child")" ] && kill -0 "$child" 2>/dev/null
}
fail() { : > "$MODDIR/disable"; printf '%s\n' "$*" > "$MODDIR/failure"; echo "DISABLED - $*"; exit 1; }
full_boot_cleanup() {
  previous=$(cat "$MODDIR/session-open" 2>/dev/null || true)
  case "$previous" in ''|"$BOOT") return 0 ;; esac
  [ ! -d "$STATE" ] || return 1
  for name in session-open failure daemon.log; do
    [ ! -f "$MODDIR/$name" ] || mv "$MODDIR/$name" "$MODDIR/$name.before-$(date +%s)-$$" || return 1
  done
}
stock() {
  [ ! -d "$STATE" ] || return 1
  previous=$(cat "$MODDIR/session-open" 2>/dev/null || true)
  [ -z "$previous" ] || [ "$previous" != "$BOOT" ]
}
status() {
  if allowed; then echo 'KernelSU checkbox: ON'; else echo 'KernelSU checkbox: OFF'; fi
  if owns && child_live && [ -f "$STATE/ready" ]; then echo 'RUNNING'; else echo 'Runtime not running'; fi
  [ ! -f "$MODDIR/failure" ] || cat "$MODDIR/failure"
  if stock; then echo 'GXR_UPDATE_STATE=STOCK'; else echo 'Runtime owns changes or restoration remains pending'; fi
}
restore_now() {
  CLASSPATH="$MODDIR/bin/helper.dex" GXR_PORT_STATE="$STATE" \
    timeout 10 /system/bin/app_process /system/bin "$MAIN" restore "$MODDIR"
}
stop_child() {
  : > "$STATE/stop"
  child=$(cat "$STATE/child-pid" 2>/dev/null || true)
  case "$child" in ''|*[!0-9]*) return 1 ;; esac
  if [ ! -s "$STATE/child-id" ] && kill -0 "$child" 2>/dev/null; then return 1; fi
  tries=0
  while child_live && [ "$tries" -lt 12 ]; do sleep 1; tries=$((tries + 1)); done
  if child_live; then
    kill -TERM "$child" 2>/dev/null || true
    sleep 2
    if child_live; then kill -KILL "$child" 2>/dev/null || true; sleep 1; fi
  fi
  ! child_live
}
stop_runtime() {
  if owns; then
    : > "$STATE/stop"
    tries=0
    while owns && [ "$tries" -lt 18 ]; do sleep 1; tries=$((tries + 1)); done
    if owns; then
      supervisor=$(cat "$STATE/supervisor-pid" 2>/dev/null || true)
      case "$supervisor" in ''|*[!0-9]*) echo 'Unknown runtime owner; full reboot required'; return 1 ;; esac
      if [ "$(cat "$STATE/supervisor-id")" = "$(identity "$supervisor")" ] && kill -0 "$supervisor" 2>/dev/null; then
        echo 'Supervisor still stopping; retry after it finishes'; return 1
      fi
      [ -f "$STATE/child-pid" ] || { echo 'Unknown child process; full reboot required'; return 1; }
      stop_child || return 1
      restore_now || return 1
      rm -f "$MODDIR/session-open"
      rm -rf "$STATE"
    fi
  fi
  if ! stock; then
    restore_now || return 1
    rm -f "$MODDIR/session-open"
  fi
}
export_logs() {
  for name in daemon.log failure; do
    [ -f "$MODDIR/$name" ] || continue
    destination="/data/local/tmp/$ID-$name"
    cp "$MODDIR/$name" "$destination" && chown 2000:2000 "$destination" && chmod 600 "$destination" || return 1
  done
}
case "${1:-action}" in
status) status ;;
export) status; export_logs ;;
off)
  : > "$MODDIR/disable"
  stop_runtime || exit 1
  stock && echo 'GXR_UPDATE_STATE=STOCK'
  ;;
prepare)
  if owns; then : > "$STATE/restart"; fi
  stop_runtime
  ;;
action)
  if ! owns && allowed; then
    full_boot_cleanup || exit 1
    stock || { status; export_logs; echo 'Restore or fully reboot before retrying'; exit 1; }
    rm -f "$MODDIR/failure"
    nohup sh "$MODDIR/control.sh" run >> "$MODDIR/service.log" 2>&1 </dev/null &
    tries=0
    while [ "$tries" -lt 25 ]; do
      [ ! -f "$MODDIR/failure" ] || break
      if owns && [ -f "$STATE/ready" ]; then break; fi
      sleep 1; tries=$((tries + 1))
    done
  elif owns && [ "$MANUAL_TOGGLE" = 1 ] && [ -f "$STATE/ready" ]; then
    printf 'toggle\n' > "$STATE/command.new" && mv "$STATE/command.new" "$STATE/command"
    sleep 1
  fi
  status
  [ ! -f "$MODDIR/daemon.log" ] || tail -8 "$MODDIR/daemon.log"
  export_logs
  [ ! -f "$MODDIR/failure" ]
  ;;
run)
  allowed || exit 0
  owns && exit 0
  full_boot_cleanup || fail 'Stale runtime state; fully reboot before retrying'
  stock || fail 'Previous restoration is unverified; fully reboot before retrying'
  [ "$(getprop ro.product.model)" = SM-I610 ] || fail 'Wrong device model'
  [ "$(getprop ro.build.fingerprint)" = 'samsung/xrvst2ue/xrvst2:14/UML2.260301.001/I610UES3AZJ2:user/release-keys' ] || fail 'Unsupported firmware'
  [ "$(getprop sys.boot_completed)" = 1 ] || fail 'Wait until Android boot completes'
  (cd "$MODDIR" && sha256sum -c SHA256SUMS) >/dev/null 2>&1 || fail 'Payload checksum mismatch'
  (cd / && sha256sum -c "$MODDIR/firmware.sha256") >/dev/null 2>&1 || fail 'Firmware checksum mismatch'
  [ -f "$MODDIR/config.conf" ] || cp "$MODDIR/config.default.conf" "$MODDIR/config.conf" || fail 'Cannot create runtime config'
  mkdir "$STATE" 2>/dev/null || fail 'Another runtime or stale lock exists'
  chmod 700 "$STATE"
  printf '%s\n' "$MODDIR" > "$STATE/module-path"
  printf '%s\n' "$$" > "$STATE/supervisor-pid"
  identity "$$" > "$STATE/supervisor-id"
  cleanup() {
    trap - EXIT INT TERM HUP
    expected=0
    if ! allowed || [ -f "$STATE/restart" ]; then expected=1; fi
    stopped=0
    if stop_child; then
      stopped=1
      [ -z "${child:-}" ] || wait "$child" 2>/dev/null || true
    fi
    if [ "$stopped" = 1 ] && restore_now >> "$MODDIR/daemon.log" 2>&1; then
      rm -f "$MODDIR/session-open"
    else
      echo 'Restoration unverified; leave disabled and fully reboot' > "$MODDIR/failure"
      expected=0
    fi
    if [ "$expected" = 0 ]; then
      : > "$MODDIR/disable"
      [ -f "$MODDIR/failure" ] || echo 'Daemon stopped unexpectedly; inspect daemon.log' > "$MODDIR/failure"
    fi
    rm -rf "$STATE"
  }
  trap cleanup EXIT
  trap 'exit 1' INT TERM HUP
  touch "$STATE/pulse"
  printf '%s\n' "$BOOT" > "$MODDIR/session-open"
  sysui_pid=$(pidof com.android.systemui)
  case "$sysui_pid" in ''|*[!0-9]*) fail 'Expected one SystemUI process' ;; esac
  sysui_id=$(identity "$sysui_pid")
  : > "$MODDIR/daemon.log"
  CLASSPATH="$MODDIR/bin/helper.dex" GXR_PORT_STATE="$STATE" GXR_SYSUI_ID="$sysui_id" \
    /system/bin/app_process /system/bin --nice-name="$ID" "$MAIN" daemon "$MODDIR" >> "$MODDIR/daemon.log" 2>&1 &
  child=$!
  printf '%s\n' "$child" > "$STATE/child-pid"
  child_start=$(start_time "$child")
  [ -n "$child_start" ] || fail 'Could not identify the daemon child'
  printf '%s:%s:%s' "$BOOT" "$child" "$child_start" > "$STATE/child-id"
  while allowed && child_live && [ ! -f "$STATE/stop" ]; do
    touch "$STATE/pulse"
    if [ "$(wc -c < "$MODDIR/daemon.log")" -gt 262144 ]; then
      tail -40 "$MODDIR/daemon.log" > "$MODDIR/daemon.log.trim"
      cat "$MODDIR/daemon.log.trim" > "$MODDIR/daemon.log"
      rm -f "$MODDIR/daemon.log.trim"
    fi
    sleep 1
  done
  ;;
*) echo 'Usage: control.sh action|status|export|off|prepare|run'; exit 1 ;;
esac
