#!/system/bin/sh
# Only a verified KernelSU restart may authorize one same-boot reattachment.
set -eu
MODDIR=$(CDPATH= cd -P "${0%/*}" && pwd)
STATE=/dev/gxr-window-curvature
LAUNCH=/dev/gxr-window-curvature-launch
HANDOFF=/dev/gxr-window-curvature-restart
COORD=/dev/ksu-restart-stage
MIN_SYSTEMUI_AGE_SECONDS=90
umask 077
[ "$(id -u)" = 0 ] || exit 1
read_file() { cat "$1" 2>/dev/null || true; }
allowed() { [ ! -f "$MODDIR/disable" ] && [ ! -f "$MODDIR/remove" ]; }
start_time() { sed 's/.*) //' "/proc/$1/stat" 2>/dev/null | awk '{print $20}'; }
identity() { printf '%s:%s:%s' "$(cat /proc/sys/kernel/random/boot_id)" "$1" "$(start_time "$1")"; }
valid_identity() { printf '%s\n' "$1" | grep -Eq '^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}:[1-9][0-9]*:[1-9][0-9]*$'; }
current_target() {
  set -- $(pidof com.android.systemui)
  [ "$#" -eq 1 ] || return 1
  current=$(identity "$1")
  valid_identity "$current" || return 1
  printf '%s\n' "$current"
}
old_is_dead() {
  old=$(read_file "$HANDOFF/old-target")
  valid_identity "$old" || return 1
  pid=${old#*:}; pid=${pid%%:*}
  [ "$(identity "$pid")" != "$old" ]
}
runtime_gone() {
  [ ! -d "$STATE" ] && [ ! -d "$LAUNCH" ] && [ -z "$(pidof frida-inject)" ]
}
if [ "${1:-}" = needs-restart ]; then
  allowed && [ ! -d "$STATE" ] && [ -z "$(pidof frida-inject)" ] &&
    [ ! -f "$MODDIR/failure" ] && [ ! -f "$MODDIR/session-open" ] || exit 1
  previous=$(read_file "$MODDIR/injected-identity")
  valid_identity "$previous" && [ "$previous" = "$(read_file "$MODDIR/clean-stop")" ] &&
    [ "$previous" = "$(current_target)" ] || exit 1
  exit 0
fi
phase=${1:-}
if [ "$phase" != startup ]; then
  generation=$(read_file "$COORD/generation")
  printf '%s\n' "$generation" | grep -Eq '^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$' || exit 1
fi
case "$phase" in
prepare|stopped|started|abort)
  [ "${KSU_RESTART_GENERATION:-}" = "$generation" ] || exit 1
  [ "$phase" = abort ] || { [ -f "$COORD/busy" ] && allowed; } || exit 1
  ;;
