#!/system/bin/sh
set -eu
MODDIR=$(CDPATH= cd -P "$(dirname "$0")" && pwd)
umask 077
[ "$(id -u)" = 0 ] || { echo 'Root required.' >&2; exit 1; }
[ "$#" -gt 0 ] || set -- json
CURVATURE=1 BORDERLESS=1 ROTATION=1 GRAB=0
load_features() {
  [ -f "$MODDIR/features.conf" ] || return 0
  seen=' '
  count=0
  while IFS='=' read -r key value || [ -n "$key" ]; do
    case "$key" in CURVATURE|BORDERLESS|ROTATION|GRAB) ;; *) return 1 ;; esac
    case "$value" in 0|1) ;; *) return 1 ;; esac
    case "$seen" in *" $key "*) return 1 ;; esac
    seen="$seen$key "
    count=$((count + 1))
    case "$key" in
      CURVATURE) CURVATURE=$value ;; BORDERLESS) BORDERLESS=$value ;;
      ROTATION) ROTATION=$value ;; GRAB) GRAB=$value ;;
    esac
  done < "$MODDIR/features.conf"
  [ "$count" -eq 4 ]
}
case "$1" in
set)
  [ "$#" -eq 5 ] || exit 2
  for value in "$2" "$3" "$4" "$5"; do
    case "$value" in 0|1) ;; *) echo 'Expected four boolean values.' >&2; exit 2 ;; esac
  done
  temporary="$MODDIR/.features.$$.tmp"
  trap 'rm -f "$temporary"' EXIT
  (set -C; printf 'CURVATURE=%s\nBORDERLESS=%s\nROTATION=%s\nGRAB=%s\n' "$2" "$3" "$4" "$5" > "$temporary")
  mv -f "$temporary" "$MODDIR/features.conf"
  exec sh "$MODDIR/features.sh" json
  ;;
wire|json)
  load_features || { echo 'Invalid saved feature settings; no change applied.' >&2; exit 1; }
  if [ "$1" = wire ]; then
    printf 'features %s %s %s %s\n' "$CURVATURE" "$BORDERLESS" "$ROTATION" "$GRAB"
  else
    runtime=STOPPED
    grab_runtime=off
    if [ "$ROTATION" = 1 ] && [ "$GRAB" = 1 ]; then
      grab_runtime=unknown
      last_grab=$(grep '^GXR_GRAB_STATE ' "$MODDIR/runtime.log" 2>/dev/null | tail -1 || true)
      case "$last_grab" in
        'GXR_GRAB_STATE waiting') grab_runtime=waiting ;;
        'GXR_GRAB_STATE tracking') grab_runtime=tracking ;;
        'GXR_GRAB_STATE unavailable') grab_runtime=unavailable ;;
      esac
    fi
    [ ! -f "$MODDIR/disable" ] || runtime=DISABLED
    [ ! -f "$MODDIR/failure" ] || runtime=QUARANTINED
    if [ "$runtime" = STOPPED ] && [ -d /dev/gxr-window-curvature-launch ]; then
      runtime=STARTING
    fi
    if [ -f /dev/gxr-window-curvature/module-path ] &&
        [ "$(cat /dev/gxr-window-curvature/module-path)" = "$MODDIR" ]; then
      case "$(cat /dev/gxr-window-curvature/status 2>/dev/null || true)" in
        RUNNING*) runtime=RUNNING ;; STARTING*) runtime=STARTING ;;
      esac
    fi
    [ "$runtime" = RUNNING ] || grab_runtime=off
    caption_ready=0
    if [ "$runtime" = RUNNING ]; then
      last_caption=$(grep -E '^GXR_BORDERLESS_(READY|STOPPED)( |$)' "$MODDIR/runtime.log" 2>/dev/null | tail -1 || true)
      [ "$last_caption" != GXR_BORDERLESS_READY ] || caption_ready=1
    fi
    restart_required=0
    if [ "$runtime" = STOPPED ] && [ -f "$MODDIR/restart.sh" ] &&
        sh "$MODDIR/restart.sh" needs-restart; then restart_required=1; fi
    printf '{"curvature":%s,"borderless":%s,"rotation":%s,"grab":%s,"runtime":"%s","grabRuntime":"%s","captionReady":%s,"restartRequired":%s}\n' \
      "$CURVATURE" "$BORDERLESS" "$ROTATION" "$GRAB" "$runtime" "$grab_runtime" "$caption_ready" "$restart_required"
  fi
  ;;
*) echo 'Usage: features.sh json|wire|set curvature borderless rotation grab' >&2; exit 2 ;;
esac
