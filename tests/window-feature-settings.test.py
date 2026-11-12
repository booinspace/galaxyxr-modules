"""Exercise persistent feature settings without root or a connected headset."""
import json
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="gxr-features-") as temporary:
    work = Path(temporary).resolve()
    state = work / "runtime"
    (work / "features.sh").write_text((ROOT / "scripts/curvature-features.sh").read_text().replace(
        "/dev/gxr-window-curvature", str(state)))
    tools = work / "tools"
    tools.mkdir()
    (tools / "id").write_text("#!/bin/sh\nprintf '0\\n'\n")
    (tools / "id").chmod(0o755)
    env = dict(os.environ, PATH=str(tools) + os.pathsep + os.environ["PATH"])

    def run(*args, ok=True):
        result = subprocess.run(["sh", str(work / "features.sh"), *args], env=env,
                                text=True, capture_output=True)
        assert (result.returncode == 0) == ok, (args, result.stdout, result.stderr)
        return result.stdout

    assert json.loads(run("json")) == dict(curvature=1, borderless=1, rotation=1, grab=0,
                                          runtime="STOPPED", grabRuntime="off", captionReady=0)
    assert json.loads(run("set", "0", "1", "1", "1"))["grab"] == 1
    assert run("wire") == "features 0 1 1 1\n"
    previous = (work / "features.conf").read_bytes()
    run("set", "1", "1", "1", "1;touch exploit", ok=False)
    assert (work / "features.conf").read_bytes() == previous
    assert (work / "features.conf").stat().st_mode & 0o777 == 0o600
    launch = work / "runtime-launch"
    launch.mkdir()
    (work / "runtime.log").write_text("GXR_GRAB_STATE tracking\n")
    data = json.loads(run("json"))
    assert data["runtime"] == "STARTING" and data["grabRuntime"] == "off"
    state.mkdir()
    (state / "module-path").write_text(str(work))
    (state / "status").write_text("RUNNING - supervised\n")
    data = json.loads(run("json"))
    assert data["grabRuntime"] == "tracking" and data["captionReady"] == 0
    with (work / "runtime.log").open("a") as log:
        log.write("GXR_BORDERLESS_READY\n")
    assert json.loads(run("json"))["captionReady"] == 1
    with (work / "runtime.log").open("a") as log:
        log.write("GXR_BORDERLESS_STOPPED curvature supervisor stopped\n")
    assert json.loads(run("json"))["captionReady"] == 0
    (work / "runtime.log").write_text("GXR_GRAB_STATE tracking\nGXR_GRAB_STATE waiting\n")
    assert json.loads(run("json"))["grabRuntime"] == "waiting"
    (work / "disable").touch()
    shutil.rmtree(state)
    data = json.loads(run("json"))
    assert data["runtime"] == "DISABLED" and data["grabRuntime"] == "off" and data["captionReady"] == 0
    (work / "disable").unlink()
    launch.rmdir()
    for malformed in ("CURVATURE=1\n", "CURVATURE=$(id)\n", previous.decode() + "GRAB=0\n",
                      previous.decode() + "OTHER=1\n"):
        (work / "features.conf").write_text(malformed)
        run("json", ok=False)
    run("set", "1", "1", "1", "0")
    (tools / "id").write_text("#!/bin/sh\nprintf '2000\\n'\n")
    run("set", "0", "0", "0", "0", ok=False)
print("PASS: feature defaults, persistence, atomic writes, strict parsing and root requirement")
