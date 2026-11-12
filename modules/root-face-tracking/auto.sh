#!/system/bin/sh
MODDIR=${0%/*}
case "${1:-on}" in on) exec sh "$MODDIR/control.sh" start ;; *) exec sh "$MODDIR/control.sh" "$@" ;; esac
