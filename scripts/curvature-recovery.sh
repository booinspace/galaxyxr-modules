#!/system/bin/sh
# Export diagnostics for the combined window module; control.sh owns reset safety.
set -eu

[ "$(id -u)" = 0 ] || { echo 'Root required'; exit 1; }
case "${1:-export}" in
  status|off)
    echo 'GXR_UPDATE_STATE=STOCK'
    exit 0
    ;;
  export) ;;
  *) echo 'Usage: recovery.sh export|status|off'; exit 1 ;;
esac

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
      for marker in disable remove update failure session-open injected-identity clean-stop; do
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