esac
case "$phase" in
prepare)
  (cd "$MODDIR" && sha256sum -c SHA256SUMS) >/dev/null 2>&1 || exit 1
  if [ -d "$HANDOFF" ]; then
    case "$(read_file "$HANDOFF/phase")" in
      consumed|idle-complete)
        rm -f "$HANDOFF/generation" "$HANDOFF/phase" "$HANDOFF/old-target" "$HANDOFF/new-target" "$HANDOFF/request"
        rmdir "$HANDOFF" || exit 1
        ;;
      *) echo 'An unfinished window restart requires a full reboot.'; exit 1 ;;
    esac
  fi
  if [ ! -d "$STATE" ]; then
    runtime_gone || { echo 'Window runtime is starting or another injector is active.'; exit 1; }
    if [ -f "$MODDIR/failure" ] || [ -f "$MODDIR/session-open" ]; then
      previous=$(read_file "$MODDIR/injected-identity")
      valid_identity "$previous" || exit 1
      case "$previous" in
        "$(cat /proc/sys/kernel/random/boot_id)":*) echo 'A crashed window session requires a full reboot.'; exit 1 ;;
      esac
    fi
    if [ "$(read_file "$MODDIR/injected-identity")" = "$(current_target)" ] &&
        ! sh "$MODDIR/restart.sh" needs-restart; then
      echo 'Clean shutdown proof is missing; fully reboot before retrying.'
      exit 1
    fi
    mkdir "$HANDOFF"
    printf '%s\n' "$generation" > "$HANDOFF/generation"
    if sh "$MODDIR/restart.sh" needs-restart; then
      previous=$(read_file "$MODDIR/clean-stop")
      printf '%s\n' "$previous" > "$HANDOFF/old-target"
      printf '%s\n' "$previous" > "$MODDIR/session-open"
      echo quiesced > "$HANDOFF/phase"
    else
      echo idle > "$HANDOFF/phase"
    fi
    exit 0
  fi
  [ "$(read_file "$STATE/module-path")" = "$MODDIR" ] || exit 1
  grep -q '^RUNNING' "$STATE/status" || { echo 'Wait for window controls to finish starting.'; exit 1; }
  target=$(current_target)
  [ "$target" = "$(read_file "$STATE/target")" ] &&
    [ "$target" = "$(read_file "$MODDIR/injected-identity")" ] &&
    [ "$target" = "$(read_file "$MODDIR/session-open")" ] &&
    [ ! -f "$MODDIR/failure" ] || exit 1
  set -- $(pidof frida-inject)
  [ "$#" -eq 1 ] && [ "$1" = "$(read_file "$STATE/injector-pid")" ] || exit 1
  mkdir "$HANDOFF"
  printf '%s\n' "$generation" > "$HANDOFF/generation"
  printf '%s\n' "$target" > "$HANDOFF/old-target"
  echo preparing > "$HANDOFF/phase"
  printf '%s\n' "$target" > "$HANDOFF/request"
  count=0
  while [ "$count" -lt 25 ]; do
    allowed || exit 1
    if [ "$(read_file "$HANDOFF/phase")" = quiesced ] && runtime_gone; then
      echo 'Window hooks stopped cleanly; waiting for Android restart.'
      exit 0
    fi
    sleep 1
    count=$((count + 1))
  done
  echo 'Window cleanup was not acknowledged; Android must remain running.'
  exit 1
  ;;
requested|complete)
  [ -f "$COORD/busy" ] && allowed &&
    [ "$generation" = "$(read_file "$HANDOFF/generation")" ] &&
    [ "$(read_file "$HANDOFF/phase")" = preparing ] &&
    [ "${2:-}" = "$(read_file "$HANDOFF/request")" ] &&
    [ "${2:-}" = "$(current_target)" ] &&
    [ ! -f "$MODDIR/failure" ] || exit 1
  if [ "$phase" = complete ]; then
    runtime_gone || exit 1
    rm "$HANDOFF/request"
    echo quiesced > "$HANDOFF/phase"
  fi
  ;;
stopped)
  [ "$generation" = "$(read_file "$HANDOFF/generation")" ] && runtime_gone || exit 1
  case "$(read_file "$HANDOFF/phase")" in
    idle) echo idle-stopped > "$HANDOFF/phase" ;;
    quiesced)
      count=0
      until old_is_dead; do
        [ "$count" -lt 10 ] || exit 1
        sleep 1
        count=$((count + 1))
      done
      echo android-stopped > "$HANDOFF/phase"
      ;;
    *) exit 1 ;;
  esac
  ;;
started)
  [ "$generation" = "$(read_file "$HANDOFF/generation")" ] && runtime_gone || exit 1
  [ "$(getprop sys.boot_completed)" = 1 ] || exit 1
  case "$(read_file "$HANDOFF/phase")" in
    idle-stopped) echo idle-complete > "$HANDOFF/phase" ;;
    android-stopped)
      old_is_dead || exit 1
      target=$(current_target)
      old=$(read_file "$HANDOFF/old-target")
      [ "${target%%:*}" = "${old%%:*}" ] && [ "$target" != "$old" ] &&
        [ "$old" = "$(read_file "$MODDIR/session-open")" ] &&
        [ "$old" = "$(read_file "$MODDIR/injected-identity")" ] &&
        [ ! -f "$MODDIR/failure" ] || exit 1
      printf '%s\n' "$target" > "$HANDOFF/new-target"
      echo verified > "$HANDOFF/phase"
      ;;
    *) exit 1 ;;
  esac
  ;;
