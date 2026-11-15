#!/system/bin/sh
set -eu
MODDIR=${0%/*}
STATE=/dev/gxr_systemui_optimization_azj2
umask 077
for path in "$STATE" "$STATE/coordinated-restart"; do [ ! -L "$path" ] || exit 1; done
mkdir -p "$STATE"
case "${1:-}" in
prepare)
    : > "$STATE/coordinated-restart"
    count=0
    while [ -d "$STATE/worker" ]; do
        [ "$count" -lt 80 ] || { echo 'Optimization worker did not restore in time'; exit 1; }
        sleep 0.1; count=$((count+1))
    done
    report=$(sh "$MODDIR/auto.sh" status) || exit 1
    printf '%s\n' "$report"
    printf '%s\n' "$report" | grep -q '^GXR_UPDATE_STATE=STOCK$'
    ;;
stopped)
    report=$(sh "$MODDIR/auto.sh" status) || exit 1
    printf '%s\n' "$report" | grep -q '^GXR_UPDATE_STATE=STOCK$'
    ;;
started|abort) exec sh "$MODDIR/service.sh" ;;
*) exit 2 ;;
esac
