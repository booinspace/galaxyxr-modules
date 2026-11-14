"""Build the disabled AZJ2 wear-aware display blanking module."""

import argparse
from pathlib import Path
import subprocess
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile

from gxr_build import class_archive, dex, package, resolve_tools

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("java", "javac", "r8", "android-jar"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "releases")
    args = parser.parse_args()
    resolve_tools(parser, args, ("java", "javac", "r8", "android_jar"))
    module = ROOT / "modules/wear-dim"
    sources = sorted((module / "src").rglob("*.java"))
    runtime = ROOT / "scripts/bread-port/PortRuntime.java"
    with tempfile.TemporaryDirectory(prefix="gxr-wear-build-") as temporary:
        work = Path(temporary)
        classes = work / "classes"
        classes.mkdir()
        subprocess.run([str(args.javac), "--release", "8", "-Xlint:-options",
                        "-classpath", str(args.android_jar), "-d", str(classes),
                        str(runtime), *(str(p) for p in sources),
                        str(ROOT / "tests/WearDimPolicyTest.java"),
                        str(ROOT / "tests/WearDisplayApiProbe.java")], check=True)
        subprocess.run([str(args.java), "-cp", str(classes), "WearDimPolicyTest"], check=True)
        (classes / "WearDimPolicyTest.class").unlink()
        probe = work / "probe.jar"
        with ZipFile(probe, "w", ZIP_DEFLATED) as archive:
            for name in ("WearDisplayApiProbe.class", "com/gxr/wear/DisplayPower.class"):
                archive.write(classes / name, name)
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "wear-display-api-probe.dex").write_bytes(
            dex(args, probe, None, work / "probe-dex"))
        (classes / "WearDisplayApiProbe.class").unlink()
        jar = work / "helper.jar"
        class_archive(classes, jar)
        payload = {p.name: p.read_bytes() for p in module.iterdir() if p.is_file()}
        payload["bin/helper.dex"] = dex(args, jar, None, work / "dex")
        payload["bin/runtime.sh"] = (ROOT / "scripts/bread-port/daemon-control.sh").read_bytes()
        for source in [runtime, Path(__file__), *sources]:
            payload["bin/source/" + source.name] = source.read_bytes()
        payload["bin/source/gxr_build.py"] = (ROOT / "scripts/gxr_build.py").read_bytes()
        if payload["disable"] or payload["skip_mount"]:
            raise ValueError("Release must install disabled without mounts")
        output = args.output / "gxr-wear-dim-azj2-0.2.0-disabled.zip"
        package(output, payload, timestamp=(2026, 11, 11, 0, 0, 0))


if __name__ == "__main__":
    main()
