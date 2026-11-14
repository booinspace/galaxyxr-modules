#!/usr/bin/env bash
set -euo pipefail

usage() { echo 'usage: build-fedora.sh [--shell | -- COMMAND ...]'; }
case ${1:---shell} in
    --help) usage; exit 0 ;;
    --shell) [[ $# -le 1 ]] || { usage >&2; exit 2; } ;;
    --) [[ $# -ge 2 ]] || { usage >&2; exit 2; } ;;
    *) usage >&2; exit 2 ;;
esac
if (( EUID != 0 )); then
    exec sudo -- "$0" "$@"
fi
if [[ ${1:---shell} == --shell ]]; then
    command=(/bin/bash); terminal=(-it)
else
    shift
    command=("$@"); terminal=()
fi

for path in /dev /proc /sys /run; do
    mountpoint -q "$path" || {
        echo "Missing $path mount; launch through /usr/local/sbin/enter-fedora in Ubuntu WSL." >&2
        exit 2
    }
done
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
uid=$(stat -c %u "$repo")
gid=$(stat -c %g "$repo")
owner_home=$(getent passwd "$uid" | cut -d: -f6)
sdk=$owner_home/Android/Sdk
for path in platforms/android-37.0/android.jar cmdline-tools/latest/lib/r8.jar \
    ndk/28.2.13676358/source.properties ndk/29.0.14206865/source.properties; do
    [[ -f $sdk/$path ]] || { echo "Missing $sdk/$path; see docs/BUILDING.md" >&2; exit 2; }
done
install -d -m 700 -o "$uid" -g "$gid" \
    "$repo/.build" "$repo/.build/home" "$repo/.build/cache" "$repo/.build/output"
podman build --network=host --platform linux/amd64 -t localhost/galaxyxr-modules:azj2 "$repo"
podman run --rm "${terminal[@]}" --network=host --platform linux/amd64 \
    --user "$uid:$gid" -e HOME=/work/home -e JAVA_TOOL_OPTIONS=-Duser.home=/work/home \
    -v "$repo":/repo:ro -v "$repo/.build":/work -v "$sdk":/opt/android-sdk:ro \
    localhost/galaxyxr-modules:azj2 "${command[@]}"
