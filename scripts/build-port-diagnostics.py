"""Build a one-shot, read-only AZJ2 firmware export helper for KernelSU GXR."""
from pathlib import Path
from gxr_build import package

ROOT = Path(__file__).resolve().parents[1]
payload = {
    'module.prop': b'id=gxr_azj2_port_diagnostics\nname=Galaxy XR AZJ2 port diagnostics\nversion=0.1.0\nversionCode=1\nauthor=booinspace\ndescription=Action exports only selected stock camera/compositor files for AZJ2 port review. No runtime changes. Uninstall after export.\n',
    'action.sh': (ROOT/'scripts/port-diagnostics/action.sh').read_bytes(),
    'auto.sh': b'#!/system/bin/sh\necho GXR_UPDATE_STATE=STOCK\n',
    'service.sh': b'#!/system/bin/sh\nexit 0\n',
    'uninstall.sh': b'#!/system/bin/sh\nexit 0\n',
    'disable': b'', 'skip_mount': b'',
    'install-info.txt': b'Read-only AZJ2 port helper. Enable, run Action once, then uninstall.\nExports only selected firmware files into a private ADB-readable temporary folder.\nNo calibration profile, camera images, credentials, or runtime settings are exported.\n',
}
output = ROOT/'releases/gxr-azj2-port-diagnostics-0.1.0-disabled.zip'
package(output,payload)
print(output)
