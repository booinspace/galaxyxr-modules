#!/system/bin/sh
set -eu
MODDIR=${0%/*}
# shellcheck source=modules/questlhsync/guard.sh
. "$MODDIR/guard.sh"
if ! gxr_guard || ! gxr_calibration_guard; then echo 'Unsupported AZJ2 camera ABI' >&2; exit 2; fi
[ ! -f "$MODDIR/profile.sha256" ] || { echo 'Legacy calibration bundle is unsupported; clean install required' >&2; exit 2; }
sh "$MODDIR/prepare.sh"
QLHS_FW=$(getprop ro.build.version.incremental)
QLHS_MAX_EXPOSURE_NS=$(sh "$MODDIR/settings.sh" get)
QLHS_CALIBRATION_DIR=/dev/questlhsync-gxr/calibration
QLHS_FACTORY_MAP="$QLHS_CALIBRATION_DIR/factory-map.bin"
export QLHS_FW QLHS_MAX_EXPOSURE_NS QLHS_CALIBRATION_DIR QLHS_FACTORY_MAP
export QLHS_CALIBRATED=1 QLHS_SENSOR_TIME=1
exec "$MODDIR/lhsyncd" "$MODDIR"
