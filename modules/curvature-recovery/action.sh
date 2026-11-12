#!/system/bin/sh
# Repair the one-off log exporter and acknowledge curvature quarantine after reboot.
set -eu

[ "$(id -u)" = 0 ] || { echo 'Root required'; exit 1; }
case "${1:-repair}" in
  status|off)
    echo 'GXR_UPDATE_STATE=STOCK'
    exit 0
    ;;
  repair|export) ;;
  *) echo 'Usage: action.sh repair|export|status|off'; exit 1 ;;
esac

diagnostic=/data/adb/modules/gxr_curvature_diagnostics
backup=/data/adb/gxr-curvature-diagnostics-0.1.0-backup
if [ "${1:-repair}" = repair ] && [ -d "$diagnostic" ]; then
  grep -qx 'id=gxr_curvature_diagnostics' "$diagnostic/module.prop"
  grep -qx 'versionCode=1' "$diagnostic/module.prop"
  [ -f "$diagnostic/disable" ] || { echo 'Disable the diagnostic helper first'; exit 1; }
  (cd "$diagnostic" && sha256sum -c SHA256SUMS >/dev/null) || {
    echo 'Diagnostic files changed; leaving them in place'; exit 1;
  }
  [ ! -e "$backup" ] || { echo "Backup already exists at $backup"; exit 1; }
  mv "$diagnostic" "$backup"
  echo "Archived old diagnostic helper to $backup; refresh the Modules screen"
fi

curvature=/data/adb/modules/gxr_window_curvature
for name in runtime.log service.log failure session-open module.prop; do
  target="/data/local/tmp/gxr-curvature-$name"
  rm -f "$target"
  if [ -f "$curvature/$name" ]; then
    cp "$curvature/$name" "$target"
    chown 2000:2000 "$target"
    chmod 600 "$target"
    echo "Exported $target"
  fi
done

borderless=/data/adb/modules/gxr_borderless_azj2
for name in runtime.log service.log failure; do
  target="/data/local/tmp/gxr-borderless-$name"
  rm -f "$target"
  if [ -f "$borderless/$name" ]; then
    cp "$borderless/$name" "$target"
    chown 2000:2000 "$target"
    chmod 600 "$target"
    echo "Exported $target"
  fi
done

umask 077
snapshot=$(mktemp /data/local/tmp/gxr-window-diagnostics.XXXXXX)
{
  date
  echo "BOOT=$(cat /proc/sys/kernel/random/boot_id)"
  echo "SYSTEMUI=$(pidof com.android.systemui || true)"
  for id in gxr_window_curvature gxr_borderless_azj2 gxr_window_rotation; do
    path="/data/adb/modules/$id"
    echo "MODULE=$id"
    if [ -d "$path" ]; then
      head -c 4096 "$path/module.prop" || true
      for marker in disable remove update failure session-open injected-identity; do
        if [ -e "$path/$marker" ]; then
          echo "MARKER=$marker"
          head -c 4096 "$path/$marker" || true
          echo
        fi
      done
      if [ -f "$path/SHA256SUMS" ]; then
        (cd "$path" && sha256sum -c SHA256SUMS) || true
      fi
      echo 'FILES: size link-count path'
      find "$path" -type f -exec stat -c '%s %h %n' {} \; || true
      echo 'SYMLINKS:'
      find "$path" -type l -print || true
    else
      echo 'NOT_INSTALLED'
    fi
    pending="/data/adb/modules_update/$id"
    if [ -e "$pending" ]; then
      echo "PENDING=$pending"
      head -c 4096 "$pending/module.prop" || true
    fi
  done
  for name in error busy ready generation; do
    path="/dev/ksu-restart-stage/$name"
    if [ -f "$path" ]; then
      echo "RESTART=$name"
      head -c 8192 "$path" || true
      echo
    fi
  done
  for name in generation phase old-target new-target; do
    path="/dev/gxr-window-curvature-restart/$name"
    if [ -f "$path" ]; then
      echo "WINDOW_RESTART=$name"
      head -c 4096 "$path" || true
      echo
    fi
  done
  for phase in prepare stopped started abort; do
    path="/dev/ksu-restart-stage/logs/gxr_window_curvature-$phase.log"
    if [ -f "$path" ]; then
      echo "WINDOW_RESTART_HOOK=$phase"
      head -c 65536 "$path" || true
      echo
    fi
  done
} > "$snapshot" 2>&1
chown 2000:2000 "$snapshot"
chmod 600 "$snapshot"
mv -f "$snapshot" /data/local/tmp/gxr-window-diagnostics.txt
echo 'Exported /data/local/tmp/gxr-window-diagnostics.txt'

[ "${1:-repair}" != export ] || exit 0

[ -d "$curvature" ] || { echo 'Curvature module is not installed'; exit 0; }

if [ -f "$borderless/failure" ] || grep -q '^GXR_BORDERLESS_FATAL ' "$borderless/runtime.log" 2>/dev/null; then
  [ -f "$borderless/disable" ] || { echo 'Disable Borderless before reset'; exit 1; }
  [ ! -d /dev/gxr-borderless-azj2 ] || { echo 'Borderless runtime remains; reboot first'; exit 1; }
  previous=$(cat "$borderless/injected-identity" 2>/dev/null || true)
  [ -n "$previous" ] || { echo 'Borderless identity missing; manual review required'; exit 1; }
  boot=$(cat /proc/sys/kernel/random/boot_id)
  case "$previous" in
    "$boot":*) echo 'Full reboot required before Borderless quarantine can be reset'; exit 0 ;;
  esac
  if [ -f "$borderless/runtime.log" ]; then
    archived="$borderless/runtime.pre-reset.$(date +%s).$$.log"
    [ ! -e "$archived" ] && mv "$borderless/runtime.log" "$archived" || exit 1
  fi
  rm -f "$borderless/failure"
  echo 'Borderless quarantine acknowledged; module remains disabled; retry update'
fi

if [ -f "$curvature/failure" ] || [ -f "$curvature/session-open" ]; then
  [ -f "$curvature/disable" ] || { echo 'Disable curvature before reset'; exit 1; }
  previous=$(cat "$curvature/injected-identity" 2>/dev/null || true)
  boot=$(cat /proc/sys/kernel/random/boot_id)
  case "$previous" in
    "$boot":*) echo 'Full reboot required before curvature quarantine can be reset'; exit 0 ;;
  esac
  /system/bin/sh "$curvature/control.sh" reset
else
  echo 'Curvature has no quarantine marker to reset'
fi
