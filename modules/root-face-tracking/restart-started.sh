#!/system/bin/sh
MODDIR=${0%/*}
if [ ! -f "$MODDIR/disable" ] && [ ! -f "$MODDIR/remove" ]; then
  nohup sh "$MODDIR/control.sh" run >> "$MODDIR/service.log" 2>&1 </dev/null &
fi
exit 0
