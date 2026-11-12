#!/system/bin/sh
set -u
MODDIR=$(CDPATH='' cd -P "${0%/*}" && pwd) || exit 1
RUN=/dev/questlhsync-gxr
BOOT=$(cat /proc/sys/kernel/random/boot_id)
umask 077
[ "$(id -u)" = 0 ] || { echo 'Root required'; exit 1; }
allowed() { [ -d "$MODDIR" ] && [ ! -f "$MODDIR/disable" ] && [ ! -f "$MODDIR/remove" ]; }
identity() {
  start=$(sed 's/.*) //' "/proc/$1/stat" 2>/dev/null | awk '{print $20}')
  [ -n "$start" ] && printf '%s:%s:%s' "$BOOT" "$1" "$start"
}
owns() { [ "$(cat "$RUN/module-path" 2>/dev/null)" = "$MODDIR" ]; }
same_process() { [ "$(identity "$1")" = "$2" ] && kill -0 "$1" 2>/dev/null; }
live() {
  same_process "$1" "$2" || return 1
  state=$(sed 's/.*) //' "/proc/$1/stat" 2>/dev/null | awk '{print $1}')
  [ -n "$state" ] && [ "$state" != Z ] && [ "$state" != X ]
}
stock() { [ ! -d "$RUN" ]; }
fail() {
  : > "$MODDIR/disable"
  printf '%s\n' "$*" > "$MODDIR/failure"
  printf '%s\n' "$BOOT" > "$MODDIR/failure-boot"
  echo "DISABLED - $*"
  exit 1
}
status() {
  if allowed; then echo 'KernelSU checkbox: ON'; else echo 'KernelSU checkbox: OFF'; fi
  owner=$(cat "$RUN/supervisor-pid" 2>/dev/null)
  owner_id=$(cat "$RUN/supervisor-id" 2>/dev/null)
  worker=$(cat "$RUN/daemon.pid" 2>/dev/null)
  worker_id=$(cat "$RUN/child-id" 2>/dev/null)
  if owns && live "$owner" "$owner_id" && live "$worker" "$worker_id" && [ -f "$RUN/ready" ]; then echo RUNNING
  elif owns && live "$owner" "$owner_id"; then echo 'STARTING - preparing factory calibration'
  else echo 'Runtime not running'; fi
  [ ! -f "$MODDIR/failure" ] || cat "$MODDIR/failure"
  stock && echo 'GXR_UPDATE_STATE=STOCK'
  return 0
}
export_logs() {
  for name in service.log previous.log; do
    source="$RUN/$name"
    if [ "$name" = service.log ] && [ ! -f "$source" ]; then source="$MODDIR/last-service.log"; fi
    [ -f "$source" ] || continue
    target="/data/local/tmp/questlhsync-gxr-$name"
    cp "$source" "$target" && chown 2000:2000 "$target" && chmod 600 "$target" || return 1
  done
}
stop_runtime() {
  stock && return 0
  owns || { echo 'Another or stale QVR service owns the runtime; fully reboot'; return 1; }
  pid=$(cat "$RUN/supervisor-pid" 2>/dev/null)
  saved=$(cat "$RUN/supervisor-id" 2>/dev/null)
  live "$pid" "$saved" || { echo 'Supervisor identity lost; fully reboot before replacing files'; return 1; }
  : > "$RUN/stop"
  tries=0
  while [ -d "$RUN" ] && [ "$tries" -lt 20 ]; do sleep 1; tries=$((tries+1)); done
  stock || { echo 'Camera cleanup is unverified; leave off and fully reboot'; return 1; }
}
case "${1:-status}" in
status) status ;;
export) status; export_logs ;;
off) : > "$MODDIR/disable"; stop_runtime && echo 'GXR_UPDATE_STATE=STOCK' ;;
prepare) stop_runtime ;;
start)
  allowed || { status; exit 1; }
  [ ! -f "$MODDIR/failure" ] || [ "$(cat "$MODDIR/failure-boot" 2>/dev/null)" != "$BOOT" ] || { status; echo 'Full reboot required after an unexpected failure'; exit 1; }
  if [ -d "$RUN" ]; then
    owns || { echo 'Unknown QVR runtime owner; fully reboot'; exit 1; }
    owner=$(cat "$RUN/supervisor-pid" 2>/dev/null)
    owner_id=$(cat "$RUN/supervisor-id" 2>/dev/null)
    live "$owner" "$owner_id" || { echo 'Stale supervisor; fully reboot'; exit 1; }
  fi
  if ! owns; then nohup sh "$MODDIR/control.sh" run >> "$MODDIR/service.log" 2>&1 </dev/null & fi
  tries=0
  while [ "$tries" -lt 20 ] && [ ! -f "$RUN/ready" ] && [ ! -f "$MODDIR/failure" ]; do sleep 1; tries=$((tries+1)); done
  status
  export_logs
  [ ! -f "$MODDIR/failure" ]
  ;;
