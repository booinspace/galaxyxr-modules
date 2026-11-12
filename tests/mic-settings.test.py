"""Exercise the root settings boundary without a connected headset."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="gxr-mic-settings-") as directory:
    work = Path(directory)
    module = ROOT / "modules/mic-gain-boost"
    for name in ("settings.sh", "config.default.conf"):
        shutil.copyfile(module / name, work / name)
    (work / "control.sh").write_text("#!/bin/sh\nprintf 'KernelSU checkbox: ON\\nRUNNING\\n'\n")
    tools = work / "tools"
    tools.mkdir()
    (tools / "id").write_text("#!/bin/sh\necho 0\n")
    (tools / "id").chmod(0o755)
    env = dict(os.environ, PATH=str(tools) + os.pathsep + os.environ["PATH"])

    def run(*args, ok=True):
        result = subprocess.run(["sh", str(work / "settings.sh"), *args], env=env,
                                text=True, capture_output=True)
        assert (result.returncode == 0) == ok, (args, result.stdout, result.stderr)
        return result.stdout

    assert json.loads(run("json")) == dict(gain=15, vdOnly=1, running=True)
    assert json.loads(run("set", "25", "0")) == dict(gain=25, vdOnly=0, running=True)
    saved = (work / "config.conf").read_bytes()
    for gain, scope in (("41", "1"), ("-1", "1"), ("1.5", "1"),
                        ("15;touch injected", "1"), ("15", "$(id)")):
        run("set", gain, scope, ok=False)
        assert (work / "config.conf").read_bytes() == saved
    assert (work / "config.conf").stat().st_mode & 0o777 == 0o600
    (work / "config.conf").write_text("MODE=2\nGAIN_DB=7\n")
    assert json.loads(run("set", "0", "1"))["gain"] == 0
    assert "MODE=2\n" in (work / "config.conf").read_text()
    for bad in ("MODE=$(touch injected)\n", "MODE=1\nMODE=0\n", "OTHER=1\n", "GAIN_DB=99\n"):
        (work / "config.conf").write_text(bad)
        run("json", ok=False)
    assert not (work / "injected").exists()
    (work / "config.conf").unlink()
    (tools / "id").write_text("#!/bin/sh\necho 2000\n")
    run("set", "15", "1", ok=False)
print("PASS: mic defaults, scope, gain bounds, atomic saves and root-only validation")
