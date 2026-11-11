#!/system/bin/sh
set -u
MODDIR=$(CDPATH='' cd -P "${0%/*}" && pwd) || exit 1
STATE=/dev/gxr-borderless-azj2
LOG="$MODDIR/runtime.log"
FINGERPRINT='samsung/xrvst2ue/xrvst2:14/UML2.260301.001/I610UES3AZJ2:user/release-keys'
umask 077

allowed() { [ ! -f "$MODDIR/disable" ] && [ ! -f "$MODDIR/remove" ]; }
start_time() { sed 's/.*) //' "/proc/$1/stat" 2>/dev/null | awk '{print $20}'; }
identity() { printf '%s:%s:%s' "$(cat /proc/sys/kernel/random/boot_id)" "$1" "$(start_time "$1")"; }
fail() {
  : > "$MODDIR/disable"
  printf '%s\n' "$*" > "$MODDIR/failure"
  echo "DISABLED - $*"
  exit 1
}
owns_state() { [ -f "$STATE/module-path" ] && [ "$(cat "$STATE/module-path")" = "$MODDIR" ]; }

case "${1:-status}" in
status)
  if allowed; then echo 'KernelSU checkbox: ON'; else echo 'KernelSU checkbox: OFF'; fi
  if owns_state; then cat "$STATE/status"; else echo 'Runtime not attached.'; fi
  [ ! -f "$MODDIR/failure" ] || cat "$MODDIR/failure"
  [ ! -f "$LOG" ] || tail -5 "$LOG"
  previous=$(cat "$MODDIR/injected-identity" 2>/dev/null || true)
  boot=$(cat /proc/sys/kernel/random/boot_id)
  case "$previous" in
    "$boot":*) echo 'Existing windows may retain the changed rim until reopened.' ;;
    *) [ ! -d "$STATE" ] && echo 'GXR_UPDATE_STATE=STOCK' ;;
  esac
  ;;
off)
  : > "$MODDIR/disable"
  count=0
  while owns_state && [ "$count" -lt 12 ]; do sleep 1; count=$((count + 1)); done
  if owns_state; then echo 'The hook has not detached; inspect runtime.log.'; exit 1; fi
  echo 'Hook stopped. Caption pills are visible; reopen affected app windows to restore their stock rim.'
  ;;
run)
  [ "$(id -u)" = 0 ] || { echo 'Root required.'; exit 1; }
  allowed || exit 0
  [ ! -f "$MODDIR/failure" ] || { echo 'Previous failure is quarantined until a reboot.'; exit 1; }
  count=0
  until [ "$(getprop sys.boot_completed)" = 1 ]; do
    allowed || exit 0
    count=$((count + 1))
    [ "$count" -lt 60 ] || fail 'Android boot completion timed out'
    sleep 2
  done
  [ "$(getprop ro.product.model)" = SM-I610 ] || fail 'Wrong device model'
  [ "$(getprop ro.build.fingerprint)" = "$FINGERPRINT" ] || fail 'Unsupported firmware'
  (cd "$MODDIR" && sha256sum -c SHA256SUMS) >/dev/null 2>&1 || fail 'Module payload hash mismatch'
  (cd / && sha256sum -c "$MODDIR/firmware.sha256") >/dev/null 2>&1 || fail 'SystemUI hash mismatch'
  # Split pidof output so multiple SystemUI processes are rejected.
  # shellcheck disable=SC2046
  set -- $(pidof com.android.systemui)
  [ "$#" -eq 1 ] || fail 'Expected one SystemUI process'
  target=$1
  target_identity=$(identity "$target")
  [ -n "$(start_time "$target")" ] || fail 'SystemUI identity unavailable'
  [ "$(cat "$MODDIR/injected-identity" 2>/dev/null || true)" != "$target_identity" ] || fail 'Already attached to this SystemUI process'
  mkdir "$STATE" 2>/dev/null || { echo 'Runtime already active or stale; reboot before retrying.'; exit 1; }
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
      until grep -q '^GXR_BORDERLESS_STOPPED ' "$LOG" 2>/dev/null || [ "$count" -ge 6 ]; do
        kill -0 "$injector_pid" 2>/dev/null || break
        sleep 1
        count=$((count + 1))
      done
      if [ -n "$injector_start" ] && [ "$(start_time "$injector_pid")" = "$injector_start" ]; then
        kill -TERM "$injector_pid" 2>/dev/null || true
        count=0
        while [ "$(start_time "$injector_pid")" = "$injector_start" ] && [ "$count" -lt 3 ]; do
          sleep 1
          count=$((count + 1))
        done
        [ "$(start_time "$injector_pid")" != "$injector_start" ] || kill -KILL "$injector_pid" 2>/dev/null || true
      fi
      wait "$injector_pid" 2>/dev/null || true
      exec 3>&-
    fi
    if [ "$ready" -eq 1 ] && grep -q '^GXR_BORDERLESS_STOPPED ' "$LOG" && ! allowed; then
      echo 'STOPPED - Java hook detached.'
    else
      : > "$MODDIR/disable"
      if [ "$(identity "$target")" != "$target_identity" ]; then
        printf '%s\n' 'SystemUI process changed; hook discarded' > "$MODDIR/failure"
      else
        printf '%s\n' 'Hook restoration unverified; disable and reboot before retrying' > "$MODDIR/failure"
      fi
      cat "$MODDIR/failure"
    fi
    rm -f "$STATE/module-path" "$STATE/status" "$STATE/control"
    rmdir "$STATE" 2>/dev/null || true
  }
  trap cleanup EXIT
  trap 'exit 1' INT TERM HUP
  mkfifo "$STATE/control" || fail 'Could not create control pipe'
  exec 3<> "$STATE/control"
  : > "$LOG"
  printf '%s\n' "$target_identity" > "$MODDIR/injected-identity"
  "$MODDIR/bin/frida-inject" -p "$target" -s "$MODDIR/bin/agent.js" -R qjs -i < "$STATE/control" >> "$LOG" 2>&1 &
  injector_pid=$!
  injector_start=$(start_time "$injector_pid")
  count=0
  while allowed && [ "$(identity "$target")" = "$target_identity" ]; do
    kill -0 "$injector_pid" 2>/dev/null || break
    grep -q '^GXR_BORDERLESS_FATAL ' "$LOG" && break
    grep -q '^GXR_BORDERLESS_STOPPED ' "$LOG" && break
    printf 'pulse\n' >&3 || break
    if grep -q '^GXR_BORDERLESS_READY' "$LOG"; then
      ready=1
      printf '%s\n' 'RUNNING - app rims suppressed and captions shown on hover' > "$STATE/status"
    elif [ "$count" -ge 20 ]; then break; fi
    count=$((count + 1))
    sleep 1
  done
  ;;
*) echo 'Usage: action.sh status|off'; exit 1 ;;
esac
