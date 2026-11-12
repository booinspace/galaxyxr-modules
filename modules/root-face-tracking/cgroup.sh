#!/system/bin/sh
# Adapted from compdoge/gxr-root-ft; move only our supervisor out of a frozen app leaf.
unified_group() {
  [ -r /proc/self/cgroup ] || return 1
  while IFS=: read -r id controllers group; do
    if [ "$id" = 0 ] && [ -z "$controllers" ]; then
      case "$group" in /*) printf '%s\n' "$group"; return 0 ;; esac
      return 1
    fi
  done < /proc/self/cgroup
  return 1
}

escape_manager_cgroup() {
  original=$(unified_group) || {
    echo "gxr-root-ft-azj2: cgroup: membership unreadable; not launching a freezer-bound relay" >>"$LOG"
    return 1
  }
  case "$original" in
    /uid_*/pid_*)
      uid=${original#/uid_}; uid=${uid%%/*}
      app_pid=${original##*/pid_}
      case "$uid:$app_pid" in
        *[!0-9:]*|:*|*:) echo "gxr-root-ft-azj2: cgroup: unexpected app leaf; not launching a freezer-bound relay" >>"$LOG"; return 1 ;;
      esac
      ;;
    *) return 0 ;; # boot or already outside an app leaf
  esac

  root=/sys/fs/cgroup
  dest=$root/gxr-root-ft-azj2
  # /proc/self/cgroup gives a hierarchy-relative path, not a mount point.
  # Do not write into an unverified bind mount or a guessed v1 hierarchy.
  if ! awk '$4=="/" && $5=="/sys/fs/cgroup" && / - cgroup2 / {found=1} END {exit !found}' /proc/self/mountinfo 2>/dev/null ||
     [ ! -r "$root/cgroup.controllers" ] || [ ! -e "$root/cgroup.procs" ] || [ -L "$dest" ]; then
    echo "gxr-root-ft-azj2: cgroup: v2 root not verified; not launching a freezer-bound relay" >>"$LOG"
    return 1
  fi
  created=0
  if [ ! -d "$dest" ]; then
    if ! mkdir -m 0755 "$dest" 2>/dev/null; then
      echo "gxr-root-ft-azj2: cgroup: cannot create relay group; not launching a freezer-bound relay" >>"$LOG"
      return 1
    fi
    created=1
  fi
  # A reused leaf could have been frozen by something else. Never enter it
  # unless its own freezer is readable and currently clear.
  if [ ! -r "$dest/cgroup.freeze" ] ||
     ! IFS= read -r frozen < "$dest/cgroup.freeze" || [ "$frozen" != 0 ]; then
    [ "$created" = 1 ] && rmdir "$dest" 2>/dev/null
    echo "gxr-root-ft-azj2: cgroup: relay group not thawed; not launching a freezer-bound relay" >>"$LOG"
    return 1
  fi
  if [ ! -e "$dest/cgroup.procs" ] ||
     ! { printf '%s\n' "$$" > "$dest/cgroup.procs"; } 2>/dev/null; then
    [ "$created" = 1 ] && rmdir "$dest" 2>/dev/null
    echo "gxr-root-ft-azj2: cgroup: migration unavailable; not launching a freezer-bound relay" >>"$LOG"
    return 1
  fi
  actual=$(unified_group) || actual=unknown
  if [ "$actual" = /gxr-root-ft-azj2 ]; then
    echo "gxr-root-ft-azj2: cgroup: supervisor migrated out of app leaf (verified)" >>"$LOG"
    return 0
  fi
  # A write can succeed but membership verification can fail. Restore this
  # shell to its original leaf before refusing the uncertain start.
  if [ "$actual" != "$original" ]; then
    if ! { printf '%s\n' "$$" > "$root$original/cgroup.procs"; } 2>/dev/null ||
       [ "$(unified_group)" != "$original" ]; then
      echo "gxr-root-ft-azj2: cgroup: migration state unknown; not launching relay" >>"$LOG"
      return 1
    fi
  fi
  [ "$created" = 1 ] && rmdir "$dest" 2>/dev/null
  echo "gxr-root-ft-azj2: cgroup: migration not verified; not launching a freezer-bound relay" >>"$LOG"
  return 1
}

