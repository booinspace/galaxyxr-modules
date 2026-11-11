#!/system/bin/sh
MODDIR=${0%/*}
sh "$MODDIR/control.sh" "${1:-status}"
