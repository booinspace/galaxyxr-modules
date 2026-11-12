#!/system/bin/sh
set -u
root=/data/local/tmp/gxr-art-cmc-probe
variant=${1:-}
case "$variant" in unpatched|patched) ;; *) exit 2 ;; esac
run=${2:-1}
case "$run" in ''|*[!0-9]*) exit 2 ;; esac
[ "$(id -u)" = 2000 ] || exit 2
work="$root/$variant-$run"
mkdir "$work" || exit 2
start_time() { sed 's/.*) //' "/proc/$1/stat" 2>/dev/null | awk '{print $20}'; }
target=
target_start=
cleanup() {
    trap - EXIT INT TERM HUP
    if [ -n "$target" ] && [ "$(start_time "$target")" = "$target_start" ]; then
        kill -TERM "$target" 2>/dev/null || true
    fi
    [ -z "$target" ] || wait "$target" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT TERM HUP
printf '{"interaction":{"type":"script","path":"%s/%s.js","on_change":"ignore"},"runtime":"qjs"}\n' "$root" "$variant" > "$root/libgadget.config.so"
CLASSPATH="$root/classes.dex" app_process /system/bin --nice-name=gxr_cmc_probe local.gxr.probe.CmcProbe "$root/libgadget.so" > "$work/probe.log" 2>&1 &
target=$!
target_start=$(start_time "$target")
[ -n "$target_start" ] || exit 2
[ "$(awk '/^Uid:/{print $2}' "/proc/$target/status")" = 2000 ] || exit 2
tr '\000' ' ' < "/proc/$target/cmdline" | grep -q gxr_cmc_probe || { echo 'Unexpected test PID'; exit 2; }
printf 'PROBE_TARGET pid=%s start=%s variant=%s\n' "$target" "$target_start" "$variant"
n=0
while [ "$n" -lt 60 ]; do
    grep -q PROBE_PASS "$work/probe.log" && break
    kill -0 "$target" 2>/dev/null || break
    n=$((n + 1))
    sleep 1
done
cat "$work/probe.log"
logcat -d --pid="$target" -v brief -t 300 > "$work/logcat.log" 2>&1
grep -q PROBE_PASS "$work/probe.log"
