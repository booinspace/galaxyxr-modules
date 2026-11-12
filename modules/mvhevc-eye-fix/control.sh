#!/system/bin/sh
set -u
MODDIR=$(CDPATH='' cd -P "${0%/*}" && pwd) || exit 1
RUN=/dev/gxr-mvhevc-azj2
SF=/system/lib64/libstagefright.so
AP=/system/lib64/libaplayer.so
SF_HASH=8db37c90c458e92faad1f0a6160d53e769da9759c6db14fb2cfedbcec1727490
AP_HASH=a1d055498e9bc9b09850748944f0605c7fd9052eec2050f027fa4724b449b047
SF_PATCHED=4e51540d13f50d94f6c8deabae1137158af826cff29c56cd30ce4963a9ef1973
AP_PATCHED=017dc755311dfc9ff42d2501d4daa4c33ce92ec7d1d543c333a80c6f62d18ddd
umask 077
[ "$(id -u)" = 0 ] || { echo 'Root required'; exit 1; }
current_ns=$(readlink /proc/self/ns/mnt) || exit 1
init_ns=$(readlink /proc/1/ns/mnt) || exit 1
[ -n "$current_ns" ] && [ -n "$init_ns" ] || exit 1
if [ "$current_ns" != "$init_ns" ]; then
  exec nsenter --mount=/proc/1/ns/mnt -- sh "$0" "$@"
fi
allowed() { [ -d "$MODDIR" ] && [ ! -f "$MODDIR/disable" ] && [ ! -f "$MODDIR/remove" ]; }
digest() { sha256sum "$1" 2>/dev/null | cut -d' ' -f1; }
file_id() { stat -c '%d:%i' "$1" 2>/dev/null; }
owned() { [ -n "$2" ] && [ "$(file_id "$1")" = "$2" ]; }
mounted() { grep -qF " $1 " /proc/self/mountinfo; }
load_owner() {
  SF_ID=$(cat "$RUN/sf-id" 2>/dev/null)
  AP_ID=$(cat "$RUN/ap-id" 2>/dev/null)
  TOKEN=$(cat "$RUN/token" 2>/dev/null)
}
watcher_live() {
  pid=$(cat "$RUN/watcher-pid" 2>/dev/null)
  case "$pid" in ''|*[!0-9]*) return 1 ;; esac
  stamp=$(sed 's/.*) //' "/proc/$pid/stat" 2>/dev/null | awk '{print $20}')
  state=$(sed 's/.*) //' "/proc/$pid/stat" 2>/dev/null | awk '{print $1}')
  [ "$state" != Z ] && [ -n "$stamp" ] && [ "$pid:$stamp" = "$(cat "$RUN/watcher-id" 2>/dev/null)" ] && kill -0 "$pid" 2>/dev/null
}
stock() {
  [ "$(digest "$SF")" = "$SF_HASH" ] && [ "$(digest "$AP")" = "$AP_HASH" ] &&
    ! mounted "$SF" && ! mounted "$AP" && [ ! -d "$RUN" ]
}
status() {
  if allowed; then echo 'KernelSU checkbox: ON'; else echo 'KernelSU checkbox: OFF'; fi
  load_owner
  if [ -n "$TOKEN" ] && watcher_live && owned "$SF" "$SF_ID" && owned "$AP" "$AP_ID" &&
      [ "$(digest "$SF")" = "$SF_PATCHED" ] && [ "$(digest "$AP")" = "$AP_PATCHED" ]; then
    echo 'ENABLED - reviewed MV-HEVC library copies are mounted'
  elif stock; then echo 'DISABLED - original libraries restored'; echo 'GXR_UPDATE_STATE=STOCK'
  else echo 'DISABLED - unverified/partial state; use off or fully reboot'; fi
}
make_payload() {
  src=$1 name=$2 baseline=$3 expected=$4
  target="$MODDIR/bin/$name"
  [ "$(digest "$target")" != "$expected" ] || return 0
  [ "$(digest "$src")" = "$baseline" ] || return 1
  mkdir -p "$MODDIR/bin" || return 1
  temporary="$target.new.$$"
  cp "$src" "$temporary" || return 1
  patch_ok=0
  case "$name" in
    libstagefright.so) printf '\025' | dd of="$temporary" bs=1 seek=1817377 count=1 conv=notrunc 2>/dev/null && patch_ok=1 ;;
    libaplayer.so)
      printf '\025' | dd of="$temporary" bs=1 seek=2309657 count=1 conv=notrunc 2>/dev/null &&
      printf '\043\000\200\122' | dd of="$temporary" bs=1 seek=1005196 count=4 conv=notrunc 2>/dev/null && patch_ok=1 ;;
    *) rm -f "$temporary"; return 1 ;;
  esac
  if [ "$patch_ok" != 1 ] || [ "$(digest "$temporary")" != "$expected" ]; then rm -f "$temporary"; return 1; fi
  chown 0:0 "$temporary" && chmod 0444 "$temporary" &&
    chcon u:object_r:system_lib_file:s0 "$temporary" && mv -f "$temporary" "$target"
}
restore_one() {
  target=$1 saved_id=$2 baseline=$3
  if owned "$target" "$saved_id"; then
    umount "$target" 2>/dev/null || umount -l "$target" 2>/dev/null || return 1
  elif mounted "$target"; then echo "Refusing unrelated mount: $target"; return 1; fi
  [ "$(digest "$target")" = "$baseline" ] && ! mounted "$target"
}
restore() {
  [ ! -d "$RUN" ] || [ "$(cat "$RUN/module-path" 2>/dev/null)" = "$MODDIR" ] || return 1
  [ -n "$TOKEN" ] || { stock; return; }
  [ "$(cat "$RUN/token" 2>/dev/null)" = "$TOKEN" ] || return 0
  am force-stop com.samsung.android.galleryxr >/dev/null 2>&1 || true
  ok=1
  restore_one "$SF" "$SF_ID" "$SF_HASH" || ok=0
  restore_one "$AP" "$AP_ID" "$AP_HASH" || ok=0
  [ "$ok" = 1 ] || { echo 'Restoration unverified; fully reboot'; return 1; }
  rm -rf "$RUN"
}
lock() { exec 9>/dev/gxr-mvhevc-azj2.lock; flock -x 9; }
case "${1:-action}" in
status) status ;;
off|prepare)
  [ "$1" != off ] || : > "$MODDIR/disable"
  lock
  load_owner
  restore || exit 1
  stock && echo 'GXR_UPDATE_STATE=STOCK'
  ;;
