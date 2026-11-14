#!/system/bin/sh
MODDIR=${0%/*}
[ ! -f "$MODDIR/disable" ] && [ ! -f "$MODDIR/remove" ] || exit 0
# Detach from the manager's frozen WebView cgroup through its existing root broker.
su -c "nohup sh '$MODDIR/control.sh' run >> '$MODDIR/service.log' 2>&1 </dev/null &"
