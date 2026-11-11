"""Check the generated shared controller rejects competing injectors before attaching."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile

source = Path(sys.argv[1]).read_text()
with tempfile.TemporaryDirectory(prefix="gxr-window-conflicts-") as temporary:
    root = Path(temporary)
    module = root / "module"
    module.mkdir()
    commands = root / "commands"
    commands.mkdir()
    for name, body in {
        "id": "echo 0",
        "pidof": f'test ! -f "{root}/injector" || echo 169',
    }.items():
        path = commands / name
        path.write_text("#!/bin/sh\n" + body + "\n")
        path.chmod(0o755)
    script = module / "control.sh"
    script.write_text(source.replace("/data/adb/", str(root / "data") + "/")
                      .replace("/dev/gxr-", str(root / "dev/gxr-")))
    env = {**os.environ, "PATH": f"{commands}:{os.environ['PATH']}"}

    def rejected(text):
        for name in ("disable", "failure"):
            (module / name).unlink(missing_ok=True)
        result = subprocess.run(["sh", str(script), "run"], env=env, capture_output=True, text=True)
        assert result.returncode != 0 and text in result.stdout, result.stdout + result.stderr
        assert (module / "disable").exists()
        assert not (module / "session-open").exists()

    rotation = root / "data/modules/gxr_window_rotation"
    rotation.mkdir(parents=True)
    rejected("Disable standalone Rotation")
    (rotation / "disable").touch()
    runtime = root / "dev/gxr-window-rotation"
    runtime.mkdir(parents=True)
    rejected("Another window runtime is still active")
    runtime.rmdir()
    (root / "injector").touch()
    rejected("Another injector is active")
    (root / "injector").unlink()
    (root / "data/modules/gxr_borderless_azj2").mkdir()
    rejected("Disable separate Borderless")
print("PASS: enabled Rotation, stopping runtimes, live injectors and separate Borderless all block attachment")