startup|await|authorize)
  if [ "$phase" = startup ]; then
    target=${2:-}
    valid_identity "$target" && allowed && [ ! -d "$STATE" ] &&
      [ ! -f "$MODDIR/failure" ] && [ ! -f "$MODDIR/session-open" ] &&
      [ -z "$(pidof frida-inject)" ] || exit 1
  else
    [ ! -f "$COORD/busy" ] && [ -f "$COORD/ready" ] && allowed &&
      [ "$generation" = "$(read_file "$HANDOFF/generation")" ] &&
      [ "$(read_file "$HANDOFF/phase")" = verified ] &&
      [ "${2:-}" = "$(read_file "$HANDOFF/old-target")" ] &&
      [ "${2:-}" = "$(read_file "$MODDIR/session-open")" ] &&
      [ "${2:-}" = "$(read_file "$MODDIR/injected-identity")" ] &&
      [ ! -f "$MODDIR/failure" ] && [ ! -d "$STATE" ] &&
      [ -z "$(pidof frida-inject)" ] && old_is_dead || exit 1
    target=$(current_target)
    [ "$target" = "$(read_file "$HANDOFF/new-target")" ] || exit 1
  fi
  ticks=$(getconf CLK_TCK) || exit 1
  case "$ticks" in ''|*[!0-9]*) exit 1 ;; esac
  [ "$ticks" -gt 0 ] && [ "$ticks" -le 1000000 ] || exit 1
  start=${target##*:}
  count=0
  while :; do
    allowed && [ ! -f "$COORD/busy" ] && [ "$target" = "$(current_target)" ] || exit 1
    if [ "$phase" != startup ]; then
      [ -f "$COORD/ready" ] && [ "$generation" = "$(read_file "$COORD/generation")" ] &&
        [ "$(read_file "$HANDOFF/phase")" = verified ] || exit 1
    fi
    age=$(awk -v ticks="$ticks" -v start="$start" 'NR == 1 { if ($1 ~ /^[0-9]+([.][0-9]+)?$/) printf "%.0f", $1 * ticks - start; else exit 1 }' /proc/uptime) || exit 1
    case "$age" in ''|*[!0-9]*) exit 1 ;; esac
    [ "$age" -ge "$((MIN_SYSTEMUI_AGE_SECONDS * ticks))" ] && break
    [ "$phase" != authorize ] && [ "$count" -lt 100 ] || exit 1
    if [ "$count" -eq 0 ]; then
      echo "STARTUP_WAIT - waiting until SystemUI is at least $MIN_SYSTEMUI_AGE_SECONDS seconds old." >&2
    fi
    sleep 1
    count=$((count + 1))
  done
  if [ "$phase" = authorize ]; then
    echo consumed > "$HANDOFF/phase"
    printf '%s\n' "$target"
  elif [ "$phase" = startup ]; then
    echo "STARTUP_AGE_PASSED - SystemUI identity unchanged; minimum age $MIN_SYSTEMUI_AGE_SECONDS seconds." >&2
  else
    echo 'STARTUP_AGE_PASSED - process identity and restart generation unchanged.' >&2
  fi
  ;;
abort)
  [ "$generation" = "$(read_file "$HANDOFF/generation")" ] || exit 0
  case "$(read_file "$HANDOFF/phase")" in
    idle|idle-stopped|idle-complete) echo idle-complete > "$HANDOFF/phase" ;;
    *)
      : > "$MODDIR/disable"
      echo 'Planned restart was interrupted; fully reboot before retrying window controls.' > "$MODDIR/failure"
      echo aborted > "$HANDOFF/phase"
      ;;
  esac
  ;;
*) exit 2 ;;
esac