watch)
  load_owner
  [ "$#" = 2 ] && [ "$2" = "$TOKEN" ] || exit 1
  start_token=$TOKEN
  watch_cleanup() {
    code=$?
    trap - EXIT INT TERM
    lock
    if [ "$(cat "$RUN/token" 2>/dev/null)" = "$start_token" ]; then
      if [ "$code" != 0 ] && [ "$(getprop sys.boot_completed)" = 1 ] &&
          [ -z "$(getprop sys.powerctl)$(getprop sys.shutdown.requested)" ]; then
        : > "$MODDIR/disable"
        echo 'Watcher stopped unexpectedly; original libraries requested' > "$MODDIR/failure"
      fi
      restore || exit 1
    fi
  }
  trap watch_cleanup EXIT
  trap 'exit 1' INT TERM
  pending=0
  # Cached functions and inode ownership still work if the module files are removed.
  while allowed && [ "$(cat "$RUN/token" 2>/dev/null)" = "$start_token" ] && [ ! -f "$RUN/stop" ]; do
    if [ ! -f "$RUN/ready" ]; then pending=$((pending+1)); [ "$pending" -lt 10 ] || exit 1; fi
    sleep 1
  done
  ;;
action|on)
  if ! allowed; then lock; load_owner; restore || exit 1; status; exit 0; fi
  [ "$(getprop ro.build.fingerprint)" = 'samsung/xrvst2ue/xrvst2:14/UML2.260301.001/I610UES3AZJ2:user/release-keys' ] || { echo 'AZJ2 required'; exit 1; }
  (cd "$MODDIR" && sha256sum -c SHA256SUMS) >/dev/null 2>&1 || exit 1
  lock
  load_owner
  if [ -n "$TOKEN" ]; then
    owned "$SF" "$SF_ID" && owned "$AP" "$AP_ID" && watcher_live && { status; exit 0; }
    restore || exit 1
  fi
  stock || { echo 'Unexpected media baseline; no changes made'; exit 1; }
  if ! make_payload "$SF" libstagefright.so "$SF_HASH" "$SF_PATCHED" ||
      ! make_payload "$AP" libaplayer.so "$AP_HASH" "$AP_PATCHED"; then echo 'Payload generation refused'; exit 1; fi
  mkdir "$RUN" || exit 1
  printf '%s\n' "$MODDIR" > "$RUN/module-path"
  cat /proc/sys/kernel/random/uuid > "$RUN/token"
  file_id "$MODDIR/bin/libstagefright.so" > "$RUN/sf-id"
  file_id "$MODDIR/bin/libaplayer.so" > "$RUN/ap-id"
  load_owner
  # Start the watcher before either mount, so disable/remove can always request rollback.
  nohup sh "$MODDIR/control.sh" watch "$TOKEN" 9>&- >> "$MODDIR/runtime.log" 2>&1 </dev/null &
  watcher=$!
  printf '%s\n' "$watcher" > "$RUN/watcher-pid"
  stamp=$(sed 's/.*) //' "/proc/$watcher/stat" 2>/dev/null | awk '{print $20}')
  printf '%s:%s\n' "$watcher" "$stamp" > "$RUN/watcher-id"
  kill -0 "$watcher" 2>/dev/null || { restore; exit 1; }
  if ! mount -o bind "$MODDIR/bin/libstagefright.so" "$SF" ||
      ! mount -o bind "$MODDIR/bin/libaplayer.so" "$AP" ||
      [ "$(digest "$SF")" != "$SF_PATCHED" ] || [ "$(digest "$AP")" != "$AP_PATCHED" ]; then
    : > "$MODDIR/disable"
    restore
    echo 'Apply failed; original-library restoration requested'
    exit 1
  fi
  : > "$RUN/ready"
  am force-stop com.samsung.android.galleryxr >/dev/null 2>&1 || true
  status
  ;;
*) echo 'Usage: control.sh action|on|off|status|prepare'; exit 2 ;;
esac
