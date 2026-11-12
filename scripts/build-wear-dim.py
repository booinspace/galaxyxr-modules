"""Build the disabled AZJ2 wear-aware display blanking module."""

import argparse
import hashlib
from pathlib import Path
import runpy
import subprocess
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("java", "javac", "r8", "android-jar"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "releases")
    args = parser.parse_args()
    for name in ("java", "javac", "r8", "android_jar"):
        path = getattr(args, name).resolve()
        if not path.is_file():
            parser.error("Missing tool: " + str(path))
        setattr(args, name, path)
    tools = runpy.run_path(str(ROOT / "scripts/build-bread-azj2.py"))
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
            tools["dex"](args, probe, None, work / "probe-dex"))
        (classes / "WearDisplayApiProbe.class").unlink()
        jar = work / "helper.jar"
        tools["class_archive"](classes, jar)
        payload = {p.name: p.read_bytes() for p in module.iterdir() if p.is_file()}
        payload["bin/helper.dex"] = tools["dex"](args, jar, None, work / "dex")
        payload["bin/runtime.sh"] = (ROOT / "scripts/bread-port/daemon-control.sh").read_bytes()
        for source in [runtime, Path(__file__), *sources]:
            payload["bin/source/" + source.name] = source.read_bytes()
        if payload["disable"] or payload["skip_mount"]:
            raise ValueError("Release must install disabled without mounts")
        payload["SHA256SUMS"] = "".join(
            f"{hashlib.sha256(data).hexdigest()}  {name}\n"
            for name, data in sorted(payload.items()) if name != "disable"
        ).encode()
        # KernelSU GXR rejects files at depth 8 or deeper during installed-tree verification.
        if any(len(Path(name).parts) >= 8 for name in payload):
            raise ValueError("Module tree is too deep for KernelSU GXR")
        hooks = {f"restart-{phase}.sh" for phase in ("prepare", "stopped", "started", "abort")}
        if "restart-prepare.sh" in payload and not hooks.issubset(payload):
            raise ValueError("Incomplete GXR coordinated-restart hooks")
        args.output.mkdir(parents=True, exist_ok=True)
        output = args.output / "gxr-wear-dim-azj2-0.2.0-disabled.zip"
        with ZipFile(output, "w", ZIP_DEFLATED) as archive:
            for name, data in sorted(payload.items()):
                entry = ZipInfo(name, (2026, 11, 11, 0, 0, 0))
                entry.create_system = 3
                entry.compress_type = ZIP_DEFLATED
                entry.external_attr = (0o100755 if name.endswith(".sh") else 0o100644) << 16
                archive.writestr(entry, data)
        with ZipFile(output) as archive:
            if archive.testzip() is not None or set(archive.namelist()) != set(payload):
                raise ValueError("ZIP integrity check failed")
            for name, data in payload.items():
                if archive.read(name) != data:
                    raise ValueError("Payload mismatch: " + name)
        digest = hashlib.sha256(output.read_bytes()).hexdigest()
        output.with_suffix(".zip.sha256").write_text(f"{digest}  {output.name}\n")
        print(f"{output}: {output.stat().st_size} bytes; SHA-256 {digest}")


if __name__ == "__main__":
    main()
