# Sourced by control.sh after firmware/payload checks, or by its disabled reset command.
clear_after_reboot() {
  [ -f "$MODDIR/failure" ] || [ -f "$MODDIR/session-open" ] || return 0
  [ ! -d "$STATE" ] || { echo 'Runtime state remains; fully reboot first.'; return 1; }
  previous=$(cat "$MODDIR/injected-identity" 2>/dev/null || true)
  boot=$(cat /proc/sys/kernel/random/boot_id) || return 1
  boot_pattern='[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}'
  printf '%s\n' "$boot" | grep -Eq "^$boot_pattern$" || {
    echo 'Current boot identity unavailable; manual review required.'
    return 1
  }
  printf '%s\n' "$previous" | grep -Eq "^$boot_pattern:[1-9][0-9]*:[1-9][0-9]*$" || {
    echo 'Previous injection identity missing or invalid; manual review required.'
    return 1
  }
  if [ -f "$MODDIR/session-open" ] && [ "$(cat "$MODDIR/session-open")" != "$previous" ]; then
    echo 'Session identity differs from the injection record; manual review required.'
    return 1
  fi
  case "$previous" in
    "$boot":*)
      sh "$MODDIR/restart.sh" await "$previous" || {
        echo 'Planned restart startup gate failed; full reboot required.'
        return 1
      }
      restart_target=$(sh "$MODDIR/restart.sh" authorize "$previous") || {
        echo 'Full reboot required; no verified planned-restart handoff.'
        return 1
      }
      ;;
  esac
  sh "$MODDIR/recovery.sh" export || return 1
  suffix="pre-reset.$(date +%s).$$"
  for name in runtime.log failure session-open; do
    if [ -f "$MODDIR/$name" ]; then
      archived="$MODDIR/$name.$suffix"
      [ ! -e "$archived" ] && mv "$MODDIR/$name" "$archived" || return 1
    fi
  done
  echo 'Previous session acknowledged; diagnostics preserved.'
}
