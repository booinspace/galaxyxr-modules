#!/system/bin/sh
# Repair the one-off log exporter and acknowledge curvature quarantine after reboot.
set -eu

[ "$(id -u)" = 0 ] || { echo 'Root required'; exit 1; }
case "${1:-repair}" in
  status|off)
    echo 'GXR_UPDATE_STATE=STOCK'
    exit 0
    ;;
  repair) ;;
  *) echo 'Usage: action.sh repair|status|off'; exit 1 ;;
esac

diagnostic=/data/adb/modules/gxr_curvature_diagnostics
backup=/data/adb/gxr-curvature-diagnostics-0.1.0-backup
if [ -d "$diagnostic" ]; then
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
[ -d "$curvature" ] || { echo 'Curvature module is not installed'; exit 0; }
for name in runtime.log failure session-open; do
  [ -f "$curvature/$name" ] || continue
  target="/data/local/tmp/gxr-curvature-$name"
  cp "$curvature/$name" "$target"
  chown 2000:2000 "$target"
  chmod 600 "$target"
  echo "Exported $target"
done

borderless=/data/adb/modules/gxr_borderless_azj2
for name in runtime.log service.log failure; do
  [ -f "$borderless/$name" ] || continue
  target="/data/local/tmp/gxr-borderless-$name"
  cp "$borderless/$name" "$target"
  chown 2000:2000 "$target"
  chmod 600 "$target"
  echo "Exported $target"
done

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
