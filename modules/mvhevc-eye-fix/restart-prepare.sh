#!/system/bin/sh
MODDIR=${0%/*}
exec sh "$MODDIR/control.sh" prepare
