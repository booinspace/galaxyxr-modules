"""Exercise low-light restart ordering and restoration with isolated property mocks."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
KEY = "ix.sysui.light_sensor.low_light_threshold"
FINGERPRINT = "samsung/xrvst2ue/xrvst2:14/UML2.260301.001/I610UES3AZJ2:user/release-keys"


class LowLightLifecycleTest(unittest.TestCase):
    def test_property_is_applied_while_stopped_and_cached_state_blocks_early_uninstall(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            module = root / "module"
            module.mkdir()
            (root / "dev").mkdir()
            commands = root / "commands"
            commands.mkdir()
            props = root / "properties.json"
            props.write_text(json.dumps({KEY: "3.0", "ix.sysui.light_sensor.enabled": "true",
                                         "ix.sysui.light_sensor.dim_light_threshold": "10.0"}))
            (root / "boot").write_text("first\n")
            (root / "pid").write_text("100\n")
            for pid in (100, 200):
                directory = root / f"proc/{pid}"
                directory.mkdir(parents=True)
                (directory / "stat").write_text(f"{pid} (systemui) S " + "0 " * 18 + f"{pid} 0\n")
            mock = '''#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
root=Path(os.environ['PORT_TEST_ROOT'])
file=root/'properties.json'
props=json.loads(file.read_text())
name=Path(sys.argv[0]).name
if name=='id': print('0')
elif name=='sha256sum': pass
elif name=='pidof': print((root/'pid').read_text().strip())
elif name=='getprop':
    fixed={'ro.product.model':'SM-I610','ro.build.fingerprint':os.environ['PORT_TEST_FINGERPRINT']}
    print(fixed.get(sys.argv[1],props.get(sys.argv[1],'')))
elif name=='resetprop':
    if sys.argv[1]=='-n': props[sys.argv[2]]=sys.argv[3]
    elif sys.argv[1]=='-d': props.pop(sys.argv[2],None)
    else: raise ValueError(sys.argv)
    file.write_text(json.dumps(props))
'''
            for name in ("id", "sha256sum", "pidof", "getprop", "resetprop"):
                target = commands / name
                target.write_text(mock)
                target.chmod(0o755)
            source = (ROOT / "modules/no-lowlight-toast/control.sh").read_text()
            source = source.replace("/dev/gxr_", str(root / "dev/gxr_"))
            source = source.replace("/proc/sys/kernel/random/boot_id", str(root / "boot"))
            source = source.replace('"/proc/$pid/stat"', '"' + str(root) + '/proc/$pid/stat"')
            script = module / "control.sh"
            script.write_text(source)
            env = {**os.environ, "PATH": f"{commands}:{os.environ['PATH']}", "PORT_TEST_ROOT": str(root),
                   "PORT_TEST_FINGERPRINT": FINGERPRINT, "KSU_RESTART_GENERATION": "test-generation"}

            def run(command, success=True):
                result = subprocess.run(["/bin/sh", str(script), command], env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
                return result.stdout

            # Checks and arming do not change a running SystemUI's property.
            self.assertIn("ARMED", run("action"))
            self.assertEqual(json.loads(props.read_text())[KEY], "3.0")
            run("prepare")
            self.assertEqual(json.loads(props.read_text())[KEY], "3.0")
            (root / "pid").write_text("")
            run("stopped")
            self.assertEqual(json.loads(props.read_text())[KEY], "-Infinity")
            self.assertEqual(json.loads(props.read_text())["ix.sysui.light_sensor.enabled"], "true")
            self.assertEqual(json.loads(props.read_text())["ix.sysui.light_sensor.dim_light_threshold"], "10.0")
            (root / "pid").write_text("100\n")
            run("started")
            self.assertNotIn("GXR_UPDATE_STATE=STOCK", run("status"))
            run("off", success=False)
            self.assertEqual(json.loads(props.read_text())[KEY], "3.0")
            # Restoring the property is insufficient while the same process caches it.
            self.assertNotIn("GXR_UPDATE_STATE=STOCK", run("status"))
            (root / "pid").write_text("200\n")
            self.assertIn("GXR_UPDATE_STATE=STOCK", run("status"))
            self.assertIn("GXR_UPDATE_STATE=STOCK", run("off"))

if __name__ == "__main__": unittest.main()
