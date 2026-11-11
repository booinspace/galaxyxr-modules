#!/system/bin/sh
export ID=gxr_passthrough_azj2 MAIN=com.gxr.pt.Main MANUAL_TOGGLE=1
MODDIR=${0%/*}
# The builder adds the shared runtime to bin/.
# shellcheck disable=SC1091
. "$MODDIR/bin/runtime.sh"
