#!/system/bin/sh
set -u
MODDIR=$(CDPATH='' cd -P "${0%/*}" && pwd) || exit 1
RUN=/dev/gxr-root-ft-azj2
STATE=/data/adb/gxr-root-ft-azj2
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
valid_pc() {
  printf '%s\n' "$1" | awk -F. 'NR!=1 || NF!=4{exit 1} {for(i=1;i<=4;i++) if($i !~ /^[0-9]+$/ || length($i)>3 || $i+0>255 || (length($i)>1 && substr($i,1,1)=="0")) exit 1; if($1==0 || $1==127 || $1>=224 || $4==0 || $4==255) exit 1}'
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
  pc=$(cat "$STATE/pc" 2>/dev/null)
  if valid_pc "$pc"; then printf 'PC=%s UDP=41463\n' "$pc"; else echo 'PC address not configured'; fi
  owner=$(cat "$RUN/supervisor-pid" 2>/dev/null)
  owner_id=$(cat "$RUN/supervisor-id" 2>/dev/null)
  worker=$(cat "$RUN/daemon.pid" 2>/dev/null)
  worker_id=$(cat "$RUN/child-id" 2>/dev/null)
  if owns && live "$owner" "$owner_id" && live "$worker" "$worker_id" && [ -f "$RUN/ready" ]; then echo RUNNING
  elif owns && live "$owner" "$owner_id"; then echo STARTING
  else echo STOPPED; fi
  [ ! -f "$MODDIR/failure" ] || cat "$MODDIR/failure"
  stock && echo 'GXR_UPDATE_STATE=STOCK'
  return 0
}
export_logs() {
  source="$RUN/service.log"
  [ -f "$source" ] || source="$MODDIR/last-service.log"
  [ -f "$source" ] || return 0
  target=/data/local/tmp/gxr-root-ft-runtime.log
  cp "$source" "$target" && chown 2000:2000 "$target" && chmod 600 "$target" || return 1
  echo "Exported $target (status/health counters; no raw face samples)"
}
stop_runtime() {
  stock && return 0
  owns || { echo 'Unknown relay owner; fully reboot before replacing files'; return 1; }
  pid=$(cat "$RUN/supervisor-pid" 2>/dev/null)
  saved=$(cat "$RUN/supervisor-id" 2>/dev/null)
  live "$pid" "$saved" || { echo 'Supervisor identity lost; fully reboot'; return 1; }
  : > "$RUN/stop"
  tries=0
  while [ -d "$RUN" ] && [ "$tries" -lt 20 ]; do sleep 1; tries=$((tries+1)); done
  stock || { echo 'Probe cleanup not verified; leave off and fully reboot'; return 1; }
}
case "${1:-status}" in
status) status ;;
export) status; export_logs ;;
set-pc)
  [ "$#" -eq 2 ] && valid_pc "$2" || { echo 'Enter one unicast PC IPv4 address'; exit 2; }
  stock || { echo 'Stop the relay before changing its destination'; exit 1; }
  mkdir -p "$STATE"; chmod 700 "$STATE"
  printf '%s\n' "$2" > "$STATE/pc.new" && mv "$STATE/pc.new" "$STATE/pc" || exit 1
  status
  ;;
off) : > "$MODDIR/disable"; stop_runtime && echo 'GXR_UPDATE_STATE=STOCK' ;;
prepare|stop) stop_runtime ;;
start)
  allowed || { status; exit 1; }
  pc=$(cat "$STATE/pc" 2>/dev/null)
  valid_pc "$pc" || { echo 'Set the receiving PC IPv4 address in Action first'; exit 0; }
  [ ! -f "$MODDIR/failure" ] || [ "$(cat "$MODDIR/failure-boot" 2>/dev/null)" != "$BOOT" ] || { status; echo 'Full reboot required after an unexpected failure'; exit 1; }
  if [ -d "$RUN" ]; then
    owns || { echo 'Unknown runtime owner; fully reboot'; exit 1; }
    owner=$(cat "$RUN/supervisor-pid" 2>/dev/null)
    owner_id=$(cat "$RUN/supervisor-id" 2>/dev/null)
    live "$owner" "$owner_id" || { echo 'Stale supervisor; fully reboot'; exit 1; }
  else
    nohup sh "$MODDIR/control.sh" run >> "$MODDIR/service.log" 2>&1 </dev/null &
  fi
  status
  ;;
run)
  allowed || exit 0
  pc=$(cat "$STATE/pc" 2>/dev/null)
  valid_pc "$pc" || exit 0
  gate=0
  while [ -f /dev/ksu-restart-stage/busy ] || [ "$(getprop sys.boot_completed)" != 1 ]; do
    allowed || exit 0
    gate=$((gate+1)); [ "$gate" -lt 120 ] || fail 'GXR restart did not complete'
    sleep 1
  done
  . "$MODDIR/guard.sh"
  gxr_guard || fail 'Unsupported firmware or tracking library hash'
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
      kill -TERM "$CHILD" 2>/dev/null || true
      tries=0
      while live "$CHILD" "$CHILD_ID" && [ "$tries" -lt 8 ]; do sleep 1; tries=$((tries+1)); done
      if live "$CHILD" "$CHILD_ID"; then kill -KILL "$CHILD" 2>/dev/null || true; fi
      wait "$CHILD" 2>/dev/null || true
    fi
    if [ -n "$CHILD" ] && live "$CHILD" "$CHILD_ID"; then CLEAN=0
    elif [ -n "$CHILD" ]; then "$MODDIR/bin/gxr_alvr" --cleanup >> "$RUN/service.log" 2>&1 || CLEAN=0; fi
    if [ "$expected" != 1 ] || [ "$CLEAN" != 1 ]; then
      : > "$MODDIR/disable"
      echo 'Unexpected relay exit or unverified probe cleanup; full reboot required' > "$MODDIR/failure"
      printf '%s\n' "$BOOT" > "$MODDIR/failure-boot"
    fi
    [ ! -f "$RUN/service.log" ] || cp "$RUN/service.log" "$MODDIR/last-service.log"
    [ "$CLEAN" != 1 ] || rm -rf "$RUN"
  }
  trap cleanup EXIT
  trap 'exit 0' INT TERM HUP
  LOG="$RUN/service.log"
  : > "$LOG"
  . "$MODDIR/cgroup.sh"
  escape_manager_cgroup || exit 1
  setsid "$MODDIR/bin/gxr_alvr" --pc "$pc" --port 41463 --state-dir "$STATE" >> "$LOG" 2>&1 &
  CHILD=$!
  CHILD_ID=$(identity "$CHILD")
  [ -n "$CHILD_ID" ] || exit 1
  printf '%s\n' "$CHILD" > "$RUN/daemon.pid"
  printf '%s\n' "$CHILD_ID" > "$RUN/child-id"
  tries=0
  while live "$CHILD" "$CHILD_ID" && allowed && [ ! -f "$RUN/stop" ]; do
    if grep -q 'armed pten@' "$LOG"; then : > "$RUN/ready"; fi
    tries=$((tries+1))
    [ -f "$RUN/ready" ] || [ "$tries" -lt 30 ] || exit 1
    sleep 1
  done
  ;;
*) echo 'Usage: control.sh start|status|export|set-pc IPv4|stop|off|prepare|run'; exit 2 ;;
esac
