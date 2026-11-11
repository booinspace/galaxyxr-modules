#!/system/bin/sh
export ID=gxr_mic_gain_azj2 MAIN=com.gxr.mic.Main MANUAL_TOGGLE=0
MODDIR=${0%/*}
# The builder adds the shared runtime to bin/.
# shellcheck disable=SC1091
. "$MODDIR/bin/runtime.sh"
