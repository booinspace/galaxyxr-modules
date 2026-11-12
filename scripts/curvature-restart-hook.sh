#!/system/bin/sh
MODDIR=${0%/*}
phase=${0##*/}
phase=${phase#restart-}
exec sh "$MODDIR/restart.sh" "${phase%.sh}"
