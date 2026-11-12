#!/system/bin/sh
# No proprietary firmware files are bundled or modified.
gxr_guard() {
  [ "$(getprop ro.build.fingerprint)" = 'samsung/xrvst2ue/xrvst2:14/UML2.260301.001/I610UES3AZJ2:user/release-keys' ] || return 1
  [ "$(sha256sum /vendor/lib64/libperception_eye_tracking_host_plugin.so | cut -d ' ' -f 1)" = b621f85c50059fcd4b4f0cb3ba9aebbeb0cee6298d6572ab64fa5ad13afb6882 ] || return 1
  [ "$(sha256sum /vendor/lib64/libperception_face_parameter_tracking_host_plugin.so | cut -d ' ' -f 1)" = b02d127f5a1ab8ac0c08c4adf6bd0f7b04a36032b110b31911af5dcf26da1a58 ] || return 1
}
