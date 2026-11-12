#!/system/bin/sh
MODDIR=${0%/*}
exec sh "$MODDIR/control.sh" "${1:-action}"
