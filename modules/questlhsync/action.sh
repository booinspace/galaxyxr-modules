#!/system/bin/sh
MODDIR=${0%/*}
case "${1:-action}" in
 action) sh "$MODDIR/control.sh" start ;;
 *) exec sh "$MODDIR/control.sh" "$@" ;;
esac
