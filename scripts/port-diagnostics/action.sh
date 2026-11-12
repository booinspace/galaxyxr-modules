#!/system/bin/sh
set -eu
case "${1:-export}" in status|off) echo 'GXR_UPDATE_STATE=STOCK'; exit 0 ;; export) ;; *) exit 2 ;; esac
[ "$(id -u)" = 0 ] || { echo 'Root required'; exit 1; }
[ "$(getprop ro.build.fingerprint)" = 'samsung/xrvst2ue/xrvst2:14/UML2.260301.001/I610UES3AZJ2:user/release-keys' ] || { echo 'AZJ2 required'; exit 1; }
umask 077
OUT=$(mktemp -d /data/local/tmp/gxr-azj2-port-review.XXXXXX)
getprop ro.build.fingerprint > "$OUT/fingerprint.txt"
for source in /vendor/lib64/libqvrcamera_client.qti.so /vendor/lib64/libqvrcameraservice.so /vendor/bin/hw/android.hardware.perceptionhost /system/bin/surfaceflinger /system/bin/init /system/etc/init/cpm.rc; do
  cp "$source" "$OUT/${source##*/}"
done
(cd "$OUT" && sha256sum lib* android.hardware.perceptionhost surfaceflinger init cpm.rc) > "$OUT/SHA256SUMS"
for source in /vendor/lib64/libperception_calibration_client_plugin.so /system/framework/services.jar /system/lib64/libbinder.so /system/lib64/libbinder_ndk.so; do
  sha256sum "$source" >> "$OUT/reference-hashes.txt"
done
chmod 600 "$OUT"/*
chown 2000:2000 "$OUT"/* "$OUT"
chmod 700 "$OUT"
echo "Exported: $OUT"
echo 'Read-only firmware copies. No cameras started or settings changed.'
echo 'GXR_UPDATE_STATE=STOCK'
