#!/system/bin/sh
set -eu
MODDIR=${0%/*}
phase=${0##*/}
phase=${phase#restart-}
phase=${phase%.sh}
sh "$MODDIR/restart.sh" "$phase"
if [ "$phase" = started ]; then
  # The launcher waits in the background until the coordinator marks ready.
  sh "$MODDIR/service.sh"
  echo 'AUTO_START_REQUESTED - startup queued after verified restart.'
fi
