#!/system/bin/sh
export ID=gxr_saved_workspaces MAIN=local.gxr.workspaces.WorkspaceRoot MANUAL_TOGGLE=0
MODDIR=${0%/*}
# The build packages the existing cooperative daemon runtime here.
. "$MODDIR/bin/runtime.sh"