run)
  allowed || exit 0
  gate_tries=0
  while [ -f /dev/ksu-restart-stage/busy ] || [ "$(getprop sys.boot_completed)" != 1 ]; do
    allowed || exit 0
    gate_tries=$((gate_tries+1)); [ "$gate_tries" -lt 120 ] || fail 'Restart did not complete'
    sleep 1
  done
  # shellcheck source=modules/questlhsync/guard.sh
  . "$MODDIR/guard.sh"
  if ! gxr_guard || ! gxr_calibration_guard; then fail 'Unsupported firmware/camera libraries'; fi
  (cd "$MODDIR" && sha256sum -c SHA256SUMS) >/dev/null 2>&1 || fail 'Payload checksum mismatch'
  if [ -f "$MODDIR/failure" ]; then
    previous_boot=$(cat "$MODDIR/failure-boot" 2>/dev/null)
    [ -n "$previous_boot" ] && [ "$previous_boot" != "$BOOT" ] || exit 1
    mv "$MODDIR/failure" "$MODDIR/failure.previous-boot"
    rm -f "$MODDIR/failure-boot"
  fi
  mkdir "$RUN" 2>/dev/null || exit 0
  chmod 700 "$RUN"
  printf '%s\n' "$MODDIR" > "$RUN/module-path"
  printf '%s\n' "$$" > "$RUN/supervisor-pid"
  identity "$$" > "$RUN/supervisor-id"
  CHILD='' CHILD_ID='' CLEAN=1
  cleanup() {
    trap - EXIT INT TERM HUP
    expected=0
    if ! allowed || [ -f "$RUN/stop" ]; then expected=1; fi
    if [ -n "$CHILD" ] && same_process "$CHILD" "$CHILD_ID"; then
      group=$(sed 's/.*) //' "/proc/$CHILD/stat" 2>/dev/null | awk '{print $3}')
      if [ "$group" = "$CHILD" ]; then kill -TERM "-$CHILD" 2>/dev/null || true
      else kill -TERM "$CHILD" 2>/dev/null || true; fi
      tries=0
      while kill -0 "-$CHILD" 2>/dev/null && [ "$tries" -lt 8 ]; do sleep 1; tries=$((tries+1)); done
      if kill -0 "-$CHILD" 2>/dev/null && same_process "$CHILD" "$CHILD_ID"; then kill -KILL "-$CHILD" 2>/dev/null || true; fi
      wait "$CHILD" 2>/dev/null || true
      kill -0 "-$CHILD" 2>/dev/null && CLEAN=0
    elif [ -n "$CHILD" ]; then
      wait "$CHILD" 2>/dev/null || true
      kill -0 "-$CHILD" 2>/dev/null && CLEAN=0
    fi
    if [ "$expected" != 1 ] || [ "$CLEAN" != 1 ]; then
      : > "$MODDIR/disable"
      echo 'Unexpected service stop or unverified camera cleanup; full reboot required' > "$MODDIR/failure"
      printf '%s\n' "$BOOT" > "$MODDIR/failure-boot"
    fi
    [ ! -f "$RUN/service.log" ] || cp "$RUN/service.log" "$MODDIR/last-service.log"
    if [ "$CLEAN" = 1 ]; then rm -rf "$RUN"; fi
  }
  trap cleanup EXIT
  trap 'exit 0' INT TERM HUP
  ready_tries=0
  while [ "$(getprop sys.boot_completed)" != 1 ]; do
    allowed || exit 0
    ready_tries=$((ready_tries+1)); [ "$ready_tries" -lt 60 ] || exit 1
    sleep 1
  done
  STATE=/data/adb/questlhsync-gxr
  mkdir -p "$STATE"
  chmod 700 "$STATE"
  if [ ! -s "$STATE/id" ]; then cat /proc/sys/kernel/random/uuid > "$STATE/id"; chmod 600 "$STATE/id"; fi
  QLHS_ID="gxr-$(cat "$STATE/id")"
  export QLHS_ID
  : > "$RUN/service.log"
  setsid sh "$MODDIR/run.sh" >> "$RUN/service.log" 2>&1 &
  CHILD=$!
  CHILD_ID=$(identity "$CHILD")
  [ -n "$CHILD_ID" ] || exit 1
  printf '%s\n' "$CHILD" > "$RUN/daemon.pid"
  printf '%s\n' "$CHILD_ID" > "$RUN/child-id"
  tries=0
  while live "$CHILD" "$CHILD_ID" && allowed && [ ! -f "$RUN/stop" ]; do
    group=$(sed 's/.*) //' "/proc/$CHILD/stat" 2>/dev/null | awk '{print $3}')
    [ "$group" = "$CHILD" ] || { sleep 1; continue; }
    if grep -q 'lhsyncd .* up:' "$RUN/service.log"; then : > "$RUN/ready"; fi
    tries=$((tries+1))
    [ -f "$RUN/ready" ] || [ "$tries" -lt 60 ] || exit 1
    if [ "$(wc -c < "$RUN/service.log")" -gt 262144 ]; then
      tail -c 65536 "$RUN/service.log" > "$RUN/previous.log"
      : > "$RUN/service.log"
    fi
    sleep 1
  done
  ;;
*) echo 'Usage: control.sh start|status|export|off|prepare|run'; exit 2 ;;
esac
